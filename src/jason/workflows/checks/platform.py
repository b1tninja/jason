"""The platform family's reads (docs/workflows/mail-and-platform.md): paper mail, Gmail, the response inbox, and the service.

Each is a ``check`` a definition names with ``named_check``. Each reads a store on disk and nothing else: it writes nothing,
calls no outside system (no PayHOA, Google, Keeper, PostScanMail, or Gmail), starts and contacts no service, and loads no
profile except through the readers' own lazy ``community()``. A store that is missing or cannot be read gives ``ok=False``
with the reason, never ``ok``, and never an exception.

**What a message holds.** A count, a date, a state, or an opaque id. Never a sender's name, an address, a subject, a word of a
letter, or a credential. A message is also *stable*: it changes only when what it reports changes (a date, a count, a state),
never with the clock alone, so a resume that reads the same store twice appends one record, not two.

**Figures copied from the sources.** The three limits below (mail and Gmail stale-after, the heartbeat's) are the integrations
registry's and ``jason.serve``'s own figures. A check here may import neither (the checks package is allowed stores and read
functions only), so they are written once here and a test pins each to its source.

**Left out, and why.** Reads this family wanted that no existing read function answers without a write, a call outside, or an
import the checks package does not allow are not here; ``defs/platform.py`` keeps their steps as a person's.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from jason.workflows.checks import check
from jason.workflows.readers import StoreReaders, when
from jason.workflows.types import CheckResult, RunView

MAIL_STALE_AFTER = timedelta(days=3)
"""The mail source's stale-after (``jason.integrations.registry``, the ``mail`` cadence; proposed, not adopted)."""

GMAIL_STALE_AFTER = timedelta(hours=1)
"""The Gmail source's stale-after (the ``gmail`` cadence)."""

HEARTBEAT_BEAT_SECONDS = 30.0
"""How often ``jason serve`` beats (``jason.serve.BEAT_SECONDS``)."""

HEARTBEAT_STALE_AFTER = 90.0
"""No beat for this long is stale (``jason.serve.STALE_AFTER``: three missed beats)."""

LANES_DAYS = 30
"""The span of the lanes (``jason mail --days 30``)."""

JOBS_READ = 5000
"""How many of the newest jobs the queue read counts."""

_ITEMS = "mail/items.json"
_TRIAGE = "mail/triage.json"
_CORRESPONDENCE = "gmail/correspondence.json"
_INBOX = "responses/inbox.json"
_REFERENCES = "forms/references.json"
_HEARTBEAT = "jobs/heartbeat.json"


# --- small helpers --------------------------------------------------------------------------------------------------

def _safe(fn: Callable[..., CheckResult]) -> Callable[..., CheckResult]:
    """A read that fails for any reason answers ``ok=False`` with the kind of failure (never its text, which may name a path)."""

    def wrapped(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
        try:
            return fn(readers, view, item)
        except Exception as exc:  # noqa: BLE001 - an unreadable store is a failed check, never an exception, never ok
            return CheckResult(False, (), f"{fn.__name__.replace('_', '-')}: the store cannot be read ({type(exc).__name__})")

    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


def _now(readers: StoreReaders) -> datetime:
    """The moment a freshness is judged at: now, or (when a test fixes ``today``) noon UTC of that day."""
    today = getattr(readers, "today", None)
    if not isinstance(today, date) or today == date.today():
        return datetime.now(timezone.utc)
    return datetime.combine(today, time(12), tzinfo=timezone.utc)


def _json(path: Path, what: str) -> tuple[Any, str]:
    """(the parsed file, "") or (None, why not)."""
    if not path.is_file():
        return None, f"there is no {what} on disk yet"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as exc:
        return None, f"the {what} cannot be read ({type(exc).__name__})"


def _span(limit: timedelta) -> str:
    seconds = int(limit.total_seconds())
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size and seconds % size == 0:
            n = seconds // size
            return f"{n} {unit}{'' if n == 1 else 's'}"
    return f"{seconds} seconds"


def _id_of(view: RunView, item: str, kind: str) -> str:
    """The id a read is about: the item if one is named, else the run's subject (``<kind>:<id>``)."""
    if item and item.strip():
        return item.strip()
    subject = str(getattr(view, "subject", "") or "").strip()
    head, colon, rest = subject.partition(":")
    if colon:
        return rest.strip() if head == kind else ""
    return subject


def _fresh(readers: StoreReaders, relative: str, what: str, limit: timedelta, command: str) -> CheckResult:
    """A store's own ``syncedAt`` against its stale-after. Fresh passes; stale, never read, or unreadable fails."""
    body, why = _json(readers.data_dir / relative, what)
    if body is None:
        return CheckResult(False, (), f"{why}; run `{command}`")
    stamp = body.get("syncedAt") if isinstance(body, dict) else None
    moment = when(stamp)
    if moment is None:
        return CheckResult(False, (), f"the {what} carries no read time; run `{command}`")
    evidence = readers.evidence_entries((f"file:{relative}",))
    words = f"stale after {_span(limit)} (proposed policy)"
    if _now(readers) - moment > limit:
        return CheckResult(False, evidence, f"the {what} was last read {moment.isoformat(timespec='seconds')}, which is more than "
                                            f"{_span(limit)} ago ({words}); run `{command}`")
    return CheckResult(True, evidence, f"the {what} was last read {moment.isoformat(timespec='seconds')}, within {_span(limit)} ({words})")


# --- paper mail -----------------------------------------------------------------------------------------------------

@check("mail-fresh")
@_safe
def mail_fresh(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The mail store's last read (``data/mail/items.json``, ``syncedAt``) against the mail source's stale-after."""
    return _fresh(readers, _ITEMS, "mail store", MAIL_STALE_AFTER, "jason mail")


@check("mail-lanes")
@_safe
def mail_lanes(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The lanes of ``mail_brief`` as counts: act, review, not scanned, and the rest. A sort, not a reading of any letter."""
    from jason.tasks.mail import mail_brief

    brief = mail_brief(readers.data_dir, days=LANES_DAYS, today=readers.today)
    if not brief.get("found"):
        return CheckResult(False, (), "there is no mail on disk yet; run `jason mail`")
    total, act, review = int(brief["items"]), len(brief["act"]), len(brief["review"])
    message = (f"{total} letter(s) in the last {LANES_DAYS} days: {act} to act on, {review} to review, "
               f"{max(0, total - act - review)} other; {len(brief['unscanned'])} not scanned (counts of a sort, not a reading of a letter)")
    return CheckResult(True, readers.evidence_entries((f"file:{_ITEMS}",)), message)


@check("mail-scanned")
@_safe
def mail_scanned(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """A scan requested for one letter has arrived: its record in the mail store says scanned. The item is the mail id."""
    from jason.tasks.mail import load_items

    mail_id = (item or "").strip()
    if not mail_id:
        return CheckResult(False, (), "the read names no letter (an item is a mail id)")
    row = load_items(readers.data_dir).get(mail_id)
    if row is None:
        return CheckResult(False, (), f"letter {mail_id} is not in the mail store; run `jason mail`")
    evidence = readers.evidence_entries((f"file:{_ITEMS}",))
    if not row.get("scanned"):
        return CheckResult(False, evidence, f"letter {mail_id} is not scanned yet")
    return CheckResult(True, evidence, f"letter {mail_id} is scanned" + (f" (received {str(row['received'])[:10]})" if row.get("received") else ""))


@check("mail-period-chosen")
@_safe
def mail_period_chosen(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every letter of the period has a recorded choice (``data/mail/triage.json``): ``chosen`` equals ``items``."""
    from jason.tasks.mail_triage import load

    items = tuple(dict.fromkeys(str(i) for i in getattr(view, "items", ()) or ()))
    if not items:
        return CheckResult(True, (), "the run has no letters, so none is left without a choice")
    chosen = load(readers.data_dir)
    missing = [i for i in items if not (chosen.get(i) or {}).get("choice")]
    evidence = readers.evidence_entries((f"file:{_TRIAGE}",))
    message = f"{len(items) - len(missing)} of {len(items)} letter(s) have a recorded choice"
    if missing:
        return CheckResult(False, evidence, f"{message}; without one: {', '.join(missing[:10])}" + (" and more" if len(missing) > 10 else ""))
    return CheckResult(True, evidence, message)


# --- Gmail ----------------------------------------------------------------------------------------------------------

@check("gmail-fresh")
@_safe
def gmail_fresh(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The Gmail store's last read (``data/gmail/correspondence.json``, ``syncedAt``) against the Gmail source's stale-after."""
    return _fresh(readers, _CORRESPONDENCE, "Gmail store", GMAIL_STALE_AFTER, "jason gmail --sync")


@check("thread-status")
@_safe
def thread_status(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Whose move it is, from the thread's last message: awaiting us, awaiting them, notice, or internal. Read from the stored
    headers by ``jason.tasks.threads.status_of``; the run's subject (or the item) is the thread id. A reading: someone may
    have answered by phone, in person, or from another mailbox, which jason cannot see."""
    from jason.tasks.threads import status_of

    thread = _id_of(view, item, "thread")
    if not thread:
        return CheckResult(False, (), "the run names no thread (its subject is thread:ID)")
    body, why = _json(readers.data_dir / _CORRESPONDENCE, "Gmail store")
    if body is None:
        return CheckResult(False, (), f"{why}; run `jason gmail --sync`")
    messages = sorted((m for m in (body.get("messages") or []) if isinstance(m, dict) and m.get("threadId") == thread),
                      key=lambda m: str(m.get("at", "")))
    if not messages:
        return CheckResult(False, (), f"thread {thread} is not in the Gmail store")
    if not all(m.get("at") and m.get("direction") in ("in", "out") and isinstance(m.get("parties"), list) for m in messages):
        return CheckResult(False, (), f"a message of thread {thread} in the Gmail store lacks its time, direction, or parties; "
                                      "run `jason gmail --sync`")
    status, _age = status_of(messages, readers.today)
    last = str(messages[-1].get("at", ""))[:10]
    return CheckResult(True, readers.evidence_entries((f"file:{_CORRESPONDENCE}",)),
                       f"{status}: {len(messages)} message(s), the last on {last}; a reading, since an answer by phone, in person, "
                       "or from another mailbox is not seen")


# --- the response inbox ---------------------------------------------------------------------------------------------

@check("responses-channels")
@_safe
def responses_channels(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """How each channel's last check ended (ok, sign-in, failed, skipped, or never checked) and when it last succeeded. A
    sign-in or a failed end fails the read; a channel no request uses is skipped, which is no failure."""
    from jason.community.response_inbox import Channel
    from jason.tasks.response_inbox import channel_status

    rows = {r["channel"]: r for r in channel_status(readers.data_dir, now=_now(readers))}
    if not rows:
        return CheckResult(False, (), "no channel has been checked yet; run `jason responses --check`")
    parts: list[str] = []
    bad = 0
    for channel in (c.value for c in Channel if c is not Channel.MANUAL):
        row = rows.get(channel)
        if row is None:
            parts.append(f"{channel} never checked")
            bad += 1
            continue
        ended = str(row.get("ended") or "never checked")
        ok_at = str(row.get("lastOk") or "")
        parts.append(f"{channel} {ended}" + (f" (last ok {ok_at[:16]})" if ok_at else ""))
        if ended not in ("ok", "skipped"):
            bad += 1
    return CheckResult(bad == 0, readers.evidence_entries((f"file:{_INBOX}",)), "; ".join(parts))


@check("responses-outstanding")
@_safe
def responses_outstanding(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Owners sent a copy less answers, as counts (``jason.tasks.response_outstanding``), for the run's request. No unit, name,
    or address is in the message."""
    from jason.tasks.response_inbox import ResponseError
    from jason.tasks.response_outstanding import outstanding

    request = _id_of(view, item, "request")
    try:
        body = outstanding(readers.data_dir, readers.community, request=request, now=_now(readers))
    except ResponseError as exc:
        return CheckResult(False, (), str(exc))
    found = body.get("requests") or []
    if not found:
        return CheckResult(False, (), "the profile watches no request, so there is no sent-copy count to read")
    if not (body.get("catalog") or {}).get("exists"):
        return CheckResult(False, (), "there is no sent-copy catalog on disk, so nobody can be counted as asked")
    sent = sum(int(r["sent"]) for r in found)
    answered = sum(int(r["answered"]) for r in found)
    waiting = sum(int(r["notResponded"]) for r in found)
    never = [r["neverAsked"] for r in found if r.get("neverAsked") is not None]
    tail = f"; {sum(len(n) for n in never)} never sent a copy" if never else "; the owner list is not on disk, so owners never sent a copy are not counted"
    return CheckResult(True, readers.evidence_entries((f"file:{_REFERENCES}", f"file:{_INBOX}")),
                       f"{sent} copy(ies) sent, {answered} answered, {waiting} not responded{tail}")


# --- the instance and the service -----------------------------------------------------------------------------------

@check("instance-which")
@_safe
def instance_which(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The community in use and where the choice came from (``jason which``): the environment and the two ``.env`` files, no
    profile loaded. A built-in default or a lone installed profile is said so, so a default is never invisible."""
    from jason.community.profile import resolve_community

    resolved = resolve_community()
    how = ("a default the code chose (set JASON_COMMUNITY or run `jason use KEY`)" if resolved.shim
           else "the old setting name JASON_PROFILE" if resolved.alias else "a choice a person made")
    return CheckResult(True, (), f"community {resolved.name}, chosen by {resolved.source}: {how}; data folder {readers.data_dir.name}")


@check("service-heartbeat")
@_safe
def service_heartbeat(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The service's heartbeat file (``data/jobs/heartbeat.json``), judged as ``jason serve`` judges it: none, running,
    draining, stale, or stopped. Reads the file only; it contacts no process."""
    path = readers.data_dir / _HEARTBEAT
    if not path.is_file():
        return CheckResult(False, (), "none: no heartbeat (jason serve has not run for this community)")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return CheckResult(False, (), f"the heartbeat cannot be read ({type(exc).__name__})")
    if not isinstance(record, dict) or not record:
        return CheckResult(False, (), "none: the heartbeat file holds no record")
    said = str(record.get("state", "running"))
    beat = when(record.get("beat", ""))
    limits = f"beats every {int(HEARTBEAT_BEAT_SECONDS)} s, stale after {int(HEARTBEAT_STALE_AFTER)} s"
    if said == "stopped":
        return CheckResult(False, (), f"stopped: the process said it ended at {record.get('beat', '?')}")
    if beat is None or (_now(readers) - beat).total_seconds() > HEARTBEAT_STALE_AFTER:
        return CheckResult(False, (), f"stale: no beat for more than {int(HEARTBEAT_STALE_AFTER)} s (last {record.get('beat', 'unreadable')}); "
                                      f"it said {said}; the process stopped without saying so, or hangs ({limits})")
    return CheckResult(True, (), f"{said}: the last beat is within {int(HEARTBEAT_STALE_AFTER)} s ({limits})")


@check("service-queue")
@_safe
def service_queue(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The job queue read as counts (queued, running, failed, done, cancelled) from ``data/jobs.db``, through the same read the
    MCP tool ``jobs_status`` makes. It adds, runs, and cancels nothing, and does not create the queue when there is none."""
    from jason.mcp.county import jobs_status

    out = jobs_status(every=True, limit=JOBS_READ, data_dir=readers.data_dir)
    if not out.get("found"):
        return CheckResult(False, (), "there is no job queue on disk yet")
    by = out.get("byStatus") or {}
    shown = ", ".join(f"{int(by.get(k, 0))} {k}" for k in ("queued", "running", "failed", "done", "cancelled") if k in by or k in ("queued", "running", "failed", "done"))
    return CheckResult(True, (), f"jobs: {shown} (of the newest {JOBS_READ})")


__all__ = ["GMAIL_STALE_AFTER", "HEARTBEAT_BEAT_SECONDS", "HEARTBEAT_STALE_AFTER", "MAIL_STALE_AFTER", "gmail_fresh", "instance_which",
           "mail_fresh", "mail_lanes", "mail_period_chosen", "mail_scanned", "responses_channels", "responses_outstanding",
           "service_heartbeat", "service_queue", "thread_status"]
