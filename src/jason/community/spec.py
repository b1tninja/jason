"""Load the `mystique` package. The facts are classes in that package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from jason.community.base import Community, TransactionRule
from jason.community.symbols import Utility

_PACKAGE = "jason_mystique"


def find_spec_root(marker: str = "mystique") -> Path:
    """Walk upward from this file to `marker/__init__.py`."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / marker
        if (candidate / "__init__.py").is_file():
            return candidate
    raise FileNotFoundError(f"no {marker}/__init__.py above {here}")


def spec_module(name: str):
    """One module of the specification package (``templates``, ``forms``, ...), loading the package first. The package is
    imported as ``jason_mystique``, so ``from mystique import ...`` works only when the working directory is the repo."""
    load_mystique()
    return importlib.import_module(f"{_PACKAGE}.{name}")


def load_mystique() -> Community:
    """Import `mystique` and return one `Mystique` instance."""
    root = find_spec_root()
    if _PACKAGE in sys.modules:
        return sys.modules[_PACKAGE].Mystique()
    spec = importlib.util.spec_from_file_location(
        _PACKAGE,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {root}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE] = module
    spec.loader.exec_module(module)
    return module.Mystique()


def first_utility(
    tx: dict[str, Any],
    rules: tuple[TransactionRule, ...] | list[TransactionRule],
) -> Utility | None:
    """First listed rule that matches and is not blocked by an earlier hit."""
    hits = [rule.utility for rule in rules if rule.matches(tx)]
    for rule in rules:
        if rule.utility not in hits:
            continue
        if any(block in hits for block in rule.blocked_by):
            continue
        return rule.utility
    return None
