"""What shows a notice went out, and how strongly: the one reader of a notice's evidence.

Three readers judge a notice clock against the record, and all of them read it here:

- ``jason record-stages`` (``tasks.record_stages``): a rule change's notices of the proposed and the adopted change
  (Civil Code 4360(a), (c));
- the meeting watch (``tasks.meeting_watch``, ``jason schedule-evidence --watch``, ``jason attention``): each board
  meeting's notice to members (4920);
- the evidence finder (``tasks.schedule_evidence``): the same notices, read backward for a duty's occurrence.

Each record of a notice has a strength (``NoticeStrength``):

- **delivered**: every member the delivery ledger holds was reached by a method the notice allows (an email the
  receiving server accepted, a letter in the mail, 4050); or a general notice posted where the annual policy statement
  designates (4045(a)), with its individual deliveries to the members who asked for them (4045(b));
- **sent, with follow-ups owed**: the ledger shows members owed a resend: a bounce (4041(e)), a returned letter, a
  member with no address on file (``notice_ledger.FOLLOW_UPS``); the follow-ups are listed with it;
- **sent**: the notice went out, but its outcomes are not synced (PayHOA's log shows the send; the Mailroom, a copy
  from the association's mail; a ledger whose attempts have no outcome yet);
- **file**: jason has the notice's file (a Drive file, a library file) but no record that it went out.

A clock is met by a delivery on time, or by a send on time with its outstanding follow-ups listed. A file never meets
one (``judge``). The ledger is read only (``data/notices/deliveries.db``, opened read-only); a member's identity never
leaves ``weigh``: a record carries counts.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.notices import Method, NoticeKind, NoticeRequirement, NoticeStrength

Strength = NoticeStrength
LEDGER = Path("notices") / "deliveries.db"
ADDRESS = "jason://notice/"
# The methods the ledger can show: an email accepted, a first-class letter in the mail. A notice that must go by
# certified mail, personal service, or personal delivery is proved by its receipts, not by these.
LEDGER_METHODS = frozenset({Method.INDIVIDUAL, Method.GENERAL, Method.FIRST_CLASS_MAIL, Method.ELECTRONIC,
                            Method.WRITTEN})
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _utc_day(stamp: str) -> date | None:
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).date()


def date_in(text: str) -> date | None:
    """The first YYYY-MM-DD a text carries (a posting recorded as "the mailroom board, 2099-01-10"); None if none."""
    m = _DAY.search(str(text or ""))
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(0))
    except ValueError:
        return None


@dataclass(frozen=True)
class NoticeRecord:
    """One record that a notice went out (or was written), with its strength. Counts only: no member's identity."""

    what: str                                  # the record, and where it is kept
    on: date | None                            # the day it went out (posted, deposited, transmitted); a file: written
    strength: NoticeStrength
    source: str = ""                           # the notice's address, drive:<id>, library:<id>, or the store
    key: str = ""                              # the delivery ledger's key, when the ledger holds it
    requirement: str = ""                      # the notice catalog's key the ledger key names
    members: int = 0                           # members the ledger holds
    reached: int = 0
    owed: int = 0                              # members owed a resend
    unsynced: int = 0                          # members not reached whose attempt has no outcome yet
    asks: int = 0                              # members to ask for an address (reached another way)
    follow_ups: tuple[tuple[str, str, str, int], ...] = ()     # (follow-up key, force, authority, members) owed
    general: bool = False                      # recorded as a general notice that was posted (4045)
    posted: str = ""                           # where and when, as a person recorded it
    agenda: bool = False                       # the agenda alone, not the notice (a meeting's)
    note: str = ""

    @property
    def address(self) -> str:
        return f"{ADDRESS}{self.key}" if self.key else ""

    def describe(self) -> str:
        """The strength in words, with the follow-ups owed and how many members are not synced."""
        s = self.strength
        if s is Strength.DELIVERED:
            if self.general:
                return (f"delivered: posted ({self.posted or 'where the policy statement designates'}), 4045(a)"
                        + (f"; {self.reached} of {self.members} members reached by the messages" if self.members else ""))
            if self.members:
                return f"delivered: {self.reached} of {self.members} members reached"
            return "delivered" + (f": {self.note}" if self.note else "")
        if s is Strength.FOLLOW_UPS:
            owed = "; ".join(f"{n} {k} [{force}; {auth}]" for k, force, auth, n in self.follow_ups)
            tail = f"; {self.unsynced} not yet synced" if self.unsynced else ""
            return (f"sent, with follow-ups owed: {self.owed} member{'s' if self.owed != 1 else ''} owed a resend "
                    f"({owed}); {self.reached} of {self.members} reached{tail}")
        if s is Strength.SENT:
            if self.key:
                return (f"sent: {self.unsynced} member{'s' if self.unsynced != 1 else ''}' outcomes not synced; "
                        f"{self.reached} of {self.members} reached so far (jason notices {self.key} --sync)")
            return "sent: its outcomes are not synced" + (f" ({self.note})" if self.note else "")
        return "file: no record that it went out" + (f" ({self.note})" if self.note else "")

    def row(self) -> dict[str, Any]:
        return {"what": self.what, "on": self.on.isoformat() if self.on else None, "strength": self.strength.value,
                "source": self.source, "key": self.key, "address": self.address, "requirement": self.requirement,
                "members": self.members, "reached": self.reached, "owed": self.owed, "unsynced": self.unsynced,
                "asks": self.asks, "followUps": [{"key": k, "force": f, "authority": a, "members": n}
                                                 for k, f, a, n in self.follow_ups],
                "general": self.general, "posted": self.posted, "agenda": self.agenda, "describe": self.describe(),
                "note": self.note}


# ---------------------------------------------------------------------------------------------------------------
# The ledger.


def shows_method(requirement: NoticeRequirement | None) -> bool:
    """Whether the ledger's emails and first-class letters are a method the requirement allows (None: no row says)."""
    if requirement is None:
        return True
    if requirement.kind in (NoticeKind.INDIVIDUAL, NoticeKind.GENERAL):
        return True
    return not requirement.methods or bool(set(requirement.methods) & LEDGER_METHODS)


def weigh(key: str, attempts: Iterable[Any], *, general: bool = False, posted: str = "",
          individual: Iterable[int] = (), requirement: NoticeRequirement | None = None,
          local_day: Callable[[str], date | None] | None = None) -> NoticeRecord | None:
    """One notice's ledger attempts as a record of its delivery. ``general`` and ``posted``: the notice was recorded
    as a general notice posted where the policy statement designates (``notice_ledger.set_general``), so the posting
    delivered it to every member but those in ``individual`` (4045(b)). A member owed a resend who has another
    attempt with no outcome yet (the resend itself, not yet synced) is counted unsynced, not owed. None for a notice
    with no attempts."""
    from jason.tasks.notice_ledger import GENERAL_NOTE, Delivery, standing

    attempts = list(attempts)
    if not attempts:
        return None
    day = local_day or _utc_day
    found = standing(attempts, general=general, individual=frozenset(individual))
    sent = sorted(d for a in attempts if a.sent_at and (d := day(a.sent_at)))
    first = sent[0] if sent else None
    owed_rows: Counter[tuple[str, str, str]] = Counter()
    owed = unsynced = asks = 0
    for s in found:
        resends = [(f, a) for f, a in s.follow_ups if f.resend]
        pending = [a for a in s.attempts if a.status is Delivery.PENDING]
        if resends and any(p.channel != a.channel for p in pending for _, a in resends):
            unsynced += 1                        # the resend went another way and has no outcome yet
        elif resends:
            owed += 1
            for f, _ in resends:
                owed_rows[(f.key, f.force, f.authority)] += 1
        elif not s.reached and pending:
            unsynced += 1
        if any(not f.resend and f is not GENERAL_NOTE for f, _ in s.follow_ups):
            asks += 1
    reached = sum(1 for s in found if s.reached)
    follow = tuple((k, force, auth, n) for (k, force, auth), n in sorted(owed_rows.items()))
    from jason.community.notice_catalog import for_ledger

    req = requirement or for_ledger(key)
    posted_on = date_in(posted) if general else None
    common = dict(source=f"{ADDRESS}{key}", key=key, requirement=req.key if req else "", members=len(found),
                  reached=reached, owed=owed, unsynced=unsynced, asks=asks, follow_ups=follow, general=general,
                  posted=posted)
    what = f"{key} (notice ledger)"
    if owed:
        return NoticeRecord(what, posted_on or first, Strength.FOLLOW_UPS, **common)
    if general and posted:
        return NoticeRecord(what, posted_on or first, Strength.DELIVERED, **common)
    if not shows_method(req):
        return NoticeRecord(what, first, Strength.SENT, note="the ledger shows emails and first-class letters; this "
                            f"notice goes by {', '.join(m.value for m in req.methods)}: its receipts prove it", **common)
    if unsynced or reached < len(found):
        return NoticeRecord(what, first, Strength.SENT, **common)
    return NoticeRecord(what, first, Strength.DELIVERED, **common)


def _attempts(con: sqlite3.Connection) -> dict[str, list[Any]]:
    from jason.tasks.notice_ledger import Attempt, Delivery

    out: dict[str, list[Any]] = {}
    for r in con.execute("select notice, membership_id, unit_id, unit, channel, batch, key, sent_at, status, "
                         "status_at, reason from attempts order by notice, unit, membership_id, sent_at"):
        try:
            status = Delivery(r[8])
        except ValueError:
            status = Delivery.PENDING
        out.setdefault(str(r[0]), []).append(Attempt(str(r[0]), int(r[1] or 0), int(r[2] or 0), str(r[3] or ""),
                                                     str(r[4] or ""), str(r[5] or ""), str(r[6] or ""),
                                                     str(r[7] or ""), status, str(r[9] or ""), str(r[10] or "")))
    return out


def read(data_dir: Path) -> tuple[dict[str, list[Any]], dict[str, tuple[bool, str]], dict[str, str]]:
    """The ledger read only: each notice's attempts, its recorded kind (general, posted), and when it was last
    synced. Empty when there is no ledger."""
    path = Path(data_dir) / LEDGER
    if not path.is_file():
        return {}, {}, {}
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        attempts = _attempts(con)
        synced = {str(k): str(v or "") for k, v in con.execute(
            "select notice, max(synced_at) from attempts group by notice")}
        try:
            kinds = {str(r[0]): (bool(r[1]), str(r[2] or "")) for r in con.execute(
                "select notice, general, posted from notice_kinds")}
        except sqlite3.Error:
            kinds = {}
    except sqlite3.Error:
        return {}, {}, {}
    finally:
        con.close()
    return attempts, kinds, synced


def posting(key: str, posted: str, requirement: NoticeRequirement | None = None) -> NoticeRecord:
    """A general notice a person recorded as posted (``jason notices KEY --mark-general --posted ... --by ...``) with
    no messages in the ledger: delivered by the posting (4045(a)), on the day its ``posted`` text carries (with no day
    in it, it is undated and meets no clock)."""
    from jason.community.notice_catalog import for_ledger

    req = requirement or for_ledger(key)
    return NoticeRecord(f"{key} (a posting recorded)", date_in(posted), Strength.DELIVERED, f"{ADDRESS}{key}", key,
                        req.key if req else "", general=True, posted=posted,
                        note="a posting a person recorded; no messages in the ledger")


def ledger(data_dir: Path, local_day: Callable[[str], date | None] | None = None) -> dict[str, NoticeRecord]:
    """Every notice in the delivery ledger as a record of its delivery (``weigh``), and each general notice a person
    recorded as posted with no messages (``posting``), read only."""
    attempts, kinds, _ = read(data_dir)
    out: dict[str, NoticeRecord] = {}
    for key, rows in attempts.items():
        general, posted = kinds.get(key, (False, ""))
        found = weigh(key, rows, general=general, posted=posted, local_day=local_day)
        if found is not None:
            out[key] = found
    for key, (general, posted) in kinds.items():
        if key not in out and general and posted:
            out[key] = posting(key, posted)
    return out


def recent(data_dir: Path, limit: int | None = None) -> list[tuple[str, str]]:
    """The ledger's notices, newest first by their latest attempt, as (key, latest attempt's time)."""
    attempts, kinds, _ = read(data_dir)
    found = {k: max((a.sent_at for a in v), default="") for k, v in attempts.items()}
    for k, (general, posted) in kinds.items():
        if k not in found and general and posted:
            day = date_in(posted)
            found[k] = day.isoformat() if day else ""
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    return rows[:limit] if limit is not None else rows


# ---------------------------------------------------------------------------------------------------------------
# A board meeting's notice: the ledger and the meeting catalog.


def _source(rec: dict[str, Any]) -> str:
    where, ref = str(rec.get("where") or ""), str(rec.get("ref") or "")
    if where == "Drive" and ref:
        return f"drive:{ref}"
    if where == "PayHOA library" and ref:
        return f"library:{ref}"
    return f"{where}:{ref}" if ref else where


def _written(row: dict[str, Any]) -> date | None:
    days = []
    for k in ("created", "modified"):
        try:
            days.append(date.fromisoformat(str(row.get(k) or "")[:10]))
        except ValueError:
            pass
    return min(days) if days else None


def meeting_notices(stores: Any, day: date) -> list[NoticeRecord]:
    """Every record of the notice to members of the meeting on ``day``, on or before it:

    - the delivery ledger's notices whose key carries the day (``board-meeting-2099-01-14``), as the ledger weighs them;
    - the meeting catalog's notice sent (PayHOA's log, a copy from the association's mail): sent;
    - the catalog's notice file with no send (Drive, the library): a file, dated by the day it was written;
    - the agenda, sent or filed, only when no notice of either kind is on record (it goes with the notice, 4920(d)).

    jason's own drafts and confidential records are left out. ``stores`` is ``schedule_evidence.Stores``."""
    notices: list[NoticeRecord] = []
    agendas: list[NoticeRecord] = []
    drive = stores.drive_files()
    for rec in stores.meetings().get(day, {}).get("records", []):
        kind = rec.get("kind")
        if kind not in ("meeting notice", "agenda") or rec.get("where") == "jason draft" or rec.get("confidential"):
            continue
        what = f"{rec.get('name')} ({rec.get('where')})"
        into = notices if kind == "meeting notice" else agendas
        agenda = kind == "agenda"
        if rec.get("sent"):
            d = stores.local_day(rec["sent"])
            if d and d <= day:
                into.append(NoticeRecord(what, d, Strength.SENT, _source(rec), agenda=agenda,
                                         note=str(rec.get("note") or "")))
            continue
        written = _written(drive.get(str(rec.get("ref") or ""), {})) if rec.get("where") == "Drive" else None
        if written is None or written <= day:
            into.append(NoticeRecord(what, written, Strength.FILE, _source(rec), agenda=agenda,
                                     note="written " + str(written) if written else "undated"))
    for key, rec in stores.ledger().items():
        if day.isoformat() in key and rec.on and rec.on <= day:
            notices.append(rec)
    return notices or agendas


def choose(records: Iterable[NoticeRecord], deadline: date | None = None) -> NoticeRecord | None:
    """The record that judges a clock ending on ``deadline``: of the records that count and are on time, the notice
    before its agenda, then the strongest, then the earliest; else the earliest that counts (late); else the earliest
    file (an undated one last)."""
    records = list(records)
    counting = [r for r in records if r.strength.counts and r.on]
    def order(r: NoticeRecord) -> tuple[Any, ...]:
        return (r.agenda, r.strength.rank, r.on or date.max, "preview" in r.what.lower(), r.what)

    on_time = [r for r in counting if deadline is None or r.on <= deadline]
    if on_time:
        return min(on_time, key=order)
    if counting:
        return min(counting, key=lambda r: (r.on, r.agenda, r.strength.rank, r.what))
    files = [r for r in records if not r.strength.counts]
    if deadline is not None:
        timely = [r for r in files if r.on and r.on <= deadline]
        if timely:
            return min(timely, key=order)
    return min(files, key=order) if files else None


class Verdict(Enum):
    MET = "met"                    # a delivery, or a send with its follow-ups listed, on time
    LATE = "late"                  # the first that counts is after the deadline
    FILE = "file"                  # only a file, written by the deadline: not met
    FILE_LATE = "file late"        # only a file, written after the deadline
    UNDATED = "undated"            # only a file with no date
    OPEN = "open"                  # nothing on record, the deadline ahead
    PASSED = "passed"              # nothing on record, the deadline passed


def judge(records: Iterable[NoticeRecord], deadline: date, today: date) -> tuple[Verdict, NoticeRecord | None]:
    """A clock ending on ``deadline``, judged on ``today`` against the records: a file never meets it."""
    r = choose(records, deadline)
    if r is None:
        return (Verdict.PASSED if today > deadline else Verdict.OPEN), None
    if r.strength.counts:
        return (Verdict.MET if r.on <= deadline else Verdict.LATE), r
    if r.on is None:
        return Verdict.UNDATED, r
    return (Verdict.FILE if r.on <= deadline else Verdict.FILE_LATE), r


__all__ = ["ADDRESS", "LEDGER", "LEDGER_METHODS", "NoticeRecord", "Strength", "Verdict", "choose", "date_in", "judge",
           "ledger", "meeting_notices", "posting", "read", "recent", "shows_method", "weigh"]
