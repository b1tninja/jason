"""The revision histories of the association's rule changes and minutes, read from disk (``jason record-stages``).

**Rule changes.** Each rule change the profile names (``Community.rule_change_records()``, the association's own past
and pending changes) and each draft in the specification (``Community.rule_changes()``, what ``jason rule-change``
builds the notices from) gets a history (``jason.community.record_stages``): its text as drafted, the notice of the
proposed change (4360(a)), the decision (4360(b)), and the notice of the adopted change (4360(c)), with the 28-day and
15-day clocks and the members' 30 days to ask for a reversal vote (4365). The evidence:

- **files** whose names the row's pattern matches, on Drive (``data/drive/files.json``: the earlier of a file's created
  and modified days, the day it was written by) and in the PayHOA library (undated);
- **sends**: PayHOA's communications log, jason's sends, the Mailroom log, and the notice delivery ledger (keys
  ``rule-change-proposed-<key>`` and ``rule-change-adopted-<key>``);
- **email**: a copy sent from the association's mail (``data/gmail/correspondence.json``); to whom is not read;
- **the minutes** of the decision meeting: the passage that names the change;
- **tasks**: a Google Task that plans a step (``data/schedule/google-read.json``), as a plan, never as done;
- for a draft in the specification: its board page (``data/board/rule-change-<slug>.md``).

Files whose names say "Notice of Proposed Rule Change" or "Notice of Adopted Rule Change" that no row claims, and
minutes passages about rule changes on days no row names, are listed as leads for a person to read.

**Minutes.** Each meeting on record (``schedule_evidence.Stores.held``, and the Zoom index's board meetings) gets a
history: each copy of its minutes on file with its date, the 30-day clock (4950(a)) read as ``jason schedule-evidence
--watch`` reads it (``minutes_on_record``), the later meetings whose minutes carry its approval (stated, or only
listed on the approval item), and corrections. Executive-session minutes show only that they exist and their date.

It reads disk only, writes nothing, and decides nothing. A miss stays a miss: "none on record" is not "none given".
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jason.community.record_stages import (CORRECTED_NAME, DRAFT_NAME, MINUTES_AVAILABLE, RULE_CHANGE_FILE, Approval,
                                           Evidence, MeetingKind, MinutesCopy, MinutesHistory, Outcome,
                                           RuleChangeHistory, RuleChangeRecord, StageClock, Standing, Strength,
                                           approval_items, file_stage, minutes_versions, rule_change_history)
from jason.community.revisions import Stage

APPROVAL_LOOKAHEAD_DAYS = 400       # a later meeting's minutes this far on can carry an approval
MAX_LEADS = 12
BOARD_KINDS = {"board meeting"}                                   # the Zoom index's kinds (``zoom.models.MeetingKind``)
EXECUTIVE_KINDS = {"executive session", "disciplinary hearing"}
MEMBER_KINDS = {"annual meeting of members", "members' meeting", "special meeting of members"}
_ADOPT = re.compile(r"\badopt\w*|\bapprov\w*|\bMSC\b(?!\s*-\s*Motion)|M/S/P", re.I)
_RULE_LEAD = re.compile(r"\brule changes?\b|\bproposed rules?\b|\brevis\w* [^.]{0,30}\brules\b|\bfine schedule\b"
                        r"|\belection rules\b|\boperating rules?\b", re.I)
CAVEATS = (
    "None on record is not none given: a notice posted or mailed where jason does not look, or minutes made available "
    "that way, are not on disk. A person confirms and records what was done.",
    "A file's date is the day it was written by (the earlier of Drive's created and modified days), not the day it "
    "reached the members.",
    "An approval named on a later meeting's approval item, with no words saying it passed, is 'listed', not 'stated'.",
    "Minutes on record in time means a copy dated by the deadline (sent, or created on Drive), as the meeting watch "
    "reads it; when members could first read it is not kept.",
    "Executive-session minutes are restricted (Civil Code 4935): only that they exist and their date are shown.",
    "Whether a rule is on a subject Civil Code 4355(a) lists, or a change the law required without discretion "
    "(4355(b)(4)), is for counsel: every change here is read against 4360.",
)


def _day(value: Any) -> date | None:
    text = str(value or "")
    try:
        return date.fromisoformat(text[:10]) if len(text) >= 10 else None
    except ValueError:
        return None


def _stores(community: Any, data_dir: Path, stores: Any = None) -> Any:
    from jason.tasks.schedule_evidence import Stores

    return stores or Stores(Path(data_dir), community)


def _text(stores: Any, doc_id: str) -> str:
    return stores.text(doc_id).replace("​", " ")


def _passage(text: str, m: re.Match, width: int = 120) -> str:
    return " ".join(text[max(0, m.start() - width):m.end() + width].split())


def _words(phrase: str) -> re.Pattern:
    """A phrase found as written, whatever the spacing between its words (a PDF's text breaks lines anywhere)."""
    return re.compile(r"\s+".join(re.escape(w) for w in phrase.split()), re.I)


# ---------------------------------------------------------------------------------------------------------------
# Rule changes.


def records(community: Any) -> list[tuple[RuleChangeRecord, str, Any]]:
    """Each rule change to read: the profile's rows, then each draft in the specification no row already names, as
    (the record, its origin, the specification's ``RuleChange`` or None)."""
    rows = tuple(getattr(community, "rule_change_records", lambda: ())() or ())
    specs = {c.key: c for c in tuple(getattr(community, "rule_changes", lambda: ())() or ())}
    out: list[tuple[RuleChangeRecord, str, Any]] = [(r, "record", specs.get(r.key)) for r in rows]
    named = {r.key for r in rows}
    for key, change in specs.items():
        if key not in named:
            out.append((RuleChangeRecord(change.key, change.title, change.document, change.document_title,
                                         outcome=Outcome.PENDING), "specification", change))
    return out


def _drive_rows(stores: Any) -> list[dict[str, Any]]:
    return [r for r in stores.drive_files().values()
            if not str(r.get("mimeType") or "").startswith(("audio/", "video/", "image/"))]


def _written(row: dict[str, Any]) -> date | None:
    days = [d for d in (_day(row.get("created")), _day(row.get("modified"))) if d]
    return min(days) if days else None


def _file_evidence(record: RuleChangeRecord, stores: Any) -> list[Evidence]:
    if not record.files:
        return []
    pattern = re.compile(record.files, re.I)
    notice = re.compile(record.notices, re.I) if record.notices else None

    def stage(name: str) -> Stage:
        return Stage.PROPOSED if notice is not None and notice.search(name) else file_stage(name)

    out = []
    for r in _drive_rows(stores):
        name = str(r.get("name") or "")
        if pattern.search(name):
            out.append(Evidence(stage(name), f"{name} (Drive: {r.get('path') or name})", f"drive:{r['id']}",
                                _written(r), Strength.FILE))
    for r in stores.library():
        name = str(r.get("name") or "")
        if pattern.search(name):
            out.append(Evidence(stage(name), f"{r.get('path') or name} (PayHOA library)", f"library:{r.get('id')}",
                                None, Strength.FILE))
    return out


def _send_evidence(record: RuleChangeRecord, stores: Any, extra: tuple[str, ...] = ()) -> list[Evidence]:
    pattern = re.compile(record.files, re.I) if record.files else None
    out = []
    for day, what, where in sorted(stores.mailings()):
        ledger = what.startswith(("rule-change-proposed", "rule-change-adopted")) and record.key in what
        named = bool(pattern and pattern.search(what)) or any(e.lower() in what.lower() for e in extra)
        if not (ledger or named):
            continue
        stage = (Stage.DISTRIBUTED if "adopted" in what.lower() else
                 Stage.PROPOSED if "proposed" in what.lower() or ledger else file_stage(what))
        out.append(Evidence(stage, f"{what} ({where})", f"{where}: {what}", day, Strength.DELIVERED))
    return out


def _gmail(root: Path) -> list[dict[str, Any]]:
    path = root / "gmail" / "correspondence.json"
    if not path.is_file():
        return []
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("messages") or [])
    except (OSError, json.JSONDecodeError):
        return []


def _email_evidence(record: RuleChangeRecord, root: Path, stores: Any) -> list[Evidence]:
    if not record.files:
        return []
    pattern = re.compile(record.files, re.I)
    out = []
    for m in _gmail(root):
        if m.get("direction") != "out":
            continue
        names = [str(a.get("name") if isinstance(a, dict) else a) for a in (m.get("attachments") or [])]
        hits = [n for n in names if pattern.search(n)]
        if not hits:
            continue
        day = stores.local_day(str(m.get("at") or ""))
        for name in hits:
            out.append(Evidence(file_stage(name), f"{name} (emailed)", f"gmail:{m.get('messageId')}", day,
                                Strength.EMAILED, note="a copy emailed; to whom is not read here"))
    return out


def _tasks(root: Path) -> list[dict[str, Any]]:
    path = root / "schedule" / "google-read.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [t for tl in raw.get("tasklists") or [] for t in tl.get("tasks") or []]


def _task_evidence(record: RuleChangeRecord, root: Path) -> list[Evidence]:
    if not record.tasks:
        return []
    pattern = re.compile(record.tasks, re.I)
    out = []
    for t in _tasks(root):
        title = str(t.get("title") or "")
        if not re.search(r"rule change", title, re.I) or not pattern.search(f"{title} {t.get('notes') or ''}"):
            continue
        status = str(t.get("status") or "")
        out.append(Evidence(file_stage(title), f"Google Task '{title}' due {_day(t.get('due'))}, {status}",
                            f"google-task:{t.get('id')}", _day(t.get("due")), Strength.PLANNED, note=status))
    return out


def _decision_evidence(record: RuleChangeRecord, stores: Any) -> tuple[list[Evidence], list[str]]:
    """The passage of the decision meeting's minutes that names the change; with no decision on record, the meetings
    whose minutes mention it (notes)."""
    words = [_words(w) for w in record.words]
    if not words:
        return [], []
    found: list[Evidence] = []
    notes: list[str] = []
    for day, minutes in sorted(stores.minutes().items()):
        if record.decided is not None and day != record.decided:
            continue
        for m in minutes:
            if m.confidential:
                continue
            text = _text(stores, m.id)
            for w in words:
                hit = w.search(text)
                if not hit:
                    continue
                passage = _passage(text, hit)
                if record.decided is not None:
                    strength = Strength.STATED if _ADOPT.search(passage) else Strength.LISTED
                    found.append(Evidence(Stage.ADOPTED, f"the minutes of {day}", m.label, day, strength,
                                          passage[:300]))
                else:
                    notes.append(f"mentioned in the minutes of {day}: \"{passage[:200]}\"")
                break
            if found:
                break
    return found[:1], notes[:3]


def _board_page(root: Path, change: Any) -> list[Evidence]:
    """A draft in the specification: its row is the proposed text; the board page jason rule-change wrote holds it."""
    out = [Evidence(Stage.DRAFT, f"the specification's draft ({change.key})", f"specification:rule_changes/{change.key}",
                    None, Strength.FILE, note="the proposed words, section by section")]
    page = root / "board" / f"rule-change-{change.slug}.md"
    if page.is_file():
        written = datetime.fromtimestamp(page.stat().st_mtime).date()
        out.append(Evidence(Stage.DRAFT, f"the board page {page.name}", f"data/board/{page.name}", written,
                            Strength.FILE, note="the member notice, agenda item, and adoption notice as drafted"))
    return out


def rule_change_histories(community: Any, data_dir: Path, *, on: date | None = None,
                          stores: Any = None) -> list[RuleChangeHistory]:
    """Every rule change's history: the profile's rows and the specification's drafts."""
    on = on or date.today()
    root = Path(data_dir)
    stores = _stores(community, root, stores)
    out = []
    for record, origin, change in records(community):
        evidence = _file_evidence(record, stores)
        evidence += _send_evidence(record, stores, (f"proposed rule change: {record.document_title}",
                                                    f"adopted rule change: {record.document_title}")
                                   if change is not None else ())
        evidence += _email_evidence(record, root, stores)
        evidence += _task_evidence(record, root)
        if change is not None:
            evidence += _board_page(root, change)
        decision, mentions = _decision_evidence(record, stores)
        evidence += decision
        h = rule_change_history(record, evidence, on=on, origin=origin)
        h.notes += mentions
        out.append(h)
    return out


def leads(community: Any, data_dir: Path, *, stores: Any = None) -> dict[str, list[dict[str, Any]]]:
    """What may be a rule change no row names: notice files no row's pattern claims, and minutes passages about rule
    changes on days that are no row's decision."""
    stores = _stores(community, Path(data_dir), stores)
    rows = [r for r, _, _ in records(community)]
    patterns = [re.compile(r.files, re.I) for r in rows if r.files]
    files = []
    for r in _drive_rows(stores):
        name = str(r.get("name") or "")
        if RULE_CHANGE_FILE.search(name) and not any(p.search(name) for p in patterns):
            files.append({"name": name, "source": f"drive:{r['id']}", "written": str(_written(r) or "")})
    decided = {r.decided for r in rows if r.decided}
    covered = [_words(w) for r in rows for w in r.words]
    passages = []
    for day, minutes in sorted(stores.minutes().items()):
        if day in decided:
            continue
        found = None
        for m in minutes:
            if m.confidential:
                continue
            text = _text(stores, m.id)
            for hit in _RULE_LEAD.finditer(text):
                passage = _passage(text, hit)
                if not any(w.search(passage) for w in covered):
                    found = {"date": day.isoformat(), "minutes": m.label, "passage": passage[:240]}
                    break
            if found:
                break
        if found:
            passages.append(found)
    specs = {c.slug for c in tuple(getattr(community, "rule_changes", lambda: ())() or ())}
    board = Path(data_dir) / "board"
    pages = [{"name": p.name, "source": f"data/board/{p.name}"} for p in sorted(board.glob("rule-change-*.md"))
             if p.stem[len("rule-change-"):] not in specs] if board.is_dir() else []
    return {"files": files[:MAX_LEADS], "minutes": passages[-MAX_LEADS:], "boardPages": pages}


# ---------------------------------------------------------------------------------------------------------------
# Minutes.


def _zoom_kinds(root: Path) -> dict[date, set[str]]:
    from jason.tasks.meeting_watch import _zoom_kinds as kinds

    return kinds(root)


def _kind(day: date, zoom: set[str], meeting: dict[str, Any], minutes_names: list[str]) -> MeetingKind:
    if zoom & BOARD_KINDS:
        return MeetingKind.BOARD
    if zoom & EXECUTIVE_KINDS:
        return MeetingKind.EXECUTIVE
    if zoom & MEMBER_KINDS:
        return MeetingKind.MEMBERS
    titles = " ".join(meeting.get("titles") or [])
    if re.search(r"annual (membership|meeting)|members'? meeting", titles, re.I):
        return MeetingKind.MEMBERS
    if minutes_names:
        if all(re.search(r"annual (membership|meeting)|members'? meeting", n, re.I) for n in minutes_names):
            return MeetingKind.MEMBERS
        return MeetingKind.BOARD
    if "meeting notice" in (meeting.get("has") or {}):
        return MeetingKind.BOARD
    return MeetingKind.UNKNOWN


def _source(rec: dict[str, Any]) -> str:
    where, ref = str(rec.get("where") or ""), str(rec.get("ref") or "")
    if where == "Drive" and ref:
        return f"drive:{ref}"
    if where == "PayHOA library" and ref:
        return f"library:{ref}"
    if where == "Gmail":
        return "gmail"
    return f"{where}:{ref}" if ref else where


def _copies(stores: Any, day: date) -> tuple[list[MinutesCopy], int]:
    """The minutes' copies on file for the meeting on ``day`` (one row per name and place, with its count and earliest
    date), and how many of jason's own drafts are on disk."""
    drive = stores.drive_files()
    grouped: dict[tuple[str, str, bool], dict[str, Any]] = {}
    jason = 0
    for rec in stores.meetings().get(day, {}).get("records", []):
        if rec.get("kind") not in ("minutes", "draft minutes"):
            continue
        if rec.get("where") == "jason draft":
            jason += 1
            continue
        on = None
        if rec.get("sent"):
            on = stores.local_day(rec["sent"])
        elif rec.get("where") == "Drive" and rec.get("ref") in drive:
            on = stores.local_day(drive[rec["ref"]].get("created") or "")
        confidential = bool(rec.get("confidential"))
        name = str(rec.get("name") or "")
        draft = rec.get("kind") == "draft minutes" or bool(DRAFT_NAME.search(name))
        key = (str(rec.get("where")), name, confidential)
        row = grouped.setdefault(key, {"name": name, "where": str(rec.get("where")), "source": _source(rec),
                                       "on": on, "draft": draft, "confidential": confidential, "count": 0})
        row["count"] += 1
        if on and (row["on"] is None or on < row["on"]):
            row["on"], row["source"] = on, _source(rec)
    names = {g["name"] for g in grouped.values()}
    for m in stores.minutes().get(day, []):         # a reading's copy the catalog does not hold
        if m.name in names:
            continue
        source = f"drive:{m.id[6:]}" if m.id.startswith("drive-") else f"library:{m.id}"
        grouped[(m.where, m.id, m.confidential)] = {"name": m.name, "where": m.where, "source": source, "on": None,
                                                    "draft": bool(DRAFT_NAME.search(m.name)),
                                                    "confidential": m.confidential, "count": 1}
    copies = [MinutesCopy(**g) for g in grouped.values()]
    return sorted(copies, key=lambda c: (c.on or date.max, c.where, c.name)), jason


def _clock(community: Any, stores: Any, day: date, on: date) -> StageClock:
    """The 4950(a) clock, read as the meeting watch reads it (``minutes_on_record``)."""
    from jason.community.notice_catalog import effective
    from jason.community.notices import Anchor
    from jason.tasks.schedule_evidence import minutes_on_record

    _, clocks, _, _ = effective(MINUTES_AVAILABLE, community)
    timing = next(t for t in clocks if t.anchor is Anchor.MEETING)
    deadline = timing.window(day)[1]
    dated, undated = minutes_on_record(stores, day)
    if dated:
        first, label = dated[0]
        found = Evidence(Stage.DRAFT, label, "", first, Strength.FILE)
        return StageClock(MINUTES_AVAILABLE, "CIV 4950(a)", timing.describe(), day, deadline,
                          Standing.MET if first <= deadline else Standing.LATE, found,
                          f"the earliest dated copy is {(first - day).days} days after the meeting")
    if undated:
        return StageClock(MINUTES_AVAILABLE, "CIV 4950(a)", timing.describe(), day, deadline, Standing.UNDATED,
                          Evidence(Stage.DRAFT, undated[0], "", None, Strength.FILE),
                          "on file with no date: when members could read it is not kept")
    return StageClock(MINUTES_AVAILABLE, "CIV 4950(a)", timing.describe(), day, deadline,
                      Standing.PASSED if on > deadline else Standing.OPEN)


def _meeting_days(stores: Any, zoom: dict[date, set[str]], on: date) -> list[date]:
    days = set(stores.held())
    days |= {d for d, kinds in zoom.items() if kinds & (BOARD_KINDS | EXECUTIVE_KINDS | MEMBER_KINDS)}
    days |= {d for d, m in stores.meetings().items()
             if set(m.get("has") or {}) & {"minutes", "draft minutes"}}
    return sorted(d for d in days if d < on)


def _approvals(stores: Any, days: list[date], kinds: dict[date, MeetingKind]) -> dict[date, list[Approval]]:
    """Each meeting's approvals, read from the approval items in later meetings' minutes (not executive sessions')."""
    out: dict[date, list[Approval]] = {}
    known = set(days)
    for later, minutes in sorted(stores.minutes().items()):
        for m in minutes:
            if m.confidential:
                continue
            for item in approval_items(_text(stores, m.id)):
                targets = [d for d in item.dates if d in known and d < later
                           and (later - d).days <= APPROVAL_LOOKAHEAD_DAYS]
                if item.previous:
                    before = [d for d in days if d < later and kinds.get(d) is not MeetingKind.EXECUTIVE]
                    targets = before[-1:]
                for d in targets:
                    if any(a.meeting == later for a in out.get(d, [])):
                        continue
                    out.setdefault(d, []).append(Approval(later, m.label, item.stated, item.corrected, item.passage))
    return out


def minutes_histories(community: Any, data_dir: Path, *, since: date | None = None, on: date | None = None,
                      stores: Any = None) -> list[MinutesHistory]:
    """Every meeting's minutes history from ``since`` to the day before ``on``."""
    on = on or date.today()
    root = Path(data_dir)
    stores = _stores(community, root, stores)
    zoom = _zoom_kinds(root)
    all_days = _meeting_days(stores, zoom, on)
    copies: dict[date, tuple[list[MinutesCopy], int]] = {d: _copies(stores, d) for d in all_days}
    kinds: dict[date, MeetingKind] = {}
    for d in all_days:
        names = [c.name for c in copies[d][0] if not c.confidential]
        kinds[d] = _kind(d, zoom.get(d, set()), stores.meetings().get(d, {}), names)
        if kinds[d] is MeetingKind.UNKNOWN and copies[d][0] and all(c.confidential for c in copies[d][0]):
            kinds[d] = MeetingKind.EXECUTIVE
    approvals = _approvals(stores, all_days, kinds)
    out: list[MinutesHistory] = []
    for d in all_days:
        if since and d < since:
            continue
        kind = kinds[d]
        found, jason = copies[d]
        has = sorted(k for k in (stores.meetings().get(d, {}).get("has") or {}) if k != "correspondence")
        basis = ("on record: " + ", ".join(has)) if has else "on record"
        if zoom.get(d):
            basis += "; Zoom: " + ", ".join(sorted(zoom[d]))
        h = MinutesHistory(d, kind, basis, found, sorted(approvals.get(d, []), key=lambda a: a.meeting))
        if kind is MeetingKind.EXECUTIVE:
            h.copies = [c for c in found if c.confidential] or found
            h.copies = [MinutesCopy(c.name, c.where, c.source, c.on, c.draft, True, c.count) for c in h.copies]
            h.approvals = []
            h.notes.append("Held solely in executive session: no open minutes are owed (4950(a)); its minutes are "
                           "restricted (4935), and its matters are generally noted in the next open meeting's minutes "
                           "(4935(e)).")
        elif kind is MeetingKind.BOARD:
            h.clock = _clock(community, stores, d, on)
        elif kind is MeetingKind.MEMBERS:
            h.notes.append("A members' meeting: 4950(a)'s 30 days are for board minutes; its minutes are usually "
                           "approved at the next members' meeting or by the board.")
        else:
            h.notes.append("What kind of meeting this was is not on record (no minutes, notice, or Zoom kind).")
        if jason:
            h.notes.append(f"{jason} of jason's own drafts on disk (not with the members).")
        h.versions = minutes_versions(h)
        if len({a.meeting for a in h.approvals}) > 1:
            h.notes.append("Named on the approval item of more than one later meeting: the first may have deferred "
                           "it; the minutes of each say which.")
        if any(CORRECTED_NAME.search(c.name) for c in h.copies if not c.confidential):
            h.notes.append("A copy is named as corrected.")
        if kind is MeetingKind.BOARD and h.clock is not None:
            if h.clock.standing is Standing.PASSED:
                h.actions.append(f"No minutes of this meeting are on record and the 30 days ended {h.clock.deadline} "
                                 "(4950(a)): a person finds or writes them and makes them (or a marked draft) "
                                 "available, and records where.")
            if not h.approvals and h.clock.standing is not Standing.OPEN and (on - d).days > 60:
                h.actions.append("No later meeting's minutes are on record approving these minutes: the board "
                                 "approves them at its next meeting, or a person records where they were approved.")
        out.append(h)
    return out


def minutes_summary(histories: list[MinutesHistory], *, since: date | None = None) -> dict[str, Any]:
    """Counts for the board meetings from ``since`` whose 30 days have run."""
    rows = [h for h in histories if h.kind is MeetingKind.BOARD and h.clock is not None
            and h.clock.standing is not Standing.OPEN and (since is None or h.day >= since)]
    clock = {s.value: sum(1 for h in rows if h.clock and h.clock.standing is s) for s in
             (Standing.MET, Standing.LATE, Standing.UNDATED, Standing.PASSED)}
    approval = {k: sum(1 for h in rows if h.approval == k) for k in ("stated", "listed", "none")}
    neither = sum(1 for h in rows if h.draft_on_time is not True and h.approval == "none")
    return {"since": since.isoformat() if since else None, "boardMeetings": len(rows), "draft": clock,
            "draftOnTime": clock[Standing.MET.value], "approval": approval,
            "approvalOnRecord": approval["stated"] + approval["listed"], "neither": neither,
            "executiveOnly": sum(1 for h in histories if h.kind is MeetingKind.EXECUTIVE
                                 and (since is None or h.day >= since)),
            "membersMeetings": sum(1 for h in histories if h.kind is MeetingKind.MEMBERS
                                   and (since is None or h.day >= since)),
            "kindUnknown": sum(1 for h in histories if h.kind is MeetingKind.UNKNOWN
                               and (since is None or h.day >= since))}


# ---------------------------------------------------------------------------------------------------------------
# One read-only call for the tools.


def histories(community: Any, data_dir: Path, *, since: date | None = None, on: date | None = None,
              rules: bool = True, minutes: bool = True, stores: Any = None) -> dict[str, Any]:
    """The rule changes' and the minutes' histories as rows a shared tool may show: executive-session minutes are only
    their existence and date. Reads disk only."""
    on = on or date.today()
    root = Path(data_dir)
    stores = _stores(community, root, stores)
    out: dict[str, Any] = {"asOf": on.isoformat(), "caveats": list(CAVEATS)}
    if rules:
        found = rule_change_histories(community, root, on=on, stores=stores)
        out["ruleChanges"] = [h.row() for h in found]
        out["ruleChangeLeads"] = leads(community, root, stores=stores)
    if minutes:
        found_minutes = minutes_histories(community, root, since=since, on=on, stores=stores)
        out["minutes"] = [h.row() for h in found_minutes]
        out["minutesSummary"] = minutes_summary(found_minutes, since=since)
    return out


def lines(result: dict[str, Any], rule_histories: list[RuleChangeHistory] | None = None,
          minute_histories: list[MinutesHistory] | None = None) -> list[str]:
    out: list[str] = []
    if rule_histories is not None:
        out.append(f"Rule changes (Civil Code 4360), as of {result['asOf']}:")
        for h in rule_histories:
            out += h.lines()
            stages = h.stages_with_evidence()
            out.append("    evidence by stage: " + ", ".join(f"{k} {v}" for k, v in stages.items()))
        if not rule_histories:
            out.append("    none: the profile names no rule change and the specification holds no draft")
        found = result.get("ruleChangeLeads") or {}
        if found.get("files") or found.get("minutes") or found.get("boardPages"):
            out.append("Leads no row names (read them; a rule change becomes a profile row):")
            out += [f"    file {f['written'] or 'undated'}: {f['name']} [{f['source']}]" for f in found.get("files", [])]
            out += [f"    minutes {p['date']}: \"{p['passage']}\"" for p in found.get("minutes", [])]
            out += [f"    board page with no draft in the specification: {p['source']}"
                    for p in found.get("boardPages", [])]
        out.append("")
    if minute_histories is not None:
        out.append(f"Minutes (Civil Code 4950), as of {result['asOf']}:")
        for h in minute_histories:
            out += h.lines()
        s = result.get("minutesSummary") or {}
        if s:
            out.append(f"Board meetings{' since ' + s['since'] if s.get('since') else ''} whose 30 days have run: "
                       f"{s['boardMeetings']}. A copy on record in time: {s['draftOnTime']} (late {s['draft'][Standing.LATE.value]}, "
                       f"undated {s['draft'][Standing.UNDATED.value]}, none {s['draft'][Standing.PASSED.value]}). "
                       f"Approval stated: {s['approval']['stated']}; only listed: {s['approval']['listed']}; none on "
                       f"record: {s['approval']['none']}. Neither a copy in time nor an approval: {s['neither']}. "
                       f"Executive sessions only: {s['executiveOnly']}; members' meetings: {s['membersMeetings']}; "
                       f"kind not on record: {s['kindUnknown']}.")
        out.append("")
    out += [f"_{c}_" for c in CAVEATS]
    return out


__all__ = ["CAVEATS", "histories", "leads", "lines", "minutes_histories", "minutes_summary", "records",
           "rule_change_histories"]
