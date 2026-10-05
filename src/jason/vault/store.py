"""The ``SecretStore`` interface, the ``Secret`` value, and ``MemoryStore`` (docs/integrations-design.md, The vault).

A secret is a small set of named fields (``login``, ``password``, ``client_id``, ...), every value a string. A
``Secret`` never shows a value in ``repr()`` or ``str()``: only its field names. ``list`` and ``describe`` return
names, versions, and times, never a value.

Versions are for check-and-set. ``put(path, value, if_version=N)`` writes only when the stored version is ``N``;
``if_version=0`` writes only when nothing is stored there (create, never overwrite). A stale version raises
``VersionConflict``. ``None`` writes unconditionally.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol, runtime_checkable

from jason.vault.paths import check_path, check_prefix


class VaultError(RuntimeError):
    """The vault could not answer as asked (a backend's own failure, or an ambiguous entry)."""


class VersionConflict(VaultError):
    """A check-and-set write whose expected version is not the stored one."""

    def __init__(self, path: str, expected: int, actual: int) -> None:
        self.path, self.expected, self.actual = path, expected, actual
        super().__init__(f"{path}: expected version {expected}, the vault holds version {actual}")


class Secret(Mapping[str, str]):
    """A secret's fields, read-only. ``repr()`` and ``str()`` name the fields and never show a value."""

    __slots__ = ("_fields",)

    def __init__(self, fields: Mapping[str, str] | None = None) -> None:
        self._fields = {str(k): str(v) for k, v in dict(fields or {}).items() if v is not None and str(v) != ""}

    def __getitem__(self, key: str) -> str:
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)

    def __repr__(self) -> str:
        return f"Secret(fields={sorted(self._fields)})"

    __str__ = __repr__

    def __reduce__(self):  # a Secret is not pickled into a cache or a job's arguments by accident
        raise TypeError("a Secret is not pickled")

    def __copy__(self) -> Secret:      # read-only, so a copy is itself
        return self

    def __deepcopy__(self, memo: dict) -> Secret:
        return self

    def first(self, *names: str) -> str:
        """The first of ``names`` that is set, matched without case, or ""."""
        lowered = {k.lower(): v for k, v in self._fields.items()}
        for name in names:
            if lowered.get(name.lower()):
                return lowered[name.lower()]
        return ""


@dataclass(frozen=True)
class VaultEntry:
    """What ``describe`` tells about a path: never its value."""

    path: str
    is_set: bool
    version: int = 0                  # 0 when nothing is stored
    changed: datetime | None = None
    by: str = ""                      # who wrote it, where the backend records it


@runtime_checkable
class SecretStore(Protocol):
    """One interface for every backend: Keeper now; SSM, Secrets Manager, or OpenBao when deployed."""

    name: str

    def get(self, path: str) -> Secret | None: ...

    def put(self, path: str, value: Mapping[str, str], if_version: int | None = None, *, by: str = "") -> int: ...

    def delete(self, path: str) -> bool: ...

    def list(self, prefix: str) -> list[str]: ...

    def describe(self, path: str) -> VaultEntry: ...


@dataclass
class _Row:
    version: int
    fields: dict[str, str]
    changed: datetime
    by: str

    def __repr__(self) -> str:
        return f"_Row(version={self.version}, fields={sorted(self.fields)}, by={self.by!r})"


class MemoryStore:
    """An in-memory ``SecretStore`` for tests: versions for check-and-set, and who wrote each entry."""

    name = "memory"

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._rows: dict[str, _Row] = {}
        self._last: dict[str, int] = {}          # a path's last version, kept across a delete
        self._lock = threading.Lock()
        self._now = now or (lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"MemoryStore({len(self._rows)} entries)"

    def get(self, path: str) -> Secret | None:
        path = check_path(path)
        with self._lock:
            row = self._rows.get(path)
            return Secret(row.fields) if row else None

    def put(self, path: str, value: Mapping[str, str], if_version: int | None = None, *, by: str = "") -> int:
        path = check_path(path)
        fields = dict(Secret(value))
        if not fields:
            raise ValueError(f"{path}: a secret has at least one field with a value")
        with self._lock:
            row = self._rows.get(path)
            current = row.version if row else 0
            if if_version is not None and if_version != current:
                raise VersionConflict(path, if_version, current)
            version = self._last.get(path, 0) + 1
            self._last[path] = version
            self._rows[path] = _Row(version, fields, self._now(), by)
            return version

    def delete(self, path: str) -> bool:
        path = check_path(path)
        with self._lock:
            return self._rows.pop(path, None) is not None

    def list(self, prefix: str) -> list[str]:
        prefix = check_prefix(prefix)
        with self._lock:
            return sorted(p for p in self._rows if p.startswith(prefix))

    def describe(self, path: str) -> VaultEntry:
        path = check_path(path)
        with self._lock:
            row = self._rows.get(path)
            if row is None:
                return VaultEntry(path, False)
            return VaultEntry(path, True, row.version, row.changed, row.by)


__all__ = ["MemoryStore", "Secret", "SecretStore", "VaultEntry", "VaultError", "VersionConflict"]
