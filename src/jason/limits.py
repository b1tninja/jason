"""Limits: the bounded numbers and switches jason runs on, each one a record with a reason, a floor, and a ceiling.

A limit is a row in the registry (``LIMITS``), never a number inside a function. Its value is found by walking the layers
from the code down, the last that sets it and is allowed to winning (docs/instance-limits.md):

1. ``default``: the code, reviewed;
2. the profile's ``Community.limits()`` (a mapping of key to value, when the caller passes the profile), reported ``community``;
3. ``JASON_LIMIT_<KEY>`` in the project's ``.env`` or the user config, reported ``instance``;
4. ``JASON_LIMIT_<KEY>`` in the process environment, reported ``env``;
5. the instance file (``~/.jason/limits.json``, ``JASON_LIMITS_FILE``): a ``value`` and a ``ceiling`` for every community,
   reported ``instance``;
6. the community file (``<data folder>/limits.json``), held to ``min(maximum, the instance ceiling)``, reported ``community``.

Every value is held to the limit's range, never rejected on read (``clamped``): a setting cannot switch a guard off, and
there is no "unlimited". A limit marked ``lower_only`` is also held to its default. A limits file that cannot be read gives
the default or the stricter of the layers that can be, never the looser. ``check`` is the one call an enforcement point
makes; it raises ``LimitReached`` with the registry's words filled in. ``set_limits`` and ``reset_limits`` are the one writer:
a dry run until told to apply, written whole under the store lock, with one line in the layer's ``limits-log.jsonl``.

There is no module-level mutable state; every call reads the settings and files afresh. Nothing here names an association, and
importing this module loads no profile (the data folder is read only when a value is asked for). The write path is a person's
act; no job, scheduled task, or MCP tool calls it.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KB = 1024
MB = 1024 * KB
GB = 1024 * MB
SOURCES = ("env", "instance", "community", "default")
SCOPES = ("instance", "community")
KINDS = ("size", "count", "rate", "time", "concurrency", "switch", "cost")
UNITS = ("bytes", "count", "per_hour", "seconds", "days", "cents", "switch")
RESTARTS = ("none", "next_job", "next_start")
FILE_VERSION = 1
LOG_NAME = "limits-log.jsonl"
FILE_NAME = "limits.json"
ROLE_INSTANCE = "instance operator"
ROLE_COMMUNITY = "community administrator"
OVERRIDE_ROLES = (ROLE_COMMUNITY, ROLE_INSTANCE)
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_UNLIMITED = frozenset({"inf", "+inf", "-inf", "infinity", "nan", "none", "null", "unlimited", "nolimit", "off-limit", ""})


class LimitRefused(ValueError):
    """A change to a limit that is not allowed. ``nearest`` is the closest allowed value, when there is one."""

    def __init__(self, message: str, nearest: Any = None, key: str = ""):
        super().__init__(message)
        self.nearest = nearest
        self.key = key

    def describe(self) -> str:
        """The refusal in words with the nearest allowed value, for a screen or a terminal."""
        if self.nearest in (None, "") or not self.key:
            return str(self)
        try:
            near = limit(self.key).format(self.nearest)
        except Exception:  # noqa: BLE001 - an unknown key has no unit to say it in
            return str(self)
        return f"{self}. The nearest allowed value is {near}."


class LimitReached(ValueError):
    """An act went past a limit. ``words`` is the registry's ``when_hit`` with the numbers filled in: what was not done, what a
    person can do, who can change it. A caller renders ``words`` and nothing else."""

    def __init__(self, key: str, amount: Any, limit: Any, source: str, words: str):
        super().__init__(words)
        self.key, self.amount, self.limit, self.source, self.words = key, amount, limit, source, words


# --- the record --------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Limit:
    key: str
    default: int | bool
    minimum: int | None
    maximum: int | None
    unit: str
    description: str
    kind: str = "size"
    direction: str = "either"            # either | lower_only
    scopes: tuple[str, ...] = SCOPES     # the layers that may set it; () is the code alone
    override: bool = False               # a person may pass it once, with a reason (phase 5; none built yet)
    override_max: int | None = None
    why: str = ""
    when_hit: str = ""
    applies_to: tuple[str, ...] = ()
    restart: str = "next_job"

    def __post_init__(self) -> None:
        """A row that cannot be enforced or explained does not load."""
        problems: list[str] = []
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", self.key):
            problems.append("the key is dotted lower case")
        if not self.why.strip():
            problems.append("no why")
        if not self.when_hit.strip():
            problems.append("no when_hit")
        if self.kind not in KINDS:
            problems.append(f"kind {self.kind!r}")
        if self.unit not in UNITS:
            problems.append(f"unit {self.unit!r}")
        if self.direction not in ("either", "lower_only"):
            problems.append(f"direction {self.direction!r}")
        if self.restart not in RESTARTS:
            problems.append(f"restart {self.restart!r}")
        if any(s not in SCOPES for s in self.scopes):
            problems.append("scopes are instance and community")
        if isinstance(self.default, bool) != (self.unit == "switch"):
            problems.append("a switch is a bool and nothing else is")
        if self.unit != "switch":
            if self.minimum is None or self.maximum is None:
                problems.append("a finite minimum and maximum")
            elif not (self.minimum <= self.default <= self.maximum):
                problems.append("a default inside its range")
            elif self.minimum < 0:
                problems.append("a negative minimum")
        if self.override and (self.override_max is None or (self.maximum is not None and self.override_max > self.maximum)):
            problems.append("an override_max at most the maximum")
        if not self.applies_to:
            problems.append("no applies_to")
        if problems:
            raise ValueError(f"limit {self.key} does not load: " + "; ".join(problems))

    @property
    def env_name(self) -> str:
        return "JASON_LIMIT_" + self.key.upper().replace(".", "_")

    @property
    def top(self) -> int | bool:
        """The highest value any layer may set: the maximum, or the default for a ``lower_only`` limit."""
        if self.unit == "switch":
            return self.default if self.direction == "lower_only" else True
        top = self.maximum
        return min(top, self.default) if self.direction == "lower_only" else top

    def parse(self, raw: Any) -> int | bool | None:
        """``raw`` as a typed value in the unit's words (``50MB``, ``30m``, ``on``, ``$12.50``); None when it cannot be read.
        Nothing parses to an unbounded value."""
        return parse_value(self, raw)

    def format(self, value: Any, *, up: bool = False) -> str:
        return format_value(self, value, up=up)

    def clamp(self, value: Any, top: Any = None) -> tuple[Any, bool]:
        """``value`` held to the range (and to ``top``, when lower): the held value and whether it moved."""
        top = self.top if top is None else top
        if self.unit == "switch":
            held = bool(value) and bool(top)
            return held, held != bool(value)
        held = max(self.minimum, min(top, int(value)))
        return held, held != int(value)

    def stricter(self, a: Any, b: Any) -> Any:
        """The value that does less: the smaller number, or the switch that is off."""
        return (bool(a) and bool(b)) if self.unit == "switch" else min(int(a), int(b))

    def effective(self, settings: Any = None, community: Any = None, *, data_folder: Any = None,
                  instance_file: Any = None) -> "Effective":
        """The value in force, with where it came from, the range, the ceiling, and who set it. ``settings`` is a
        ``jason.config.Settings`` (its ``env_path`` names the .env to read) or None; ``community`` is the profile when the caller
        has it (its ``limits()`` and its data folder); ``data_folder`` and ``instance_file`` name the files directly (tests)."""
        return _resolve(self, settings, community, data_folder, instance_file)


@dataclass(frozen=True)
class Effective:
    """A limit's value in force and where it came from."""

    key: str
    value: Any
    source: str                  # env | instance | community | default
    clamped: bool = False        # the winning setting was outside its range or ceiling and was held to it
    raw: str = ""                # what was set, when it was set
    note: str = ""               # in words: why the value is not what was written, or which file could not be read
    minimum: int | None = None
    maximum: int | None = None
    ceiling: Any = None          # the highest this community may set
    set: dict = field(default_factory=dict)       # by, at, reason, of the layer that won (a file's entry)
    layers: dict = field(default_factory=dict)    # each layer's value as read, for the one-limit view
    unreadable: tuple[str, ...] = ()              # the files that could not be read (the stricter value was taken)

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value, "source": self.source, "clamped": self.clamped, "note": self.note,
                "minimum": self.minimum, "maximum": self.maximum, "ceiling": self.ceiling, "set": dict(self.set),
                "unreadable": list(self.unreadable)}


# --- the registry ------------------------------------------------------------------------------------------------------------

LIMITS: tuple[Limit, ...] = (
    Limit("upload.max_bytes", 100 * MB, 1 * MB, 500 * MB, "bytes",
          "The largest file a person may upload from the computer (a record slot, or a key document). A larger file is put on "
          "Drive and picked there.",
          kind="size", why="A very large upload fills the disk and makes the reading of a scan very slow. The limit keeps one "
                           "file from using the machine for an hour.",
          when_hit="This file is {amount}; the limit is {limit}. Nothing was saved. You can split the scan into smaller files, "
                   "or put it on Drive and pick it there. Your community's administrator can change the limit, or allow this one "
                   "file up to {override_max} with a reason.",
          applies_to=("tasks.record_upload.check", "tasks.record_upload._bytes", "community.key_documents.max_upload_bytes"),
          restart="next_job", override=True, override_max=250 * MB),
    Limit("fetch.max_bytes", 100 * MB, 1 * MB, 500 * MB, "bytes",
          "The largest file jason fetches from Drive in one act (a stored PDF or image copied for the console, or a file read "
          "back for a record slot).",
          kind="size", why="A very large download fills the disk and keeps the machine busy for a long time. The limit keeps one "
                           "fetch from using the machine for an hour.",
          when_hit="This file is {amount}; the largest jason fetches is {limit}. Nothing was copied. Open it in Google, or ask "
                   "your community's administrator to raise the limit (the most allowed is {ceiling}).",
          applies_to=("tasks.drive_copies.export", "tasks.record_readback._problem"), restart="next_job"),
    Limit("split.auto_read", True, None, None, "switch",
          "After a person confirms a split, queue a read-back job for each new part file (on the same lane, in the confirming "
          "person's name). Off: each part is read by hand.",
          kind="switch", why="Reading a new part takes the machine's time; a community that reads each part by hand can turn the "
                             "automatic read off.",
          when_hit="The new files were not read automatically because the automatic read is off. Read each one by hand, or ask "
                   "your community's administrator to turn it on.",
          applies_to=("tasks.record_upload.split",), restart="next_job"),
    Limit("split.thumbnail_cache_bytes", 512 * MB, 32 * MB, 8 * GB, "bytes",
          "How much disk the splitter's page pictures (thumbnails) may use in all. The oldest are removed to make room.",
          kind="size", why="A large scan has thousands of pages and every page is drawn at three sizes; the pictures are a "
                           "convenience that can be redrawn, so they must never fill the disk.",
          when_hit="Page pictures are using their whole allowance ({limit}). The oldest were removed to make room; this file's "
                   "pictures are loading more slowly. Ask your community's administrator to raise the allowance (the most "
                   "allowed is {ceiling}).",
          applies_to=("tasks.split_thumbs.store",), restart="next_job"),
    Limit("split.max_pages", 3000, 50, 10000, "count",
          "The most pages a file may have for the splitter to open it.",
          kind="count", why="One draft of thousands of pages is already a great deal of review for a person, and drawing "
                            "every page keeps the machine busy.",
          when_hit="This file has {amount} pages; the splitter opens files of up to {limit}. Nothing was changed. Split the "
                   "scan into smaller files first, or ask your community's administrator to raise the limit (the most "
                   "allowed is {ceiling}).",
          applies_to=("tasks.split_session.open_session",), restart="next_job"),
    Limit("split.max_parts", 500, 2, 2000, "count",
          "The most files one split may write.",
          kind="count", why="A split that writes a thousand files at once is more likely a wrong mark than a real archive; "
                            "the limit makes a person look again.",
          when_hit="This split would write {amount} files; one split writes at most {limit}. Nothing was written. Merge some "
                   "segments, or ask your community's administrator to raise the limit (the most allowed is {ceiling}).",
          applies_to=("tasks.split_session.apply",), restart="next_job"),
    Limit("split.suggest_enabled", True, None, None, "switch",
          "Whether the splitter offers suggested first pages. Off: a person marks each first page; the editor still works.",
          kind="switch", why="Suggestions are guesses from the pages' shapes; a community that wants none can turn them "
                             "off without losing the splitter.",
          when_hit="Suggestions are off for this community. You can still mark each first page yourself.",
          applies_to=("tasks.split_session.suggest",), restart="next_job"),
    Limit("split.draft_days", 60, 7, 365, "days",
          "How many days a split draft is kept after its last change before it and its page pictures are removed.",
          kind="time", why="A draft that never ends is clutter and holds a copy of a large file; the original is never "
                           "removed.",
          when_hit="This draft was removed after {limit} without a change. Open the file again to start a new one.",
          applies_to=("tasks.split_session.sweep",), restart="next_job"),
)
_REGISTRY = LIMITS      # the older name


def all_limits() -> tuple[Limit, ...]:
    """The registry: every limit jason keeps, in a fixed order."""
    return LIMITS


def limit(key: str) -> Limit:
    found = next((l for l in LIMITS if l.key == key), None)
    if found is None:
        raise KeyError(f"no limit {key!r}; the limits are {', '.join(l.key for l in LIMITS)}")
    return found


def default(key: str) -> Any:
    return limit(key).default


# --- units: reading and saying a value ---------------------------------------------------------------------------------------

_SIZE = {"b": 1, "kb": KB, "k": KB, "mb": MB, "m": MB, "gb": GB, "g": GB}
_TIME_S = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_TIME_D = {"d": 1, "w": 7}


def parse_value(l: Limit, raw: Any) -> int | bool | None:
    if l.unit == "switch":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        return True if text in _TRUE else False if text in _FALSE else None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if math.isfinite(raw) and raw == int(raw) else None
    text = str(raw).strip().lower().replace("_", "").replace(",", "").replace(" ", "")
    if text in _UNLIMITED:
        return None
    try:
        if l.unit == "bytes":
            m = re.fullmatch(r"(\d+(?:\.\d+)?)(b|kb|k|mb|m|gb|g)?", text)
            return int(float(m.group(1)) * _SIZE[m.group(2) or "b"]) if m else None
        if l.unit in ("seconds", "days"):
            table = _TIME_S if l.unit == "seconds" else _TIME_D
            m = re.fullmatch(r"(\d+(?:\.\d+)?)([a-z])?", text)
            if not m or (m.group(2) and m.group(2) not in table):
                return None
            return int(float(m.group(1)) * table[m.group(2) or next(iter(table))])
        if l.unit == "cents":
            m = re.fullmatch(r"\$(\d+(?:\.\d{1,2})?)", text)
            return round(float(m.group(1)) * 100) if m else int(text) if re.fullmatch(r"\d+", text) else None
        return int(text) if re.fullmatch(r"\d+", text) else None
    except (ValueError, OverflowError):
        return None


def format_value(l: Limit, value: Any, *, up: bool = False) -> str:
    """A value in words with its unit. ``up`` rounds a size or a time up, for an amount that went over (a 1,048,581 byte file
    over a 1 MB limit reads "1.1 MB", never "1 MB")."""
    if l.unit == "switch":
        return "on" if value else "off"
    n = int(value)
    rounder = math.ceil if up else math.floor
    if l.unit == "bytes":
        for size, name in ((GB, "GB"), (MB, "MB"), (KB, "KB")):
            if n >= size:
                x = rounder(n / size * 10) / 10
                return f"{x:.0f} {name}" if x == int(x) else f"{x:.1f} {name}"
        return f"{n} bytes"
    if l.unit == "seconds":
        for size, name in ((86400, "day"), (3600, "hour"), (60, "minute")):
            if n >= size and n % size == 0:
                k = n // size
                return f"{k} {name}{'' if k == 1 else 's'}"
        return f"{n} second{'' if n == 1 else 's'}"
    if l.unit == "days":
        return f"{n} day{'' if n == 1 else 's'}"
    if l.unit == "cents":
        return f"${n // 100:,}.{n % 100:02d}"
    if l.unit == "per_hour":
        return f"{n} an hour"
    return f"{n:,}"


# --- the files ---------------------------------------------------------------------------------------------------------------

def instance_file() -> Path:
    """The instance limits file: ``JASON_LIMITS_FILE`` (environment, a project's .env, or the user config), else ``limits.json``
    beside the user config (``~/.jason``). Never relative to the working directory."""
    from jason import config

    named = config._env_value("JASON_LIMITS_FILE")
    return config._anchored(named) if named else config.user_config_path().parent / FILE_NAME


def community_folder(community: Any = None) -> Path:
    """The community's data folder: the profile's own when the caller passes one that names itself (``slug``), else the active
    community's. Raises ``CommunityNotChosen`` when none is chosen and none was given."""
    from jason import config

    slug = str(getattr(community, "slug", "") or "") if community is not None else ""
    return config.default_data_dir(slug)


def _folder_or_none(community: Any, data_folder: Any) -> Path | None:
    if data_folder is not None:
        return Path(data_folder)
    try:
        return community_folder(community)
    except Exception:  # noqa: BLE001 - no community chosen (or no profile): the instance and the defaults
        return None


def read_file(path: Path | None) -> tuple[dict[str, dict], str]:
    """A limits file's entries and its state: ``absent`` (no file, no layer), ``ok``, or ``unreadable`` (present but empty,
    cut off, not JSON, or not the shape; the entries are then {}). An unknown key is kept."""
    if path is None or not Path(path).is_file():
        return {}, "absent"
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = data["limits"]
        if not isinstance(data, dict) or not isinstance(entries, dict) or not all(isinstance(v, dict) for v in entries.values()):
            return {}, "unreadable"
        return entries, "ok"
    except (OSError, ValueError, KeyError, TypeError):
        return {}, "unreadable"


# --- the resolver ------------------------------------------------------------------------------------------------------------

def _from_profile(community: Any, key: str) -> Any:
    if community is None:
        return None
    try:
        held = community.limits()
    except Exception:  # noqa: BLE001 - a profile with nothing to say sets nothing
        return None
    return held.get(key) if isinstance(held, dict) else None


def _resolve(l: Limit, settings: Any, community: Any, data_folder: Any, inst_file: Any) -> Effective:
    from jason import config

    top = l.top
    layers: dict[str, Any] = {"default": l.default}
    notes: list[str] = []
    unreadable: list[str] = []

    # the instance file: its ceiling binds every community
    inst_path = Path(inst_file) if inst_file is not None else None
    if inst_path is None:
        try:
            inst_path = instance_file()
        except Exception:  # noqa: BLE001
            inst_path = None
    inst_entries, inst_state = read_file(inst_path)
    inst_entry = inst_entries.get(l.key) if "instance" in l.scopes else None
    ceiling = top
    inst_value = None
    if inst_state == "unreadable":
        unreadable.append("the instance limits file")
        ceiling = l.stricter(top, l.default)
    elif isinstance(inst_entry, dict):
        inst_value = l.parse(inst_entry.get("value"))
        if inst_value is None:
            unreadable.append(f"the instance setting for {l.key}")
            ceiling = l.stricter(top, l.default)
        else:
            raw_ceiling = l.parse(inst_entry["ceiling"]) if "ceiling" in inst_entry else None
            held = l.clamp(raw_ceiling if raw_ceiling is not None else inst_value)[0]
            ceiling = l.stricter(top, held)

    value: Any = l.default
    source, raw, clamped, who = "default", "", False, {}

    def apply(src: str, got_raw: Any, cap: Any, meta: dict | None = None, ceiling_layer: bool = False) -> None:
        nonlocal value, source, raw, clamped, who
        parsed = l.parse(got_raw)
        if parsed is None:
            notes.append(f"the {src} setting {got_raw!r} could not be read and was skipped")
            return
        held, moved = l.clamp(parsed, cap)
        layers[src] = held
        value, source, raw, clamped, who = held, src, str(got_raw), moved, dict(meta or {})
        if moved and ceiling_layer and cap != top:
            notes.append(f"set to {l.format(parsed)} here; the operator's limit is {l.format(cap)}")
        elif moved:
            notes.append(f"{l.format(parsed) if l.unit != 'switch' else 'on'} is outside the range allowed; held to {l.format(held)}")

    comm_ok = "community" in l.scopes
    inst_ok = "instance" in l.scopes
    if comm_ok:
        got = _from_profile(community, l.key)
        if got not in ("", None):
            apply("community", got, ceiling, ceiling_layer=True)
    if inst_ok:
        env_file: Path | None = getattr(settings, "env_path", None)
        process = os.environ.get(l.env_name, "").strip()
        from_file = "" if process else config._env_value(l.env_name, env_file)
        if from_file:
            apply("instance", from_file, top)
        if process:
            apply("env", process, top)
        if inst_value is not None:
            apply("instance", inst_value, top, {k: inst_entry.get(k, "") for k in ("by", "at", "reason")})
    if inst_value is not None:
        layers["instance_ceiling"] = ceiling

    comm_path = _folder_or_none(community, data_folder)
    comm_entries, comm_state = read_file(comm_path / FILE_NAME if comm_path is not None else None)
    if comm_state == "unreadable":
        unreadable.append("this community's limits file")
    elif comm_ok and isinstance(comm_entries.get(l.key), dict):
        entry = comm_entries[l.key]
        if l.parse(entry.get("value")) is None:
            unreadable.append(f"this community's setting for {l.key}")
        else:
            apply("community", entry["value"], ceiling, {k: entry.get(k, "") for k in ("by", "at", "reason")}, ceiling_layer=True)

    if unreadable:
        strict = l.stricter(value, l.default)
        if strict != value:
            value, source, clamped = strict, "default", False
        notes.append("could not read " + ", ".join(unreadable) + "; the stricter of the values that could be read is used")
    return Effective(l.key, value, source, clamped=clamped, raw=raw, note="; ".join(notes), minimum=l.minimum, maximum=l.maximum,
                     ceiling=ceiling, set=who if source != "default" else {}, layers=layers, unreadable=tuple(unreadable))


def effective(key: str, settings: Any = None, community: Any = None, **where: Any) -> Effective:
    return limit(key).effective(settings, community, **where)


def value(key: str, *, settings: Any = None, community: Any = None, **where: Any) -> Any:
    """The value in force for ``key`` (see ``Limit.effective``)."""
    return limit(key).effective(settings, community, **where).value


def listing(settings: Any = None, community: Any = None, **where: Any) -> list[dict[str, Any]]:
    """Every limit with its value in force and source, as ``jason limits --json`` prints it. Read-only."""
    out = []
    for l in LIMITS:
        e = l.effective(settings, community, **where)
        out.append({**e.as_dict(), "default": l.default, "unit": l.unit, "kind": l.kind, "direction": l.direction,
                    "scopes": list(l.scopes), "env": l.env_name, "description": l.description, "why": l.why, "when_hit": l.when_hit,
                    "restart": l.restart, "applies_to": list(l.applies_to), "words": l.format(e.value)})
    return out


def instance_listing(**where: Any) -> list[dict[str, Any]]:
    """The instance layer alone: each key's instance value and ceiling, who set them, and whether the file could be read.
    Needs no community."""
    path = Path(where["instance_file"]) if where.get("instance_file") is not None else instance_file()
    entries, state = read_file(path)
    out = []
    for l in LIMITS:
        entry = entries.get(l.key) if isinstance(entries.get(l.key), dict) else {}
        out.append({"key": l.key, "unit": l.unit, "default": l.default, "minimum": l.minimum, "maximum": l.maximum,
                    "value": entry.get("value"), "ceiling": entry.get("ceiling"), "by": entry.get("by", ""),
                    "at": entry.get("at", ""), "reason": entry.get("reason", ""), "file": state,
                    "instance_may_set": "instance" in l.scopes})
    return out


# --- enforcement -------------------------------------------------------------------------------------------------------------

def refusal(key: str, amount: Any, limit_value: Any, *, source: str = "default", ceiling: Any = None) -> LimitReached:
    """The ``LimitReached`` for ``amount`` over ``limit_value`` in the registry's words. For a caller whose cap is a derived
    reading (the smaller of two limits) and has already compared; ``check`` is the one for a direct comparison."""
    l = limit(key)
    words = l.when_hit.format_map(_Words(amount=l.format(amount, up=True), limit=l.format(limit_value),
                                         ceiling=l.format(ceiling if ceiling is not None else l.top), unit=l.unit,
                                         override_max=l.format(l.override_max) if l.override_max is not None else ""))
    return LimitReached(key, amount, limit_value, source, words)


class _Words(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass(frozen=True)
class Override:
    """One act's request to pass a limit once (docs/instance-limits.md, the per-act override). It is the act's, never a setting:
    ``check`` honours it only for a limit whose row allows it, up to ``override_max``, with a reason and a person in the role that
    may confirm it, and writes one ``override`` line to the community's trail. ``allowed`` is the most this one act may carry."""

    key: str
    allowed: Any
    reason: str
    by: str
    role: str = ROLE_COMMUNITY
    via: str = "cli"
    what: str = "an act"             # the kind of act ("an upload"), never the thing: no file name, no unit, no owner


def override_from(act: Any) -> "Override | None":
    """The override an act carries: an ``Override``, a dict with ``limit_override`` (the act's record), or None."""
    if act is None:
        return None
    if isinstance(act, Override):
        return act
    held = act.get("limit_override") if isinstance(act, dict) else getattr(act, "limit_override", None)
    if isinstance(held, Override):
        return held
    if isinstance(held, dict):
        fields = {k: held[k] for k in ("key", "allowed", "reason", "by", "role", "via", "what") if k in held}
        try:
            return Override(**fields)
        except TypeError:
            return None
    return None


def parse_override(pair: str, *, reason: str, by: str, role: str = ROLE_COMMUNITY, via: str = "cli", what: str = "an act") -> Override:
    """``KEY=VALUE`` (``upload.max_bytes=200MB``) as an ``Override``. Raises ``LimitRefused`` for a pair that is not one."""
    key, eq, raw = str(pair or "").partition("=")
    key = key.strip()
    if not eq or not key or not raw.strip():
        raise LimitRefused("an override is KEY=VALUE, for example upload.max_bytes=200MB")
    l = limit(key)
    parsed = l.parse(raw.strip())
    if parsed is None or l.unit == "switch":
        raise LimitRefused(f"{key}: {raw.strip()!r} is not a size or count to allow once; a switch has no override", None, key)
    return Override(key, parsed, reason, by, role, via, what)


def _validated_override(l: Limit, ov: Override) -> int:
    """The most ``ov`` lets one act carry, or ``LimitRefused`` in words (with the nearest allowed value)."""
    if not l.override or l.override_max is None:
        raise LimitRefused(f"{l.key} cannot be passed, even once: its row allows no override", None, l.key)
    if not str(ov.reason or "").strip():
        raise LimitRefused(f"{l.key}: allowing it once needs a reason", None, l.key)
    if not str(ov.by or "").strip():
        raise LimitRefused(f"{l.key}: allowing it once needs the name of the person who allows it", None, l.key)
    if ov.role not in OVERRIDE_ROLES:
        raise LimitRefused(f"{l.key}: only a community administrator may allow a limit to be passed once", None, l.key)
    allowed = l.parse(ov.allowed)
    if allowed is None or isinstance(allowed, bool):
        raise LimitRefused(f"{l.key}: {ov.allowed!r} is not a value to allow once", l.override_max, l.key)
    if allowed > l.override_max:
        raise LimitRefused(f"{l.key}: {l.format(allowed)} is more than may be allowed once, {l.format(l.override_max)}",
                           l.override_max, l.key)
    return int(allowed)


def override_cap(key: str, act: Any, base: int) -> int:
    """The largest amount ``act`` may carry for ``key``: ``base`` (the limit in force), or the act's validated override when that is
    higher. Reads only: nothing is logged here (``check`` logs the override when it is used). Raises ``LimitRefused`` for an
    override the row does not allow, or one without a reason, a name, or the role."""
    l = limit(key)
    ov = override_from(act)
    if ov is None or ov.key != key:
        return int(base)
    return max(int(base), _validated_override(l, ov))


def _trail_scope(source: str) -> str:
    return "community" if source == "community" else "instance"


def _try_log(scope: str, line: dict, *, community: Any = None, data_folder: Any = None, instance_file_: Any = None) -> bool:
    """Append one line to a layer's trail; False when it could not be written (a read never fails because of it)."""
    try:
        _, log = _paths(scope, community, data_folder, instance_file_)
        _append_log(log, [line])
        return True
    except Exception:  # noqa: BLE001 - no community chosen, a folder that cannot be written
        return False


def _note_clamp(l: Limit, eff: Effective, community: Any, where: dict) -> None:
    """A read found the winning setting outside its range or ceiling: one ``clamped`` line in the layer's trail, once for each
    setting (the same key and raw value is not written twice in a row). Best effort: the read does not depend on it."""
    scope = _trail_scope(eff.source)
    kw = {"community": community, "data_folder": where.get("data_folder"), "instance_file": where.get("instance_file")}
    try:
        history = read_log(scope, key=l.key, **kw)
    except Exception:  # noqa: BLE001 - no community chosen: nowhere to note it
        return
    mine = [r for r in history if r.get("kind") == "clamped"]
    if mine and mine[-1].get("from") == eff.raw and mine[-1].get("to") == eff.value:
        return
    _try_log(scope, {"at": _now(), "kind": "clamped", "scope": scope, "key": l.key, "from": eff.raw, "to": eff.value,
                     "from_source": eff.source, "unit": l.unit, "reason": eff.note, "by": "jason", "via": "read", "who": "", "role": ""},
             community=community, data_folder=where.get("data_folder"), instance_file_=where.get("instance_file"))


def check(key: str, amount: Any, *, act: Any = None, community: Any = None, settings: Any = None, record: bool = True,
          **where: Any) -> Effective:
    """The one call at an enforcement point. Returns the limit in force when ``amount`` is within it; raises ``LimitReached``
    (a ValueError) with the words when it is over, or when a switch is off and ``amount`` is truthy.

    ``act`` may carry an ``Override`` (see there): when ``amount`` is over the limit, an override the row allows, up to its
    ``override_max``, lets this act through once, and ``check`` writes one ``override`` line to the community's trail (``record``
    False, for a dry run, writes none). An override the row does not allow, or one without a reason, raises ``LimitRefused``;
    an amount past even the override raises ``LimitReached``. The override is never stored as a setting. A stored value that was
    held to its range is noted once in the trail as ``clamped``."""
    l = limit(key)
    eff = l.effective(settings, community, **where)
    if record and eff.clamped:
        _note_clamp(l, eff, community, where)
    over = (not eff.value and bool(amount)) if l.unit == "switch" else int(amount) > int(eff.value)
    if not over:
        return eff
    ov = override_from(act)
    if ov is not None and ov.key == key and l.unit != "switch":
        allowed = _validated_override(l, ov)
        if int(amount) > allowed:
            raise refusal(key, amount, max(allowed, int(eff.value)), source="override", ceiling=eff.ceiling)
        if record:
            line = {"at": _now(), "kind": "override", "scope": "community", "key": key, "from": eff.value, "from_source": eff.source,
                    "to": allowed, "amount": int(amount), "unit": l.unit, "reason": str(ov.reason).strip(), "by": str(ov.by).strip(),
                    "via": ov.via, "who": _who(), "role": ov.role, "what": ov.what}
            if not _try_log("community", line, community=community, data_folder=where.get("data_folder")):
                raise LimitRefused(f"{l.key}: the override could not be recorded in this community's trail, so it was not allowed")
        return eff
    raise refusal(key, amount, eff.value, source=eff.source, ceiling=eff.ceiling)


def megabytes(n: int) -> int:
    return n // MB


# --- the one writer ----------------------------------------------------------------------------------------------------------

def _paths(scope: str, community: Any, data_folder: Any, inst_file: Any) -> tuple[Path, Path]:
    if scope == "instance":
        path = Path(inst_file) if inst_file is not None else instance_file()
    else:
        path = (Path(data_folder) if data_folder is not None else community_folder(community)) / FILE_NAME
    return path, path.with_name(LOG_NAME)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _who() -> str:
    try:
        import getpass

        return "claim: " + getpass.getuser()
    except Exception:  # noqa: BLE001
        return "claim"


def _append_log(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_log(scope: str, *, key: str = "", community: Any = None, data_folder: Any = None, instance_file: Any = None,
             limit_lines: int = 0) -> list[dict]:
    """A layer's trail, oldest first (the last ``limit_lines`` when given). A line that cannot be read is skipped."""
    _, log = _paths(scope, community, data_folder, instance_file)
    out: list[dict] = []
    if log.is_file():
        for text in log.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(text)
            except ValueError:
                continue
            if isinstance(row, dict) and (not key or row.get("key") == key):
                out.append(row)
    return out[-limit_lines:] if limit_lines else out


def _validate_set(l: Limit, scope: str, raw: Any, ceiling_raw: Any, inst_ceiling: Any) -> tuple[Any, Any]:
    if scope not in l.scopes:
        who = "only the code sets it" if not l.scopes else f"only the {' and '.join(l.scopes)} layer sets it"
        raise LimitRefused(f"{l.key} cannot be set in the {scope} layer: {who}", l.default)
    parsed = l.parse(raw)
    if parsed is None:
        raise LimitRefused(f"{l.key}: {raw!r} is not a value in {l.unit if l.unit != 'switch' else 'on or off'}; there is no "
                           "unlimited value", None)
    if l.unit != "switch":
        if parsed < l.minimum:
            raise LimitRefused(f"{l.key}: {l.format(parsed)} is below the lowest allowed, {l.format(l.minimum)}", l.minimum)
        if parsed > l.top:
            why = "the most jason will ever do in one act" if l.direction == "lower_only" else "the highest allowed"
            raise LimitRefused(f"{l.key}: {l.format(parsed)} is above {l.format(l.top)}, {why}", l.top)
    elif parsed and not l.top:
        raise LimitRefused(f"{l.key} cannot be turned on; the code keeps it off", False)
    if scope == "community" and parsed is not None:
        held = l.clamp(parsed, inst_ceiling)[0]
        if held != parsed:
            raise LimitRefused(f"{l.key}: {l.format(parsed)} is above the operator's limit of {l.format(inst_ceiling)}", inst_ceiling)
    new_ceiling = None
    if ceiling_raw not in (None, ""):
        if scope != "instance":
            raise LimitRefused("a ceiling is set only in the instance layer", None)
        new_ceiling = l.parse(ceiling_raw)
        if new_ceiling is None or l.clamp(new_ceiling)[0] != new_ceiling:
            raise LimitRefused(f"{l.key}: the ceiling {ceiling_raw!r} is outside the range", l.top)
        if l.stricter(parsed, new_ceiling) != parsed:
            raise LimitRefused(f"{l.key}: the value {l.format(parsed)} is above its own ceiling {l.format(new_ceiling)}", new_ceiling)
    return parsed, new_ceiling


def _effects(l: Limit, scope: str, before: Any, after: Any) -> str:
    """What a change does, in words: it applies to new acts and removes or hides nothing."""
    when = {"none": "at once", "next_job": "from the next job", "next_start": "after the next start"}[l.restart]
    return (f"takes effect {when}; it applies to new acts only and never removes or hides what already exists"
            + ("; the operator's ceiling still binds every community" if scope == "instance" else ""))


ROLE_SCOPES = {ROLE_INSTANCE: "instance", ROLE_COMMUNITY: "community"}      # the layer each role may change


def _plan(scope: str, keys: dict[str, Any], *, reset: bool, ceiling: Any, reason: str, by: str, role: str | None, community: Any,
          where: dict, settings: Any) -> list[dict]:
    if scope not in SCOPES:
        raise LimitRefused(f"the scope is instance or community, not {scope!r}")
    if role is not None and ROLE_SCOPES.get(role) != scope:
        mine = ROLE_SCOPES.get(role)
        raise LimitRefused(f"a {role} changes the {mine} layer only; the {scope} layer is changed by the "
                           f"{ROLE_INSTANCE if scope == 'instance' else ROLE_COMMUNITY}" if mine else
                           f"{role!r} may not change a limit; a limit is changed by an instance operator or a community administrator")
    if not str(reason or "").strip() or not str(by or "").strip():
        raise LimitRefused("a reason and a name are required")
    if ceiling not in (None, "") and len(keys) != 1:
        raise LimitRefused("a ceiling goes with exactly one limit")
    plan: list[dict] = []
    # a community change is held to the instance ceiling as it stands now
    for key, raw in keys.items():
        l = limit(key)
        before = l.effective(settings, community, **where)
        if reset:
            if scope not in l.scopes:
                raise LimitRefused(f"{l.key} is not set in the {scope} layer: nothing to reset", None, key)
            plan.append({"limit": l, "key": key, "from": before.value, "from_source": before.source, "remove": True})
            continue
        inst_ceiling = before.ceiling if scope == "community" else l.top
        try:
            parsed, new_ceiling = _validate_set(l, scope, raw, ceiling, inst_ceiling)
        except LimitRefused as exc:
            exc.key = exc.key or key
            raise
        plan.append({"limit": l, "key": key, "from": before.value, "from_source": before.source, "to": parsed, "ceiling": new_ceiling})
    return plan


def _change(scope: str, keys: dict[str, Any], *, reset: bool, ceiling: Any, reason: str, by: str, via: str, community: Any,
            data_folder: Any, instance_file_: Any, dry_run: bool, settings: Any, role: str | None = None,
            who: str | None = None) -> dict[str, Any]:
    where = {"data_folder": data_folder, "instance_file": instance_file_}
    try:
        plan = _plan(scope, keys, reset=reset, ceiling=ceiling, reason=reason, by=by, role=role, community=community, where=where,
                     settings=settings)
    except LimitRefused as exc:
        # a refused change that was meant to be applied leaves a line saying so and why; a dry run writes nothing
        if not dry_run and scope in SCOPES:
            _try_log(scope, {"at": _now(), "kind": "refused", "scope": scope, "key": exc.key or ",".join(keys), "from": None,
                             "to": None if reset else (next(iter(keys.values())) if len(keys) == 1 else None), "unit": "",
                             "reason": str(reason or "").strip(), "refusal": str(exc), "by": str(by or "").strip() or "unknown",
                             "via": via, "who": who or _who(), "role": role or (ROLE_INSTANCE if scope == "instance" else ROLE_COMMUNITY)},
                     community=community, data_folder=data_folder, instance_file_=instance_file_)
        raise
    path, log = _paths(scope, community, data_folder, instance_file_)
    held_role = role or (ROLE_INSTANCE if scope == "instance" else ROLE_COMMUNITY)
    held_who = who or _who()

    def doc() -> dict[str, Any]:
        return {"dryRun": dry_run, "scope": scope, "path": str(path), "log": str(log), "reason": reason, "by": by,
                "changes": [{"key": p["key"], "from": p["from"], "from_source": p["from_source"],
                             "to": None if p.get("remove") else p["to"], "ceiling": p.get("ceiling"), "unit": p["limit"].unit,
                             "words": (f"{p['limit'].key}: {p['limit'].format(p['from'])} ({p['from_source']}) -> "
                                       + ("back to the layer above" if p.get("remove") else p["limit"].format(p["to"]))
                                       + f" ({scope}); " + _effects(p["limit"], scope, p["from"], p.get("to")))}
                            for p in plan]}

    if dry_run:
        return doc()
    import hashlib

    from jason.locks import Resource, hold

    with hold(Resource.STORE, "limits-" + hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12], timeout=30,
              purpose=f"limits {scope}"):
        entries, state = read_file(path)
        if state == "unreadable":
            raise LimitRefused(f"{path.name} in the {scope} layer cannot be read; fix or move it first. Nothing was changed")
        lines = []
        at = _now()
        for p in plan:
            if p.get("remove"):
                entries.pop(p["key"], None)
            else:
                entry = {"value": p["to"], "by": by, "at": at, "reason": reason}
                if p.get("ceiling") is not None:
                    entry["ceiling"] = p["ceiling"]
                entries[p["key"]] = entry
        # the file and its line are one write: the file is staged, the line appended, then the file renamed into place
        staged = _stage(path, entries)
        try:
            for p in plan:
                lines.append({"at": at, "kind": "reset" if p.get("remove") else "set", "scope": scope, "key": p["key"],
                              "from": p["from"], "from_source": p["from_source"], "to": None if p.get("remove") else p["to"],
                              "unit": p["limit"].unit, "reason": reason, "by": by, "via": via, "who": held_who,
                              "role": held_role})
                if p.get("ceiling") is not None:
                    lines[-1]["ceiling"] = p["ceiling"]
            _append_log(log, lines)
            os.replace(staged, path)
        except BaseException:
            try:
                os.unlink(staged)
            except OSError:
                pass
            raise
    # after the write, say what the value in force became
    out = doc()
    for c in out["changes"]:
        c["now"] = limit(c["key"]).effective(settings, community, **where).value
    return out


def _stage(path: Path, entries: dict[str, dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".limits-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"version": FILE_VERSION, "limits": entries}, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return tmp


def set_limits(changes: dict[str, Any], *, scope: str, reason: str, by: str, ceiling: Any = None, via: str = "cli",
               dry_run: bool = True, community: Any = None, data_folder: Any = None, instance_file: Any = None,
               settings: Any = None, role: str | None = None, who: str | None = None) -> dict[str, Any]:
    """Set one or more limits in one layer, in one write with one reason. A dry run (the default) says what would change and
    writes nothing. Raises ``LimitRefused`` (nothing is written) for an unknown key, a layer that may not set it, a value
    out of range, above the operator's ceiling or a ``lower_only`` default, or a missing reason or name. ``role`` (``instance
    operator`` or ``community administrator``) is the role the person acts in: it may change only its own layer, and it is the
    ``role`` of the trail line; ``who`` is the signed-in account's subject (the console), else the claim of the terminal's user.
    A refused change that was meant to be applied leaves a ``refused`` line."""
    for key in changes:
        limit(key)
    return _change(scope, dict(changes), reset=False, ceiling=ceiling, reason=reason, by=by, via=via, community=community,
                   data_folder=data_folder, instance_file_=instance_file, dry_run=dry_run, settings=settings, role=role, who=who)


def reset_limits(keys: list[str], *, scope: str, reason: str, by: str, via: str = "cli", dry_run: bool = True,
                 community: Any = None, data_folder: Any = None, instance_file: Any = None, settings: Any = None,
                 role: str | None = None, who: str | None = None) -> dict[str, Any]:
    """Remove the layer's value for each key, so the layer above (or the code's default) is in force again. It never writes the
    built-in value as if the layer chose it."""
    for key in keys:
        limit(key)
    return _change(scope, {k: None for k in keys}, reset=True, ceiling=None, reason=reason, by=by, via=via, community=community,
                   data_folder=data_folder, instance_file_=instance_file, dry_run=dry_run, settings=settings, role=role, who=who)


__all__ = ["Effective", "FILE_NAME", "LIMITS", "LOG_NAME", "Limit", "LimitReached", "LimitRefused", "SOURCES", "all_limits",
           "check", "community_folder", "default", "effective", "format_value", "instance_file", "instance_listing", "limit",
           "listing", "megabytes", "parse_value", "read_file", "read_log", "refusal", "reset_limits", "set_limits", "value",
           "OVERRIDE_ROLES", "Override", "ROLE_COMMUNITY", "ROLE_INSTANCE", "override_cap", "override_from", "parse_override"]
