# Personas and jobs

Who uses the console, the jobs each one does there, and what each must never see or do.

Until the console has sign-in ([security-and-privacy.md](security-and-privacy.md#identity)), there is one user: the person at the manager's machine. They pick who they are in "Signed in as", a sample picker over the profile's officers (`Community.officers()`: a name, an `OfficerRole`, and what that person may approve). The pick puts their name on the record; it grants nothing. Today the console has one audience switch, Board or Owner view, and no roles. Once roles are enforced, a role decides:
- which screens and data levels the session shows;
- which approvals the person may give.

The console never infers a role from a name. The names come from the private facts (`data/spec/<profile>.json`, read through `jason.community.private.facts`), never checked in.

The roles below are proposed ([security-and-privacy.md](security-and-privacy.md#roles)): manager, director, secretary, and treasurer match `OfficerRole`; reviewer (second-person, and the committee reviewer below) and counsel are not in it yet. The owner is a view, not a role: no owner can sign in. The data levels are defined in [security-and-privacy.md](security-and-privacy.md#data-levels):
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
- **What applies (proposed, `#/applies`).** Read jason's three-valued answer for each rule row and see the facts it turns on or lacks; file the questions the undetermined rows raise; answer a question a record states (a count, a standard, a date) with the record named, signed as themselves; describe an event to the notice catalog and read which notices it requires. Read the buildings' inspection record, with **date not on record** where a counting date is missing. ([handoff-applicability-questions.md](handoff-applicability-questions.md))
- **Take a question to the board.** Put a fact the board decides, a reading, a program draft, or an improvement request on the board's agenda, as a signed act with no recommendation attached. Never settle one by choosing.
- **The confirmations queue (proposed, `#/confirmations`).** Re-read a stale reading, put a candidate reading on the board's agenda, record that two readings remain, reject or skip one, and label a gold row. ([handoff-confirmations-queue.md](handoff-confirmations-queue.md))
- **Programs (proposed, `#/programs`).** Find which required programs have no document or no act on record, read the requirement recited element by element, confirm or correct a detected mandate, bind a document as the program's, generate a draft from the base template, and put it on the board's agenda. After the vote, add the derived obligations to the schedule's record and record each done. ([handoff-programs.md](handoff-programs.md))
- **Improvement requests (proposed, `#/requests?id=`).** Record a request complete or the list of what is missing, record a wait, draft the decision letter after the vote, post it in the PayHOA thread by hand and record where it was sent, record the owner's report of work, and add an entry to a unit's manual for an owner who asks. ([handoff-improvement-requests.md](handoff-improvement-requests.md))

**Sees:** P0 to P2. P2 is masked by default and shown on request, logged. P3 only when the private view is opened for a stated reason, which is logged. A restricted book, such as executive-session minutes, opens only in that view. The building inspection record's inspector, license number, and report name are P3 by their source (`data/spec`), so they show in the private view only; the building's reach and next due show without it.

**Never:**
- approves an item held for the board;
- is the second person on their own plan or approval;
- enters or sees a secret: the console has no field for one, and a Keeper record is named by title only;
- approves, denies, or assigns a member's request (AGENTS.md boundaries; no such button exists), including an improvement request: the board decides it by a vote;
- sends a broadcast to members or mails a letter without a separate Mailroom approval;
- answers a fact the board decides by choosing for the board, or answers any question in a way that picks between the profile's value and a person's answer (the row stays undetermined with both named);
- makes a reading the board's: a confirmation puts a reading on the agenda; only the board's recorded vote adopts it, and only the president or the secretary writes the profile row from that vote;
- adopts a program: the console has no control for it, and the adoption is read from the board's decision or the minutes;
- posts a comment to an owner in the PayHOA thread, attaches a file, or sets a request's status from the console (no gate yet): the console shows the text to copy;
- reads an owner's private manual entries: they are counted, never listed.

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
- **Read the board's brief for a program, an improvement request, a reading, or a fact the board decides:** the question, the criteria, the lettered options, and the facts, with no recommendation; a reviewer's recommendation beside it, named as theirs.
- **Confirm a reading for the agenda** (`#/confirmations`, proposed): read the words and the digest, then put the candidate on the board's agenda, or record that two readings remain (the board asks counsel). A re-read first, when the words changed.
- **Be the second person on a board fact's answer,** if the board puts acclamation, electronic voting, or the directors' quorum into the set a second person confirms (an open decision).
- **Move and vote at the meeting.** The director's vote is a roll call by name, recorded by the officer; it is not in the console's other screens.

**Sees:** P0 and P1. P2 only on an item they are asked to decide, masked until revealed. P3 executive-session material in the private view, when the director is entitled to it as a director.

**Never:**
- approves their own plan or confirms their own approval;
- uses an approval to make a board decision: a decision is made in a meeting and recorded in the minutes, and the console records only that it was made and where;
- sees a secret;
- confirms a reading "as a director's reading": the readings are jason's, the board's (by its recorded vote), or counsel's (from counsel's letter), and a director's strongest act is to put one before the board;
- writes the profile row for an adopted reading unless they are the president or the secretary.

## Secretary

Keeps the minutes, the notices of meetings, and the association's records.

**Jobs to be done**
- See each meeting's notice clock (Civil Code 4920) and minutes clock (4950(a)), and which record meets each (`meeting_watch.Standing`).
- Read a minutes draft beside its checks (`minutes_draft.checks`), and fill each blank the draft leaves for the Secretary.
- Follow the stages of a rule change (`record_stages.rule_change_histories`) and of minutes (`record_stages.minutes_histories`).
- Approve the private Docs for agendas and packets (`board --agenda --doc`, `board --packet --doc`).
- **Record what the board decided, once, where every vote is** (`#/room`, `#/decisions`). Other screens read that record: a reading's adoption, a program's adoption, an improvement request's decision.
- **Write the profile row from the board's decision** on a reading (`#/confirmations`, proposed): the secretary or the president only, from a decision on record whose outcome is approved. The result is a patch a person applies.
- **Record the conditions** an improvement request's approval carries, after the vote, and approve the decision letter's words as the officer who recorded the vote, with the meeting's date.
- **Record an adoption act jason did not find** for a program, with the record that states it (the minutes, a resolution); refused without one.

**Sees:** P0 and P1. P3 executive-session minutes in the private view, logged.

**Never:**
- publishes or posts minutes from the console: jason posts nothing, and a draft stays DRAFT until the board approves it;
- sees members' contact details except on a notice's delivery follow-up, and then masked;
- records a vote for the board that was not taken, or an adoption without the record that shows it: the console reads the decision and the minutes and takes no vote, meeting date, or officer's name from a form.

## Treasurer

Answers for the books, the reserves, and the bank.

**Jobs to be done**
- Read budget against actual (`budget_status`), the bank balances (`bank_accounts`), the reconciliations (`bank_reconciliations`), the reserve study and transfers (`reserve_study`, `reserve_transfers`), invoice checks (`invoice_review`), and collections (`association_collections`).
- See the finance clocks on the schedule (`schedule_agenda(role="treasurer")`).
- Be the second person on a write that costs money: a Mailroom send, or a mail batch.
- The treasurer has no job of their own on `#/applies`, `#/confirmations`, `#/programs`, or the improvement screens beyond what a director has. None holds an account figure, and an owner's figure on an improvement is the owner's, labeled "paid by the owner; not certified".

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
- Confirm a high-stakes intake answer (`onboarding_confirm`). The rule is the same: not the person who answered. An applicability answer waits for a second person only for a fact in the set `CONFIRMED` (empty today).
- Read the answer's own words, the record named, and the question's reasons before confirming. A confirmation of an answer is not a confirmation of a reading: the two are different queues.

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
- **Read a candidate reading's recited words and the question the board asks** (a reading marked "two readings remain", a program draft, an improvement request's need), as granted. Counsel's answer reaches the console as a letter a person records as **counsel's reading** (P3, the private view); counsel does not act in the console.
- **Read a program's requirement, element by element, and its draft**, where the board has asked about the owners' half or the notice a rule needs.

**Sees:** P0, and the documents and matters the board grants: a matter's P3 file. No member contact details, unless a matter needs them.

**Never:**
- sees the Approvals screen, makes or confirms any write, or answers an intake question;
- sees other matters, the membership list, or owners' contact details, unless the board grants them;
- sees an approval's audit trail, except for a matter it was granted;
- confirms, adopts, or records a reading, or sees the confirmations queue's other items: the queue is the roster's, and counsel's words enter it only as the passage a roster person records from the letter.

## Committee reviewer (proposed)

A person the board names to read improvement applications (an architectural or design committee member). Not in `OfficerRole`; the console's reviewer role is proposed ([security-and-privacy.md](security-and-privacy.md#roles)), and until it exists a committee member's note is entered at the manager's machine under their own name.

**Jobs to be done**
- Read an application, its completeness list, the standards recited (the statute's, then the board's adopted ones with their adoption dates), and similar earlier decisions in general words.
- Save a review note with their name, role, and date. A recommendation is theirs, shown as theirs, never inside the board's brief.
- Check work against the approval, with the evidence named, and record the check.

**Sees:** the one request at a time, P0 and P1; the owner's name and unit as the request carries them, masked contact details; the board's adopted standards.

**Never:**
- approves, denies, or decides: the board decides by a vote;
- sees another request, an owner's private manual, or the membership list beyond the request;
- sees a finding about an owner's entry without an approval (those go to the owner only), or a "records show work" lead (the board's, as a board item).

## Owner (a view, not a sign-in)

A member of the association. The console serves 127.0.0.1 and admits the roster's accounts, so an owner cannot open a console page today. The owner's view (`?view=owner`) is the manager's preview of what an owner is shown, and what an owner receives arrives through PayHOA's portal and thread and a generated packet a person delivers ([handoff-improvement-requests.md](handoff-improvement-requests.md#what-is-real-now-delivery-of-the-owners-view)).

**Jobs to be done**
- See their own requests in their own words: received, needs more from you, on the board's agenda, approved with conditions, denied, work confirmed, in your manual; the next step; the decision letter.
- Keep their unit's manual: record what was done, and choose, entry by entry, whether it is private, shared with the association, or made by the association, with the consequence read first.
- Make a summary for a buyer or a schedule for an insurer from the entries they choose, as their own document.
- Read which changes need approval, how to apply, and how to ask for reconsideration, with the provisions recited.

**Sees:** P0 and their own unit only. Their own entries, requests, and letters.

**Never:**
- sees an internal state that sounds like a ruling before a ruling exists, a proposed clock as a date, another unit, the reviewers' notes, or any finding meant for the board;
- sees `#/applies`, `#/programs`, `#/confirmations`, or a board item: none of them has an owner view;
- is shown a statement that an approval means a change is safe, lawful, insured, or worth what it cost.

## Who approves what, in one table

| Kind of decision | Who | Where it is recorded |
|---|---|---|
| A routine write jason planned (approver `one person`) | One named person in the manager or director role | The approval and the audit log |
| A write a board rule already authorizes (approver `one person`, the rule in `rule`) | One named person, with the rule row recited on the item | The approval cites the rule row |
| A two-person kind, or a high-stakes item (approver `two person`, or `high_stakes`) | Two different named people, neither the requester | The approval, with both names and times |
| A letter's words | The letter's named approver: an officer whose `approves` names it | The letter's own log |
| A letter for the board, or a question no rule answers (`Outcome.BOARD`) | The board, by a vote at a meeting, recorded by the president or the secretary with the meeting's date. Never a click | The board item, the decision (`data/board/decisions.json`), the minutes, and for a letter its log |
| A high-stakes intake answer | The person answering, then a different person confirming | `data/intake/asks.json` (`answered_by`, `confirmed_by`) |
| An applicability answer: a fact a record states (a count, a standard, a date) | One named roster person, with the record that states it; a second person only for a fact in `CONFIRMED` | `data/intake/asks.json`; the specification only by `jason intake --apply`, a person's act |
| A fact the board decides (acclamation, electronic voting, the directors' quorum) | The board, by a vote at a meeting. A roster person records what the board's record says, never the choice; where there is no decision, a person puts the question on the agenda | The board item and the decision; then `data/intake/asks.json` |
| An act on a candidate reading (agenda, two readings, reject, skip, re-read) | One named roster person; adopts nothing | The confirmations store, with the digests read |
| A reading becoming the board's | The board, by a vote at a meeting, recorded by the president or the secretary; the secretary or the president then writes the profile row from the decision, and a person applies the patch | The decision (`data/board/decisions.json`), the proposal patch, and the profile |
| A reading becoming counsel's | Counsel's letter, recorded by a person who may open P3, quoting its passage | The confirmations store and the patch |
| A program adopted | The board, by a vote at a meeting. A person generates the draft and puts it on the agenda. The adoption is read from the decision or the minutes, or recorded by a person with the record that states it | The decision, the minutes, `data/programs/` |
| An improvement request's decision | The board, by a vote at a meeting, recorded by an officer; conditions recorded by the recording officer; the letter's words approved by the officer who recorded the vote | The decision, the request's record, the letter's log |
| A request's completeness, review, delivery, work, and check | A named person each (the manager, the reviewer), as their own record; none is a decision on the request | The `improvements/` store, each step with `by` |
| A gold label, or a lesson's decision | One named roster person; a lesson for the board goes to its agenda | The confirmations store; a board item |
