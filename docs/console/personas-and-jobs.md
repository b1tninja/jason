# Personas and jobs

Who uses the console, the jobs each one does there, and what each must never see or do.

Until the console has sign-in (phase 5, [security-and-privacy.md](security-and-privacy.md#identity)), there is one user: the person at the manager's machine. Every visit, they say who they are acting as (a named person) and in what role. A role decides:
- which screens and data levels the session shows;
- which approvals the person may give.

The console never infers a role from a name. The roster of names and roles is a private fact. It lives in `data/spec/<profile>.json`, read through `jason.community.private.facts`, and is never checked in.

Roles are a closed set: `Role` in `jason.console.identity` (see [security-and-privacy.md](security-and-privacy.md#roles)). The data levels are defined in [security-and-privacy.md](security-and-privacy.md#data-levels):
- **P0:** the association's public documents;
- **P1:** members' names and units;
- **P2:** contact details;
- **P3:** restricted;
- **P4:** secrets.

## Manager

The person who runs the association day to day, and who today runs the CLI.

**Jobs to be done**
- See what needs attention today, most urgent first. A passed legal clock comes before anything else (`attention.Urgency.LEGAL`).
- Review jason's plans and approve the routine writes:
  - the owner-information cycle's tags;
  - requests completed under the board's rule;
  - calendar events and Gmail drafts.
- Hand to the board what jason holds for it, and to a person what jason cannot enter.
- Answer intake and onboarding questions, signed with their name.
- Follow a notice from its requirement to its delivery to its proof (`jason://notice/KEY`).
- Track members' requests against their clocks, and draft acknowledgments for a person to send.
- Record a duty done, with its evidence (`record_completion`).
- Start a long read (a sync, a live plan) and see when it is done.

**Sees:** P0 to P2. P2 is masked by default and shown on request, logged. P3 only when the private view is opened for a stated reason, which is logged. A restricted book, such as executive-session minutes, opens only in that view.

**Never:**
- approves an item held for the board;
- is the second person on their own plan or approval;
- enters or sees a secret: the console has no field for one, and a Keeper record is named by title only;
- approves, denies, or assigns a member's request (AGENTS.md boundaries; no such button exists);
- sends a broadcast to members or mails a letter without a separate Mailroom approval.

## Board president or director

A director who reads the console during or before a meeting. Phase 5 gives directors their own sign-in. Until then, a director uses the console at the manager's machine or sees exports.

**Jobs to be done**
- Read the board's queue:
  - items held for the board, each with its finding, its board item, and the rule that is silent;
  - conflicts (`document_conflicts`);
  - the action items (`board_items`).
- See the clocks the board answers for: meeting notice and minutes (`meeting_watch.watch`), and rule-change notices (`record_stages.histories`).
- Be the second person on a high-stakes approval, for example a Mailroom send or a legal hold.
- Read the governing documents as recited, with the history of each section.

**Sees:** P0 and P1. P2 only on an item they are asked to decide, masked until revealed. P3 executive-session material in the private view, when the director is entitled to it as a director.

**Never:**
- approves their own plan or confirms their own approval;
- uses an approval to make a board decision: a decision is made in a meeting and recorded in the minutes, and the console records only that it was made and where;
- sees a secret.

## Secretary

Keeps the minutes, the notices of meetings, and the association's records.

**Jobs to be done**
- See each meeting's notice clock (Civil Code 4920) and minutes clock (4950(a)), and which record meets each (`meeting_watch.Standing`).
- Read a minutes draft beside its checks (`minutes_draft.checks`), and fill each blank the draft leaves for the Secretary.
- Follow the stages of a rule change (`record_stages.rule_change_histories`) and of minutes (`record_stages.minutes_histories`).
- Approve the private Docs for agendas and packets (`board --agenda --doc`, `board --packet --doc`).

**Sees:** P0 and P1. P3 executive-session minutes in the private view, logged.

**Never:**
- publishes or posts minutes from the console: jason posts nothing, and a draft stays DRAFT until the board approves it;
- sees members' contact details except on a notice's delivery follow-up, and then masked.

## Treasurer

Answers for the books, the reserves, and the bank.

**Jobs to be done**
- Read budget against actual (`budget_status`), the bank balances (`bank_accounts`), the reconciliations (`bank_reconciliations`), the reserve study and transfers (`reserve_study`, `reserve_transfers`), invoice checks (`invoice_review`), and collections (`association_collections`).
- See the finance clocks on the schedule (`schedule_agenda(role="treasurer")`).
- Be the second person on a write that costs money: a Mailroom send, or a mail batch.

**Sees:** P0 and P1. Account numbers by their last four digits only. Delinquency by unit at P1, and owners' names at P1.

**Never:**
- sees a full account number, routing number, or online-banking credential (the console has none to show);
- submits an account to collection: that is a sheet or CSV handoff only, and no console action exists for it.

## Second-person reviewer

Any person on the roster who is not the one who made the first approval. Often this is a director or the treasurer.

**Jobs to be done**
- Open an approval waiting for a second person.
- Read the same plan, the evidence, and the cost.
- Confirm or decline, signed with their own name.
- Confirm a high-stakes intake answer (`onboarding_confirm`). The rule is the same: not the person who answered.

**Sees:** what the approval shows, at the level their own role allows. Masked fields stay masked unless their own role allows a reveal.

**Never:**
- confirms when their name matches the first approver or the requester. The comparison ignores case and surrounding spaces, as `intake.confirm` does. The console refuses, it does not merely warn.
- edits the plan: a changed plan is a new plan, and both approvals start over.

## Counsel

The association's attorney: a narrower, read-only view, granted when the board asks.

**Jobs to be done**
- Read the governing documents as recited, with history and in force on a date (`cite_document`, `living_document`, `jason://` addresses).
- Read conflicts marked for counsel (`document_conflicts`, status "counsel"), and the leads behind them.
- Read a notice's requirement and proof (`notice_record.build`, `notice_proof.build`).
- Read a legal matter's case file when the board grants it (`case_file`, `legal_cases`).

**Sees:** P0, and the documents and matters the board grants: a matter's P3 file. No member contact details, unless a matter needs them.

**Never:**
- sees the Approvals screen, makes or confirms any write, or answers an intake question;
- sees other matters, the membership list, or owners' contact details, unless the board grants them;
- sees an approval's audit trail, except for a matter it was granted.

## Who approves what, in one table

| Kind of decision | Who | Where it is recorded |
|---|---|---|
| A routine write jason planned (the registry's approver rule `manager`) | One named person in the manager or director role | The approval and the audit log |
| A write a board rule already authorizes (approver rule `board-rule`) | One named person, with the rule row recited on the item | The approval cites the rule row |
| A high-stakes write (approver rule `two-person`) | Two different named people, neither the requester | The approval, with both names and times |
| A question no rule answers (`Outcome.BOARD`) | The board, in a meeting | The board item and the minutes. The console only shows it |
| A high-stakes intake answer | The person answering, then a different person confirming | `data/intake/asks.json` (`answered_by`, `confirmed_by`) |
