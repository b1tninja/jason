"""The approvals store: one JSON file an approval in ``approvals/`` under the active profile's data folder
(``jason.config.data_dir``), written whole under the store lock (``jason.locks``), never checked in.

The audit log (``audit.jsonl``) sits beside the approvals; ``jason.approvals.audit`` appends to it. A plan that read
records live keeps what it read beside its approval (``<id>.evidence.json``, written once with the plan), so its
evidence can be opened later without reading the system again (``jason.approvals.evidence``).
"""

from __future__ import annotations

import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from jason.approvals.model import Approval, from_dict, to_dict

LOCK_KEY = "approvals"


def store_dir(data_dir: Path | None = None) -> Path:
    """``approvals/`` in ``data_dir``, else in the active profile's data folder, resolved when called."""
    if data_dir is None:
        from jason.config import data_dir as profile_data_dir

        data_dir = profile_data_dir()
    return Path(data_dir) / "approvals"


@contextmanager
def locked(purpose: str = "") -> Iterator[None]:
    """The approvals store's lock, for a read, change, and write back."""
    from jason.locks import Resource, hold

    with hold(Resource.STORE, LOCK_KEY, timeout=120, purpose=purpose or "approvals"):
        yield


def new_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"apr-{now.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(2)}"


def _file(data_dir: Path | None, ident: str) -> Path:
    return store_dir(data_dir) / f"{ident}.json"


def save(approval: Approval, data_dir: Path | None = None) -> Path:
    """Write the approval whole (a temporary file, then a replace). The caller holds ``locked``."""
    folder = store_dir(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    file = _file(data_dir, approval.id)
    tmp = file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(to_dict(approval), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, file)
    return file


def ids(data_dir: Path | None = None) -> list[str]:
    """The approvals' ids. A sidecar beside one (``apr-....evidence.json``) is not an approval: an id has no dot."""
    folder = store_dir(data_dir)
    return sorted(p.stem for p in folder.glob("apr-*.json") if "." not in p.stem) if folder.is_dir() else []


def snapshot_file(ident: str, data_dir: Path | None = None) -> Path:
    """``approvals/<id>.evidence.json``: what the plan read of each record its evidence names, as it was read."""
    return store_dir(data_dir) / f"{ident}.evidence.json"


def save_snapshots(ident: str, snapshots: dict[str, Any], data_dir: Path | None = None) -> Path | None:
    """Write the plan's snapshot sidecar whole; nothing when there is nothing to keep. The caller holds ``locked``."""
    if not snapshots:
        return None
    file = snapshot_file(ident, data_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshots, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, file)
    return file


def load_snapshots(ident: str, data_dir: Path | None = None) -> dict[str, Any]:
    """The plan's snapshot by address, or {} when the plan kept none (an older approval, or a kind that reads none)."""
    file = snapshot_file(ident, data_dir)
    if not file.is_file():
        return {}
    data = json.loads(file.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def resolve(ident: str, data_dir: Path | None = None) -> str:
    """An approval's id from its id or a unique prefix."""
    known = ids(data_dir)
    if ident in known:
        return ident
    found = [i for i in known if i.startswith(ident)]
    if len(found) != 1:
        raise KeyError(f"{'no' if not found else 'more than one'} approval {ident}")
    return found[0]


def load(ident: str, data_dir: Path | None = None) -> Approval:
    file = _file(data_dir, resolve(ident, data_dir))
    return from_dict(json.loads(file.read_text(encoding="utf-8")))


def load_all(data_dir: Path | None = None) -> list[Approval]:
    return [load(i, data_dir) for i in ids(data_dir)]


__all__ = ["LOCK_KEY", "ids", "load", "load_all", "load_snapshots", "locked", "new_id", "resolve", "save",
           "save_snapshots", "snapshot_file", "store_dir"]
