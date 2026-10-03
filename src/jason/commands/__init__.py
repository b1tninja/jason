"""CLI commands that live in their own modules.

Each module here defines ``register(sub, add_common, agent_factory)``: it adds its subparser to ``sub``, calls
``add_common(parser)`` for ``--env`` and ``--interactive``, and sets ``func``. ``agent_factory(args)`` gives the ``Jason``
agent (a context manager). A module is listed in ``MODULES`` to be registered; one that fails to import is skipped with a
note on stderr, so a half-built command never breaks the others.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

MODULES: tuple[str, ...] = (
    "calendar",
    "drive_activity",
    "drafts_forms",
    "photos",
    "drive_labels",
    "legal_hold",
    "cross_checks",
    "paid_approved",
    "minutes_privacy",
    "registers",
    "rule_change",
    "broadcast",
    "review",
    "packet",
    "statute_align",
    "delivery",
    "owner_info",
    "qr",
    "rentals",
    "batches",
    "form_fuzz",
    "form_lab",
    "leases",
    "signatures",
    "report",
    "lessons",
    "notices",
    "living",
    "section_refs",
    "cite",
    "intake",
    "schedule",
    "schedule_evidence",
    "record_stages",
    "manual",
    "respond",
    "attention",
)


def register_all(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    for name in MODULES:
        try:
            module = importlib.import_module(f"jason.commands.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"jason.commands.{name}":
                continue                           # not built yet
            print(f"jason: command module {name} failed to import: {exc}", file=sys.stderr)
            continue
        except Exception as exc:  # a broken module must not break the other commands
            print(f"jason: command module {name} failed to import: {exc}", file=sys.stderr)
            continue
        module.register(sub, add_common, agent_factory)


__all__ = ["MODULES", "register_all"]
