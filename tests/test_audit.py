from datetime import date

from jason.community.audit import audit_chain, reassessing_steps, step_reassesses
from jason.community.recorder import ChainStep, Conveyance, OwnershipHistory
from jason.community.reports import HeldUnits, PlanBlock, PublicReport
from jason.community.symbols import Building
from jason.community.tax import TaxBill
from mystique.developers import DEVELOPERS

PHASE_1 = PublicReport("130654SA", Building.BLDG_8, 1, 12, date(2007, 11, 15), "John Laing Homes", opened=date(2007, 9, 28), issued=date(2007, 9, 26))
PHASE_2 = PublicReport("132246SA", Building.BLDG_3, 2, 12, date(2008, 2, 29), "John Laing Homes", issued=date(2008, 2, 1))
BLOCKS = (PlanBlock(Building.BLDG_3, "024", 21, 12), PlanBlock(Building.BLDG_8, "017", 81, 12))
HELD = (HeldUnits("201010121565", date(2010, 10, 12), Building.BLDG_3, (25, 26, 27, 30)),)


def _deed(number, grantors, grantees, priors=()):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return ChainStep(Conveyance(number, recorded, tuple(grantors), tuple(grantees), (), "20111700170008"), tuple(priors))


def _bill(year, value):
    return TaxBill(str(year), f"{year} Secured Annual Bill", year=year, land_cents=value // 3, improvement_cents=value - value // 3)


def _history(apn="20111700170008"):
    return OwnershipHistory(
        apn,
        (
            _deed("201710301395", ("WEXMOOR DAGNY T T", "MARROWDALE FENNA V"), ("WEXMOOR EAMON M T TR", "MARROWDALE FENNA V TR"), ("201511130485",)),
            _deed("201511130485", ("THISTLEWOOD ANSEL S",), ("WEXMOOR DAGNY T T", "MARROWDALE FENNA V"), ("201408010234",)),
            _deed("201408010234", ("FARROWBY MARIT K", "FARROWBY TORVALD A"), ("THISTLEWOOD ANSEL S",), ("201204201319",)),
            _deed("201204201319", ("DUNHOLLOW FLORIAN C", "DUNHOLLOW GREER S"), ("FARROWBY MARIT K", "FARROWBY TORVALD A"), ("200709281724",)),
            _deed("200709281724", ("WL HOMES LLC",), ("DUNHOLLOW FLORIAN C", "DUNHOLLOW GREER S")),
        ),
        DEVELOPERS,
    )


def test_a_restatement_and_a_family_deed_do_not_reassess():
    history = _history()
    assert step_reassesses(history.step("201710301395"), history) is False
    assert step_reassesses(history.step("201408010234"), history) is True
    assert reassessing_steps(history) == {2008: "200709281724", 2013: "201204201319", 2015: "201408010234", 2016: "201511130485"}


def test_a_chain_that_matches_the_bills_and_the_phase_is_clean():
    bills = [_bill(y, v * 100) for y, v in ((2013, 102_462), (2014, 104_511), (2015, 169_000), (2016, 215_000), (2017, 219_300), (2018, 223_686))]
    found = audit_chain(
        _history(),
        developers=DEVELOPERS,
        report=PHASE_1,
        blocks=BLOCKS,
        held=HELD,
        bills=bills,
        prices={"201204201319": 100_000_00, "201408010234": 162_000_00},
    )
    assert found.clean, found.findings
    assert found.steps == 5


def test_a_missing_sale_and_a_flat_year_are_reported_from_the_bills():
    bills = [_bill(y, v * 100) for y, v in ((2013, 102_462), (2014, 104_511), (2015, 106_601), (2016, 215_000), (2017, 219_300))]
    found = audit_chain(_history(), developers=DEVELOPERS, report=PHASE_1, bills=bills)
    kinds = [(item.check, item.number, item.year) for item in found.findings]
    assert ("calendar", "201408010234", 2015) in kinds  # deed without reassessment
    assert all(item.check == "calendar" for item in found.findings)


def test_a_root_outside_the_phase_or_from_the_wrong_developer_is_reported():
    early = OwnershipHistory(
        "20111700240002",
        (_deed("200612131170", ("WL HOMES LLC",), ("ASHCOMBE KASIMIR M",)),),
        DEVELOPERS,
    )
    found = audit_chain(early, developers=DEVELOPERS, report=PHASE_2, blocks=BLOCKS, held=HELD)
    assert [item.check for item in found.findings] == ["phase"]
    watt = OwnershipHistory(
        "20111700240002",
        (_deed("202003060706", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("GALEWORTH LINNEA",)),),
        DEVELOPERS,
    )
    found = audit_chain(watt, developers=DEVELOPERS, report=PHASE_2, blocks=BLOCKS, held=HELD)
    assert [item.check for item in found.findings] == ["developer"]
    builders = OwnershipHistory(
        "20111700240006",
        (_deed("201203270471", ("MYSTIQUE BLDRS LLC",), ("INCHBURY OONA",)),),
        DEVELOPERS,
    )
    found = audit_chain(builders, developers=DEVELOPERS, report=PHASE_2, blocks=BLOCKS, held=HELD)
    assert found.clean, found.findings


def test_a_chain_that_does_not_start_at_a_developer_and_a_bad_order_are_reported():
    history = OwnershipHistory(
        "20111700170011",
        (
            _deed("202006121161", ("LARKHAVEN RAGNA P JR",), ("MOSSGROVE VIGGO",), ("202206150517",)),
            _deed("202206150517", ("MOSSGROVE VIGGO",), ("NETTLEFIELD WYNN",)),
        ),
        DEVELOPERS,
    )
    found = audit_chain(history, developers=DEVELOPERS, report=PHASE_1)
    assert sorted(item.check for item in found.findings) == ["order", "root"]


def test_a_price_far_from_the_enrolled_base_is_reported():
    bills = [_bill(2015, 169_000_00), _bill(2016, 215_000_00)]
    found = audit_chain(_history(), developers=DEVELOPERS, report=PHASE_1, bills=bills, prices={"201511130485": 300_000_00})
    assert [(item.check, item.number) for item in found.findings if item.check == "price"] == [("price", "201511130485")]
