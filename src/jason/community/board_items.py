"""Board action items: the matters jason's reviews found that need a board decision, kept as a running list.

A ``BoardItem`` is one matter for the board: what it is, what the board is asked to do, the authority, the evidence
(with the jason command that reproduces it), how urgent it is, and where it stands. Items carry stable ids so a review
that finds the same matter again updates it instead of adding a copy. The board owns an item's status, owner, meeting,
and notes; jason owns its summary and evidence. The list is the association's working record, not a determination: an
item says what a person should look at and decide, never what the answer is.

``agenda_session`` places an item in open or executive session. The board may meet in executive session to consider
litigation, the formation of contracts with third parties, member discipline, personnel matters, or a member's request
to meet about the member's assessments (CIV 4935(a)); it must for a payment plan (4935(c)) and a decision to foreclose
(4935(d)). Everything else is open, and what executive session discussed is noted generally in the next open minutes
(4935(e)). Notice is at least four days before a meeting, two for one held solely in executive session (CIV 4920).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ItemCategory(Enum):
    GOVERNANCE = "governance"      # the board, meetings, elections, governing documents
    FINANCE = "finance"            # budget, assessments, accounts
    RESERVES = "reserves"          # reserve funding, loans, studies
    SAFETY = "safety"              # fire, life safety, inspections
    INSURANCE = "insurance"
    LEGAL = "legal"                # litigation, counsel, disclosures
    COLLECTIONS = "collections"    # assessment collection and liens
    RECORDS = "records"            # association records, filings, housekeeping
    MAINTENANCE = "maintenance"


class Priority(Enum):
    URGENT = "urgent"    # a deadline has passed or is days away, or life safety
    HIGH = "high"        # a statutory duty unmet, or money at stake
    NORMAL = "normal"


class ItemStatus(Enum):
    OPEN = "open"                  # found; not yet scheduled
    PROPOSED = "proposed"          # proposed for the next agenda
    ON_AGENDA = "on agenda"        # noticed for a meeting
    IN_PROGRESS = "in progress"    # decided; being carried out
    DEFERRED = "deferred"
    CLOSED = "closed"


class Session(Enum):
    OPEN = "open session"
    EXECUTIVE = "executive session"


@dataclass
class BoardItem:
    id: str                                   # a stable slug ("cost-centers-not-kept")
    title: str
    summary: str                              # what the records show, in a few sentences
    ask: str                                  # what the board is asked to do ("decide", "direct counsel to ...")
    category: ItemCategory
    priority: Priority = Priority.NORMAL
    status: ItemStatus = ItemStatus.OPEN
    authority: str = ""                       # the statute or governing document ("CIV 5515(d)", "Annexation 1.3")
    evidence: tuple[str, ...] = ()            # records and commands ("jason reserves --transfers")
    session: Session | None = None            # None: decided by ``agenda_session``
    special_notice: str = ""                  # a notice the agenda item itself must carry ("Notice of Intent to Borrow, CIV 5515(b)")
    due: date | None = None
    opened: date | None = None
    owner: str = ""                           # the board's
    meeting: str = ""                         # the board's: the meeting it is noticed for
    notes: str = ""                           # the board's
    source: str = "jason"                     # "jason" or "board"
    history: list[str] = field(default_factory=list)


EXECUTIVE_CATEGORIES = {ItemCategory.COLLECTIONS}


def agenda_session(item: BoardItem) -> Session:
    """The item's own session when it sets one (litigation, a contract being formed); else executive for collections
    (a payment plan or a decision to foreclose, CIV 4935(c), (d)) and open for everything else."""
    if item.session is not None:
        return item.session
    return Session.EXECUTIVE if item.category in EXECUTIVE_CATEGORIES else Session.OPEN


PRIORITY_ORDER = {Priority.URGENT: 0, Priority.HIGH: 1, Priority.NORMAL: 2}


__all__ = ["ItemCategory", "Priority", "ItemStatus", "Session", "BoardItem", "agenda_session", "PRIORITY_ORDER"]
