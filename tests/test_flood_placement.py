"""A flood payment's building: the NFIP number in its bank line, else a building its memo or attachment names."""

from __future__ import annotations

from types import SimpleNamespace

from jason.community.symbols import Building
from jason.tasks.insurance import _flood_key, flood_policy_named


def _flood(number: str, building: Building, prior: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(kind=SimpleNamespace(name="FLOOD"), number=number, building=building, numbers=(number, *prior))


POLICIES = [_flood("5010000011", Building.BLDG_2, ("5010000096",)), _flood("5010000095", Building.BLDG_6),
            _flood("5010022209", Building.BLDG_5), SimpleNamespace(kind=SimpleNamespace(name="MASTER"), number="N030PK2940-01",
                                                                   building=None, numbers=("N030PK2940-01",))]


def test_the_bank_line_number_places_a_flood_payment() -> None:
    line = "ORIG CO NAME:FLOOD INSURANCE ... IND NAME:MYSTIQUE COMMUNITY ASS 5010000011 ACH TRANSACTION"
    assert flood_policy_named(line, POLICIES) == _flood_key(POLICIES[0])
    assert flood_policy_named("PREMIUM 5010000096", POLICIES) == _flood_key(POLICIES[0])      # a prior number


def test_a_building_named_in_the_attachment_places_it_when_no_number_does() -> None:
    assert flood_policy_named("FEMA NFIP FLOOD INSUR MT 10/28 Invoice Flood Bldg 5 24-25.pdf", POLICIES) == _flood_key(POLICIES[2])
    assert flood_policy_named("Philadelphia Indemnity Insurance Company 95501371.PDF", POLICIES) is None
    # Two buildings named is no placement.
    assert flood_policy_named("Invoice Bldg 5 and Bldg 6", POLICIES) is None
