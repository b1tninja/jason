"""The association's Zoom meetings, synced to disk and read; and disciplinary hearings planned and, when asked, scheduled.

``sync`` reads the account's history from the specification's first Zoom day (``zoom_history_since``), or from two
weeks before the last sync: the past occurrences of every meeting id the host has, the cloud recordings, and the AI
Companion summaries. Each occurrence is one folder, ``data/zoom/meetings/<date>-<key>/``: ``transcript.vtt`` and its
speaker turns ``transcript.txt``, ``chat.txt``, ``summary.json`` and ``summary.md``, and ``participants.json``. Audio
and video are downloaded only with ``media``. The index is ``data/zoom/meetings.json``.

``meetings_brief`` lists the meetings by kind (``classify_meeting``) with the summary's next steps, and the schedule's
meeting days that have no Zoom meeting. ``meeting_text`` returns one meeting's summary and transcript; an executive
session's or a hearing's is held back unless asked for.

``plan_hearing`` computes a hearing's dates under Civil Code 5855 and drafts its notice; ``save_hearing`` writes the
plan to ``data/zoom/hearings.json`` and the notice to ``data/zoom/hearings/``. Scheduling the Zoom meeting is a
separate step a person takes (``jason hearing --create --yes``). jason never sends the notice.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from jason.zoom.client import Zoom, ZoomError
from jason.zoom.models import (
    NOTICE_DAYS,
    SUSPENSION_NOTICE_DAYS,
    BoardMeetingPlan,
    HearingPlan,
    MeetingKind,
    ZoomMeeting,
    classify_meeting,
    notice_text,
    ExecutiveBreak,
    find_executive_break,
    parse_vtt,
    speakers,
    summary_record,
    summary_text,
    schedule_time,
)

ZOOM_DIR = "zoom"
INDEX = "meetings.json"
HEARINGS = "hearings.json"
BOARD_MEETINGS = "board-meetings.json"   # the board meetings jason scheduled on Zoom, by date
OVERLAP_DAYS = 14                       # a recording or summary can appear days after the meeting
FILE_NAMES = {"TRANSCRIPT": "transcript.vtt", "CHAT": "chat.txt"}
MEDIA_NAMES = {"M4A": "audio.m4a", "MP4": "video.mp4"}
CAVEATS = (
    "Zoom's AI Companion summary is not the minutes: it records no roll call, motion, or vote.",
    "A transcript is Zoom's speech recognition; names and numbers can be wrong.",
    "A board meeting's recording can run on into the executive session that followed it; read before sharing.",
    "An executive session's or a hearing's transcript and summary are confidential (Civil Code 4935) and held back unless asked for.",
)


def zoom_dir(data_dir: Path) -> Path:
    return Path(data_dir) / ZOOM_DIR


def load_index(data_dir: Path) -> dict[str, Any]:
    path = zoom_dir(data_dir) / INDEX
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _key(uuid: str) -> str:
    return hashlib.sha1(uuid.encode("utf-8")).hexdigest()[:10]


def _folder(root: Path, meeting: ZoomMeeting) -> Path:
    day = meeting.start.date().isoformat() if meeting.start else "undated"
    return root / "meetings" / f"{day}-{_key(meeting.uuid)}"


def _utc_day(stamp: str) -> date | None:
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def sync(client: Zoom, data_dir: Path, community: Any, *, full: bool = False, since: date | None = None,
         until: date | None = None, media: bool = False, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read the account's meetings, recordings, and summaries in the window, and save each occurrence's files."""
    say = log or (lambda _msg: None)
    root = zoom_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    index = load_index(data_dir)
    known: dict[str, dict[str, Any]] = {row["uuid"]: row for row in index.get("meetings", [])}
    policy = community.hearing_policy()
    tz = policy.timezone if policy else "America/Los_Angeles"
    rules, schedule = tuple(community.zoom_meeting_rules()), community.meeting_schedule()
    until = until or date.today()
    if since is None:
        through = index.get("through")
        first = community.zoom_history_since() or until - timedelta(days=365)
        since = first if full or not through else max(first, date.fromisoformat(through) - timedelta(days=OVERLAP_DAYS))
    counts = {"occurrences": 0, "new": 0, "transcripts": 0, "summaries": 0, "chats": 0, "media": 0, "failed": 0}

    rows: dict[str, dict[str, Any]] = {}          # uuid -> the richest row seen (past meeting > recording > summary)
    recordings: dict[str, list[dict[str, Any]]] = {}
    summarized: set[str] = set()
    for rec in client.recordings(since, until):
        uuid = str(rec.get("uuid") or "")
        if uuid:
            rows.setdefault(uuid, rec)
            recordings[uuid] = rec.get("recording_files") or []
    say(f"{len(recordings)} recordings from {since} to {until}")
    for row in client.summaries(since, until):
        uuid = str(row.get("meeting_uuid") or "")
        if uuid:
            rows.setdefault(uuid, row)
            summarized.add(uuid)
    say(f"{len(summarized)} AI Companion summaries")
    ids = {str(m.get("id")) for kind in ("previous_meetings", "scheduled") for m in client.meetings(kind) if m.get("id")}
    ids |= {str(r.get("id") or r.get("meeting_id")) for r in rows.values() if r.get("id") or r.get("meeting_id")}
    for meeting_id in sorted(ids):
        for inst in client.past_instances(meeting_id):
            day = _utc_day(str(inst.get("start_time") or ""))
            if inst.get("uuid") and day and since - timedelta(days=1) <= day <= until + timedelta(days=1):
                rows.setdefault(str(inst["uuid"]), {"uuid": inst["uuid"], "id": meeting_id, "start_time": inst.get("start_time")})
    say(f"{len(ids)} meeting ids, {len(rows)} occurrences in the window")

    for uuid, row in rows.items():
        counts["occurrences"] += 1
        old = known.get(uuid, {})
        if not old:
            counts["new"] += 1
        detail = row if old.get("topic") else (client.past_meeting(uuid) or {})
        meeting = ZoomMeeting.from_api({**row, **{k: v for k, v in detail.items() if v not in (None, "")}}, tz)
        if old and not meeting.topic:
            meeting.topic = old.get("topic") or ""
        meeting.kind, meeting.evidence = classify_meeting(meeting.topic, meeting.start, rules, schedule)
        folder = _folder(root, meeting)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            counts_for = _save_files(client, folder, recordings.get(uuid, []), media)
            for name, n in counts_for.items():
                counts[name] += n
            if uuid in summarized and not (folder / "summary.json").is_file():
                body = client.summary(uuid)
                if body:
                    summary = summary_record(body)
                    (folder / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
                    (folder / "summary.md").write_text(summary_text(summary), encoding="utf-8")
                    counts["summaries"] += 1
            if not (folder / "participants.json").is_file():
                people = [{"name": p.get("name"), "email": p.get("user_email"), "join": p.get("join_time"),
                           "leave": p.get("leave_time"), "seconds": p.get("duration")} for p in client.participants(uuid)]
                if people:
                    (folder / "participants.json").write_text(json.dumps(people, indent=1), encoding="utf-8")
        except ZoomError as exc:
            counts["failed"] += 1
            say(f"meeting {meeting.start} {meeting.topic!r}: {exc}")
        meeting.files = {name: str(path.relative_to(root)).replace("\\", "/") for name, path in (
            ("transcript", folder / "transcript.txt"), ("chat", folder / "chat.txt"), ("summary", folder / "summary.md"),
            ("participants", folder / "participants.json")) if path.is_file()}
        known[uuid] = {**old, **meeting.record(), "folder": str(folder.relative_to(root)).replace("\\", "/")}
        if uuid in recordings:
            # What Zoom's cloud still holds for the meeting (MP4, M4A, TRANSCRIPT, CHAT, ...), as of this sync.
            known[uuid]["cloud"] = sorted({str(f.get("file_type") or "").upper() for f in recordings[uuid]} - {""})
            known[uuid]["cloudCheckedAt"] = until.isoformat()

    meetings = sorted(known.values(), key=lambda r: r.get("start") or "", reverse=True)
    (root / INDEX).write_text(json.dumps({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                          "since": min(since.isoformat(), index.get("since") or since.isoformat()),
                                          "through": until.isoformat(), "meetings": meetings}, indent=1, default=str),
                              encoding="utf-8")
    return counts


def _save_files(client: Zoom, folder: Path, files: list[dict[str, Any]], media: bool) -> dict[str, int]:
    counts = {"transcripts": 0, "chats": 0, "media": 0}
    names = {**FILE_NAMES, **(MEDIA_NAMES if media else {})}
    for f in files:
        kind = str(f.get("file_type") or "").upper()
        name = names.get(kind)
        if not name or not f.get("download_url") or (folder / name).is_file():
            continue
        client.download(str(f["download_url"]), folder / name)
        if kind == "TRANSCRIPT":
            turns = parse_vtt((folder / name).read_text(encoding="utf-8", errors="replace"))
            (folder / "transcript.txt").write_text("\n".join(t.line() for t in turns) + "\n", encoding="utf-8")
            counts["transcripts"] += 1
        elif kind == "CHAT":
            counts["chats"] += 1
        else:
            counts["media"] += 1
    return counts


def _summary(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = root / (row.get("folder") or "") / "summary.json"
    return json.loads(path.read_text(encoding="utf-8")) if row.get("folder") and path.is_file() else {}


def meetings_brief(data_dir: Path, community: Any, *, days: int | None = None, kind: str = "", since: str = "",
                   today: date | None = None) -> dict[str, Any]:
    """The meetings on disk, newest first, with each summary's next steps; and scheduled meeting days with no meeting."""
    root = zoom_dir(data_dir)
    index = load_index(data_dir)
    if not index:
        return {"found": False, "note": "no Zoom meetings on disk; run `jason zoom` to sync"}
    today = today or date.today()
    start = date.fromisoformat(since) if since else (today - timedelta(days=days) if days else None)
    out: list[dict[str, Any]] = []
    for row in index.get("meetings", []):
        if kind and kind.casefold() not in (row.get("kind") or "").casefold():
            continue
        if start and (row.get("date") or "") < start.isoformat():
            continue
        entry = {k: row.get(k) for k in ("date", "start", "topic", "kind", "evidence", "duration", "participants", "uuid", "confidential")}
        entry["has"] = sorted((row.get("files") or {}).keys())
        entry["mentions"] = confidential_mentions(root, row)
        _, brk = executive_break(root, row, community)
        entry["executiveSession"] = brk.record() if brk else None
        # The AI summary covers the whole call, the executive session included.
        if not row.get("confidential") and not entry["mentions"] and brk is None:
            entry["nextSteps"] = _summary(root, row).get("nextSteps") or []
        out.append(entry)
    by_kind: dict[str, int] = {}
    for row in out:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    return {"found": True, "syncedAt": index.get("syncedAt"), "since": index.get("since"), "through": index.get("through"),
            "count": len(out), "byKind": by_kind, "meetings": out,
            "scheduleGaps": schedule_gaps(index, community, start=start, today=today), "caveats": list(CAVEATS)}


def schedule_gaps(index: dict[str, Any], community: Any, *, start: date | None = None, today: date | None = None) -> list[dict[str, Any]]:
    """Each of the schedule's meeting days (monthly, as the board meets in practice) from the account's first meeting to
    the end of the synced window with no Zoom meeting that day. A gap may be a cancelled meeting, one held on another account, or one never recorded here."""
    schedule = community.meeting_schedule()
    if schedule is None or not index.get("since"):
        return []
    days = {row.get("date") for row in index.get("meetings", []) if row.get("date")}
    if not days:
        return []
    # Before the account's first meeting, a missing day says only that the history starts later (another account, or
    # meetings Zoom no longer lists).
    first = max(date.fromisoformat(index["since"]), date.fromisoformat(min(days)), *([start] if start else []))
    last = min(date.fromisoformat(index.get("through") or (today or date.today()).isoformat()), today or date.today())
    gaps, day = [], schedule.next_meeting(first - timedelta(days=1), monthly=True)
    while day <= last:
        if day.isoformat() not in days:
            regular = not schedule.regular_months or day.month in schedule.regular_months
            gaps.append({"date": day.isoformat(), "regular": regular or day.month == schedule.annual_month,
                         "note": "no Zoom meeting this day"})
        day = schedule.next_meeting(day, monthly=True)
    return gaps


def _find(index: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = index.get("meetings", [])
    exact = [r for r in rows if key in (r.get("uuid"), r.get("folder"), (r.get("folder") or "").rsplit("/", 1)[-1])]
    return exact or [r for r in rows if r.get("date") == key or r.get("meetingId") == key]


CONFIDENTIAL_WORDS = ("executive session", "hearing")


def confidential_mentions(root: Path, row: dict[str, Any]) -> list[str]:
    """The words in a meeting's transcript or summary that say the call ran into an executive session or a hearing.
    A board meeting's topic does not say so; the board adjourns to executive session on the same call."""
    folder = root / (row.get("folder") or "")
    text = " ".join(p.read_text(encoding="utf-8", errors="replace").lower()
                    for p in (folder / "transcript.txt", folder / "summary.md") if row.get("folder") and p.is_file())
    return [w for w in CONFIDENTIAL_WORDS if w in text]


def _departures(folder: Path, row: dict[str, Any]) -> list[float]:
    """Each participant's last leave, in seconds from the meeting's start."""
    path = folder / "participants.json"
    if not path.is_file() or not row.get("start"):
        return []
    start = datetime.fromisoformat(row["start"])
    last: dict[str, float] = {}
    for p in json.loads(path.read_text(encoding="utf-8")):
        if p.get("leave"):
            t = (datetime.fromisoformat(str(p["leave"]).replace("Z", "+00:00")) - start).total_seconds()
            key = p.get("name") or p.get("email") or str(len(last))
            last[key] = max(last.get(key, t), t)
    return list(last.values())


def executive_break(root: Path, row: dict[str, Any], community: Any) -> tuple[list[Any], ExecutiveBreak | None]:
    """A meeting's transcript turns and where its executive session begins, if the transcript shows one."""
    folder = root / (row.get("folder") or "")
    vtt = folder / "transcript.vtt"
    if not row.get("folder") or not vtt.is_file():
        return [], None
    turns = parse_vtt(vtt.read_text(encoding="utf-8", errors="replace"))
    return turns, find_executive_break(turns, tuple(community.executive_break_patterns()), _departures(folder, row))


def meeting_text(data_dir: Path, key: str, *, include_confidential: bool = False, max_chars: int = 60000,
                 community: Any = None) -> dict[str, Any]:
    """One meeting (by UUID, folder, date, or meeting id): its record, summary, speakers, participants, and transcript.

    When the transcript shows the board adjourning to executive session on the same call, the open portion is given
    and the rest is held back; Zoom's AI summary and the chat cover the whole call, so they are held back too. A
    meeting that mentions an executive session or hearing with no break found is held back whole."""
    if community is None:
        from jason.community import mystique

        community = mystique()
    root = zoom_dir(data_dir)
    found = _find(load_index(data_dir), key)
    if not found:
        return {"found": False, "note": f"no meeting {key!r} on disk"}
    if len(found) > 1:
        return {"found": True, "choose": [{k: r.get(k) for k in ("uuid", "date", "start", "topic", "kind")} for r in found]}
    row = found[0]
    out: dict[str, Any] = {"found": True, "meeting": row, "caveats": list(CAVEATS)}
    turns, brk = executive_break(root, row, community)
    mentions = confidential_mentions(root, row)
    whole = bool(row.get("confidential")) or (bool(mentions) and brk is None)
    if whole and not include_confidential:
        why = f"a {row.get('kind')} is confidential" if row.get("confidential") else \
            f"its recording mentions {', '.join(mentions)} and no adjournment to executive session was found, so it may include one"
        out["heldBack"] = f"{why}; ask with include_confidential to read it"
        return out
    folder = root / (row.get("folder") or "")
    hide_tail = brk is not None and not include_confidential
    if brk is not None:
        out["executiveSession"] = {**brk.record(), "heldBack": hide_tail}
    open_turns = turns[:brk.turn] if hide_tail else turns
    if hide_tail:
        out["heldBack"] = (f"the executive session from {brk.at / 60:.1f} minutes on, and the AI summary and chat, which "
                           "cover the whole call (CIV 4935); ask with include_confidential to read them")
    else:
        out["summary"] = _summary(root, row)
        if (folder / "chat.txt").is_file():
            out["chat"] = (folder / "chat.txt").read_text(encoding="utf-8", errors="replace")[:max_chars]
    if turns:
        out["speakers"] = speakers(open_turns)
        text = "\n".join(t.line() for t in open_turns)
        out["transcript"] = text[:max_chars]
        out["truncated"] = len(text) > max_chars
    if (folder / "participants.json").is_file():
        people = json.loads((folder / "participants.json").read_text(encoding="utf-8"))
        out["participants"] = sorted({p.get("name") or "" for p in people} - {""})
    return out


def brief_lines(brief: dict[str, Any], *, limit: int = 40) -> list[str]:
    if not brief.get("found"):
        return [brief.get("note") or "no meetings"]
    lines = [f"Zoom meetings {brief.get('since')} to {brief.get('through')} (synced {brief.get('syncedAt')}): {brief['count']}",
             "  " + ", ".join(f"{k} {v}" for k, v in sorted(brief["byKind"].items()))]
    for row in brief["meetings"][:limit]:
        has = ", ".join(row["has"]) or "no files"
        lines.append(f"- {row.get('start') or row.get('date')}  {row.get('kind'):<26} {row.get('topic') or ''}  "
                     f"[{row.get('duration') or '?'} min; {row.get('participants') or '?'} joined; {has}]"
                     + (f" (executive session from {row['executiveSession']['minute']} min: held back)" if row.get("executiveSession")
                        else f" (mentions {', '.join(row['mentions'])}: held back)" if row.get("mentions") else ""))
        for step in (row.get("nextSteps") or [])[:5]:
            lines.append(f"    next: {step}")
    if brief["scheduleGaps"]:
        lines.append("Scheduled meeting days with no Zoom meeting:")
        lines += [f"- {g['date']}{'' if g['regular'] else ' (a month the resolution does not make regular)'}" for g in brief["scheduleGaps"]]
    lines += ["", *[f"Note: {c}" for c in brief["caveats"]]]
    return lines


# --- board meetings -------------------------------------------------------------------------------------------------

def plan_board_meeting(community: Any, *, on: date | None = None, at: str = "", today: date | None = None) -> BoardMeetingPlan:
    """A board meeting on ``on`` (default the schedule's next meeting day) at ``at`` (default the schedule's hour)."""
    policy = community.board_meeting_policy()
    if policy is None:
        raise ValueError("the specification sets no board meeting policy (board_meeting_policy)")
    schedule = community.meeting_schedule()
    if on is None:
        if schedule is None:
            raise ValueError("give the meeting's date; the specification sets no meeting schedule")
        on = schedule.next_meeting(today or date.today(), monthly=True)
    hour = schedule_time(at or (schedule.time if schedule else ""))
    if hour is None:
        raise ValueError(f"cannot read the meeting's time {at!r}; give it like '6:30 pm'")
    from zoneinfo import ZoneInfo

    return BoardMeetingPlan(start=datetime.combine(on, hour, tzinfo=ZoneInfo(policy.timezone)), policy=policy)


def save_board_meeting(data_dir: Path, plan: BoardMeetingPlan) -> dict[str, Any]:
    """Keep the scheduled meeting in ``board-meetings.json`` (one row per date); a later run for the same date replaces it."""
    path = zoom_dir(data_dir) / BOARD_MEETINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text(encoding="utf-8")).get("meetings", []) if path.is_file() else []
    record = {**plan.record(), "saved": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    rows = [r for r in rows if r.get("date") != record["date"]] + [record]
    path.write_text(json.dumps({"meetings": sorted(rows, key=lambda r: r["date"])}, indent=1), encoding="utf-8")
    return record


def board_meeting(data_dir: Path, on: date | str) -> dict[str, Any] | None:
    """The scheduled board meeting for ``on``, or None."""
    path = zoom_dir(data_dir) / BOARD_MEETINGS
    if not path.is_file():
        return None
    day = on if isinstance(on, str) else on.isoformat()
    return next((r for r in json.loads(path.read_text(encoding="utf-8")).get("meetings", []) if r.get("date") == day), None)


# --- disciplinary hearings ----------------------------------------------------------------------------------------

def plan_hearing(community: Any, *, address: str, violation: str, on: date | None = None, at: str = "",
                 notice_on: date | None = None, today: date | None = None, suspension: bool = False) -> HearingPlan:
    """A hearing for the owner at ``address``: on ``on`` (default the first meeting day the notice can still reach) at
    ``at`` (default the schedule's hour). ``notice_on`` is the day the notice is delivered, if known."""
    policy = community.hearing_policy()
    if policy is None:
        raise ValueError("the specification sets no hearing policy (hearing_policy)")
    building = community.building_for_address(address)
    if building is None:
        raise ValueError(f"{address!r} is not an address in {community.name}")
    schedule = community.meeting_schedule()
    if on is None:
        if schedule is None:
            raise ValueError("give the hearing's date; the specification sets no meeting schedule")
        earliest = (notice_on or today or date.today()) + timedelta(days=SUSPENSION_NOTICE_DAYS if suspension else NOTICE_DAYS)
        on = schedule.next_meeting(earliest - timedelta(days=1), monthly=True)
    hour = schedule_time(at or (schedule.time if schedule else ""))
    if hour is None:
        raise ValueError(f"cannot read the hearing's time {at!r}; give it like '6:30 pm'")
    from zoneinfo import ZoneInfo

    start = datetime.combine(on, hour, tzinfo=ZoneInfo(policy.timezone))
    return HearingPlan(address=address, building=str(getattr(building.number, "value", building.number)), violation=violation,
                       start=start, policy=policy, notice_on=notice_on, suspension=suspension)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def save_hearing(data_dir: Path, plan: HearingPlan, association: str, *, letter: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write the plan to ``hearings.json`` (one row per address and start) and its notice draft beside it. ``letter``
    is the notice Doc made from the template, kept with the plan; an earlier run's Doc is kept when there is none."""
    root = zoom_dir(data_dir)
    notice = root / "hearings" / f"{plan.start.date().isoformat()}-{_slug(plan.address)}.md"
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_text(notice_text(plan, association), encoding="utf-8")
    path = root / HEARINGS
    rows = json.loads(path.read_text(encoding="utf-8")).get("hearings", []) if path.is_file() else []
    start = plan.start.isoformat(timespec="minutes")
    earlier = next((r for r in rows if (r.get("address"), r.get("start")) == (plan.address, start)), {})
    doc = {k: letter[k] for k in ("id", "url", "unfilled")} if letter else earlier.get("noticeDoc")
    record = {**plan.record(), "notice": str(notice.relative_to(root)).replace("\\", "/"), "noticeDoc": doc,
              "saved": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    rows = [r for r in rows if (r.get("address"), r.get("start")) != (record["address"], record["start"])] + [record]
    path.write_text(json.dumps({"hearings": sorted(rows, key=lambda r: r["start"])}, indent=1), encoding="utf-8")
    return record


def hearings(data_dir: Path, *, today: date | None = None) -> dict[str, Any]:
    """The saved hearings, each with where it stands against its notice and decision deadlines."""
    path = zoom_dir(data_dir) / HEARINGS
    if not path.is_file():
        return {"found": False, "hearings": [], "note": "no hearings saved; plan one with `jason hearing`"}
    today = today or date.today()
    out = []
    for row in json.loads(path.read_text(encoding="utf-8")).get("hearings", []):
        held = date.fromisoformat(row["start"][:10])
        if held < today:
            stand = f"held {held}? the written decision is due by {row['decisionByIfHeld']} if the board acted (CIV 5855(f))"
        elif date.fromisoformat(row["noticeBy"]) < today and not row.get("noticeOn"):
            stand = f"the notice was due by {row['noticeBy']} and no delivery is recorded: the hearing must move (CIV 5855(a))"
        else:
            stand = f"notice by {row['noticeBy']}" + (f" (delivered {row['noticeOn']})" if row.get("noticeOn") else "")
        out.append({**row, "standing": stand, "scheduled": bool((row.get("zoom") or {}).get("id"))})
    return {"found": True, "hearings": out}


def hearing_lines(plan: HearingPlan, record: dict[str, Any] | None = None) -> list[str]:
    lines = [f"Hearing for {plan.address} (building {plan.building or '?'}) on {plan.start:%Y-%m-%d %I:%M %p} {plan.policy.timezone}",
             f"- the notice must be delivered by {plan.notice_by} ({plan.notice_days} days before; {plan.notice_authority}; a mailed notice is delivered on deposit, CIV 4050(b))",
             f"- if held solely in executive session, notice the members of its time and place by {plan.executive_notice_by} (CIV 4920(b)(2))",
             f"- the written decision is due within 14 days of the board's action: by {plan.decision_by_if_held} if it acts that night (CIV 5855(f))"]
    lines += [f"- PROBLEM: {p}" for p in plan.problems]
    if plan.zoom.get("id"):
        lines.append(f"- Zoom meeting {plan.zoom['id']}: {plan.zoom.get('joinUrl')} (passcode {plan.zoom.get('passcode')})")
    else:
        lines.append("- no Zoom meeting scheduled; `--create --yes` schedules one: " + json.dumps(plan.meeting_body()))
    if record:
        lines.append(f"- notice draft: data/zoom/{record['notice']}")
    return lines


__all__ = ["CAVEATS", "brief_lines", "hearing_lines", "hearings", "load_index", "meeting_text", "meetings_brief", "plan_hearing",
           "save_hearing", "schedule_gaps", "sync", "zoom_dir"]
