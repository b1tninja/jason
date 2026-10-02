# PayHOA's ledger reports and the treasurer's report

The treasurer's report in the library is not written by hand. It is PayHOA's "Treasurer's Report" report packet, run each month and saved as a PDF. The packet assembles eight reports:

1. The balance sheet, as of the previous month end.
2. The aging of accounts.
3. Budget performance for the previous month.
4. Budget against actual, fiscal year to date.
5. Profit and loss, fiscal year to date.
6. The general ledger for the previous month.
7. The bank reconciliation for the operating account.
8. The bank reconciliation for the reserve account.

`app.payhoa.com - reports.har`, analyzed with hardly on September 29, 2026, captured the calls behind it. The payhoa client implements the ones the capture shows: `balance_sheet`, `account_register` (JSON, CSV, and PDF), `general_ledger`, `journal_entries`, `ledger_accounts`, `report_packets`, and `saved_reports`. See payhoa's `API.md`, "Rendered reports". The aging, budget performance, profit and loss, and bank reconciliation render calls were not in the capture.

## What jason does with them

`jason ledger --fetch` reads every saved packet run, a balance sheet as of every month end since the first run, and the chart of accounts. It writes `data/payhoa/saved-reports.json`, `balance-sheets.json`, and `ledger-accounts.json`. `--download` also saves each run's PDF the library does not hold. Nothing in PayHOA changes. `jason ledger` then checks the library against those files:

- **Copies.** A run's `uploadedFile.fileHash` is the SHA-256 of its PDF. A library copy with that hash is the run as generated. A copy with no matching hash was changed afterwards; a redacted copy is expected to be.
- **Periods.** A run's criteria use relative dates (`PREVIOUS_MONTH_END`) or stored dates. The check reports a run whose balance sheet is not a month end, whose ledger spans more than a month, or whose name gives another month.
- **Misfiled copies.** A copy whose printed balances are the ledger's figures for a different month was filed under the wrong month.
- **Rewritten history.** An account a report printed that PayHOA's balance sheet for that date no longer carries. The chart of accounts' starting balance and date usually explain it.
- **Changed balances.** A printed balance that the ledger now reports differently for the same date means transactions were imported late, re-dated, or edited after the board saw the report.

The printed report is the record of what the board was told. The reserve brief (`jason reserves`) takes each month's reserve accounts from PayHOA's balance sheet, adds any account the report printed that the ledger dropped, and checks each reserve study's starting balance against the December before it.

## The books from the general ledger

`jason books --sync` asks PayHOA for the general ledger one month at a time, using the captured call, and stores every row in `data/payhoa/ledger.db`. The first sync reads every month from the ledger's start. Later syncs read new months and re-read the last four, because the ledger changes after the fact. `--full` re-reads everything. Every report is then computed locally (`jason.community.ledger`):

| Report | What it gives |
|---|---|
| `pl` | Income and expense by category over a period, and the net |
| `months` | Each expense (or income) category by month |
| `vendors` | Spending by payee: total, payments, categories, first and last date. The payee is PayHOA's vendor, else the bank line's company, bill-pay payee, or merchant |
| `cashflow` | Each bank account's start, money in and out by category, and end |
| `balances` | Bank account balances on a date. Unit accounts only with `--owners` |
| `receivables` | What the units owe and have prepaid, as totals and counts, with no names |
| `check` | The ledger's year-to-date category totals against PayHOA's own budget-against-actual figures from `jason budget`, and each category's months against PayHOA's Profit vs Loss by Month (`data/payhoa/profit-loss-<year>.json`, fetched by `--sync`) |
| `query` | Entries matching words, payee, category, account, an amount range, and dates |

The `books_report` and `ledger_query` MCP tools read the same store. `ledger_query` leaves the units' own accounts out.

## Bank reconciliations

`jason reconcile --fetch` reads every completed reconciliation and its report from PayHOA into `data/payhoa/reconciliations.json`. It changes nothing in PayHOA. `jason reconcile` and the `bank_reconciliations` MCP tool then read the file and report, per bank account:

- the months reconciled, and any month skipped between the first and the latest;
- the latest statement's ending balance, and PayHOA's register balance;
- the register items that never cleared, oldest first, with their age;
- each statement's ending balance against the general ledger's balance for the same account and day. The ledger account is found by PayHOA's bank-account id in `ledger-accounts.json`, because two ledger accounts are named "Operating Account". A difference equal to the items in transit at month end is marked explained. A statement dated before the ledger account's starting balance is counted and not compared;
- transfers open on both sides: an open payment in one account and an open deposit of the same amount in another within three days.
- why each open item may not have cleared. The fetch keeps each reconciliation's cleared items, and open and cleared items are compared as bank lines: pieces that share an ACH trace number or a transfer's transaction number are one line split across categories. An open line that cleared under the same number is **the same bank line**, held twice in the register. A cleared line of the same total and company within ten days, under another number, is **a cleared twin**. The other reasons are a **voided bill payment** (a deposit PayHOA made when a bill payment was voided), a **transfer**, and **in transit** (dated in the last 45 days). A single piece is not compared on its own, because a small fixed charge, such as a fire-service fee, recurs on many utility accounts. A reason is a lead for the treasurer, not a finding.

Clearing, voiding, or re-reconciling an item is the treasurer's work in PayHOA.

## Reports not yet reachable

PayHOA's catalogue (`/reports/config`) lists about 55 reports. The first capture rendered the balance sheet, the account register, the general ledger, and journal entries. The second added profit and loss by month and in detail, the budget summary by year, vendor info, bank reconciliations, saved-report downloads, custom reports, and PDF exports (payhoa `API.md`, "Rendered reports, second capture"). Blind requests for the other catalogue reports answered 404, or 500 when the request body did not fit, so their paths still need a capture, recorded with the cache disabled while each report is opened. The most useful left are aging of accounts, budget performance by month, the trial balance, the cash-flow statement, deposit detail, delinquent accounts, and the vendor balance and aging reports.

This association's findings are in its private notes (mystique/notes/ledger-reports.md).
