"""Community facts: what the association knows about itself, each with its status, its sources, and the provisions that speak to it.

A fact never restates a provision's words. It stores the expression (``provisions``, a ``cite_document`` expression) and the
loader recites it. ``sources`` are evidence addresses. The profile supplies the rows (``Community.facts()``); this module holds the
records and one pure count. No I/O, no profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class FactStatus(Enum):
    DOCUMENTED = "documented"  # a stored document says it
    REPORTED = "reported"  # a person said it; no document yet
    ASSUMED = "assumed"  # nothing on file; a working assumption


class ScopeKind(Enum):
    COMMUNITY = "community"
    PLAN = "plan"
    BUILDING = "building"
    PHASE = "phase"


@dataclass(frozen=True)
class FactScope:
    kind: ScopeKind
    name: str = ""


@dataclass(frozen=True)
class Fact:
    key: str
    statement: str
    topics: tuple[str, ...]
    scope: FactScope
    status: FactStatus
    sources: tuple[str, ...] = ()  # evidence addresses
    provisions: tuple[str, ...] = ()  # cite_document expressions
    answers: tuple[str, ...] = ()  # the questions it settles
    as_of: str = ""
    confirmations: int = 0


@dataclass(frozen=True)
class PlanFactCoverage:
    plan: str
    documented: int = 0
    reported: int = 0
    assumed: int = 0

    @property
    def total(self) -> int:
        return self.documented + self.reported + self.assumed


def coverage_by_plan(facts: Iterable[Fact], plans: Iterable[str]) -> tuple[PlanFactCoverage, ...]:
    """Count each plan's plan-scoped facts by status, in the order of ``plans``. A plan with none gets zeros."""
    facts = tuple(facts)
    rows = []
    for plan in plans:
        counts = {status: 0 for status in FactStatus}
        for fact in facts:
            if fact.scope.kind is ScopeKind.PLAN and fact.scope.name == plan:
                counts[fact.status] += 1
        rows.append(
            PlanFactCoverage(
                plan=plan,
                documented=counts[FactStatus.DOCUMENTED],
                reported=counts[FactStatus.REPORTED],
                assumed=counts[FactStatus.ASSUMED],
            )
        )
    return tuple(rows)
