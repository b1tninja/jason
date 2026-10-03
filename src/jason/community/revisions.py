"""A record's revision history: each version (an expression of the work) and the event that made it.

Every association record moves through stages, each with a date, and each stage is a version that can be cited:

- a declaration amendment is drafted, adopted by the members, and recorded (it takes effect on recording, Civil Code
  4270(a); ``living.Standing`` and ``living.Effect``);
- an operating rule change is proposed with its text (4360(a)), then adopted at a board meeting (4360(b));
- minutes are available as a draft within 30 days (4950(a)), then approved, and sometimes corrected;
- a budget, a reserve study, or a policy statement is drafted, then adopted or distributed.

A ``RecordVersion`` names one stage of one work: the book (a key such as ``decl``), the item in a series (a meeting
day, a resolution number, a year; empty for a living document), the stage, the day of the event, the day it took
effect, and the source that holds its words. A version that is not in force (a draft, a proposal, an adopted
declaration amendment not yet recorded) is cited as itself and never merged into the text in force.

Pure records: the readers that build a history are in ``jason.tasks``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Stage(Enum):
    """Where a version stands. The value is the word a citation prints (``rules@proposed-2026-11-01``)."""

    DRAFT = "draft"              # written, not adopted; never in force
    PROPOSED = "proposed"        # noticed for comment with its text (a rule change, 4360(a)); not in force
    ADOPTED = "adopted"          # approved by the board or the members; in force on adoption unless it must be recorded
    APPROVED = "approved"        # minutes the board approved (a draft was available before, 4950(a))
    RECORDED = "recorded"        # recorded by the county; a declaration amendment takes effect now (4270(a))
    DISTRIBUTED = "distributed"  # delivered to members (a budget report, a policy statement)
    CORRECTED = "corrected"      # a later version that corrects an approved or adopted one
    SUPERSEDED = "superseded"    # replaced by a later work (a restatement, a new policy)
    REPEALED = "repealed"        # removed; no longer in force

    @property
    def in_force_capable(self) -> bool:
        """Whether a version at this stage can be the text in force (a draft or a proposal never is)."""
        return self not in (Stage.DRAFT, Stage.PROPOSED, Stage.SUPERSEDED, Stage.REPEALED)


@dataclass(frozen=True)
class RecordVersion:
    book: str                    # the record's key (decl, bylaws, rules, min, res, budget, ...)
    item: str                    # the item in a series (2026-09-15, 20230130-1, 2027); empty for a living document
    stage: Stage
    on: date | None              # the day of the event (adopted, recorded, approved, noticed)
    effective: date | None       # the day it took effect; None while not in force
    source: str = ""             # where its words are (a Drive id, a recorder number, a library path)
    event: str = ""              # what made it ("Second Amendment", "board meeting 2026-10-20, item 4")
    note: str = ""

    def in_force_on(self, day: date) -> bool:
        return self.stage.in_force_capable and self.effective is not None and self.effective <= day

    def label(self) -> str:
        """The version part of an address: ``@2023-12-06`` for one in force, ``@proposed-2026-11-01`` otherwise."""
        when = (self.effective or self.on)
        stamp = when.isoformat() if when else "undated"
        return f"@{stamp}" if self.effective else f"@{self.stage.value}-{stamp}"
