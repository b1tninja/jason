"""Writes that survive a power cut: the splitter's and the record slots' stores (docs/pdf-splitter-failure-modes.md, G-4 and E-8).

``os.replace`` makes a swap atomic, not durable: after a power loss the new name can point at an empty file. ``durable_write`` writes
a temporary file in the same folder, flushes it and ``fsync``s it, replaces the target (retrying a short while when an antivirus scan
or an indexer holds the file, which Windows allows to happen), and ``fsync``s the folder where the operating system has that (Windows
has not; the file's own ``fsync`` is what it offers). ``durable_append`` is the same for one line added to a log. Neither names a file
in its error: the caller words it.

``backup=True`` first copies the file it is about to replace to ``<name>.bak`` (itself durably), so one version back is always on disk.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

RETRY_DELAYS = (0.05, 0.15, 0.4)         # seconds before the second, third, and fourth try of a replace that Windows refuses


def fsync_dir(folder: Path) -> None:
    """Flush a folder's entries where the platform allows it; a platform that does not is not an error."""
    if sys.platform == "win32":
        return
    try:
        fd = os.open(str(folder), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _replace(tmp: Path, target: Path) -> None:
    for delay in (*RETRY_DELAYS, None):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)


def _as_bytes(data: bytes | str) -> bytes:
    return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")


def durable_write(path: Path | str, data: bytes | str, *, backup: bool = False) -> Path:
    """Write ``data`` to ``path`` whole: temp file, flush, ``fsync``, replace, ``fsync`` of the folder. With ``backup``, the file that
    was there is kept as ``<name>.bak`` first. The temp file is removed if anything fails. Returns the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if backup and target.is_file():
        try:
            durable_write(target.with_name(target.name + ".bak"), target.read_bytes())
        except OSError:
            pass                                                     # a version that cannot be copied is not a reason to lose the new one
    tmp = target.with_name(f"{target.name}.{os.getpid()}.{os.urandom(3).hex()}.tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(_as_bytes(data))
            fh.flush()
            os.fsync(fh.fileno())
        _replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    fsync_dir(target.parent)
    return target


def durable_append(path: Path | str, line: bytes | str) -> None:
    """Add one line to a log: a single write, flushed and ``fsync``ed, so a reader never sees half of one that was acknowledged."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _as_bytes(line)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_create(path: Path | str, data: bytes | str) -> bool:
    """Create ``path`` with ``data`` only if nothing is there (``O_EXCL``), flushed to disk. False when the name is taken; nothing is
    overwritten. A failure after the file exists removes it, so a half-written file is never left under the name."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_as_bytes(data))
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    fsync_dir(target.parent)
    return True


__all__ = ["durable_append", "durable_create", "durable_write", "fsync_dir"]
