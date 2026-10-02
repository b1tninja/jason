"""Leasing: occupancy and approval kept apart, counted against the declaration's cap, never below the statute's floor."""

from jason.community.leasing import LeasingRules, standing
from jason.community.tags import PayhoaTag, TagPurpose, TagScope

U = TagScope.UNIT
TAGS = (PayhoaTag("Rental", U, TagPurpose.OCCUPANCY, "Rented out"),
        PayhoaTag("Rental Approved", U, TagPurpose.RENTAL_APPROVAL))


def _unit(uid, *tags):
    return {"id": uid, "title": f"{3000 + uid} ENCHANTED WALK", "tags": [{"tag": t} for t in tags]}


def test_each_unit_stands_by_its_two_tags_against_the_cap():
    units = [_unit(1, "Rental", "Rental Approved"), _unit(2, "Rental"), _unit(3, "Rental Approved"), *(_unit(i) for i in range(4, 13))]
    found = standing(units, TAGS, LeasingRules(cap_percent=25, authority="CC&Rs 4.15(a)"))
    by_unit = {u.unit_id: u.standing for u in found.units}
    assert by_unit[1] == "rented, approved" and by_unit[2] == "rented, no approval on file"
    assert by_unit[3] == "approved, not rented now" and by_unit[4] == "owner-occupied or vacant"
    report = found.summary()
    assert found.cap == 3 and report["rentedNow"] == 2 and report["roomUnderCap"] == 1     # 25% of 12 units
    assert "capBelowStatute" not in report


def test_a_cap_below_the_statutes_floor_is_reported():
    report = standing([_unit(1)], TAGS, LeasingRules(cap_percent=20)).summary()
    assert "4741(b)" in report["capBelowStatute"]


def test_mystiques_rules_are_the_amended_declarations():
    from jason.community import mystique

    rules = mystique().leasing_rules()
    assert rules.cap_percent == 25 and rules.min_term_days == 30 and "Second Amendment" in rules.authority
    names = {t.name for t in mystique().payhoa_tags() if t.purpose is TagPurpose.RENTAL_APPROVAL}
    assert names == {"Rental Approved"}
