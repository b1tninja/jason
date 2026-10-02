"""The association's legal matters: construction defect claims, lawsuits, liens, collections, disputes.

A ``LegalCase`` is one matter: its forum and number, the association's role, the parties that are businesses (a private
person is described by role, never named), counsel, the insurer's claims, the events in order with where each is
recorded, the money, and the duties a statute attaches to it, each with whether the record shows it met. The cases are
facts of the specification (``Mystique.legal_cases()``), confirmed by a person; a duty's ``met`` is ``None`` until the
record shows it either way. Every case is confidential by default: litigation is an executive session matter
(CIV 4935(a)), and the board decides what to disclose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Forum(Enum):
    SB800 = "SB 800 prelitigation (Civil Code 895-945.5)"
    SUPERIOR_COURT = "Superior Court"
    NONJUDICIAL_FORECLOSURE = "nonjudicial foreclosure (CIV 5700-5710)"
    IDR = "internal dispute resolution (CIV 5900)"
    ADR = "alternative dispute resolution (CIV 5925)"
    ADMINISTRATIVE = "administrative agency"
    RECORDED_LIEN = "recorded lien"


class CaseRole(Enum):
    CLAIMANT = "claimant"
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    RESPONDENT = "respondent"
    NOT_A_PARTY = "not a party"


class CaseStatus(Enum):
    PRELITIGATION = "prelitigation"
    PENDING = "pending"
    SETTLED = "settled"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass(frozen=True)
class CaseEvent:
    day: date
    step: str
    source: str = ""          # where it is recorded: a Drive path, a library file, a Gmail date and sender, a ledger entry


@dataclass(frozen=True)
class CaseDuty:
    statute: str              # "CIV 6100(a)"
    requirement: str
    met: bool | None = None   # None: the record does not show it either way, or it does not apply yet
    evidence: str = ""
    due: date | None = None
    applies: bool = True      # False: the statute's condition never arose (no suit filed, so no 6150 notice)


class RepairStanding(Enum):
    OPEN = "open"                     # no work on file
    PARTLY = "partly done"            # work on file touches the item; a person decides whether it is the repair
    DONE = "done"


@dataclass(frozen=True)
class SettledItem:
    """One item a settlement released, with the claimant's cost of repair for it: the scope a repair plan starts from."""

    section: str                      # the cost of repair's section ("1.42")
    title: str
    scope: str                        # the repair the claimant's consultant priced
    hard_cents: int | None = None     # the consultant's line subtotals before markups; None when it priced none
    standing: RepairStanding = RepairStanding.OPEN
    work: str = ""                    # the work on file that touches it: vendor, date, amount, fund


@dataclass(frozen=True)
class LegalCase:
    key: str
    title: str
    forum: Forum
    role: CaseRole
    status: CaseStatus
    court: str = ""
    case_number: str = ""
    opposing: tuple[str, ...] = ()         # businesses; a private person by role only ("a unit owner")
    counsel: tuple[str, ...] = ()
    insurer_claims: tuple[str, ...] = ()
    buildings: tuple[int, ...] = ()
    events: tuple[CaseEvent, ...] = ()
    gross_cents: int | None = None
    fees_cents: int | None = None
    net_cents: int | None = None
    proceeds_account: str = ""
    duties: tuple[CaseDuty, ...] = ()
    board_item: str = ""                   # the board action item that tracks it (data/board/items.json)
    confidential: bool = True
    # The folder under My Drive that holds the case file; the case gets its own AnythingLLM catalog from it.
    drive_folder: str = ""
    # File names (globs) in that folder held back from the catalog unless a person asks: medical and veterinary records.
    held_back: tuple[str, ...] = ()
    # What the settlement released, priced by the claimant's consultant; the repair plan's scope.
    settled_items: tuple[SettledItem, ...] = ()
    settled_source: str = ""               # where the pricing is, and any limit on sharing it

    @property
    def settled_hard_cents(self) -> int:
        return sum(i.hard_cents or 0 for i in self.settled_items)

    @property
    def opened(self) -> date | None:
        return min((e.day for e in self.events), default=None)

    @property
    def open_duties(self) -> tuple[CaseDuty, ...]:
        return tuple(d for d in self.duties if d.applies and d.met is not True)


def settled_lines(case: LegalCase) -> list[str]:
    """The settled items as a repair plan's starting scope: each item's price and standing, then the total against the net."""
    if not case.settled_items:
        return []
    out = []
    for i in case.settled_items:
        price = f"${i.hard_cents / 100:,.0f}" if i.hard_cents is not None else "not priced"
        line = f"{i.section} {i.title}: {price} ({i.standing.value}); {i.scope}"
        out.append(line + (f"; work on file: {i.work}" if i.work else ""))
    total = f"settled items priced at ${case.settled_hard_cents / 100:,.0f} before markups"
    if case.net_cents is not None:
        total += f", against ${case.net_cents / 100:,.2f} net received"
    out.append(total)
    if case.settled_source:
        out.append(case.settled_source)
    return out


__all__ = ["Forum", "CaseRole", "CaseStatus", "CaseEvent", "CaseDuty", "RepairStanding", "SettledItem", "LegalCase",
           "settled_lines"]
