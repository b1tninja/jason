"""Bulk writes done slowly, item by item, with a ledger that survives a crash, a rate limit, or Ctrl-C.

A batch is a list of items (one email, one letter) that a person confirmed together. The ledger (``data/batches.db``)
keeps every item's status, attempts, last error, and result, and an event for each step, so a run can stop at any point
and the next run picks up where it left off:

- **pending** items are sent one at a time, with a pause between them (``Pace``: an interval plus a random jitter);
- an item is marked **sending** before its request and **sent** after; one left **sending** by a crash or Ctrl-C is
  **uncertain** on the next run, and the handler's ``verify`` asks PayHOA whether it happened before anything is resent
  (sent, back to pending, or left for a person when it cannot tell);
- a **429** (or 503) waits the server's Retry-After, or a growing backoff, and tries the same item again without
  counting an attempt; a wait longer than ``Pace.max_wait`` pauses the batch instead;
- a timeout, dropped connection, or 5xx leaves the outcome unknown: the item is verified, then tried again, up to
  ``Pace.max_attempts``;
- a rejected request (another 4xx) fails that item and the run goes on; a refused session (401, 403, 419) pauses the
  batch, since every item after it would fail the same way;
- ``Pace.max_failures`` failures in a row pause the batch (a circuit breaker).

A paused or interrupted batch resumes with the same command. One run at a time holds the PayHOA lock. Nothing is sent
without a person's confirmation: ``create`` records who confirmed it, and only items in the ledger are ever sent.
"""

from __future__ import annotations

import json
import random
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from jason.locks import Resource, account, hold


class ItemStatus(Enum):
    PENDING = "pending"
    SENDING = "sending"        # the request is out; a crash here leaves the outcome unknown
    SENT = "sent"
    UNCERTAIN = "uncertain"    # may or may not have happened: verify before sending again
    FAILED = "failed"
    SKIPPED = "skipped"


class BatchStatus(Enum):
    OPEN = "open"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    CANCELLED = "cancelled"


class Outcome(Enum):
    RATE_LIMITED = "rate limited"      # wait and try the same item again
    UNKNOWN = "unknown"                # timeout, connection, 5xx: verify, then maybe again
    REFUSED = "refused"                # the session: pause the batch
    REJECTED = "rejected"              # this item: fail it, go on


@dataclass(frozen=True)
class Pace:
    interval: float = 8.0          # seconds between items
    jitter: float = 4.0            # plus up to this, at random
    step: float = 2.0              # between the requests inside one item (an upload, then a send)
    max_attempts: int = 3          # tries of one item after unknown outcomes
    max_failures: int = 3          # failures in a row before the batch pauses
    backoff: float = 30.0          # the first wait on a rate limit with no Retry-After; doubles each time
    max_wait: float = 900.0        # a longer wait pauses the batch instead
    max_rate_waits: int = 6        # rate-limit waits for one item before the batch pauses
    headroom: int = 50             # when PayHOA says fewer requests than this are left (x-ratelimit-remaining) ...
    cooldown: float = 60.0         # ... wait this long before the next item


@dataclass
class Item:
    batch_id: str
    key: str
    label: str
    payload: dict[str, Any]
    status: ItemStatus = ItemStatus.PENDING
    attempts: int = 0
    last_error: str = ""
    result: dict[str, Any] = field(default_factory=dict)


class Handler(Protocol):
    def send(self, item: Item, checkpoint: Callable[..., None], step: Callable[[], None]) -> dict[str, Any]: ...

    def verify(self, item: Item) -> bool | None: ...


class BatchPaused(RuntimeError):
    pass


def classify(exc: BaseException) -> tuple[Outcome, float | None]:
    """What a failed request means for the batch, and the server's wait (seconds) when it gave one."""
    import httpx

    from payhoa.exceptions import PayhoaApiError, PayhoaAuthError

    if isinstance(exc, PayhoaAuthError):
        return Outcome.REFUSED, None
    if isinstance(exc, PayhoaApiError):
        code = exc.status_code or 0
        wait = getattr(exc, "retry_after", None)
        if code == 429 or (code == 503 and wait is not None):
            return Outcome.RATE_LIMITED, wait
        if code == 419:
            return Outcome.REFUSED, None
        if code >= 500:
            return Outcome.UNKNOWN, None
        return Outcome.REJECTED, None
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, ConnectionError, TimeoutError)):
        return Outcome.UNKNOWN, None
    return Outcome.REJECTED, None


# -- the ledger --------------------------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(data_dir: Path) -> sqlite3.Connection:
    con = sqlite3.connect(data_dir / "batches.db")
    con.row_factory = sqlite3.Row
    con.executescript("""
        create table if not exists batches (id text primary key, kind text, title text, created text, confirmed_by text,
            status text, params text, notes text default '');
        create table if not exists items (batch_id text, key text, label text, payload text, status text,
            attempts integer default 0, last_error text default '', result text default '{}', updated text,
            primary key (batch_id, key));
        create table if not exists events (batch_id text, key text, at text, kind text, detail text);
    """)
    return con


def create(data_dir: Path, batch_id: str, kind: str, title: str, items: Iterable[tuple[str, str, dict[str, Any]]], *,
           confirmed_by: str, params: dict[str, Any] | None = None) -> int:
    """Record a batch and its items (key, label, payload). A batch is created once; creating it again adds only the
    items it does not have, so a re-run of the command that made it never resends what was sent."""
    if not confirmed_by:
        raise ValueError("a batch needs the name of the person who confirmed it")
    with _connect(data_dir) as con:
        con.execute("insert or ignore into batches values (?, ?, ?, ?, ?, ?, ?, '')",
                    (batch_id, kind, title, _now(), confirmed_by, BatchStatus.OPEN.value, json.dumps(params or {})))
        added = 0
        for key, label, payload in items:
            cur = con.execute("insert or ignore into items (batch_id, key, label, payload, status, updated) "
                              "values (?, ?, ?, ?, ?, ?)", (batch_id, key, label, json.dumps(payload),
                                                            ItemStatus.PENDING.value, _now()))
            added += cur.rowcount
        if added:                                             # new items reopen a finished batch
            con.execute("update batches set status = ? where id = ? and status = ?",
                        (BatchStatus.OPEN.value, batch_id, BatchStatus.DONE.value))
        _event(con, batch_id, "", "created" if added else "re-created", f"{added} item(s) added by {confirmed_by}")
    return added


def _event(con: sqlite3.Connection, batch_id: str, key: str, kind: str, detail: str = "") -> None:
    con.execute("insert into events values (?, ?, ?, ?, ?)", (batch_id, key, _now(), kind, detail[:500]))


def items(data_dir: Path, batch_id: str) -> list[Item]:
    with _connect(data_dir) as con:
        rows = con.execute("select * from items where batch_id = ? order by rowid", (batch_id,)).fetchall()
    return [Item(r["batch_id"], r["key"], r["label"], json.loads(r["payload"]), ItemStatus(r["status"]), r["attempts"],
                 r["last_error"], json.loads(r["result"] or "{}")) for r in rows]


def batch(data_dir: Path, batch_id: str) -> dict[str, Any]:
    with _connect(data_dir) as con:
        row = con.execute("select * from batches where id = ?", (batch_id,)).fetchone()
        if row is None:
            raise KeyError(batch_id)
        counts = dict(con.execute("select status, count(*) from items where batch_id = ? group by status", (batch_id,)))
    return {**dict(row), "params": json.loads(row["params"] or "{}"), "counts": counts}


def batches(data_dir: Path) -> list[dict[str, Any]]:
    with _connect(data_dir) as con:
        ids = [r[0] for r in con.execute("select id from batches order by created desc")]
    return [batch(data_dir, i) for i in ids]


def events(data_dir: Path, batch_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    with _connect(data_dir) as con:
        rows = con.execute("select * from events where batch_id = ? order by rowid desc limit ?", (batch_id, limit))
        return [dict(r) for r in rows]


def _set(data_dir: Path, item: Item, status: ItemStatus, *, error: str = "", event: str = "", detail: str = "") -> None:
    item.status = status
    if error:
        item.last_error = error
    with _connect(data_dir) as con:
        con.execute("update items set status = ?, attempts = ?, last_error = ?, result = ?, updated = ? "
                    "where batch_id = ? and key = ?", (status.value, item.attempts, item.last_error,
                                                       json.dumps(item.result), _now(), item.batch_id, item.key))
        _event(con, item.batch_id, item.key, event or status.value, detail or error)


def _set_batch(data_dir: Path, batch_id: str, status: BatchStatus, note: str = "") -> None:
    with _connect(data_dir) as con:
        con.execute("update batches set status = ?, notes = ? where id = ?", (status.value, note, batch_id))
        _event(con, batch_id, "", f"batch {status.value}", note)


def cancel(data_dir: Path, batch_id: str) -> None:
    """Stop a batch for good: its pending items are skipped; what was sent stays sent."""
    with _connect(data_dir) as con:
        con.execute("update items set status = ?, updated = ? where batch_id = ? and status in (?, ?)",
                    (ItemStatus.SKIPPED.value, _now(), batch_id, ItemStatus.PENDING.value, ItemStatus.FAILED.value))
    _set_batch(data_dir, batch_id, BatchStatus.CANCELLED, "cancelled by a person")


def retry_failed(data_dir: Path, batch_id: str) -> int:
    """Put a batch's failed items back to pending (a person looked at why they failed)."""
    with _connect(data_dir) as con:
        cur = con.execute("update items set status = ?, attempts = 0, updated = ? where batch_id = ? and status = ?",
                          (ItemStatus.PENDING.value, _now(), batch_id, ItemStatus.FAILED.value))
        _event(con, batch_id, "", "failed items reset", f"{cur.rowcount} item(s)")
        return cur.rowcount


def resolve(data_dir: Path, batch_id: str, key: str, *, sent: bool) -> None:
    """A person's answer for an uncertain item: it was sent, or it was not (back to pending)."""
    item = next(i for i in items(data_dir, batch_id) if i.key == key)
    _set(data_dir, item, ItemStatus.SENT if sent else ItemStatus.PENDING, event="resolved by a person",
         detail="sent" if sent else "not sent")


# -- the run -----------------------------------------------------------------------------------------------------------

def run(data_dir: Path, batch_id: str, handler: Handler, *, pace: Pace = Pace(), limit: int | None = None,
        sleep: Callable[[float], None] = time.sleep, say: Callable[[str], None] = print,
        rng: random.Random | None = None, remaining: Callable[[], int | None] = lambda: None,
        profile: str = "") -> dict[str, int]:
    """Send a batch's remaining items through ``handler``, slowly, recording each step. ``limit`` stops after that many
    items are sent (a first test). ``remaining`` reads the API's own count of requests left (the client's
    ``rate_remaining``); below ``Pace.headroom`` the run cools down first. Returns the item counts by status.

    The run holds the community's PayHOA lock (``profile``, the active one by default): one PayHOA writer per
    community at a time, and another community's batch never waits on it."""
    rng = rng or random.Random()
    info = batch(data_dir, batch_id)
    if info["status"] in (BatchStatus.DONE.value, BatchStatus.CANCELLED.value):
        say(f"batch {batch_id} is {info['status']}: nothing to do")
        return info["counts"]
    with hold(Resource.PAYHOA, account(profile), timeout=5, purpose=f"batch {batch_id}"):
        _set_batch(data_dir, batch_id, BatchStatus.RUNNING)
        try:
            _recover(data_dir, batch_id, handler, say)
            _send_all(data_dir, batch_id, handler, pace, limit, sleep, say, rng, remaining)
        except BatchPaused as why:
            _set_batch(data_dir, batch_id, BatchStatus.PAUSED, str(why))
            say(f"paused: {why}. Resume with the same command.")
        except KeyboardInterrupt:
            _set_batch(data_dir, batch_id, BatchStatus.PAUSED, "interrupted")
            say("interrupted: the item in flight is checked against PayHOA on the next run")
        else:
            left = [i for i in items(data_dir, batch_id) if i.status in (ItemStatus.PENDING, ItemStatus.UNCERTAIN)]
            _set_batch(data_dir, batch_id, BatchStatus.OPEN if left else BatchStatus.DONE,
                       f"{len(left)} item(s) left" if left else "")
    return batch(data_dir, batch_id)["counts"]


def _recover(data_dir: Path, batch_id: str, handler: Handler, say: Callable[[str], None]) -> None:
    """Items a crash left in flight are uncertain; each uncertain item is checked against PayHOA."""
    for item in items(data_dir, batch_id):
        if item.status is ItemStatus.SENDING:
            _set(data_dir, item, ItemStatus.UNCERTAIN, event="found in flight", detail="the last run stopped mid-send")
        if item.status is ItemStatus.UNCERTAIN:
            _verify(data_dir, item, handler, say)


def _verify(data_dir: Path, item: Item, handler: Handler, say: Callable[[str], None]) -> bool:
    """Whether an uncertain item happened, by the handler's check: sent, back to pending, or left for a person."""
    try:
        done = handler.verify(item)
    except Exception as exc:                                  # the check itself failed: leave it for later
        say(f"  {item.label}: could not verify ({exc}); left uncertain")
        return False
    if done is True:
        _set(data_dir, item, ItemStatus.SENT, event="verified sent")
        say(f"  {item.label}: verified sent")
        return True
    if done is False:
        _set(data_dir, item, ItemStatus.PENDING, event="verified not sent")
        return False
    say(f"  {item.label}: cannot tell whether it was sent; left for a person (jason batches --resolve)")
    return False


def _send_all(data_dir: Path, batch_id: str, handler: Handler, pace: Pace, limit: int | None,
              sleep: Callable[[float], None], say: Callable[[str], None], rng: random.Random,
              remaining: Callable[[], int | None] = lambda: None) -> None:
    sent = failures = 0
    first = True
    for item in items(data_dir, batch_id):
        if item.status is not ItemStatus.PENDING:
            continue
        if limit is not None and sent >= limit:
            say(f"stopped after {sent} (the limit for this run)")
            return
        if not first:
            sleep(pace.interval + rng.uniform(0, pace.jitter))
        first = False
        left = remaining()
        if left is not None and left < pace.headroom:
            say(f"  PayHOA allows {left} more requests for now; waiting {pace.cooldown:.0f}s")
            sleep(pace.cooldown)
        if _send_one(data_dir, item, handler, pace, sleep, say):
            sent += 1
            failures = 0
        elif item.status is ItemStatus.FAILED:
            failures += 1
            if failures >= pace.max_failures:
                raise BatchPaused(f"{failures} failures in a row (last: {item.last_error})")


def _send_one(data_dir: Path, item: Item, handler: Handler, pace: Pace, sleep: Callable[[float], None],
              say: Callable[[str], None]) -> bool:
    waits = 0

    def checkpoint(**data: Any) -> None:                    # a step inside the item that a retry should reuse
        item.result.update(data)
        _set(data_dir, item, ItemStatus.SENDING, event="checkpoint", detail=json.dumps(data))

    while True:
        item.attempts += 1
        _set(data_dir, item, ItemStatus.SENDING, event="sending", detail=f"attempt {item.attempts}")
        try:
            result = handler.send(item, checkpoint, lambda: sleep(pace.step))
        except Exception as exc:                              # noqa: BLE001 — every failure is classified and recorded
            outcome, wait = classify(exc)
            error = f"{type(exc).__name__}: {exc}"
            if outcome is Outcome.RATE_LIMITED:
                item.attempts -= 1                            # a rate limit is not the item's fault
                waits += 1
                delay = wait if wait is not None else pace.backoff * 2 ** (waits - 1)
                _set(data_dir, item, ItemStatus.PENDING, error=error, event="rate limited", detail=f"wait {delay:.0f}s")
                if delay > pace.max_wait or waits > pace.max_rate_waits:
                    raise BatchPaused(f"rate limited at {item.label}; the server asked for {delay:.0f}s") from exc
                say(f"  rate limited: waiting {delay:.0f}s before {item.label}")
                sleep(delay)
                continue
            if outcome is Outcome.REFUSED:                    # refused before it was processed: not sent
                item.attempts -= 1
                _set(data_dir, item, ItemStatus.PENDING, error=error, event="refused")
                raise BatchPaused(f"PayHOA refused the session ({error}); sign in again (jason login)") from exc
            if outcome is Outcome.UNKNOWN:
                _set(data_dir, item, ItemStatus.UNCERTAIN, error=error, event="outcome unknown")
                say(f"  {item.label}: {error}; checking whether it went through")
                if _verify(data_dir, item, handler, say):
                    return True
                if item.status is ItemStatus.UNCERTAIN:       # cannot tell: never resend blind
                    return False
                if item.attempts >= pace.max_attempts:
                    _set(data_dir, item, ItemStatus.FAILED, error=error, event="gave up",
                         detail=f"{item.attempts} attempts")
                    return False
                sleep(pace.backoff)
                continue
            _set(data_dir, item, ItemStatus.FAILED, error=error, event="rejected")
            say(f"  {item.label}: failed: {error}")
            return False
        item.result.update(result or {})
        _set(data_dir, item, ItemStatus.SENT, event="sent", detail=json.dumps(result or {})[:300])
        say(f"  sent: {item.label}")
        return True


def lines(info: dict[str, Any]) -> str:
    counts = ", ".join(f"{k} {v}" for k, v in sorted(info["counts"].items()))
    return f"{info['id']}  {info['status']:9}  {info['title']}  ({counts}; confirmed by {info['confirmed_by']})"


__all__ = ["BatchPaused", "BatchStatus", "Handler", "Item", "ItemStatus", "Outcome", "Pace", "batch", "batches",
           "cancel", "classify", "create", "events", "items", "lines", "resolve", "retry_failed", "run"]
