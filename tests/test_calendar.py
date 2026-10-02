from datetime import date

from jason.community.calendar import (
    CONSTRUCTION,
    DECLINE,
    IMPROVEMENT,
    RESTORATION,
    SALE,
    classify,
    enrolled_by_year,
    findings,
    reassessing_years,
)
from jason.community.tax import TaxBill


def _bill(year: int, value: int, *, supplemental: bool = False) -> TaxBill:
    if supplemental:
        return TaxBill(f"s{year}", f"{year} Secured Supplemental Bill", year=year)
    return TaxBill(str(year), f"{year} Secured Annual Bill", year=year, land_cents=value // 3, improvement_cents=value - value // 3)


def _track(start: int, first: int, *values: int) -> list[TaxBill]:
    """Bills from ``start`` whose values are given, in dollars."""
    return [_bill(start + index, value * 100) for index, value in enumerate((first, *values))]


def test_a_supplemental_bill_has_no_enrolled_value_and_the_annual_bill_wins():
    bills = [_bill(2020, 10_000_00), _bill(2020, 0, supplemental=True), _bill(2021, 10_200_00)]
    assert enrolled_by_year(bills) == {2020: 10_000_00, 2021: 10_200_00}


def test_a_reassessing_deed_lands_on_the_next_bill_year():
    steps = (
        ("202006121161", date(2020, 6, 12), True),
        ("202206150517", date(2022, 6, 15), True),
        ("202408130870", date(2024, 8, 13), False),
        ("999", None, True),
    )
    assert reassessing_years(steps) == {2021: "202006121161", 2023: "202206150517"}


def test_a_rise_the_year_the_building_was_finished_is_construction():
    # Land only in 2020, the finished unit in 2021, the sale in 2022.
    bills = _track(2019, 16_695, 16_695, 164_028, 313_283)
    events = classify(bills, {2022: "202103111504"}, first_conveyance=date(2021, 3, 11))
    assert [(e.year, e.kind, e.number) for e in events] == [
        (2021, CONSTRUCTION, ""),
        (2022, SALE, "202103111504"),
    ]
    assert findings(bills, {2022: "202103111504"}, first_conveyance=date(2021, 3, 11)) == ()


def test_a_rise_under_the_factored_base_is_a_restoration_not_a_sale():
    # Bought for 215,000 in 2008 (base), reduced under Proposition 8, restored in 2017.
    bills = _track(2013, 108_360, 141_814, 149_255, 157_067, 208_000, 216_600)
    events = classify(bills, {}, first_conveyance=date(2008, 10, 17))
    kinds = [(e.year, e.kind) for e in events]
    assert (2014, RESTORATION) in kinds
    assert (2017, RESTORATION) in kinds
    assert all(kind != SALE for _, kind in kinds)
    assert findings(bills, {}, first_conveyance=date(2008, 10, 17)) == ()


def test_a_rise_well_over_the_ceiling_with_no_deed_is_a_missing_sale():
    bills = _track(2013, 117_600, 151_704, 154_738, 157_833, 215_000)
    events = classify(bills, {2014: "201312310832"})
    assert [(e.year, e.kind, e.number) for e in events] == [
        (2014, SALE, "201312310832"),
        (2017, SALE, ""),
    ]
    found = findings(bills, {2014: "201312310832"})
    assert [(f.kind, f.year) for f in found] == [("sale without deed", 2017)]
    assert "recorded in 2016" in found[0].detail


def test_a_small_rise_over_the_ceiling_is_an_improvement():
    bills = _track(2013, 100_000, 102_000, 108_000, 110_160)
    events = classify(bills, {}, base=(2013, 100_000_00))
    assert [(e.year, e.kind) for e in events] == [(2015, IMPROVEMENT)]


def test_a_sale_below_the_factored_base_is_a_decline_that_the_deed_explains():
    bills = _track(2022, 462_133, 478_515, 460_000)
    events = classify(bills, {2024: "202407100627"}, first_conveyance=date(2022, 3, 21))
    assert [(e.year, e.kind, e.number) for e in events] == [
        (2023, CONSTRUCTION, ""),
        (2024, SALE, "202407100627"),
    ]
    assert findings(bills, {2024: "202407100627"}, first_conveyance=date(2022, 3, 21)) == ()


def test_a_fall_with_no_deed_is_a_decline():
    bills = _track(2013, 200_000, 180_000, 183_600)
    assert [(e.year, e.kind) for e in classify(bills, {})] == [(2014, DECLINE)]


def test_a_deed_that_lands_on_a_flat_year_is_reported_for_a_person():
    bills = _track(2020, 150_843, 153_859, 156_935)
    found = findings(bills, {2022: "202107190658"})
    assert [(f.kind, f.number) for f in found] == [("deed without reassessment", "202107190658")]


def test_a_deed_outside_the_bill_years_is_not_checked():
    bills = _track(2013, 100_000, 102_000)
    assert findings(bills, {2013: "201203270988", 2027: "202607011365"}) == ()
