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

**The integration, limits and storage readers.** ``integration-state`` reads ``jason.integrations.connections`` (the stored
connection and the Status rows, from disk and the settings; the vault is never asked), ``service-limits`` reads ``jason.limits``
(the two limits files and trails; a clamp is not recorded), and ``service-verify`` reads the same Status rows, the heartbeat, and
``jason.storage``'s free-space function. Free space is said as at least or under a floor, never as a figure, so a message does not
change with the clock alone.

**Left out, and why.** Reads this family wanted that no existing read function answers without a write, a call outside, or an
import the checks package does not allow are not here; ``defs/platform.py`` keeps their steps as a person's (``WANTED`` says why):
``mail-findings`` (``mail_links`` opens the tax store, which creates its tables), ``thread-leads`` (``threads`` writes
``reports/threads.json``), ``thread-closed`` (a person's note has no store), ``draft-source`` and ``draft-preview`` (the profile,
the settings, or Google), and ``vault-answers`` (the vault is the development environment's store and is not asked).
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


# --- a response arrival, recognized ---------------------------------------------------------------------------------------

@check("responses-recognized")
@_safe
def responses_recognized(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Whose copy an arrival is: recognized (a copy jason sent), candidate (looks like one of its forms), or not ours, with the
    rung that decided it and how sure. The item is the arrival id. An arrival already read is judged from its stored reading;
    one not yet read only from its subject (the cheap first rung, no file opened), and a subject that names no copy of ours is
    *not decided* (its files are looked at at the read), never "not ours". A structured arrival (PayHOA, a Google Form) names its
    own request and has no sent copy to find. No unit, owner, sender, or subject is in the message."""
    from jason.community.response_inbox import Channel
    from jason.tasks import response_inbox as ri
    from jason.tasks.recognize import recognize

    arrival_id = (item or "").strip()
    if not arrival_id:
        return CheckResult(False, (), "the read names no arrival (an item is an arrival id)")
    try:
        arrival = ri.get(readers.data_dir, arrival_id)
    except ri.ResponseError:
        return CheckResult(False, (), f"arrival {arrival_id} is not in the inbox; run `jason responses --check`")
    evidence_paths = [f"file:{_INBOX}"]
    reading = ri.reading_path(readers.data_dir, arrival)
    reading_body, _why = _json(reading, "reading") if reading.is_file() else (None, "")
    if reading_body is not None:
        evidence_paths.append("file:" + reading.relative_to(readers.data_dir).as_posix())
    evidence = readers.evidence_entries(tuple(evidence_paths))
    if isinstance(reading_body, dict) and isinstance(reading_body.get("recognition"), dict):
        found = reading_body["recognition"]
        outcome = str(found.get("outcome") or "")
        if outcome not in ("recognized", "candidate", "not-ours"):
            return CheckResult(False, evidence, f"arrival {arrival_id}: its reading holds no recognition; read it again")
        rung = int(found.get("rungNumber") or 0)
        by = f" by rung {rung} ({found.get('rung')})" if rung else ""
        return CheckResult(True, evidence, f"{outcome}{by}, how sure: {found.get('sure') or 'unknown'} (from its reading); "
                                           "recognition is a lead for a person, never an answer")
    if arrival.channel is Channel.MANUAL:
        return CheckResult(True, evidence, "keyed by a person: there is no message to recognize")
    if arrival.structured:
        return CheckResult(True, evidence, f"a {arrival.channel.value} arrival: the form names its own request, so there is no sent "
                                           "copy to find; it is not read for a marker")
    found_by_subject = recognize(readers.data_dir, None, subject=arrival.summary, images=False)
    if found_by_subject.recognized:
        rung = found_by_subject.rung
        return CheckResult(True, evidence, f"recognized by rung {rung.number if rung else 0} ({rung.value if rung else 'subject'}), how sure: "
                                           f"{found_by_subject.sure.value} (from its subject only; not yet read)")
    if found_by_subject.unsent:
        return CheckResult(True, evidence, "not ours by its subject: it carries a reference no copy we sent carries (not yet read; a "
                                           "person looks at it)")
    return CheckResult(True, evidence, "not decided: its subject names no copy of ours, and its files are looked at when it is read")


# --- the integration's state ----------------------------------------------------------------------------------------------

def _settings() -> Any:
    """The settings the integration probes look at (paths and whether a record is named; never a value), or None."""
    try:
        from jason.config import Settings

        return Settings.load(None)
    except Exception:  # noqa: BLE001 - no .env: the default paths, and nothing configured
        return None


def _day(stamp: Any) -> str:
    moment = when(stamp)
    return moment.date().isoformat() if moment is not None else ""


def _community_key() -> str:
    """The community the connections are kept for (the chosen one), else a neutral word: only a label on a row, never a path."""
    try:
        from jason.community.profile import profile_name

        return profile_name()
    except Exception:  # noqa: BLE001 - none chosen: the readings are still taken from the data folder
        return "community"


@check("integration-state")
@_safe
def integration_state(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """An integration's state from disk and the settings, as ``jason integrations list`` reads it: not set up, needs sign-in,
    connected, failing, or paused. The vault is not asked and nothing is called, so a credential kept only in the vault reads as
    not set, and *connected* means only that a store was read or a check once passed: a live check by a person is what proves it.
    The run's subject (or the item) is ``integration:KEY``. The message holds the state, counts, and dates: no account, vault
    path, error text, or name."""
    from jason.integrations import connections
    from jason.integrations.registry import Scope, integration

    key = _id_of(view, item, "integration")
    if not key:
        return CheckResult(False, (), "the run names no integration (its subject is integration:KEY)")
    try:
        integ = integration(key)
    except KeyError:
        return CheckResult(False, (), f"{key} is not an integration jason knows (`jason integrations list`)")
    instance = integ.scope is Scope.INSTANCE
    community = connections.INSTANCE if instance else _community_key()
    path = connections.store_path(connections.INSTANCE) if instance else readers.data_dir / connections.FILE
    found = [r for r in connections.readings(community, scope=integ.scope, settings=_settings(), root=readers.data_dir,
                                             now=_now(readers), path=path, profile=lambda: readers.community)
             if r.integration.key == integ.key]
    if not found:
        return CheckResult(False, (), f"{key} has no reading")
    reading = found[0]
    parts = [f"{reading.state.value}", ("its credential is set" if reading.configured else "its credential is not set")
             if integ.credential else "it holds no credential"]
    sources = reading.sources
    if sources:
        counts: dict[str, int] = {}
        for row in sources:
            word = str(row.get("standing") or "no threshold")
            counts[word] = counts.get(word, 0) + 1
        parts.append(f"{len(sources)} source(s): " + ", ".join(f"{n} {w}" for w, n in sorted(counts.items())))
        last = max((str(r.get("lastRead") or "") for r in sources), default="")
        if _day(last):
            parts.append(f"last read {_day(last)}")
    conn = reading.connection
    if conn.last_checked:
        parts.append(f"last check {'ok' if conn.last_check.startswith('ok') else 'failed'} on {_day(conn.last_checked) or 'an unreadable day'}")
    else:
        parts.append("never checked")
    tail = ("from disk and the settings only; the vault was not asked, and a live check by a person is what proves a connection")
    evidence = readers.evidence_entries((f"file:{connections.FILE}",)) if not instance else ()
    return CheckResult(True, evidence, "; ".join(parts) + f" ({tail})")


# --- the service's limits, and everything current ---------------------------------------------------------------------------

def _profile_or_none(readers: StoreReaders) -> Any:
    try:
        return readers.community
    except Exception:  # noqa: BLE001 - no profile chosen: the instance and the code's defaults
        return None


@check("service-limits")
@_safe
def service_limits(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each limit in force (``jason limits``): its value, the layer it came from, its range, and when that layer last changed
    it, as counts and, for a limit that is not the code's default, its key, value, source, range, and day. A limits file that
    cannot be read fails the read (jason then holds the stricter value). Reads the two limits files and the two trails; writes
    nothing and records no clamp. No name, reason, or path is in the message."""
    import jason.limits as limits

    inst_file = None
    try:
        inst_file = limits.instance_file()
    except Exception:  # noqa: BLE001 - no user config: the instance layer is read as absent
        pass
    rows = limits.listing(_settings(), _profile_or_none(readers), data_folder=readers.data_dir, instance_file=inst_file)
    unreadable = sorted({u for r in rows for u in r["unreadable"]})
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    changed = []
    for r in rows:
        if r["source"] == "default":
            continue
        l = limits.limit(r["key"])
        span = "on or off" if l.unit == "switch" else f"{l.format(l.minimum)} to {l.format(l.top)}"
        day = _day((r.get("set") or {}).get("at"))
        changed.append(f"{r['key']} {l.format(r['value'])} ({r['source']}, range {span}" + (f", changed {day}" if day else "") + ")")
    last = ""
    for scope in ("community", "instance"):
        trail = limits.read_log(scope, data_folder=readers.data_dir, instance_file=inst_file) if (scope == "community" or inst_file) else []
        for line in trail:
            if line.get("kind") in ("set", "reset"):
                last = max(last, _day(line.get("at")))
    held = sum(1 for r in rows if r["clamped"])
    figures = ", ".join(f"{by_source[s]} {s}" for s in limits.SOURCES if s in by_source)
    message = f"{len(rows)} limit(s) in force: {figures}"
    if held:
        message += f"; {held} held to its range"
    message += f"; last change {last or 'none on record'}"
    if changed:
        message += "; set: " + "; ".join(changed[:12]) + (f"; and {len(changed) - 12} more" if len(changed) > 12 else "")
    if unreadable:
        return CheckResult(False, readers.evidence_entries((f"file:{limits.FILE_NAME}",)),
                           message + f"; cannot be read: {', '.join(unreadable)} (the stricter value is held until it is fixed)")
    return CheckResult(True, readers.evidence_entries((f"file:{limits.FILE_NAME}",)), message)


DRIVE_FLOOR_GB = 20.0
"""The free space a drive must have (``jason.storage.DEFAULT_MIN_FREE_GB``: what ``jason storage --check`` calls roomy)."""


def _free(path: Path) -> int | None:
    from jason.storage import free_bytes

    return free_bytes(path)


@check("service-verify")
@_safe
def service_verify(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Everything current: each source's standing (the Status screen's rows, from the stores' own last-read stamps), a fresh
    heartbeat (``service-heartbeat``), and room on the drives jason writes to (the data folder's and the temp folder's, against
    ``jason storage --check``'s floor). A source that is stale, failed, or not signed in fails the read; one never read is counted
    and does not (a community may not use every source). Free space is said as *at least* or *under* the floor, never as a
    figure, so the message changes only when the answer does. Reads disk only; contacts nothing."""
    import jason.config as config
    import jason.storage as storage
    from jason.integrations import connections
    from jason.integrations.registry import Scope

    rows: dict[str, dict[str, Any]] = {}
    for reading in connections.readings(_community_key(), scope=Scope.COMMUNITY, settings=_settings(), root=readers.data_dir,
                                        now=_now(readers), path=readers.data_dir / connections.FILE,
                                        profile=lambda: readers.community):
        for row in reading.sources:
            rows[str(row.get("key"))] = row
    counts: dict[str, int] = {}
    for row in rows.values():
        word = str(row.get("standing") or "no threshold")
        counts[word] = counts.get(word, 0) + 1
    bad = sum(counts.get(w, 0) for w in ("stale", "failed", "not signed in"))
    beat = service_heartbeat(readers, view, item)
    beat_word = beat.message.split(":", 1)[0]
    floor = int(DRIVE_FLOOR_GB * storage.GB)
    setting = config.temp_dir_setting(None)
    temp = config.resolve_temp_dir(setting) if setting else config.system_temp()
    drives, short = [], 0
    for name, path in (("data", readers.data_dir), ("temp", temp)):
        free = _free(path)
        if free is None:
            drives.append(f"{name} drive not readable")
            short += 1
        elif free < floor:
            drives.append(f"{name} drive under {DRIVE_FLOOR_GB:g} GB free")
            short += 1
        else:
            drives.append(f"{name} drive at least {DRIVE_FLOOR_GB:g} GB free")
    temp_problem = config.temp_dir_problem(temp) if setting else ""
    if temp_problem:
        drives.append("the temp folder cannot be used")
        short += 1
    standing = ", ".join(f"{n} {w}" for w, n in sorted(counts.items())) or "no source"
    message = f"{len(rows)} source(s): {standing}; heartbeat {beat_word}; {'; '.join(drives)}"
    return CheckResult(bad == 0 and beat.ok and short == 0, (), message)


__all__ = ["GMAIL_STALE_AFTER", "HEARTBEAT_BEAT_SECONDS", "HEARTBEAT_STALE_AFTER", "MAIL_STALE_AFTER", "gmail_fresh",
           "instance_which", "integration_state", "mail_fresh", "mail_lanes", "mail_period_chosen", "mail_scanned",
           "responses_channels", "responses_outstanding", "responses_recognized", "service_heartbeat", "service_limits",
           "service_queue", "service_verify", "thread_status"]
