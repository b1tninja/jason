"""The association's meetings, each with every record of it the association holds, wherever it is held.

``build`` reads what jason already has on disk: the Zoom sync (``data/zoom``: what Zoom's cloud still holds for each
meeting, and jason's copies of the transcripts, chats, summaries, and attendance), the Drive listing
(``data/drive/files.json``, from `jason drive --sync`), the PayHOA library (``data/library/library.db``), and jason's
agenda drafts (``data/board``). It names each file by the specification's record rules, places it on the date its name
carries, and groups the records by meeting. It calls nothing and moves, copies, or deletes nothing.

Each meeting is checked:
- minutes: none found 30 days after the meeting (CIV 4950), or only a draft;
- recordings: audio or video still held after the minutes (the Decorum Rules say the recording is deleted once the
  minutes are prepared), and where;
- executive session: a transcript that mentions an executive session or a hearing is confidential and held back;
- the schedule: a meeting day with no record of any kind.

A file that looks like a meeting record but carries no date is listed as unplaced. The catalog is
``data/meetings/catalog.json``; the report is ``data/reports/meetings.md``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.meeting_records import RECORDINGS, Meeting, MeetingRecord, RecordKind, Where, meeting_date, record_kind

MINUTES_DAYS = 30                                   # CIV 4950(a)
CLOUD_KINDS = {"MP4": RecordKind.VIDEO, "M4A": RecordKind.AUDIO, "TRANSCRIPT": RecordKind.TRANSCRIPT, "CHAT": RecordKind.CHAT,
               "SUMMARY": RecordKind.AI_SUMMARY}
COPY_KINDS = {"transcript": RecordKind.TRANSCRIPT, "chat": RecordKind.CHAT, "summary": RecordKind.AI_SUMMARY,
              "participants": RecordKind.ATTENDANCE}
LIBRARY_KINDS = ("minutes", "agenda", "executive_session", "notice")
CAVEATS = (
    "A record is placed by the date its name carries; a misnamed file lands on the wrong meeting or none.",
    "Drive and the PayHOA library hold many copies of the same minutes; each copy is listed.",
    "Minutes 'not found' means not found in these places, not that none were written.",
    "A retained recording may be under a litigation hold; nothing here says to delete it.",
)


def _zoom(data_dir: Path) -> list[tuple[MeetingRecord, str, str]]:
    from jason.tasks.zoom import confidential_mentions, load_index, zoom_dir

    out = []
    root = zoom_dir(data_dir)
    for row in load_index(data_dir).get("meetings", []):
        day = date.fromisoformat(row["date"]) if row.get("date") else None
        secret = bool(row.get("confidential") or confidential_mentions(root, row))
        title = row.get("topic") or ""
        for kind in row.get("cloud") or []:
            if kind in CLOUD_KINDS:
                out.append((MeetingRecord(CLOUD_KINDS[kind], Where.ZOOM_CLOUD, f"{title} ({kind})", f"zoom:{row['uuid']}", row["uuid"],
                                          day, secret, f"as of {row.get('cloudCheckedAt')}"), title, row.get("kind") or ""))
        for name, rel in (row.get("files") or {}).items():
            if name in COPY_KINDS:
                out.append((MeetingRecord(COPY_KINDS[name], Where.JASON, f"{title} ({name})", f"data/zoom/{rel}", row["uuid"], day, secret),
                            title, row.get("kind") or ""))
    return out


def _drive(data_dir: Path, community: Any, tz: str) -> tuple[list[MeetingRecord], list[MeetingRecord]]:
    path = Path(data_dir) / "drive" / "files.json"
    if not path.is_file():
        return [], []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("files", [])
    rules, skip, schedule = tuple(community.meeting_record_rules()), tuple(community.not_meeting_records()), community.meeting_schedule()
    placed, unplaced = [], []
    for r in rows:
        if r.get("mimeType", "").endswith(".folder") or any(r.get("path", "").startswith(p) for p in skip):
            continue
        kind = record_kind(r["name"], r.get("path", ""), rules)
        if kind is None:
            continue
        day = meeting_date(r["name"], r.get("path", ""), tz=tz, schedule=schedule)
        rec = MeetingRecord(kind, Where.DRIVE, r["name"], r.get("path", ""), r.get("id", ""), day,
                            note="shortcut" if r.get("mimeType", "").endswith("shortcut") else
                            "Google Doc" if r.get("mimeType", "").endswith(".document") else "",
                            md5=r.get("md5") or "")
        (placed if day else unplaced).append(rec)
    return placed, unplaced


def _library(data_dir: Path, community: Any, tz: str, digests: Any = None) -> tuple[list[MeetingRecord], list[MeetingRecord]]:
    db = Path(data_dir) / "library" / "library.db"
    if not db.is_file():
        return [], []
    rules, schedule = tuple(community.meeting_record_rules()), community.meeting_schedule()
    placed, unplaced = [], []
    with sqlite3.connect(db) as con:
        rows = con.execute(f"select id, path, name, kind, period, confidential, sha256 from documents where kind in "
                           f"({','.join('?' * len(LIBRARY_KINDS))})", LIBRARY_KINDS).fetchall()
    for doc_id, path, name, kind, period, confidential, sha in rows:
        rk = record_kind(name, path or "", rules)
        if rk is None:
            if kind != "notice":
                rk = {"minutes": RecordKind.MINUTES, "agenda": RecordKind.AGENDA, "executive_session": RecordKind.EXECUTIVE_AGENDA}[kind]
            else:
                continue
        day = None
        if period and len(period) == 10:
            day = date.fromisoformat(period)
        day = day or meeting_date(name, path or "", tz=tz, schedule=schedule)
        rec = MeetingRecord(rk, Where.PAYHOA, name, path or "", str(doc_id), day, bool(confidential) or rk is RecordKind.EXECUTIVE_AGENDA,
                            note=_recap_note(Path(data_dir) / "library" / "text" / f"{doc_id}.txt") if rk is RecordKind.MINUTES else "",
                            md5=digests.of(Path(data_dir) / "library" / "files" / (path or ""))[0] if digests and path else "",
                            sha256=sha or "")
        (placed if day else unplaced).append(rec)
    return placed, unplaced


RECAP = re.compile(r"Quick recap|Next steps\s", re.I)
EXECUTIVE_SUBJECTS = re.compile(r"\b(?:executive session|disciplin\w*|hearings?|fine[sd]?|delinquen\w*|collections?|foreclos\w*|liens?|"
                                r"lawsuits?|attorneys?|counsel)\b", re.I)


def _recap_note(text_file: Path) -> str:
    """Whether posted minutes carry Zoom's AI recap, and whether the recap names executive-session subjects."""
    if not text_file.is_file():
        return ""
    text = text_file.read_text(encoding="utf-8", errors="replace")
    m = RECAP.search(text)
    if not m:
        return ""
    subjects = sorted({s.group(0).strip().lower() for s in EXECUTIVE_SUBJECTS.finditer(text[m.start():])})
    return "AI recap appended" + (f"; it names {', '.join(subjects)}" if subjects else "")


COMMUNICATIONS = Path("payhoa") / "communications.json"


def sync_communications(client: Any, org_id: int, data_dir: Path, community: Any, *, log: Any = None) -> dict[str, int]:
    """Read PayHOA's communications log for meeting notices (read-only) and keep one row per mailing: its subject,
    when it went out, its type, how many members it went to, and how many were delivered, opened, bounced, or failed.
    No member's name, email, or address is kept."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    seen: set[str] = set()
    for term in community.communication_search():
        for row in client.iter_communications(org_id, search=term):
            rid = str(row.get("activityId") or row.get("id") or "")
            if rid in seen:
                continue
            seen.add(rid)
            sent = str(row.get("sentAt") or row.get("activityCreatedAt") or row.get("createdAt") or "")
            key = (str(row.get("subject") or ""), sent[:16])
            g = groups.setdefault(key, {"subject": key[0], "sent": sent, "type": row.get("type"), "category": row.get("category"),
                                        "sender": row.get("senderName"), "recipients": 0, "status": {}, "attachments": []})
            g["recipients"] += 1
            status = str(row.get("status") or "unknown")
            g["status"][status] = g["status"].get(status, 0) + 1
            for a in row.get("fileAttachments") or []:
                name = a.get("name") or a.get("fileName") or a.get("originalName")
                if name and name not in g["attachments"]:
                    g["attachments"].append(name)
    path = Path(data_dir) / COMMUNICATIONS
    path.parent.mkdir(parents=True, exist_ok=True)
    notices = sorted(groups.values(), key=lambda g: g["sent"], reverse=True)
    path.write_text(json.dumps({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "notices": notices}, indent=1),
                    encoding="utf-8")
    if log:
        log(f"{len(seen)} communication rows in {len(notices)} mailings")
    return {"rows": len(seen), "mailings": len(notices)}


def _local_day(stamp: str, tz: str) -> date | None:
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    from zoneinfo import ZoneInfo

    return moment.astimezone(ZoneInfo(tz)).date()


def _payhoa_sent(data_dir: Path, community: Any, tz: str) -> tuple[list[MeetingRecord], list[MeetingRecord]]:
    path = Path(data_dir) / COMMUNICATIONS
    if not path.is_file():
        return [], []
    schedule = community.meeting_schedule()
    placed, unplaced = [], []
    for n in json.loads(path.read_text(encoding="utf-8")).get("notices", []):
        sent_day = _local_day(n["sent"], tz)
        day = meeting_date(n["subject"], tz=tz, schedule=schedule, reference=sent_day)
        status = ", ".join(f"{v} {k}" for k, v in sorted(n["status"].items()))
        rec = MeetingRecord(RecordKind.NOTICE, Where.PAYHOA_SENT, n["subject"], f"PayHOA communications ({n.get('type')})", "", day,
                            note=f"{n['recipients']} recipients; {status}" + (f"; attached {', '.join(n['attachments'])}" if n["attachments"] else ""),
                            sent=n["sent"])
        (placed if day else unplaced).append(rec)
    return placed, unplaced


def _gmail(data_dir: Path, community: Any, tz: str, digests: Any) -> tuple[list[MeetingRecord], list[MeetingRecord]]:
    """Emails about a meeting (by the email rules) and the agenda and minutes files attached to any email."""
    root = Path(data_dir) / "gmail"
    placed, unplaced = [], []
    schedule, email_rules, file_rules = community.meeting_schedule(), tuple(community.meeting_email_rules()), tuple(community.meeting_record_rules())
    corr = root / "correspondence.json"
    if corr.is_file():
        for msg in json.loads(corr.read_text(encoding="utf-8")).get("messages", []):
            rule = next((r for r in email_rules if r.matches(msg.get("subject") or "", msg.get("domains") or [])), None)
            if rule is None:
                continue
            sent_day = _local_day(msg.get("at") or "", tz)
            day = meeting_date(msg["subject"], tz=tz, schedule=schedule, reference=sent_day)
            if day is None and "zoom.us" in (msg.get("domains") or []):
                day = sent_day                       # Zoom writes the evening of the meeting
            rec = MeetingRecord(rule.kind, Where.GMAIL, msg["subject"], f"gmail:{msg.get('threadId')}", msg.get("messageId", ""), day,
                                note=rule.note, sent=msg.get("at") or "")
            (placed if day else unplaced).append(rec)
    files = root / "files.json"
    if files.is_file():
        raw = json.loads(files.read_text(encoding="utf-8"))
        for f in raw if isinstance(raw, list) else raw.get("files", []):
            kind = record_kind(f.get("name") or "", f.get("subject") or "", file_rules)
            if kind is None:
                continue
            sent_day = _local_day(f.get("at") or "", tz)
            day = meeting_date(f["name"], tz=tz, schedule=schedule, reference=sent_day) or \
                meeting_date(f.get("subject") or "", tz=tz, schedule=schedule, reference=sent_day)
            md5, _ = digests.of(Path(data_dir) / str(f.get("path", "")).replace("\\", "/"))
            rec = MeetingRecord(kind, Where.GMAIL, f["name"], str(f.get("path", "")).replace("\\", "/"), f.get("messageId", ""), day,
                                note=f"attached to: {f.get('subject') or ''}", sent=f.get("at") or "", md5=md5, sha256=f.get("sha256", ""))
            (placed if day else unplaced).append(rec)
    return placed, unplaced


def _drafts(data_dir: Path) -> list[MeetingRecord]:
    out = []
    for p in sorted((Path(data_dir) / "board").glob("*-20??-??-??.md")):
        stem = p.stem
        day = date.fromisoformat(stem[-10:])
        kind = RecordKind.AGENDA if stem.startswith("agenda") else RecordKind.DRAFT_MINUTES if stem.startswith("minutes") else None
        if kind:
            out.append(MeetingRecord(kind, Where.DRAFT, p.name, f"data/board/{p.name}", "", day, note="jason's draft"))
    return out


def build(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    """Every meeting record on disk, grouped by meeting, with each meeting's checks."""
    today = today or date.today()
    policy = community.hearing_policy()
    tz = policy.timezone if policy else "America/Los_Angeles"
    meetings: dict[date, Meeting] = {}

    def add(rec: MeetingRecord, title: str = "") -> None:
        m = meetings.setdefault(rec.day, Meeting(rec.day))
        m.records.append(rec)
        if title:
            m.titles.add(title)

    from jason.tasks.zoom import load_index

    # Every Zoom occurrence is a meeting that was held, with or without a file.
    for row in load_index(data_dir).get("meetings", []):
        if row.get("date"):
            meetings.setdefault(date.fromisoformat(row["date"]), Meeting(date.fromisoformat(row["date"]))).titles.add(row.get("topic") or "")
    for rec, title, kind in _zoom(data_dir):
        if rec.day:
            add(rec, title)
    from jason.tasks.zoom import executive_break, zoom_dir

    breaks: dict[date, Any] = {}
    for row in load_index(data_dir).get("meetings", []):
        if row.get("date"):
            _, brk = executive_break(zoom_dir(data_dir), row, community)
            if brk:
                breaks[date.fromisoformat(row["date"])] = brk
    from jason.tasks.digests import Digests

    digests = Digests(data_dir)
    drive, drive_loose = _drive(data_dir, community, tz)
    library, library_loose = _library(data_dir, community, tz, digests)
    sent, sent_loose = _payhoa_sent(data_dir, community, tz)
    mail, mail_loose = _gmail(data_dir, community, tz, digests)
    digests.save()
    for rec in drive + library + sent + mail + _drafts(data_dir):
        add(rec)
    # PayHOA's log starts somewhere; before its first mailing a missing notice says nothing.
    notices_from = min((r.day for r in sent if r.day), default=None)

    out = []
    for day in sorted(meetings, reverse=True):
        m = meetings[day]
        kinds = {r.kind for r in m.records}
        checks = []
        final = RecordKind.MINUTES in kinds
        if not final and day <= today - timedelta(days=MINUTES_DAYS) and day <= today:
            checks.append("no minutes found" + (" (a draft only)" if RecordKind.DRAFT_MINUTES in kinds else "")
                          + f"; minutes are due to members within {MINUTES_DAYS} days (CIV 4950(a))")
        held = sorted({r.where.value for r in m.records if r.kind in RECORDINGS})
        if held and final:
            checks.append(f"a recording is still held after the minutes ({', '.join(held)}); the Decorum Rules say it is deleted "
                          "once the minutes are prepared")
        elif held:
            checks.append(f"a recording is held ({', '.join(held)})")
        brk = breaks.get(day)
        if brk:
            checks.append(f"the board adjourned to executive session at {brk.at / 60:.1f} minutes on the same call"
                          + (f" ({brk.departed} left)" if brk.departed else "") + "; the transcript after that is confidential (CIV 4935)")
            if RecordKind.AI_SUMMARY in kinds:
                checks.append("Zoom's AI summary covers the whole call, the executive session included")
        elif any(r.confidential and r.kind is RecordKind.TRANSCRIPT for r in m.records):
            checks.append("a transcript mentions an executive session or a hearing but shows no adjournment: confidential whole (CIV 4935)")
        recaps = [r for r in m.records if r.kind is RecordKind.MINUTES and r.note.startswith("AI recap")]
        if recaps and (brk or "names" in recaps[0].note):
            resale = any("resale" in r.location.lower() for r in recaps)
            checks.append("the posted minutes carry Zoom's AI recap of the call" + (f" ({recaps[0].note.split('; ', 1)[1]})" if "names" in recaps[0].note else "")
                          + "; executive session matters are only generally noted in the open minutes (CIV 4935(e))"
                          + ("; a copy is in the resale documents" if resale else ""))
        checks += _notice_checks(m, day, today, tz, notices_from)
        by_kind: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in m.records:
            by_kind[r.kind.value][r.where.value] += 1
        out.append({"date": day.isoformat(), "titles": sorted(m.titles), "has": {k: dict(v) for k, v in sorted(by_kind.items())},
                    "checks": checks, "sameFile": same_file(m.records), "records": [r.row() for r in m.records]})
    gaps = _gaps(community, set(meetings), today)
    loose = [r.row() for r in drive_loose + library_loose + sent_loose + mail_loose if r.kind is not RecordKind.CORRESPONDENCE]
    return {"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "meetings": out, "count": len(out),
            "scheduleGaps": gaps, "unplaced": loose, "caveats": list(CAVEATS)}


NOTICE_DAYS = 4          # CIV 4920(a); two for a meeting held solely in executive session, 4920(b)(2)


def _notice_checks(m: Meeting, day: date, today: date, tz: str, notices_from: date | None) -> list[str]:
    """When the members were told of the meeting, from PayHOA's mailing (or its copy in Gmail)."""
    sent = sorted(d for d in (_local_day(r.sent, tz) for r in m.records if r.kind is RecordKind.NOTICE and r.sent) if d)
    if sent:
        out = []
        lead = (day - sent[0]).days
        if 0 <= lead < NOTICE_DAYS:
            out.append(f"the notice went to members {lead} day{'s' if lead != 1 else ''} before the meeting ({sent[0]}); a board "
                       f"meeting is noticed at least {NOTICE_DAYS} days before (CIV 4920(a))")
        for r in m.records:
            if r.where is Where.PAYHOA_SENT:
                missed = sum(int(n) for n, _ in re.findall(r"(\d+) (failed|bounced)", r.note))
                if missed:
                    out.append(f"PayHOA's email notice failed or bounced for {missed} of its recipients; email is notice only to "
                               "members who chose it, so they rely on a posting the annual policy statement designates (CIV 4040, 4045)")
                    break
        return out
    held = bool(m.titles) or any(r.kind in (RecordKind.AGENDA, RecordKind.MINUTES) for r in m.records)
    if held and notices_from and notices_from <= day <= today:
        return ["no notice to members found in PayHOA's communications or its Gmail copies (CIV 4920, 4045)"]
    return []


def same_file(records: list[MeetingRecord]) -> list[dict[str, Any]]:
    """Copies in more than one place that are the same bytes (by MD5, else SHA-256): one document, many copies."""
    groups: dict[str, list[MeetingRecord]] = defaultdict(list)
    for r in records:
        key = r.md5 or r.sha256
        if key:
            groups[key].append(r)
    by_sha = {r.sha256: r.md5 for r in records if r.sha256 and r.md5}
    for sha, md5 in by_sha.items():            # a SHA-256-only copy joins the MD5 group of the same file
        if sha in groups and md5 in groups and sha != md5:
            groups[md5] += groups.pop(sha)
    out = []
    for key, recs in groups.items():
        places = sorted({f"{r.where.value}: {r.location}" for r in recs})
        if len(places) > 1:
            out.append({"kind": recs[0].kind.value, "name": recs[0].name, "copies": places})
    return out


def _gaps(community: Any, days: set[date], today: date) -> list[str]:
    schedule = community.meeting_schedule()
    if schedule is None or not days:
        return []
    # The schedule is the one Resolution 20230130-1 fixed; before it, meetings were set one at a time.
    first = max(min(days), community.zoom_history_since() or min(days))
    gaps, day = [], schedule.next_meeting(first - timedelta(days=1), monthly=True)
    while day < today:
        if not any(abs((day - d).days) <= 10 for d in days):
            regular = not schedule.regular_months or day.month in schedule.regular_months or day.month == schedule.annual_month
            gaps.append(day.isoformat() + ("" if regular else " (not a regular month under the resolution)"))
        day = schedule.next_meeting(day, monthly=True)
    return gaps


def write(data_dir: Path, catalog: dict[str, Any]) -> tuple[Path, Path]:
    out = Path(data_dir) / "meetings" / "catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, indent=1), encoding="utf-8")
    report = Path(data_dir) / "reports" / "meetings.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(report_lines(catalog)), encoding="utf-8")
    return out, report


def load(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / "meetings" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


ORDER = [k.value for k in (RecordKind.NOTICE, RecordKind.AGENDA, RecordKind.EXECUTIVE_AGENDA, RecordKind.DRAFT_MINUTES, RecordKind.MINUTES,
                           RecordKind.TRANSCRIPT, RecordKind.AI_SUMMARY, RecordKind.CHAT, RecordKind.ATTENDANCE, RecordKind.AUDIO,
                           RecordKind.VIDEO, RecordKind.RECORDING_NOTICE, RecordKind.CORRESPONDENCE)]


def report_lines(catalog: dict[str, Any], *, limit: int | None = None) -> list[str]:
    lines = ["# Meeting records", "", f"Built {catalog.get('builtAt')}: {catalog.get('count')} meetings.", ""]
    for m in catalog.get("meetings", [])[:limit]:
        titles = "; ".join(m["titles"]) or ""
        lines.append(f"## {m['date']} {titles}".rstrip())
        for kind in ORDER:
            if kind in m["has"]:
                lines.append(f"- {kind}: " + ", ".join(f"{where} {n}" for where, n in m["has"][kind].items()))
        for group in m.get("sameFile") or []:
            lines.append(f"- same file ({group['kind']}, {group['name']}): " + "; ".join(group["copies"]))
        lines += [f"- CHECK: {c}" for c in m["checks"]]
        lines.append("")
    if catalog.get("scheduleGaps"):
        lines += ["## Scheduled meeting days with no record within ten days", ""] + [f"- {d}" for d in catalog["scheduleGaps"]] + [""]
    if catalog.get("unplaced"):
        lines += ["## Meeting files with no date in their names", ""]
        lines += [f"- {r['kind']}: {r['where']} {r['location']}" for r in catalog["unplaced"]] + [""]
    lines += [f"_Note: {c}_" for c in catalog.get("caveats", [])]
    return lines


def meeting(data_dir: Path, day: str) -> dict[str, Any]:
    """One meeting's records from the stored catalog, with the files its agenda links under each item; a confidential
    record's location is kept, its text is not read."""
    from jason.tasks.agenda_links import for_meeting

    items_file = Path(data_dir) / "meetings" / "agenda-items.json"
    items = []
    if items_file.is_file():
        items = [i for a in json.loads(items_file.read_text(encoding="utf-8")).get("meetings", []) if a["date"] == day for i in a["items"]]
    for m in load(data_dir).get("meetings", []):
        if m["date"] == day:
            return {"found": True, **m, "linked": for_meeting(data_dir, day), "items": items}
    return {"found": False, "note": f"no meeting records on {day}; run `jason meetings`"}


__all__ = ["build", "load", "meeting", "report_lines", "write"]
