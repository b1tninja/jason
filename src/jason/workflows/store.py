"""The run store: one append-only file a run, ``<data_dir>/workflows/<definition>/<run-id>.jsonl``.

One JSON object a line, ``{n, kind, step, by, at, detail, prev}``. ``n`` is the run's sequence number and the
compare-and-swap: an append whose ``n`` is not the last plus one is refused with ``RunChanged``. ``prev`` is the first 12
hex of the sha256 of the previous line, so an edited line breaks the chain (``verify``). Every append holds
``locks.hold(Resource.STORE, "workflows-<run-id>")`` and writes with a flush and fsync. A partial last line (a crash) is
dropped on read and reported as ``torn``; it is never repaired by guessing. ``index.json`` beside the folders is a cache a
run list reads; deleting it loses nothing (``reindex``).

Nothing here sends, files, or writes outside ``data_dir``.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from jason import locks
from jason.locks import Resource
from jason.workflows.types import Event, EventKind, RunChanged, WorkflowError

ROOT = "workflows"
INDEX = "index.json"
LOCK_TIMEOUT = 60.0


class NoSuchRun(WorkflowError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def folder(data_dir: Path | str) -> Path:
    return Path(data_dir) / ROOT


def run_id(definition: str, subject: str, opened_at: str, salt: str = "") -> str:
    """Opaque: ``run-`` and ten hex characters from the hash of the definition, the subject key, the open time, and, when given,
    a ``salt``. Without a salt the id can be recomputed by anyone who tries the subjects (a unit or a parcel is a few hundred
    values, and the open day shows on the run), so ``api.start`` always gives one: a random string kept nowhere, which makes
    the id a handle that says nothing of its subject."""
    text = f"{definition}\0{subject}\0{opened_at}" + (f"\0{salt}" if salt else "")
    return "run-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def path(data_dir: Path | str, definition: str, rid: str) -> Path:
    return folder(data_dir) / definition / f"{rid}.jsonl"


def chain(line: str) -> str:
    """The ``prev`` the next line carries: the first 12 hex of the sha256 of this line (no newline)."""
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]


def encode(event: Event) -> str:
    return json.dumps(event.to_dict(), separators=(",", ":"), ensure_ascii=False)


def _lock(rid: str, purpose: str = ""):
    return locks.hold(Resource.STORE, f"workflows-{rid}", timeout=LOCK_TIMEOUT, purpose=purpose or f"workflow {rid}")


@dataclass(frozen=True)
class Run:
    """A run as read from disk: its events, the raw lines they came from (for ``verify``), and what could not be read."""

    id: str
    definition: str
    data_dir: Path
    events: tuple[Event, ...]
    lines: tuple[str, ...]
    torn: str = ""               # the partial last line that was dropped, "" when none
    corrupt: int = 0             # the 1-based line number of the first line that is not an event, 0 when none
    good_bytes: int = 0          # how many bytes of the file are whole lines before the torn or corrupt tail

    @property
    def n(self) -> int:
        return self.events[-1].n if self.events else 0

    @property
    def tip(self) -> str:
        return chain(self.lines[-1]) if self.lines else ""

    @property
    def path(self) -> Path:
        return path(self.data_dir, self.definition, self.id)


def read(data_dir: Path | str, definition: str, rid: str) -> Run:
    file = path(data_dir, definition, rid)
    if not file.is_file():
        raise NoSuchRun(f"no run {rid} of {definition}")
    data = file.read_bytes()
    pieces = data.split(b"\n")
    tail = pieces.pop()          # after the last newline: empty for a whole file, a partial line after a crash
    events: list[Event] = []
    lines: list[str] = []
    good = 0
    corrupt = 0
    for i, raw in enumerate(pieces, 1):
        try:
            text = raw.decode("utf-8")
            event = Event.from_dict(json.loads(text))
        except (ValueError, UnicodeDecodeError):
            corrupt = i
            break
        events.append(event)
        lines.append(text)
        good += len(raw) + 1
    torn = tail.decode("utf-8", errors="replace") if tail else ""
    return Run(id=rid, definition=definition, data_dir=Path(data_dir), events=tuple(events), lines=tuple(lines),
               torn=torn, corrupt=corrupt, good_bytes=good)


def locate(data_dir: Path | str, rid: str) -> str:
    """The definition a run id belongs to, found by its file; ``NoSuchRun`` when there is none."""
    for found in sorted(folder(data_dir).glob(f"*/{rid}.jsonl")):
        return found.parent.name
    raise NoSuchRun(f"no run {rid}")


def open_run(data_dir: Path | str, rid: str) -> Run:
    return read(data_dir, locate(data_dir, rid), rid)


def list_runs(data_dir: Path | str) -> list[tuple[str, str]]:
    """(definition, run id) for every run file on disk."""
    out = []
    for file in sorted(folder(data_dir).glob("*/run-*.jsonl")):
        out.append((file.parent.name, file.stem))
    return out


def _write_line(file: Path, line: str) -> None:
    with open(file, "ab") as handle:
        handle.write((line + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def create(data_dir: Path | str, definition: str, subject: str, *, by: str, label: str = "",
           detail: Mapping[str, Any] | None = None, at: str = "", salt: str = "") -> Run:
    """Start a run: its first event, ``opened``. The id comes from the definition, the subject, the open time, and a
    ``salt`` (``api.start`` gives a random one); a run that already exists is not overwritten."""
    at = at or now()
    rid = run_id(definition, subject, at, salt)
    file = path(data_dir, definition, rid)
    body = {"definition": definition, "subject": subject, "label": label, **dict(detail or {})}
    event = Event(n=1, kind=EventKind.OPENED, by=by, at=at, detail=body, prev="")
    with _lock(rid, "workflow create"):
        file.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = open(file, "xb")
        except FileExistsError:
            raise WorkflowError(f"run {rid} already exists ({definition}, {subject}, opened {at})") from None
        with handle:
            handle.write((encode(event) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    return read(data_dir, definition, rid)


def append(data_dir: Path | str, definition: str, rid: str, kind: EventKind, *, by: str, step: str = "",
           detail: Mapping[str, Any] | None = None, at: str = "", n: int | None = None) -> Event:
    """Append one event under the run's lock. ``n`` is the sequence number the caller expects the event to have
    (the run's last plus one when it read the run); another process having appended first makes the call fail with
    ``RunChanged`` naming the changed ``n``. A torn last line is cut off (and its text kept in the new event's
    ``detail._torn``) so the file ends in whole lines."""
    with _lock(rid):
        run = read(data_dir, definition, rid)
        if run.corrupt:
            raise WorkflowError(f"run {rid} has a line that is not an event (line {run.corrupt}); no append until a person looks at it")
        want = run.n + 1
        if n is not None and n != want:
            last = run.events[-1]
            raise RunChanged(f"run {rid} changed: expected to append n={n}, but the run is now at n={run.n} "
                             f"({last.kind.value} by {last.by or '?'} at {last.at}); read it again", expected=n, actual=run.n)
        body = dict(detail or {})
        file = run.path
        if run.torn:
            body["_torn"] = run.torn[:200]
            with open(file, "r+b") as handle:
                handle.truncate(run.good_bytes)
                handle.flush()
                os.fsync(handle.fileno())
        event = Event(n=want, kind=kind, by=by, at=at or now(), step=step, detail=body, prev=run.tip)
        _write_line(file, encode(event))
        return event


@dataclass(frozen=True)
class Verification:
    ok: bool
    n: int = 0                   # the event whose link to the line before it is broken
    message: str = ""
    torn: bool = False
    events: int = 0


def verify(run: Run, *, tip: str = "", tip_n: int = 0) -> Verification:
    """Check the chain: every event's ``n`` follows the last, and every ``prev`` is the hash of the line before it. A
    broken link names the event after the edited line, since the edit shows in the next line's ``prev``. The last line
    has no successor to show an edit; the index's ``tip`` (the hash of the last line when it was written) covers it when
    given."""
    for i, event in enumerate(run.events):
        if event.n != i + 1:
            return Verification(False, event.n, f"line {i + 1} has n={event.n}; expected {i + 1}", bool(run.torn), len(run.events))
        want = chain(run.lines[i - 1]) if i else ""
        if event.prev != want:
            edited = f"line n={event.n - 1} was edited or removed" if i else "the first line's prev is not empty"
            return Verification(False, event.n, f"n={event.n}: prev {event.prev!r} does not match the line before it ({edited})",
                                bool(run.torn), len(run.events))
    if run.corrupt:
        return Verification(False, run.corrupt, f"line {run.corrupt} is not an event", bool(run.torn), len(run.events))
    if tip and tip_n and run.n >= tip_n:
        seen = chain(run.lines[tip_n - 1])
        if seen != tip:
            return Verification(False, tip_n, f"line n={tip_n} no longer matches the hash the index kept for it", bool(run.torn), len(run.events))
    return Verification(True, 0, "the chain is whole" + (" (a torn last line was dropped)" if run.torn else ""), bool(run.torn), len(run.events))


# --- the index (a cache) --------------------------------------------------------------------------------------------

def index_path(data_dir: Path | str) -> Path:
    return folder(data_dir) / INDEX


def index_read(data_dir: Path | str) -> dict[str, dict[str, Any]]:
    file = index_path(data_dir)
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
        return {str(r["id"]): dict(r) for r in raw.get("runs", []) if isinstance(r, dict) and r.get("id")}
    except (OSError, ValueError, KeyError, AttributeError):
        return {}


def index_write(data_dir: Path | str, rows: Iterable[Mapping[str, Any]]) -> None:
    """Write the whole index to a temporary file and replace the old one."""
    file = index_path(data_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(f"{INDEX}.{os.getpid()}.tmp")
    body = {"savedAt": now(), "runs": sorted((dict(r) for r in rows), key=lambda r: str(r.get("id", "")))}
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(body, handle, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, file)


def index_put(data_dir: Path | str, row: Mapping[str, Any]) -> None:
    with locks.hold(Resource.STORE, "workflows-index", timeout=LOCK_TIMEOUT, purpose="workflow index"):
        rows = index_read(data_dir)
        rows[str(row["id"])] = dict(row)
        index_write(data_dir, rows.values())


def reindex(data_dir: Path | str, summarize: Callable[[Run], Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild the index from the events: ``summarize`` turns a run into its row. A run that cannot be read is listed with
    its trouble instead of dropped."""
    rows = []
    for definition, rid in list_runs(data_dir):
        try:
            run = read(data_dir, definition, rid)
            row = dict(summarize(run))
        except Exception as exc:  # noqa: BLE001 - one unreadable run does not hide the rest
            row = {"id": rid, "definition": definition, "state": "unreadable", "label": "", "current": "", "due": "",
                   "owner": "", "updated": "", "problem": str(exc)}
        rows.append(row)
    with locks.hold(Resource.STORE, "workflows-index", timeout=LOCK_TIMEOUT, purpose="workflow reindex"):
        index_write(data_dir, rows)
    return rows


__all__ = ["INDEX", "NoSuchRun", "ROOT", "Run", "Verification", "append", "chain", "create", "encode", "folder", "index_path",
           "index_put", "index_read", "index_write", "list_runs", "locate", "now", "open_run", "path", "read", "reindex",
           "run_id", "verify"]
