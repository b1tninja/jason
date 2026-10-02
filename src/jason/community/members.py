"""PayHOA's members beside the county's owners.

PayHOA keeps, for each unit, the occupancy periods and the owner records
that sit inside them, each owner pointing at a membership. The recorder
keeps who holds title. The two lists should agree for the current period:
every grantee on the newest deed is a member, and every owner-member is a
grantee. Where they differ, the difference has a name: a tenant listed as
an owner, a trust that holds title while the person is the member, a sale
PayHOA has not caught up with, or a member who never held title.

This module compares the two. It does not write PayHOA and it does not
decide who is a member; it reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from jason.community.index_cache import _ROLE

AGREES = "agrees"
TITLE_NOT_MEMBER = "on title, not a member"
MEMBER_NOT_TITLE = "member, not on title"
NO_MEMBER = "no member on file"
NO_DEED = "no deed on file"


@dataclass(frozen=True)
class Occupancy:
    """One period PayHOA tracked for a unit, and the members it lists as owners."""

    unit_id: int
    address: str
    occupancy_id: int
    from_date: date | None
    to_date: date | None
    members: tuple[str, ...]
    membership_ids: tuple[int, ...]

    @property
    def current(self) -> bool:
        return self.to_date is None


@dataclass(frozen=True)
class MemberCheck:
    """The current occupancy of a unit read against the newest deed."""

    apn: str
    address: str
    members: tuple[str, ...]
    owners: tuple[str, ...]
    verdict: str
    unmatched_members: tuple[str, ...] = ()
    unmatched_owners: tuple[str, ...] = ()
    since: date | None = None


def occupancies(units: list[dict[str, Any]], people: dict[int, str]) -> tuple[Occupancy, ...]:
    """Every occupancy period of every unit, oldest first, with member names.

    ``units`` are the PayHOA unit records (the raw JSON), ``people`` maps a
    membership id to a display name. An owner whose membership is unknown
    keeps its id as the name.
    """
    found: list[Occupancy] = []
    for unit in units:
        address = str(unit.get("title") or unit.get("streetAddress") or unit.get("address") or "").strip()
        unit_id = int(unit.get("id") or 0)
        owners_by_period: dict[int, list[tuple[int, str]]] = {}
        for owner in unit.get("owners") or []:
            if owner.get("deletedAt"):
                continue
            period = int(owner.get("unitOccupancyId") or 0)
            membership = int(owner.get("membershipId") or 0)
            owners_by_period.setdefault(period, []).append((membership, people.get(membership, str(membership))))
        periods = unit.get("occupancies") or []
        if not periods and owners_by_period:
            periods = [{"id": key, "unitId": unit_id} for key in owners_by_period]
        for period in periods:
            key = int(period.get("id") or 0)
            listed = owners_by_period.get(key, [])
            found.append(
                Occupancy(
                    unit_id,
                    address,
                    key,
                    _day(period.get("fromDate")),
                    _day(period.get("toDate")),
                    tuple(name for _, name in listed),
                    tuple(membership for membership, _ in listed),
                )
            )
    found.sort(key=lambda item: (item.address, item.from_date or date.min, item.occupancy_id))
    return tuple(found)


def check_members(
    apn: str,
    address: str,
    owners: tuple[str, ...],
    periods: tuple[Occupancy, ...],
) -> MemberCheck:
    """Compare the newest deed's grantees with the unit's current members.

    A member matches a grantee when they share a surname, so a trust named
    for the family and a member with that family name agree, and a company
    on title agrees with the company as the member. The unit agrees
    when at least one person on title is a member and every member is on
    title; a co-owner who is not a member is listed but does not fail it.
    Nobody on title being a member is the failure.
    """
    current = [item for item in periods if item.current] or ([periods[-1]] if periods else [])
    members = tuple(dict.fromkeys(name for item in current for name in item.members))
    since = current[0].from_date if current else None
    if not owners and not members:
        return MemberCheck(apn, address, (), (), NO_DEED, since=since)
    if not owners:
        return MemberCheck(apn, address, members, (), NO_DEED, unmatched_members=members, since=since)
    if not members:
        return MemberCheck(apn, address, (), owners, NO_MEMBER, unmatched_owners=owners, since=since)
    owner_keys = {_surnames(name) for name in owners}
    member_keys = {name: _surnames(name) for name in members}
    unmatched_members = tuple(name for name, keys in member_keys.items() if not any(keys & other for other in owner_keys))
    unmatched_owners = tuple(
        name for name in owners if not any(_surnames(name) & keys for keys in member_keys.values())
    )
    nobody_on_title = len(unmatched_owners) == len(owners)
    if nobody_on_title and unmatched_members:
        verdict = f"{TITLE_NOT_MEMBER}; {MEMBER_NOT_TITLE}"
    elif nobody_on_title:
        verdict = TITLE_NOT_MEMBER
    elif unmatched_members:
        verdict = MEMBER_NOT_TITLE
    else:
        verdict = AGREES
    return MemberCheck(apn, address, members, owners, verdict, unmatched_members, unmatched_owners, since)


def load_units(catalog_path: str) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """The unit records and the membership names from the local PayHOA catalog."""
    import sqlite3

    connection = sqlite3.connect(catalog_path)
    try:
        units = [json.loads(row[0]) for row in connection.execute("SELECT raw_json FROM units")]
        people: dict[int, str] = {}
        for identifier, name in connection.execute("SELECT id, name FROM people"):
            people[int(identifier)] = str(name or "")
    finally:
        connection.close()
    return units, people


def _surnames(name: str) -> frozenset[str]:
    """Words of a name that can identify a family: the index surname or a person's family name.

    The recorder prints SURNAME GIVEN; PayHOA prints Given Surname. Both
    forms contribute every word longer than one letter that is not a role
    word, so the two spellings meet on the surname wherever it sits.
    """
    tokens = [token.strip(".,") for token in name.upper().replace("&", " ").split()]
    return frozenset(token for token in tokens if len(token) > 1 and token not in _ROLE and token not in {"AND", "THE", "OF"})


def _day(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None
