# Finance

Bands added to `#/payments`, `#/reserves`, and `#/books` · phase 2 · read-only throughout · CLI: `jason budget`, `jason books`, `jason accounts`, `jason reconcile`, `jason reserves`

## In the console

The Money group already covers most of what this spec asked for:

| Console screen | What it shows | Loaders |
|---|---|---|
| **Payments with questions** (`#/payments`, `ConsolePayments`) | The monthly review under CIV 5500: budget against actual with the categories furthest off, each account's reconciliation with its open items, the payments with questions, and the delinquent accounts by standing, marked executive session | `budget`, `reconciliations`, `invoices`, `collections` |
| **Reserves and budget** (`#/reserves`, `ConsoleReserves`; owner view too) | Each borrowing's 5515 record as a checklist, contributions against the budget, movements nothing explains | `reserves` |
| **Reserve findings** (`#/reserve-findings`) | The board's 5515 finding per borrowing | `reserve-findings` |
| **Liens and delinquency** (`#/liens`, `ConsoleLiens`) | The board's step per delinquent account beside its standing | `delinquency` |
| **Books checks** (`#/books`) | Utility payments against the bills they paid; the treasurer's reports validated against the ledger | `utility-payments`, `ledger-validation` |
| **Title watch** (`#/title`) | Recorded liens by standing, the four a person acts on first | `title-watch` |

**What this spec adds**, as bands on those screens:

1. **Bank balances** on `#/payments`: each account named from the specification, by its last four digits, which is the reserve, and the balance with its date.
2. **The reserve study** on `#/reserves`: the study's percent funded, the funding plan, and its Civil Code 5570 disclosure.
3. **The ledger's reports** on `#/books`: PayHOA's reports as last synced (income and expense, balance sheet).
4. **Utility costs** on `#/books`: each utility's cost over time and the change on last year.

## Purpose and personas

The association's money, as last synced. The screens read; they never write outside jason, and the board's steps (`#/liens`, `#/reserve-findings`) are the board's own records.

- **Treasurer:** the main user. Reads every band before a board meeting.
- **Manager:** reads the same, and runs the syncs.
- **Director:** reads budget against actual and the reserves.

## Data

Amounts are integer cents in every source, shown as dollars ([style.md](../content/style.md#amounts)).

| Band | Source | Loader |
|---|---|---|
| Bank balances | `bank_accounts`: each account from the specification (`BankAccount` rows), its last four digits, which is the reserve, and the balance with its date; the note that Plaid balances are confirmed on the bank's statement | `bank-accounts` (to add) |
| The reserve study | `reserve_study(year)` | `reserve-study` (to add) |
| The ledger's reports | `books_report(report=...)` | `books-report` (to add; `?report=`) |
| Utility costs | `utility_brief` | `utility-brief` (to add) |

Each band shows its snapshot's `syncedAt` (or `ledgerSynced`).

## Layout

```
+------------------------------------------------------------------------------------------+
| BANK ACCOUNTS                                       synced Oct 2 · jason accounts [copy]  |
| Operating ··0004    $42,118.06   as of Oct 2   (confirm on the bank's statement)          |
| Reserve   ··0011   $310,550.00   as of Oct 2                                              |
+------------------------------------------------------------------------------------------+
| RESERVE STUDY · 2098: 61% funded · funding plan: $4,200.00 a month · disclosure (5570)   |
+------------------------------------------------------------------------------------------+
| LEDGER REPORTS · income and expense, Jan to Sep · balance sheet, Sep 30   [open]         |
| UTILITIES · water up 8% on last year                                                      |
+------------------------------------------------------------------------------------------+
```

Wide tables scroll inside their own frame with the first column fixed; the page never scrolls sideways.

## Documents

Each document these screens name is a `Doc` fed a `DocRef` from its loader ([doc-component.md](../doc-component.md)). Opening one is a logged view; nothing opens on load.

| Screen | Document | Reference (loader field) | Level | Variant |
|---|---|---|---|---|
| Invoice review (`#/payments`) | Each payment's attachment, jason's copy under `transactions/` | `file:` (`payments[].documents[].doc`, beside `filename`) | P2 | `chip` in the Attached cell |
| Books checks, utility payments (`#/books`) | Each utility payment's attached bill, jason's copy under `transactions/` | `file:` (`payments[].attachments[].doc`) | P2 | `chip` in the Attached cell |
| Books checks, ledger validation (`#/books`) | The library's copy of each treasurer's report a run or a checklist row names | `library:` (`runs[].libraryDocs`, `<row>.doc` beside `path`) | the library's flag | `chip` in the Library copies and Copy cells |
| Reserves (`#/reserves`) and Reserve findings (`#/reserve-findings`) | Each borrowing's 5515 record: the agenda giving notice, the minutes of that meeting, the resolution | `library:` (`borrowings[].documents.<notice\|minutes\|resolution>.doc`); a minutes row read from Drive is `drive:` | the library's flag | `chip` on its tick |
| Reserves (`#/reserves`), board view only | The latest reserve study, the one the funding plan is read from | `file:` (`study`) | P1 (`reserve-studies/`) or the library's flag | `card` |

**What stays a name:**
- An attachment PayHOA gave no link for, or one kept only in a portal's folder outside `data/`, keeps its filename, marked "No copy on disk": nothing opens.
- A file whose name holds two spaces in a row stays a name too, until the evidence address keeps the spaces.
- A treasurer's report copy the library no longer holds stays its file name.

The owner view of `#/reserves` leaves the study out (Privacy, below).

## Components

`Card`, `DataTable` (amounts right-aligned, tabular figures), `Money`, `Stat`, `Pill`, `DueDate`, `Caveats`, `Command`, `RemoteView`, `Doc`.

## Actions

| Control | Does | CLI |
|---|---|---|
| Copy the sync command | Copies it; the page runs nothing | `jason budget`, `jason books --sync`, `jason accounts` |
| Open a band's table | Expands in place | the band's command |

## States

- **No snapshot:** the band is unavailable with its command: "Bank balances are unavailable: no account snapshot on disk. Run `jason accounts`."
- **Stale:** a snapshot older than 7 days shows "Synced 9 days ago" beside its freshness line.
- **No problems found:** "No problems found in 214 payments checked." Never an empty table alone.

## Privacy

- Account numbers by their last four digits only. A full account or routing number is P4 and never in any source these bands read.
- Delinquency stays on `#/payments` and `#/liens` as built: an executive-session subject (Civil Code 4935(a)), by unit for the manager and treasurer.
- None of these bands is in the owner view, except the reserve study on `#/reserves` once the board decides what owners see of it.

## Acceptance criteria

1. No band writes, and no control reaches PayHOA or a bank.
2. Every amount renders from integer cents as dollars with two decimals, a thousands separator, and a minus sign for negatives.
3. Every account shows only its last four digits.
4. Each band shows its own sync time; a missing store affects only its band.
