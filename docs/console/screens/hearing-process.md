# Hearing process

A member discipline hearing as a run, `#/work/hearing/<run id>`, with the list kept at `#/hearings` · Governance group · phase 2 · CLI: `jason hearing --list` (built); `jason hearing RUN` (to add)

## In the console

**Built:** `#/hearings` (`HearingsView`, loader `hearings`, `jason.web.sources.hearings` over `zoom.hearings`). A table of saved hearings (hearing time, unit, notice by, decision, where it stands, problems), and for one opened row: the `Clock` stages (notice by, hearing, decision by), the notice documents (`DocList`), the decision entry (findings, day, recorded by, behind `Confirm`, `POST /api/hearings/<key>` into `hearing_decisions.record`), and the decision notice as it would read (`NoticePreview`, `/api/templates`, kind `decision-notice`). Behind it: `jason hearing` (`--list`, `--doc`, `--create`, `--notice-on`, `--suspension`), the Gmail draft case `hearing`, the notice catalog rows `discipline-hearing` and `discipline-decision`, `jason notice-check discipline-hearing`, and the executive-session records of `#/room` and `board/decisions.json`.

**This spec adds the steps the law adds and the run around them:** the run page and its opaque id, the cure record, the member's request for executive session, the member's reply, the penalty-schedule check, the decision-notice delivery record, a 5855(g) checklist, and one decision store. It follows `hearing` (h1 to h16) in [board-governance.md](../../workflows/board-governance.md#24-hearing-no-sop-jason-hearing-civ-5855) and gap G4 in [design-gaps.md](../design-gaps.md); it adds no parallel screen to the spine ([work.md](work.md)).

## Purpose and personas

One member's hearing from the board's proposal to consider discipline to the written decision, so that no requirement the code states is skipped and each one shows what is on record. jason reads, computes dates, and records what a person says. It never imposes a fine or discipline, never mails a notice, and never decides. The board decides; the secretary records.

- **President or manager:** states the matter, plans the dates, and writes and delivers the notice.
- **Secretary:** records the member's requests, the cure, the decision, and the day the decision notice was delivered.
- **Director:** reads the run as an officer does (same access to information); decides at the hearing.
- **Counsel:** reads the requirements and the proof, on grant.
- **Treasurer:** reads the run as a director or an officer does (same access to information; the treasurer's office opens P3 in the private view since 2026-10-11).

## Data

| Part | Source | State |
|---|---|---|
| Run list and one run | `jason.workflows` over the `hearing` definition; the process facts of the run record (id, dates, requests, cure, reply, penalty check, links) | Run page and record: **to add** |
| Saved hearing row | `zoom.hearings(data_dir)`: `start`, `noticeBy`, `noticeOn` (a person's statement), `decisionByIfHeld`, `executiveNoticeBy`, `problems`, `standing`, `scheduled`, `zoom`, `noticeDoc`, `decision`; loader `hearings` | Built (rows keyed by day and address slug, `key_of`) |
| The board's decision | `board/decisions.json` (`Decision`: `motion`, `session`, `subject`, `votes`, `recused`, `outcome`, `by`); executive decisions carry `session: "executive session"` and `subject` | Built. Findings and `noticeDueBy` today live on the hearing row: see Decisions 1 |
| The statute | `data/authorities/CIV/CIV-5850-5875.md` (5850, 5855, 5865), `CIV-4900-4955.md` (4920, 4935, 4950), `CIV-4000-4070.md` (4040, 4045), `CIV-5900-5920.md` (5910) | On the shelf |
| Notice requirements | `jason.api.notice_requirements("discipline-hearing")` (10 days before; personal or individual delivery; five elements) and `("discipline-decision")` (14 days after the action) | Built |
| Notice elements check | `notice_elements` `discipline-hearing`: date, time, place; nature of the violation; right to attend and address; executive session; cure | Built |
| Penalty schedule in force | A `Community` method (empty default) returning each schedule version with its adoption day and the day and means of its distribution; proof from the `penalty-schedule` notice's ledger key | **To add.** The catalog row exists (`notice_catalog`, annual); no store of schedule versions and no check against a violation day |
| Cure, executive-session request, reply | Run-record fields (below) | **To add**; no store today |
| Open-session note | `decisions.general_notes`, `meeting_room` open record: the matter by its 4935 subject only | Built |

**Run record, proposed** (`data/board/hearings.json`, opaque `run` id, no address in any key or path): `unit` (a unit id, never an address), `matter` (the board's words, P3), `violationOn`, `penalty` (`kind`, `amountCents`, `scheduleVersion`), `dates` (`hearingOn`, `noticeBy`, `noticeOn` plus `by` and `means`), `execRequest` (`on`, `how`, `recordedBy`, or none), `cure` (`state` none, cured, or commitment; `on`; `evidenceRef`; `recordedBy`), `reply` (`receivedOn`, `docRef`), `agendaItem`, `decisionId`, `decisionNotice` (`dueBy`, `deliveredOn`, `by`, `means`), `state`, `events[]`. Amounts are integer cents.

## The law, recited

The words are as stored in `data/authorities` (jason's consolidated text, not an official restatement; the recorded or published copy governs). Each block is a `Recitation`; every reading is under a `ReadingLabel`.

- **CIV 5855(a):** "When the board is to meet to consider or impose discipline upon a member, or to impose a monetary charge as a means of reimbursing the association for costs incurred by the association in the repair of damage to the common area and facilities caused by a member or the member's guest or tenant, the board shall notify the member in writing, by either personal delivery or individual delivery pursuant to Section 4040, at least 10 days prior to the meeting." (Verified in the stored text.)
- **CIV 5855(b):** "The notification shall contain, at a minimum, the date, time, and place of the meeting, the nature of the alleged violation for which a member may be disciplined or the nature of the damage to the common area and facilities for which a monetary charge may be imposed, and a statement that the member has a right to attend and may address the board at the meeting. The board shall meet in executive session if requested by the member."
- **CIV 5855(c):** "A member shall have the opportunity to cure the violation prior to the meeting. The board shall not impose discipline in either of the following circumstances: (1) The member cures the violation prior to the meeting. (2) If curing the violation would take longer than the time between the notice provided pursuant to subdivision (a) and the meeting, the member provides financial commitment to cure the violation."
- **CIV 5855(d), (e):** "If the board and the member are not in agreement after the meeting, a member shall have the opportunity to request internal dispute resolution pursuant to Section 5910." "If the board and the member are in agreement after the meeting, the board shall draft a written resolution."
- **CIV 5855(f), (g):** "... the board shall provide the member with a written notification of the decision, by either personal delivery or individual delivery pursuant to Section 4040, within 14 days following the action." "A disciplinary action or the imposition of a monetary charge for damage to the common area shall not be effective against a member unless the board fulfills the requirements of this section."
- **CIV 4935(b), (e):** "The board shall adjourn to, or meet solely in, executive session to discuss member discipline, if requested by the member who is the subject of the discussion. That member shall be entitled to attend the executive session." "Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership."
- **CIV 4920(b)(2):** "If a nonemergency board meeting is held solely in executive session, the association shall give notice of the time and place of the meeting at least two days prior to the meeting."
- **CIV 5850(a), (c):** "... the board shall adopt and distribute to each member, in the annual policy statement prepared pursuant to Section 5310, a schedule of the monetary penalties that may be assessed for those violations, which shall be in accordance with authorization for member discipline contained in the governing documents. Monetary penalties shall be reasonable." "A monetary penalty for a violation of the governing documents shall not exceed the lesser of the following: (1) The monetary penalty stated in the schedule of monetary penalties or supplement that is in effect at the time of the violation. (2) One hundred dollars ($100) per violation."
- **CIV 5850(d)(1), (2), (e):** a penalty above $100 only "if the violation may result in an adverse health or safety impact on the common area or another association member's property"; "Before imposing a penalty on a violation pursuant to this subdivision, the board shall make a written finding specifying the adverse health or safety impact in a board meeting open to the members." "A late charge or interest shall not be charged to a member for a monetary penalty."
- **CIV 5865:** "Nothing in Section 5850 or 5855 shall be construed to create, expand, or reduce the authority of the board to impose monetary penalties on a member for a violation of the governing documents."

**Readings, labeled (jason's, not the statute's):** (1) jason computes "notice by" as the hearing day minus 10 days; the statute does not say how the days are counted, and the board or counsel may count otherwise. (2) The member's request for executive session is read as arriving at any time before the meeting; the statute sets no day for it. (3) Whether a cure is complete is the board's finding on the member's evidence; jason records the statement and decides nothing. (4) 5850(d)(2) puts the written finding "in a board meeting open to the members" while 5855(b) and 4935(b) put the discussion in executive session on request; jason's reading is two items, the finding made in open session and the discussion in executive session. This is a question for counsel before it is relied on. (5) Whether a charge to reimburse damage to the common area is a "monetary penalty" under 5850 is not decided here; jason runs the check for any money amount and says so.

**Not on the shelf:** Corporations Code 7341, which `SUSPENSION_NOTICE_DAYS = 15` and `--suspension` cite (it appears only as a cross-reference in CORP 7151(d)). It is not recited and its 15-day period is not verified: the run offers no suspension path until the section is on the shelf. The governing documents' discipline clauses are read through the document citations, not recited from memory. Also not stated in the statute: how a mailed notice is counted as delivered (the code cites CIV 4050(b); not re-read for this page).

## Layout

Run page: a header, a clock strip, then eight bands in order, so the page reads like the statute. Each band shows what is on record, who recorded it, and what is missing.

```
+------------------------------------------------------------------------------------------+
| Work > Hearing H-7 (Unit U-14)           [Private view: on, "board prep"]       Open · Nov 6 |
| jason://hearing/H-7 [copy] · CLI: jason hearing H-7 [copy]       [Note] [Print history]    |
+------------------------------------------------------------------------------------------+
| CLOCKS  Notice by Nov 7 [LEGAL] CIV 5855(a)  Hearing Nov 17  Decision notice by Dec 1 [LEGAL]  |
+------------------------------------------------------------------------------------------+
| 1 THE MATTER   in the board's words (P3) · violation day Oct 2 · alleged: A. Owner (P3)      |
| 2 THE PENALTY CHECK   schedule v2099-1 (distributed Jan 15, annual statement) · cap $100     |
|   [Recitation 5850(c)] [ReadingLabel] Proposed $50: within the schedule and the cap.        |
| 3 THE NOTICE   elements 5 of 5 · delivered Nov 5, personal delivery, by the manager (stmt)   |
|   [Recitation 5855(a), (b)] · Gmail draft saved · [Preview the notice]                       |
| 4 THE MEMBER   request for executive session: received Nov 6 (recorded by the secretary)     |
|   cure: none on record · financial commitment: none · reply: none received                  |
| 5 THE HEARING   agenda item 4 (executive session, subject: member discipline) · Nov 17     |
| 6 THE DECISION   board decides, secretary records · outcome · link to decision d-2099-11-17  |
| 7 THE DECISION NOTICE   due Dec 1 · preview · delivered: not recorded · [Record delivery]    |
| 8 EFFECTIVE ONLY IF   5855(g): notice 10 days [met] · cure window [met] · exec session [met]  |
|   · decision notice 14 days [open]    jason states; the board and counsel decide             |
+------------------------------------------------------------------------------------------+
| Caveats (verbatim): jason records and computes; the board decides; the notice is delivered  |
| by a person. Confidential: member discipline (CIV 4935).                                     |
+------------------------------------------------------------------------------------------+
```

The list (`#/hearings`) shows, per run, only the opaque label ("H-7"), the state word, the hearing date, and the next clock. The unit and the matter open only in the private view.

## Components

Reused: `ScreenHeader`, `Clock` (`HearingClock`), `Card`, `Recitation`, `ReadingLabel`, `Findings`, `Pill`, `DueDate`, `DocList`, `Confirm`, `Command`, `Caveats`, `RemoteView`, `DataTable`, `DecisionStep` (links to `#/room` and `#/decisions`; no approve control), the spine's step rail. Built: `NoticePreview` (kept, moved into band 7). To add: `CureRecord` (state, evidence reference, who), `ExecRequest` (when and how the member asked; shows what the request obliges, recited), `PenaltyCheck` (the schedule version, the cap, the 5850(d) finding when needed; every line labeled as a check, never a verdict), and `RequirementsList` (the 5855(g) band: each requirement, met or open or not on record, with its basis).

## Actions

| Control | Does | Approval? | CLI / state |
|---|---|---|---|
| Start a run | Picks the unit by id, the matter in the board's words, the violation day, the hearing date; computes the dates; mints a random run id | No: a signed record | `jason hearing --address "123 Main St" --violation TEXT`: built; the run id: to add |
| Run the penalty check | Reads the schedule in force on the violation day and compares the amount; read only; with no schedule on file it says "no schedule on file: jason cannot state a penalty" | No | To add |
| Write the notice Doc, save the Gmail draft | The template, then the draft for a person to send | Draft: built (`gmail-drafts`, case `hearing`); the Doc kind `google.doc`: not built | `jason hearing --doc --yes` (to add as a kind); `jason draft --hearing ADDRESS` (built) |
| Record the delivery day | The person's statement: day, means (personal or individual delivery), who delivered; sets `noticeOn` | No: a signed record behind `Confirm` | `jason hearing ... --notice-on DATE` (built, CLI only); web writer: to add |
| Record the member's request for executive session | Day, how received, who recorded; makes the agenda item executive | No: a signed record | To add |
| Record a cure or a financial commitment | State, day, evidence reference, who; a cure recorded closes the run "no discipline" with the record, after a second person confirms | No: a signed record, second person confirms | To add |
| File the member's reply | Day received and the document reference; the body stays in the private view | No | To add |
| Link the agenda item | Attaches the run to an item of a `board-meeting` run | No | To add |
| Record the board's decision | Opens `#/decisions`; findings and vote in the board's words | The board decides; the secretary records | Built, on the hearing row; moves with Decisions 1 |
| Record the decision notice delivered | Day, means, who; against the 14-day clock | No: a signed record | To add |
| Request internal dispute resolution | Names CIV 5910; the member's request opens a request run, not this family | No | Not this family |

There is no control to impose, fine, suspend, send, or mail. A mailing is a person's `jason mailroom --send --yes`. The words "approve", "impose", and "send" are on no button.

## States

- **No hearings:** "No hearings saved; plan one with `jason hearing`" (the loader's note).
- **Notice not delivered by notice-by:** "The notice was due by DATE and no delivery is recorded: the hearing must move (CIV 5855(a))." Band 5 is blocked. Whether a resent notice cures a late one is held for the board or counsel (an open question in [notices.md](notices.md)).
- **Cure or commitment recorded:** "The board shall not impose discipline" recited; the run closes `no discipline`; bands 5 to 7 are skipped with the reason.
- **No penalty schedule on file:** band 2 reads "No schedule of monetary penalties on file; jason states no penalty." Over the cap with no recorded open-session finding: "Not within CIV 5850(c); (d) asks a written finding in an open meeting" (a check, not a verdict).
- **Decision notice past `dueBy`:** LEGAL, recited, step overdue; the run stays visible.
- **Stores disagree:** "changed since": the run and the decision store differ, shown as a difference, never reconciled.
- **Private view off:** the unit, the matter, the member, the reply, and the findings read "In the private view".

## Privacy

- P3, private view only, opened for a stated reason and logged. Directors and officers have the same access to information; a director sees what an officer sees at the same level.
- The open record names the matter generally: the 4935 subject in the statute's words ("member discipline"), never the unit, the member, the violation, or the executive item's title. The minutes of the next open meeting note it generally (4935(e)). This includes the minutes draft, the agenda, the Dock, and any export outside the private view.
- A run's id and URL are random; no key, path, or filename carries an address. The built view's address column and the `hearings.json` path `zoom/hearings/*` (P3 by path rule) are the cases to fix.
- The owner view has no hearings loader. A member sees only their own notice, as delivered to them.
- [work.md](work.md) shows a sample hearing row with an address; this spec supersedes it.

## Acceptance criteria

1. The page shows the five 5855 recitations and the 4935(b) recitation as stored, before any reading; each reading carries a `ReadingLabel`.
2. Notice-by is the hearing day minus 10 days, labeled as jason's count; a delivery after it blocks the hearing step with "the hearing must move".
3. The notice band lists the five elements from `notice_elements` and shows a missing one by name.
4. A recorded request for executive session makes the item executive; the open record, agenda, and minutes draft name only "member discipline".
5. A recorded cure, or financial commitment, closes the run `no discipline` and recites 5855(c); a second person confirms it.
6. The penalty check names the schedule version and its distribution record; with none, it states no penalty. An amount over $100 with no recorded open-session finding shows "not within 5850(c)".
7. The decision is recorded once; the run holds its id; findings are never stored in two places.
8. The decision-notice due day is the decision day plus 14 days, goes overdue, and is recited.
9. The 5855(g) band lists each requirement as met, open, or not on record, and never says the discipline is effective or void.
10. No control sends, mails, imposes, or fines; the page shows commands for those.
11. With the private view off, no address, name, unit, matter, or finding is in the HTML or the URL.
12. A treasurer, a director, and an officer see the same fields.
13. Corporations Code 7341 appears only as "not on the shelf".
14. Statute words are exactly the stored words (`jason verify-quotes` passes).

## Decisions for the user

1. **One decision store.** Recommended: `board/decisions.json` holds the vote and the findings; the run record holds `decisionId` and nothing of the decision. Alternative: one file for both. Either removes the `decision` block from `zoom/hearings.json`.
2. **The run id.** [board-governance.md](../../workflows/board-governance.md#5-the-screens) says a digest of the key; a digest of day and address can be recovered by trying the association's few addresses. Recommended: a random id.
3. **Where the schedule lives.** A `Community` method returning versions with distribution dates, or a register the board keeps. Without it, the penalty check can only say "no schedule on file".
4. **The open-session finding (5850(d)(2)).** Two items (finding in open session, discussion in executive session), or counsel's reading first.
5. **Suspension.** Keep `--suspension` hidden until Corporations Code 7341 is added to the shelf, or retire the constant.
6. **Who confirms a cure.** The secretary records and the president confirms, or the board decides at the hearing.
7. **Late notice and resend.** Whether a resent notice cures a late one stays a board or counsel question.
8. **The SOP `hearing`** and a lesson on the late-notice path (gap in section 8) are written when the run is built.
