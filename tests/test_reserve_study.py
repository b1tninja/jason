"""The reserve study reader: the statutory disclosure from any preparer, and California Builder Services' tables."""

from __future__ import annotations

from datetime import date

from jason.community.reserve_study import StudyLevel, read_disclosure, read_pages
from jason.tasks.reserves import checks, site_visit_due

COVER = """1446 Tollhouse Rd, Suite 101 • Clovis, CA 93611
RESERVE ANALYSIS REPORT
Mystique Community Association
Update | FY26
October 23, 2025
"""

DISCLOSURE = """CALIFORNIA BUILDER SERVICES • 559.473.2690
PAGE 1-1
Assessment and Reserve Funding Disclosure Summary
for the Fiscal Year Ending 2026
(1) The regular assessment per ownership interest is $310.00 per Month.
(3) Based upon the most recent reserve study and other information available to the board of directors, will currently
projected reserve account balances be sufficient at the end of each year to meet the association's obligation for repair
and/or replacement of major components during the next 30 years?
Yes   X  No _____
(6) Based on the method of calculation in paragraph (4) of subdivision (b) of Section 5570, the estimated amount required
in the reserve fund at the end of the current fiscal year is $609,887, based in whole or in part on the last reserve study.
The projected reserve fund cash balance at the end
of the current fiscal year is $265,272, resulting in reserves being 43% funded at this date.
PAGE 1-2
(7) Year Estimated Reserve
Amount Required
2026 $609,887
2027 $659,917
If the reserve funding plan approved by the association is implemented, the projected reserve fund cash balance in each of
those years will be:
Year Projected Reserve Fund Balance Percent Funded
2026 $265,272 43%
2027 $288,376 44%
Note: At the time this summary was prepared, the assumed long-term before-tax interest
rate earned on reserve funds was 0.05% per year, and the assumed long-term inflation rate to be applied to major
component repair and replacement costs was 3.5% per year.
"""

SUMMARY = """Current Assessment Funding Model Summary
CALIFORNIA BUILDER SERVICES • 559.473.2690
Budget Year Beginning January 1, 2026
Total Units 81
Report Parameters
Inflation 3.50%
Annual Assessment Increase 5.00%
2026 Beginning Balance $195,572
Required Monthly Contribution $7,364.67
"""

PROJECTION = """Current Assessment Funding Model Projection
CALIFORNIA BUILDER SERVICES • 559.473.2690
Current Annual Annual Annual Ending Funded Percent
Year Cost Contribution Interest Expenditures Reserves Reserves Funded
2026 1,673,060 88,376 79 18,754 265,272 609,887 43%
2027 1,731,617 92,795 86 69,777 288,376 659,917 44%
2033 2,128,599 124,354 187 592,412 1,132,461 52%
"""

COMPONENTS = """Mystique Community Association
Component Funding Summary
CALIFORNIA BUILDER SERVICES • 559.473.2690
PAGE 2-3
Cost
Future
Description
Paving
Paving - Asphalt; Overlay & Replacement 218,050
35
16
5,815
218,050
68,265
Paving - Asphalt; Slurry Seal & Repairs
15,165
5
3
5,471
1,381
9,694
5,471
     Paving - Total
$5,471
$7,196
$227,744
$73,736
Grounds Components
Fire Hydrants - Replacement unfunded
Grand Total: $233,215 $5,471 $7,196 $227,744 $73,736
Percent Fully Funded   38%
"""

EXPENDITURES = """Mystique Community Association
Annual Expenditure Detail
CALIFORNIA BUILDER SERVICES • 559.473.2690
PAGE 2-5
Description Expenditures
Replacement Year   2026
Building Components
Building - Balcony; Resurfacing 1,500
Equipment
Equipment - Backflow Sleeves; Replacement
14,154
Total for 2026 $15,654
Replacement Year   2027
Painting
Painting - Bldg. Exteriors; Stucco (Bldg 1 & 7) 69,777
Total for 2027 $69,777
"""


def _study():
    return read_pages([COVER, DISCLOSURE, SUMMARY, PROJECTION, COMPONENTS, EXPENDITURES], "ud26.pdf")


def test_disclosure_reads_the_statutory_figures() -> None:
    d = read_disclosure(DISCLOSURE)
    assert d.fiscal_year == 2026 and d.assessment_per_month_cents == 31000 and d.sufficient_for_30_years is True
    assert d.required_end_of_year_cents == 60988700 and d.projected_end_of_year_cents == 26527200 and d.percent_funded == 0.43
    assert d.interest_rate == 0.0005 and d.inflation_rate == 0.035
    assert [(y.year, y.required_cents, y.projected_cents, y.percent_funded) for y in d.next_years] == [
        (2026, 60988700, 26527200, 0.43), (2027, 65991700, 28837600, 0.44)]


def test_california_builder_services_reads_plan_components_and_schedule() -> None:
    s = _study()
    assert s.preparer == "California Builder Services" and s.prepared == date(2025, 10, 23)
    assert s.fiscal_year == 2026 and s.units == 81 and s.level is StudyLevel.UPDATE_WITHOUT_SITE_VISIT
    assert s.beginning_balance_cents == 19557200 and s.monthly_contribution_cents == 736467 and s.contribution_increase == 0.05
    assert s.annual_contribution_cents == 8837600
    # A year with no expenditures prints seven numbers, not eight.
    assert [(r.year, r.expenditures_cents, r.ending_balance_cents) for r in s.projection] == [
        (2026, 1875400, 26527200), (2027, 6977700, 28837600), (2033, 0, 59241200)]
    overlay, slurry, hydrants = s.components
    assert (overlay.future_cost_cents, overlay.useful_life_years, overlay.remaining_life_years, overlay.distribution_cents,
            overlay.contribution_cents, overlay.fully_funded_cents) == (21805000, 35, 16, 0, 581500, 6826500)
    assert slurry.distribution_cents == 547100 and slurry.liability_cents == 969400 and slurry.category == "Paving"
    assert hydrants.unfunded and hydrants.category == "Grounds Components"
    assert [(e.year, e.category, e.description, e.cost_cents) for e in s.expenditures_in(2026)] == [
        (2026, "Building Components", "Building - Balcony; Resurfacing", 150000),
        (2026, "Equipment", "Equipment - Backflow Sleeves; Replacement", 1415400)]


def test_checks_flag_a_wrong_unit_count_and_a_plan_the_next_study_did_not_start_from() -> None:
    from dataclasses import replace

    fy26 = _study()
    fy25 = replace(fy26, fiscal_year=2025, units=61, level=StudyLevel.FULL, prepared=date(2024, 12, 12),
                   disclosure=replace(fy26.disclosure, projected_end_of_year_cents=34527100))
    found = checks([fy25, fy26], 81)
    assert any("counts 61 units" in c for c in found)
    assert any("starts 2026 at $195,572 (-$149,699)" in c for c in found)
    assert site_visit_due([fy25, fy26]) == {"lastSiteVisitStudy": "2024-12-12", "lastSiteVisitFiscalYear": 2025,
                                           "nextSiteVisitForFiscalYear": 2028, "nextReviewForFiscalYear": 2027}


def test_helsing_and_browning_plans_read_their_own_layouts() -> None:
    helsing = read_pages([
        "Mystique HOA\nLevel III Funding Update (W/O Site Visit)\nJanuary 01, 2024\nby\nThe Helsing Group, Inc.\nNovember 8, 2023\n",
        "California Disclosure Notes\nFor Fiscal Year Ending: 12/31/2024\nFor our Fiscal Year starting 1/1/24 our Reserve Study shows a current fund balance of $201,068\n",
        "California Disclosure Notes\n7) Reserve Fund Projections (Summary) over the next 30 Years\n"
        "$130,872 \n$573,913 \n 22.8% \n$84,168.04 \n$0.00 \n$3,905 \n$-158,269\n2024\n"
        "$225,972 \n$708,354 \n 31.9% \n$90,901.48 \n$0.00 \n$4,198 \n$0\n2025\n",
    ])
    assert helsing.preparer == "The Helsing Group" and helsing.prepared == date(2023, 11, 8) and helsing.fiscal_year == 2024
    assert helsing.beginning_balance_cents == 20106800 and helsing.annual_contribution_cents == 8416804
    assert [(r.year, r.expenditures_cents, r.ending_balance_cents) for r in helsing.projection] == [(2024, 15826900, 13087200), (2025, 0, 22597200)]

    browning = read_pages([
        "Reserve Study Transmittal Letter\nSeptember 26, 2022\nBrowning Reserve Group, LLC (BRG)\nUpdate w/o Site Visit Review\n",
        "Table of Contents\nSection IV\n30 Year Reserve Funding Plan Including Fully Funded Balance and % Funded\n",
        "California Assessment and Reserve Funding Disclosure For the Fiscal Year Ending 2023\n",
        "Section IV\n30 Year Reserve Funding Plan Including Fully Funded Balance and % Funded\n"
        "2022\n200,716\n378,731\n51.5%\n68,525\n59,900\n0\n2,946\n195,037\n"
        "2023\n195,037\n388,219\n51.8%\n59,394\n62,476\n0\n2,949\n201,068\n",
    ])
    assert browning.preparer == "Browning Reserve Group" and browning.fiscal_year == 2023
    assert browning.beginning_balance_cents == 19503700 and browning.annual_contribution_cents == 6247600
    assert browning.year(2023).ending_balance_cents == 20106800


def test_treasurer_reports_supply_the_reserve_accounts_and_check_a_study(tmp_path) -> None:
    import sqlite3
    from dataclasses import replace

    from jason.tasks.reserves import report_checks, treasurer_reserves

    (tmp_path / "library" / "text").mkdir(parents=True)
    with sqlite3.connect(tmp_path / "library" / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, period TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Treasurer''s Report - 2025-12.pdf', 'treasurer_report', '2025-12')")
    (tmp_path / "library" / "text" / "1.txt").write_text(
        "Balance Sheet\n"
        "                C/D Settlement - 12Mth CD 7/3/26 (First Citizens Bank)\n$165,123.03\n"
        "                Reserve Account (Chase)\n$1,049.15\n"
        "                Reserve C/D (Chase)\n$181,858.18\n"
        "Total Assets\n$400,000.00\n"
        "Transfer to Reserve C/D\n(Chase)\n$80,000.00\n"
        "C/D (Chase)\n$80,000.00\n", encoding="utf-8")
    reports = treasurer_reserves(tmp_path)
    assert reports["2025-12"]["totalCents"] == 34803036 and len(reports["2025-12"]["accounts"]) == 3
    study = replace(_study(), fiscal_year=2026, beginning_balance_cents=19557200)
    (finding,) = report_checks([study], reports)
    assert "short by $152,458" in finding


def test_helsing_and_browning_component_tables() -> None:
    from jason.community.reserve_study import BrowningReserveGroup, HelsingGroup

    helsing = HelsingGroup._components([
        "Detailed Component List\nCurrent\nMystique HOA\nAsphalt, Repair Fund\nDrives & Parking\n$ 2.60\n20\n5\n20\n$ 128,895\n$ 156,820\n"
        "49,575 S.F.\nWest Drive (50%)\n$ 1.30\n20\n5\n20\n$ 12,059\n$ 14,671\n9,276 S.F.\nSubtotal for Asphalt, Repair Fund :\n"
        "$ 140,954\n$ 171,492\nAsphalt, Striping\nParking\n$ 1,500.00\n5\n1\n6\n$ 1,500\n$ 1,560\n1 Lot\n"])
    assert [(c.description, c.current_cost_cents, c.future_cost_cents, c.remaining_life_years) for c in helsing] == [
        ("Asphalt, Repair Fund: Drives & Parking", 12889500, 15682000, 5),
        ("Asphalt, Repair Fund: West Drive (50%)", 1205900, 1467100, 5),
        ("Asphalt, Striping: Parking", 150000, 156000, 1)]

    browning = BrowningReserveGroup._components([
        "Component Tabular Listing\nPaving\n01000 -\n100 - Asphalt: Sealing\n49,575\n$.22/SqFt\n5\n$10,827\n1\nDrives & Parking\n"
        "210 - Asphalt: Ongoing Repairs\n9,276\n$3.64/SqFt\n5\n$506\n1\n(2%)\nShared West Drive\n"])
    assert [(c.description, c.current_cost_cents, c.useful_life_years, c.remaining_life_years) for c in browning] == [
        ("Paving: Asphalt: Sealing", 1082700, 5, 1), ("Paving: Asphalt: Ongoing Repairs (2%)", 50600, 5, 1)]


def test_an_expenditure_schedule_is_read_by_the_words_positions():
    from jason.community.reserve_study import schedule_expenditures

    def word(x, y, text):
        return (x, y - 4, x + 30, y + 4, text, 0, 0, 0)

    page = [word(250, 40, "Estimated"), word(300, 40, "Expenditure"), word(360, 40, "Schedule"), word(420, 40, "from"),
            word(188, 74.4, "2024"), word(236, 75, "2025"), word(294, 75, "2026")]
    # A name with one amount on its line and the rest on the line under it; then one on a single line.
    page += [word(27, 90, "Asphalt,"), word(59, 90, "Sealcoat"), word(294, 90, "$0"),
             word(188, 93, "$33,829"), word(236, 93, "$0")]
    page += [word(27, 105, "Fire"), word(43, 105, "Safety"), word(188, 105, "$1,560"), word(236, 105, "$0"), word(294, 105, "$18,250")]
    page += [word(113, 120, "Grand"), word(139, 120, "Total:"), word(183, 120, "$35,390"), word(236, 120, "$0"), word(294, 120, "$18,251")]
    found = schedule_expenditures([page, [word(10, 10, "Unrelated")]])
    assert [(e.year, e.description, e.cost_cents) for e in found] == [
        (2024, "Asphalt, Sealcoat", 3382900), (2024, "Fire Safety", 156000), (2026, "Fire Safety", 1825000)]
    assert found[0].category == "Asphalt"
