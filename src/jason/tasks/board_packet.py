"""The board packet: each agenda item researched in depth, for the directors to read before the meeting.

For every action item on the agenda (proposed or on agenda, ``data/board/items.json``) the packet gives:

- **Background** and **the question for the board**, from the item;
- **The law**: each section the item's authority cites, quoted from the statute pages jason keeps (``data/authorities``,
  ``jason export-authorities``), trimmed to the subdivisions cited;
- **What the records show now**: the facts re-read from the review that found the item (the cost centers, the reserve
  transfers, the deadlines, the developer securities, the insurance), so the packet is as current as the data on disk;
- **Evidence** to open: the documents and commands behind the item;
- **Options** and a **draft motion** for the secretary to adapt (the specification's ``board_item_options()`` where it
  wrote them for the item, else a generic frame), with any notice the item needs of its own;
- **Deadlines**.

Executive session items are listed by their Civil Code 4935 subject in general words only, never by title
(``meeting_agenda.executive_lines``); their research goes to the directors separately (CIV 4935(e)). The
packet reads disk only and decides nothing: the options are the board's to weigh, and a draft motion is a starting point.

The **members' copy** (``packet(..., audience=Audience.MEMBERS)``, ``members_copy``) is drawn from the same data and is
its own review, never a flag on the directors' packet. It keeps each open item's background and question, the law
quoted, the research and records at P0 or P1 (``jason.web.access`` levels), and any notice and deadline. It leaves out
the draft motions, the option briefs, privileged and mediation material, executive matters beyond their 4935 general
line, the board's notes and standing reports, and any record above P1 or with no level on file; what it leaves out is
listed by item with a count and a reason class (``Withheld``), never the words. It is a draft: ``request_members_copy``
puts it in the approvals store for the officer the specification names (``Community.document_approvers``), and a
person posts it once approved. jason never posts or sends it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from jason.community.board_items import PRIORITY_ORDER, BoardItem, ItemStatus, Session, agenda_session
from jason.community.legal_cases import settled_lines


class Audience(Enum):
    """Whose packet: the directors' (confidential, for the directors and counsel) or the members' copy."""

    DIRECTORS = "directors"
    MEMBERS = "members"


class Withheld(Enum):
    """Why the members' copy leaves something out: the reason class it lists, with a count, never the words."""

    MOTION = "draft motion (the board's working text)"
    OPTIONS = "option brief (the board's deliberation)"
    PRIVILEGED = "privileged or mediation material (counsel's advice; Evidence Code 1119)"
    EXECUTIVE = "executive session matter beyond its general line (CIV 4935)"
    RESTRICTED = "record above P1 (contact details, submissions, or restricted material)"
    UNPLACED = "record with no level on file (closed until a person places it)"
    NOTES = "the board's notes and the reports they name"
    REPORT = "standing report, not reviewed for members"
    COMMAND = "jason command (not a record)"


MEMBER_LEVELS = ("P0", "P1")       # the levels anyone on the roster opens (jason.web.access.SEE_RULES), and a member's copy keeps
# Words that mark text as drawing on counsel's advice or on what was shared for mediation or settlement (Evidence Code
# 1119, 1152, 1154): a part carrying them is left out of the members' copy. A screen that can over-withhold, never under.
PRIVILEGED_WORDS = re.compile(r"privileged|attorney[- ]client|work product|evidence code (?:section )?11(?:19|52|54)|"
                              r"\bmediation\b|confidential|counsel'?s (?:advice|opinion)|advice of counsel", re.IGNORECASE)


def _placed(level: str, reason: Withheld | None = None) -> Callable[[Callable], Callable]:
    """Mark a researcher with the data level of what it reads (``jason.web.access``) and, when above P1, why the
    members' copy leaves it out. A researcher with no mark is a record with no level on file: closed."""
    def mark(fn: Callable) -> Callable:
        fn.level = level                    # type: ignore[attr-defined]
        fn.withheld = reason                # type: ignore[attr-defined]
        return fn
    return mark

def citations(authority: str) -> list[tuple[str, str]]:
    """("CIV 5515", "(d)") pairs from an authority string ("CIV 5515(d), (e); 5510"), read by the one citation
    grammar (``references.STATUTE_IN_TEXT``): a section whose number ends in a letter keeps it ("CIV 2924f")."""
    from jason.community.references import ABBREVIATIONS, SECTION_NUMBER, STATUTE_IN_TEXT, statute_citation

    found, code = [], ""
    for part in re.split(r"[;,]", authority or ""):
        part = part.strip()
        whole = statute_citation(part)
        m = STATUTE_IN_TEXT.search(part)
        if whole is not None and (whole.code in ABBREVIATIONS or whole.code.endswith(" CCR")):
            code = whole.code                    # the part is one citation: "Civil Code section 5515(d)", "10 CCR 2792.23"
            found.append((whole.base, whole.subdivisions))
        elif m:
            code = m.group("code")
            found.append((f"{code} {m.group('number')}", m.group("subs").replace(" ", "")))
        elif code:
            bare = re.match(rf"^({SECTION_NUMBER})((?:\([a-z0-9]+\))*)$", part)
            if bare and re.match(r"\d{3,5}(?!\d)", part):
                found.append((f"{code} {bare.group(1)}", bare.group(2)))
            elif re.match(r"^\([a-z0-9]+\)", part) and found:
                last, sub = found[-1]
                found[-1] = (last, sub + part)
    return found


def statute_excerpt(data_dir: Path, citation: str, subdivisions: str = "", *, limit: int = 1800) -> str:
    """The section's words, trimmed to the cited top-level subdivisions ("(d)(e)") when given.

    A section the publication prints in two versions under one number is quoted as the version in force today,
    followed by jason's note saying which it is and why (the versions' own operative words). Where the disk does not
    decide, each version's words are given under its own label: never the first alone."""
    from jason.tasks.export_authorities import authority_text, version_label

    found = authority_text(Path(data_dir), citation)
    if not found.get("found"):
        return ""
    if found.get("undecided"):
        return " ".join(f"{version_label(row['label'])} {_excerpt(row.get('text', ''), subdivisions, limit)}"
                        for row in found.get("versions") or [])
    excerpt = _excerpt(str(found.get("text", "")), subdivisions, limit)
    return excerpt + (f" {version_label(found['version'])}" if found.get("version") else "")


def _excerpt(words: str, subdivisions: str, limit: int) -> str:
    text = " ".join(words.split())
    # A subdivision starts the text or follows a sentence's end; "(b) of Section 5300" in a lead-in is a reference, not one.
    start = r"(?:^|(?<=[.:;]\s)|(?<=\)\s))"
    wanted = re.findall(r"\(([a-z])\)((?:\(\d+\))?)", subdivisions)
    if wanted:
        pieces = []
        for letter, paragraph in dict.fromkeys(wanted):
            m = re.search(rf"{start}\({letter}\)\s(.*?)(?=\s\([a-z]\)\s[A-Z]|$)", text)
            if not m:
                continue
            body = m.group(1)
            number = paragraph.strip("()")
            if number:
                p = re.search(rf"\({number}\)\s(.*?)(?=\s\({int(number) + 1}\)\s|$)", body)
                pieces.append(f"({letter})({number}) {p.group(1)}" if p else f"({letter}) {body}")
            else:
                pieces.append(f"({letter}) {body}")
        text = " ".join(pieces) or text
    return text[:limit] + ("..." if len(text) > limit else "")


# Researchers: re-read the facts behind an item from the review that found it. Each is marked with the level of what it
# reads (``_placed``): the association's own books and duties are P1; a legal case's file, executive-session records,
# and minutes' recaps that name executive subjects are P3.

@_placed("P1")
def _cost_centers(data_dir: Path, community: Any) -> list[str]:
    from jason.tasks.cost_centers import review

    r = review(data_dir, community)
    out = [f"{c['center']}: A.C.A. {', '.join(map(str, c['acas']))}, {c['units']} units" for c in r.get("centers", [])]
    return out + r.get("findings", [])


@_placed("P1")
def _reserve_transfers(data_dir: Path, community: Any) -> list[str]:
    from jason.tasks.reserve_transfers import review

    r = review(data_dir, community)
    out = []
    for b in r.get("borrowings", []):
        state = f"restored {b['repaidOn']}" if b["repaidOn"] else f"outstanding ${b['outstandingCents'] / 100:,.2f}"
        out.append(f"{b['day']} borrowing ${b['cents'] / 100:,.2f}: due back {b['deadline']}; {state}")
        out.extend(f"  - {g}" for g in b.get("gaps", []))
    for y in r.get("budgetYears", []):
        out.append(f"{y['year']}: contributions budgeted ${y['contributionBudgetCents'] / 100:,.2f}, paid ${y['contributionPaidCents'] / 100:,.2f}")
    return out


def _deadlines(words: tuple[str, ...]) -> Callable[[Path, Any], list[str]]:
    def research(data_dir: Path, community: Any) -> list[str]:
        from jason.tasks.deadlines import calendar

        rows = calendar(data_dir, community).get("obligations", [])
        return [f"{r['name']}: {r['standing']}, next {r.get('next') or '-'}, last {r.get('lastDone') or '-'}" + (f". {r['note']}" if r.get("note") else "")
                for r in rows if any(w in r["name"].lower() for w in words)]
    return _placed("P1")(research)


@_placed("P1")
def _securities(data_dir: Path, community: Any) -> list[str]:
    from jason.tasks.developer_security import register

    r = register(data_dir, community)
    return [f"bond {b['number']} phase {b['phase'] or '?'} {b['type'] or ''} {'$' + format(b['penalSumCents'] / 100, ',.2f') if b['penalSumCents'] else ''}: "
            f"{b['status']}" for b in r.get("bonds", [])]


def _legal_case(key: str) -> Callable[[Path, Any], list[str]]:
    def research(data_dir: Path, community: Any) -> list[str]:
        case = next((c for c in community.legal_cases() if c.key == key), None)
        if case is None:
            return []
        out = [f"{case.forum.value}{' ' + case.case_number if case.case_number else ''}; the association is {case.role.value}; {case.status.value}"]
        out += [f"{e.day} {e.step}" for e in case.events]
        if case.net_cents is not None:
            out.append(f"gross ${(case.gross_cents or 0) / 100:,.2f}; net ${case.net_cents / 100:,.2f} to {case.proceeds_account}")
        out += [f"{d.statute}: {'not met' if d.met is False else 'not shown'}: {d.evidence}" for d in case.open_duties]
        return out + settled_lines(case)
    return _placed("P3", Withheld.PRIVILEGED)(research)       # counsel's file and the settlement's figures


@_placed("P3", Withheld.RESTRICTED)
def _meeting_recordings(data_dir: Path, community: Any) -> list[str]:
    """What the association's Zoom account and jason's copy hold, from the last `jason zoom` sync."""
    from jason.tasks.zoom import confidential_mentions, load_index, zoom_dir

    index = load_index(data_dir)
    if not index:
        return ["no Zoom sync on disk; run `jason zoom`"]
    rows = [r for r in index.get("meetings", []) if r.get("cloud")]
    media = [r for r in rows if {"MP4", "M4A"} & set(r["cloud"])]
    out = [f"Zoom's cloud holds audio or video for {len(media)} meetings "
           f"({min(r['date'] for r in media)} to {max(r['date'] for r in media)}), as of {rows[0].get('cloudCheckedAt')}"] if media else []
    held = [r for r in index["meetings"] if (r.get("files") or {}).get("transcript")]
    exec_rows = [r for r in held if confidential_mentions(zoom_dir(data_dir), r)]
    out.append(f"jason's copy (data/zoom) holds {len(held)} transcripts; {len(exec_rows)} mention an executive session or a "
               f"hearing: {', '.join(r['date'] for r in exec_rows)}")
    summaries = [r for r in index["meetings"] if (r.get("files") or {}).get("summary")]
    out.append(f"AI Companion summaries held: {len(summaries)}")
    from jason.tasks.meeting_catalog import load as load_catalog

    catalog = load_catalog(data_dir)
    drive = sorted({m["date"] for m in catalog.get("meetings", []) for r in m["records"]
                    if r["where"] == "Drive" and r["kind"] in ("audio recording", "video recording", "transcript")})
    if drive:
        # What else the specification says of the recordings Drive holds (``Community.recordings_note()``), if anything.
        note = str(getattr(community, "recordings_note", str)() or "")
        out.append(f"Drive holds recordings or transcripts of {len(drive)} meetings ({drive[0]} to {drive[-1]})"
                   f"{', ' + note if note else ''} (`jason meetings`)")
    return out


@_placed("P3", Withheld.EXECUTIVE)
def _minutes_recaps(data_dir: Path, community: Any) -> list[str]:
    """The posted minutes that carry Zoom's AI recap naming executive-session subjects, from the meeting catalog."""
    from jason.tasks.meeting_catalog import load as load_catalog

    out = []
    for m in load_catalog(data_dir).get("meetings", []):
        recaps = [r for r in m["records"] if r["kind"] == "minutes" and r["note"].startswith("AI recap") and "names" in r["note"]]
        if recaps:
            places = sorted({r["location"].split("/")[0] for r in recaps})
            out.append(f"{m['date']}: {recaps[0]['note'].split('; ', 1)[1]}; posted in {', '.join(places)}")
    return out or ["no posted minutes with an AI recap naming executive subjects (run `jason meetings`)"]


@_placed("P1")
def _meeting_notices(data_dir: Path, community: Any) -> list[str]:
    """Each meeting's notice timing and delivery, and the meetings with no minutes, from the meeting catalog."""
    from jason.tasks.meeting_catalog import load as load_catalog

    out = []
    for m in load_catalog(data_dir).get("meetings", []):
        for c in m["checks"]:
            if c.startswith(("the notice went", "no notice to members", "PayHOA's email notice failed", "no minutes found")):
                out.append(f"{m['date']}: {c.split(';')[0]}")
    return out or ["no notice or minutes findings (run `jason meetings --sync`)"]


RESEARCHERS: dict[str, Callable[[Path, Any], list[str]]] = {
    "meeting-notice-and-minutes": _meeting_notices,
    "minutes-ai-recap-executive": _minutes_recaps,
    "meeting-recordings-retention": _meeting_recordings,
    "settlement-disclosure-6100": _legal_case("watt-construction-defects-2022"),
    "defect-repairs-and-941-review": _legal_case("watt-construction-defects-2022"),
    "cost-centers-not-kept": _cost_centers,
    "reserve-loan-march-2024": _reserve_transfers,
    "due-to-reserve-6531": _reserve_transfers,
    "fire-sprinkler-inspections": _deadlines(("sprinkler",)),
    "fire-alarm-deficiencies": _deadlines(("fire alarm",)),
    "insurance-renewals-2026": _deadlines(("insurance renewal",)),
    "developer-bond-phase-7": _securities,
}

def options_for(item_id: str, community: Any) -> tuple[tuple[str, ...], str]:
    """The options and the draft motion the specification wrote for an item (``Community.board_item_options()``,
    ``ItemOptions`` rows), or none: the packet then frames the item generically."""
    rows = getattr(community, "board_item_options", None)
    for row in (rows() if callable(rows) else ()):
        if row.item == item_id:
            return tuple(row.options), row.motion
    return (), ""


def item_section(item: BoardItem, data_dir: Path, community: Any, *, n: int, meeting: date | None = None) -> list[str]:
    out = [f"## {n}. {item.title}", "", f"_Priority: {item.priority.value}. Category: {item.category.value}._", "", "**Background.** " + item.summary,
           "", "**The question for the board.** " + item.ask, ""]
    cites = citations(item.authority)
    if item.authority:
        out.append(f"**The law.** {item.authority}")
        for cite, sub in cites:
            excerpt = statute_excerpt(data_dir, cite, sub)
            if excerpt:
                out.append(f"> **{cite}{sub}.** {excerpt}")
        out.append("")
    research = RESEARCHERS.get(item.id)
    if research is not None:
        try:
            facts = research(Path(data_dir), community)
        except Exception as exc:  # the packet still stands without one item's live facts
            facts = [f"(could not re-read: {exc})"]
        if facts:
            out.append("**What the records show now.**")
            out.extend(f"  - {f.strip()[2:]}" if f.startswith("  - ") else f"- {f}" for f in facts)
            out.append("")
    if item.notes:
        # the board's notes, with any {REPORT:key} run now (live_reports): the facts as of the packet, not the note
        from jason.tasks.live_reports import expand

        notes = expand(item.notes, Path(data_dir), community, context={"on": meeting or date.today()})
        out.append("**Notes.** " + notes[0] if notes else "**Notes.**")
        out += notes[1:] + [""]
    if item.evidence:
        out.append("**Evidence.** " + "; ".join(item.evidence))
        out.append("")
    options, motion = options_for(item.id, community)
    out.append("**Options.**")
    out.extend(f"{k}. {o}" for k, o in enumerate(options or ["Act as asked", "Refer for more information (to a committee, counsel, or a vendor)",
                                                            "Defer to a later meeting"], start=1))
    out.append("")
    out.append("**Draft motion.** " + (motion or f"Move that the board {item.ask[0].lower() + item.ask[1:]}"))
    if item.special_notice:
        out.append("")
        out.append(f"**Notice.** The agenda must carry: {item.special_notice}.")
    if item.due:
        out.append("")
        out.append(f"**Deadline.** {item.due.isoformat()}" + (" (passed)" if item.due < date.today() else ""))
    out.append("")
    return out


def _planned_subjects(data_dir: Path, meeting: date) -> dict[str, Any]:
    """The 4935 subject the meeting's agenda plan gives each board item, by item id; none when there is no plan."""
    from jason.tasks import agenda_plan

    try:
        plan = agenda_plan.load(Path(data_dir), meeting.isoformat())
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {k: v.get("subject") for k, v in (plan.get("items") or {}).items() if isinstance(v, dict) and v.get("subject")}


def _agenda_items(data_dir: Path) -> tuple[list[BoardItem], list[BoardItem]]:
    """The items proposed or on the agenda, by priority: the open-session ones and the executive ones."""
    from jason.tasks.board_items import load

    items = sorted((i for i in load(data_dir) if i.status in (ItemStatus.PROPOSED, ItemStatus.ON_AGENDA)),
                   key=lambda i: (PRIORITY_ORDER[i.priority], i.id))
    return ([i for i in items if agenda_session(i) is Session.OPEN],
            [i for i in items if agenda_session(i) is Session.EXECUTIVE])


def packet(data_dir: Path, community: Any, meeting: date, *, audience: Audience | str = Audience.DIRECTORS) -> list[str]:
    """The packet's Markdown lines: the directors' (confidential), or with ``audience="members"`` the members' copy
    (``members_copy``), a draft for the approver the specification names."""
    if (Audience(audience) if isinstance(audience, str) else audience) is Audience.MEMBERS:
        return members_copy(data_dir, community, meeting).lines
    open_items, executive = _agenda_items(data_dir)
    out = [f"# Board packet: {meeting:%B} {meeting.day}, {meeting.year}", "",
           "**Confidential: for the directors and counsel. Not for posting or forwarding; parts draw on privileged advice and "
           "on figures shared for mediation only (Evidence Code 1119).**", "",
           "_Prepared by jason from the association's records for the directors. Research, not advice: the options are the board's to "
           "weigh, statute text is quoted from the stored pages, and counsel's reading governs._", "", "## Contents", ""]
    out += [f"{k}. {i.title} ({i.priority.value})" for k, i in enumerate(open_items, start=1)]
    if executive:
        # By each matter's 4935 subject in the statute's words, never its title: a packet can be forwarded or served
        # beyond the directors, and a title can name the member, the party, or the matter (CIV 4935(e)).
        from jason.tasks.meeting_agenda import executive_lines
        out += ["", "Executive session (research provided to the directors separately):"]
        out += [f"- {line}" for line in executive_lines([], executive, _planned_subjects(data_dir, meeting))]
    out.append("")
    standing = getattr(community, "packet_reports", lambda: ())()
    if standing:
        # the reports every packet carries (the treasurer's report as PayHOA ran it), shown as already built
        from jason.tasks.live_reports import expand

        out += ["## Reports", ""]
        for ref in standing:
            out += expand(ref, Path(data_dir), community, context={"on": meeting}) + [""]
    for k, item in enumerate(open_items, start=1):
        out += item_section(item, Path(data_dir), community, n=k, meeting=meeting)
    return out


# --- the members' copy ----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Omission:
    """What the members' copy left out of one place (``where``: an item's heading, "Executive session", "Reports"): a
    count of one reason class. Never the words left out."""

    where: str
    reason: Withheld
    count: int


@dataclass
class MembersCopy:
    """The members' copy as drawn: its Markdown ``lines``, what it left out (``withheld``), the approver the
    specification names for it ("" when none), and the people on the roster who may record that approval."""

    meeting: date
    lines: list[str]
    withheld: list[Omission] = field(default_factory=list)
    approver: str = ""
    approver_names: tuple[str, ...] = ()

    def withheld_lines(self) -> list[str]:
        """``- <where>: <reason> (<count>); ...``, one line a place, in the copy's order."""
        places: dict[str, list[str]] = {}
        for o in self.withheld:
            places.setdefault(o.where, []).append(f"{o.reason.value} ({o.count})")
        return [f"- {where}: {'; '.join(parts)}" for where, parts in places.items()]


def _privileged(text: str) -> bool:
    return bool(PRIVILEGED_WORDS.search(text or ""))


def _plan_items(data_dir: Path, meeting: date) -> dict[str, dict[str, Any]]:
    """The meeting's agenda plan's items by id (their saved ``motion``, ``brief``, and ``packet`` files); none without one."""
    from jason.tasks import agenda_plan

    try:
        plan = agenda_plan.load(Path(data_dir), meeting.isoformat())
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {k: v for k, v in (plan.get("items") or {}).items() if isinstance(v, dict)}


def _ref_line(ref: dict[str, Any]) -> str:
    source = str(ref.get("source") or "")
    return str(ref.get("name") or ref.get("address") or "") + (f" ({source})" if source else "")


def _evidence_for_members(evidence: tuple[str, ...], data_dir: Path, held: Counter) -> list[str]:
    """The evidence a member may see (a document or citation at P0 or P1, by ``refs_from_strings``), counting the rest
    into ``held`` by reason: a command, free text no store places, or a record above P1."""
    from jason.approvals.docref import refs_from_strings

    kept = []
    for ref in refs_from_strings(list(evidence), data_dir=Path(data_dir)):
        if "command" in ref:
            held[Withheld.COMMAND] += 1
        elif "address" not in ref:
            held[Withheld.UNPLACED] += 1
        elif ref.get("level") in MEMBER_LEVELS:
            kept.append(_ref_line(ref))
        else:
            held[Withheld.RESTRICTED] += 1
    return kept


def _files_for_members(files: list[dict[str, Any]], data_dir: Path, held: Counter) -> list[str]:
    """The agenda plan's packet files a member may see: a Drive file whose copy is P0 or P1 (``drive_copies.level_of``)."""
    from jason.approvals.docref import drive_ref

    kept = []
    for f in files:
        try:
            ref = drive_ref(str(f.get("id") or ""), name=str(f.get("name") or "") or None, data_dir=Path(data_dir))
        except Exception:  # noqa: BLE001 - a file whose level cannot be read is closed: left out, and counted
            ref = {}
        if ref.get("level") in MEMBER_LEVELS:
            kept.append(_ref_line(ref))
        else:
            held[Withheld.RESTRICTED] += 1
    return kept


def _member_section(item: BoardItem, data_dir: Path, community: Any, *, n: int, planned: dict[str, Any],
                    held: Counter) -> list[str]:
    """One open item for members: its background and question, the law, the research and records at P0 or P1, and its
    notice and deadline. Each thing left out is counted into ``held`` by reason."""
    out = [f"## {n}. {item.title}", "", f"_Priority: {item.priority.value}. Category: {item.category.value}._", ""]
    if _privileged(item.summary):
        held[Withheld.PRIVILEGED] += 1
    else:
        out += ["**Background.** " + item.summary, ""]
    if _privileged(item.ask):
        held[Withheld.PRIVILEGED] += 1
    else:
        out += ["**The question for the board.** " + item.ask, ""]
    if item.authority:
        out.append(f"**The law.** {item.authority}")
        for cite, sub in citations(item.authority):
            excerpt = statute_excerpt(data_dir, cite, sub)
            if excerpt:
                out.append(f"> **{cite}{sub}.** {excerpt}")
        out.append("")
    research = RESEARCHERS.get(item.id)
    if research is not None:
        level = getattr(research, "level", "")
        if level not in MEMBER_LEVELS:
            held[getattr(research, "withheld", None) or (Withheld.RESTRICTED if level else Withheld.UNPLACED)] += 1
        else:
            try:
                facts = research(Path(data_dir), community)
            except Exception as exc:  # the copy still stands without one item's live facts
                facts = [f"(could not re-read: {type(exc).__name__})"]
            kept = [f for f in facts if not _privileged(f)]
            if len(kept) < len(facts):
                held[Withheld.PRIVILEGED] += len(facts) - len(kept)
            if kept:
                out.append("**What the records show now.**")
                out.extend(f"  - {f.strip()[2:]}" if f.startswith("  - ") else f"- {f}" for f in kept)
                out.append("")
    if item.notes:
        held[Withheld.NOTES] += 1
    records = _evidence_for_members(item.evidence, data_dir, held)
    if records:
        out += ["**Records.** " + "; ".join(records), ""]
    files = _files_for_members(list(planned.get("packet") or []), data_dir, held)
    if files:
        out += ["**Files.** " + "; ".join(files), ""]
    options, _ = options_for(item.id, community)
    held[Withheld.OPTIONS] += len(options) or 3          # the directors' packet's options, or its generic three
    if planned.get("brief"):
        held[Withheld.OPTIONS] += 1
    held[Withheld.MOTION] += 1                           # the directors' packet always carries one, its own or the frame
    if item.special_notice:
        out += [f"**Notice.** The agenda must carry: {item.special_notice}.", ""]
    if item.due:
        out += [f"**Deadline.** {item.due.isoformat()}" + (" (passed)" if item.due < date.today() else ""), ""]
    return out


def members_copy(data_dir: Path, community: Any, meeting: date) -> MembersCopy:
    """The members' copy of the packet for ``meeting`` (the module doc): drawn from the same items, plan, and stores as
    the directors' packet, with what it leaves out listed by place, count, and reason. Reads disk only; posts nothing."""
    from jason.tasks.approvals import approver_for, approvers_named
    from jason.community.base import DraftKind

    data_dir = Path(data_dir)
    open_items, executive = _agenda_items(data_dir)
    plan = _plan_items(data_dir, meeting)
    approver = approver_for(community, DraftKind.MEMBERS_PACKET)
    names = approvers_named(community, approver)
    withheld: list[Omission] = []
    sections: list[str] = []
    for k, item in enumerate(open_items, start=1):
        held: Counter = Counter()
        sections += _member_section(item, data_dir, community, n=k, planned=plan.get(item.id, {}), held=held)
        where = f"{k}. {item.title}"
        counts = [Omission(where, reason, held[reason]) for reason in Withheld if held[reason]]
        withheld += counts
        if counts:
            sections += ["_Left out of this copy: " + "; ".join(f"{o.reason.value} ({o.count})" for o in counts) + "._", ""]
    standing = getattr(community, "packet_reports", lambda: ())() if community is not None else ()
    if standing:
        withheld.insert(0, Omission("Reports", Withheld.REPORT, len(standing)))
    if executive:
        withheld.append(Omission("Executive session", Withheld.EXECUTIVE, len(executive)))

    who = (approver[0].upper() + approver[1:]) if approver else ""
    gate = (f"{who} approves it before it is posted; until then it is a draft, and jason never posts or sends it." if who else
            "No approver for the members' copy is on file (Community.document_approvers); it is not posted until one is "
            "named and approves it, and jason never posts or sends it.")
    out = [f"# Meeting packet for members: {meeting:%B} {meeting.day}, {meeting.year}", "",
           f"**The members' copy of the board packet. {gate}**", "",
           "_Drawn by jason from the directors' packet for this meeting. It leaves out the draft motions, the option briefs, "
           "privileged and mediation material, executive session matters beyond their general line, and records above P1. "
           "What it leaves out is listed below by item, with a count and the reason, never the words. Statute text is quoted "
           "from the stored pages; the board decides each item at the meeting._", "", "## Contents", ""]
    out += [f"{k}. {i.title}" for k, i in enumerate(open_items, start=1)]
    if executive:
        from jason.tasks.meeting_agenda import executive_lines

        out += ["", "Executive session (Civil Code 4935), noted generally:"]
        out += [f"- {line}" for line in executive_lines([], executive, _planned_subjects(data_dir, meeting))]
    out += ["", "## What this copy leaves out", ""]
    copy = MembersCopy(meeting, [], withheld, approver, names)
    out += copy.withheld_lines() or ["- Nothing: every part of the directors' packet is in this copy."]
    out.append("")
    copy.lines = out + sections
    return copy


def request_members_copy(data_dir: Path, community: Any, copy: MembersCopy, path: Path, *, by: str) -> dict[str, Any]:
    """Put the members' copy in the approvals store as a draft for its approver, and ask for the approval: draft, saved,
    requested, each step in ``by``'s name. Refused (ValueError) when the specification names no approver, or when the copy
    is already requested, approved, or sent (its text is fixed). Posts nothing; ``sentCommand`` stays empty because a
    person posts it."""
    from jason.tasks import approvals as store
    from jason.community.base import DraftKind

    if not copy.approver:
        raise ValueError(f"the specification names no approver for the {DraftKind.MEMBERS_PACKET.value} "
                         "(Community.document_approvers); the draft is written and no approval is requested")
    data_dir = Path(data_dir)
    try:
        key = Path(path).resolve().relative_to(data_dir.resolve()).as_posix()
    except ValueError:
        key = Path(path).as_posix()
    current = store.load(data_dir).get(key)
    if current is not None and current.get("stage") not in ("draft", "saved"):
        raise ValueError(f"{key} is {current['stage']}: its text is fixed; withdraw it or send it back first")
    meeting = copy.meeting
    text = {"kind": DraftKind.MEMBERS_PACKET.value, "title": f"Meeting packet for members, {meeting:%B} {meeting.day}, {meeting.year}",
            "date": date.today().isoformat(), "to": "All members, with the notice of the meeting",
            "via": "Posted by a person once approved (general delivery, CIV 4045)", "body": "\n".join(copy.lines),
            "signoff": "", "approver": copy.approver, "sentCommand": ""}
    held = sum(o.count for o in copy.withheld)
    store.draft(data_dir, key, text, by=by, note=f"members' copy; {held} parts left out, listed in it by reason")
    store.step(data_dir, key, "save", by=by)
    return store.step(data_dir, key, "request", by=by,
                      note=f"{copy.approver} reads the members' copy against the directors' packet before a person posts it")


__all__ = ["Audience", "MembersCopy", "Omission", "Withheld", "citations", "item_section", "members_copy", "packet",
           "options_for", "request_members_copy", "statute_excerpt", "RESEARCHERS"]
