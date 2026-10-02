"""Helpers the command modules share: where the data lives, a day from the command line, and JSON for dates and enums.

Not a command (``MODULES`` does not list it). A command module imports what it needs::

    from jason.commands._shared import data_dir, day, to_json

    root = data_dir(args)               # the folder that holds payhoa.db, ownership.db, and every store
    on = day(args.on)                   # "2026-10-20" -> date, "" or None -> None
    print(to_json(rows))                # dates as ISO, enums as their value, dataclasses as dicts
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def data_dir(args: argparse.Namespace | None = None) -> Path:
    """The data folder for ``args.env`` (the folder of the PayHOA catalog; ``ownership.db`` and the stores sit beside
    it)."""
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).payhoa_catalog.parent


def day(value: str | None) -> date | None:
    """A YYYY-MM-DD argument as a date; empty is None. A malformed one raises ``ValueError``."""
    return date.fromisoformat(value) if value else None


def json_default(value: Any) -> Any:
    """``json.dumps(default=...)``: a date or datetime as ISO, an enum as its value, a path as text, a dataclass as a
    dict, a set or tuple as a list."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"{type(value).__name__} is not JSON")


def to_json(value: Any, *, indent: int | None = 1) -> str:
    return json.dumps(value, indent=indent, default=json_default)


__all__ = ["data_dir", "day", "json_default", "to_json"]
