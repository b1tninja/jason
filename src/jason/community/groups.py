"""The association's Google Groups: shared addresses whose mail reaches several people.

A group is a fact of the specification (``mystique/groups.py``): its address, its name, and what mail sent to it is
for. The Gmail sync records the groups each message came through (its ``List-Id``, and the group that rewrote its
sender); a task reads the group's purpose from here instead of guessing from the address.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GroupPurpose(Enum):
    ACCOUNTS_PAYABLE = "accounts payable: invoices, bills, and statements to pay"
    BOARD = "the board of directors"
    GENERAL = "the association's general inbox: owners, vendors, and agencies"
    MANAGEMENT = "the manager's mail"
    ARCHITECTURAL = "architectural review"
    MAIL = "the paper mail: the mailbox service's delivery and scan notices"
    OTHER = "other"


@dataclass(frozen=True)
class GoogleGroup:
    address: str
    name: str
    purpose: GroupPurpose
    # Mail to it is for directors only (the board's own deliberation), never an owner-facing page.
    confidential: bool = False
    note: str = ""


def group_of(address: str, groups: tuple[GoogleGroup, ...]) -> GoogleGroup | None:
    wanted = address.strip().lower()
    return next((g for g in groups if g.address.lower() == wanted), None)


def groups_for(purpose: GroupPurpose, groups: tuple[GoogleGroup, ...]) -> frozenset[str]:
    """The addresses of the groups with this purpose."""
    return frozenset(g.address.lower() for g in groups if g.purpose is purpose)


__all__ = ["GoogleGroup", "GroupPurpose", "group_of", "groups_for"]
