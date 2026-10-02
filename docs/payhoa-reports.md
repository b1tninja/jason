# PayHOA's reporting

What PayHOA can report, how it computes it, how jason reads it, and what is left to learn. Read from both help centers (October 2, 2026), the report catalog the API serves, and the captured calls (`app.payhoa.com - reports.har`).

**Sources on disk** (`data/`, never committed):
- `data/payhoa/payhoa-help/articles.json`: PayHOA's help center (intercom.help/payhoa), 320 articles.
- `data/payhoa/legfi-help/articles.json`: LegFi's help center (legfi.zendesk.com), 218 articles, read through Zendesk's public API.

## The system underneath

**PayHOA runs on LegFi's platform.** Every API call carries `x-legfi-site-id`, and LegFi's help center describes the same ledger. LegFi's own product serves fraternities and clubs, so most of its articles are about other things (treasury cards, national headquarters). The parts about the ledger apply to PayHOA.

**The ledger is the source.** LegFi moved its reporting onto a new ledgering system:
- Its Income Statement "pulls directly from the General Ledger to ensure every transaction is included".
- The older Profit vs Loss and Budget vs Actual reports "remain available for reference to historical transactions".
- Payables post their own journal entries (bill created, bill paid), and edits and voids sync in real time.

PayHOA's catalog still lists Profit vs Loss and Budget vs Actual. The newer calls (below) are the ledger's.

**What a report includes:**
- **Only reviewed transactions count.** "In PayHOA Balance" is the account's starting balance plus every categorized, reviewed transaction. Anything still "For Review" is in no report.
- **The bank balance is not in any report.** On a linked account (Plaid), the bank's own balance is shown "for visual reasons" only.
- **Some transactions write themselves:** PayHOA deposits, lockbox deposits, bill-pay checks sent from the vendor tab (when "write to transactions" is on), and payables.
- **Everything else is entered or imported.** On an unlinked account, every other transaction is entered by hand or imported from CSV, and owner payments made outside PayHOA are recorded in the payment tab.
- **Computed on the balance sheet:** equity is assets minus liabilities. Accounts Receivable is open invoices (an asset). "Accounts Receivable – Prepaids" is owners' overpayments (a liability).
- **A month is only complete after reconciliation.** PayHOA tells associations to reconcile every account monthly, linked or not, so that every transaction is in the system. A report for a month run before that month's reconciliation can be missing transactions.
- **The ledger can change later.** A month's numbers can still move after its report was run. `jason ledger` already finds reports whose printed balances the ledger now reports differently. That is why a packet run's own PDF, with its SHA-256, is the record of what the board was shown.

**Bank reconciliation** (redone July 2026 as "AI bank reconciliation"):
- Upload the statement PDF, and an AI agent matches the transactions. Western Alliance Bank statements are pulled automatically.
- The completed reconciliation's report gives the period, the number of transactions reconciled, and the ending balance. If the statement and register don't agree, it lists the unreconciled transactions causing the difference.
- The report downloads as a PDF or exports as a CSV.

## The catalog

`GET /reports/config` serves 42 reports in five groups. Each is a page at `app.payhoa.com/app/reports/...`.

| Group | Reports |
|---|---|
| Business overview | Balance Sheet; General Ledger; Account Register; Profit vs Loss Summary, by Month, Detail, as Percentage of Income; Budget Summary; Budget vs Actual Summary; Budget Performance by Month; Journal Entries; Bank Reconciliation |
| Who owes you | Unit Balance List, Summary, Detail; Delinquent Accounts, Detail; Aging of Accounts; Invoices by Unit, by Revenue Category, by Title; New Recurring Charges |
| Payments | Payments by Unit; Receipts Detail; Prepayments by Unit; Deposit Details; Returned Payments |
| Expenses | Expenses by Vendor, by Category, Detail; Check Register; Vendor Overview; Vendor Balance Summary, Detail; Vendor Aging of Accounts, Detail; Subscription History |
| Other | Custom Report; Owner Directory; Vendor Directory; Ownership Change; Violations |

**What some of them mean**, from PayHOA's "Report breakdown":
- **Account Register:** the General Ledger for the accounts you choose (to chase a bank account's discrepancy).
- **Profit vs Loss Detail:** each line item behind a category's total.
- **Delinquent Accounts:** the whole unit balance (current and past due) beside the past-due part, as of the day it is run.
- **Prepayments by Unit:** each overpaid unit's credit.

**Who owes you, the owner directory, and violations name owners.** They are for the board, and the delinquencies are executive session matters. Never put them in an open-session document.

**Every report exports.** In the app, "Export" gives a CSV and "Save as PDF" a PDF.

## How the API serves them

**Two generations of calls, both captured:**

| Generation | Shape | Reports captured |
|---|---|---|
| Older | `GET /organizations/{org}/reports/{report}/0` for the data, `/1` for the PDF | balance sheet, budget summary (summary, monthly), profit vs loss by month and details, vendor info |
| Ledger | `POST /organizations/{org}/reports/{report}/json`, `/csv`, `/pdf` (journal entries: `GET .../json`) | general ledger, account register (json, csv, pdf), journal entries |

**Also captured:**
- **Bank reconciliations:** `GET /organizations/{org}/reconciliations`, `.../{id}/report`, `.../{id}/report/pdf`.
- **Custom reports:** `GET .../reports/custom/fields`, `POST .../reports/custom/{id}`.
- **Packets:** `GET /report-packets` (the packets and their templates) and `GET /saved-reports` (every run). A run's PDF comes from `GET /saved-reports/{id}/download` or the run's signed `downloadUrl`.
- **Favourites:** `GET /ai-reports/organizations/{org}/favorite-reports` returns `{"favoriteReportKeys": []}`.

The payhoa client implements these (`general_ledger`, `balance_sheet`, `profit_loss_by_month`, `budget_summary_report`, `download_report_pdf`, `reconciliation_report`, `saved_reports`, `custom_report`, ...).

## Report packets

**What a packet is.** A packet is a named set of report templates, each with relative criteria (`PREVIOUS_MONTH_END`, `FISCAL_YEAR_START`, `RECENT_RECONCILIATION`). This association has three:
- **Treasurer's Report:** balance sheet, aging of accounts, budget performance by month, budget vs actual summary, profit vs loss summary, general ledger, and the two bank reconciliations.
- **Annual Financial Package:** budget summary, budget vs actual, balance sheet, general ledger, journal entries.
- **Pro Forma Budget:** budget summary and monthly.

**How runs are kept.** Each run is kept with its PDF and SHA-256. All 39 runs on record were started by a person (each has a `batchId`). None was scheduled (`scheduledReportId` is empty on every one), though the run record has room for a schedule.

**How jason uses them.** jason catalogs the runs (`jason report --catalog`, [board-agenda.md](board-agenda.md)) and includes a run already built. It never starts one.

**Bookkeeping packets are a separate store.** Associations enrolled in PayHOA's bookkeeping service (an in-app module since July 2026) get a monthly packet from their bookkeeper: balance sheet, profit and loss, budget vs actual, aging, and more. It lands under Other Tools, Bookkeeping, Financial and Tax Documents. That is not the saved-reports list. This association is not enrolled, so those calls have not been seen.

## Gable

PayHOA's AI assistant (beta, free, announced October 1, 2026) works from the association's documents and data.

**What it does:**
- Answers questions with their source (a governing document's section, a number's period).
- Drafts work as previews: next year's budget from actuals, side-by-side vendor quotes, a six-month board executive summary as a Word document and PDF.
- Runs overnight: triages requests, codes bank transactions, and answers owners' questions.
- Can be shaped with instructions, saved "skills", and scheduled "workflows".

**Its limits:**
- Nothing is sent or posted without an administrator's confirmation, and each batch is confirmed on its own.
- Each instance sees one association, and conversations aren't shared with other admins.
- It won't give out account numbers or other protected details.

**What it means for jason.**
- **Gable does inside PayHOA what jason does beside it.** jason's analyses run on this machine, cite their sources, and draw on records PayHOA never sees: deeds, the county roll, Drive, the mail, the statutes.
- **A Gable report could be a source.** If the board keeps a Gable report, its export can be catalogued like a packet run: a file with its date, filed for the board.
- **jason should not duplicate Gable's PayHOA-only answers.** Where both could answer, jason's version should add the outside records.

## What this means for jason's reports

1. **A finance report is current only after its month's reconciliation.** Before including a month's figures, check that each bank account has a completed reconciliation for that month (`jason reconcile`). Without one, the document should say the month is not closed.
2. **Keep PayHOA's own file, with its hash.** For a packet run, a reconciliation report, or any report saved as PDF, the PDF is what the board relies on. jason's summary beside it is commentary.
3. **CSV feeds the Sheet.** The ledger calls' `/csv` and the app's Export give each report as a table. That is the data layer for a reports Sheet: one tab per report, refreshed with the report, from which a Doc a person keeps can carry a linked table or chart (Docs' Tools, Linked objects, Update all; the Docs API cannot insert or refresh one).
4. **Mark what names owners.** Who owes you, the owner directory, violations, ownership change, unit balances, and payments by unit are confidential. The report source should carry that audience, so an open-session item refuses them.
5. **Accounting method.** PayHOA's bookkeepers work on cash or accrual, and outside revenue is handled differently on accrual. Which method this association uses should be a specification fact, cited beside any profit-and-loss figure.

## Left to capture (a HAR each)

- **Starting a packet run, and scheduling one.** Both are writes; jason would only read. Capturing them tells us how a scheduled monthly run would appear in `/saved-reports`.
- **The reports never opened in a capture:** aging, delinquent accounts, unit balances, invoices, payments and receipts, deposits, returned payments, expenses, the check register, vendor balances and aging, the owner and vendor directories, ownership change, violations, and profit vs loss summary and percentage. Most are probably the ledger shape (`json`/`csv`/`pdf`); a capture of each confirms its criteria.
- **CSV export of the older reports,** and whether `/2` or another path serves it.
- **The bookkeeping module's packets,** if the association enrolls.
- **Gable's API,** read only, if the board uses it and its reports are to be catalogued.
