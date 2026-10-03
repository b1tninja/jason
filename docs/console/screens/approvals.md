# Approvals

`/approvals`, `/approvals/{id}` · phase 1 · CLI: `jason approvals`, `jason approvals show ID`

The model behind this screen is [approval-workflow.md](../approval-workflow.md): the `Approval` record, its states, item classes, decisions, re-plan, fingerprint, second person, and audit log. This page specifies what a person sees and does.

## Purpose and personas

A person reads a plan jason made, item by item, with each item's reason, rule, and evidence. They approve some or all of the approvable items and sign with their name. jason reads the live state again, refuses if anything moved, and applies only what was approved.

- **Manager:** plans, reviews, approves, applies, withdraws. The first signature on a two-person kind.
- **Director:** reviews, and gives the first or the second signature.
- **Secretary:** approves Google Doc kinds, and gives a second signature.
- **Treasurer:** gives the second signature on kinds that cost money.
- **Reviewer:** opens approvals waiting on a second person, and confirms or declines.
- **Counsel:** no access.

## Data

| Part | Source |
|---|---|
| The queue | `jason.approvals.store.list(status=..., kind=...)`; each row's `id`, `kind`, `status`, item counts by `ItemClass`, `requested_by`, `requested_at`, `first`, `second`, `cost`, `clock` |
| The kind | `jason.approvals.registry.KINDS[kind]`: `title`, `cli`, `risk`, `approver`, `reversible`, `cost`, `clock`, `rule`, `max_age_hours` |
| One approval | `jason.approvals.store.get(id)`: the whole `Approval` with its `Item`s |
| An item's rule, recited | `jason.api.cite_document(item.rule)` (`text`, `citation`, `inForce`, and the caveat). A board rule row is cited by its address (`ActionKind.rule`) |
| An item's evidence | `Item.evidence[]`: each `Evidence(label, address, level)`. A `jason://` address opens `/r/{address}`. A console path opens in place. A P2 address asks before it shows |
| A held item's board item | `Item.board_item`, and its row in `board_items` (`jason.mcp.county.board_items`) |
| The audit timeline | `jason.approvals.audit.read(approval=id)` |
| The plan's freshness | `Approval.read_at` against `ActionKind.max_age_hours` |

## Layout: the queue

```
+------------------------------------------------------------------------------------------+
| Approvals                                                          [ New plan v ]        |
| Status [Open v]  Kind [All v]  Waiting on [Anyone v]   [Filter]                          |
+------------------------------------------------------------------------------------------+
| Kind                          Status            Items                 Requested     Age  |
|------------------------------------------------------------------------------------------|
| Owner information: tags       In review         10 · 2 held · 1 pers  Jane Example  2 h  |
| Mailroom letters              Approved, 2nd     4 letters · $8.16     Jane Example  1 d  |
|                               person waiting                                              |
| Owner information: tags       Superseded        -> apr-...-9c1d       Jane Example  3 d  |
+------------------------------------------------------------------------------------------+
```

"Open" means planned, in review, approved, partially approved, applying, or failed. A filter is a GET with `status` and `kind` only.

## Layout: one approval

```
+------------------------------------------------------------------------------------------+
| Approvals > Owner information: PayHOA tags                                     In review |
| Planned by Jane Example · Oct 3, 08:40 · live read Oct 3, 08:40 · fingerprint 3f9a02c1d4e7 |
| Risk: member-facing record · Approver: one person · Reversible: yes, a tag is removed     |
| Clock: answers in PayHOA by Nov 1 (the cycle's deadline) [Legal]  29 days left            |
| CLI: jason approvals show apr-20991003T084000-1a2b  [copy]                                 |
+------------------------------------------------------------------------------------------+
| [changed-banner, only when the re-plan differs]                                          |
| [held-banner] 2 writes held for the board. Approving this plan does not approve them.     |
+------------------------------------------------------------------------------------------+
| APPROVABLE (8)                                         Show: [All] [Undecided] [Rejected] |
| [ ] Unit 12: Owner A                                    Approve group | Reject group      |
|   [ ] + member tag   (none) -> Notices: mail     Why: no election on file: the law      |
|                                                  sends first-class mail                  |
|                                                  Rule: Civil Code 4040(a)(2) [recite]    |
|                                                  Evidence: [Ledger] Unit 12 row          |
|   [ ] + unit tag     (none) -> Answered 2099     Why: this cycle's answer                |
|                                                  Evidence: [Form] Answer, Oct 2          |
|   Then: complete request 678, comment emailed to the owner (waits on the 2 writes above) |
|        Rule: the board's owner-information rule [recite]                                 |
| [ ] Unit 14: Owner B                                                                     |
|   ...                                                                                    |
+------------------------------------------------------------------------------------------+
| HELD FOR THE BOARD (2)                       never approvable                            |
|   Unit 15: occupancy tag   Board item BI-2099-04 · next meeting Oct 15 [open]          |
| FOR A PERSON (1)                             jason does not do these                     |
|   Unit 12: enter the mailing address in PayHOA [open in PayHOA]                          |
| CONFIRM WITH THE OWNER (0) · TEST ACCOUNTS LEFT OUT (1)                                  |
+------------------------------------------------------------------------------------------+
| COST: no cost: tag writes and a status change                                            |
+------------------------------------------------------------------------------------------+
| TIMELINE  Oct 3 08:40 jason planned (Jane Example asked) · 08:52 Jane Example approved 3 |
+------------------------------------------------------------------------------------------+
| [sticky approve bar]                                                                     |
| 5 of 8 approved · 1 rejected · 2 undecided    Your full name [Jane Example        ]      |
| Your name, the time, and fingerprint 3f9a02c1d4e7 are recorded. jason re-plans first.    |
|                                        [Approve 5 of 8 changes as Jane Example]          |
+------------------------------------------------------------------------------------------+
```

Below 768 px each write row becomes a card: the change, before → after, the reason, the rule link, the evidence chips, then the decision. The approve bar stays sticky at the foot. The page reserves the bar's height at the bottom, so a focused row is never hidden under it (WCAG 2.4.11).

## Components

`page-header`, `status-badge`, `deadline-badge`, `person-chip`, `changed-banner`, `held-banner` (and its `--inline` variant on a held row), `write-row` (`--held`, `--person`, `--changed`, and `.jc-writes__then` for a dependent completion), `evidence-chip`, `recitation` (in a disclosure under "recite"), `cost-summary` (`--none` for tag writes), `approve-bar`, `confirm-panel` (for the second person), `result-panel` (after apply), `approval-card` (in the queue), `data-table`, `filters-bar`, `job-status` (planning and applying run as jobs).

**Two kinds of "held".** The planner's class `HELD_FOR_BOARD` (a response-policy finding) puts an item in the "Held for the board" section with no controls. A person's decision `Decision.HELD` (the approve bar's **Hold for the board**) refers an approvable item to the board: it needs a reason, is not written, and on submit proposes a board item (`tasks.board_items.propose`, signed by the person). The row then shows "Held for the board by Jane Example: <reason>" and links the board item. The two are labeled apart: "held for the board" (jason's policy finding) and "held for the board by NAME" (a person's decision).

## Actions

| Control | Calls | Approval effect | CLI |
|---|---|---|---|
| New plan (by kind) | `jason.approvals.plan(kind, scope, by)` as a job, on one live read | Creates an approval, `planned`. Supersedes an open one of the same kind and scope | `jason approvals plan KIND --by NAME` |
| Approve, reject, or hold an item | `decide(id, item, APPROVED, REJECTED, or HELD, by, reason)` | `planned` → `in review`. A rejection or a hold asks for a reason of a few words, in place, before it saves. A hold proposes a board item on submit | `jason approvals decide ID --approve ITEM` |
| Approve or reject a group | The same, for each approvable item in the group | Each item logged on its own | `--approve ITEM...` |
| Approve all approvable | The same, for every approvable item. It never touches a held, for-a-person, or confirm item | Each item logged on its own | `--approve-all` |
| Submit (the approve bar) | `submit(id, by)` with the fingerprint the page showed | `approved` or `partially approved`; none approved: `withdrawn` with "nothing approved", and its holds still propose their board items | `jason approvals submit ID --by NAME` |
| Confirm (second person) | `confirm(id, by)` with the fingerprint | Sets `second`. Refused for the first signer's or requester's name | `jason approvals confirm ID --by NAME` |
| Decline (second person) | `decline(id, by, reason)` | Back to `in review`; decisions kept; `first` cleared | `jason approvals decline ID` |
| Apply | `apply(id, by)` as a job, under the store lock and the kind's resource lock | `applying`, then `applied`, `failed`, or `superseded` | `jason approvals apply ID --by NAME` |
| Re-plan | `plan(kind, scope, by)` | A new approval with `supersedes` set; earlier decisions shown as hints, not counted | `jason approvals plan` |
| Withdraw | `withdraw(id, by, reason)` | `withdrawn` | `jason approvals withdraw ID` |
| Recite (on an item) | `cite_document(item.rule)` | None | `jason cite "EXPR"` |
| Show (a P2 evidence chip) | The reveal endpoint, one field | None; logged as `reveal` by kind | — |
| Open in PayHOA (for a person) | A link to the owner's page in PayHOA's own interface | None | `jason party` |

**Submit copy.** The button says what will be signed: "Approve 5 of 8 changes as Jane Example". With every approvable item approved: "Approve all 8 changes as Jane Example". When some are undecided, the button is disabled and says why beside it: "Decide 2 more changes to submit." ([style.md](../content/style.md#confirmations-and-approvals))

**Apply copy.** For a reversible kind: "Apply 5 changes now". For a kind whose `reversible` begins "no", apply asks the person to type the count of letters or messages, as GitHub asks for a repository's name before it deletes it ([patterns.md](../content/patterns.md#undo-and-no-undo)): "This mails 4 letters and charges the association $8.16. A letter cannot be recalled once it is mailed. Type 4 to apply."

## States

| State | What shows |
|---|---|
| Planning (job running) | `job-status` with "Reading PayHOA…", then "Planning…". The page refreshes to the new approval when done |
| Plan failed | `states` (error): the live read's error and its fix. `KeeperAuthRequired`: "jason could not sign in to PayHOA: no Keeper session. Run `jason login` in a terminal, then plan again." Logged as `plan.failed` |
| Planned, nothing to write | "Nothing to write. Every owner's tags already match their answers." Held and for-a-person sections still show |
| In review | As drawn |
| Plan too old | Before apply: "This plan was read 26 hours ago, longer than the 24 this kind allows. Re-plan to apply." Approve stays enabled; Apply is replaced by Re-plan |
| Changed since review | `changed-banner` first, both fingerprints, what changed, and Re-plan. The approve bar is `--blocked` |
| Waiting on a second person | `confirm-panel` for anyone but the first signer and the requester; for them: "Waiting on a second person. You signed this plan, so you cannot confirm it." |
| Applying | `job-status`, item results streaming in a `role="status"` region: "Applied 3 of 5" |
| Applied | `result-panel`: written, failed, skipped, each in a disclosure. Skipped items say why: rejected, held for the board, for a person, changed |
| Failed | `result-panel --failures`, failed open. Each failed item: what happened and what next. An `uncertain` item: "The request went out and no answer came back. The next plan's live read will show whether it was written. Do not apply again until then." |
| Superseded | "Superseded by apr-… on Oct 3, 09:15: the live state changed. Open the new plan." Read-only |
| Withdrawn | Who, when, and why. Read-only |

## Privacy

- Item labels are P1: unit and owner name ("Unit 12: Owner A"). The reviewer sees them as the approval shows them.
- An item's value is a tag name or a status (P1). An item never carries an email, an address, or an account number. The planner refuses a value `intake.secret_reason` flags.
- Evidence chips at P2 render as `masked-field` until shown. A P3 chip is listed by kind only unless the private view is on.
- The audit timeline shows names, times, and events, never values above P1.
- Counsel has no access. A treasurer opening a non-money kind sees it read-only.

## Acceptance criteria

1. Every item renders in exactly one section by its `ItemClass`. Held, for-a-person, and confirm items have no checkbox and no decision control in the HTML.
2. "Approve all approvable" sets only `APPROVABLE` items. A test with a held item checks it stays undecided.
3. The submit button's label always states the approved count, the approvable total, and the signer's name, and changes as decisions change.
4. A rejection or a hold without a reason is refused with "Give a reason of a few words for rejecting this change." (or "…for holding this change for the board."). A person's hold renders as "held for the board by NAME", apart from the planner's held section.
5. The second-person form refuses the first signer's and the requester's names, compared casefold and trimmed, on the server. The same name with different case and spaces is refused.
6. A POST whose fingerprint differs from the stored one is refused with "This plan changed since you opened it. Reload to see the new plan." and changes nothing.
7. When the re-plan differs at apply, nothing is written, the approval becomes `superseded`, and the new approval's page shows the changed items marked and earlier decisions as hints only.
8. After apply, the result panel's counts match the audit log's `item.applied`, `item.failed`, and `item.uncertain` events.
9. Each item's rule opens its recitation (words, citation, version in force, caveat) before any reading.
10. The sticky approve bar never covers the focused element: a keyboard walk through 30 rows keeps each focused row visible.
11. Item checkboxes and decision buttons are at least 24 by 24 CSS pixels, or spaced to pass WCAG 2.5.8.
12. Applying a kind whose `reversible` begins "no" requires the typed count, and the count must match the approved items.
