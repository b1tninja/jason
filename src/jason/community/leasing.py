"""Leasing under the CC&Rs and Civil Code 4740-4741: how many units may be rented, and where each unit stands.

Two different facts, kept apart:

- **occupancy**: the unit is rented out now (4041(a)(4)), the occupancy tag ("Rental"), whether or not anyone approved it;
- **approval**: the board approved the owner's written application to rent under the CC&Rs (the rental-approval tag,
  with its date and source in a unit field: an application, or the board's recognition of an existing rental).

``LeasingRules`` holds the declaration's cap and minimum term; ``standing`` sets the two tags side by side for every
unit and counts the rented units against the cap. The cap may not be set below 25 percent (4741(b)); a rule that does
is reported, never applied. A unit rented without an approval is a matter for the board (a request for the
application, or recognition of a rental the association long allowed); jason only lists it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from jason.community.tags import PayhoaTag, TagPurpose, TagScope, tag_names, tagged

STATUTORY_FLOOR = 25            # 4741(b): no cap below 25 percent of the separate interests


@dataclass(frozen=True)
class LeasingRules:
    cap_percent: int                       # the most units that may be rented at once, as a percent of all units
    min_term_days: int = 0                 # the shortest lease the declaration allows
    reapply_after_days: int = 0            # an approval lapses after a vacancy longer than this (0: never)
    authority: str = ""


@dataclass
class UnitLease:
    unit_id: int
    unit: str
    rented: bool
    approved: bool

    @property
    def standing(self) -> str:
        if self.rented and self.approved:
            return "rented, approved"
        if self.rented:
            return "rented, no approval on file"
        if self.approved:
            return "approved, not rented now"
        return "owner-occupied or vacant"


@dataclass
class LeasingStanding:
    rules: LeasingRules
    units: list[UnitLease] = field(default_factory=list)

    @property
    def cap(self) -> int:
        return math.floor(len(self.units) * self.rules.cap_percent / 100)

    def summary(self) -> dict[str, Any]:
        rented = [u for u in self.units if u.rented]
        out = {
            "units": len(self.units),
            "cap": f"{self.rules.cap_percent}% = {self.cap} units ({self.rules.authority})",
            "rentedNow": len(rented),
            "roomUnderCap": self.cap - len(rented),
            "byStanding": {s: sum(1 for u in self.units if u.standing == s) for s in
                           ("rented, approved", "rented, no approval on file", "approved, not rented now")},
        }
        if self.rules.cap_percent < STATUTORY_FLOOR:
            out["capBelowStatute"] = (f"the declaration's {self.rules.cap_percent}% is below the 25% floor of Civil Code "
                                      "4741(b); the law's floor governs")
        return out


def standing(units: Iterable[dict[str, Any]], tags: Iterable[PayhoaTag], rules: LeasingRules) -> LeasingStanding:
    """Every unit's occupancy and approval tags, side by side."""
    tags = tuple(tags)
    out = LeasingStanding(rules)
    for unit in units:
        if unit.get("deletedAt"):
            continue
        names = tag_names(unit)
        rented = any(t.value == "Rented out" for t in tagged(tags, names, TagPurpose.OCCUPANCY, TagScope.UNIT))
        approved = bool(tagged(tags, names, TagPurpose.RENTAL_APPROVAL, TagScope.UNIT))
        out.units.append(UnitLease(int(unit["id"]), str(unit.get("title") or unit.get("label") or unit["id"]), rented,
                                   approved))
    out.units.sort(key=lambda u: u.unit)
    return out


__all__ = ["LeasingRules", "LeasingStanding", "STATUTORY_FLOOR", "UnitLease", "standing"]
