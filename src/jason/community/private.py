"""The community's private facts, kept apart from its specification so the specification can be shared.

The specification (``mystique/``) holds rules: patterns, ranges, kinds, the law. A private fact (an account number, a
person's name or address, a settlement figure, counsel's direct contact) lives in ``<data>/spec/<name>.json``, which
is never checked in. ``facts(name)`` reads one; a missing file is an empty answer, so a checkout without the private
data still runs, with those facts absent. The data folder is ``JASON_SPEC_DIR`` when set, else ``data/spec`` beside
the working directory, else beside this checkout.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def spec_dir() -> Path:
    env = os.environ.get("JASON_SPEC_DIR")
    if env:
        return Path(env)
    here = Path("data") / "spec"
    if here.is_dir():
        return here
    return Path(__file__).resolve().parents[3] / "data" / "spec"


@lru_cache(maxsize=None)
def _read(path: str, mtime: float) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def facts(name: str, default: Any = None) -> Any:
    """``<spec dir>/<name>.json``, or ``default`` (an empty dict when not given) when there is none."""
    path = spec_dir() / f"{name}.json"
    if not path.is_file():
        return {} if default is None else default
    return _read(str(path), path.stat().st_mtime)


def write(name: str, value: Any) -> Path:
    """Save a private fact file (used when moving facts out of the specification)."""
    path = spec_dir() / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


__all__ = ["facts", "spec_dir", "write"]
