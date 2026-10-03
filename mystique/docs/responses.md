# Members' requests: what this association's requests held

The general design is [docs/responses.md](../../docs/responses.md). This page records what the association's own requests showed.

## PayHOA's own fields

On the association's 75 PayHOA requests through October 2, 2026, only tags were ever set, on 2 of them. No request had a due date, an assignee, a vendor, approvals, or an AI analysis. The work queue lives in jason's clocks, not in PayHOA's fields.

## How well the kinds are read

Measured on October 2, 2026 with `jason respond --measure` (75 PayHOA requests, 314 email threads, hand-labelled in the private gold set):

| | Before | After |
|---|---|---|
| PayHOA requests right | 83% | 100% |
| PayHOA complaints, precision / recall | 50% / 25% | 100% / 100% |
| PayHOA maintenance, precision / recall | 100% / 81% | 100% / 100% |
| PayHOA questions, precision / recall | 64% / 96% | 100% / 100% |
| Email threads right | 59% | 76% |
| Email maintenance, precision / recall | 57% / 49% | 88% / 100% |
| Email complaints, precision / recall | 0% / 0% | 100% / 33% |
| Email rental and architectural applications, recall | 0% | 100% |
| All 389, right | 64% | 80% |

The rules were fixed against this same set, so the "after" column is an upper bound until new requests are labelled and measured.

## Open

- About nine email maintenance threads from 2024 and 2025 now show as overdue. They may have been answered by phone or in person; a person reads each and closes it or decides it.
- Whether a lender's request for an insurance certificate or the master policy is a 5200 record, and whether a copy of the governing documents is a 5205 request, are for counsel ([docs/responses.md](../../docs/responses.md), Limits).
