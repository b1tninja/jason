# Flagged items: a finding the board has not answered, which a director or the manager may still decide

The approvals engine used to treat an item **held for the board** as never approvable: jason found that no rule the board adopted answers it, and the plan could only wait for a board vote. A plan could carry such items for weeks with no way to review them, change what was held, or act on one.

**Decided 2026-10-11 (the board's Treasurer-Secretary):** "held" is a **flag for further review**, not a lock. A director, an officer, or the manager can review a flagged item in full and **act on it**.

**Status: built** (2026-10-11). The engine (`decide(..., exception=True)`, `refer`), the exceptions log (`jason.approvals.exceptions`), `jason approvals decide --exception`, `refer`, and `exceptions`, the web routes (`decide` with `exception: true`, and `refer`), and the plan review (`FlaggedItem`) are in. The choices made in the build are in section 7.

## 1. What does not change

- **jason never decides a flagged item.** The finding stays jason's: "No rule the board has adopted answers this." A person decides, in their own name, as a **one-off decision**. A one-off decision needs no rule (Civil Code 4355(b)(2)) and is not a rule; jason adopts none.
- **A flagged item is still not in the plan's ordinary approval.** Approving the plan does not approve a flagged item. Each is decided on its own, with a reason.
- **The board is still the place to write the rule.** The board item stays linked, and the plan shows how many times the same finding has been decided by exception, with "propose a rule" (AGENTS.md, "Where the law is silent, write it down": a policy applied the same way every time is the board's best evidence of good faith, and exceptions case by case are the opposite).
- Stored data does not change: the class is still `held_for_board`. Only the words and the rules about deciding it change.

## 2. The model

| | Before | Now |
|---|---|---|
| Word on screen | "Held for the board" | **"Flagged for review"** (the board-held word stays for an item a *person* held, `decision: held`) |
| Can a person decide it | no ("never approvable") | **yes**: approve as a one-off exception, reject, or keep it flagged, each with a reason |
| Who | n/a | any signed-in board office, or the manager (the offices that open P2) |
| Signatures | n/a | an approved exception is **high-stakes**: a second, distinct person signs before it applies (the engine's existing second-person rule) |
| Record | n/a | each exception goes in the **exceptions log** (`data/approvals/exceptions.jsonl`, append only) |

**Actions on a flagged item**
- **Approve as a one-off exception.** A reason is required, in words (not "ok"). The item then needs a second signature. The label reads "One-off decision, not a rule."
- **Reject.** A reason is required; nothing is written.
- **Keep flagged** (a note): leaves the item flagged for the next reviewer. The note is required, by the engine's rule that a hold says why.
- **Refer to the board:** creates or refreshes the board item for the finding (the loop of the approval workflow, section 12) with this plan's evidence. Does not decide anything.

**What a reviewer sees on the item:** the change that would be written (target, from, to), why it is flagged (the finding and the rule row that raised it, `owner_responses.RULES` etc.), the evidence, the board item and its status, and **the exceptions already made under this finding** (who, when, the reason, applied or not).

## 3. The exceptions log and the nudge to write a rule

One line a decision, never edited: `{at, approval, item, finding, boardItem, by, secondBy, decision, reason, applied}`. A correction is a later line.

When a finding has been decided by exception **twice or more**, the plan shows "This finding has been decided by exception N times. The board may want to write a rule" with a link to its board item. The number is the board's to change (a named constant, 2). jason proposes a policy; it never makes one.

## 4. Edges

- **A control the board adopted** (docs/controls.md) can add signers or narrow who may sign; an exception follows the same rule as any approved item of the kind.
- **Superseded plans:** a newer plan of the same kind and scope supersedes the older; exceptions decided on the old plan stay in the log with `applied: false`.
- **Basis changed:** if the item's basis changed since review (the engine's `CHANGED` re-plan check), the decision is void and the reviewer decides again.
- **Executive session / member privacy:** the exceptions log holds ids and words, never an address or name of a member beyond what the plan item already shows to a viewer at their level.
- **The terminal-only kinds** (the Mailroom send) have no flagged items; if one ever did, it would still apply only from the terminal.
- **Occupancy follow-ups** to owners remain held until the board takes up the rental-approvals item (an owner-contact rule, separate from this); an exception here changes a PayHOA tag only if the person approves that write.

## 5. Screens

- **Plan review (`PlanReview`)**: the "Flagged for review" section replaces the "Held for the board" note: a list of items, each expandable to its change, finding, evidence, board item, and exceptions history, with the four actions above in `Confirm` dialogs; the heading counts say "3 flagged, 1 decided by exception".
- **ApproveBar:** unchanged for the approvable items; it mentions flagged items by count and never approves them.
- **`jason approvals`:** `decide --item ID --exception --reason TEXT --by NAME` approves a flagged item; `show` lists flagged items and their history; `exceptions` lists the log.

## 6. Decisions for the board

- The threshold of exceptions before the plan suggests a rule (recommended: 2).
- Whether an exception needs a second signature in every case (recommended: yes; the engine's high-stakes rule) or only above a cost.
- Whether the manager alone may approve an exception when the plan's kind is one-person (recommended: no; a second distinct person is required).

## 7. Choices made in the build

- **Only approvals count as exceptions.** The log records every decision (approved, rejected, kept flagged), but the count that raises the nudge, and the heading's "decided by exception", count the exceptions approved, one for each plan and item (its latest decision). A rejection affirms the finding; it is history, not an exception to it.
- **The reason.** An approval needs a reason of at least two words (`exceptions.REASON_WORDS`); "ok" is refused. A rejection and a kept flag need a reason or note of any words, as every hold does.
- **A decision is void when the basis moves.** The re-plan at apply compares an approved exception like any approved item; a changed basis, or a changed class, supersedes the approval and the reviewer decides again. The log keeps the old decision with `applied: false`.
- **The plan's fingerprint is unchanged.** It still covers only the approvable items. A flagged item's basis is checked at apply instead, so a change to it is caught, and each decision records the fingerprint it was made on.
- **Later facts are later lines.** `secondBy` and `applied` reach the log as `event: second` and `event: applied` lines for the same plan and item; reading the log folds them into the decision. The log also carries the action `kind` and an `event` word beside the fields listed in section 3.
- **Referring writes a board item and an audit line.** `refer` makes or refreshes the finding's board item (its own id, else `flagged-` and a slug of the rule) and proposes it for the next agenda. It carries no member's name or address, adds this plan's evidence, and is logged `item.referred`. The plan's flagged items of that finding then name the board item.
- **Who may.** The console takes an exception or a referral only from a signed-in roster person whose office opens P2 (a board office or the manager); an administrator without an office, and an admin viewing as someone else, are refused. Where console sign-in is not set up, the named person is the record, as for any decision.
