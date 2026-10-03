"""A notice as a record: ``jason://notice/KEY``, read from the delivery ledger and what jason keeps beside it.

A notice given to members is a series book (``books.Book.NOTICE``), keyed by its delivery ledger's key
(``jason notices KEY --sync``), so no profile maps it. ``build`` gathers, read only:

- **the requirement** the key names (``notice_catalog.for_ledger``: the longest catalog key it starts with; or the
  form whose request it is, ``FORM_REQUIREMENTS``), recited: the statute's words from ``data/authorities``, the
  clocks made stricter by the governing documents (``notice_catalog.effective``), and each document clause recited
  from its own text, with the profile's paraphrase labeled as jason's reading;
- **the text sent**, if jason has it: the Markdown or HTML kept in ``data/notices/KEY/``, else the body or message
  file a batch named (``params``: ``body``, ``message``), with the letter's PDF and the subject;
- **the fill records** of its ``{QUOTE:}`` and ``{CITE:}`` tokens (``*.refs.json`` beside the text), each with the
  version's digest, and whether the words now differ;
- **the recipients plan**: the counts of ``data/notices/KEY/recipients.json`` (``jason delivery --notice RULE --ids``)
  and of the notice's batches;
- **the delivery standing** (``notice_evidence.weigh``): delivered, sent with its follow-ups owed, or sent and not
  synced; counts by channel and outcome, and the follow-ups;
- **the proof-of-notice record** (``notice_proof.build``), dated by the stage it served;
- **the stage it served**: a rule change's ``proposed`` or ``distributed`` stage, a board meeting's notice, or the
  minutes' availability, with their addresses.

Reading a notice is not restricted, but a member's identity never appears in what is shared: counts only. A member's
unit and ledger id appear only when the shelf is opened with ``private`` (``jason cite --private``); names are not in
the ledger. Nothing here writes.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.forms import FormKey
from jason.community.notices import Evidence, NoticeRequirement

ADDRESS = "jason://notice/"
# jason's own sends are keyed by a form's key (``delivery_engines.batch_id``): the requirement that form's request is.
FORM_REQUIREMENTS = {FormKey.OWNER_INFO.value: "owner-info-solicitation"}
MEETING_NOTICES = frozenset({"board-meeting", "board-meeting-executive", "board-meeting-emergency",
                             "teleconference-meeting", "reserve-transfer-consideration", "disaster-meeting-first"})
MINUTES_NOTICE = "minutes-available"
PROPOSED, ADOPTED = "rule-change-proposed", "rule-change-adopted"
CAVEAT = ("A notice record is read from jason's stores: the delivery ledger as last synced, the batches, and the files "
          "kept beside them. A posting, or a send jason did not make or read, is not on record until a person records "
          "it. Delivery is complete on deposit or transmission (Civil Code 4050); whether a notice was sufficient is "
          "for the board or counsel.")


def _rel(path: Path, data_dir: Path) -> str:
    try:
        return "data/" + Path(path).resolve().relative_to(Path(data_dir).resolve()).as_posix()
    except ValueError:
        return Path(path).name


def requirement_for(key: str) -> tuple[NoticeRequirement | None, str]:
    """The catalog row a ledger key names, and how: the longest requirement key it starts with, or the form whose
    request it is. (None, "") when neither: the proof then needs ``jason notices KEY --proof --requirement R``."""
    from jason.community.notice_catalog import for_ledger, requirement

    row = for_ledger(key)
    if row is not None:
        return row, f"the key starts with the requirement's key ({row.key})"
    for prefix, req in FORM_REQUIREMENTS.items():
        if key == prefix or key.startswith(prefix + "-"):
            return requirement(req), f"the key starts with the form's key ({prefix}), whose request this is"
    return None, ""


# ---------------------------------------------------------------------------------------------------------------
# The batches, read only.


def _batches(data_dir: Path, key: str) -> list[dict[str, Any]]:
    """The notice's batches (ids that start with KEY, test batches left out), with their items' counts."""
    path = Path(data_dir) / "batches.db"
    if not path.is_file():
        return []
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("select id, kind, title, created, status, params from batches "
                                             "order by created")]
        out = []
        for b in rows:
            bid = str(b["id"])
            if not bid.startswith(key) or "-test" in bid:
                continue
            items = con.execute("select status, payload from items where batch_id = ?", (bid,)).fetchall()
            owners = 0
            for it in items:
                try:
                    owners += len(json.loads(it["payload"] or "{}").get("ownerIds") or [])
                except (ValueError, AttributeError):
                    pass
            try:
                params = json.loads(b.get("params") or "{}")
            except ValueError:
                params = {}
            out.append({"id": bid, "kind": b.get("kind") or "", "title": b.get("title") or "",
                        "created": str(b.get("created") or ""), "status": b.get("status") or "", "params": params,
                        "items": len(items), "sent": sum(1 for it in items if it["status"] == "sent"),
                        "owners": owners})
        return out
    except sqlite3.Error:
        return []
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------------------------
# The text sent, and its fill records.


def _fills(path: Path, shelf: Any = None) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in raw.get("references") or ():
        row = {"token": r.get("token", ""), "key": r.get("key", ""), "section": r.get("section", ""),
               "asOf": r.get("as_of", ""), "citation": r.get("citation", ""), "setBy": r.get("set_by_title", ""),
               "dated": r.get("dated", ""), "digest": r.get("digest", ""), "rendered": raw.get("rendered", ""),
               "record": path.name}
        if shelf is not None and row["key"] and row["section"]:
            try:
                day = date.fromisoformat(row["asOf"]) if row["asOf"] else None
                now = shelf.section(row["key"], row["section"], day).digest
                row["digestNow"], row["same"] = now, now == row["digest"]
            except Exception:
                row["digestNow"], row["same"] = "", None
        out.append(row)
    return out


def text_sent(data_dir: Path, key: str, batches: list[dict[str, Any]], shelf: Any = None) -> dict[str, Any]:
    """The text as sent, if jason has it, and the fill records of its tokens: ``data/notices/KEY/`` first (a rendered
    Markdown or HTML file), then a batch's ``body`` or ``message``; the letter's PDF and the subject as named."""
    data_dir = Path(data_dir)
    out: dict[str, Any] = {"words": "", "source": "", "subjects": [], "files": [], "fills": []}
    folder = data_dir / "notices" / key
    sidecars: list[Path] = []
    if folder.is_dir():
        for ext in (".md", ".html", ".htm", ".txt"):
            for path in sorted(folder.glob(f"*{ext}")):
                if ".preview." in path.name:
                    continue
                if not out["words"]:
                    out["words"], out["source"] = path.read_text(encoding="utf-8", errors="replace"), _rel(path, data_dir)
                else:
                    out["files"].append({"what": "kept with the notice", "path": _rel(path, data_dir)})
        sidecars += sorted(folder.glob("*.refs.json"))
        for path in sorted(folder.glob("*.pdf")):
            out["files"].append({"what": "kept with the notice (a PDF)", "path": _rel(path, data_dir)})
    for b in batches:
        params = b.get("params") or {}
        if params.get("subject") and params["subject"] not in out["subjects"]:
            out["subjects"].append(str(params["subject"]))
        if not out["words"] and params.get("body"):
            out["words"], out["source"] = str(params["body"]), f"batch {b['id']} (its body)"
        message = params.get("message")
        if message:
            path = Path(str(message))
            if not out["words"] and path.is_file():
                out["words"] = path.read_text(encoding="utf-8", errors="replace")
                out["source"] = (f"{_rel(path, data_dir)} (the message batch {b['id']} sent from; each member's own "
                                 "fills are not in it)")
            side = path.with_name(path.name + ".refs.json")
            if side.is_file() and side not in sidecars:
                sidecars.append(side)
        if params.get("pdf"):
            row = {"what": f"the letter as mailed (batch {b['id']})", "path": _rel(Path(str(params["pdf"])), data_dir)}
            if params.get("pages"):
                row["pages"] = params["pages"]
            if row not in out["files"]:
                out["files"].append(row)
    for side in sidecars:
        out["fills"] += _fills(side, shelf)
    return out


def recipients(data_dir: Path, key: str, batches: list[dict[str, Any]]) -> dict[str, Any]:
    """The recipients plan's counts: the ids file kept with the notice (``jason delivery --notice RULE --ids
    data/notices/KEY/recipients.json``), and each batch's items. Counts only."""
    out: dict[str, Any] = {"plan": None, "batches": []}
    path = Path(data_dir) / "notices" / key / "recipients.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            out["plan"] = {"rule": raw.get("notice", ""), "unitTag": raw.get("unitTag", ""),
                           "emails": len(raw.get("emailMembershipIds") or []), "letters": len(raw.get("mail") or []),
                           "secondaryCopies": len(raw.get("secondary") or []), "source": _rel(path, data_dir)}
        except (OSError, ValueError):
            out["plan"] = {"source": _rel(path, data_dir), "unreadable": True}
    for b in batches:
        row = {"batch": b["id"], "kind": b["kind"], "items": b["items"], "sent": b["sent"], "status": b["status"]}
        if b["owners"]:
            row["owners"] = b["owners"]
        out["batches"].append(row)
    return out


# ---------------------------------------------------------------------------------------------------------------
# The stage it served.


def _rule_change_stage(key: str, community: Any, data_dir: Path, stores: Any, books: Any, today: date
                       ) -> dict[str, Any] | None:
    from jason.community.revisions import Stage
    from jason.tasks import record_stages as rs

    stage = Stage.DISTRIBUTED if key.startswith(ADOPTED) else Stage.PROPOSED
    rest = key.split("-", 3)[-1] if key.count("-") >= 3 else ""
    found = [r for r, _, _ in rs.records(community) if r.key and r.key in rest]
    if not found:
        return {"stage": stage.value, "what": "a rule change's notice", "ruleChange": rest, "found": False,
                "note": "no rule change in the profile's rows or the specification has this key"}
    record = max(found, key=lambda r: len(r.key))
    h = next((x for x in rs.rule_change_histories(community, data_dir, on=today, stores=stores) if x.key == record.key),
             None)
    out: dict[str, Any] = {"stage": stage.value, "ruleChange": record.key, "title": record.title,
                           "document": record.document, "found": True,
                           "what": ("the notice of the proposed change (4360(a))" if stage is Stage.PROPOSED else
                                    "the notice of the adopted change (4360(c))"),
                           "event": record.decided.isoformat() if record.decided else None}
    if h is not None:
        book = books.key(record.document) if books is not None else record.document
        v = next((v for v in h.versions if v.stage is stage), None)
        if v is not None:
            out["version"] = f"{book}{v.label()}"
        clock = h.clocks[0 if stage is Stage.PROPOSED else 1]
        out["clock"] = {"authority": clock.authority, "timing": clock.timing,
                        "deadline": clock.deadline.isoformat() if clock.deadline else None,
                        "standing": clock.standing.value, "notice": clock.notice}
        out["history"] = f"jason record-stages --change {record.key}"
    return out


def _meeting_stage(key: str, requirement: NoticeRequirement | None, community: Any, stores: Any, today: date,
                   how: str) -> dict[str, Any] | None:
    from jason.community.notice_catalog import effective
    from jason.community.notices import Anchor
    from jason.tasks.notice_evidence import date_in, judge, meeting_notices

    day = date_in(key)
    if day is None:
        return None
    if requirement is not None and requirement.key == MINUTES_NOTICE:
        return {"stage": "the minutes' availability (4950(a))", "meeting": day.isoformat(), "event": day.isoformat(),
                "minutes": f"jason://min/{day.isoformat()}", "how": how}
    req_key = requirement.key if requirement is not None and requirement.key in MEETING_NOTICES else "board-meeting"
    out = {"stage": "the notice of the board meeting (4920)", "meeting": day.isoformat(), "event": day.isoformat(),
           "agenda": f"jason://agenda/{day.isoformat()}", "minutes": f"jason://min/{day.isoformat()}", "how": how}
    try:
        _, clocks, _, _ = effective(req_key, community)
        timing = next((t for t in clocks if t.anchor is Anchor.MEETING and t.least is not None), None)
    except KeyError:
        timing = None
    if timing is not None:
        deadline = timing.window(day)[1]
        verdict, r = judge(meeting_notices(stores, day), deadline, today)
        out["clock"] = {"requirement": req_key, "timing": timing.describe(), "deadline": deadline.isoformat(),
                        "standing": verdict.value, "record": r.what if r else "", "strength": r.strength.value if r
                        else "", "notice": r.address if r else ""}
    return out


def stage_of(key: str, requirement: NoticeRequirement | None, community: Any, data_dir: Path, stores: Any,
             books: Any, today: date) -> dict[str, Any] | None:
    """The stage the notice served: a rule change's proposed or distributed stage, a meeting's notice, or the
    minutes' availability. A key that names no requirement but carries a meeting's day is read as that meeting's
    notice, and says it is a reading."""
    if key.startswith((PROPOSED, ADOPTED)):
        return _rule_change_stage(key, community, data_dir, stores, books, today)
    if requirement is not None and (requirement.key in MEETING_NOTICES or requirement.key == MINUTES_NOTICE):
        return _meeting_stage(key, requirement, community, stores, today, "the key names the requirement and the day")
    if requirement is None:
        from jason.tasks.notice_evidence import date_in

        day = date_in(key)
        if day is not None and day in stores.meetings():
            return _meeting_stage(key, None, community, stores, today,
                                  "a reading: the day in its key is a meeting on record; a key that starts with "
                                  f"board-meeting (board-meeting-{day}) names it")
    return None


# ---------------------------------------------------------------------------------------------------------------
# The requirement, recited.


def _passage(text: str, pattern: str) -> str:
    """The sentence of the statute that carries the row's words, as written."""
    if not pattern or not text:
        return ""
    flat = " ".join(text.split())
    m = re.search(pattern, flat, re.I)
    if not m:
        return ""
    lo = flat.rfind(". ", 0, m.start())
    hi = flat.find(". ", m.end())
    return flat[lo + 2 if lo != -1 else 0: hi + 1 if hi != -1 else len(flat)].strip()


def recite(requirement: NoticeRequirement, community: Any, shelf: Any, how: str) -> dict[str, Any]:
    """The requirement as the catalog states it, its statute's words, its clocks made stricter by the documents, and
    each document clause recited from its own text (the profile's paraphrase is jason's reading, labeled so)."""
    from jason.community.notice_catalog import effective

    row, clocks, notes, touching = effective(requirement.key, community)
    out: dict[str, Any] = {
        "key": row.key, "title": row.title, "statute": row.statute, "also": list(row.also), "how": how,
        "recipients": row.recipients.value, "kind": row.kind.value if row.kind else "",
        "methods": [m.value for m in row.methods], "clocks": [t.describe() for t in clocks],
        "content": list(row.content), "evidence": [e.value for e in row.proof()], "verified": row.verified,
        "note": row.note, "caveat": row.caveat, "notes": list(notes), "words": "", "passage": "", "source": "",
        "address": "", "clauses": []}
    if shelf is not None:
        law = shelf(row.statute)
        if law.found:
            out["words"], out["source"] = law.text, str(law.version.get("source") or "")
            out["passage"] = _passage(law.text, row.words)
            out["address"] = "law:" + (law.target.id if law.target is not None else row.statute)
    for p in touching:
        clause = {"citation": p.citation, "comparison": p.comparison.value, "reading": p.says, "lead": p.lead,
                  "words": "", "address": ""}
        if shelf is not None and p.document and p.section:
            try:
                c = shelf.doc(p.document).section(p.section)
                if c.found:
                    clause["words"], clause["address"], clause["citation"] = c.text, c.address, str(c)
            except Exception:
                pass
        out["clauses"].append(clause)
    return out


# ---------------------------------------------------------------------------------------------------------------
# The proof, shared without identities.


def proof(requirement: NoticeRequirement, community: Any, attempts: list[Any], *, general: bool, posted: str,
          event: date | None, have: set[Evidence], key: str, private: bool) -> dict[str, Any]:
    from jason.community.notice_catalog import effective
    from jason.tasks import notice_proof
    from jason.tasks.notice_evidence import date_in
    from jason.tasks.notice_ledger import standing

    _, clocks, notes, _ = effective(requirement.key, community)
    found = standing(attempts, general=general)
    p = notice_proof.build(requirement, clocks=clocks, event=event, posted=date_in(posted) if general else None,
                           standings=found, general=general, have=have, ledger_key=key, notes=notes)
    out = {"requirement": requirement.key, "title": requirement.title, "statute": requirement.statute,
           "event": event.isoformat() if event else None,
           "windows": [{"clock": t.describe(), "from": a.isoformat() if a else None, "through": b.isoformat() if b
                        else None, "judges": t.delivery} for t, a, b in p.windows],
           "wentOut": p.delivered.isoformat() if p.delivered else None,
           "onTime": p.on_time, "members": p.members, "reached": p.reached, "unreached": len(p.unreached),
           "late": len(p.late), "items": [{"evidence": i.evidence.value, "status": i.status.value,
                                           "detail": i.detail} for i in p.items],
           "notes": list(p.notes), "complete": p.complete}
    if private:
        out["unreachedMembers"], out["lateMembers"] = list(p.unreached), list(p.late)
    return out


def proof_lines(p: dict[str, Any]) -> list[str]:
    out = [f"{p['title']} [{p['requirement']}; {p['statute']}]" + (f"; the event {p['event']}" if p["event"] else
                                                                  "; no event date: the windows are not judged")]
    for w in p["windows"]:
        span = (f": from {w['from']}" if w["from"] else "") + (f" through {w['through']}" if w["through"] else "")
        out.append(f"clock: {w['clock']}{span}" + ("" if w["judges"] else " (governs another act, not the delivery)"))
    if p["wentOut"]:
        out.append(f"went out {p['wentOut']}: " + {True: "in time", False: "OUTSIDE the window",
                                                   None: "not judged"}[p["onTime"]])
    if p["members"]:
        out.append(f"members: {p['reached']} of {p['members']} reached; {p['unreached']} not reached; "
                   f"{p['late']} reached late")
    out += [f"[{i['status']}] {i['evidence']}" + (f" ({i['detail']})" if i["detail"] else "") for i in p["items"]]
    out += [f"not reached: {w}" for w in p.get("unreachedMembers", [])]
    out += [f"late: {w}" for w in p.get("lateMembers", [])]
    out += [f"note: {n}" for n in p["notes"]]
    out.append("complete" if p["complete"] else "not yet complete")
    return out


# ---------------------------------------------------------------------------------------------------------------
# The record.


def build(key: str, *, community: Any = None, data_dir: Path | None = None, shelf: Any = None, private: bool = False,
          today: date | None = None, stores: Any = None) -> dict[str, Any] | None:
    """The notice ``key`` as a record (see the module's docstring); None when jason holds nothing under that key (no
    ledger attempts, no batch, no folder)."""
    from jason.tasks.notice_evidence import posting, read, weigh
    from jason.tasks.schedule_evidence import Stores

    if shelf is not None:
        community = community if community is not None else shelf.community
        data_dir = data_dir if data_dir is not None else shelf.data_dir
    data_dir = Path(data_dir) if data_dir is not None else Path("data")
    today = today or date.today()
    stores = stores or Stores(data_dir, community)
    attempts_by, kinds, synced = read(data_dir)
    attempts = attempts_by.get(key, [])
    batches = _batches(data_dir, key)
    folder = data_dir / "notices" / key
    if not attempts and not batches and not folder.is_dir() and key not in kinds:
        return None
    general, posted = kinds.get(key, (False, ""))
    requirement, how = requirement_for(key)
    rec = weigh(key, attempts, general=general, posted=posted, requirement=requirement, local_day=stores.local_day)
    if rec is None and general and posted:
        rec = posting(key, posted, requirement)
    text = text_sent(data_dir, key, batches, shelf)
    books = getattr(shelf, "books", None)
    stage = stage_of(key, requirement, community, data_dir, stores, books, today)
    event = None
    if stage and stage.get("event"):
        event = date.fromisoformat(stage["event"])
    out: dict[str, Any] = {"key": key, "address": f"{ADDRESS}{key}", "proofAddress": f"{ADDRESS}{key}/proof",
                           "requirement": recite(requirement, community, shelf, how) if requirement else None,
                           "text": text, "recipients": recipients(data_dir, key, batches), "stage": stage,
                           "private": private, "caveat": CAVEAT}
    if rec is not None:
        counts = Counter(f"{a.channel} {a.status.value}" for a in attempts)
        standing_row = rec.row()
        standing_row.update({"byOutcome": dict(sorted(counts.items())), "synced": synced.get(key, "")})
        if private:
            from jason.tasks.notice_ledger import standing

            standing_row["memberRows"] = [
                {"unit": s.unit, "membershipId": s.membership_id, "reached": s.reached,
                 "attempts": [f"{a.channel} {a.status.value}" for a in s.attempts],
                 "followUps": [f.key for f, _ in s.follow_ups]} for s in standing(attempts, general=general)]
        out["standing"] = standing_row
    else:
        out["standing"] = None
    if requirement is not None:
        have = {Evidence.TEXT_AS_SENT} if text["words"] or text["files"] else set()
        out["proof"] = proof(requirement, community, attempts, general=general, posted=posted, event=event, have=have,
                             key=key, private=private)
    else:
        out["proof"] = None
    return out


def sections(r: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """The record as titled lists of lines for a page (a line that starts with "> " is quoted words)."""
    out: list[tuple[str, list[str]]] = []
    req = r.get("requirement")
    if req:
        lines = [f"{req['title']} [{req['key']}; {req['statute']}" + (f"; also {', '.join(req['also'])}"
                                                                      if req["also"] else "") + "]",
                 f"Found by: {req['how']}.", f"To: {req['recipients']}" + (f"; {req['kind']}" if req["kind"] else "")
                 + (f"; by {', or '.join(req['methods'])}" if req["methods"] else "") + "."]
        lines += [f"Clock: {c}." for c in req["clocks"]] + [f"Content: {c}." for c in req["content"]]
        lines += [f"Note: {n}" for n in req["notes"]]
        if req["caveat"]:
            lines.append(f"For counsel: {req['caveat']}")
        if req["words"]:
            lines += ["", f"The statute's words ({req['statute']}, as exported: {req['source']}):", ""]
            lines += [f"> {x}" if x.strip() else ">" for x in req["words"].strip().splitlines()]
        out.append(("The requirement", lines))
        if req["clauses"]:
            lines = []
            for c in req["clauses"]:
                lines.append(f"{c['citation']} ({c['comparison']})" + (f" `{c['address']}`" if c["address"] else "")
                             + ":")
                if c["words"]:
                    lines += [f"> {x}" if x.strip() else ">" for x in c["words"].strip().splitlines()]
                lines.append(f"jason's reading, not the clause: {c['reading']}")
                if c["lead"]:
                    lines.append(f"Lead for the conflict register: {c['lead']}")
                lines.append("")
            out.append(("The governing documents' clauses", lines))
    else:
        out.append(("The requirement", ["No catalog requirement fits this key: name a notice's batches with its "
                                        "requirement's key (board-meeting-2099-01-14), or give the proof one (jason "
                                        f"notices {r['key']} --proof --requirement KEY)."]))
    t = r["text"]
    lines = [f"Subject: {s}" for s in t["subjects"]]
    lines.append(f"Text: {t['source']} (recited above)." if t["words"] else
                 "jason does not have the text as sent: keep it in data/notices/KEY/ (the rendered Markdown), or "
                 "send it from a batch that names its message.")
    lines += [f"{f['what']}: {f['path']}" + (f" ({f['pages']} pages)" if f.get("pages") else "") for f in t["files"]]
    out.append(("The notice as sent", lines))
    if t["fills"]:
        lines = []
        for f in t["fills"]:
            same = {True: "", False: "; the words now differ", None: "; not compared"}.get(f.get("same"), "")
            lines.append(f"{f['token']} -> {f['citation']}" + (f", set by {f['setBy']}" if f["setBy"] else "")
                         + (f" ({f['dated']})" if f["dated"] else "") + f"; digest {f['digest']}{same}")
        out.append(("Fill records ({QUOTE:} and {CITE:})", lines))
    rc = r["recipients"]
    lines = []
    if rc["plan"]:
        p = rc["plan"]
        lines.append(f"Plan ({p.get('source')}): {p.get('emails', '?')} emails, {p.get('letters', '?')} letters, "
                     f"{p.get('secondaryCopies', '?')} secondary copies" + (f"; reach {p['unitTag']}" if p.get("unitTag")
                                                                             else ""))
    for b in rc["batches"]:
        lines.append(f"Batch {b['batch']} ({b['kind']}): {b['items']} items, {b['sent']} sent"
                     + (f", {b['owners']} owners" if b.get("owners") else "") + f"; {b['status']}")
    if not lines:
        lines.append("No recipients plan or batch is kept with this notice (jason delivery --notice RULE --ids "
                     "data/notices/KEY/recipients.json keeps one).")
    out.append(("Recipients", lines))
    s = r.get("standing")
    if s:
        lines = [s["describe"] + ".", "By outcome: " + "; ".join(f"{k} {v}" for k, v in s["byOutcome"].items()) + ".",
                 f"Synced {str(s['synced'])[:16]}."]
        lines += [f"Owed: {f['members']} {f['key']} [{f['force']}; {f['authority']}]" for f in s["followUps"]]
        if s["asks"]:
            lines.append(f"{s['asks']} members to ask for an address (reached another way).")
        if s["general"]:
            lines.append(f"Recorded as a general notice, posted: {s['posted'] or '(where and when not given)'}.")
        for m in s.get("memberRows") or ():
            lines.append(f"{m['unit'] or 'unit ?'} (member {m['membershipId']}): {', '.join(m['attempts'])}"
                         + (f" -> {', '.join(m['followUps'])}" if m["followUps"] else ""))
        if not r["private"]:
            lines.append("Counts only: a member's unit is shown only privately (jason cite --private).")
        out.append(("Delivery", lines))
    else:
        out.append(("Delivery", [f"Nothing in the delivery ledger under {r['key']} (jason notices {r['key']} --sync "
                                 "reads it from PayHOA)."]))
    if r.get("proof"):
        out.append(("Proof of notice", proof_lines(r["proof"]) + [f"Address: {r['proofAddress']}"]))
    st = r.get("stage")
    if st:
        lines = [f"{st.get('what') or st['stage']}" + (f": {st.get('title')}" if st.get("title") else "")
                 + (f" ({st['ruleChange']})" if st.get("ruleChange") else "")
                 + (f", the meeting of {st['meeting']}" if st.get("meeting") else "") + "."]
        if st.get("how"):
            lines.append(f"How: {st['how']}.")
        if st.get("version"):
            lines.append(f"Version: {st['version']} (jason record-stages --change {st.get('ruleChange')}).")
        for k in ("agenda", "minutes"):
            if st.get(k):
                lines.append(f"{k.capitalize()}: {st[k]}")
        c = st.get("clock")
        if c:
            lines.append(f"Clock: {c.get('timing', '')}, by {c.get('deadline')}: {c.get('standing')}"
                         + (f" ({c['strength']})" if c.get("strength") else "")
                         + (f" [{c['notice']}]" if c.get("notice") else ""))
        if st.get("note"):
            lines.append(st["note"])
        out.append(("The stage it served", lines))
    return out


def nodes(r: dict[str, Any], *, proof_page: bool = False) -> list[dict[str, Any]]:
    """The page's links: the proof (or back to the notice), the statute, and the stage's records."""
    out: list[dict[str, Any]] = []
    if proof_page:
        out.append({"kind": "the notice", "caption": r["key"], "address": r["address"]})
    elif r.get("proof"):
        out.append({"kind": "proof of notice", "caption": r["key"], "address": r["proofAddress"]})
    req = r.get("requirement")
    if req and req.get("address"):
        out.append({"kind": "the statute", "caption": req["statute"], "address": req["address"]})
    for c in (req or {}).get("clauses") or ():
        if c.get("address"):
            out.append({"kind": "a governing document's clause", "caption": c["citation"], "address": c["address"]})
    st = r.get("stage") or {}
    for k in ("agenda", "minutes"):
        if st.get(k):
            out.append({"kind": f"the meeting's {k}", "caption": st.get("meeting", ""), "address": st[k]})
    return out


__all__ = ["ADDRESS", "CAVEAT", "FORM_REQUIREMENTS", "build", "nodes", "proof", "proof_lines", "recipients",
           "recite", "requirement_for", "sections", "stage_of", "text_sent"]
