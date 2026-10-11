"""The general workflow definitions, one module per family (docs/workflows/README.md): ``members``, ``board``, ``money``,
``records``, ``property``, and ``platform``. Each module defines ``BUILDERS``, a tuple of functions that return a ``Workflow``,
and may add to ``jason.workflows.readers.CHECKS`` and ``JOBS`` (read-only checks and the job names its steps use) when it is
imported. ``all_builders`` imports the modules that exist; a family not written yet is skipped, and a module that fails to
import raises, so a broken definition is never silently dropped. Importing this package registers nothing:
``definitions_general.register_general`` does, when ``jason workflow`` lists or starts a run."""

from __future__ import annotations

from importlib import import_module
from typing import Callable

FAMILIES: tuple[str, ...] = ("members", "board", "money", "records", "property", "platform")


def all_builders() -> tuple[Callable[[], object], ...]:
    out: list[Callable[[], object]] = []
    for name in FAMILIES:
        try:
            module = import_module(f"jason.workflows.defs.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"jason.workflows.defs.{name}":
                continue                              # not written yet
            raise
        out.extend(getattr(module, "BUILDERS", ()))
    return tuple(out)


__all__ = ["FAMILIES", "all_builders"]
