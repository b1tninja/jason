"""PayHOA tags as records: what each tag the association uses means, and how an owner's tags decide notice delivery.

PayHOA tags units and members, and both of its sending tools select by them: a broadcast takes unit and member tags,
and the Mailroom takes the owners and units they resolve to. So the association keeps owners' choices as tags in
PayHOA, its books (Civil Code 4041(b)(1)), and every other channel (a paper form, a fillable PDF, a Google Form) is a
way to collect a choice a person then tags. ``PayhoaTag`` rows in the specification name each tag, whether it is on
units or members, and what it means; a tag the association means to use but has not created yet is marked
``exists=False``.

``delivery`` applies Civil Code 4040(a) to one owner: a member tagged for email gets email when PayHOA has a valid
address for them, a member tagged for mail gets mail, both tags get both, and a member with no valid election gets
first-class mail to the address on the books (4040(a)(2)) — the mailing address in their profile, else the unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class TagScope(Enum):
    UNIT = "unit"
    MEMBER = "member"


class TagPurpose(Enum):
    BUILDING = "building"                        # which flood building a unit is in
    NOTICE_DELIVERY = "notice delivery"          # 4041(a)(1): email or mail
    LEGAL_REPRESENTATIVE = "legal representative"  # 4041(a)(3): the representative's own person record on the unit
    MEMBERSHIP_LIST = "membership list"          # 5220: the owner opted out of sharing their name and addresses
    OCCUPANCY = "occupancy"                      # 4041(a)(4)
    ANSWERED = "answered"                        # the owner answered this year's 4041 solicitation
    SECONDARY_CONTACT = "additional deliveries"  # an additional owner record for a second address: 4040(b) copies only
    GENERAL_INDIVIDUALLY = "general notices individually"  # 4045(b): general notices by individual delivery
    RENTAL_APPROVAL = "rental approval"          # the board approved the owner's written application to rent
    UNCONFIRMED = "unconfirmed"                  # a secondary record whose address the owner has not confirmed
    PROPERTY_MANAGER = "property manager"        # the owner's property manager's own person record, at the owner's ask
    BALLOT = "ballot"                            # the Election Rules' paper or electronic ballot
    STATEMENTS = "statements"                    # billing statements on paper
    ROLE = "role"                                # a board member
    SYSTEM = "system"                            # set by PayHOA itself


class Channel(Enum):
    EMAIL = "email"
    MAIL = "mail"


@dataclass(frozen=True)
class PayhoaTag:
    """One tag: its exact ``name`` in PayHOA, on units or members, its purpose, and the value it stands for (``email``
    or ``mail`` for delivery; an occupancy option; a year for ``ANSWERED``). ``managed`` is who sets it: the board, or
    PayHOA. ``exists`` is False for a tag the specification proposes and PayHOA does not have yet. ``answer`` is the
    owner-information form question that sets it: the tag goes on when the answer is ``value`` (a choice's option), or,
    with no value, when the question is answered at all; another option of the same question takes it off."""

    name: str
    scope: TagScope
    purpose: TagPurpose
    value: str = ""
    managed: str = "board"
    exists: bool = True
    note: str = ""
    answer: str = ""


class FieldPurpose(Enum):
    PRIOR_ANSWER = "prior answer"                # retired: one summary of an earlier answer (October 1, 2026)


@dataclass(frozen=True)
class PayhoaField:
    """A PayHOA custom field the association uses: its exact ``name``, on members or units, its purpose, and who may see
    and edit it. ``exists`` is False until the board (or jason, with a person's --yes) creates it. ``answer_key`` is the
    owner-information form's question whose answer the field holds. A ``retired`` field is one jason removes from PayHOA
    (with a person's --yes) once its values live elsewhere."""

    name: str
    scope: TagScope
    purpose: FieldPurpose
    owners_can_view: bool = True
    owners_can_edit: bool = False
    exists: bool = True
    note: str = ""
    answer_key: str = ""
    retired: bool = False


# A person record on a unit that carries one of these is not an owner of title: an additional-deliveries record, a
# legal representative, or the owner's property manager. It gets no election, no vote, and no place in owner counts or
# answer matching.
NOT_OWNERS = frozenset({TagPurpose.SECONDARY_CONTACT, TagPurpose.LEGAL_REPRESENTATIVE, TagPurpose.PROPERTY_MANAGER})


def owner_of_title(tags: Iterable["PayhoaTag"], names: set[str]) -> bool:
    """Whether a member with these tags (case folded) is an owner of title, not a record kept for an owner."""
    return not any(t.purpose in NOT_OWNERS and t.scope is TagScope.MEMBER and t.name.casefold() in names for t in tags)


def tag_names(row: dict) -> set[str]:
    """The tags on a PayHOA unit or member row, case folded."""
    return {str(t.get("tag") if isinstance(t, dict) else t).casefold() for t in row.get("tags") or []}


def tagged(tags: Iterable[PayhoaTag], names: set[str], purpose: TagPurpose, scope: TagScope) -> list[PayhoaTag]:
    """The specification's tags of ``purpose`` that ``names`` (a row's tags, case folded) carry."""
    return [t for t in tags if t.purpose is purpose and t.scope is scope and t.name.casefold() in names]


@dataclass(frozen=True)
class Delivery:
    channels: tuple[Channel, ...]
    reason: str
    send_to: str = ""            # for mail: "mailing" (the profile's address) or "unit"


def delivery(tags: Iterable[PayhoaTag], member_tags: set[str], *, valid_email: bool, mailing_address: bool) -> Delivery:
    """How one owner receives an individual notice under Civil Code 4040(a), from their member tags."""
    elected = {Channel(t.value) for t in tagged(tags, member_tags, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER)}
    send_to = "mailing" if mailing_address else "unit"
    if Channel.EMAIL in elected and not valid_email:
        return Delivery((Channel.MAIL,), "elected email, but PayHOA has no valid email: first-class mail (4040(a)(2))",
                        send_to)
    if elected == {Channel.EMAIL}:
        return Delivery((Channel.EMAIL,), "elected email")
    if elected == {Channel.MAIL}:
        return Delivery((Channel.MAIL,), "elected mail", send_to)
    if elected == {Channel.EMAIL, Channel.MAIL}:
        return Delivery((Channel.EMAIL, Channel.MAIL), "elected email and mail", send_to)
    return Delivery((Channel.MAIL,), "no election on file: first-class mail to the address on the books (4040(a)(2))",
                    send_to)


__all__ = ["Channel", "Delivery", "FieldPurpose", "NOT_OWNERS", "PayhoaField", "PayhoaTag", "TagPurpose", "TagScope", "delivery",
           "owner_of_title", "tag_names", "tagged"]
