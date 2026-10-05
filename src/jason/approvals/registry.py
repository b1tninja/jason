"""The action kinds: each write jason can plan for a person's approval is a row, not a branch.

A kind declares how to plan (a read-only function returning the items and the live state they rest on), how to apply
the approved items, its approver rule, and its cost. Adding a ``--yes`` path to the approvals means adding a row with
a planner and an applier that call the task functions the CLI already calls (docs/console/approval-workflow.md).

``planner(live, scope) -> engine.Planned`` reads and never writes. ``applier(live, planned, items, recorder)``
performs only ``items`` (the approved ones, from the re-plan) and reports each one through ``recorder``.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from jason.locks import Resource


class Risk(Enum):
    R0 = "local"
    R1 = "private outside jason"
    R2 = "member-facing record"
    R3 = "irreversible, costly, or legal"


class Approver(Enum):
    ONE_PERSON = "one person"        # one named person decides and submits; a high-stakes item still needs a second
    TWO_PERSON = "two person"        # a second, distinct person signs the same fingerprint before any apply


@dataclass(frozen=True)
class ActionKind:
    key: str                          # "owner-info-tags"
    title: str
    cli: str                          # the command it stands beside
    system: str                       # "payhoa", "google", "zoom", "local": what the live read needs
    resource: Resource                # the lock held during apply
    risk: Risk
    approver: Approver
    reversible: str
    planner: str | Callable[..., Any]  # dotted "module:function", or the function
    applier: str | Callable[..., Any]
    cost: str = ""                    # how its cost is shown; "" when it has none
    clock: str = ""                   # the clock it serves
    rule: str = ""                    # the rule that authorizes it, where one does
    max_age_hours: int = 24           # an approval older than this is planned again before apply
    default_scope: dict[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()

    @property
    def has_cost(self) -> bool:
        return bool(self.cost)

    def plan(self, live: Any, scope: dict[str, Any]) -> Any:
        return _resolve(self.planner)(live, scope)

    def apply(self, live: Any, planned: Any, items: list[Any], recorder: Any) -> None:
        _resolve(self.applier)(live, planned, items, recorder)


def _resolve(ref: str | Callable[..., Any]) -> Callable[..., Any]:
    if callable(ref):
        return ref
    module, _, name = ref.partition(":")
    return getattr(importlib.import_module(module), name)


KINDS: tuple[ActionKind, ...] = (
    ActionKind(
        key="owner-info-tags",
        title="Owner information: PayHOA tags and request completions",
        cli="jason owner-info --apply --payhoa --yes",
        system="payhoa", resource=Resource.PAYHOA, risk=Risk.R2, approver=Approver.ONE_PERSON,
        reversible="tags: yes, remove or add the tag back; a completed request's status: yes; the comment emailed "
                   "to the owner: no",
        planner="jason.approvals.kinds.owner_info:plan",
        applier="jason.approvals.kinds.owner_info:apply",
        clock="the owner-information cycle (Civil Code 4040, 4041)",
        rule="the board's owner-information completion rule "
             "(Community.owner_information: OWNER_INFO_COMPLETED_COMMENT)",
        aliases=("payhoa.owner-info.tags",),
    ),
)

_registered: dict[str, ActionKind] = {}


def register(kind: ActionKind) -> ActionKind:
    """Add a kind (a test's fake kind, or one a module defines); a key already taken is replaced."""
    _registered[kind.key] = kind
    return kind


def unregister(key: str) -> None:
    _registered.pop(key, None)


def kinds() -> list[ActionKind]:
    out = {k.key: k for k in KINDS}
    out.update(_registered)
    return list(out.values())


def get(key: str) -> ActionKind:
    for kind in kinds():
        if key == kind.key or key in kind.aliases:
            return kind
    raise KeyError(f"no action kind {key}: " + ", ".join(k.key for k in kinds()))


__all__ = ["ActionKind", "Approver", "KINDS", "Risk", "get", "kinds", "register", "unregister"]
