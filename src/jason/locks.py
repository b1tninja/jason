"""Locks on what jason's processes share: the local model server, the Google and PayHOA accounts, and its own stores.

Several jason processes can run at once: a CLI command, the MCP server answering a tool call, another agent session,
a scheduled sync. Two model requests at once make Ollama load two models, which on this machine runs out of Windows
commit and crashes the model server; two writers of the same store lose one another's changes. ``hold`` takes a
resource for the length of a ``with`` block and waits, up to its timeout, while another process has it.

The lock is an operating-system lock on a byte of a file in the lock folder (``JASON_LOCK_DIR``, else
``%LOCALAPPDATA%/jason/locks``), so it is released when the holding process ends, even by a crash. Beside it a small
JSON note says who holds it (process, command, purpose, since), for ``holders`` and ``jason local-ai``; the note is
advice, the lock is the fact. Within one process a lock is re-entrant: a function that holds the board store may call
another that takes it again.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


class Resource(Enum):
    GPU = "gpu"            # the local model server (Ollama): one generation request from jason at a time
    GOOGLE = "google"      # the association's Google account
    PAYHOA = "payhoa"      # the PayHOA session
    STORE = "store"        # a file jason reads, changes, and writes back; the key names it ("board-items")


class ResourceBusy(RuntimeError):
    """Another process held the resource past the timeout."""


_held = threading.local()


def lock_dir() -> Path:
    base = os.environ.get("JASON_LOCK_DIR") or str(Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "jason" / "locks")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _name(resource: Resource, key: str) -> str:
    return resource.value + (f"-{re.sub(r'[^A-Za-z0-9_.-]+', '-', key)}" if key else "")


def _try_lock(fd: int) -> bool:
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fd: int) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


def _note(name: str) -> Path:
    return lock_dir() / f"{name}.json"


def _read_note(name: str) -> dict[str, Any]:
    try:
        return json.loads(_note(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@contextmanager
def hold(resource: Resource, key: str = "", *, timeout: float = 600, purpose: str = "") -> Iterator[None]:
    """Hold ``resource`` (and ``key``) for the block, waiting up to ``timeout`` seconds for another process to let go."""
    name = _name(resource, key)
    counts: dict[str, int] = getattr(_held, "counts", None) or {}
    _held.counts = counts
    if counts.get(name):
        counts[name] += 1
        try:
            yield
        finally:
            counts[name] -= 1
        return
    fd = os.open(str(lock_dir() / f"{name}.lock"), os.O_RDWR | os.O_CREAT)
    deadline = time.monotonic() + timeout
    try:
        while not _try_lock(fd):
            if time.monotonic() >= deadline:
                who = _read_note(name)
                raise ResourceBusy(f"{name} is held by process {who.get('pid', '?')} ({who.get('purpose') or who.get('command', '?')}) "
                                   f"since {who.get('since', '?')}")
            time.sleep(0.25)
        counts[name] = 1
        note = {"resource": resource.value, "key": key, "pid": os.getpid(), "command": " ".join(sys.argv)[:300],
                "purpose": purpose, "since": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        try:
            _note(name).write_text(json.dumps(note), encoding="utf-8")
        except OSError:
            pass
        try:
            yield
        finally:
            counts[name] = 0
            if _read_note(name).get("pid") == os.getpid():
                try:
                    _note(name).unlink()
                except OSError:
                    pass
            _unlock(fd)
    finally:
        os.close(fd)


def holders() -> list[dict[str, Any]]:
    """Who holds each lock now. A note whose lock is free was left by a process that died; it is removed."""
    out = []
    for note in sorted(lock_dir().glob("*.json")):
        name = note.stem
        fd = os.open(str(lock_dir() / f"{name}.lock"), os.O_RDWR | os.O_CREAT)
        try:
            if _try_lock(fd):
                _unlock(fd)
                try:
                    note.unlink()
                except OSError:
                    pass
                continue
        finally:
            os.close(fd)
        out.append({"lock": name, **_read_note(name)})
    return out


__all__ = ["Resource", "ResourceBusy", "hold", "holders", "lock_dir"]
