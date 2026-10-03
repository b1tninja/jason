"""The approvals audit log: ``audit.jsonl`` in the approvals store, append only.

One JSON object a line: ``seq``, ``at``, ``event``, the approval and kind, the actor and how they came (``via``: the
CLI or the console), the operating-system user, the fingerprint, the items, the result, and a detail. Each line
carries the hash of the line before it (``prev``) and its own (``hash``), so an edit anywhere breaks the chain and
``verify`` names the first broken line. That makes tampering detectable, not impossible.

No code path rewrites or deletes a line. A line holds nothing above a name and a tag: an email address in a detail is
masked before it is written.
"""

from __future__ import annotations

import getpass
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.approvals.model import canonical, digest

EVENTS = (
    "plan.created", "plan.failed", "item.decided", "approval.submitted", "approval.confirmed", "approval.declined",
    "apply.started", "apply.refused", "item.applying", "item.applied", "item.failed", "item.uncertain", "item.blocked",
    "item.not_applied", "approval.applied", "approval.failed", "approval.superseded", "approval.withdrawn",
    "cli.applied",
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def path(data_dir: Path | None = None) -> Path:
    from jason.approvals.store import store_dir

    return store_dir(data_dir) / "audit.jsonl"


def os_actor() -> str:
    """The operating-system user, named as such, when no person was named."""
    try:
        return f"os:{getpass.getuser()}"
    except Exception:  # noqa: BLE001 - no user name on this machine
        return "os:unknown"


def mask(value: Any) -> Any:
    """``value`` with any email address replaced: the log holds names and tags, never contact details."""
    if isinstance(value, str):
        return _EMAIL.sub("[email]", value)
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask(v) for v in value]
    return value


def _last(file: Path) -> dict[str, Any] | None:
    if not file.is_file():
        return None
    last = None
    with file.open("rb") as fh:
        for line in fh:
            if line.strip():
                last = line
    return json.loads(last) if last else None


def append(data_dir: Path | None, event: str, **fields: Any) -> dict[str, Any]:
    """Append one entry, chained to the last, under the store lock. Returns the entry as written."""
    from jason.locks import Resource, hold

    if event not in EVENTS:
        raise ValueError(f"unknown audit event {event}")
    file = path(data_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, "approvals-audit", timeout=60, purpose=f"audit {event}"):
        last = _last(file)
        entry = {"seq": int(last["seq"]) + 1 if last else 1,
                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event,
                 "os_user": os_actor()[3:]}
        entry.update({k: mask(v) for k, v in fields.items() if v not in (None, "", [], {})})
        entry["prev"] = last["hash"] if last else ""
        entry["hash"] = digest({k: v for k, v in entry.items() if k != "hash"})
        with file.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical(entry) + "\n")
    return entry


def read(data_dir: Path | None = None, approval: str = "") -> list[dict[str, Any]]:
    """The entries, oldest first; with ``approval``, that approval's only."""
    file = path(data_dir)
    if not file.is_file():
        return []
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if not approval or r.get("approval") == approval]


def verify(data_dir: Path | None = None) -> tuple[bool, int | None, str]:
    """Walk the chain: (whole, the first broken line's number, why)."""
    file = path(data_dir)
    if not file.is_file():
        return True, None, "no audit log yet"
    prev = ""
    for n, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            return False, n, "not JSON"
        if entry.get("prev", "") != prev:
            return False, n, "its prev is not the hash of the line before"
        if digest({k: v for k, v in entry.items() if k != "hash"}) != entry.get("hash"):
            return False, n, "its hash does not match its contents"
        prev = entry["hash"]
    return True, None, "the chain is whole"


def record_cli(data_dir: Path | None, *, kind: str, actor: str, command: str,
               writes: Iterable[tuple[str, str, str, str, str, str]], completed: Iterable[int] = ()) -> None:
    """A CLI --yes, as the approvals log it: one line a write (op, target, label, value, result, detail) and a
    completed request, then a summary with a fingerprint of what was written."""
    writes = list(writes)
    for op, target, label, value, result, detail in writes:
        event = {"applied": "item.applied", "failed": "item.failed"}.get(result, "item.not_applied")
        append(data_dir, event, kind=kind, actor=actor, via="cli", op=op, target=target, label=label, value=value,
               result=result, detail=detail)
    completed = list(completed)
    for sid in completed:
        append(data_dir, "item.applied", kind=kind, actor=actor, via="cli", op="complete request",
               target=f"submission:{sid}", value="complete", result="applied")
    made = sorted([op, target, value] for op, target, _, value, result, _ in writes if result == "applied")
    append(data_dir, "cli.applied", kind=kind, actor=actor, via="cli", detail=command,
           fingerprint=digest({"writes": made, "completed": sorted(completed)}),
           result={"applied": len(made), "notApplied": len(writes) - len(made), "completedRequests": len(completed)})


__all__ = ["EVENTS", "append", "mask", "os_actor", "path", "read", "record_cli", "verify"]
