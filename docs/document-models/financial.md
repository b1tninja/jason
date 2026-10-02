# Financial documents

These are the association's money records: bank statements, the monthly treasurer's reports and the prior manager's statements, budgets and the annual disclosures, the CPA review, county tax bills, and reserve studies. The models live in `jason.community.models.financial_*`:

| Module | Models (tried in this order) | Kinds |
|---|---|---|
| `financial_bank` | `chase-statement` | bank_statement |
| `financial_reports` | `payhoa-treasurers-report`; `helsing-financial-statements` | treasurer_report; financial_statement |
| `financial_annual` | `payhoa-budget`, `dre-budget-worksheet`, `insurance-summary-disclosure`, `annual-budget-report`; `cpa-review` | budget, annual_disclosure; financial_review |
| `financial_tax` | `sacramento-secured-bill` | tax_bill |
| `financial_reserve` | `reserve-study` | reserve_study |
| `financial_common` | shared helpers: signed amounts, the file's period, the specification's accounts, cached disk reads | none |

Amounts are integer cents. Treasurer's reports and the manager's statements carry owners' balances. The records keep totals only, such as the aging total, and never names or unit balances.

## Coverage

`jason models` and the `document_models` tool count, per kind, the classified files in the library, those with text, those a model read, and those it read complete. Each section below says what its model reads and checks.

Mystique's findings are in the private notes (mystique/notes/document-models/financial.md).

## Bank statements (`chase-statement`)

The layout is JPMorgan Chase business checking: "Beginning Balance / $x / Ending Balance / n / $y", then the product ("Chase Business Complete Checking", "Chase Performance Business Checking") and the checking summary as label, count, and amount.

**Record `BankStatement`.** It holds the bank, the product, and the account's last four digits, taken from the statement's account line and separately from the file name ("20250829-statements-1234-.pdf"). It also holds the period start and end, the beginning and ending balances, and the transaction count. The summary lines (`SummaryLine`: label, count, and signed cents) give the deposits, withdrawals, checks paid, fees, and interest. The record also notes whether the service fee was waived, the "Total Service Charge", the date the fee page says it will be assessed and the services charged ("Stop Payment - Online"), and the account's purpose (operating or reserve) from `community.bank_accounts()`.

Chase computes a period's service charges on the fee page and debits them early in the next period ("Total Service Charge (Will be assessed on 12/3/25)"). So one charge shows twice: computed on one statement, debited as "Fees" on the next. An account that earns no interest or pays no checks leaves those fields empty, and that is right.

**Required:** the account, the period, the beginning and ending balances, and the deposits.

**Checks:**

- The file name's account differs from the statement's (problem).
- The account is not one of `bank_accounts()` (check).
- The file name's date differs from the period end (check).
- Beginning balance plus the summary lines does not equal the ending balance (problem).
- The bank debited fees this period, or charged them with no assessment date (check).
- The fee page computes a charge the next statement debits (info).
- The account ended overdrawn (problem).
- Money left the reserve account. Each withdrawal needs two signers and a reserve purpose, and a transfer over the lesser of $10,000 or 5% of budgeted income needs prior written approval (check; CIV 5510(a), (b) and 5502(a)(2)).
- Against `data/payhoa/reconciliations.json`, matched by account and end date:
  - no reconciliation (check);
  - the reconciliation's starting or ending balance differs from the statement's (problem);
  - the balances match (info).
  These cite CIV 5500(a) for the operating account and 5500(b) for the reserve.

**Cannot show:** who signed a withdrawal, or whether the board approved a transfer.

## Treasurer's report (`payhoa-treasurers-report`)

This is PayHOA's generated "Treasurer's Report" packet. It holds an index of the included reports, the balance sheet, the aging, the budget reports, profit vs loss, the general ledger, and the two bank reconciliations. The model reuses `jason.tasks.reserves._ACCOUNT_LINE` for the reserve accounts. It follows `jason.tasks.ledger_reports` in treating the printed report as the record of what the board was told.

**Record `TreasurerReport`** holds:

- the title and the month it names;
- the included reports, read from the cover page, which lists them after "Included Reports:" (2026) or before it (2024 and 2025);
- the reported period, from the balance sheet date (a sheet "as of February 01" with a January ledger reports January), and the generated date;
- the general ledger range;
- each bank account (`AccountBalance`), the bank total, total assets, liabilities, equity, and liabilities plus equity;
- the reserve accounts and their total (a reserve account left with a prior manager can print as an other asset), and the aging total;
- profit vs loss: the range, income, expenses, and net;
- each reconciliation (`ReconciliationSummary`): the account, the dates, the beginning balance, cleared payments and deposits with their counts, the ending balance, open items, and the register balance;
- whether the copy is the member version (`redacted`), whether its file name says "Redacted" (`named_redacted`), and how many units its receivables aging lists (`aging_units`).

**Two versions.** The board version's aging lists each unit with its balance by age. The member version, included with the agendas, keeps the receivables totals and leaves the units out.

- **The law.** The association may withhold or redact information "reasonably likely to compromise the privacy of an individual member" and "records of ... collection activities, or payment plans of members other than the member requesting the records" (Civil Code 5215(a)(4), (a)(5)(B)). The board takes up payment plans and foreclosure in executive session (4935(c), (d)).
- **The rule.** Which version a copy is comes from its content, not its name or folder:
  - `content.aging_units` reads the unit addresses between the aging's first "Days Past Due" header and its Total row. A unit a ledger line names elsewhere does not count.
  - `content.PRIVATE_RULES` then makes any file with such units confidential, wherever it is filed.
  - The library records why in `Classified.private`. `anythingllm_sync.library_items` walks distinct files, so one confidential copy keeps every copy of the same bytes out of the shared catalogs.

**Required:** the period, the generated date, total assets, liabilities plus equity, and the reconciliations.

**Checks:**

- A copy named "Redacted" whose aging still lists units: `redaction-incomplete` (problem; CIV 5215(a)(4), (a)(5)(B)). A board version gets `member-receivables` (info).
- The copy is filed under another month (problem).
- The title names another month than the balance sheet (problem).
- The general ledger covers more than one month (check; 5500(f)).
- The copy was generated more than 60 days after its month, so the board may have seen an earlier run (check).
- The bank lines do not add to their total, or the balance sheet does not balance (problem).
- Net is not income less expenses (problem).
- A reconciliation does not foot (problem; 5500(a)/(b)).
- A reconciliation covers another month (check).
- The operating or reserve reconciliation is missing (check; 5500(a), (b)).
- The index lacks the budget report (5500(c)), the income statement (5500(e)), the general ledger, or the aging (5500(f)) (check).
- Reserve money sits at a bank the specification's accounts do not name (check).
- Printed bank balances differ from `data/payhoa/balance-sheets.json` for the same month end (check).

## Monthly financial statements (`helsing-financial-statements`)

These are The Helsing Group's "Monthly Financial Statements", a prior manager's monthly packets. The model reads full packets and the "Pages from" excerpts.

**Record `HelsingStatement`** holds:

- the preparer, the period end, the sections present, and whether the copy is an excerpt;
- operating cash, reserve cash, and the certificate of deposit;
- total assets, total liabilities, and liabilities plus equity (operating, reserve, total);
- the reserve fund's receivable ("A/R Reserve Fund") and the operating fund's "Due to Reserve";
- from the operating budget comparison (`BudgetLine`: month and year-to-date actual and budget, and the annual budget): total income, total expense, the excess, and the reserve contribution;
- the manager's notes that a reserve payment was not made.

**Required:** the period end, total assets, liabilities plus equity, and the reserve contribution.

**Checks:**

- The copy is filed under another month (problem).
- The balance sheet does not balance (problem).
- "Due to Reserve" is nonzero (problem). Money set for reserves was not moved; if it was borrowed, CIV 5515(d) requires restoring it within one year.
- The reserve side's receivable differs from the operating side's liability (check).
- The year-to-date reserve contribution is below budget (problem).
- The manager notes a missed contribution (problem).
- Operating cash is negative (problem).
- The budget comparison does not foot (check).
- There is an operating deficit (info; 5500(c)).
- A full packet lacks a report 5500 names (check).

## Budgets and annual disclosures

### PayHOA budgets (`payhoa-budget`)

This covers the "Pro Forma Budget" packet (Budget Summary and Budget - Monthly) and the "Monthly Budget" report. It handles the budget kind, and the annual report model reuses the same reader.

**Record `Budget`:** the layout, the title, the fiscal year, the generated date, the draft flag, and the basis (cash or accrual, when printed). It holds the items (`BudgetItem`), income, expenses, and net. It also holds assessments for the year and month, per unit a month (with `units()`), the reserve transfer, and the lines it came from (`reserve_budget_lines()` plus "Reserves", "Reserve Funding", and "Repayment").

**Required:** the fiscal year, income, expenses, and the reserve transfer.

**Checks:**

- The budget does not foot (problem).
- The budget plans a deficit (check).
- The budget is a draft (check; 5300(b)(1)).
- The budget is labeled cash basis, where 5300(b)(1) calls for accrual (check).
- There is no reserve line (check; 5300(b)(3)).
- The reserve transfer differs from the newest study's plan for that year, which is read from disk with `load_studies` (check; 5300(b)(3) and 5560(a)).
- The generated date falls after December 1, the last day of the 30-to-90-day window (check; a later run prints a later date).
- A pro forma budget is only item (1) of the report (info).

### Fund budgets (`read_fund_budget`)

CiraConnect's "Revenue and Expense Budget Summary for FY 2023" has three columns: operating fund, replacement fund, and consolidated. `read_fund_budget` reads it into the same `Budget` record, and the annual report model uses it when the packet has no PayHOA budget. Each row is a label followed by one line per column, where "-" means none.

- A row with three values is operating, replacement, and consolidated.
- A pair of values that cancel is a transfer between the funds, so its consolidated figure is nil. The "Assessment Allocation" is one: it moves the reserve contribution from operating to replacement.
- Any other pair ends in the consolidated figure.

The replacement fund's positive allocation is the reserve transfer. Its capital expenditures are `reserve_expenditures_cents`, the year's planned spending from reserves. The annual report carries the budget's `net_cents` too.

A consolidated deficit equal to the contribution less the planned reserve spending is the replacement fund drawing on its balance while the operating fund balances. That case is a `reserve-drawdown` (info; CIV 5510(b)), not a deficit budget.

### Developer budget worksheets (`dre-budget-worksheet`)

This is form RE 623, the developer's budget prepared for the public report.

**Record `DreBudgetWorksheet`:** the form, the preparer, the date (printed in capitals, "MARCH, 2018"), and each phase's lots and per-lot budget and reserves (`PhaseAssessment`). A worksheet may summarize only some of the phases.

**Checks:** the worksheet is informational only (info), and the lot count is compared with the specification.

### Insurance summary (`insurance-summary-disclosure`)

This model reads the summary when it is filed on its own.

**Record `InsuranceSummary`:** each coverage line and whether it says "None", the insurers, the policy periods, and whether the 5300(b)(9) statement, the 5810 notice, and the distribution claim are present.

**Checks:**

- The statutory statement is missing (problem; 5300(b)(9)).
- The 10-point boldface cannot be shown in text (info).
- A coverage line is missing (check).
- The summary says "None" for flood while the specification's insurance catalog lists flood policies (problem; 5300(b)(9)).

### Annual budget report and policy statement (`annual-budget-report`)

This covers CiraConnect's "Resident Budget Package" and the association's own "Annual Disclosures" packets. A packet with a contents page names every item there ("Reserve Funding Mechanism", "Anticipated Special Assessments"). Items are searched only after that page ends, at the "Annual Policy Statement" or the "Contact Information" page, whichever comes first, so a contents line is not counted as an item, even when a cover letter comes before the contents page.

The phrase rules skip a few look-alikes:

- A row of the "Charges for Documents Provided" form ("Insurance summary / Sections 5300 and 4525(a)(3)") prices an item; it is not the item.
- The form itself is known by its first lines ("Check or Complete Applicable Column"), because its heading can drop out of the text.
- The 5310(a)(4) option of individual delivery needs "option", "right", "request", or "elect" near the words, or a mention of general notices. A hearing notice "by personal or individual delivery" does not count.

**Record `AnnualReport`** holds:

- the preparer, the fiscal year, and the prepared date;
- the monthly and annual assessment, and the revenue and expense totals;
- the PayHOA budget inside the packet;
- which 5300(b)(1)-(12) and 5300(e) items the text carries, and which 5310(a)(1)-(11) items;
- the insurance summary, and the flood policy numbers the packet's own certificate lists ("11/20/2025 - 11/20/2026 5010000000 Bldg 5");
- the 5570 form, read by `reserve_study.read_disclosure`;
- the full-plan notice (5300(b)(3)) and the copy-request instructions (5320(a)(2)).

**Required:** the fiscal year, the 5300 items, and the 5310 items.

**Checks:**

- Each missing 5300(b), 5300(e), or 5310(a) item (check; the statute subdivision). A phrase rule that misses is not proof of absence.
- There is no full-plan notice (check).
- The dated copy falls outside the 30-to-90-day window: after the window it is a problem, before it a check (5300(a), 5310(a)).
- The packet has no date, so its budget's generated date is the earliest it could have gone out (check).
- The insurance summary checks above.
- The 5570 form is for another fiscal year than the budget (check).
- Percent funded, and a "No" to 30-year sufficiency (info).
- The letter's per-unit assessment differs from the budget's (check).
- Individual delivery (info; 5320(a)).

### CPA review (`cpa-review`)

This covers the review report of Propp, Christensen and Caniglia with its transmittal letter, and the engagement's other papers: the representation letter and the Form 1120-H and 199 returns.

**Record `FinancialReview`:** the fiscal year, the firm, the report date, the papers present, the conclusion, gross income (the largest total-revenues figure printed), and whether the statements carry the supplementary information on future major repairs and replacements.

**Required:** the fiscal year, the firm, and the report date.

**Checks:**

- The file has no review report (check; 5305).
- The report is dated after the 120-day distribution deadline (problem; 5305). When gross income was not over $75,000 the statute did not require the review, so a late report is a check against the governing documents.
- The deadline otherwise (info; 5305 and 4040).
- There is no conclusion, or the conclusion is modified (check or problem).
- Gross income is over $75,000, so the review is required (info), or it is not, so the statute did not require it (info).
- Confirm the firm's Board of Accountancy license (info).

## Tax bills (`sacramento-secured-bill`)

This model adapts `jason.community.tax`. The printed bills are read into the existing `TaxBill` and `TaxLevy` rows, and `direct_levies` groups the levies across years. The county's HTML reader (`parse_bill`) is unchanged. There are two layouts: the internet copy from 2022 on ("AMOUNT TO PAY BOTH INSTALLMENTS"), and the 2017-2021 bill ("FOR FISCAL YEAR BEGINNING JULY 1"). The "Delinquent Tax Bills for ..." files hold several years.

**Record `TaxBillDocument`** holds:

- the parcel, the layout, and whether the file is a delinquent-bill file;
- the bills (number in the county's eleven-digit form, year, tax rate area, summed rates, direct levies, total), and the eight-digit numbers as printed;
- the years a bill says are delinquent;
- the levy series, and whether the parcel is a common area.

**Required:** the parcel and at least one bill.

**Checks:**

- The parcel is not in `parcels()` (check), or is a unit's (info).
- "Prior year taxes are delinquent" (problem).
- The total differs from the direct levies on a bill with no ad valorem tax (check).
- A levy's amount changed across years (info).
- Against `data/tax.db`, opened read-only: the bill is missing (info), the direct levies differ (check), there is a balance due (check), or the bill is paid (info).

No Civil Code section governs these bills.

## Reserve studies (`reserve-study`)

This model adapts `jason.community.reserve_study`. The library joins each PDF page's text with a newline, so an empty line is a page break. `split_pages` rebuilds the pages, and `read_pages` picks the preparer's reader: California Builder Services, The Helsing Group, Browning Reserve Group, or disclosure-only. On the library's studies this gives the same readings as `read_study` on the PDFs.

**Record `ReserveStudyRecord`** holds:

- the reader's `ReserveStudy` (disclosure, projection, components, expenditures);
- the preparer, the fiscal year, the prepared date, the level, and the units;
- the component counts (all, and with a life and a cost), the projection years, and the planned expenditures;
- the stated last site visit (an update may state none);
- the lines on balconies, decks, and SB 326, and whether the 5551 report is cited;
- the 5570 note's interest and inflation rates and the 30-year answer, read from the form's own words when the preparer's reader misses them ("3.75 percent per year", "2.50% per year was the assumed long-term inflation rate", "Answer: Yes");
- the components the study says were not visually inspected.

When the preparer's reader has no itemized expenditures, `by_year_expenditures` reads Browning's "Expenditures by Year - Next 6 Years". Each component row gives its current cost, useful life, and (after the first year) its inflated cost. A year is kept only when its components' current costs add to the printed year total. Helsing's "Estimated Expenditure Schedule" comes out of the PDF in a scrambled column order, so it is not read. Its projection still gives each year's total spending.

**Required:** the preparer, the fiscal year, the prepared date, and the level.

**Checks:**

- A site-visit study (info) or an update without a site visit (check; 5550(a)).
- No components read, or components without a life or a cost (check; 5550(b)(1)-(3)).
- No funding plan read (check; 5550(b)(4), (5)).
- Each 5570 figure not read (check).
- A "No" to 30-year sufficiency, and percent funded (info).
- The interest assumption, against the 5300(b)(7) cap of 2 points over the discount rate (info; the rate is not in the text).
- The unit count differs from the specification (check).
- An unknown preparer (check).
- Elevated elements not mentioned, or the 5551 report not cited (check; 5551(f)).
- The study says components were not visually inspected (check; 5550(a)).
- Against the studies on disk: superseded (info), the next site visit due (5550(a)), and no current study (check).

## What the texts cannot show

The texts cannot show:

- signatures (the two signers on reserve withdrawals, and the board's written approval of transfers);
- the date a report actually reached members, or the 10-point boldface the statutes require;
- whether a review firm is a California Board of Accountancy licensee;
- the Federal Reserve discount rate against a study's interest assumption;
- whether a treasurer's report was the run the board reviewed (only the PayHOA run hashes in `jason ledger` can show that).

A phrase rule that finds no item is a lead, not proof that the item is absent.
