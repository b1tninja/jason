"""Where each recorded lien stands against a unit's title today."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace as NS

from jason.community import filings
from jason.community.association_record import ParcelLien
from jason.community.filings import ADVANCES, CLOSES, ESCALATES, OPENS, Encumbrance, NameMatch, Process, Step
from jason.community.title import LienStanding, lien_standing, standing_counts, title_markdown, title_watch


def _step(number, day, filing, effect):
    return Step(number, day, filing, effect, (), ())


def _lien(owner, process, steps, *, claimant=("CLAIMANT",), during=True, community=False, match=NameMatch.FULL, corroborated=False):
    return ParcelLien(owner, Encumbrance(process, (owner,), tuple(claimant), tuple(steps)), during, community, match, corroborated)


def _unit(apn, owners, sales, liens, address="1 TEST WAY"):
    return NS(apn=apn, address=address, building=1, owners=tuple(owners), sales=tuple(NS(recorded=d) for d in sales), liens=tuple(liens), association=False)


def test_each_lien_reads_one_standing_against_the_title(monkeypatch):
    monkeypatch.setattr(filings, "today_for_status", lambda: date(2026, 9, 28))
    current = "DOE JANE"
    prior = "ROE BOB"
    cases = [
        (_lien(current, Process.UTILITY_LIEN, [_step("1", date(2024, 1, 1), "401 UTILITY BILLING LIEN", OPENS)]), LienStanding.STANDS),
        (_lien(current, Process.UTILITY_LIEN, [_step("2", date(2024, 1, 1), "401", OPENS), _step("3", date(2024, 3, 1), "644", CLOSES)]), LienStanding.RELEASED),
        (_lien(current, Process.LOAN, [_step("4", date(2022, 1, 1), "230", OPENS)]), LienStanding.CURRENT_LOAN),
        (_lien(current, Process.LOAN, [_step("5", date(2022, 1, 1), "230", OPENS), _step("6", date(2026, 5, 28), "531", ESCALATES)]), LienStanding.IN_DEFAULT),
        (_lien(current, Process.LOAN, [_step("7", date(2011, 11, 17), "531", ESCALATES)]), LienStanding.QUIET_DEFAULT),
        (_lien(current, Process.FIXTURE_FILING, [_step("8", date(2021, 1, 1), "368", OPENS)], claimant=("TESLA INC",)), LienStanding.SOLAR_LEASE),
        (_lien(current, Process.FIXTURE_FILING, [_step("9", date(2021, 1, 1), "368", OPENS)], claimant=("VELOCITY COMML CAPITAL LLC",)), LienStanding.STANDS),
        (_lien(current, Process.JUDGMENT_LIEN, [_step("10", date(2009, 1, 27), "376", OPENS)]), LienStanding.LAPSED),
        (_lien(prior, Process.JUDGMENT_LIEN, [_step("11", date(2019, 1, 1), "376", OPENS)]), LienStanding.PRESUMED_PAID),
        (_lien(prior, Process.ASSESSMENT_LIEN, [_step("12", date(2019, 1, 1), "386", OPENS)], community=True), LienStanding.RELEASE_DUE),
        (_lien(prior, Process.UTILITY_LIEN, [_step("13", date(2023, 6, 1), "401", OPENS)]), LienStanding.STANDS_ON_PRIOR),
        (_lien(prior, Process.FIXTURE_FILING, [_step("14", date(2019, 1, 1), "368", OPENS)]), LienStanding.FIXTURE_PRIOR),
        (_lien(current, Process.SPECIAL_TAX, [_step("15", date(2005, 1, 1), "", OPENS)]), LienStanding.RUNS_WITH_LAND),
        (_lien(current, Process.UTILITY_LIEN, [_step("16", date(2024, 1, 1), "401", OPENS)], during=False), LienStanding.ELSEWHERE),
        # Another association's lien is on a unit in that community, never on this one.
        (_lien(current, Process.ASSESSMENT_LIEN, [_step("17", date(2025, 3, 12), "386", OPENS)], claimant=("NATOMAS PARK COMMUNITY ASSOCIATION",)), LienStanding.ELSEWHERE),
    ]
    # The prior owner sold in 2020; a lien on them after that sale followed no sale.
    unit = _unit("20111700990001", [current], [date(2020, 1, 1)], [lien for lien, _ in cases])
    for lien, wanted in cases:
        assert lien_standing(unit, lien).standing is wanted, (lien.encumbrance.opened.number, wanted)
    assert lien_standing(unit, cases[8][0]).sale == date(2020, 1, 1)


def test_the_watch_marks_a_filing_shared_by_units_and_the_page_groups_what_needs_a_person(monkeypatch):
    monkeypatch.setattr(filings, "today_for_status", lambda: date(2026, 9, 28))

    def shared():
        return _lien("JCDT TRUST", Process.UTILITY_LIEN, [_step("202605140001", date(2026, 5, 14), "401", OPENS)], claimant=("CITY OF SACRAMENTO UTILITIES",))

    namesake = _lien("BRAMBLE MICAH W", Process.MECHANICS_LIEN, [_step("202405280001", date(2024, 5, 28), "389", OPENS)], match=NameMatch.BARE)
    units = (
        _unit("20111700990020", ["JCDT TRUST"], [], [shared()], "15 EXAMPLE WALK"),
        _unit("20111700990019", ["JCDT TRUST"], [], [shared()], "18 EXAMPLE WALK"),
        _unit("20111700990003", ["BRAMBLE MICAH W"], [], [namesake], "39 EXAMPLE LN"),
    )
    rows = title_watch(units)
    by_unit = {row.apn: row for row in rows}
    assert by_unit["20111700990020"].shared_with == ("20111700990019",) and by_unit["20111700990019"].shared_with == ("20111700990020",)
    assert by_unit["20111700990003"].standing is LienStanding.EXPIRED and by_unit["20111700990003"].namesake_risk
    assert standing_counts(rows) == {"STANDS": 2, "EXPIRED": 1}
    page = title_markdown(rows, title="T", today=date(2026, 9, 28))
    assert "## Needs a person" in page and "### Stands" in page and "## Unenforceable but of record" in page
    assert "the same filing names the owner of 201-1170-099-0019; it charges one of them" in page
    assert "names the owner by surname and given name only" in page and "2 of those are city or county utility liens" in page
    assert by_unit["20111700990003"].as_dict()["standing"] == "EXPIRED"


def test_a_utility_lien_is_settled_through_the_parcels_own_paid_tax_bill(monkeypatch):
    from jason.community.tax import RollRule, TaxBill, TaxLevy, roll_charges

    monkeypatch.setattr(filings, "today_for_status", lambda: date(2026, 9, 28))
    rules = (
        RollRule("0202", ("CITY OF SACRAMENTO", "CITY OF SACTO"), "city"),
        RollRule("0411", ("COUNTY OF SACRAMENTO", "COUNTY OF SACTO"), "sewer district"),
    )
    bills = (
        TaxBill("1", "2019-20", 2019, total_cents=313070, payments_cents=313070, balance_cents=0, levies=(TaxLevy("direct", "SACTO CITY DELQ UTILITIES", 6132, code="0202"),)),
        TaxBill("2", "2025-26", 2025, total_cents=500000, payments_cents=250000, balance_cents=250000, levies=(TaxLevy("direct", "CSD #1 DELINQUENT SEWER", 70536, code="0411"),)),
        TaxBill("3", "2021-22", 2021, total_cents=300000, balance_cents=0, levies=(TaxLevy("direct", "SAFCA", 150, code="0169"),)),
    )
    charges = roll_charges(bills, rules)
    assert [(c.year, c.code, c.paid) for c in charges] == [(2019, "0202", True), (2025, "0411", False)]
    owner = "SAMPLE AVERY W"

    def utility(number, day, claimant):
        return _lien(owner, Process.UTILITY_LIEN, [_step(number, day, "401 UTILITY BILLING LIEN", OPENS)], claimant=(claimant,))

    city = utility("201905020001", date(2019, 5, 2), "CITY OF SACTO")
    sewer = utility("202409110001", date(2024, 9, 11), "COUNTY OF SACRAMENTO FINANCE")
    late = utility("201910220001", date(2019, 10, 22), "COUNTY OF SACRAMENTO FINANCE")  # no 0411 charge on the 2020 or 2021 bill
    unit = _unit("20111700990001", [owner], [], [city, sewer, late])
    unit.utility_roll = charges
    paid, due, stands = (lien_standing(unit, lien) for lien in (city, sewer, late))
    assert paid.standing is LienStanding.ROLL_PAID and paid.roll_year == 2019
    assert due.standing is LienStanding.ON_ROLL and due.roll_year == 2025
    assert stands.standing is LienStanding.STANDS
    row = next(r for r in title_watch((unit,)) if r.number == "201905020001")
    assert row.as_dict()["taxBillYear"] == 2019
    page = title_markdown(title_watch((unit,)), title="T")
    assert "## Utility liens on the tax roll" in page and "2019-20, paid" in page and "2025-26, unpaid" in page


def test_the_ledger_beside_the_associations_liens_names_the_release_owed_and_the_debt(monkeypatch):
    from jason.community.collections import CollectionStanding, LedgerBalance, collections

    monkeypatch.setattr(filings, "today_for_status", lambda: date(2026, 9, 28))

    def ours(owner, number, day):
        return _lien(owner, Process.ASSESSMENT_LIEN, [_step(number, day, "386", OPENS)], claimant=("MYSTIQUE COMMUNITY ASSOCIATION",), community=True)

    paid = _unit("1", ["PAID OWNER"], [], [ours("PAID OWNER", "202401010001", date(2024, 1, 1))], "1 PAID WAY")
    owing = _unit("2", ["OWING OWNER"], [], [ours("OWING OWNER", "202504240001", date(2025, 4, 24))], "2 OWING WAY")
    fresh = _unit("3", ["NEW DEBTOR"], [], [ours("NEW DEBTOR", "202608010001", date(2026, 8, 1))], "3 FRESH WAY")
    no_lien = _unit("4", ["LATE PAYER"], [], [], "4 LATE WAY")
    credit = _unit("5", ["AHEAD"], [], [], "5 AHEAD WAY")
    square = _unit("6", ["SQUARE"], [], [], "6 SQUARE WAY")
    for unit in (paid, owing, fresh, no_lien, credit, square):
        unit.association = False
    ledger = {
        "1 PAID WAY": LedgerBalance("1 PAID WAY", 0, 0, "2026-09-24"),
        "2 OWING WAY": LedgerBalance("2 OWING WAY", 1150000, 1150000, "2026-09-24"),
        "3 FRESH WAY": LedgerBalance("3 FRESH WAY", 90000, 90000, "2026-09-24"),
        "4 LATE WAY": LedgerBalance("4 LATE WAY", 720000, 720000, "2026-09-24"),
        "5 AHEAD WAY": LedgerBalance("5 AHEAD WAY", -2500, 0, "2026-09-24"),
        "6 SQUARE WAY": LedgerBalance("6 SQUARE WAY", 0, 0, "2026-09-24"),
    }
    rows = collections((paid, owing, fresh, no_lien, credit, square), ledger, today=date(2026, 9, 28))
    by = {row.address: row for row in rows}
    assert [row.standing for row in rows] == [
        CollectionStanding.RELEASE_DUE, CollectionStanding.LIEN_SECURES_DEBT, CollectionStanding.LIEN_SECURES_DEBT,
        CollectionStanding.OWED_NO_LIEN, CollectionStanding.CREDIT,
    ]
    assert "Civil Code 5685(a)" in by["1 PAID WAY"].next_step and "6 SQUARE WAY" not in by
    assert "more than 12 months delinquent" in by["2 OWING WAY"].floor_question and by["2 OWING WAY"].lien_days == 522
    assert "foreclosure is barred" in by["3 FRESH WAY"].floor_question
    assert "Civil Code 5660" in by["4 LATE WAY"].next_step and "Civil Code 5673" in by["4 LATE WAY"].next_step
    assert by["4 LATE WAY"].as_dict()["pastDueCents"] == 720000
