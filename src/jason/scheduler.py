"""The scheduler: each community's ``schedules`` table and the loop in ``jason serve`` that adds due sources to the job
queue (docs/scheduler-daemon-design.md, build step 2).

**The table.** ``schedules`` sits in the community's ``jobs.db`` beside ``jobs``: one row per source the integrations
registry declares (``jason.integrations.registry.cadences``), with its command, its cadence (``every`` or a five-field
``cron``, a ``window`` of hours in the community's time zone, and the registry's ``outside`` cadence for the other
hours), the floor, where the setting came from (the registry's default, or an administrator's change with who and
when), whether a person has adopted it, a pause (by, when, why; a person's or a sign-in failure's), and the bookkeeping:
next due, last enqueued, last job and its result, consecutive failures, and the backoff. ``seed`` writes the rows from
the registry; a registry change updates each row's defaults and keeps an administrator's change.

**Adopted first.** The registry's cadences are defaults for the board or the administrator to adopt
(integrations-design.md, open decision 6), so a seeded row runs only once a person adopts it: ``jason cadence --restore
SOURCE`` (or ``--restore-all``) adopts the default, and ``jason cadence SOURCE --every ...`` adopts a change.

**The loop** (``run``, one thread per served community) wakes every 30 to 60 seconds and, for each source (``tick``):
- takes in its last job's outcome: done clears the failures; a failure counts, and backs off exponentially from the
  floor (``backoff``), or until the ``Retry-After`` the job printed (``retry_after``), whichever is later;
- pauses the source's whole integration on a sign-in failure (``KeeperAuthRequired``, ``GoogleAuthRequired``, a 401,
  or the connection's check saying it needs sign-in). Nothing retries it on a timer: a person's successful check
  (``jason integrations check KEY --live``) or ``jason cadence --resume SOURCE`` clears it;
- adds the source's command to the queue (``jobs.add``: the same lanes and locks as a person's job) when it is due, in
  its window, past its backoff, never sooner than its floor after the last, and only when no job for the same command
  is queued or running (coalesced);
- after downtime, a missed run is one catch-up run (``run-once``), never a burst; ``skip`` moves to the next slot.

A command that writes (it carries ``--yes``) is never scheduled: the registry's writes stay off, and a scheduled write
is the board's decision (docs/jobs.md). A ``manual`` source (one a person must run) is shown and never scheduled.

Each decision is a JSON line in ``<data>/jobs/scheduler.jsonl``; a person's change carries who and when. Nothing here
calls a service: the jobs it adds do, in the worker.
"""

from __future__ import annotations

import email.utils
import json
import os
import random
import re
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from jason import jobs
from jason.integrations.registry import cadences, duration, integration_of

TICK_SECONDS = (30.0, 60.0)              # the loop wakes at a random point in this span
GRACE = timedelta(minutes=5)             # later than this past its due time, a run was missed (misfire)
BACKOFF_BASE = timedelta(minutes=5)      # the first wait after a failure, unless the floor is longer
BACKOFF_CAP = timedelta(hours=24)        # the longest wait, unless the floor is longer
RETRY_AFTER_CAP = timedelta(days=7)      # a Retry-After further off than this is held to it
JITTER_SHARE = 0.1                       # up to a tenth of the gap ...
JITTER_CAP = timedelta(minutes=5)        # ... and never more than five minutes
NEXT_SHOWN = 5                           # the next runs the heartbeat carries
DEFAULT_ZONE = "America/Los_Angeles"     # the zone a profile that names none is read in, as the hearing policy's
LOG = "scheduler.jsonl"
PENDING = ("queued", "running")


class Setting(Enum):
    """Where a schedule's cadence came from."""

    DEFAULT = "default"                  # the integration's default (jason.integrations.registry)
    ADMIN = "admin"                      # an administrator's change, with who and when


class PauseKind(Enum):
    PERSON = "person"
    SIGN_IN = "sign-in"


class Misfire(Enum):
    """What a run missed during downtime becomes."""

    RUN_ONCE = "run-once"                # one catch-up run, coalesced
    SKIP = "skip"                        # none; the next slot


class ScheduleRefused(ValueError):
    """A change to a schedule that cannot be made as asked, with why."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    key TEXT PRIMARY KEY,
    integration TEXT NOT NULL DEFAULT '',
    argv TEXT NOT NULL,
    every TEXT NOT NULL DEFAULT '',
    cron TEXT NOT NULL DEFAULT '',
    run_window TEXT NOT NULL DEFAULT '',
    outside TEXT NOT NULL DEFAULT '',
    floor TEXT NOT NULL DEFAULT '',
    stale_after TEXT NOT NULL DEFAULT '',
    default_every TEXT NOT NULL DEFAULT '',
    default_cron TEXT NOT NULL DEFAULT '',
    default_window TEXT NOT NULL DEFAULT '',
    setting TEXT NOT NULL DEFAULT 'default',
    set_by TEXT NOT NULL DEFAULT '',
    set_at TEXT NOT NULL DEFAULT '',
    adopted INTEGER NOT NULL DEFAULT 0,
    misfire TEXT NOT NULL DEFAULT 'run-once',
    manual TEXT NOT NULL DEFAULT '',
    refused TEXT NOT NULL DEFAULT '',
    retired TEXT NOT NULL DEFAULT '',
    paused INTEGER NOT NULL DEFAULT 0,
    pause_kind TEXT NOT NULL DEFAULT '',
    paused_by TEXT NOT NULL DEFAULT '',
    paused_at TEXT NOT NULL DEFAULT '',
    paused_why TEXT NOT NULL DEFAULT '',
    resumed_by TEXT NOT NULL DEFAULT '',
    resumed_at TEXT NOT NULL DEFAULT '',
    next_due TEXT NOT NULL DEFAULT '',
    last_enqueued TEXT NOT NULL DEFAULT '',
    last_job INTEGER NOT NULL DEFAULT 0,
    last_result TEXT NOT NULL DEFAULT '',
    last_finished TEXT NOT NULL DEFAULT '',
    failures INTEGER NOT NULL DEFAULT 0,
    backoff_until TEXT NOT NULL DEFAULT ''
)
"""

WRITES_REFUSED = ("it writes (--yes): the scheduler never adds a write; a scheduled write is the board's decision and "
                  "needs a person's confirmation (docs/jobs.md)")


# --- times -------------------------------------------------------------------------------------------------------------

def _s(at: datetime | None) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="seconds") if at else ""


def _t(text: str) -> datetime | None:
    if not text:
        return None
    try:
        at = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def zone_of(profile: str) -> str:
    """The community's time zone: its hearing policy's (the zone its meetings are held in), else ``DEFAULT_ZONE``."""
    try:
        from jason.community.profile import load_profile

        policy = load_profile(profile).hearing_policy()
        return str(getattr(policy, "timezone", "") or DEFAULT_ZONE)
    except Exception:  # noqa: BLE001 - a profile that cannot load or names no zone: the default
        return DEFAULT_ZONE


# --- windows and crons -------------------------------------------------------------------------------------------------

_WINDOW = re.compile(r"^(\d{1,2})-(\d{1,2})$")


def parse_window(text: str) -> tuple[int, int] | None:
    """``"07-22"`` as (7, 22): from 07:00 up to 22:00. ``"22-06"`` runs over midnight. "" is no window."""
    if not text:
        return None
    hit = _WINDOW.match(text.strip())
    if not hit:
        raise ScheduleRefused(f"{text!r} is not a window of hours like 07-22")
    start, end = int(hit.group(1)), int(hit.group(2))
    if not (0 <= start <= 23 and 1 <= end <= 24) or start == end:
        raise ScheduleRefused(f"{text!r} is not a window of hours like 07-22 (00 to 24, start and end differ)")
    return start, end


def in_window(at: datetime, window: str, zone: tzinfo) -> bool:
    hours = parse_window(window)
    if hours is None:
        return True
    start, end = hours
    h = at.astimezone(zone).hour
    return start <= h < end if start < end else (h >= start or h < end)


def window_opens(after: datetime, window: str, zone: tzinfo) -> datetime:
    """The next time the window opens, after ``after``."""
    start, _ = parse_window(window) or (0, 24)
    local = after.astimezone(zone)
    opens = datetime(local.year, local.month, local.day, start, tzinfo=zone)
    if opens <= local:
        nxt = local.date() + timedelta(days=1)
        opens = datetime(nxt.year, nxt.month, nxt.day, start, tzinfo=zone)
    return opens.astimezone(timezone.utc)


def _cron_field(text: str, lo: int, hi: int, name: str) -> frozenset[int]:
    out: set[int] = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, raw = part.split("/", 1)
            if not raw.isdigit() or int(raw) < 1:
                raise ScheduleRefused(f"cron {name} {text!r}: a step is a whole number")
            step = int(raw)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            x, _, y = part.partition("-")
            if not (x.isdigit() and y.isdigit()):
                raise ScheduleRefused(f"cron {name} {text!r}: numbers only (no names)")
            a, b = int(x), int(y)
        elif part.isdigit():
            a = b = int(part)
            if step > 1:
                b = hi
        else:
            raise ScheduleRefused(f"cron {name} {text!r}: numbers, ranges, lists, and steps only (no names)")
        if a < lo or b > hi or a > b:
            raise ScheduleRefused(f"cron {name} {text!r}: out of {lo}-{hi}")
        out.update(range(a, b + 1, step))
    return frozenset(out)


@dataclass(frozen=True)
class Cron:
    """A five-field cron (minute, hour, day of month, month, day of week; Sunday 0 or 7), read in the community's zone.
    As cron does, a day of the month and a day of the week both given match on either."""

    text: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]
    any_day: bool
    any_weekday: bool

    @classmethod
    def parse(cls, text: str) -> Cron:
        fields = str(text).split()
        if len(fields) != 5:
            raise ScheduleRefused(f"{text!r} is not a five-field cron (minute hour day month weekday)")
        m, h, dom, mon, dow = fields
        weekdays = frozenset(d % 7 for d in _cron_field(dow, 0, 7, "weekday"))
        return cls(text, _cron_field(m, 0, 59, "minute"), _cron_field(h, 0, 23, "hour"), _cron_field(dom, 1, 31, "day"),
                   _cron_field(mon, 1, 12, "month"), weekdays, dom == "*", dow == "*")

    def day_matches(self, d: date) -> bool:
        if d.month not in self.months:
            return False
        on_day, on_weekday = d.day in self.days, (d.isoweekday() % 7) in self.weekdays
        if self.any_day and self.any_weekday:
            return True
        if self.any_day:
            return on_weekday
        if self.any_weekday:
            return on_day
        return on_day or on_weekday

    def fires(self, after: datetime, zone: tzinfo, *, days: int = 400) -> Iterable[datetime]:
        """Each time it fires after ``after`` (UTC), for up to ``days`` days."""
        local = after.astimezone(zone)
        for offset in range(days):
            d = local.date() + timedelta(days=offset)
            if not self.day_matches(d):
                continue
            for h in sorted(self.hours):
                for mi in sorted(self.minutes):
                    at = datetime(d.year, d.month, d.day, h, mi, tzinfo=zone)
                    if at > local:
                        yield at.astimezone(timezone.utc)

    def next_after(self, after: datetime, zone: tzinfo, window: str = "") -> datetime | None:
        for at in self.fires(after, zone, days=366 * 5):
            if in_window(at, window, zone):
                return at
        return None

    def shortest_gap(self, zone: tzinfo, start: datetime) -> timedelta | None:
        """The shortest gap between two runs over the month from ``start``; None when it fires at most once in it."""
        gap, prev = None, None
        for n, at in enumerate(self.fires(start, zone, days=32)):
            if prev is not None:
                gap = at - prev if gap is None else min(gap, at - prev)
            prev = at
            if n > 5000:
                break
        return gap


def floor_refusal(every: str, cron: str, floor: str, *, zone: tzinfo, now: datetime) -> str:
    """Why a cadence is faster than the floor, or "" when it is not."""
    least = duration(floor) if floor else None
    if every:
        try:
            gap = duration(every)
        except ValueError as exc:
            raise ScheduleRefused(str(exc)) from None
        if gap is None or gap <= timedelta(0):
            raise ScheduleRefused(f"{every!r} is not a duration like 10m, 2h, or 9d")
    else:
        gap = Cron.parse(cron).shortest_gap(zone, now)
    if least is not None and gap is not None and gap < least:
        return (f"{every or cron!r} runs every {_words(gap)} at its closest, faster than the floor {floor} its "
                f"integration declares (from its published or polite rate); jason never schedules faster than the floor")
    return ""


def _words(gap: timedelta) -> str:
    minutes = int(gap.total_seconds() // 60)
    if minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


# --- failures ----------------------------------------------------------------------------------------------------------

_SIGN_IN_MORE = re.compile(r"\b401\b|Unauthorized|invalid_grant", re.IGNORECASE)
_RETRY_AFTER = re.compile(r"retry-after\s*[:=]\s*(?P<value>[^\r\n]+)", re.IGNORECASE)


def sign_in_failure(text: str) -> bool:
    """Whether a job's last lines say it failed for want of a sign-in: the Status screen's words (``AuthRequired``,
    ``jason login``, ``not signed in``, ...) or a 401."""
    from jason.web.extra.status import _SIGN_IN_WORDS

    text = str(text or "")
    return bool(_SIGN_IN_WORDS.search(text) or _SIGN_IN_MORE.search(text))


def retry_after(text: str, now: datetime) -> datetime | None:
    """The time a job's output asked to wait until: its last ``Retry-After: VALUE`` line, the value in seconds, an
    HTTP date (RFC 9110), or an ISO 8601 time (as Zoom sends on a daily limit); held to ``RETRY_AFTER_CAP``."""
    found = list(_RETRY_AFTER.finditer(str(text or "")))
    if not found:
        return None
    value = found[-1].group("value").strip()
    at: datetime | None = None
    if re.fullmatch(r"\d+(\.\d+)?", value):
        at = now + timedelta(seconds=float(value))
    else:
        try:
            at = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            at = _t(value)
        if at is not None and at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
    if at is None:
        return None
    return min(at, now + RETRY_AFTER_CAP)


def backoff(failures: int, floor: str = "") -> timedelta:
    """The wait after ``failures`` failures in a row: ``BACKOFF_BASE`` (or the floor, when longer) doubled each time,
    up to ``BACKOFF_CAP`` (or the floor)."""
    least = duration(floor) if floor else None
    base = max(BACKOFF_BASE, least) if least else BACKOFF_BASE
    cap = max(BACKOFF_CAP, base)
    return min(base * (2 ** max(0, failures - 1)), cap)


# --- the rows ----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Schedule:
    key: str
    integration: str
    argv: tuple[str, ...]
    every: str = ""
    cron: str = ""
    window: str = ""
    outside: str = ""
    floor: str = ""
    stale_after: str = ""
    default_every: str = ""
    default_cron: str = ""
    default_window: str = ""
    setting: Setting = Setting.DEFAULT
    set_by: str = ""
    set_at: str = ""
    adopted: bool = False
    misfire: Misfire = Misfire.RUN_ONCE
    manual: str = ""
    refused: str = ""
    retired: str = ""
    paused: bool = False
    pause_kind: PauseKind | None = None
    paused_by: str = ""
    paused_at: str = ""
    paused_why: str = ""
    resumed_by: str = ""
    resumed_at: str = ""
    next_due: str = ""
    last_enqueued: str = ""
    last_job: int = 0
    last_result: str = ""
    last_finished: str = ""
    failures: int = 0
    backoff_until: str = ""

    @property
    def command(self) -> str:
        return "jason " + " ".join(self.argv)

    def words(self) -> str:
        when = f"every {self.every}" if self.every else f"cron {self.cron}"
        if self.window:
            when += f" {self.window}"
        if self.outside and self.every:
            when += f" ({self.outside} outside)"
        return when

    def step(self) -> timedelta:
        """The ``every`` gap, never under the floor."""
        gap = duration(self.every) or timedelta(hours=1)
        least = duration(self.floor) if self.floor else None
        return max(gap, least) if least else gap


def _row(r: sqlite3.Row) -> Schedule:
    d = dict(r)
    return Schedule(
        d["key"], d["integration"], tuple(json.loads(d["argv"])), d["every"], d["cron"], d["run_window"], d["outside"],
        d["floor"], d["stale_after"], d["default_every"], d["default_cron"], d["default_window"], Setting(d["setting"]),
        d["set_by"], d["set_at"], bool(d["adopted"]), Misfire(d["misfire"]), d["manual"], d["refused"], d["retired"],
        bool(d["paused"]), PauseKind(d["pause_kind"]) if d["pause_kind"] else None, d["paused_by"], d["paused_at"],
        d["paused_why"], d["resumed_by"], d["resumed_at"], d["next_due"], d["last_enqueued"], int(d["last_job"] or 0),
        d["last_result"], d["last_finished"], int(d["failures"] or 0), d["backoff_until"])


def connect(data_dir: Path) -> sqlite3.Connection:
    """The community's ``jobs.db`` with its ``schedules`` table."""
    conn = jobs._connect(data_dir)
    conn.execute(_SCHEMA)
    return conn


def schedules(data_dir: Path) -> list[Schedule]:
    with closing(connect(data_dir)) as conn:
        return [_row(r) for r in conn.execute("SELECT * FROM schedules ORDER BY key").fetchall()]


def get(data_dir: Path, key: str) -> Schedule:
    with closing(connect(data_dir)) as conn:
        r = conn.execute("SELECT * FROM schedules WHERE key = ?", (key,)).fetchone()
    if r is None:
        known = ", ".join(s.key for s in schedules(data_dir))
        raise ScheduleRefused(f"no source {key!r}; the sources: {known}")
    return _row(r)


def _update(data_dir: Path, key: str, **cols: Any) -> None:
    if not cols:
        return
    names = {"window": "run_window"}
    sets = ", ".join(f"{names.get(k, k)} = ?" for k in cols)
    values = [v.value if isinstance(v, Enum) else (int(v) if isinstance(v, bool) else v) for v in cols.values()]
    with closing(connect(data_dir)) as conn, conn:
        conn.execute(f"UPDATE schedules SET {sets} WHERE key = ?", (*values, key))


def log_path(data_dir: Path) -> Path:
    return Path(data_dir) / "jobs" / LOG


def _log(data_dir: Path, now: datetime, event: str, key: str, **detail: Any) -> dict[str, Any]:
    entry = {"at": _s(now), "event": event, "source": key, **{k: v for k, v in detail.items() if v not in ("", None)}}
    path = log_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def decisions(data_dir: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    """The newest of the scheduler's logged decisions and changes, newest last."""
    path = log_path(data_dir)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def seed(data_dir: Path, *, now: datetime | None = None) -> list[str]:
    """Write a row for each source the registry declares; update each row's defaults, command, floor, and outside
    cadence from the registry, and its cadence too while it is the default; keep an administrator's change. A row the
    registry no longer lists is retired (kept, never run). Returns what changed, in words."""
    now = now or datetime.now(timezone.utc)
    declared = {c.source_key: c for c in cadences()}
    changed: list[str] = []
    with closing(connect(data_dir)) as conn, conn:
        have = {r["key"]: _row(r) for r in conn.execute("SELECT * FROM schedules").fetchall()}
        for key, cad in declared.items():
            integ = integration_of(key)
            refused = WRITES_REFUSED if "--yes" in cad.argv else ""
            common = {"integration": integ.key if integ else "", "argv": json.dumps(list(cad.argv)),
                      "outside": cad.outside, "floor": cad.floor, "stale_after": cad.stale_after,
                      "default_every": cad.every, "default_cron": cad.cron, "default_window": cad.window,
                      "manual": cad.manual, "refused": refused, "retired": ""}
            old = have.get(key)
            if old is None:
                cols = {**common, "key": key, "every": cad.every, "cron": cad.cron, "run_window": cad.window}
                conn.execute(f"INSERT INTO schedules ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             tuple(cols.values()))
                changed.append(f"{key}: added from the registry ({cad.words()})")
                continue
            if old.setting is Setting.DEFAULT:
                common.update(every=cad.every, cron=cad.cron, run_window=cad.window)
            before = (old.default_every, old.default_cron, old.default_window, old.argv, old.floor, old.outside,
                      old.manual, old.refused, old.retired)
            after = (cad.every, cad.cron, cad.window, tuple(cad.argv), cad.floor, cad.outside, cad.manual, refused, "")
            if before != after:
                conn.execute(f"UPDATE schedules SET {', '.join(f'{k} = ?' for k in common)} WHERE key = ?",
                             (*common.values(), key))
                kept = "; the administrator's change is kept" if old.setting is Setting.ADMIN else ""
                changed.append(f"{key}: the registry's default is now {cad.words()}{kept}")
        for key, old in have.items():
            if key not in declared and not old.retired:
                conn.execute("UPDATE schedules SET retired = ? WHERE key = ?", ("the registry no longer lists it", key))
                changed.append(f"{key}: retired (the registry no longer lists it)")
    for line in changed:
        _log(data_dir, now, "seed", line.split(":", 1)[0], detail=line.split(": ", 1)[-1])
    return changed


# --- when ----------------------------------------------------------------------------------------------------------------

def _jitter(gap: timedelta, rng: random.Random | None) -> timedelta:
    if rng is None:
        return timedelta(0)
    most = min(gap * JITTER_SHARE, JITTER_CAP)
    return timedelta(seconds=rng.uniform(0, most.total_seconds()))


def next_due(row: Schedule, after: datetime, zone: tzinfo, rng: random.Random | None = None) -> datetime | None:
    """When the source is next due after a run at ``after``: the next cron time in the window, or ``after`` plus the
    gap (the ``outside`` gap outside the window, else the window's opening); never sooner than the floor; plus
    jitter."""
    least = duration(row.floor) if row.floor else None
    if row.cron:
        cron = Cron.parse(row.cron)
        at = cron.next_after(after, zone, row.window)
        if at is not None and least and at - after < least:
            at = cron.next_after(after + least - timedelta(seconds=1), zone, row.window)
        if at is None:
            return None
        return at + _jitter(cron.shortest_gap(zone, after) or timedelta(days=1), rng)
    step = row.step()
    at = after + step
    if row.window and not in_window(at, row.window, zone):
        opens = window_opens(after, row.window, zone)
        if row.outside:
            out = duration(row.outside) or step
            at = min(after + max(out, least or out), opens)
        else:
            at = opens
        if least:
            at = max(at, after + least)
    return at + _jitter(step, rng)


def _first_due(row: Schedule, now: datetime, zone: tzinfo, rng: random.Random | None) -> datetime | None:
    """When an adopted source first runs: from its last run if it has one; else now (an ``every``) or the next cron."""
    last = _t(row.last_enqueued)
    if last is not None:
        return next_due(row, last, zone, rng)
    if row.cron:
        return Cron.parse(row.cron).next_after(now, zone, row.window)
    return now + _jitter(row.step(), rng)


def held(row: Schedule, connection: Any = None) -> str:
    """Why the scheduler will not run the source now, or "" when it may."""
    if row.retired:
        return f"retired: {row.retired}"
    if row.refused:
        return f"refused: {row.refused}"
    if row.manual:
        return f"a person runs it: {row.manual}"
    if not row.adopted:
        return "the default is not adopted (jason cadence --restore SOURCE --by NAME adopts it)"
    if row.paused:
        if row.pause_kind is PauseKind.SIGN_IN:
            return f"paused, needs sign-in: {row.paused_why}"
        return f"paused by {row.paused_by or '?'}: {row.paused_why}"
    if connection is not None and getattr(getattr(connection, "state", None), "value", "") == "paused":
        return f"its connection is paused: {connection.note or 'paused'}"
    return ""


def when_next(row: Schedule, now: datetime, zone: tzinfo) -> datetime | None:
    """When the source will run next as things stand (its due time, its backoff, its window), or None when held."""
    if held(row):
        return None
    at = _t(row.next_due) or now
    backoff_until = _t(row.backoff_until)
    if backoff_until and backoff_until > at:
        at = backoff_until
    if row.window and not row.cron and not row.outside and not in_window(max(at, now), row.window, zone):
        at = window_opens(max(at, now), row.window, zone)
    return at


# --- the tick ------------------------------------------------------------------------------------------------------------

def _pending(data_dir: Path, argv: tuple[str, ...]) -> int:
    """The id of a queued or running job with this command (the scheduler's or a person's), else 0."""
    with closing(jobs._connect(data_dir)) as conn:
        r = conn.execute("SELECT id FROM jobs WHERE status IN ('queued','running') AND argv = ? ORDER BY id LIMIT 1",
                         (json.dumps(list(argv)),)).fetchone()
    return int(r["id"]) if r else 0


def _connections(data_dir: Path) -> dict[str, Any]:
    from jason.integrations.connections import FILE, load

    path = Path(data_dir) / FILE
    try:
        return load("", path) if path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _mask(text: str) -> str:
    from jason.approvals.audit import mask

    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    return str(mask(lines[-1][:300] if lines else ""))


def _pause_integration(data_dir: Path, rows: list[Schedule], integration: str, why: str, now: datetime,
                       out: list[dict[str, Any]]) -> list[Schedule]:
    """Pause every source of ``integration`` for a sign-in; returns the rows as they now stand."""
    fresh = []
    for r in rows:
        if r.integration == integration and not r.paused:
            _update(data_dir, r.key, paused=True, pause_kind=PauseKind.SIGN_IN, paused_by="jason", paused_at=_s(now),
                    paused_why=why)
            out.append(_log(data_dir, now, "paused-sign-in", r.key, why=why,
                            fix="a person signs in (jason integrations check KEY --live) or jason cadence --resume"))
            r = get(data_dir, r.key)
        fresh.append(r)
    return fresh


def tick(data_dir: Path, *, now: datetime | None = None, zone: tzinfo | None = None,
         rng: random.Random | None = None) -> list[dict[str, Any]]:
    """One pass: take in the last jobs' outcomes, follow the connections' sign-in state, and add each due source to
    the queue. Returns the decisions it logged."""
    now = now or datetime.now(timezone.utc)
    zone = zone or ZoneInfo(DEFAULT_ZONE)
    out: list[dict[str, Any]] = []
    rows = schedules(data_dir)

    # 1. The last job of each source: done, failed (backoff, or a sign-in pause), or cancelled.
    for r in list(rows):
        if not r.last_job or r.last_result not in ("",) + PENDING:
            continue
        try:
            job = jobs.get(data_dir, r.last_job)
        except KeyError:
            _update(data_dir, r.key, last_result="gone")
            continue
        status = job.status.value
        if status in PENDING:
            if status != r.last_result:
                _update(data_dir, r.key, last_result=status)
            continue
        if status == "done":
            _update(data_dir, r.key, last_result="done", last_finished=job.finished, failures=0, backoff_until="")
            if r.failures:
                out.append(_log(data_dir, now, "recovered", r.key, job=job.id, after_failures=r.failures))
            continue
        if status == "cancelled":
            _update(data_dir, r.key, last_result="cancelled", last_finished=job.finished)
            continue
        text = f"{job.summary}\n{job.note}"
        failures = r.failures + 1
        if sign_in_failure(text):
            _update(data_dir, r.key, last_result="failed", last_finished=job.finished, failures=failures)
            rows = _pause_integration(data_dir, schedules(data_dir), r.integration,
                                      f"job {job.id} failed for want of a sign-in: {_mask(text)}", now, out)
            continue
        wait = backoff(failures, r.floor)
        until = now + wait
        asked = retry_after(text, now)
        if asked and asked > until:
            until = asked
        due = _t(r.next_due)
        _update(data_dir, r.key, last_result="failed", last_finished=job.finished, failures=failures,
                backoff_until=_s(until), next_due=_s(max(due, until) if due else until))
        out.append(_log(data_dir, now, "backoff", r.key, job=job.id, failures=failures, until=_s(until),
                        retry_after=_s(asked) if asked else ""))
    rows = schedules(data_dir)

    # 2. The connections: one that needs sign-in pauses its sources; a person's successful check after a sign-in
    #    pause clears it. A pause a person resumed is not taken again from the same check.
    conns = _connections(data_dir)
    for key, conn in conns.items():
        mine = [r for r in rows if r.integration == key]
        if not mine:
            continue
        state = getattr(conn.state, "value", "")
        checked = _t(conn.last_checked)
        if state == "needs sign-in" and checked is not None:
            fresh = [r for r in mine if not r.paused and (not _t(r.resumed_at) or checked > _t(r.resumed_at))]
            if fresh:
                _pause_integration(data_dir, fresh, key, f"its connection needs sign-in: {_mask(conn.last_check)}",
                                   now, out)
        if conn.last_check.startswith("ok") and checked is not None:
            for r in mine:
                if r.paused and r.pause_kind is PauseKind.SIGN_IN and checked > (_t(r.paused_at) or checked):
                    _update(data_dir, r.key, paused=False, pause_kind="", paused_why="", resumed_by="sign-in",
                            resumed_at=_s(now), failures=0, backoff_until="")
                    out.append(_log(data_dir, now, "resumed", r.key, by="sign-in",
                                    why=f"the connection's check succeeded at {conn.last_checked}"))
    rows = schedules(data_dir)

    # 3. Each due source, once.
    for r in rows:
        if held(r, conns.get(r.integration)):
            continue
        due = _t(r.next_due)
        if due is None:
            first = _first_due(r, now, zone, rng)
            _update(data_dir, r.key, next_due=_s(first))
            due = first
            if due is None or due > now:
                continue
        if now < due:
            continue
        backoff_until = _t(r.backoff_until)
        if backoff_until and now < backoff_until:
            continue
        if r.window and not r.cron and not r.outside and not in_window(now, r.window, zone):
            continue                                       # it waits for its window; the missed run is caught up there
        last = _t(r.last_enqueued)
        least = duration(r.floor) if r.floor else None
        if last and least and now - last < least:
            continue                                       # never faster than the floor
        if pending := _pending(data_dir, r.argv):
            if pending != r.last_job:
                _update(data_dir, r.key, last_job=pending, last_result="queued")
                out.append(_log(data_dir, now, "coalesced", r.key, job=pending))
            continue
        finished = _t(r.last_finished)
        missed = now - max(due, finished or due) > GRACE   # late only while nothing ran: a pending job is coalescing
        if missed and r.misfire is Misfire.SKIP:
            nxt = next_due(r, now, zone, rng)
            _update(data_dir, r.key, next_due=_s(nxt))
            out.append(_log(data_dir, now, "skipped", r.key, missed=_s(due), next=_s(nxt)))
            continue
        try:
            job = jobs.add(data_dir, list(r.argv))
        except jobs.JobRefused as exc:
            _update(data_dir, r.key, refused=str(exc))
            out.append(_log(data_dir, now, "refused", r.key, why=str(exc)))
            continue
        nxt = next_due(r, now, zone, rng)
        _update(data_dir, r.key, last_enqueued=_s(now), last_job=job.id, last_result="queued", next_due=_s(nxt))
        out.append(_log(data_dir, now, "catch-up" if missed else "enqueued", r.key, job=job.id, command=r.command,
                        missed=_s(due) if missed else "", next=_s(nxt)))
    return out


def next_runs(data_dir: Path, *, now: datetime | None = None, zone: tzinfo | None = None,
              limit: int = NEXT_SHOWN) -> list[dict[str, Any]]:
    """The next ``limit`` runs: each source the scheduler will run, by when."""
    now = now or datetime.now(timezone.utc)
    zone = zone or ZoneInfo(DEFAULT_ZONE)
    conns = _connections(data_dir)
    out = []
    for r in schedules(data_dir):
        if held(r, conns.get(r.integration)):
            continue
        at = when_next(r, now, zone)
        if at is not None:
            out.append({"source": r.key, "at": _s(at), "command": r.command})
    return sorted(out, key=lambda x: x["at"])[:limit]


# --- a person's changes --------------------------------------------------------------------------------------------------

def _need_by(by: str) -> str:
    if not str(by or "").strip():
        raise ScheduleRefused("say who makes the change: --by NAME")
    return str(by).strip()


def set_cadence(data_dir: Path, key: str, *, every: str = "", cron: str = "", window: str | None = None, by: str,
                now: datetime | None = None, zone: tzinfo | None = None) -> Schedule:
    """An administrator's change to one source's cadence, adopted: refused faster than the floor, or for a source the
    scheduler never runs."""
    by = _need_by(by)
    now = now or datetime.now(timezone.utc)
    zone = zone or ZoneInfo(DEFAULT_ZONE)
    row = get(data_dir, key)
    if bool(every) == bool(cron):
        raise ScheduleRefused("give one of --every SPAN or --cron \"M H D M W\"")
    if row.retired or row.refused or row.manual:
        raise ScheduleRefused(f"{key} is not scheduled: {held(row)}")
    win = row.window if window is None else ("" if window.lower() in ("", "all", "none") else window)
    parse_window(win)
    if cron:
        Cron.parse(cron)
    if reason := floor_refusal(every, cron, row.floor, zone=zone, now=now):
        _log(data_dir, now, "refused", key, by=by, asked=every or cron, why=reason)
        raise ScheduleRefused(f"{key}: refused: {reason}")
    _update(data_dir, key, every=every, cron=cron, window=win, setting=Setting.ADMIN, set_by=by, set_at=_s(now),
            adopted=True)
    row = get(data_dir, key)
    _update(data_dir, key, next_due=_s(_first_due(row, now, zone, None)))
    _log(data_dir, now, "set", key, by=by, cadence=row.words())
    return get(data_dir, key)


def restore(data_dir: Path, key: str | None, *, by: str, now: datetime | None = None,
            zone: tzinfo | None = None) -> list[Schedule]:
    """Put one source (or every one, ``key`` None) back to the registry's default, and adopt it."""
    by = _need_by(by)
    now = now or datetime.now(timezone.utc)
    zone = zone or ZoneInfo(DEFAULT_ZONE)
    rows = [get(data_dir, key)] if key else schedules(data_dir)
    out = []
    for row in rows:
        if row.retired or row.refused or row.manual:
            if key:
                raise ScheduleRefused(f"{row.key} is not scheduled: {held(row)}")
            continue
        _update(data_dir, row.key, every=row.default_every, cron=row.default_cron, window=row.default_window,
                setting=Setting.DEFAULT, set_by=by, set_at=_s(now), adopted=True)
        fresh = get(data_dir, row.key)
        _update(data_dir, row.key, next_due=_s(_first_due(fresh, now, zone, None)))
        _log(data_dir, now, "restored", row.key, by=by, cadence=fresh.words())
        out.append(get(data_dir, row.key))
    return out


def pause(data_dir: Path, key: str, *, why: str, by: str, now: datetime | None = None) -> Schedule:
    by = _need_by(by)
    if not str(why or "").strip():
        raise ScheduleRefused("say why it is paused: --why TEXT")
    now = now or datetime.now(timezone.utc)
    get(data_dir, key)
    _update(data_dir, key, paused=True, pause_kind=PauseKind.PERSON, paused_by=by, paused_at=_s(now),
            paused_why=why.strip())
    _log(data_dir, now, "paused", key, by=by, why=why.strip())
    return get(data_dir, key)


def resume(data_dir: Path, key: str, *, by: str, now: datetime | None = None) -> list[Schedule]:
    """Clear a pause, the failures, and the backoff. A sign-in pause is cleared on every source of the integration it
    paused (the person says the sign-in is fixed)."""
    by = _need_by(by)
    now = now or datetime.now(timezone.utc)
    row = get(data_dir, key)
    if not row.paused:
        raise ScheduleRefused(f"{key} is not paused")
    rows = [row]
    if row.pause_kind is PauseKind.SIGN_IN:
        rows = [r for r in schedules(data_dir) if r.integration == row.integration and r.paused
                and r.pause_kind is PauseKind.SIGN_IN]
    for r in rows:
        _update(data_dir, r.key, paused=False, pause_kind="", paused_why="", resumed_by=by, resumed_at=_s(now),
                failures=0, backoff_until="")
        _log(data_dir, now, "resumed", r.key, by=by)
    return [get(data_dir, r.key) for r in rows]


def run_now(data_dir: Path, key: str, *, by: str, now: datetime | None = None) -> jobs.Job:
    """Add the source's command to the queue once, now (a person's ``jobs add``); refused while one is queued or
    running, or for a source the scheduler never runs."""
    by = _need_by(by)
    now = now or datetime.now(timezone.utc)
    row = get(data_dir, key)
    if row.retired or row.refused or row.manual:
        raise ScheduleRefused(f"{key} is not run by the scheduler: {held(row)}")
    if pending := _pending(data_dir, row.argv):
        raise ScheduleRefused(f"{key}: job {pending} ({row.command}) is already queued or running")
    job = jobs.add(data_dir, list(row.argv))
    _update(data_dir, key, last_enqueued=_s(now), last_job=job.id, last_result="queued")
    _log(data_dir, now, "run-now", key, by=by, job=job.id, command=row.command)
    return job


# --- reading ------------------------------------------------------------------------------------------------------------

def listing(data_dir: Path, *, now: datetime | None = None, zone: tzinfo | None = None) -> list[dict[str, Any]]:
    """Each source's schedule as JSON: its cadence, window, floor, where the setting came from, the next run, the last
    result, and a pause or why it is held."""
    now = now or datetime.now(timezone.utc)
    zone = zone or ZoneInfo(DEFAULT_ZONE)
    conns = _connections(data_dir)

    def local(text: str) -> str:
        at = _t(text)
        return at.astimezone(zone).isoformat(timespec="minutes") if at else ""

    out = []
    for r in schedules(data_dir):
        why = held(r, conns.get(r.integration))
        at = None if why else when_next(r, now, zone)
        setting = (f"changed by {r.set_by} {local(r.set_at)}" if r.setting is Setting.ADMIN
                   else f"default, adopted by {r.set_by} {local(r.set_at)}" if r.adopted
                   else "default, not adopted")
        under = ""
        if r.every and r.floor and (duration(r.every) or timedelta(0)) < (duration(r.floor) or timedelta(0)):
            under = f"faster than the floor {r.floor}; the floor applies"
        out.append({
            "source": r.key, "integration": r.integration, "command": r.command, "cadence": r.words(),
            "every": r.every, "cron": r.cron, "window": r.window, "outside": r.outside, "floor": r.floor,
            "staleAfter": r.stale_after, "default": {"every": r.default_every, "cron": r.default_cron,
                                                     "window": r.default_window},
            "setting": r.setting.value, "settingWords": setting, "setBy": r.set_by, "setAt": r.set_at,
            "adopted": r.adopted, "held": why, "nextRun": _s(at) if at else "", "nextRunLocal": local(_s(at)) if at else "",
            "lastEnqueued": r.last_enqueued, "lastJob": r.last_job or None, "lastResult": r.last_result,
            "lastFinished": r.last_finished, "failures": r.failures, "backoffUntil": r.backoff_until,
            "paused": ({"by": r.paused_by, "at": r.paused_at, "why": r.paused_why,
                        "kind": r.pause_kind.value if r.pause_kind else ""} if r.paused else None),
            "misfire": r.misfire.value, "note": under})
    return out


def lines(rows: list[dict[str, Any]]) -> list[str]:
    out = []
    for r in rows:
        floor = f", floor {r['floor']}" if r["floor"] else ""
        out.append(f"{r['source']}: {r['command']}")
        out.append(f"  {r['cadence']}{floor}; {r['settingWords']}" + (f"; {r['note']}" if r["note"] else ""))
        if r["held"]:
            out.append(f"  not scheduled: {r['held']}")
        else:
            out.append(f"  next {r['nextRunLocal'] or '?'}")
        last = (f"last job {r['lastJob']} {r['lastResult'] or '?'}" + (f" {r['lastFinished']}" if r["lastFinished"] else "")
                if r["lastJob"] else "no job yet")
        if r["failures"]:
            last += f"; {r['failures']} failure(s) in a row" + (f", backing off until {r['backoffUntil']}"
                                                                 if r["backoffUntil"] else "")
        out.append(f"  {last}")
    return out


# --- the loop ------------------------------------------------------------------------------------------------------------

def run(profile: str, data_dir: Path, stop: threading.Event, state: dict[str, Any], *,
        every: float | tuple[float, float] = TICK_SECONDS, zone: str = "",
        clock: Callable[[], datetime] | None = None, rng: random.Random | None = None,
        log: Callable[[str], None] = print) -> None:
    """One community's scheduler, until ``stop``: seed the table from the registry, then tick every 30 to 60 seconds.
    ``state`` carries what the heartbeat shows: the zone, the last tick, the next runs, and the last error."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    rng = rng or random.Random()
    name = zone or zone_of(profile)
    tz = ZoneInfo(name)
    state.update(zone=name, next=[], tick="", error="")
    for line in seed(data_dir, now=clock()):
        log(f"schedules: {line}")
    while not stop.is_set():
        now = clock()
        try:
            for d in tick(data_dir, now=now, zone=tz, rng=rng):
                log(f"{d['source']}: {d['event']}" + (f" job {d['job']}" if d.get("job") else "")
                    + (f" until {d['until']}" if d.get("until") else "") + (f" ({d['why']})" if d.get("why") else ""))
            state.update(next=next_runs(data_dir, now=now, zone=tz), tick=_s(now), error="")
        except Exception as exc:  # noqa: BLE001 - one bad tick is logged and the loop goes on
            state.update(tick=_s(now), error=f"{type(exc).__name__}: {exc}")
            log(f"tick failed: {state['error']}")
        wait = rng.uniform(*every) if isinstance(every, tuple) else float(every)
        stop.wait(wait)


def by_default() -> str:
    """Who runs a command, when ``--by`` is not given: the signed-in user's name."""
    return os.environ.get("USERNAME") or os.environ.get("USER") or ""


__all__ = ["Cron", "DEFAULT_ZONE", "Misfire", "PauseKind", "Schedule", "ScheduleRefused", "Setting", "backoff",
           "by_default", "connect", "decisions", "floor_refusal", "get", "held", "in_window", "listing", "lines",
           "log_path", "next_due", "next_runs", "parse_window", "pause", "restore", "resume", "retry_after", "run",
           "run_now", "schedules", "seed", "set_cadence", "sign_in_failure", "tick", "when_next", "window_opens",
           "zone_of"]
