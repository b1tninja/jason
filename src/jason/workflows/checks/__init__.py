"""The read-only checks a definition's ``check`` step may name, one module per family (``members``, ``board``, ``money``,
``records``, ``property``, ``platform``). Each module registers its reads into ``jason.workflows.readers.CHECKS`` when it is
imported, with the ``check`` decorator below; ``load_all`` imports the modules that exist (a family not written yet is
skipped, a module that fails to import raises). A check takes the readers, the run's view, and the item, and returns a
``CheckResult``; it reads stores on disk and writes nothing, calls no outside system, and loads no profile except through the
readers' own lazy ``community()``. ``definitions_general.register_general`` calls ``load_all`` before it registers a
definition, so a step may name any of them."""

from __future__ import annotations

from importlib import import_module
from typing import Callable

FAMILIES: tuple[str, ...] = ("members", "board", "money", "records", "property", "platform")


def check(name: str) -> Callable[[Callable], Callable]:
    """Register ``fn`` as the read ``name`` (``named_check(name)`` finds it). A name already taken is an error: two reads
    never share a name."""

    def register(fn: Callable) -> Callable:
        from jason.workflows import readers

        if name in readers.CHECKS and readers.CHECKS[name] is not fn:
            raise ValueError(f"the read {name!r} is already registered")
        readers.CHECKS[name] = fn
        return fn

    return register


def load_all() -> tuple[str, ...]:
    loaded: list[str] = []
    for family in FAMILIES:
        try:
            import_module(f"jason.workflows.checks.{family}")
        except ModuleNotFoundError as exc:
            if exc.name == f"jason.workflows.checks.{family}":
                continue
            raise
        loaded.append(family)
    return tuple(loaded)


__all__ = ["FAMILIES", "check", "load_all"]
