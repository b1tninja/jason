"""The financial document models: bank statements, treasurer's reports, the prior manager's statements, budgets and annual
disclosures, the CPA review, tax bills, and reserve studies. Every fixture is made up in the real layouts."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from types import SimpleNamespace

from jason.community.base import AccountPurpose, BankAccount, Policy, ReserveLine
from jason.community.document_models import ModelContext, Severity, read
from jason.community.models.financial_reserve import split_pages
from jason.community.models.financial_tax import stored_number
from jason.community.symbols import DocumentKind, PolicyKind


class Spec:
    """A made-up association: 81 units, two Chase accounts, one common-area parcel, a flood policy."""

    def units(self):
        return tuple(f"9000000002{i:04d}" for i in range(81))

    def common_areas(self):
        return ("90000000010001",)

    def parcels(self):
        return self.units() + self.common_areas()

    def bank_accounts(self):
        return (BankAccount("1111", AccountPurpose.OPERATING, "JPMorgan Chase", "Operating"),
                BankAccount("2222", AccountPurpose.RESERVE, "JPMorgan Chase", "Reserve"))

    def reserve_budget_lines(self):
        return {ReserveLine.CONTRIBUTION: "Transfer to Reserves"}

    def insurance(self):
        return SimpleNamespace(policies=(Policy(PolicyKind.MASTER), Policy(PolicyKind.FLOOD)))


def ctx(tmp_path=None, **kw) -> ModelContext:
    return ModelContext(community=Spec(), data_dir=tmp_path, today=date(2026, 9, 29), **kw)


def codes(reading) -> dict[str, Severity]:
    return {f.code: f.severity for f in reading.findings}


# Bank statements (Chase).

OPERATING = """ 000000999991111
CUSTOMER SERVICE INFORMATION
JPMorgan Chase Bank, N.A.
P O Box 182051
Columbus, OH 43218 - 2051
August 01, 2025 through August 29, 2025
Account Number:
Beginning Balance
$10,000.00
Ending Balance
23
$11,475.00
EXAMPLE COMMUNITY ASSOCIATION
Chase Business Complete Checking
Deposits and Additions
10
5,000.00
Checks Paid
1
-100.00
Electronic Withdrawals
11
-3,410.00
Fees
1
-15.00
CHECKING SUMMARY
"""

RESERVE = """ 000000999992222
JPMorgan Chase Bank, N.A.
August 01, 2025 through August 29, 2025
Beginning Balance
$50,000.00
Ending Balance
2
$45,000.00
Chase Performance Business Checking
Deposits and Additions
1
7,000.00
Electronic Withdrawals
1
-12,000.00
The monthly service fee of $30.00 was waived this period because you maintained a relationship balance.
CHECKING SUMMARY
Total Service Charge
$0.00
"""


def test_chase_statement_reads_the_summary_and_checks_the_reconciliation(tmp_path) -> None:
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "reconciliations.json").write_text(json.dumps({"reconciliations": [
        {"last4": "1111", "end": "2025-07-31", "startingBalance": 900000, "endingBalance": 1000000},
        {"last4": "1111", "end": "2025-08-29", "startingBalance": 1000000, "endingBalance": 1147000}]}))
    reading = read(DocumentKind.BANK_STATEMENT, OPERATING, ctx(tmp_path, name="20250829-statements-1111-.pdf"))
    s = reading.record
    assert reading.complete and s.account_last4 == "1111" and s.product == "Chase Business Complete Checking"
    assert (s.period_start, s.period_end) == (date(2025, 8, 1), date(2025, 8, 29))
    assert (s.beginning_cents, s.ending_cents, s.deposits_cents, s.checks_paid_cents, s.fees_cents) == (1_000_000, 1_147_500, 500_000, -10_000, -1_500)
    assert s.purpose == "operating" and s.transactions == 23
    found = codes(reading)
    assert "balance-does-not-foot" not in found
    assert found["service-fee"] is Severity.CHECK
    assert found["reconciliation-ending-differs"] is Severity.PROBLEM


def test_chase_reserve_statement_flags_withdrawals_and_a_misnamed_file() -> None:
    reading = read(DocumentKind.BANK_STATEMENT, RESERVE, ctx(name="20250830-statements-3333-.pdf"))
    s = reading.record
    assert s.purpose == "reserve" and s.service_fee_waived and s.withdrawals_cents == -1_200_000
    found = codes(reading)
    assert found["reserve-withdrawal"] is Severity.CHECK
    assert found["name-account-mismatch"] is Severity.PROBLEM
    assert found["name-date-mismatch"] is Severity.CHECK
    assert "service-fee" not in found
    broken = RESERVE.replace("$45,000.00", "$46,000.00")
    assert codes(read(DocumentKind.BANK_STATEMENT, broken, ctx()))["balance-does-not-foot"] is Severity.PROBLEM


def test_chase_fee_page_charge_is_debited_on_the_next_statement() -> None:
    fee_page = RESERVE.replace("Total Service Charge\n$0.00\n", """TRANSACTIONS FOR SERVICE FEE CALCULATION
Total Service Charge (Will be assessed on 9/3/25)
$25.00
Waived Monthly Service Fee
0
$30.00
$0.00
Stop Payment - Online
1
0
1
$25.00
$25.00
Total Service Charges
$25.00
""")
    reading = read(DocumentKind.BANK_STATEMENT, fee_page, ctx())
    s = reading.record
    assert (s.service_charge_cents, s.service_charge_assessed, s.service_charges) == (2_500, date(2025, 9, 3), ("Stop Payment - Online",))
    found = codes(reading)
    assert found["service-charge-next-period"] is Severity.INFO and "service-fee" not in found


# PayHOA's treasurer's report.

TREASURER = """Example Community Association
Treasurer's Report - 2025-11
Bank Reconciliation: Reserve Account
Bank Reconciliation: Operating Account
General Ledger: 11/01/2025 - 11/30/2025
Profit vs Loss Summary: 01/01/2025 - 11/30/2025
Budget vs Actual Summary: 01/01/2025 - 11/30/2025
Aging of Accounts as of: 11/30/2025
Balance Sheet as of: 11/30/2025
Included Reports:

Example Community Association
Balance Sheet
As of Nov 30, 2025
Label
Total
Assets
        Bank Accounts
                CD 7/3/26 (Other Bank)
$100,000.00
                Operating Account (Chase)
$30,000.00
                Reserve Account (Chase)
$90,000.00
        Total Bank Accounts
$220,000.00
        Other Assets
                Accounts Receivable
$5,000.00
        Total Other Assets
$5,000.00
Total Assets
$225,000.00
Liabilities and Equity
        Liabilities
                Accounts Receivable - Prepaids
$2,000.00
                Total Liabilities
$2,000.00
        Equity
                Equity
$223,000.00
                Total Equity
$223,000.00
Total Liabilities and Equity
$225,000.00
Generated 12-03-2025 08:25am PST
Page 1 of 1

Example Community Association
Aging of Accounts
As of Nov 30, 2025
Unit
Total Due
Totals
$5,000.00
$0.00

Example Community Association
Profit vs Loss Cash
Jan 1, 2025 - Nov 30, 2025
Category
Total
Income
        Assessments
$270,000.00
Total Income
$270,000.00
Expenses
        Landscaping
$265,000.00
Total Expenses
$265,000.00
Net Total
$5,000.00
Generated 12-03-2025 08:25am PST

Example Community Association
Bank Reconciliation: Operating Account
Nov 1, 2025 - Nov 28, 2025
Statement beginning balance . . . . . . . . . . $19,000.00
Checks and payments cleared (47) . . . . . . . . $22,000.00
Deposits and other credits cleared (16) . . . . . $23,000.00
Statement ending balance . . . . . . . . . . . . $20,000.00
Checks and payments not reconciled (0) . . . . . $0.00
Deposits and other credits not reconciled (0) . . $0.00
Register Balance as of 11-28-2025 . . . . . . . . $20,000.00

Example Community Association
Bank Reconciliation: Reserve Account
Oct 1, 2025 - Oct 31, 2025
Statement beginning balance . . . . . . . . . . $85,000.00
Checks and payments cleared (0) . . . . . . . . $0.00
Deposits and other credits cleared (1) . . . . . $5,000.00
Statement ending balance . . . . . . . . . . . . $91,000.00
"""


def test_a_treasurers_report_named_redacted_that_still_lists_units_is_flagged() -> None:
    board = TREASURER + ("\nAging of Accounts as of: 11/30/2025\nUnit\n1-30 Days Past Due\n90+ Days Past Due\n"
                         "3101 Enchanted Walk\n$315.87\nTotals\n$315.87\n")
    named = read(DocumentKind.TREASURER_REPORT, board, ctx(name="Treasurer's Report - 2025-11_Redacted.pdf"))
    assert (named.record.redacted, named.record.aging_units) == (False, 1)
    assert codes(named)["redaction-incomplete"] is Severity.PROBLEM
    board_copy = read(DocumentKind.TREASURER_REPORT, board, ctx(name="Treasurer's Report - 2025-11.pdf"))
    assert "member-receivables" in codes(board_copy) and "redaction-incomplete" not in codes(board_copy)
    member = read(DocumentKind.TREASURER_REPORT, TREASURER, ctx(name="Treasurer's Report - 2025-11_Redacted.pdf"))
    assert member.record.redacted and not {"redaction-incomplete", "member-receivables"} & set(codes(member))


def test_treasurers_report_reads_the_packet_and_catches_a_misfiled_copy(tmp_path) -> None:
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "balance-sheets.json").write_text(json.dumps({"sheets": {"2025-11": {"asOf": "2025-11-30", "accounts": [
        {"section": "Bank Accounts", "label": "Operating Account (Chase)", "cents": 2_900_000}]}}}))
    reading = read(DocumentKind.TREASURER_REPORT, TREASURER, ctx(tmp_path, name="Treasurer's Report - 2025-06.pdf", period="2025-06"))
    r = reading.record
    assert reading.complete
    assert (r.period, r.title_period, r.generated) == ("2025-11", "2025-11", date(2025, 12, 3))
    assert (r.total_bank_cents, r.total_assets_cents, r.total_liabilities_equity_cents) == (22_000_000, 22_500_000, 22_500_000)
    assert [a.label for a in r.reserve_accounts] == ["CD 7/3/26 (Other Bank)", "Reserve Account (Chase)"]
    assert r.reserve_cents == 19_000_000 and r.receivable_cents == 500_000
    assert (r.income_cents, r.expenses_cents, r.net_cents) == (27_000_000, 26_500_000, 500_000)
    assert [x.account for x in r.reconciliations] == ["Operating Account", "Reserve Account"]
    found = codes(reading)
    assert found["copy-under-another-month"] is Severity.PROBLEM
    assert found["reconciliation-does-not-foot"] is Severity.PROBLEM    # 85,000 + 5,000 is not 91,000
    assert found["reconciliation-other-month"] is Severity.CHECK        # the reserve reconciliation is October's
    assert found["reserve-at-unnamed-bank"] is Severity.CHECK
    assert found["ledger-changed-since"] is Severity.CHECK
    assert "balance-sheet-does-not-balance" not in found and "net-does-not-foot" not in found


def test_early_treasurers_report_takes_january_from_a_february_first_balance_sheet() -> None:
    text = TREASURER.replace("Treasurer's Report - 2025-11", "Treasurer's Report").replace("As of Nov 30, 2025", "As of February 01, 2024") \
        .replace("General Ledger: 11/01/2025 - 11/30/2025", "General Ledger 01/01/2024 - 01/31/2024").replace("Generated 12-03-2025", "Generated 09-05-2024")
    reading = read(DocumentKind.TREASURER_REPORT, text, ctx(period="2024-01"))
    assert reading.record.period == "2024-01"
    assert codes(reading)["generated-later"] is Severity.CHECK
    old = text.replace("                Reserve Account (Chase)\n$90,000.00", "                Old Reserve Account\n$90,000.00") \
        .replace("                CD 7/3/26 (Other Bank)\n$100,000.00\n", "")
    assert [(a.label, a.cents) for a in read(DocumentKind.TREASURER_REPORT, old, ctx()).record.reserve_accounts] == [("Old Reserve Account", 9_000_000)]


def test_treasurers_report_index_after_its_heading() -> None:
    index = "\n".join(TREASURER.splitlines()[2:9])
    text = TREASURER.replace(index + "\nIncluded Reports:", "Included Reports:\n" + index)
    assert text.startswith("Example Community Association\nTreasurer's Report - 2025-11\nIncluded Reports:\n")
    r = read(DocumentKind.TREASURER_REPORT, text, ctx()).record
    assert len(r.included) == 7 and r.included[0] == "Bank Reconciliation: Reserve Account"


# The Helsing Group's monthly financial statements.

HELSING = """Example Community Association
Monthly Financial Statements
December 2023
The following reports are included:
Balance Sheet
Budget vs. Actual Comparison Report
PLEASE NOTE THIS MONTH'S SCHEDULED
RESERVE CONTRIBUTION WAS NOT
MADE DUE TO LOW FUNDS IN THE
OPERATING ACCOUNT.

Example Community Association
GL Balance Sheet Standard
Transaction 12/31/2023
Operating
Reserve
Total
Assets
Cash
Operating
(500.00)
(500.00)
Total Cash
(500.00)
(500.00)
Reserve
Reserve
100,000.00
100,000.00
Total Reserve
100,000.00
100,000.00
Other Receivable
A/R Reserve Fund
6,000.00
6,000.00
Total Assets
10,000.00
106,000.00
116,000.00
Liabilities & Equity
Liability
Due to Reserve
6,000.00
6,000.00
Total Liability
16,000.00
16,000.00
Total Liabilities & Equity
10,000.00
106,000.00
116,000.00
1/22/2024 9:16:19 AM
Page 1 of 1

Example Community Association
Budget Comparison Standard Code Category
Transaction 12/1/2023 To 12/31/2023 11:59:00 PM
Current Month Operating
Year to Date Operating
TOTAL Other Revenue
100.00
0.00
100.00
0.00%
1,000.00
0.00
1,000.00
0.00%
0.00
TOTAL Income
26,000.00
25,000.00
1,000.00
-4.00%
300,000.00
300,000.00
0.00
0.00%
300,000.00
Expense
91002    Reserve Contributio
0.00
6,000.00
6,000.00
100.00%
66,000.00
72,000.00
6,000.00
8.33%
72,000.00
TOTAL Expense
30,000.00
25,000.00
(5,000.00)
-20.00%
310,000.00
300,000.00
(10,000.00)
-3.33%
300,000.00
Excess Revenue / Expense
(4,000.00)
0.00
(4,000.00)
0.00%
(10,000.00)
0.00
(10,000.00)
0.00%
0.00
Current Month Reserve
"""


def test_helsing_statements_flag_the_due_to_reserve_and_the_missed_contribution() -> None:
    reading = read(DocumentKind.FINANCIAL_STATEMENT, HELSING, ctx(period="2023-12"))
    s = reading.record
    assert reading.complete and s.period == "2023-12" and not s.excerpt
    assert (s.operating_cash_cents, s.reserve_cash_cents, s.due_to_reserve_cents) == (-50_000, 10_000_000, 600_000)
    assert s.total_assets == (1_000_000, 10_600_000, 11_600_000)
    assert (s.reserve_contribution.ytd_actual_cents, s.reserve_contribution.ytd_budget_cents) == (6_600_000, 7_200_000)
    assert s.income.ytd_actual_cents == 30_000_000 and s.excess.ytd_actual_cents == -1_000_000
    assert s.notes and "RESERVE CONTRIBUTION WAS NOT MADE" in s.notes[0]
    found = codes(reading)
    assert found["due-to-reserve"] is Severity.PROBLEM
    assert found["reserve-contribution-short"] is Severity.PROBLEM
    assert found["manager-note"] is Severity.PROBLEM
    assert found["operating-cash-negative"] is Severity.PROBLEM
    assert found["packet-lacks-check"] is Severity.CHECK
    assert "balance-sheet-does-not-balance" not in found and "interfund-mismatch" not in found


# Budgets and the annual budget report.

PRO_FORMA = """Example Community Association
Pro Forma Budget
Budget - Monthly: 01/01/2026 - 12/31/2026
Budget Summary: 01/01/2026 - 12/31/2026
Included Reports:

Example Community Association
Budget Summary
Jan 1, 2026 - Dec 31, 2026
Category
Total
Income
        Assessments
$121,500.00
Total Income
$121,500.00
Expenses
        Landscaping
$30,000.00
        Transfer to Reserves
$40,000.00
        Contingency
$51,500.00
Total Expenses
$121,500.00
Net Total
$0.00
Generated 12-05-2025 05:47pm PDT
Page 1 of 1
"""


def monthly_budget() -> str:
    def row(label: str, month: str, total: str) -> str:
        return label + "\n" + "\n".join([month] * 12) + "\n" + total + "\n"

    return ("Example Community Association\nMonthly Budget\nJan 1, 2025 - Dec 31, 2025\nCategory\n"
            + "\n".join(f"{m} '25" for m in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))
            + "\nTotal\nIncome\n" + row("        Assessments", "$10,125.00", "$121,500.00") + row("Total Income", "$10,125.00", "$121,500.00")
            + "Expenses\n" + row("        Reserve Funding", "$4,000.00", "$48,000.00") + row("        Landscaping", "$6,500.00", "$78,000.00")
            + row("Total Expenses", "$10,500.00", "$126,000.00") + row("Net Total", "-$375.00", "-$4,500.00")
            + "Generated 11-14-2024 09:59pm PST\nPage 1 of 1\nDRAFT\n")


def test_payhoa_pro_forma_budget_reads_totals_and_the_reserve_line() -> None:
    reading = read(DocumentKind.BUDGET, PRO_FORMA, ctx())
    b = reading.record
    assert reading.model == "payhoa-budget" and reading.complete
    assert (b.fiscal_year, b.total_income_cents, b.total_expenses_cents, b.net_cents) == (2026, 12_150_000, 12_150_000, 0)
    assert b.reserve_lines == ("Transfer to Reserves",) and b.reserve_transfer_cents == 4_000_000
    assert b.monthly_assessments_cents == 1_012_500 and b.per_unit_monthly_cents == 12_500
    found = codes(reading)
    assert found["generated-after-window"] is Severity.CHECK
    assert found["operating-budget-only"] is Severity.INFO


def test_payhoa_monthly_draft_budget() -> None:
    reading = read(DocumentKind.BUDGET, monthly_budget(), ctx())
    b = reading.record
    assert b.layout == "payhoa monthly" and b.draft and b.fiscal_year == 2025
    assert (b.total_income_cents, b.total_expenses_cents, b.net_cents, b.reserve_transfer_cents) == (12_150_000, 12_600_000, -450_000, 4_800_000)
    found = codes(reading)
    assert found["draft-budget"] is Severity.CHECK and found["deficit-budget"] is Severity.CHECK
    assert found["distribution-window"] is Severity.INFO


DRE = """EXAMPLE COMMUNITY ASSOCIATION
ASSESSMENT SUMMARY
PER LOT PER MONTH
MARCH, 2018
Phase
Total Number of Lots
Budget
Reserves*
   7
 10 (70)
 $310.50
 $70.32
   8
 10 (80)
 $309.25
 $69.60
STATE OF CALIFORNIA
BUREAU OF REAL ESTATE
BUDGET WORKSHEET
RE 623 (Rev. 12/15)
"""


def test_dre_budget_worksheet_is_the_developers_budget() -> None:
    reading = read(DocumentKind.BUDGET, DRE, ctx())
    w = reading.record
    assert reading.model == "dre-budget-worksheet" and w.form == "RE 623"
    assert [(p.phase, p.cumulative_lots, p.monthly_cents) for p in w.phases] == [(7, 70, 31_050), (8, 80, 30_925)]
    assert w.prepared == "MARCH, 2018"
    found = codes(reading)
    assert found["developer-budget"] is Severity.INFO and found["lot-count"] is Severity.CHECK


INSURANCE = """I.
GENERAL LIABILITY INSURANCE
A.
Name of insurer:
II.
PROPERTY INSURANCE
A.
Name of insurer:
III.
EARTHQUAKE INSURANCE
None
IV.
FLOOD INSURANCE
None
V.
FIDELITY BOND INSURANCE
A.
Name of insurer:
Example Community Association
INSURANCE SUMMARY DISCLOSURE
Pursuant to Section 5300 (b)(9) of the California Civil Code, the Association is providing you with the following information.
Example Mutual Insurance Company
$1,000,000 per occurrence
09/28/2025 - 09/28/2026
This summary of the association's policies of insurance provides only certain information, as required by Section 5300 of the
Civil Code, and should not be considered a substitute for the complete policy terms and conditions contained in the actual
policies of insurance.
"""


def test_insurance_summary_says_no_flood_while_the_association_has_it() -> None:
    reading = read(DocumentKind.ANNUAL_DISCLOSURE, INSURANCE, ctx())
    s = reading.record
    assert reading.model == "insurance-summary-disclosure"
    assert {line.kind: line.none for line in s.lines} == {"general liability": False, "property": False, "earthquake": True,
                                                          "flood": True, "fidelity": False}
    assert s.insurers == ("Example Mutual Insurance Company",) and s.statutory_statement
    found = codes(reading)
    assert found["flood-listed-as-none"] is Severity.PROBLEM
    assert "no-insurance-statement" not in found


PACKET = """EXAMPLE COMMUNITY ASSOCIATION
Annual Disclosures
2025-2026
Annual Budget and Assessment
A copy of the adopted 2026 Annual Budget and Assessment is enclosed in accordance with Civil Code Section 5300.
Regular annual assessments for 2026 are hereby established and levied against each lot in the amount of $1,500. This amount
shall be collected in twelve (12) equal monthly installments in the amount of $125.00.
Pro Forma Budget (Civ. 5300(b)(1))
Right to Individual Delivery
Architectural
Example Community Association - Annual Disclosures - Civ. §5310
Annual Policy Statement
(1) Notice of Rights to Minutes of Board Meetings
(2) Name and Address of Person Designated to Receive Official Communications to the Association pursuant to Section 4035
(3) Secondary Address
(4) Designated Location for Posting of General Notices
Civ. §5300(b)(8) OUTSTANDING LOANS
The Association has no outstanding loans.
The reserve funding plan adopted by the board is summarized below.
The Board of Directors does not anticipate the levy of any special assessments.
Assessment and Reserve Funding Disclosure Summary
For the Fiscal Year Ending 2026
reserves being 55% funded at this date.
""" + PRO_FORMA


def test_annual_disclosure_packet_lists_the_items_it_lacks() -> None:
    reading = read(DocumentKind.ANNUAL_DISCLOSURE, PACKET, ctx())
    a = reading.record
    assert reading.model == "annual-budget-report"
    assert a.fiscal_year == 2026 and a.monthly_assessment_cents == 12_500 and a.annual_assessment_cents == 150_000
    assert a.budget is not None and a.budget.total_income_cents == 12_150_000
    assert {"5300(b)(1)", "5300(b)(3)", "5300(b)(5)", "5300(b)(8)", "5300(e)"} <= set(a.budget_report_items)
    assert "5310(a)(4)" not in a.policy_items and "5310(a)(10)" not in a.policy_items   # named only in the table of contents
    found = codes(reading)
    assert found["lacks-5300-b-4"] is Severity.CHECK and found["lacks-5310-a-4"] is Severity.CHECK
    assert found["packet-after-budget"] is Severity.CHECK   # its budget ran after December 1
    assert found["percent-funded"] is Severity.INFO
    assert found["no-full-plan-notice"] is Severity.CHECK


NEW_PACKET = """EXAMPLE COMMUNITY ASSOCIATION
Annual Disclosures
2025-2026
A copy of the full
 is available free online, and upon request for a
Reserve Study 2026.pdf
nominal fee of $25.
Example Community Association - Annual Disclosures - Civ. §5310

Annual Disclosures
The association is required by Civil Code §5300 to make certain disclosures to all members annually.
Accordingly you will find the following information and disclosures contained within:
Reserve Funding Mechanism
Anticipated Special Assessments
Charges for Documents Provided
Right to Individual Delivery

EXAMPLE COMMUNITY ASSOCIATION
Contact Information
Email hoa@example.org
Annual Policy Statement
(1) Notice of Rights to Minutes of Board Meetings
Notice of the violation and hearing will be by personal or individual delivery at least 10 days before the hearing.
Pro Forma Budget
Property Address
Check or Complete Applicable Column or Columns Below:
Insurance summary
Sections 5300 and 4525(a)(3)
15.00
Commercial Flood:
11/20/2025 - 11/20/2026 9000000001 Bldg 5 - $2,500,000 / Ded $2,000
12/03/2025 - 12/03/2026 9000000002 Bldg 3 - $3,000,000 / Ded $2,000
""" + INSURANCE


def test_association_packet_reads_items_after_its_contents_page() -> None:
    reading = read(DocumentKind.ANNUAL_DISCLOSURE, NEW_PACKET, ctx())
    a = reading.record
    assert a.full_plan_notice and a.flood_policies_enclosed == ("9000000001", "9000000002")
    assert "5300(b)(12)" in a.budget_report_items                       # the form, though its heading dropped out
    assert "5300(b)(6)" not in a.budget_report_items and "5300(b)(5)" not in a.budget_report_items   # contents page only
    assert "5310(a)(4)" not in a.policy_items                           # a hearing notice's delivery is not the option
    found = codes(reading)
    assert found["lacks-5300-b-6"] is Severity.CHECK and found["lacks-5310-a-4"] is Severity.CHECK
    flood = next(f for f in reading.findings if f.code == "flood-listed-as-none")
    assert "encloses 2 flood policies" in flood.message


CIRA = """Annual Budget Report - Resident Budget Package
Example Community Association
Annual Budget Report for Fiscal Year 2023
Prepared on: 12/15/2022
Annual Policy Statement
Revenue and Expense Budget Summary for FY 2023
  TOTAL of Revenues
$229,525
$81,515
$311,040
  TOTAL of Expenses
$229,525
$103,043
$332,568
"""


def test_cira_package_prepared_after_the_window() -> None:
    reading = read(DocumentKind.BUDGET, CIRA, ctx())
    a = reading.record
    assert reading.model == "annual-budget-report"
    assert (a.fiscal_year, a.prepared, a.total_revenue_cents, a.total_expenses_cents) == (2023, date(2022, 12, 15), 31_104_000, 33_256_800)
    assert codes(reading)["prepared-after-window"] is Severity.PROBLEM


FUND_BUDGET = """Annual Budget Report - Resident Budget Package
Example Community Association
Annual Budget Report for Fiscal Year 2023
Prepared on: 11/1/2022
Example Community Association
Revenue and Expense Budget Summary for FY 2023
Operating Fund
Replacement
Fund
Consolidated
  Revenues
    Assessments
      Regular Assessments
$120,000
-
$120,000
      Assessment Allocation
($30,000)
$30,000
    TOTAL of Revenues
$90,000
$30,000
$120,000
  Expenses
        Landscape Maintenance
$90,000
-
$90,000
        Telephone
-
      Capital Expenditures
-
$40,000
$40,000
    TOTAL of Capital Expenditures (Non-capitalized)
-
$40,000
$40,000
  TOTAL of Expenses
$90,000
$40,000
$130,000
  Net Surplus (Deficit)
($10,000)
($10,000)
Final
Printed on 11/1/2022
"""


def test_fund_budget_reads_the_consolidated_column_and_the_reserve_draw() -> None:
    reading = read(DocumentKind.BUDGET, FUND_BUDGET, ctx())
    a = reading.record
    b = a.budget
    assert b.layout == "ciraconnect fund budget" and b.fiscal_year == 2023 and b.generated == date(2022, 11, 1)
    assert (b.total_income_cents, b.total_expenses_cents, b.net_cents, a.net_cents) == (12_000_000, 13_000_000, -1_000_000, -1_000_000)
    assert (b.reserve_transfer_cents, b.reserve_expenditures_cents, b.assessments_cents) == (3_000_000, 4_000_000, 12_000_000)
    assert {i.label: i.cents for i in b.items}["Assessment Allocation"] == 0      # a transfer between the funds
    found = codes(reading)
    assert found["reserve-drawdown"] is Severity.INFO and "deficit-budget" not in found


# The CPA's review.

REVIEW = """EXAMPLE COMMUNITY ASSOCIATION
RE: 2017 Financial Review
Pursuant to Civil Code Section 5305 and the Association's Governing Documents, enclosed is a copy of the Association's 2017
financial statements and annual review prepared by the independent accounting firm of Smith and Jones, LLP. These statements
INDEPENDENT ACCOUNTANT'S REVIEW REPORT
We have reviewed the accompanying financial statements of Example Community Association, which comprise the balance sheet as of
December 31, 2017, and the related statements.
Accountant's Conclusion on the Financial Statements
Based on our review, we are not aware of any material modifications that should be made to the
accompanying financial statements.
Sacramento, California
October 30, 2018
STATEMENT OF REVENUES, EXPENSES AND CHANGES IN FUND BALANCES
For the Year Ended December 31, 2017
Total revenues
55,425
20,948
76,373
"""

LETTER = """Example Certified Public Accountant, PC
We are providing this letter in connection with your review of the financial statements of Example Community Association,
which comprise the balance sheet as of December 31, 2021.
Form 1120-H (2021)
Aug 30, 2022
"""


def test_review_report_after_120_days() -> None:
    reading = read(DocumentKind.FINANCIAL_REVIEW, REVIEW, ctx())
    r = reading.record
    assert (r.fiscal_year, r.firm, r.report_date, r.conclusion) == (2017, "Smith and Jones, LLP", date(2018, 10, 30), "no material modifications")
    assert r.gross_income_cents == 7_637_300
    found = codes(reading)
    assert found["review-after-120-days"] is Severity.PROBLEM and found["review-required"] is Severity.INFO
    small = read(DocumentKind.FINANCIAL_REVIEW, REVIEW.replace("76,373", "70,637"), ctx())
    found = codes(small)
    assert found["review-after-120-days"] is Severity.CHECK and found["review-not-required"] is Severity.INFO


def test_engagement_papers_without_the_review_report() -> None:
    reading = read(DocumentKind.FINANCIAL_REVIEW, LETTER, ctx())
    assert reading.record.papers == ("representation letter", "tax return") and reading.record.fiscal_year == 2021
    assert codes(reading)["no-review-report"] is Severity.CHECK


# Sacramento County tax bills.

BILL_2023 = """PARCEL NUMBER
BILL NUMBER
TRA
SECURED PROPERTY TAX BILL
AMOUNT TO PAY BOTH INSTALLMENTS
900-0000-001-0001
900-0000-001-0001
23400001
23400001
03436
2023-2024
2023-2024
2010-11 PRIOR YEAR TAXES ARE DELINQUENT
0198 SAFCA CONSOLIDATED CAP ASMT #2
916-874-7606
1.50
0739 RD 1000 STORMWATER SERVICE FEE
800-676-7516
10.56
12.06
COUNTY WIDE 1%
1.00000
.00
12.06
2024
$
6.03
2024
$
26.63
$20.00
2023
$
6.03
2023
$
6.63
2023
$
12.06
INTERNET COPY
"""


def old_bill(year: int, number: str, safca: str, total: str) -> str:
    return (f"PARCEL NUMBER\nBILL NUMBER\nSECURED PROPERTY TAX BILL\nFOR FISCAL YEAR BEGINNING JULY 1,\nTO PAY TOTAL OF BOTH INSTALLMENTS BY 12/10/\n"
            f"900-0000-001-0001\n{number}\n10\n03435\n{year}-{year + 1}\n0169\nSAFCA\nACT\nNATOMAS\nBASIN\nLOCAL\nASMT\nDIST\n916-874-7606\n"
            f"2.42\n0198\nSAFCA\nACT\nSAFCA\nCONSOLIDATED\nCAP\nASMT\n#2\n916-874-7606\n{safca}\n1-844-430-2823\nCOUNTY\nWIDE\n1%\n1\n1.00000\n.12\n"
            f"$\n{total}\n5.92\n$20.00\nINTERNET COPY\n")


def test_tax_bill_reads_levies_and_checks_the_county_catalog(tmp_path) -> None:
    with sqlite3.connect(tmp_path / "tax.db") as conn:
        conn.execute("CREATE TABLE bills (apn TEXT, number TEXT, direct_cents INTEGER, total_cents INTEGER, balance_cents INTEGER)")
        conn.execute("INSERT INTO bills VALUES ('900-0000-001-0001', '20230400001', 1206, 1206, 0)")
    reading = read(DocumentKind.TAX_BILL, BILL_2023, ctx(tmp_path, name="Bill 90000000010001-23400001.pdf"))
    d = reading.record
    assert stored_number("23400001") == "20230400001"
    assert d.apn == "900-0000-001-0001" and d.common_area is True and d.printed_numbers == ("23400001",)
    bill = d.bills[0]
    assert (bill.year, bill.tax_rate_area, bill.direct_cents, bill.total_cents) == (2023, "03436", 1206, 1206)
    assert [(levy.code, levy.amount_cents) for levy in bill.levies if levy.kind == "direct"] == [("0198", 150), ("0739", 1056)]
    found = codes(reading)
    assert found["prior-year-delinquent"] is Severity.PROBLEM and found["paid-per-county"] is Severity.INFO


def test_older_tax_bills_in_one_delinquent_file() -> None:
    text = old_bill(2018, "18000001", "9.30", "11.84") + "\n" + old_bill(2019, "19000001", "9.50", "12.04")
    reading = read(DocumentKind.TAX_BILL, text, ctx(name="Delinquent Tax Bills for 900-0000-001-0001.pdf"))
    d = reading.record
    assert d.delinquent_file and [b.year for b in d.bills] == [2018, 2019]
    assert [b.direct_cents for b in d.bills] == [1172, 1192] and [b.total_cents for b in d.bills] == [1184, 1204]
    assert [s.code for s in d.levy_series] == ["0169", "0198"]
    assert codes(reading)["levy-changed"] is Severity.INFO
    unit = text.replace("900-0000-001-0001", "900-0000-002-0003")
    assert codes(read(DocumentKind.TAX_BILL, unit, ctx()))["unit-parcel"] is Severity.INFO


# Reserve studies.

STUDY = "\n\n".join([
    """1446 Example Rd, Suite 101 • Clovis, CA 93611
RESERVE ANALYSIS REPORT
Example Community Association
Update | FY26
October 23, 2025""",
    """CALIFORNIA BUILDER SERVICES • 559.473.2690
PAGE 1-1
Assessment and Reserve Funding Disclosure Summary
for the Fiscal Year Ending 2026
(3) Based upon the most recent reserve study, will currently projected reserve account balances be sufficient at the end of each
year to meet the association's obligation for repair and/or replacement of major components during the next 30 years?
Yes   X  No _____
(6) the estimated amount required in the reserve fund at the end of the current fiscal year is $600,000, based in whole or in part on
the last reserve study. The projected reserve fund cash balance at the end of the current fiscal year is $270,000, resulting in
reserves being 45% funded at this date.
Note: the assumed long-term before-tax interest rate earned on reserve funds was 1.5% per year, and the assumed long-term
inflation rate to be applied to major component repair and replacement costs was 3.5% per year.""",
    """Current Assessment Funding Model Summary
CALIFORNIA BUILDER SERVICES • 559.473.2690
PAGE 2-1
Budget Year Beginning January 1, 2026
Total Units 80
Report Parameters
2026 Beginning Balance $200,000
Required Monthly Contribution $7,000.00""",
    """Current Assessment Funding Model Projection
CALIFORNIA BUILDER SERVICES • 559.473.2690
PAGE 2-2
Current Annual Annual Annual Ending Funded Percent
Year Cost Contribution Interest Expenditures Reserves Reserves Funded
2026 1,600,000 84,000 100 14,100 270,000 600,000 45%
2027 1,650,000 87,000 200 10,000 347,200 650,000 53%
Contingency - SB326 - Balcony Inspection""",
])

OTHER_STUDY = """Example Reserve Consultants
Reserve Study Update
Prepared for FY 2027
Assessment and Reserve Funding Disclosure Summary For the Fiscal Year Ending 2027
The exterior elevated elements inspection report (SB 326) of March 2025 is incorporated in this study.
"""


def test_reserve_study_pages_go_to_the_preparers_reader() -> None:
    assert len(split_pages(STUDY)) == 4
    reading = read(DocumentKind.RESERVE_STUDY, STUDY, ctx(name="Reserve Study 2026.pdf"))
    r = reading.record
    assert reading.complete and r.preparer == "California Builder Services"
    assert (r.fiscal_year, r.prepared, r.units) == (2026, date(2025, 10, 23), 80)
    assert r.projection_years == 2 and r.study.disclosure.percent_funded == 0.45 and r.study.disclosure.interest_rate == 0.015
    assert r.elevated_elements and not r.elevated_report_cited
    found = codes(reading)
    assert found["no-site-visit"] is Severity.CHECK
    assert found["unit-count"] is Severity.CHECK
    assert found["elevated-report-not-cited"] is Severity.CHECK
    assert found["no-components-read"] is Severity.CHECK
    assert found["interest-assumption"] is Severity.INFO


def test_other_preparer_yields_the_disclosure_and_the_elevated_report() -> None:
    reading = read(DocumentKind.RESERVE_STUDY, OTHER_STUDY, ctx())
    r = reading.record
    assert r.fiscal_year == 2027 and not r.preparer and r.elevated_report_cited
    found = codes(reading)
    assert found["unknown-preparer"] is Severity.CHECK and found["elevated-report-cited"] is Severity.INFO
    assert "missing-preparer" in found


BY_YEAR = """Browning Reserve Group
Reserve Study - Update w/o Site Visit Review
For the Fiscal Year Ending 12/31/2023
the assumed long-term before tax interest rate earned on reserve funds was 1.25 percent per year
2.00% per year was the assumed long-term inflation rate
will currently projected Reserve account balances be sufficient at the end of each year to meet the association's
obligation for repair and/or replacement of major components during the next 30 years?
Answer: Yes
At the time of inspection, the decks were not visually inspected but assumed to be in good condition.
Section VII-a
Expenditures by Year - Next 6 Years
2022
Painting: Exterior
03000 -
120 - Surface Restoration
      10,000 sf Buildings
40,000
8
Lighting
20000 -
100 - Exterior: Fixtures
      10 Wall Fixtures
5,000
15
110 - Exterior: Fixtures
      40 Entry Fixtures
6,000
15
11,000
Total   20000 - Lighting:
11,000
51,000
Total  2022:
2023
Paving
01000 -
100 - Asphalt: Sealing
      40,000 sf Drives
10,000
5
10,200
800 - Striping
      40 Spaces
800
5
816
11,016
Total   01000 - Paving:
10,800
10,800
Total  2023:
2024
Fencing
05000 -
300 - Wood
      100 lf Screens
3,000
16
3,121
3,121
Total   05000 - Fencing:
3,000
9,999
Total  2024:
Section X
"""


def test_expenditures_by_year_keep_the_years_that_add_up() -> None:
    reading = read(DocumentKind.RESERVE_STUDY, BY_YEAR, ctx())
    r = reading.record
    assert [(e.year, e.cost_cents) for e in r.study.expenditures] == [(2022, 4_000_000), (2022, 500_000), (2022, 600_000),
                                                                      (2023, 1_020_000), (2023, 81_600)]   # 2024's total is off
    assert r.planned_expenditures == 5 and r.study.expenditures[0].category == "Painting: Exterior"
    assert (r.interest_rate, r.inflation_rate, r.sufficient_for_30_years) == (0.0125, 0.02, True)
    found = codes(reading)
    assert found["components-not-inspected"] is Severity.CHECK
    assert "disclosure-lacks-interest-rate-assumed" not in found and "disclosure-lacks-answer-on-30-year-sufficiency" not in found


def test_models_decline_other_texts() -> None:
    for kind in (DocumentKind.BANK_STATEMENT, DocumentKind.TREASURER_REPORT, DocumentKind.FINANCIAL_STATEMENT, DocumentKind.FINANCIAL_REVIEW,
                 DocumentKind.BUDGET, DocumentKind.ANNUAL_DISCLOSURE, DocumentKind.TAX_BILL, DocumentKind.RESERVE_STUDY):
        assert read(kind, "Minutes of the regular meeting of the board of directors.", ctx()) is None
