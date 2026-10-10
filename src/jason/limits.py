"""Limits: the reasonable defaults jason runs on, each one a record that can be read and, by a person, changed.

A limit is a number or a switch that decides how much jason will take or whether it does a step on its own (the largest upload,
whether a confirmed split queues the read-back). Each is a ``Limit`` with its key, default, minimum, maximum, unit, and
description. ``Limit.effective`` returns the value in force and where it came from, first match winning:

1. ``env``: the process environment, ``JASON_LIMIT_<KEY>`` (``upload.max_bytes`` is ``JASON_LIMIT_UPLOAD_MAX_BYTES``);
2. ``instance``: the same name in the project's ``.env`` or the user config (``config._env_value``, so the user config applies);
3. ``community``: the active profile's ``Community.limits()`` (a mapping of key to value), when the caller passes the profile;
4. ``default``.

A value outside the limit's range is held to the range (``clamped``), never rejected: a setting cannot switch a guard off.
There is no module-level mutable state; every call reads the settings afresh. Nothing here writes (``jason limits`` only lists).
Importing this module loads no profile; the profile is read only when a caller hands it in. See docs/record-intake.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MB = 1024 * 1024
SOURCES = ("env", "instance", "community", "default")
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class Effective:
    """A limit's value in force and where it came from."""

    key: str
    value: Any
    source: str                  # env | instance | community | default
    clamped: bool = False        # the setting was outside the range and was held to it
    raw: str = ""                # what was set, when it was set


@dataclass(frozen=True)
class Limit:
    key: str
    default: int | bool
    minimum: int | None
    maximum: int | None
    unit: str
    description: str

    @property
    def env_name(self) -> str:
        return "JASON_LIMIT_" + self.key.upper().replace(".", "_")

    def _coerce(self, raw: Any) -> tuple[Any, bool] | None:
        """The value held to the range, and whether it was moved; None when it cannot be read."""
        if isinstance(self.default, bool):
            text = str(raw).strip().lower()
            if text in _TRUE:
                return True, False
            if text in _FALSE:
                return False, False
            return None
        try:
            number = int(str(raw).strip().replace("_", ""))
        except (TypeError, ValueError):
            return None
        held = number
        if self.minimum is not None:
            held = max(self.minimum, held)
        if self.maximum is not None:
            held = min(self.maximum, held)
        return held, held != number

    def effective(self, settings: Any = None, community: Any = None) -> Effective:
        """The value in force. ``settings`` is a ``jason.config.Settings`` (its ``env_path`` names the .env to read) or None;
        ``community`` is the active profile when the caller has it. An unreadable setting is skipped for the next source."""
        from jason import config

        env_file: Path | None = getattr(settings, "env_path", None)
        process = os.environ.get(self.env_name, "").strip()
        sources: list[tuple[str, Any]] = [("env", process)]
        sources.append(("instance", "" if process else config._env_value(self.env_name, env_file)))
        sources.append(("community", _from_community(community, self.key)))
        for source, raw in sources:
            if raw in ("", None):
                continue
            got = self._coerce(raw)
            if got is not None:
                return Effective(self.key, got[0], source, clamped=got[1], raw=str(raw))
        return Effective(self.key, self.default, "default")


def _from_community(community: Any, key: str) -> Any:
    if community is None:
        return None
    try:
        held = community.limits()
    except Exception:  # noqa: BLE001 - a profile with nothing to say sets nothing
        return None
    return held.get(key) if isinstance(held, dict) else None


_REGISTRY: tuple[Limit, ...] = (
    Limit("upload.max_bytes", 100 * MB, 1 * MB, 500 * MB, "bytes",
          "The largest file a person may upload from the computer (a record slot, or a key document). A larger file is put on "
          "Drive and picked there."),
    Limit("split.auto_read", True, None, None, "switch",
          "After a person confirms a split, queue a read-back job for each new part file (on the same lane, in the confirming "
          "person's name). Off: each part is read by hand."),
)


def all_limits() -> tuple[Limit, ...]:
    """The registry: every limit jason keeps, in a fixed order."""
    return _REGISTRY


def limit(key: str) -> Limit:
    found = next((l for l in _REGISTRY if l.key == key), None)
    if found is None:
        raise KeyError(f"no limit {key!r}; the limits are {', '.join(l.key for l in _REGISTRY)}")
    return found


def default(key: str) -> Any:
    return limit(key).default


def value(key: str, *, settings: Any = None, community: Any = None) -> Any:
    """The value in force for ``key`` (see ``Limit.effective``)."""
    return limit(key).effective(settings, community).value


def listing(settings: Any = None, community: Any = None) -> list[dict[str, Any]]:
    """Every limit with its value in force and source, as ``jason limits --json`` prints it. Read-only."""
    out = []
    for l in _REGISTRY:
        e = l.effective(settings, community)
        out.append({"key": l.key, "value": e.value, "source": e.source, "clamped": e.clamped, "default": l.default,
                    "minimum": l.minimum, "maximum": l.maximum, "unit": l.unit, "env": l.env_name, "description": l.description})
    return out


def megabytes(n: int) -> int:
    return n // MB


__all__ = ["Effective", "Limit", "SOURCES", "all_limits", "default", "limit", "listing", "megabytes", "value"]
