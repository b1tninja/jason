# Finance

`/finance` · phase 2 · read-only throughout · CLI: `jason budget`, `jason books`, `jason accounts`, `jason reconcile`, `jason reserves`

## Purpose and personas

The association's money, as last synced: budget against actual, bank balances, reconciliations, reserves, invoices checked against payments, collections, the ledger's reports, and utility costs. The screen reads; it never writes.

- **Treasurer:** the main user. Reads every panel before a board meeting and checks the reconciliations.
- **Manager:** reads the same, and starts the refresh.
- **Director:** reads budget against actual and the reserves.
- **Secretary, reviewer, counsel:** no access.

## Data

Amounts are integer cents in every source, shown as dollars ([style.md](../content/style.md#amounts)).

| Panel | Source |
|---|---|
| Budget against actual, and the variances | `budget_status(year)` → `finance.finance_summary` |
| Bank balances | `bank_accounts`: each account named from the specification (`BankAccount` rows), its last four digits, which is the reserve, and the balance with its date. The note that Plaid balances are confirmed on the bank's statement |
| Reconciliations | `bank_reconciliations` |
| Reserves | `reserve_study(year)`, `reserve_transfers` |
| Invoices checked against payments | `invoice_review(problems_only=True)` |
| Collections and liens | `association_collections()`: each account's `standing`, `past_due_cents`, the statute's next step, and the note "Jason does not send an account to a collection agency, record a lien, or start a foreclosure"; `assessment_liens` |
| The ledger's reports | `books_report(report="pl" \| ...)` |
| Utility costs | `utility_brief`, `utility_payments(problems_only=True)` |

Each panel shows its snapshot's `syncedAt` (or `ledgerSynced`).

## Layout

```
+------------------------------------------------------------------------------------------+
| Finance · fiscal year 2099                       Synced Oct 3, 06:00 · [Refresh (job)]    |
| Read-only. Amounts as last synced from PayHOA.                                           |
+------------------------------------------------------------------------------------------+
| BUDGET AGAINST ACTUAL (9 of 12 months)                                                   |
| Category            Budget to date  Actual        Variance      Note                     |
| Landscaping         $27,000.00      $25,412.50    −$1,587.50    under                    |
| Insurance           $36,000.00      $51,220.00    +$15,220.00   over: premium renewed    |
+------------------------------------------------------------------------------------------+
| BANK ACCOUNTS                                                                            |
| Operating ··0004    $42,118.06   as of Oct 2  (confirm on the bank's statement)          |
| Reserve   ··0011   $310,550.00   as of Oct 2                                              |
+------------------------------------------------------------------------------------------+
| RECONCILIATIONS · last: Aug 2099, both accounts · Sep: not yet                            |
+------------------------------------------------------------------------------------------+
| RESERVES · study 2098: funded 61% · transfers this year: 3 of 4 on record                |
+------------------------------------------------------------------------------------------+
| INVOICES · 2 problems: 1 paid twice?, 1 no invoice on file                               |
+------------------------------------------------------------------------------------------+
| COLLECTIONS · 3 accounts owed · $1,236.00 past due · 1 release due (Civil Code 5685)     |
| jason does not send an account to a collection agency, record a lien, or foreclose.      |
+------------------------------------------------------------------------------------------+
| UTILITIES · water up 8% on last year · 1 payment problem                                 |
+------------------------------------------------------------------------------------------+
```

Each panel opens to its full table. Below 768 px panels stack, and wide tables scroll inside their own frame with the first column fixed; the page never scrolls sideways.

## Components

`page-header`, `section-card`, `freshness`, `cli-hint`, `data-table` (amounts right-aligned, tabular figures), `status-badge`, `deadline-badge` (`--legal` for a lien release due under Civil Code 5685), `states` (empty), `states` (unavailable), `job-status` (refresh).

No `approve-bar`, `write-row`, or form appears on this screen.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Refresh | Reads new months from PayHOA as a job, under the PayHOA lock. A read | No | `jason budget`, `jason books --sync` |
| Open a panel's table | Expands in place | No | the panel's command |
| Download CSV | The table's shown columns, logged with its column list and row count | No; logged | — |

## States

- **No snapshot:** "Finance is unavailable: no PayHOA ledger on disk. Run `jason sync-catalog`."
- **A panel's store missing:** that panel only is unavailable, with its command.
- **Stale:** a snapshot older than 7 days shows "Synced 9 days ago" in the `--soon` style beside the freshness line.
- **No problems found** (invoices, utility payments): "No problems found in 214 invoices checked." Never an empty table alone.

## Privacy

- Account numbers by their last four digits only. A full account or routing number is P4 and never in any source the screen reads.
- Collections are by unit (P1) for the manager and treasurer. A director sees counts and totals, and units in the private view, since delinquency is an executive-session subject (Civil Code 4935(a)).
- Vendor names are P0. Payees who are members (reimbursements) are P1.

## Acceptance criteria

1. The screen has no form that writes, and no control on it reaches PayHOA except Refresh, which only reads.
2. Every amount renders from integer cents as dollars with two decimals, a thousands separator, and a minus sign for negatives; no float arithmetic in the template.
3. Every account shows only its last four digits.
4. Each panel shows its own sync time; a missing store affects only its panel.
5. For a director with the private view off, the collections panel shows no unit.
6. The collections note renders verbatim.
