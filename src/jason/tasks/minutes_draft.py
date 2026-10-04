"""Draft a meeting's minutes from its Zoom record with the local model, section by section, then check the draft.

``draft`` finds the meeting's Zoom record for the day (``data/zoom``) and gives the model only the open meeting: the
transcript up to the executive session's break (``jason.tasks.zoom.executive_break``), who joined and for how long,
and the agenda's items (the Doc, ``data/meetings/agenda-docs``). Zoom's AI summary is not given: it can retell the
executive session. The model writes each ``MinutesSection`` by its prompt (``jason.community.minutes_template``) as
JSON, with the transcript's words that support each section; the executive session section gets only the agenda's
general headings, the meeting room's general notes (its open file, never the executive record), and an executive
decision's 4935 subject in general terms (CIV 4935(e)), never its title, motion, or votes. What the record does not show is written as a blank for the Secretary, never guessed.

The draft is written to ``data/board/minutes-draft-<date>.md`` and then asked the minutes questions
(``jason.community.question_sets.MINUTES``): each gap left is a line the Secretary fills from memory or the video. jason
posts nothing; the draft is marked DRAFT until the board approves it.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.community.minutes_template import FOOTER, SECTIONS, UNKNOWN
from jason.community.questions import grounded

_SECTION = {"type": "object", "properties": {"text": {"type": "string"}, "quotes": {"type": "array", "items": {"type": "string"}}},
            "required": ["text", "quotes"]}
_VOTE = {"type": "object", "properties": {"director": {"type": "string"}, "vote": {"type": "string"}}, "required": ["director", "vote"]}
_MOTION = {"type": "object", "properties": {
    "motion": {"type": "string"}, "moved": {"type": "string"}, "seconded": {"type": "string"},
    "votes": {"type": "array", "items": _VOTE}, "result": {"type": "string"}, "amount": {"type": "string"},
    "quote": {"type": "string"}}, "required": ["motion", "moved", "seconded", "votes", "result", "amount", "quote"]}
_ITEM = {"type": "object", "properties": {"item": {"type": "string"}, "discussion": {"type": "string"},
                                          "motions": {"type": "array", "items": _MOTION}},
         "required": ["item", "discussion", "motions"]}


def schema() -> dict[str, Any]:
    props: dict[str, Any] = {s.key: _SECTION for s in SECTIONS if s.key != "business"}
    props["business"] = {"type": "array", "items": _ITEM}
    return {"type": "object", "properties": props, "required": list(props)}


def prompt(day: date, record: dict[str, Any]) -> str:
    lines = [f"Write the minutes of the homeowners association board meeting held {day:%B} {day.day}, {day.year}, from the "
             "meeting record below. Follow each section's instructions. Use only what the record shows. Where the record "
             f"does not show something a section asks for, write exactly \"{UNKNOWN}\"; never guess a time, a name, a vote, "
             "or an amount. Speaker names in a transcript can be misspelled; use the attendance list's spelling. For each "
             "section give 'quotes': the transcript's exact words that support it, without the bracketed time and speaker. "
             "Times in the transcript are clock times; write them as clock times. The attendance list is everyone on the "
             "call, members included: call a person a director only if the record says so (a director roster is given "
             "when there is one), and never mark someone absent who is not known to be a director. The attendance minutes "
             "count the whole call, the executive session included, so they never show that someone left the open meeting "
             "early: do not write that anyone joined late or left early unless the transcript says so. Refer to people by "
             "name, never as he or she. A caller shown only by a telephone number may be a director who dialed in: when a director on the "
             "roster is not named on the call, write that director's attendance as unknown and note the unidentified "
             "caller, rather than absent, unless the transcript says the director was absent. The executive session "
             "section states only general subjects: the headings listed as its agenda, or the general matters the chair "
             "names when adjourning to it (for example \"delinquencies and legal matters\"), nothing else.", "",
             *(["Directors: " + ", ".join(record["directors"])] if record.get("directors") else []),
             *([f"Callers known not to be directors: {', '.join(n for n, c in record['knownCallers'].items() if not c.get('director'))}. "
                "A roster director who is not on the call is absent when no unidentified caller remains."]
               if any(not c.get("director") for c in record.get("knownCallers", {}).values()) else []),
             *([f"Unidentified callers: {', '.join(record['unidentified'])}."] if record.get("unidentified") else
               ["There are no unidentified callers."] if record.get("directors") else []),
             *([f"Meeting type (from the meeting's title, \"{record['topic']}\"): {record['kind']}."] if record.get("kind") else []),
             *([_quorum_fact(record["quorum"])] if (record.get("quorum") or {}).get("needed") else []),
             "Sections:"]
    for s in SECTIONS:
        lines.append(f"- {s.key}: {s.prompt}" + (" Write one entry per agenda item, in the agenda's order." if s.per_item else ""))
    decided = record.get("decisions") or []
    lines += ["", "Agenda items:", *([f"- {i}" for i in record["items"]] or ["- (no agenda on file)"]),
              *(["", "Decisions the Secretary recorded at the meeting (the record; quote each motion, its mover, second, votes, and outcome as given, and do not infer a different vote from the transcript):",
                 *[f"- {d['title']}: \"{d['motion']}\" moved by {d.get('mover') or 'unknown'}, seconded by {d.get('second') or 'unknown'}; "
                   f"votes {', '.join(f'{n} {v}' for n, v in (d.get('votes') or {}).items()) or 'not recorded'}"
                   + (f"; recused (disclosed an interest, did not vote) {', '.join(d['recused'])}" if d.get("recused") else "")
                   + f"; outcome {d.get('outcome') or 'not recorded'}"
                   for d in decided]] if decided else []),
              "", "Executive session agenda headings:", *([f"- {h}" for h in record["executive"]] or ["- (none)"]),
              "", "Attendance (name, minutes on the call):",
              *([f"- {n}: {m}" for n, m in record["attendance"]] or ["- (none)"]),
              "", "Transcript of the open meeting:", "<<<", record["transcript"], ">>>"]
    return "\n".join(lines)


KINDS = ("emergency", "special", "annual", "organizational", "regular")


def meeting_kind(title: str) -> str:
    """The meeting's type as its title names it ("Special Meeting of the Board of Directors"), or empty."""
    words = title.casefold()
    return next((k for k in KINDS if re.search(rf"\b{k}\b", words)), "")


def meeting_record(data_dir: Path, community: Any, day: date) -> dict[str, Any]:
    """The open meeting's record: agenda items, executive headings, attendance, and the transcript up to the break."""
    from jason.community.agenda_items import items_in_doc
    from jason.community.meeting_records import meeting_date
    from jason.tasks.zoom import executive_break, load_index, zoom_dir

    root = zoom_dir(data_dir)
    rows = [m for m in load_index(data_dir).get("meetings", []) if m.get("date") == day.isoformat() and m.get("folder")
            and "board" in str(m.get("kind", ""))]
    if not rows:
        raise ValueError(f"no board meeting on {day} in the Zoom record (data/zoom)")
    row = max(rows, key=lambda m: m.get("duration") or 0)
    turns, brk = executive_break(root, row, community)
    open_turns = turns[: brk.turn] if brk is not None else turns
    # Each turn at the clock time it was said (the recording's start plus its offset), so a call to order reads "7:05 PM".
    from datetime import datetime, timedelta

    try:
        started = datetime.fromisoformat(str(row.get("start")))
    except ValueError:
        started = None

    def said(t: Any) -> str:
        if started is None:
            return t.line()
        clock = started + timedelta(seconds=t.at)
        return f"[{clock:%I:%M %p}".replace("[0", "[") + f"] {t.speaker or 'unknown'}: {t.text}"

    transcript = "\n".join(said(t) for t in open_turns) if open_turns else ""
    if not transcript:
        path = root / row["folder"] / "transcript.txt"
        transcript = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        if brk is not None:
            transcript = ""                    # an executive session in a transcript that cannot be cut is not given
    attendance: dict[str, int] = {}
    parts = root / row["folder"] / "participants.json"
    for p in json.loads(parts.read_text(encoding="utf-8")) if parts.is_file() else []:
        name = p.get("name") or p.get("email") or "unknown"
        attendance[name] = attendance.get(name, 0) + int(p.get("seconds") or 0)
    items, executive = [], []
    schedule = community.meeting_schedule()
    for path in (Path(data_dir) / "meetings" / "agenda-docs").glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if meeting_date(doc.get("title", ""), doc.get("_path", ""), schedule=schedule) != day:
            continue
        inside = False
        for it in items_in_doc(doc, tuple(community.agenda_link_rules())):
            if "executive session" in it.title.lower():
                inside = True
                if it.subitem:
                    executive.append(it.subitem)
                continue
            if inside and it.subitem:
                executive.append(it.subitem)
            elif not it.subitem and "decorum" not in it.title.lower() and not re.match(r"\s*(?:see\s*:|\[)", it.title, re.I):
                inside = False
                items.append(it.title)
    # The directors: PayHOA's "Board Member" tag as last synced (jason board --members), or the community's own list.
    from jason.tasks.board_members import current_names

    hook = getattr(community, "directors", None)
    directors = [str(d) for d in (hook() if callable(hook) else ())] or current_names(data_dir)
    # What the Secretary has said about callers shown only by a number (data/board/callers.json, kept off the repo):
    # {"19168912598": {"director": false, "note": "..."}}. A caller known not to be a director cannot be one who dialed in.
    callers_file = Path(data_dir) / "board" / "callers.json"
    callers = json.loads(callers_file.read_text(encoding="utf-8")) if callers_file.is_file() else {}
    known_callers = {n: c for n, c in callers.items() if n in attendance}
    unidentified = [n for n in attendance if re.fullmatch(r"[\d\s()+-]{7,}", n) and n not in callers]
    from jason.tasks.decisions import as_dict, for_meeting, general_notes, open_only

    # The model is given the open record only: an executive-session decision is noted by its 4935 subject in general
    # terms (4935(e)), never by its title, motion, or votes; the room's executive sessions likewise (room_general).
    recorded = for_meeting(data_dir, day)
    return {"zoom": row["uuid"], "topic": str(row.get("topic") or ""), "kind": meeting_kind(str(row.get("topic") or "")),
            "items": list(dict.fromkeys(items)),
            "executive": list(dict.fromkeys(executive + room_general(data_dir, day) + general_notes(recorded))),
            "decisions": [as_dict(d) for d in open_only(recorded)],
            "knownCallers": known_callers, "unidentified": unidentified,
            "directors": directors,
            "attendance": [(n, round(s / 60)) for n, s in sorted(attendance.items(), key=lambda kv: -kv[1])],
            "transcript": transcript[:55_000], "brokeAtExecutive": brk is not None}


def room_general(data_dir: Path, day: date) -> list[str]:
    """The meeting room's executive sessions for ``day`` as the open record notes them: the 4935 subjects' general
    words with their citation, one line a session (Civil Code 4935(e): "Any matter discussed in executive session shall
    be generally noted in the minutes ..."). Read from the open room file only (``meetings/room-<date>.json``), never
    the executive record; none when the room was not used."""
    from jason.community.models.meetings import executive_general_note
    from jason.tasks.meeting_room import load

    try:
        room = load(Path(data_dir), day.isoformat())
    except (OSError, ValueError, KeyError):
        return []
    out: list[str] = []
    for s in (room.get("executive") or {}).get("sessions") or []:
        said = executive_general_note(s.get("subjects") or [])
        if said:
            out.append(f"The board met in executive session to discuss {said}.")
    return out


def _tokens(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", name.casefold()) if len(w) > 1}


def directors_on_call(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The directors in office the attendance names (a participant's words all in one director's name, or the other
    way round, and no second director matching), and the participants that could be a director but are not named:
    callers shown only by a number that the Secretary has not said are not directors."""
    found: list[str] = []
    for participant, _minutes in record.get("attendance") or []:
        words = _tokens(participant)
        if not words:
            continue
        hits = [d for d in record.get("directors") or [] if words <= _tokens(d) or _tokens(d) <= words]
        if len(hits) == 1 and hits[0] not in found:
            found.append(hits[0])
    return found, list(record.get("unidentified") or [])


def quorum_check(record: dict[str, Any], community: Any) -> dict[str, Any]:
    """The quorum, counted: the directors the record shows on the call against the board's quorum for the number in
    office (``Board.quorum``). An unidentified caller may be a director, so it can only raise the count."""
    directors = list(record.get("directors") or [])
    present, maybe = directors_on_call(record)
    board = community.board() if hasattr(community, "board") else None
    needed = board.quorum(len(directors)) if board is not None and directors else None
    if needed is None:
        standing = "unknown"
    elif len(present) >= needed:
        standing = "present"
    elif len(present) + len(maybe) >= needed:
        standing = "depends on an unidentified caller"
    else:
        standing = "not on the record"
    return {"inOffice": len(directors), "present": present, "unidentified": len(maybe), "needed": needed,
            "standing": standing}


# Subjects the open minutes give only by their general nature (Civil Code 4935): a line naming one is for the
# Secretary to read before the draft is shared.
CONFIDENTIAL = re.compile(r"\blawsuits?\b|\blitigation\b|\bsued\b|\bevict\w*|\bdelinquen\w*|\bpayment plan|"
                          r"\bdisciplin\w*|\bhearing\b|\bfined?\b|\bviolation|\blien\b|\bforeclos\w*|\bcollections?\b|"
                          r"\breimbursement assessment|\bpersonnel\b", re.I)


def _quorum_fact(q: dict[str, Any]) -> str:
    """The counted quorum, as a fact the model is given rather than asked to work out."""
    named = ", ".join(q["present"]) or "none"
    if q["standing"] == "present":
        result = "so a quorum was present"
    elif q["standing"] == "depends on an unidentified caller":
        result = "so whether a quorum was present depends on an unidentified caller: write it as unknown"
    else:
        result = "so a quorum was NOT present on the record: say so, and never write that a quorum was present"
    return (f"Quorum (counted by jason): directors in office {q['inOffice']}; a quorum is {q['needed']}; directors "
            f"identified on the call {len(q['present'])} ({named}); unidentified callers {q['unidentified']}; {result}.")


PRONOUNS = re.compile(r"\b(?:he|she|him|her|his|hers|himself|herself)\b", re.I)


def checks(record: dict[str, Any], text: str, community: Any) -> dict[str, Any]:
    """What jason counts rather than the model: the quorum, the meeting's type, the lines naming a subject the open
    minutes give only in general terms, and lines that call a person he or she."""
    quorum = quorum_check(record, community)
    claims = bool(re.search(r"\ba quorum was present\b", text, re.I) and
                  not re.search(r"\bno quorum\b|\bquorum was not present\b|\bnot a quorum\b", text, re.I))
    meeting = re.search(r"## Meeting\s+(.*?)(?=\n## )", text, re.S)
    said = meeting_kind(meeting.group(1)) if meeting else ""
    kind_differs = bool(record.get("kind") and said and said != record["kind"])
    pronouns = [ln.strip() for ln in text.splitlines() if PRONOUNS.search(ln) and not ln.startswith(("_", "#", "-  "))]
    lines, heading = [], ""
    for ln in text.splitlines():
        if ln.startswith("## "):
            heading = ln[3:].strip().casefold()
        # The executive session section names its general headings by design (4935(e)); the checks block is jason's.
        elif heading not in ("executive session", "jason's checks") and not ln.startswith(("_", "#")) \
                and CONFIDENTIAL.search(ln):
            lines.append(ln.strip())
    motions = len(re.findall(r"^\s*- \*\*Motion:\*\*", text, re.M))
    return {"quorum": quorum, "claimsQuorum": claims, "motions": motions, "confidential": lines,
            "kind": record.get("kind", ""), "kindSaid": said, "kindDiffers": kind_differs, "pronouns": pronouns}


def check_lines(found: dict[str, Any]) -> list[str]:
    """The checks as a block for the top of the draft."""
    q = found["quorum"]
    out = ["## jason's checks", ""]
    if q["needed"] is None:
        out.append("- Quorum: not counted (no directors in office are on record).")
    else:
        out.append(f"- Quorum: the record shows {len(q['present'])} of {q['inOffice']} directors in office on the call "
                   f"({', '.join(q['present']) or 'none'}), with {q['unidentified']} unidentified caller(s); a quorum "
                   f"is {q['needed']}. Standing: {q['standing']}.")
        if q["standing"] == "not on the record":
            if found["claimsQuorum"]:
                out.append("  - The draft says a quorum was present; the count does not support it. Correct the "
                           "attendance, or the statement.")
            if found["motions"]:
                out.append(f"  - {found['motions']} motion(s) are recorded as acted on without a quorum on the record. "
                           "Recite the bylaws' quorum provision to the board; whether to ratify at a meeting with a "
                           "quorum is the board's decision.")
    if found.get("kindDiffers"):
        out.append(f"- Meeting type: the draft says {found['kindSaid']}, but the meeting's title says {found['kind']}.")
    if found.get("pronouns"):
        out.append(f"- {len(found['pronouns'])} line(s) call a person he or she: use the person's name.")
    if found["confidential"]:
        out.append(f"- {len(found['confidential'])} line(s) name a subject the open minutes give only by its general "
                   "nature (Civil Code 4935): read each before the draft is shared, and keep members' names and "
                   "details out.")
    return out + [""]


def recheck(data_dir: Path, community: Any, day: date) -> dict[str, Any]:
    """The checks applied to a draft already written, without the model: the block replaces any earlier one."""
    out = Path(data_dir) / "board" / f"minutes-draft-{day.isoformat()}.md"
    text = out.read_text(encoding="utf-8")
    text = re.sub(r"\n## jason's checks\n.*?(?=\n## )", "\n", text, flags=re.S)
    found = checks(meeting_record(data_dir, community, day), text, community)
    head, _, rest = text.partition("\n## ")
    out.write_text(head.rstrip("\n") + "\n\n" + "\n".join(check_lines(found)) + "\n## " + rest, encoding="utf-8")
    return {"file": str(out), **found}


def _ask(model: str) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    from jason.tasks.model_questions import _asker

    return _asker(model)


def render(day: date, answer: dict[str, Any], transcript: str) -> tuple[list[str], list[str]]:
    """The draft's Markdown, and the sections whose support is not in the transcript (for the Secretary to check)."""
    unsupported: list[str] = []
    out = [f"# DRAFT Minutes of {day.month}/{day.day}/{day.year % 100:02d}", "",
           "_Drafted by jason from the Zoom record of the open meeting; every line is for the Secretary to check. "
           f"\"{UNKNOWN}\" marks what the record does not show._", ""]
    for s in SECTIONS:
        out += [f"## {s.heading}", ""]
        if s.key == "business":
            for n, item in enumerate(answer.get("business") or [], 1):
                out += [f"### {n}. {item.get('item', '')}", "", item.get("discussion") or UNKNOWN, ""]
                for m in item.get("motions") or []:
                    votes = "; ".join(f"{v.get('director')}: {v.get('vote')}" for v in m.get("votes") or []) or UNKNOWN
                    out += [f"- **Motion:** {m.get('motion')}" + (f" ({m['amount']})" if m.get("amount") else ""),
                            f"  - Moved: {m.get('moved') or UNKNOWN}; seconded: {m.get('seconded') or UNKNOWN}",
                            f"  - Roll call: {votes}", f"  - Result: {m.get('result') or UNKNOWN}"]
                    if m.get("quote") and not grounded(m["quote"], transcript):
                        unsupported.append(f"business: {m.get('motion', '')[:60]}")
                out.append("")
            continue
        sec = answer.get(s.key) or {}
        out += [sec.get("text") or UNKNOWN, ""]
        quotes = [q for q in sec.get("quotes") or [] if q.strip()]
        if quotes and not all(grounded(q, transcript) for q in quotes):
            unsupported.append(s.key)
        if s.authority:
            out += [f"_({s.authority})_", ""]
    out += [f"_{FOOTER}_"]
    return out, unsupported


def draft(data_dir: Path, community: Any, day: date, *, model: str = "",
          ask: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    from jason.community.question_sets import MINUTES
    from jason.community.questions import judge
    from jason.community.questions import prompt as question_prompt
    from jason.community.questions import schema as question_schema

    record = meeting_record(data_dir, community, day)
    if not record["transcript"]:
        raise ValueError(f"the {day} meeting has no open-session transcript to draft from")
    record["quorum"] = quorum_check(record, community)        # given to the model as a counted fact
    if ask is None:
        from jason.community.ollama_extractor import DEFAULT_MODEL
        from jason.local_ai import preflight

        model = model or DEFAULT_MODEL
        preflight(model)
        ask = _ask(model)
    answer = ask(prompt(day, record), schema())
    lines, unsupported = render(day, answer, record["transcript"])
    found = checks(record, "\n".join(lines), community)
    lines = lines[:4] + check_lines(found) + lines[4:]
    if found["quorum"]["standing"] == "not on the record" and found["claimsQuorum"]:
        unsupported.append("attendance (quorum)")
    text = "\n".join(lines)
    out = Path(data_dir) / "board" / f"minutes-draft-{day.isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    # The draft asked the minutes questions: what it still lacks is for the Secretary.
    answers = ask(question_prompt(MINUTES, text), question_schema(MINUTES))
    checks = [judge(q, answers.get(q.key) or {}, text, {}) for q in MINUTES.questions]
    gaps = [c["key"] for c in checks if c["verdict"] == "gap"]
    return {"file": str(out), "zoom": record["zoom"], "items": len(record["items"]), "attendance": record["attendance"],
            "unsupported": unsupported, "gaps": gaps, "unknowns": text.count(UNKNOWN), "checks": found}


__all__ = ["checks", "check_lines", "directors_on_call", "draft", "meeting_record", "prompt", "quorum_check", "recheck",
           "render", "schema"]
