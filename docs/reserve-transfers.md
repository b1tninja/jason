# Reserve transfers and borrowing

Reserve money is spent only on the major components it was set aside for (Civil Code 5510(b)). Withdrawing it takes two signatures (5510(a)). The board may lend it to the operating fund for a short-term cash need (5515). A loan needs:

- **Notice.** A board meeting agenda under § 4920 with the item, giving the reasons, some repayment options, and whether a special assessment may be considered.
- **Finding.** A written finding in the minutes that says why the transfer is needed and when and how the money will be repaid.
- **Restoration.** The money back in the reserve within one year of the transfer. The board may delay that only after the same notice, with a documented finding that the delay is in the association's best interest.

The statute's words are in `data/authorities/CIV/CIV-5510-5520.md` (`authorities` tool).

## What jason reads

`jason reserves --transfers` and the `reserve_transfers` MCP tool read the general ledger (`jason books --sync`), the chart of accounts (`jason ledger --fetch`), the bank accounts pinned in `mystique/banking.py`, and the classified library (`jason library`). They sort every row on the reserve accounts (`jason.community.reserve_transfers`):

| Movement | Purpose | How it is told |
|---|---|---|
| Money in from operating | regular contribution | the year's most common amount, or last year's (January often carries the old amount) |
| | catch-up contribution | the memo names an earlier month ("January 2024") |
| | restores a payment | the reserve paid a fee or purchase of the same amount in the 45 days before |
| | unscheduled | anything else; a loan's repayment shows here |
| Money out to operating | forwards a deposit | a deposit of the same amount landed in the reserve in the 10 days before |
| | reimbursement | an operating expense of the same amount in the 60 days before (5510(b) spending when the expense was a reserve component) |
| | borrowing (5515) | anything else |
| Money to a certificate of deposit | investment | "Transfer to CD" |

Unscheduled contributions are set against the borrowings. A run that sums exactly to one borrowing within its year is its repayment. The rest are applied oldest borrowing first. A match by amount is a lead. The board's resolution says which loan a payment restored.

Each year's budget comes from PayHOA (`jason reserves --transfers --fetch` saves `data/payhoa/budgets/<year>.json`, read-only). The budget lines are specified in `mystique/banking.py` (`RESERVE_BUDGET_LINES`):

- "Transfer to Reserves" is the contribution;
- its child "Repayment" is the repayment of borrowed reserve funds;
- the other child, "Reserve Analyst", is the study's fee, not a transfer.

Each budgeted month is set beside the transfer that paid it. That is the month the memo names ("January 2024"), else the month the transfer was made. The report lists the months short and the months paid after they ended. A deleted liability account that named the reserve (a "Due to Reserves") is reported too, because deleting one removes its entries, and with them the record of what operating owed.

For each borrowing, the library is searched for the agenda with a "Notice of Intent to Borrow" in the 60 days before, the minutes of that meeting, and a borrowing resolution that names the amount. When the resolution is missing, the report prints the one the agenda cites. Nothing here changes PayHOA or decides that the statute was met.

This association's findings are in its private notes (mystique/notes/reserve-transfers.md).
