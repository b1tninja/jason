"""The notices the law requires, as rules: who receives each and how, so a send reaches everyone it must.

A ``NoticeRule`` names a notice, its authority, whether it goes by individual delivery (Civil Code 4040: each owner's
election, or first-class mail without one) or as a general notice (4045: posted where the annual policy statement says,
and individually to any member who asked for general notices that way), whether the secondary addresses get a copy
(4040(b): the annual budget report and policy statement, and the assessment collection notices), and its reach: every
owner, or the owners of the units carrying a unit tag (a building's flood policy).

PayHOA's own filters select anyone carrying any of the chosen tags; they cannot say "owners with no election", who are
the ones the law sends first-class mail. So jason resolves a rule to the exact recipients (``tasks.notice_delivery``)
and the sending tools take the ids; and ``audit`` keeps the tags whole, so a person using PayHOA's filters alone selects
the same people: every owner carries a delivery tag, mail until they elect otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NoticeKind(Enum):
    INDIVIDUAL = "individual delivery (4040)"
    GENERAL = "general notice (4045)"


@dataclass(frozen=True)
class NoticeRule:
    key: str
    title: str
    authority: str
    kind: NoticeKind
    secondary_copies: bool = False        # 4040(b): a copy to each secondary address on file
    reach: str = "all owners"             # or "unit tag", narrowed to the units carrying a tag given at send time
    note: str = ""
    courtesy_email: bool = False          # also email every owner with a deliverable address, beside the law's delivery
    unconfirmed_copies: bool = False      # copies also reach secondary records tagged unconfirmed (an address not yet the owner's word)


__all__ = ["NoticeKind", "NoticeRule"]
