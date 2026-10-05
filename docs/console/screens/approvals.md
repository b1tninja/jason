# Approvals

`#/approvals` · phase 1 · CLI: `jason approvals`, `jason approvals show ID`

The model behind this screen is [approval-workflow.md](../approval-workflow.md): the `Approval` record, its states, item classes, decisions, re-plan, fingerprint, second person, and audit log. This page specifies what a person sees and does.

## In the console

**Approvals** (`#/approvals`, `ConsoleApprovals`) is built for **letters**: every letter jason drafted, grouped by whose turn it is (`ApprovalsInbox`): with someone signed in, "Waiting on you" first (the letters awaiting a personal approver's approval that person may approve, or "Nothing is waiting on you."), then "Waiting on others" (each naming its approver), "Waiting on the board's vote" (every letter whose approver is the board, for everyone: a vote at a meeting (CIV 4910) on an item on the posted agenda (CIV 4930), which the president or the secretary records afterwards with the meeting's date), "Approved, not sent", and "Sent"; with no one signed in, "Awaiting approval", "Approved, not sent", and "Sent". The selected one opens below as a `DraftLetter`, and the nav counts the letters awaiting an approver. A board approval there is the vote recorded by the president or the secretary with the meeting's date.

**What this spec adds:** the engine's **plans of writes** on the same screen (`PlanApprovals`), and the review of one of them (`PlanReview`). The routes are `jason.web.approvals` ([web-ui.md](../../web-ui.md#approvals)) and the components are built ([components.md](../components.md#approval)). The letters' part is unchanged.

**As built, and what is still to do.** The plans are a "Plans of writes" table above the "Letters" groups, on one screen, not one interleaved list; a plan opens below its row as a `PlanReview`. Four things the layouts below show are not wired yet:
- **The item's rule** shows as its citation ("Rule: Civil Code 4040(a)(2)"), with no "recite" disclosure: `PlanApprovals` passes `PlanReview` no `recitations`, and the `cite` loader that would feed them is not built ([governing-documents.md](governing-documents.md)).
- **The header's risk and reversibility line** is not shown: the plan's answer carries no kind record (see Data, "The kind").
- **The nav count** is the letters waiting on a person; it does not add the plans.
- **"Open in PayHOA"** (Actions) has no control.

## Purpose and personas

A person reads a plan jason made, item by item, with each item's reason, rule, and evidence. They approve some or all of the approvable items and sign with their name. jason reads the live state again, refuses if anything moved, and applies only what was approved.

- **Manager:** reviews, decides, submits, checks, and applies (with `--allow-apply`) or runs the apply command; withdraws. The first signature on a two-person kind.
- **Director:** reviews, and gives the first or the second signature.
- **Secretary, Treasurer:** give the second signature where a kind or an item needs one.
- **Reviewer:** opens approvals waiting on a second person, and confirms or declines.
- **Counsel:** no access.

## Data

| Part | Source |
|---|---|
| The inbox | `GET /api/approvals`: the letters (`letters`, `groups`, `pending`, `people`) and the engine's approvals (`approvals[]` with id, kind, title, status, counts by class and decision, who asked, when; `approvalsOpen`; `approvalsCaveat`). `?status=`, `?kind=` filter the plans |
| One plan | `GET /api/approvals/<id>`: the `Approval` as stored (`approval.schema.json`), with its items, decisions, signatures, `costCents`, `clock`, `summary`, `result`, and `notes` |
| The kind | `jason.approvals.registry.get(kind)`: `title`, `cli`, `risk`, `approver`, `reversible`, `cost`, `clock`, `rule`, `max_age_hours`. Not in any answer yet: add it to the plan's answer, or as `GET /api/approvals/kinds` (the CLI has `jason approvals kinds`). `PlanPanel` needs `approver` (is a second person always needed) and `max_age_hours` from it: today it passes the component's defaults, one person and 24 hours |
| An item's rule, recited | `jason.api.cite_document(item.rule)` where the rule is a citation; a rule row by its address. A loader to add (`cite`, shared with [governing-documents.md](governing-documents.md)); `PlanReview` takes the answers as `recitations`, keyed by the rule, and the view passes none yet |
| The audit | `GET /api/approvals/audit?approval=<id>` (`?verify=1` for the chain) |
| Whether apply is on | `GET /api/session`: `applyEnabled`, `liveChecks` |
| Who is signing | "Signed in as" (`useSession`), over `people` |

## Layout: the inbox

```
+------------------------------------------------------------------------------------------+
| Approvals                                                                                 |
| Everything jason drafted or planned that is waiting on a person.                          |
+------------------------------------------------------------------------------------------+
| WAITING ON A PERSON                                                                       |
| Owner information: PayHOA tags   plan     In review        10 changes · 2 held   2 h  >  |
| Notice of the Oct 7 meeting      letter   Awaiting the secretary                 1 d  >  |
| APPROVED, NOT YET APPLIED OR SENT                                                         |
| Owner information: PayHOA tags   plan     Partially approved  8 of 10 · apply off   >    |
| DONE                                                                                      |
| Owner information: PayHOA tags   plan     Superseded -> apr-...-9c1d             3 d     |
+------------------------------------------------------------------------------------------+
```

## Layout: one plan

```
+------------------------------------------------------------------------------------------+
| Owner information: PayHOA tags                                                 In review |
| Requested by Jane Example · read Oct 3, 08:40 · fingerprint 3f9a02c1d4e7                  |
| Risk: member-facing record · one person · Reversible: tags yes; the owner's email no     |
| Clock: answers in PayHOA by Nov 1 · 29 days left                                          |
| jason approvals show apr-20991003T084000-1a2b [copy]                                      |
+------------------------------------------------------------------------------------------+
| [ChangedBanner, only when stale, superseded, or a check differs]                          |
| [HeldNote] 2 changes held for the board. Approving this plan does not approve them;      |
|            they go to the board's agenda.                                                 |
+------------------------------------------------------------------------------------------+
| TO DECIDE (8)                                          Show: [All] [Undecided] [Rejected] |
| Unit 12: Owner A                                                                          |
|   [ ] + member tag   (none) -> Notices: mail     Why: no election on file: the law      |
|                                                  sends first-class mail                  |
|                                                  Rule: Civil Code 4040(a)(2) [recite]    |
|                                                  Evidence: Ledger, Unit 12               |
|   [ ] + unit tag     (none) -> Answered 2099     Why: this cycle's answer                |
|   Then: complete request 678, comment emailed to the owner (waits on the 2 changes above)|
| Unit 14: Owner B                                                                          |
|   ...                                                                                    |
+------------------------------------------------------------------------------------------+
| HELD FOR THE BOARD (2)                     never approvable; on the board's agenda       |
|   Unit 15: occupancy tag   board item BI-2099-04 · meeting Oct 15                        |
| FOR A PERSON (1)                           jason does not do these                       |
|   Unit 12: enter the mailing address in PayHOA                                           |
| CONFIRM WITH THE OWNER (0) · WHAT FOLLOWS (3)                                            |
+------------------------------------------------------------------------------------------+
| COST: No cost: tag changes and a request status                                          |
+------------------------------------------------------------------------------------------+
| HISTORY  Oct 3 08:40 jason planned (Jane Example asked) · 08:52 Jane Example approved 3  |
+------------------------------------------------------------------------------------------+
| [sticky ApproveBar]                                                                      |
| 5 of 8 approved · 1 rejected · 2 undecided    Your full name [Jane Example        ]      |
| Your name, the time, and fingerprint 3f9a02c1d4e7 are recorded. jason re-reads first.    |
|                                        [Approve 5 of 8 changes as Jane Example]          |
+------------------------------------------------------------------------------------------+
```

After submit, the bar becomes: **Check** (re-read, write nothing), and either **Apply 8 changes now** (with `--allow-apply`) or the command `jason approvals apply apr-… --yes --by "Jane Example"` to copy. Under 720 px each `WriteRow` becomes a card, and the bar stays sticky at the foot with its height reserved.

## Components

`ScreenHeader`, `ApprovalsInbox` (letters), `PlanApprovals` and `PlanReview` (plans), `Pill` (status, item result), `DueDate` (the clock), `ChangedBanner`, `HeldNote` (and its inline form on a held row), `WriteRow`, `Evidence`, `Recitation` (in a disclosure under "recite"), `CostLine`, `ApproveBar`, `SecondConfirm`, `ApplyResult`, `AuditLog`, `Command`, `Confirm`, `DraftLetter` (letters, unchanged).

**Two kinds of "held".** The planner's class `held_for_board` (a response-policy finding) puts an item in "Held for the board" with no controls. A person's decision `held` (the bar's **Hold for the board**) refers an approvable item to the board: it needs a reason and is not written. `HeldNote` keeps the two apart: "held for the board" (jason's policy finding) and "held for the board by NAME" (a person's decision). Both say where the item goes: a board item, and the meeting's agenda ([approval-workflow.md](../approval-workflow.md#12-the-board-decides-by-vote)).

## Actions

| Control | Calls | Effect | CLI |
|---|---|---|---|
| New plan | none: a plan reads PayHOA live and is made in the terminal | The page shows the command | `jason approvals plan owner-info-tags --by NAME` |
| Approve, reject, or hold items | `POST /api/approvals/<id>/decide` (`items`, `decision`, `reason`, `by`), behind `Confirm` | `planned` → `in_review`. Reject and hold need a reason, asked in place | `jason approvals decide ID --items ITEM... [--reject \| --hold --reason TEXT] --by NAME` |
| Approve all approvable | the same with `items: "all"` | Each item logged as its own decision; never a held, for-a-person, or confirm item | `--all` |
| Submit | `POST /api/approvals/<id>/submit` (`by`) | `approved` or `partially_approved`; none approved: `withdrawn` ("nothing approved") | `jason approvals submit ID --by NAME` |
| Confirm (second person) | `POST /api/approvals/<id>/confirm` (`by`) | Sets `second`. Refused for the first signer's and the requester's names | `jason approvals confirm ID --by NAME` |
| Decline (second person) | `POST /api/approvals/<id>/decline` (`by`, `reason`) | Back to `in_review`; decisions kept; `first` cleared | `jason approvals decline ID --by NAME --reason TEXT` |
| Check | `POST /api/approvals/<id>/check` (token header) | Re-reads live and compares. Writes nothing | `jason approvals apply ID` |
| Apply | `POST /api/approvals/<id>/apply` (`by`, `confirm`: the fingerprint shown), only with `--allow-apply` | `applying`, then `applied` or `failed`; or `superseded` with nothing written | `jason approvals apply ID --yes --by NAME` |
| Withdraw | `POST /api/approvals/<id>/withdraw` (`by`, `reason`) | `withdrawn` | `jason approvals withdraw ID --by NAME --reason TEXT` |
| Recite | the rule's `Recitation` | None | `jason cite "EXPR"` |
| Open in PayHOA (for a person) (proposed, not built) | a link to the owner in PayHOA's own interface | None | `jason party` |

**Submit copy.** The button says what will be signed: "Approve 5 of 8 changes as Jane Example". With every approvable item approved: "Approve all 8 changes as Jane Example". With some undecided, the button is unavailable and says why beside it: "Decide 2 more changes to submit." ([style.md](../content/style.md#confirmations-and-approvals))

**Apply copy.** For a reversible kind: "Apply 8 changes now" (built, through `Confirm`, naming the signer and the fingerprint's first 12 hex). For a kind whose `reversible` says no for any part, the `Confirm` restates what cannot be undone and asks the person to type the count: "This marks 1 request complete and emails the owner the board's comment. An email cannot be recalled. Type 1 to apply." ([patterns.md](../content/patterns.md#undo-and-no-undo)). The type-the-count step is proposed: the built `Confirm` does not ask for it, and needs the kind's `reversible` (see Data) to know when to.

## States

| State | What shows |
|---|---|
| No plans | "No plan of writes on disk." with the command that makes one (`jason approvals plan owner-info-tags --by NAME`) |
| Planned, nothing to write | "Nothing to write. Every owner's tags already match their answers." Held and for-a-person sections still show |
| In review | As drawn |
| Plan too old | "This plan was read 26 hours ago. That is longer than the 24 hours this kind allows before apply." (`ChangedBanner`). Decisions stay, but the engine refuses an apply on a plan older than its kind allows ("plan again", `engine.problems`), so the banner should say to plan again. The built banner says "Decisions stand; apply reads live again first, or re-plan now", which the engine does not do (a defect in the banner, not in this spec) |
| Changed since review | `ChangedBanner` first, with what changed and the new approval. `ApproveBar` is blocked |
| Waiting on a second person | `SecondConfirm` for anyone but the first signer and the requester; for them: "Waiting on a second person. You signed this plan, so you cannot confirm it." |
| Approved, apply off | The terminal command, and "Apply is off in this console: a person applies from a terminal, or starts jason-web with --allow-apply." |
| A live read needs a person | The server answers 503 with the sign-in's own message, then "run `jason login` in a terminal; jason-web never asks for a credential" (`KeeperAuthRequired` for PayHOA, `GoogleAuthRequired` for Google). Nothing was written |
| Applying | Busy, then `ApplyResult` |
| Applied | `ApplyResult`: applied, and what was not, each in a disclosure. Not applied says why: rejected, held for the board, for a person |
| Failed | `ApplyResult` with failures open. An uncertain item: "The request went out and no answer came back. The next plan's live read will show whether it was written. Do not apply again until then." |
| Superseded | "Superseded by apr-… on Oct 3, 09:15: the live state changed. Open the new plan." Read-only |
| Withdrawn | Who, when, and why. Read-only |

## Privacy

- Item labels are P1: unit and owner name ("Unit 12: Owner A"). An item's value is a tag name or a status. An item never carries an email, an address, or an account number; the planner refuses a value `intake.secret_reason` flags.
- The routes mask anything that looks like an email address or a phone number before it leaves the server.
- The audit shows names, times, and events, never contact details.
- The owner view does not show this screen.

## Acceptance criteria

1. Letters and plans render in one inbox, each row naming its kind; the letters' behavior is unchanged.
2. Every item renders in exactly one section by its class. Held, for-a-person, confirm, and informational items have no checkbox and no decision control, and the server refuses a decision on one (400, in the engine's words).
3. "Approve all approvable" sets only approvable items. A test with a held item checks it stays undecided.
4. The submit button's label always states the approved count, the approvable total, and the signer's name, and changes as decisions change.
5. A rejection or a hold without a reason is refused with "Give a reason of a few words for rejecting these changes." (or "…for holding these changes for the board.").
6. The second-person form refuses the first signer's and the requester's names, compared casefold and trimmed, on the server.
7. Without `--allow-apply`, no Apply button renders and the command does; a forced POST is refused and writes nothing.
8. With it, an apply whose echoed fingerprint differs from the approval's writes nothing (409); a re-plan that differs supersedes the approval, writes nothing, and the new approval shows the changed items and earlier decisions as hints only.
9. After apply, `ApplyResult`'s counts match the audit log's `item.applied`, `item.failed`, `item.uncertain`, `item.blocked`, and `item.not_applied` events.
10. Each item's rule opens its recitation (words, citation, version in force, caveat) before any reading. Not met yet: the rule shows as its citation (see the note at the top).
11. The sticky `ApproveBar` never covers the focused element: a keyboard walk through 30 rows keeps each focused row visible.
12. Item checkboxes and decision buttons are at least 24 by 24 CSS pixels, or spaced to pass WCAG 2.5.8.
