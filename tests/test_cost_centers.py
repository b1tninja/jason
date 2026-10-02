"""The Association Common Areas, the two assessment cost centers, and how the governing models read them."""

from __future__ import annotations

from datetime import date

from jason.community import mystique
from jason.community.base import CostCenter
from jason.community.document_models import ModelContext, read
from jason.community.symbols import DocumentKind

ANNEXATION = """DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR MYSTIQUE, PHASE 7
Declarant hereby annexes the real property more particularly described as follows (the "Annexed Property"): Association Common Area
designated A.C.A. 4, Condominium Common Area designated C.C.A. 4, Units 18 through 27, inclusive, together with all Exclusive Use Common Areas.
1.8. Common Area. Each Owner of a Unit within the Annexed Property shall have a 1110th undivided interest in the Condominium Common Area.
1.3. (a) Assessment Components. (i) General Budgeted Expenses. The "General Assessment Component" of the Regular Assessments shall consist of
the budgeted expenses of the Association. (ii) Cost Center Assessment Expenses. The "Phases 1 and 2 Property Cost Center Assessment Component"
and the "Annexed Property Cost Center Assessment Component" of the Regular Assessments.
(b) Allocation of Regular Assessments. (ii) Cost Center Assessment Component. The Phases 1 and 2 Property Cost Center Assessment Component
of Regular Assessments shall be allocated and assessed equally among the Units within the Phases 1 and 2 Property.
(c) Commencement of Assessments. Regular Assessments shall commence with respect to the Annexed Property on the first day of the first month
following the month in which the first Unit is conveyed to a person other than Declarant.
(d) Cost Center Allocation Due to Distinction Between ACA 3 and ACA 8 Buildings and Annexed Property. (i) Segregation of Expenses for
Buildings. The Common Area building structures located within Association Common Area 3 and Association Common Area 8, as such areas are
shown and described in the Condominium Plan, were originally constructed by the first builder in 2008. The statutory period for asserting
construction defects for all Common Area building Improvements located within the Phases 1 and 2 Property has expired. The
Association shall allocate the obligation for certain expenses described in this Section to either the Phases 1 and 2 Property Owners
only or the Annexed Property Owners only.
(iii) Cost Center For Expenses Attributable to Annexed Property. The expenses associated with the maintenance, repair, replacement and
insurance of Common Area building Improvements within the Annexed Property shall be included in the "Annexed Property Cost Center".
"""

DECLARATION = """RESTATED DECLARATION OF COVENANTS, CONDITIONS AND RESTRICTIONS FOR MYSTIQUE
1.10 Common Area. "Common Area" shall mean all of the property comprising the Development, excluding the Units. Within the Development there
are two(2) types of Common Area based on ownership. (a) Association Common Area. The Association Common Area, as referred to in the Plan,
shall be owned in fee by the Association. The Association Common Area includes the entire dwelling structure containing Residences, but
excludes the individual Units and Condominium Common Area. In addition, Lot A, as shown on the Subdivision Map, is Association Common Area.
(b) Condominium Common Area. The Condominium Common Area, commonly referred to as "Cloud" Common Area, are the air spaces between elevations
150 feet and 160 feet above the ground level of each Association Common Area shown on the Plan. Each Owner shall have, as appurtenant to the
Owner's Unit, an equal undivided interest in the Condominium Common Area located above the Owner's Unit.
1.11 Condominium. "Condominium" shall mean an estate in real property.
"""


def test_the_specification_puts_aca_3_and_8_in_their_own_cost_center():
    m = mystique()
    centers = {a.number: a.cost_center for a in m.association_common_areas()}
    assert [n for n, c in centers.items() if c is CostCenter.PHASES_1_AND_2] == [3, 8]
    assert all(c is CostCenter.ANNEXED for n, c in centers.items() if n not in (3, 8))
    assert {r.center for r in m.cost_centers()} == set(CostCenter)


def test_the_annexation_model_reads_the_cost_centers_and_share():
    reading = read(DocumentKind.ANNEXATION, ANNEXATION, ModelContext(mystique(), None, date(2026, 9, 29), "Annexation - Phase 7.pdf"))
    r = reading.record
    assert (r.association_common_areas, r.first_unit, r.last_unit, r.undivided_interest) == ((4,), 18, 27, "1/10")
    assert r.cost_centers and r.cost_center_clause and r.phases_1_2_acas == (3, 8) and r.allocated_equally and r.defect_period_expired
    assert r.assessment_components == ("general", "phases 1 and 2 property cost center", "annexed property cost center")
    assert r.annexed_center_expenses.startswith("the maintenance, repair, replacement and insurance")
    codes = {f.code for f in reading.findings}
    assert {"cost-centers", "phases-1-2-clause-skipped"} <= codes   # Phase 7 goes from (i) to (iii), as recorded
    assert not codes & {"aca-units-differ", "aca-phase-differs", "aca-cost-center", "phases-1-2-acas-differ", "cca-share-differs"}


def test_the_declaration_model_reads_the_two_kinds_of_common_area():
    reading = read(DocumentKind.DECLARATION, DECLARATION, ModelContext(mystique(), None, date(2026, 9, 29), "CCRs.pdf"))
    r = reading.record
    assert r.aca_owned_in_fee and r.aca_includes_structure and r.lot_a_is_aca and r.cca_elevations == (150, 160)
    assert r.cca_share_text.startswith("Each Owner shall have")


def test_the_review_finds_flat_charges_and_no_budget_line(tmp_path):
    import json
    import sqlite3

    from jason.tasks.cost_centers import review

    (tmp_path / "payhoa" / "budgets").mkdir(parents=True)
    (tmp_path / "payhoa" / "budgets" / "2026.json").write_text(json.dumps({"expense": [{"name": "Landscaping"}], "income": []}), encoding="utf-8")
    with sqlite3.connect(tmp_path / "payhoa" / "ledger.db") as conn:
        conn.execute("CREATE TABLE entries (month TEXT, seq INTEGER, type TEXT, account TEXT, day TEXT, description TEXT, category TEXT, memo TEXT, "
                     "vendor TEXT, debit INTEGER, credit INTEGER, balance INTEGER, starting INTEGER)")
        m = mystique()
        # One address in a Phases 1 and 2 building (8) and one in an annexed building (2), charged the same.
        eight = next(b for b in m.buildings() if int(b.number) == 8)
        two = next(b for b in m.buildings() if int(b.number) == 2)
        for building in (eight, two):
            address = f"{building.low} {building.street.value}"
            conn.execute("INSERT INTO entries VALUES ('2026-01', 0, 'Accounts Receivable', ?, '2026-01-01', ?, 'Assessments', '', '', 28500, 0, 28500, 0)",
                         (address, f"{address}: Regular Assessment (monthly)"))
    result = review(tmp_path, mystique())
    assert result["charges"]["2026"] == {"annexed property": {28500: 1}, "phases 1 and 2 property": {28500: 1}}
    assert any("same monthly assessment" in f for f in result["findings"]) and any("carry no cost center line" in f for f in result["findings"])
    assert [c["units"] for c in result["centers"]] == [24, 57]


def test_the_phase_3_heading_of_1_3_d_ii_reads():
    # Phase 3 heads (ii) without "Attributable to", and OCR prints the 1 as I.
    text = ANNEXATION.replace("(iii) Cost Center For Expenses Attributable to Annexed Property.",
                              "(ii) Establishment of Cost Center For Expenses the Phases I and 2 Property. The expenses associated with the "
                              "maintenance of Common Area building Improvements within the Phases 1 and 2 Property shall be designated as the "
                              "\"Phases 1 and 2 Property Cost Center\". (iii) Cost Center For Expenses Attributable to Annexed Property.")
    reading = read(DocumentKind.ANNEXATION, text, ModelContext(mystique(), None, date(2026, 9, 29), "Annexation - Phase 3.pdf"))
    codes = {f.code for f in reading.findings}
    assert reading.record.phases_1_2_center_text and not reading.record.phases_1_2_clause_skipped
    assert not codes & {"phases-1-2-clause-skipped", "phases-1-2-clause-missing"}


def test_budgeted_assessments_sum_the_monthly_items(tmp_path):
    import json

    from jason.tasks.cost_centers import budgeted_assessments

    folder = tmp_path / "payhoa" / "budgets"
    folder.mkdir(parents=True)
    items = [{"amount": 2308500, "month": m, "deletedAt": None} for m in range(1, 13)] + [{"amount": 99, "month": 1, "deletedAt": "x"}]
    tree = {"income": [{"name": "Assessments", "budgetItems": items}, {"name": "Interest", "budgetItems": [{"amount": 5}]}]}
    (folder / "2026.json").write_text(json.dumps(tree), encoding="utf-8")
    totals = budgeted_assessments(tmp_path)
    assert totals == {2026: 27702000} and totals[2026] / 81 / 12 == 28500   # $277,020 over 81 units: $285 a month
