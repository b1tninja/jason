# Board governance: the board's cycles as durable workflows

Status: **design**. A family page of [../workflows-design.md](../workflows-design.md); it follows that page's template (§5) and uses its model (definition, run, the seven step kinds, the event log). Nothing here is built as a workflow engine. Every step names what exists today (verified against the repo on 2026-10-11, section 7) and what is to add.

The page is general. The association is "the association"; the people, addresses, and dates in the samples are made up ("A. Owner", "123 Main St", 2099 dates). The statutes are recited from `data/authorities` (`CIV-4900-4955.md`, `CIV-4340-4370.md`, `CIV-5100-5145.md`, `CIV-5850-5875.md`, `CIV-4205-4235.md`); a number that is not the law's or the documents' is labeled **proposed policy**; where the law is silent a step holds a question for the board.

## 0. How the seven relate

```text
law-review ──leads──► conflicts ──► board item ─┐
    │                                           ▼
    └──stale copies──► owners-manual ◄── rule-change ──► (member vote to reverse, §2.3 election)
                            ▲                │ decision step
duty-schedule ──────────────┼────────────────┤
  (every duty owned; notices, minutes,       ▼
   hearing, election clocks live here)   board-meeting  ◄── hearing (executive item)
                                              ▲              election (count meeting, acclamation vote)
                                              └── hosts every board `decision` step
```

- **A meeting hosts a decision.** `board-meeting` is the only place a board vote is taken. A `decision` step in another run (the adoption of a rule change, the discipline decision, seating by acclamation, the approval of minutes) is *linked* to an agenda item of a `board-meeting` run and is done when the vote is on record. The other run never takes the vote (section 2.0).
- **A rule change feeds the manual.** A carried `rule-change` opens the carry-out step that reopens `owners-manual` (the Rules document and the manual regenerate from the version in force). The manual's own extraction of the rules is itself put to the board as a rule change (SOP `owners-manual`, last two steps).
- **A rule change feeds an election, and an election feeds a rule change.** Election operating rules are operating rules (CIV 5105(a)) and are "not ... amended less than 90 days prior to an election" (5105(h)(4)(B)(iii)): `election` checks the rule-change runs. A member vote to reverse a rule change (CIV 4365) is an `election`-family subject.
- **The law review feeds conflicts and rule changes.** Its leads become `Conflict` rows and board items; a conflict the board resolves by amending an operating rule becomes a `rule-change` run; its stale-copy findings become `owners-manual` work.
- **The duty schedule owns the clocks.** Each notice, minutes, hearing-decision, and election clock the other six start is an occurrence of an assignment; recording it done is a step of the run that owns it and is mirrored to the schedule (`record_completion`).
- **A hearing is a meeting item.** Its notice clock is its own (5855(a)); the hearing itself is an executive-session agenda item (4935) of a `board-meeting` run.

## 1. The tasks

| Key | Task | Trigger | Subject (run id) | SOP and main docs |
|---|---|---|---|---|
| `board-meeting` | The board packet and meeting: notice, agenda, packet, the meeting, minutes, their approval | Each board meeting; notice day and packet day ahead (a week ahead and the day before, proposed policy) | a meeting (ISO date) | `board-packet`, `notice-delivery`; [board-agenda](../board-agenda.md), [meetings](../meetings.md), [record-stages](../record-stages.md) |
| `rule-change` | Adopt, amend, or repeal an operating rule | The board proposes a change; a law-review conflict; an owners-manual extraction | a `RuleChange` key | `rule-change`, `rule-history`; [rule-records](../rule-records.md), [handoff-rule-records](../console/handoff-rule-records.md) |
| `election` | An election of directors, a recall, or a member vote (an assessment, an amendment, a reversal of a rule change) | A term ends ("term ended; election due" on People), the four-year rule (5100(a)(2)), a petition, a board decision | an election (kind and year) | `election`; [notices](../notices.md), [candidate nomination](../form-templates/candidate-nomination.md) |
| `hearing` | A hearing on a member's discipline or a damage charge | The board proposes to consider discipline | a hearing (opaque id; section 5) | no SOP (gap, section 8); `jason hearing`; CIV 5855 |
| `law-review` | The year's changes in the law against the written provisions | Each January once the year's laws are operative; again when a law takes effect mid-year (SOP: proposed policy) | a year | `law-review`; [law-history](../law-history.md), [law-readings](../law-readings.md) |
| `duty-schedule` (with `document-duties`) | Every duty owned, every clock set, each occurrence done | Each month before the board meeting; when a document, amendment, or law adds duties | a month (YYYY-MM), or a document key | `duty-schedule`, `document-duties`; [schedule](../schedule.md), [document-duties](../document-duties.md) |
| `owners-manual` | Keep the owner's manual and the Rules document generated and citable | A rule changes, the manual's Doc changes, or a copied document is amended | a revision of the manual | `owners-manual`, `rule-history`; [owners-manual](../owners-manual.md) |

## 2. The definitions

Columns: **Kind** is one of the seven; **Role** is who acts (the server enforces it); **Needs** are step ids and facts; **Produces / evidence** is the link kind and what shows it done; **Clock** gives the basis (`law`, `documents`, `proposed policy`, `person`). "New kind" means an approvals kind that does not exist (section 7). A `plan` is applied by a person; no step sends, files, mails, or adopts.

### 2.0 Board decisions: the `decision` step, and how a vote is recorded

A `decision` step is done when a decision with a final outcome is on record in `data/board/decisions.json` (`jason.tasks.decisions`, `/api/decisions`). It is **recorded by the secretary** (the Decisions screen is for officers and administrators), never by the run's owner and never by a click on the run page. The run page shows the motion's words, mover, second, each director's vote by name, recusals, outcome, and a link to the decision; it has no approve, vote, or adopt control.

- **How a vote is taken and kept.** A motion needs two different directors (mover, second) and a quorum of those present, counted by the profile's `BoardRule` (the bylaws' provision recited, or counsel's reading labeled, or "not on file; ask counsel"). The vote is a **roll call by name** (`Vote`: aye, no, abstain, absent), a recusal is the director's disclosure entered by the secretary (never inferred), the outcome is an `Outcome` (`approved`, `denied`, `tabled`, `continued`, `referred`). The minutes draft quotes the decision; the next meeting's approval of the minutes states it in words; `jason record-stages` reads "approved: stated" or "listed, not stated".
- **The law on the roll call.** CIV 4926(a)(3): "Any vote of the directors shall be conducted by a roll call vote." That is a condition of a meeting conducted entirely by teleconference; for other meetings the roll call by name is jason's practice and the board's, not a statutory requirement stated in the text read for this page.
- **Step states from an outcome.** `approved` or `denied`: the step is `done` (a `decided` event). `tabled` or `continued`: the step goes to `waiting` until the named later meeting (`continued` sets the board item's meeting). `referred`: `waiting` on the committee or person the motion named. A motion withdrawn before the vote leaves the step `ready`. A decision made in executive session (`session = executive session`, with its 4935 subject) is read in the private view only; elsewhere the step shows "decided in executive session: <4935 subject in the statute's words>".

| Board decision | Run and step | Recorded by | Where the law or documents put it |
|---|---|---|---|
| Adopt, amend, repeal an operating rule | `rule-change` r13 | secretary | CIV 4360(b): "A decision on a proposed rule change shall be made at a board meeting, after consideration of any comments made by association members." |
| Determine an emergency rule change | `rule-change` r1 branch | secretary | CIV 4360(d): "If the board determines that an immediate rule change is required ..." |
| Approve the minutes | `board-meeting` m21 (in the next meeting's m16) | secretary | the board's act at a meeting; 4950(a) governs only availability |
| Seat candidates by acclamation | `election` e9 | secretary | CIV 5103(e): "The association board votes to consider the qualified candidates elected by acclamation at a meeting ... for which the agenda item reflects the name of each qualified candidate" |
| Make the acclamation option available (a standing fact) | `election` e2 | secretary | the board's decision, written down once (AGENTS.md, "Where the law is silent") |
| Appoint the inspector of elections | `election` e4 | secretary | the election rules' method (5105(a)(5)); board appoints only if the rules say so |
| Discipline a member, or impose a damage charge | `hearing` h12 | secretary | CIV 5855(a) to (g) |
| Adopt, change, or decline duty assignments | `duty-schedule` d8 | secretary | `Assignment.adoption` (schedule.md) |
| Accept a vendor's proposal for an overdue inspection | `duty-schedule` d5 | secretary | the board's decision (fire-protection.md) |
| Act on a conflict (amend, ask counsel, leave) | `law-review` l12 | secretary | CIV 4205(a): "the law shall prevail"; jason notes, the board, counsel, or an amendment resolves |
| Correct former cross-references by resolution | `law-review` l13 (optional) | secretary | CIV 4235(a): "the board may amend the governing documents, solely to correct the cross-reference, by adopting a board resolution that shows the correction." |
| Whether the manual's extraction needs the 4360 notice | `owners-manual` o9 | secretary | two readings; the lawful course under either is the notice (owners-manual.md) |
| Call an emergency meeting | `board-meeting` m3 branch (a `person` step, not a vote) | the president, or any two directors other than the president | CIV 4923 |

### 2.1 `board-meeting` (SOP `board-packet`, journeys c)

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| m1 | Rebuild the meeting catalog | job | jason (cadences `payhoa-notices`, `zoom` already scheduled) | run active | catalog rows; job finished | `jason meetings --sync` | none | on open; skip: none |
| m2 | Read the clocks forward | check | jason | m1 | `Watch` rows: notice by, minutes owed from the last meeting | `jason schedule-evidence --watch` | notice 4 days (law, 4920(a)) or the documents' longer period (4920(b)(3)); last minutes 30 days (law, 4950(a)) | on open, daily; not skippable |
| m3 | Say the kind and format of the meeting | branch | secretary | m2 | facts `board_meeting`, `meeting_format`; the catalog rows that apply and those undetermined | `jason notices --catalog --fact board_meeting=ordinary --fact meeting_format=in_person` | executive-only: 2 days (law, 4920(b)(2)); emergency: none (4920(b)(1), 4923) | once; emergency path skips m9 to m13 with the 4923 reason recorded |
| m4 | Bring the action items up to date | person | manager | m3 | board items "on agenda" for the date; `board-items` | `jason board --set ITEM --status 'on agenda' --meeting DATE`; `#/actions` | none | per item; items from other runs arrive by link |
| m5 | Refresh the reports the items name | job | manager | m4 | live reports, none stale or failed | `jason report --all` | the day before (proposed policy) | per report |
| m6 | Last month's Treasurer's Report run in PayHOA | person | treasurer | m5 | report-run catalog entry for the month | PayHOA Report Packets; `jason report treasurers-report period=previous-month` | the day before (proposed policy) | skip: reason if none is due |
| m7 | Build the packet | job | manager | m4, m5, m6 | `packet-DATE.md`; executive items by 4935 subject only | `jason board --packet` | none | re-run on a changed item |
| m8 | Private packet Doc; members' copy | plan | manager; officer approves the copy | m7 | Doc in the private folder; members' copy as a letter in the letters store, approver per `Community.document_approvers` | `jason board --packet --doc --yes` (new kind `google.doc`); `jason board --packet --audience members --by NAME` (letters store, built) | none | members' copy skipped if the profile names no approver |
| m9 | Draft the agenda | plan | secretary | m3, m4 | agenda Markdown and Doc; the format line names the meeting's format | `#/agenda` (`AgendaWizard`); `jason board --agenda DOC_ID --doc --yes` (new kind `google.doc`) | content: "Notice of a board meeting shall contain the agenda for the meeting." (law, 4920(d)) | once; revised until m12 |
| m10 | Draw and check the notice | job | secretary | m9 | `notice-DATE.md`, `.html`, `.refs.json` (statutes recited from disk) | `jason board --notice --date DATE`; `jason notice-check FILE --requirement board-meeting` | last day = m2's notice-by | once |
| m11 | Save the notice as a Gmail draft | plan | secretary | m10 | draft with no recipient until chosen | approvals kind `gmail-drafts`, case `meeting-notice` (built) | notice-by | once |
| m12 | Post and send; record the posting | person | secretary | m11 | posting record with where and when | `jason notices board-meeting-DATE --mark-general --posted "WHERE, DATE" --by NAME`; or `jason schedule --done KEY DUE --by NAME --evidence TEXT` | by notice-by (law, 4920(a)); delivery "by general delivery pursuant to Section 4045" (4920(c)) | once; skip: none |
| m13 | Read delivery until nothing is owed | wait | jason | m12 | ledger strength: delivered, or sent with follow-ups listed | `jason notices board-meeting-DATE --sync` | until the meeting | repeats on `reopened` |
| m14 | Share the packet with the directors | person | secretary | m8 | share event (Drive, outside the console) | Drive | before the meeting (proposed policy) | once |
| m15 | Hold the meeting | person | president (chair), secretary | m13 or the emergency path | room record `meetings/room-DATE.json` (open); executive record apart | `#/room` | wait until the date | once |
| m16 | Each motion decided | decision | board; secretary records | m15 | decision ids; roll call by name | `#/room`, `#/decisions` | per section 2.0 | per agenda item |
| m17 | Executive session noted generally | check | jason | m15 | open record holds only the 4935 subject and the times | `jason board --minutes DATE` reads the open record | "Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership." (law, 4935(e)) | skipped if none was held |
| m18 | Bring in the Zoom record; draft the minutes | job | secretary | m15 | `minutes-draft-DATE.md`, marked DRAFT | `jason meetings --sync`; `jason board --minutes DATE` (preflight, GPU lock) | start soon: 30 days (m20) | once |
| m19 | Read jason's checks | check | jason | m18 | quorum counted, motions without a quorum, confidential-subject lines, blanks | `jason board --minutes DATE --recheck`; `jason minutes-privacy` | none | until the count reads clean |
| m20 | Fill the blanks; make the minutes available; record it | person | secretary | m19 | filled copy (`minutes-DATE.md`); availability record with evidence | `#/minutes-review`; `jason schedule --done KEY DUE --by NAME --evidence TEXT` | "shall be available to members within 30 days of the meeting." (law, 4950(a)) | once; skipped for a meeting held solely in executive session |
| m21 | The board approves the minutes | decision | board at the next meeting | m20 | decision on that meeting's approval item; stage "approved: stated" | `jason record-stages --meeting DATE` | the next meeting | "listed, not stated" keeps it `waiting` |
| m22 | Close the run | check | jason | m1 to m21 | run `done` | none | none | a late-found fact reopens it |

**m12 and m20 are read-and-link (decided 2026-10-11).** The posting and the minutes' availability are recorded on `#/meetings`; each step reads done when that record appears, and the run offers no "Mark done" for them.

### 2.2 `rule-change` (SOP `rule-change`, then `owners-manual`; docs/rule-records.md)

The subject is a `RuleChange` row in the profile (`Community.rule_changes()`), or a proposal built from the manual (`--from-manual`). The rule-records proposal store and event log are phases 2 and 3 of docs/rule-records.md and are not built; until they are, the run log is the record of who drafted, checked, and acknowledged.

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| r0 | Read the rule as a record | check | jason | run active | the version in force on the day; changed-with-no-adoption findings | `jason revisions KEY --fetch --versions`; `jason rule-records --show ID --as-of DAY`; `#/documents/rules` records band | none | skip only if the rule is new |
| r1 | Say the change's facts; read the 4355 reach | branch | any roster person drafts; a reading labeled the board's | r0 | facts `rule_scope`, `rule_change`; notice rows that apply, do not, are undetermined | `jason notices --catalog --fact rule_scope=listed_subject --fact rule_change=noticed` | none | paths: `listed`, `not_reached` (4355(b): a one-off needs no rule), `emergency` (4360(d)); where two readings remain: "the board asks counsel" on the item |
| r2 | Authority and conflicts | check | jason | r0 | grant standing; `Conflict` rows for the subject; a duplicate of the declaration | `jason rules --subjects`; `jason conflicts` | none | acknowledgment of each flag is a `person` event; a flag does not block (decision 5 of rule-records) |
| r3 | Draft the proposed words, reason, purpose and effect | person | any roster person (drafter) | r1 | `RuleChange` row: sections, `[bracket]` choices left to the board | profile row in `rule_changes.py`; `#/rules` (read) | none | jason never fills a bracket |
| r4 | Compute the timeline | job | jason | r3 | notice date, decision meeting, comment deadline, notice of adoption, reversal window | `jason rule-change KEY --notice-date DATE` | decision meeting = first meeting at least 28 days after the notice (law, 4360(a)); comment deadline default the day before (proposed policy) | recomputed on a changed date |
| r5 | Put it before the board | person | manager or secretary | r3, r4 | board item with text, clock, readings | `jason board --set ITEM ...`; `#/actions` | none | one item |
| r6 | Check the notice text | check | jason | r3 | required elements present: text first, then purpose and effect | `jason notice-check FILE --requirement rule-change-proposed --event rule_scope=listed_subject` | none | skipped on the emergency path |
| r7 | Save the member notice as a Gmail draft | plan | secretary | r6 | draft with no recipients; text kept in `data/notices/KEY/` | `jason rule-change KEY --draft-email --yes --by NAME` (**new case** `rule-change` in kind `gmail-drafts`) | notice at least 28 days before the decision | skipped on emergency or `not_reached` |
| r8 | Address, send, and post the notice | person | secretary | r7 | notice sent; posting recorded | PayHOA broadcast, Gmail; `jason notices rule-change-proposed-KEY --mark-general --posted ... --by NAME` | as r7 | once |
| r9 | Read delivery | wait | jason | r8 | ledger "delivered" or "sent" in time (a file never meets the clock) | `jason notices rule-change-proposed-KEY --sync` | "at least 28 days before making the rule change" (law, 4360(a)) | repeats until nothing is owed |
| r10 | Collect the members' comments | person | secretary | r8 | comments received (file or note), dated | none yet (gap) | the board considers them before deciding (4360(b)) | one entry per comment |
| r11 | Agenda item for the decision meeting | wait | jason | r5, r9 | link to the `board-meeting` run's agenda item | `#/agenda` | agenda notice 4 days (law, 4920(a)) | blocks if the meeting is under 28 days out |
| r12 | Wait for the meeting | wait | none | r11 | the meeting date passed | none | the decision meeting | `continued` returns here |
| r13 | The board decides | decision | board; secretary records | r9, r10, r12 | decision id; motion's words; roll call | `#/room`, `#/decisions` | at a meeting after notice and comments (law, 4360(a), (b)) | per section 2.0 |
| r14 | Record the adoption and read the stages | check, then person | secretary | r13 | adoption event with minutes reference; "adopted" stage | `jason record-stages --change KEY`; `jason rule-records --record-adoption` (phase 3, not built) | none | the adopted words are entered from the minutes, not typed |
| r15 | Notice the adopted change | plan | secretary | r14 | adoption notice draft | `jason rule-change KEY` section (c); **new case** in `gmail-drafts` | "not more than 15 days after making the rule change" (law, 4360(c)) | emergency: text, purpose and effect, expiry date |
| r16 | Read delivery of the adoption notice | wait | jason | r15 | ledger entry | `jason notices rule-change-adopted-KEY --sync` | as r15 | repeats |
| r17 | Hold the reversal window | wait | none | r16 | window end date | `jason record-stages --change KEY` | "not more than 30 days after the association gives general notice of the rule change" (law, 4365(b)) | not applicable to an emergency change (4365(h)) |
| r18 | A reversal request arrives | branch | secretary | r17 | request received, or none by the window's end | none (gap) | request from members owning 5 percent of the separate interests (4365(a)) | if yes: open an `election` run (member vote) |
| r19 | Carry out the effects | person | manager | r14 | links to `owners-manual`, the next policy statement, citations, new-member packets | `jason manual --render`; `jason document-template` | none | each effect its own event; opens an `owners-manual` run |
| r20 | Record the lesson | person | manager | r19 | lesson row or "none" | `jason lessons --area governing` | none | skippable with a reason |

### 2.3 `election` (SOP `election`; CIV 5100 to 5145; candidate nomination form)

One definition for directors, a recall, and a member vote; the kind is a branch. No election store exists. The inspector of elections is an independent third party (5110(a), (b)) who acts outside the console; the secretary or manager records what the inspector reports, with the report as evidence.

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| e1 | Say the kind of election | branch | secretary | run draft | fact `election` (directors, recall, assessment, amendment, exclusive_use, other); notice rows that apply | `jason notices --catalog --fact election=directors` | none | `member vote`: skips e7 to e9 |
| e2 | Answer the standing facts | decision (acclamation); person (the rest) | secretary records; roster person answers with the record | e1 | answers with the record that states each: electronic ballots and opt-out in the election rules; quorum in the documents; acclamation availability | `jason applies --questions`; `jason intake --answer ID TEXT --by NAME` | none | "undetermined" is never "not required" |
| e3 | Election rules in force | check | jason | e2 | the rules' record; any rule-change run that amends them; "not ... amended less than 90 days prior to an election" | `jason rule-records`; `jason record-stages --rules` | 90 days (law, 5105(h)(4)(B)(iii)) | blocks e5 if a change falls inside the window |
| e4 | Select the inspector or inspectors | decision or person | per the election rules (board, members, other) | e2 | one or three independent third parties; none a director, candidate, or contractor | none (gap) | "The number of inspectors of elections shall be one or three." (law, 5110(a)) | if the rules are silent: a question for the board |
| e5 | Set the dates | person | secretary | e3, e4 | nomination deadline, ballots out, voting deadline, count meeting, opt-out deadline, each with the notice day it forces | catalog anchors (`NOMINATION_DEADLINE`, `BALLOTS_DISTRIBUTED`, `VOTING_DEADLINE`, `OPT_OUT_DEADLINE`) | room for one correction (proposed policy) | a passed notice day moves the election; no clock is shortened |
| e6 | Candidate list and voter list | person | inspector; secretary records | e5 | both lists retained; members verify their entries | none (gap) | verify "at least 30 days before the ballots are distributed"; corrections in "two business days" (law, 5105(a)(7)) | per correction |
| e7 | Notice of the nomination procedure | plan | secretary | e5 | draft per notice; text checked | `jason notice-check FILE --requirement nomination-procedure --event election=directors`; approvals `gmail-drafts` (new case) and PayHOA broadcast (new kinds) | "at least 30 days before any deadline for submitting a nomination" (law, 5115(a)) | directors and recall only |
| e8 | Acclamation notices (if available) | plan | secretary | e2, e7 | initial notice; reminder with candidates' names | `jason notices acclamation-initial-DATE`, `acclamation-reminder-DATE` | initial "at least 90 days before the deadline for submitting nominations"; reminder "between 7 and 30 days before" (law, 5103(b)(1), (2)) | skipped when e2 says not available |
| e9 | Receive and acknowledge nominations | person | secretary | e7 | each nomination acknowledged; each nominee qualified or disqualified with the basis and appeal route | candidate-nomination form (handler `response-clock`, built) | "within seven business days of receiving a nomination" (law, 5103(c)) | per nomination; disqualification only on the grounds 5105(b) to (e) allow |
| e10 | At the nomination deadline: acclaim or ballot | branch, then decision | secretary; board for the vote | e9 | qualified candidates counted against vacancies; the vote with each candidate named on the agenda item | `#/agenda`, `#/decisions` | acclamation is "may, but is not required" (5103) | no: go to e11 |
| e11 | Notice before ballots go out | plan | secretary | e5, e6, e9 | notice with return place and time, electronic instructions, count meeting, candidate list, quorum statement | `jason notices pre-ballot-notice-DATE`; `jason notice-check` | "at least 30 days before the ballots are distributed" (law, 5115(b)) | directors and recall only |
| e12 | Ballots, envelopes, and the rules delivered | plan | inspector delivers; manager plans | e11 | ballots with two preaddressed envelopes and the election rules; electronic and opt-out notices | `jason mailroom` (letters cannot be recalled); `payhoa.mailroom.send` (proposed, two-person) | "not less than 30 days prior to the deadline for voting" (law, 5115(c)); electronic notice 30 days before the election (5105(i)(3)(A)); opt-out notice 30 days before its deadline (5105(i)(4)) | one per channel |
| e13 | Voting period | wait | none | e12 | voting deadline passed | none | the voting deadline | none |
| e14 | Count in public | person | inspector; secretary hosts the meeting | e13 | tabulation at a properly noticed open meeting; quorum determined | `#/agenda`, `#/room` | counting is at "a properly noticed open meeting of the board or members" (law, 5120(a)); not entirely by teleconference (4926(b)) | no quorum: e15 |
| e15 | Reconvene if no quorum | branch | secretary | e14 | adjourned meeting at least 20 days later; notice | `jason notices reconvened-election-meeting-DATE` | notice "No less than 15 days prior" (law, 5115(d)(3)); 20 days apart (5115(d)(2)) | skipped when a quorum was met |
| e16 | Results to the board and the members | plan, then person | inspector reports; secretary | e14 | results recorded in the next board minutes; general notice | `jason notices election-results-DATE` | "Within 15 days of the election, the board shall give general notice pursuant to Section 4045 of the tabulated results of the election." (law, 5120(b)) | once |
| e17 | Record the seats and terms | person | secretary; a second person confirms | e16 | seat holders and terms with the inspector's report as the record | `jason onboard --questions --group elections`; `jason onboard --answer ID TEXT --by NAME`; `--confirm`; `--apply` | none | closes the "term ended" flag on People |
| e18 | Custody and the challenge period | wait | inspector, then the association | e16 | election materials held by the inspector, then transferred | none (gap) | held "until the time allowed by Section 5145 for challenging the election has expired" (law, 5125); suit "within one year of the date that the inspector or inspectors of elections notifies the board and membership of the election results or the cause of action accrues, whichever is later" (5145(a)) | run `done` after transfer |

### 2.4 `hearing` (no SOP; `jason hearing`; CIV 5855)

No `Procedure` row exists for hearings; this definition is the proposed SOP `hearing` and must be added (section 8) with its lessons.

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| h1 | State the matter and the authority | person | president or manager | run draft | the alleged violation in the board's words; the discipline the documents authorize; for a monetary penalty, the schedule in effect at the time of the violation | `jason hearing --address "123 Main St" --violation TEXT`; schedule check (gap) | "A monetary penalty ... shall not exceed the lesser of ... (1) The monetary penalty stated in the schedule ... in effect at the time of the violation. (2) One hundred dollars ($100) per violation." (law, 5850(c)); higher only on 5850(d) | per matter; a penalty over the cap needs the open-meeting written finding in 5850(d)(2) |
| h2 | Compute the dates | check | jason | h1 | notice by, executive notice by, decision by if held, problems | `jason hearing --address ... --date DATE [--notice-on DATE]` (saved in `data/zoom/hearings.json`) | notice by: "at least 10 days prior to the meeting" (law, 5855(a)); executive-only meeting notice 2 days (law, 4920(b)(2)) | `--suspension` uses a 15-day constant whose authority (Corp. Code 7341) is not on the shelf: not verified |
| h3 | Agenda item, executive session | wait | jason | h2 | link to a `board-meeting` agenda item, 4935 subject "member discipline" | `#/agenda` | executive subject (law, 4935(a)); "if requested by the member" the board "shall meet in executive session" (5855(b), 4935(b)) | the item lists by subject only |
| h4 | Write the notice | plan | manager | h2 | notice Doc from the template; elements checked: date, time, place, nature, right to attend and address, executive session, cure | `jason hearing ... --doc --yes` (new kind `google.doc`); `jason notice-check discipline-hearing` | within h2's notice-by | once |
| h5 | Schedule the Zoom meeting | plan | manager; second person | h2 | meeting id and link | `jason hearing ... --create --yes` (new kind `zoom.hearing.create`, two-person per approval-workflow.md) | the hearing date starts the notice clock | skipped for an in-person hearing |
| h6 | Save the notice email as a Gmail draft | plan | manager | h4 | draft with the Doc or its PDF | approvals kind `gmail-drafts`, case `hearing` (built) | within h2's notice-by | once |
| h7 | Deliver the notice and record the day | person | manager | h6 | delivery day; proof | personal delivery or individual delivery (4040); `jason hearing ... --notice-on DATE` | "by either personal delivery or individual delivery pursuant to Section 4040, at least 10 days prior to the meeting" (law, 5855(a)) | the day is the person's statement; not read from the ledger |
| h8 | Read delivery | check | jason | h7 | ledger strength, or "no delivery recorded: the hearing must move" | `jason hearing --list`; `jason notices discipline-hearing-DATE --sync` (not verified for a single member) | notice-by | a notice delivered late moves the hearing; whether a resend cures is a question for the board or counsel (notices.md) |
| h9 | The cure window | wait | none | h7 | a cure or a financial commitment to cure, with its record | none (gap) | "The board shall not impose discipline" if the member cures, or commits to cure when the cure takes longer than the notice period (law, 5855(c)) | cured: branch to close the run `no discipline` |
| h10 | Hold the hearing | person | president, secretary | h8, h3 | executive-session room record; the member's attendance | `#/room` (executive record, P3) | the hearing date | the member requested executive session: recorded |
| h11 | Record the board's findings | decision | board; secretary records | h10 | decision with 4935 subject; findings in the board's words on the hearing row | `#/room`, `#/decisions`; `#/hearings` (`POST /api/hearings/KEY`) | at the hearing or after | two stores today (section 8) |
| h12 | Agreement or no agreement | branch | secretary | h11 | agreement: the written resolution drafted; no agreement: IDR offered | none | "If the board and the member are in agreement after the meeting, the board shall draft a written resolution." (law, 5855(e)); IDR "pursuant to Section 5910" (5855(d)) | IDR request opens a request run (not this family) |
| h13 | Write and deliver the decision | plan, then person | manager; secretary | h11 | decision notice Doc; delivery day | `jason letter --template decision-notice --yes` (new kind `google.doc`); gmail-drafts case for a decision notice (**new case**) | "within 14 days following the action" (law, 5855(f)); `noticeDueBy` on the hearing row | once |
| h14 | Read delivery of the decision | wait | jason | h13 | delivered, with the day | `jason notices discipline-decision-DATE --sync` (not verified) | as h13 | repeats |
| h15 | Effective only if every step was met | check | jason | h8, h9, h13 | each requirement shown met or not on record | the run page | "A disciplinary action ... shall not be effective against a member unless the board fulfills the requirements of this section." (law, 5855(g)) | jason states; the board and counsel decide |
| h16 | General note in the next open minutes | check | jason | h10 | the matter noted by its 4935 subject only | `jason board --minutes DATE` | 4935(e) | closes the run |

### 2.5 `law-review` (SOP `law-review`, journeys d for the reading side)

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| l1 | Refresh the law and the change history | job | manager | run active | export date; the year's chaptered bills listed | `jason export-authorities`; `jason law-history --export` | each January, and when a law takes effect mid-year (proposed policy) | per run |
| l2 | Set aside readings whose words changed | check | jason | l1 | stale readings | `jason readings --stale` | none | each is redone or confirmed by the board or counsel (person) before use |
| l3 | Keep the earlier versions of changed sections | job | manager | l1 | versions with the range in force; shelf differs: 0 | `jason law-history --versions --since YEAR --shelf` | none | a miss is a citation to correct |
| l4 | Shelf holds the sections the documents cite | check, then person | manager | l1 | cited-not-exported list; rows added by a person | `jason reference --cites WORK`; `jason ingest SOURCE`; `citation_gaps` | none | per gap |
| l5 | Refresh the documents' outlines | job | manager | l1 | outlines current, written dates pinned | `jason outlines --fetch` | none | skip: none |
| l6 | List the leads | job | manager | l3, l5 | each change since a document was written, with the citing or subject-matching section | `jason conflicts --leads --since YEAR-01-01` | none | a document with no written date counts every change |
| l7 | Read each lead beside the statute | person | manager, with counsel where unclear | l6 | per lead: no conflict, or a `Conflict` row (part that yields, how applied meanwhile, plain or for counsel) | `jason law-history --section NNNN`; the row is a profile edit committed by a person | none | repeat per lead; "a provision yields only to the extent of any conflict" (law, 4205) |
| l8 | Check jason's own rules and pages | job | administrator | l1 | `law-sweep.md` | `jason law-history --sweep --since YEAR` | none | corrections are code changes (a spawned task) |
| l9 | Survey citations and stale records | job, then person | manager | l5 | misses by reason; stale records re-keyed | `jason cite --survey`; `jason cite --stale`; `jason cite --renumbered`; `jason cite --migrate-ids` | none | a "more than one section answers" row is picked by a person |
| l10 | Check people-task rules that retire a duty | check | manager | l1 | each retire reason still true | `jason schedule --people --all` | none | per rule |
| l11 | Find stale copies of changed sections | job, then plan | manager | l1 | copies scan, guide rebuilt; patch proposal | `jason section-refs --refresh --scan --guide`; `jason section-refs --patch` (new kind `local.section-refs.apply`) | none | patch on a person's word |
| l12 | Put each new conflict before the board | decision | board; secretary records | l7 | board item per conflict; the decision | `jason board --set ITEM ...`; `{REPORT:conflicts}` | none | amend (a `rule-change` run), ask counsel, or leave |
| l13 | Correct former cross-references | decision | board | l7 | resolution showing the correction | board resolution (4235) | none | optional |
| l14 | Lessons and procedure | person | manager | l1 to l12 | lessons added; the SOP updated | `jason lessons --area governing` | none | skippable with a reason |

### 2.6 `duty-schedule` and `document-duties` (SOPs of the same names)

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| d1 | Read what falls due, by role | check | jason | run active | occurrences with standing: done, overdue, due soon, upcoming | `jason schedule --days 45` | each month before the board meeting (proposed policy); each duty's own clock (law or documents) | per role |
| d2 | Read people's own tasks and events | job | jason (cadences `calendar`, `tasks`) | d1 | classes: covered, untracked recurring, one-off; stale tasks | `jason schedule --read-google --people` | none | a task proposed to close is closed by its owner in Google |
| d3 | Find the evidence on disk | job | jason | d1 | proposals: proposed, partial, contrary, none | `jason schedule-evidence --since DATE --all` | none | "contrary" goes to the board |
| d4 | Record each occurrence done | person | the assignment's role | d3 | `done.jsonl` line: who, when, evidence | `jason schedule --done KEY DUE --by NAME --evidence TEXT`; `jason schedule-evidence --record KEY DUE --by NAME` | the occurrence's due day | per occurrence; refused without a name and evidence |
| d5 | Overdue life-safety inspection | branch, plan, decision | manager; board accepts a proposal | d1 | proposal request draft; the vendor's report | `jason inspections`; `jason draft --proposal-request SYSTEM` (gmail-drafts case `proposal-request`, built) | the inspection's period | "accepting a proposal is the board's decision" |
| d6 | Publish the schedule | plan | manager | d1 | dated occurrences on the board calendar; open ones on each role's Tasks list | `jason schedule --tasks --calendar` then `--yes` (new kinds `google.calendar`, `google.tasks`) | none | a check-off in Google is weaker evidence; record the minutes' item too |
| d7 | Coverage | check | jason | d1 | duties with no owner; duties on a clock nothing schedules | `jason duties --documents KEY`; `jason schedule --coverage` | none | a non-empty list blocks d8 |
| d8 | The board adopts the assignments | decision | board; secretary records | d7 | each assignment adopted, changed, declined, or not applicable, with the minutes | `{REPORT:schedule}` in the packet | none | until adopted, an assignment reads "proposed, not adopted" |

`document-duties` (run when a document is outlined, amended, or replaced): **dd1** read with the phrase grammar (job, `jason duties --documents --read`); **dd2** fill unstated bearers (job, local model, GPU lock, preflight; `--fill-bearers`); **dd3** review timed untracked duties, notice duties, and owners' prohibitions, each confirmed, corrected, or rejected against the sentence (person, repeat per reading; `--review ID --status confirmed`); **dd4** say what tracks each timed duty, or propose the recurring-deadline row (person, `--tracked-by WHAT`); **dd5** after a grammar or model change, score again and record the trial (job, `python scripts/eval_duties.py`). A "may" is a power, not a duty; a conflict between a "shall" and a "may" is a finding for the conflict register.

### 2.7 `owners-manual` (SOP `owners-manual`; `rule-history` runs inside it)

| id | Step | Kind | Role | Needs | Produces / evidence | Command or surface | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| o1 | Refresh outlines and the copies scan | job | manager | run active | outlines and `copies.json` current | `jason outlines --fetch`; `jason section-refs --scan` | whenever a rule changes or a copied document is amended (the SOP's trigger) | per run |
| o2 | Versions and adoption history of the Doc | job | manager | o1 | revisions kept by Drive; pending suggestions listed | `jason revisions KEY --fetch --versions` | none | "no adoption found" is a finding, never proof none happened |
| o3 | Check headings against the PDF | check | manager | o1 | every numbered capital line is a styled heading or a person says it is not | `python scripts/structure_fuzz.py gold ...` | none | skip: reason if no template is built |
| o4 | Classify each section; answer the questions | job, then person | manager | o1 | `classification.json`; asks in the intake queue answered | `jason manual --classify --asks`; `jason intake --answer ID TEXT --by NAME` | none | per unclear section |
| o5 | Concordance | check | jason | o4 | zero unresolved citations | `jason manual --concordance` | none | blocks o7 |
| o6 | Template equals the manual | check | jason | o4 | identical: yes; 0 unlabeled pieces | `jason document-template owners-manual` | none | after any base or block change |
| o7 | Render the rules and the manual | job | manager | o5, o6 | `rules-and-regulations.md`, `owners-manual.md`, `owners-manual.diff`; 0 unlabeled differences | `jason manual --render`; `jason manual --render --current` | none | the rules print the last adopted words |
| o8 | Read the plan for the Docs | plan | manager | o7 | Rules document and manual template Docs; the plan names folder, styles, link | `jason document-template rules-and-regulations`; `--doc plan`; then `--doc create --yes` (new kind `google.doc`) | none | a draft rules document is never filed where a folder syncs to a public list |
| o9 | Does the extraction need the 4360 notice? | decision | board | o7 | the board's choice, recorded; counsel read first if reading 1 is preferred | `jason board --set ITEM ...` | "notice the extraction under 4360(a)" is lawful under either reading (owners-manual.md) | opens a `rule-change` run |
| o10 | Refetch the Doc's links before publishing | job | manager | o8 | chips current | `jason outlines --fetch` | none | once |
| o11 | After adoption: citable document, aliases, rerun | person | manager | o9 | the rules document is a citable document and the rules book's source; run reopens o1 | profile edit, committed by a person | none | a `reopened` event on o1 to o7 |

## 3. Branches and failure paths

| Family and step | Failure or branch | What the run does |
|---|---|---|
| board-meeting m2 | A notice day already passed | blocked; the step says "a later meeting day noticed in time"; a follow-up opens; the run never marks 4920 met |
| board-meeting m12/m13 | No delivery on record | state `waiting`; after the notice-by date, a LEGAL follow-up in the law's words (4920(a)); "None on record is not none given": record the posting |
| board-meeting m13 | A file exists but no delivery | the clock stays open ("a file never meets a notice clock") |
| board-meeting m16 | Outcome `tabled`, `continued`, `referred` | decision step `waiting` (section 2.0); the item moves to a later meeting's run |
| board-meeting m16 | A vote the two recusal readings decide differently | the store refuses to record it (`held`); the step stays `ready` and shows both tallies |
| board-meeting m18 | No GPU headroom (`preflight` fails fast) | step `failed` with the message; the secretary writes the minutes by hand in the Doc |
| board-meeting m19 | Draft claims a quorum the count does not support | step blocked; shown first; correct the attendance or the statement |
| board-meeting m20 | 30 days pass with no availability record | LEGAL, recited; the run is not hidden |
| rule-change r1 | Two readings of the 4355 reach | `branch` records both; the board item says "the board asks counsel"; the lawful course under either is the notice (r6 to r9 stay applicable) |
| rule-change r9 | Delivery late or only a file | the 28-day clock is not met; decision meeting moves; r11 blocked |
| rule-change r13 | Words changed at the meeting | adopted words are entered from the minutes and differ from the noticed words; whether renotice is needed is a reading for counsel |
| rule-change r13 | Failed, tabled, or no action | the run ends or parks as the decision says; a decision not to act is kept |
| rule-change r18 | A reversal request arrives | opens an `election` run (kind `member vote`); r19 waits on its result; a reversed change cannot be readopted for one year (4365(f)) |
| election e3 | A rule amendment falls inside the 90-day window | e5 blocked until the date moves |
| election e5 | A required notice day has passed | the election date moves; no clock is shortened |
| election e9 | A disqualification | recorded with its basis and the appeal route; refused on a ground 5105(d), (e) rule out |
| election e14 | No quorum | e15 opens; materials stay in the inspector's custody |
| election any | Inspector's report not in hand | e16 and e17 stay `waiting`; a seat is never recorded from a name alone |
| hearing h8 | Notice not delivered in time | "the hearing must move" (the code's words, CIV 5855(a)); a new date and a new notice; h10 blocked |
| hearing h9 | The member cures or commits to cure | "The board shall not impose discipline"; the run closes `no discipline` with the record |
| hearing h13 | Decision notice past `noticeDueBy` | LEGAL follow-up; step shown overdue |
| hearing h11 | Decision recorded in one store only | `changed` event: the hearing row and `decisions.json` disagree; shown as a difference, never reconciled |
| law-review l2 | A reading is stale | blocks any use of it; redone by the board or counsel |
| law-review l7 | The extent of a conflict is unclear | recorded as "for counsel"; the course lawful under either reading is followed meanwhile |
| duty-schedule d4 | "contrary" evidence | goes to the board; nothing is recorded done |
| duty-schedule d7 | Unowned duty | d8 blocked; the unowned list is the finding |
| owners-manual o7 | An unlabeled difference | the render exits 1; the step `failed` with the diff |
| owners-manual o9 | The board declines the notice | a written finding for the record; the extraction stays unpublished |
| any plan step | Plan rejected, held, or superseded | per the approvals engine: rejected is recorded; held goes to the board; a changed source supersedes the plan and the run shows "changed since" |

## 4. The clocks and their basis

Law is recited from `data/authorities` as stored (jason's consolidated text, not an official restatement; the recorded or published copy governs).

| Clock | Basis | Operative words |
|---|---|---|
| Notice of a board meeting | law, CIV 4920(a), (b)(2), (b)(3), (c), (d) | "... the association shall give notice of the time and place of a board meeting at least four days before the meeting." Executive session only: "at least two days prior to the meeting." Longer in the documents: "the association shall comply with the period stated in its governing documents." |
| Minutes available | law, CIV 4950(a) | "The minutes, minutes proposed for adoption that are marked to indicate draft status, or a summary of the minutes, of any board meeting, other than an executive session, shall be available to members within 30 days of the meeting." |
| Act only on listed items | law, CIV 4930(a) | "... the board may not discuss or take action on any item at a nonemergency meeting unless the item was placed on the agenda included in the notice ..." |
| Executive matters in minutes | law, CIV 4935(e) | quoted in m17 |
| Proposed rule change | law, CIV 4360(a) | "The board shall provide general notice pursuant to Section 4045 of a proposed rule change at least 28 days before making the rule change. The notice shall include the text of the proposed rule change and a description of the purpose and effect of the proposed rule change." |
| Notice of an adopted rule change | law, CIV 4360(c) | "... not more than 15 days after making the rule change, the board shall deliver general notice pursuant to Section 4045 of the rule change." |
| Reversal request window | law, CIV 4365(b) | "The written request may not be delivered more than 30 days after the association gives general notice of the rule change, pursuant to Section 4045." The vote: "Not less than 35 days nor more than 90 days after receipt of a proper request." Results notice "not more than 15 days after the close of voting" (4365(g)). |
| Hearing notice | law, CIV 5855(a) | "... the board shall notify the member in writing, by either personal delivery or individual delivery pursuant to Section 4040, at least 10 days prior to the meeting." |
| Hearing decision notice | law, CIV 5855(f) | "... within 14 days following the action." (15 days before 2025-06-30; `statutory_terms.in_force` gives the period for a decision's date) |
| Election notices and dates | law, CIV 5103, 5105, 5115, 5120, 5125, 5145 | quoted in the e-steps; the catalog's anchors compute each day |
| Election rules amendment | law, CIV 5105(h)(4)(B)(iii) | "Election operating rules adopted pursuant to this section shall not be amended less than 90 days prior to an election." |
| Conflicts | law, CIV 4205(a) | "To the extent of any conflict between the governing documents and the law, the law shall prevail." |
| The year's law review | proposed policy | each January and when a law takes effect mid-year (jason's procedure; no statute sets it); the board adopts it as a duty assignment |
| Monthly duty read | proposed policy | the month before the board meeting; each duty's own clock is the law's or the documents' |
| Packet and reports | proposed policy | a week ahead, and again the day before |
| Comment deadline for a rule change | proposed policy | default the day before the decision; the board adopts or changes it |
| Election dates with room to correct | proposed policy | one correction before each notice day |
| Hearing suspension notice (15 days) | not verified | a code constant citing a section not on the authorities shelf; it is not recited until the section is on the shelf (a board or counsel question) |
| Internal dispute resolution, written resolution | law, CIV 5855(d), (e) | named only; CIV 5910 is not recited here (not read for this page) |

Where the law is silent, the run holds a question for the board and records it as a board item: who selects the inspector when the election rules are silent; whether a resent hearing notice cures a late one (docs/notices.md, open); how a comment on a rule change is recorded.

## 5. The screens

Common screens are those of the spine (§4): **Work** (`#/work`), **Run** (`#/work/<definition>/<id>`) with the step rail, step panel, clock strip, links, and history, **StartRun**, the small dialogs, and the Today/dock. This family adds no parallel screen: each step panel hands the act to the screen that already does it, and the run page shows that screen's current state.

**Routes.** `#/work/board-meeting/2099-10-20`, `#/work/rule-change/<key>`, `#/work/election/<id>`, `#/work/hearing/<opaque id>`, `#/work/law-review/2099`, `#/work/duty-schedule/2099-10`, `#/work/owners-manual/<revision>`. A hearing's run id is not `key_of` (day plus address slug): a URL carries an id or a filter, never an address ([security-and-privacy](../console/security-and-privacy.md)). The existing `POST /api/hearings/<key>` already puts the address slug in the path; the run uses an opaque id (a digest of the key) instead (gap).

**Step panels reuse these built screens** (`ui/src/App.tsx` `SCREENS`; loaders in `jason.web.sources`):

| Step | Screen and loader | What the panel shows from real fields |
|---|---|---|
| m4, r5, l12 | Board action items `#/actions`, `board-items` | item `status`, `owner`, `meeting`, `notes`, `evidenceRefs`; executive items held back outside the private view |
| m9, m10, m11 | Plan a meeting `#/agenda`, `agenda-plan`; Next meeting `#/meeting`, `meeting` | the plan's items and order, format line, notice-by with its source, `agendaMarkdown`, `minutesTemplate`, the commands |
| m15, m16 | Meeting room `#/room`, `meeting-room`; Decisions `#/decisions`, `decisions` | attendance, motions, roll call by name, `rules` with sources, executive state; the decision record |
| m18 to m20 | Minutes review `#/minutes-review`, `minutes-review` | the draft beside its checks (`quorum`, `claimsQuorum`, `confidential[]`, `unsupported`, `gaps`); a filled copy saved |
| m2, m12, m13, m21 | Meetings and minutes `#/meetings`, `meetings` (the watch and stages bands are **to add**) | `Watch.as_dict()`: `meetings[]`, `clocks[]` (`standing`, `deadline`, `record`, `notice`), `unrecorded[]`, `caveats` |
| m8, m11, h6, r7, d6 | Approvals `#/approvals`, `approvals` | the plan, items, held and for-a-person sections, the apply result |
| r3, r4, r13 | Rule changes `#/rules`, `rule-changes` | sections as current and proposed, placeholders, decisions for the board, the 4360 timeline |
| r0, r14 | Rules and authority `#/documents/rules`; loaders `rule-records`, `rule-record`, `rule-record-history`, `rule-record-compare`, `rule-uses`, `rule-events` (built, read only) | the version in force on a day, history, compare words, grounds |
| h2 to h15 | Hearings `#/hearings`, `hearings` | `stages` (notice by, hearing, decision by), `standing`, `scheduled`, `noticeRefs`, the decision entry, the decision-notice preview |
| e17, e2 | Onboarding `#/onboarding`; People `#/people` | election-status terms; "term ended; election due" |
| d4, d8 | Duties `#/duties` (the manager's duty anchors only), the dock's Deadlines and Tasks (`dock`) | anchors by cadence; the schedule band is **to add** |
| o7 to o11 | Templates `#/templates`; Records; the Rules records band | render results, the diff, the plan |

**What is specific to the family (components to add, over built ones):**
- **`MeetingStrip`** (`board-meeting` run header): date, kind, format, notice-by with source, minutes-by with source, the `Standing` word of each clock. Built from `Clock`, `Pill`, `DueDate`.
- **`DecisionStep`**: the step panel for every `decision` step. It reads `/api/decisions` for the linked agenda item and shows motion, mover, second, votes by name, recusals, outcome (a word), and links to `#/room` and `#/decisions`. Its only act is "Link to this agenda item". It has no approve control, and the words "approve" and "adopt" are not on any button. Built from `DecisionBrief` and `Findings`.
- **`ChangeFlow`** (designed in handoff-rule-records.md): the rule-change rail, equal to the spine's `WorkflowRail` with the 4360 clock line (`NoticeClockLine`). Built partly; the proposal pages are to add.
- **`ElectionTimeline`**: dates with the notice day each forces, computed from catalog anchors, each with its basis word. Built from `Clock` stages.
- **`HearingClock`**: today's `Clock` stages in `HearingsView` (notice by, hearing, decision by). Reused.
- **`LeadList`**: law-review leads, each with citing section, the statute recited first (`Recitation`), then the reading under `ReadingLabel`; acts "Record no conflict", "Record a conflict row to add to the profile", "Put on the board's agenda". To add.
- **`CoverageBand`**: the schedule's unowned duties and assigned-not-scheduled duties. To add (screens/schedule-and-duties.md).

**Loaders to add** (each wraps a function that exists): `work`, `work-run`; `meeting-watch` (`meeting_watch.watch`, `record_stages.histories`); `record-stages`; `schedule` (`schedule_agenda`, `schedule_assignments`); `governance-digest` (`attention.digest`); `notice-catalog` and `notices` (`notice_catalog.applicable`, `notice_ledger`); `conflict-leads` (`conflict_leads`); `election` (new store); `rule-proposals` and the rest of the rule-records phase 2.

**StartRun, per definition.** `board-meeting`: the date (from `meeting_schedule()` or a special date), the format, the kind; opening checks the 4-day day against today and says so if it has passed. `rule-change`: pick a `RuleChange` row (today only the profile's; a proposal is rule-records phase 2); the dates are computed, not typed. `election`: the kind and the four dates of section 9, each checked for room to correct. `hearing`: the unit by id, the violation in the board's words, the hearing date; the address is read from the unit record, never typed into a URL. `law-review`: a year. `duty-schedule`: a month. `owners-manual`: a revision of the manual's Doc.

**Today and the dock.** The dock's Deadlines already group the calendar by a screen hint; a run adds its next clock (name, date, basis word, office that owns it). The Tasks part (the action register) shows a `person` step as a task with the run as its source. The red counts stay the signed-in person's (`/api/dock?part=counts`): a step counts for an office when its role names that office.

**Export.** The run's history prints as a `Doc` for the board's record with its evidence addresses: for `board-meeting` the notice's address (`jason://notice/board-meeting-DATE`), the decision ids, and the minutes' stages; for `rule-change` the noticed and adopted versions (`RECORD@proposed-DATE`); for `hearing`, only in the private view (P3). Executive material is never in an export outside the private view.

**States.** Loading: skeleton and "reading the stores on disk". Empty: "No board meeting in the window: the profile sets no meeting schedule, and the catalog holds none." Missing: the loader's `found: false` note with the command that fills it, never an empty table (for example, "no hearings saved; plan one with `jason hearing`"). Stale: each band shows its freshness ("synced Oct 17, 06:00") with the refresh command; the watch reads the catalog as last built. Blocked: the step names what blocks it ("waiting on the 28-day notice to be delivered"). Changed since: a done step whose store moved (the minutes file changed, a decision re-recorded, the hearing row differs from the decision store) reads "changed since" with the difference.

## 6. Privacy and roles

Levels are `jason.web.access` (P0 public, P1 names and units, P2 contact details, P3 restricted, P4 secrets). The run list never carries an owner's contact details or an answer.

| Family | Steps and level | Who acts |
|---|---|---|
| board-meeting | notice, agenda, open packet, minutes: P0 or P1; the directors' packet: P1 to P3 (executive items by 4935 subject only); executive record and minutes: P3, private view | manager, secretary, treasurer, president; board decides |
| rule-change | rule text, notice, adoption: P0 (open once adopted); draft, reason, conflict flag: board-confidential (P1 board view); comments: P1 | any roster person drafts; secretary records; secretary sends |
| election | notices, results: P0; candidate list and voter list: P1 with addresses P2; ballots and tally sheets: held by the inspector, never in jason | secretary, manager; inspector outside the console |
| hearing | the hearing row, notice Doc, decision, `zoom/hearings/*`: P3 (private view, logged); the run list shows a state and a date, never the unit or the owner | president, manager, secretary |
| law-review | statutes and leads: P0; conflict flags for counsel: board; counsel's letters: P3 | manager, secretary, counsel (read) |
| duty-schedule | duties, roles, standings: P0 or P1; people's own task titles masked to the rule's label | each assignment's role; manager |
| owners-manual | rules and manual text: P0; open questions: P1 | manager |

Directors and officers have the same access to information (the board's decision of 2026-10-11): they differ in duties, not in what they may read. A director sees what an officer sees at the same level. By `access.SEE_RULES` the roster opens P0 and P1; the manager, president, vice president, director, secretary, and treasurer open P2 and, in the private view, P3 (the treasurer since 2026-10-11).

Roles come from the signed-in person's offices; the server enforces them (`access.SEE_RULES`). A step shows a person their own steps first and the rest as "waiting on the secretary". No role may skip a legal step: its absence is recorded as a finding for the board (recommendation of the spine; a decision for the user).

## 7. What exists now

Verified in the repo on 2026-10-11 unless marked "not verified".

| Piece | State |
|---|---|
| SOPs in `jason.community.procedures` | present: `board-packet`, `rule-change`, `election`, `law-review`, `duty-schedule`, `document-duties`, `owners-manual`, `rule-history`, `notice-delivery`. **No SOP for a hearing, and none for minutes approval.** |
| Commands | `jason meetings`, `schedule-evidence --watch`, `notices` (`--catalog`, `--sync`, `--mark-general`, `--proof`), `notice-check`, `board` (`--packet`, `--agenda`, `--notice`, `--minutes`, `--recheck`, `--set`, `--members`), `report`, `minutes-privacy`, `record-stages`, `rule-change` (`--list`, `--draft-email`, `--from-manual`), `rule-records` (read only), `revisions`, `hearing` (`--list`, `--doc`, `--create`, `--notice-on`, `--suspension`), `letter`, `conflicts` (`--leads`), `law-history`, `readings --stale`, `schedule`, `duties`, `manual`, `document-template`, `onboard`, `applies`, `intake`, `lessons`, `sop` |
| Approvals kinds | `owner-info-tags`, `payhoa-attach-bills`, `gmail-drafts` (cases `proposal-request`, `hearing`, `meeting-notice`). The letters store (`data/approvals/letters.json`) holds the members' packet copy. **Not built:** `google.doc`, `google.calendar`, `google.tasks`, `zoom.hearing.create`, a `rule-change` or decision-notice case of `gmail-drafts`, PayHOA broadcast and Mailroom kinds, `local.section-refs.apply` |
| Stores | `data/board/items.json`, `decisions.json`, `data/meetings/room-DATE.json` (+ `-executive.json`), `plan-DATE.json`, `data/zoom/hearings.json`, `data/schedule/done.jsonl`, `data/notices/` ledger, `data/followups/acts.jsonl`, `data/rule-records/` (when exported), `data/duties/<key>.json`, `data/manual/KEY/` |
| Console loaders (built) | `board-items`, `decisions`, `agenda-plan`, `meeting`, `meetings`, `meeting-room`, `minutes-review`, `rule-changes`, `hearings`, `approvals`, `duties`, `calendar`, `dock`, `people`, `rule-records`, `rule-record`, `rule-record-history`, `rule-record-compare`, `rule-uses`, `rule-events`, `followups`, `jobs` |
| Console writers (built) | `POST /api/board-items/<id>`, `/api/decisions`, `/api/hearings/<key>` (the decision), `/api/write/minutes-review`, `/api/write/meeting-room`, `/api/write/agenda-plan`, `/api/write/approvals`, `/api/write/dock` |
| Screens (built) | Board action items, Decisions, Plan a meeting, Meeting room, Meetings and minutes, Next meeting, Minutes review, Rule changes, Hearings, Approvals, Duties by cadence, Annual disclosures, People, Templates |
| Scheduler cadences | `payhoa-notices` (`meetings --sync`), `zoom`, `calendar` and `tasks` (`schedule --read-google`), `drive`, `gmail` already registered; a write is never scheduled |
| **Not built** | loaders `meeting-watch`, `record-stages`, `schedule`, `governance-digest`, `notice-catalog`, `notices`, `conflict-leads`, `rule-proposals`; any election store or screen; the schedule band on `#/duties`; the watch and stages bands on `#/meetings`; web writers for "record a posting" (`notice_ledger.set_general`) and "record done" (`record_completion`: CLI and MCP only) |

Not verified: that `jason notices KEY --sync` tracks a single member's hand-delivered hearing notice; `jason readings --stale` output fields; the `statutory_terms` row for the suspension period; CIV 5910 and Corp. Code 7341 text (not on the shelf).

## 8. Gaps and the build order

Gaps found against the repo:
- **No SOP for a hearing.** `jason hearing` plans and drafts; nothing says what to check, in what order, or what went wrong before. Add SOP `hearing` and a lesson on the late-notice path.
- **Two stores for one hearing decision**: `data/zoom/hearings.json` (findings, `noticeDueBy`) and `data/board/decisions.json` (the vote). A run needs one; the hearing row should link the decision id.
- **The hearing key carries an address** in URLs and run ids (`key_of`).
- **No cure record** (5855(c)) and no record of the member's request for executive session; no penalty-schedule check (5850(c)) against the schedule in force on the violation's day.
- **`noticeOn` is the person's statement**, not read from the delivery ledger; whether the ledger tracks a one-member notice is not verified.
- **`SUSPENSION_NOTICE_DAYS = 15`** cites a section not on the authorities shelf.
- **No election store**: inspector, voter list, candidate list, nominations, dates, ballots, custody. Only notices (catalog rows), the nomination form, and the seats question exist.
- **Rule-records phases 2 and 3 are not built**: no proposal store, event log, comment record, or `record-adoption`.
- **No comment record** for a proposed rule change (4360(b) requires consideration of comments).
- **No reversal-request intake** (4365): the 5 percent test and the 30-day window have no store.
- **`rule-change --draft-email` is not an approvals case**; `meeting-notice` and `hearing` are.
- **The meeting watch and record stages are not on the console**, so the secretary's clocks are CLI only; "record a posting" and "record done" are not web writes.
- **The schedule is not on the console**: `#/duties` shows the manager's anchors, not assignments, occurrences, or coverage.
- **No law-review screen**: leads and conflicts are CLI and MCP (`document_conflicts`, `citation_gaps`).
- **The minutes approval has no SOP step**; `record-stages` reads it from later minutes.

Decisions that are this family's and the user's to make:
- **Child runs or links for a decision step.** A `decision` step is a link to an agenda item of a `board-meeting` run (recommended: one meeting hosts many decisions; no second run per motion).
- **Who may record a decision.** The Decisions screen is for officers and administrators today; the personas page proposes the president or the secretary for the profile-row writes. Recommended: the president or the secretary for every `decision` step.
- **One hearing decision store** (recommended: `decisions.json` is the vote; the hearing row keeps findings and links the decision id).
- **Whether the manual extraction (o9) always takes the notice** (recommended: yes, the course lawful under either reading, with counsel read first if the board prefers reading 1).
- **Who selects the inspector when the election rules are silent**: a question for the board, not a default.
- **Whether a rule-change comment deadline is adopted** as a rule row (proposed policy until then).

Build order (after the spine's steps 1 to 3):
1. **Pure definitions** for `board-meeting` and `rule-change` over the existing `Procedure` rows, with the `decision`-step reader of `decisions.json`. These two use the most that is built.
2. **Loaders** `meeting-watch`, `record-stages`, `schedule` (read only), then the `board-meeting` Run page over `#/meetings`, `#/agenda`, `#/room`, `#/decisions`, `#/minutes-review`.
3. **Web writers** for "record a posting" and "record done" (signed, behind `Confirm`).
4. **Approvals cases and kinds**: the `rule-change` and decision-notice cases of `gmail-drafts`; `google.doc`; `zoom.hearing.create`.
5. **`hearing`**: write the SOP, merge the two stores, opaque id, cure and executive-session requests.
6. **`rule-change` phase 2** (proposal store, event log, comment record) and the reversal intake.
7. **`duty-schedule`, `law-review`, `owners-manual`** definitions and the schedule band, the leads list.
8. **`election`**: the store and `ElectionTimeline`, last, because nothing of it is built beyond notices.

## 9. A made-up sample run

`board-meeting` for 2099-10-20, in-person format, as of 2099-10-17. People appear only as offices.

| Step | State | Who or wait | Note |
|---|---|---|---|
| m1 catalog | done | jason, 2099-10-17 06:00 | job finished |
| m2 clocks | done | jason | notice by 2099-10-16; minutes of the 2099-09-15 meeting due 2099-10-15 |
| m3 kind and format | done | Secretary | ordinary, in person |
| m4 items | done | Manager | 4 items on the agenda; 1 executive item (by subject) |
| m5 reports | done | Manager | no report stale |
| m6 Treasurer's report | needs a person | Treasurer | September run not in the catalog yet |
| m7 packet | blocked | none | by m6 |
| m8 Doc and members' copy | not started | Manager | needs m7 |
| m9 agenda | done | Secretary | format line names "in person" |
| m10 notice | done | Secretary | text checked, 0 missing |
| m11 Gmail draft | done | Secretary | draft saved 2099-10-14 |
| m12 post and send | done | Secretary | "posted on the clubhouse board, 2099-10-15, 09:00" |
| m13 delivery | waiting | jason | sent, 2 follow-ups owed; next sync tomorrow |
| m14 share packet | not started | Secretary | needs m8 |
| m15 hold the meeting | waiting | none | until 2099-10-20 |
| m16 motions | not started | Board | 3 motions expected |
| m18 to m21 | not started | Secretary, Board | minutes due 2099-11-19 (30 days, law, 4950(a)) |

Clock strip: notice 2099-10-16 (law, 4920(a)): "on record in time: delivered, with follow-ups owed"; minutes 2099-11-19 (law, 4950(a)): "none on record yet". Links: approval `apr-0012` (gmail-drafts, applied), board items BI-2099-04, BI-2099-05, a `rule-change` run (decision at m16, item 2), a `hearing` run (executive item 4). History: newest first, each with who and when.

`rule-change` `example-parking`, as of 2099-10-17 (the item on that agenda):

| Step | State | Note |
|---|---|---|
| r1 facts | done | `rule_scope=listed_subject` recorded by the secretary as the board's reading |
| r4 timeline | done | notice 2099-09-21; decision meeting 2099-10-20 (29 days later) |
| r9 delivery | done | delivered 2099-09-21: 29 days before the meeting (28 required, law, 4360(a)) |
| r10 comments | done | 3 comments, entered by the secretary |
| r11 agenda item | done | link to m4 above |
| r13 decision | waiting | at the meeting; no approve control |
| r15 to r19 | not started | adoption notice due within 15 days of the decision (law, 4360(c)) |

`hearing` for the unit at 123 Main St (the page shows "Unit H-1", never the address), as of 2099-11-06. The owner is A. Owner and appears only in the private view.

| Step | State | Note |
|---|---|---|
| h1 matter | done | recorded by the president; penalty within the schedule in effect on the violation's day (a person's statement; no check built) |
| h2 dates | done | notice by 2099-11-07 (10 days, law, 5855(a)); if only executive session, notice of the meeting by 2099-11-15 (2 days, law, 4920(b)(2)); decision notice by 2099-12-01 if the board acts on 2099-11-17 (14 days, law, 5855(f)) |
| h4 notice Doc | done | Doc from the template; 0 elements missing |
| h5 Zoom | skipped | in-person hearing; reason recorded by the manager |
| h6 Gmail draft | done | draft saved; sent by a person |
| h7 deliver and record | done | delivered 2099-11-05 by personal delivery (the manager's statement) |
| h8 read delivery | waiting | no ledger entry yet; "notice by 2099-11-07" |
| h9 cure window | waiting | no cure or commitment on record |
| h10 to h16 | not started | blocked by h8 |

`election` (directors), computed from the catalog's anchors for a nomination deadline of 2100-03-01, ballots out 2100-04-01, voting deadline 2100-05-03, count and election day 2100-05-04. Every day is "computed", with the row it came from; none is typed.

| Day | Step | Basis |
|---|---|---|
| 2099-12-01 | e8 initial acclamation notice (at least 90 days before the nomination deadline) | law, 5103(b)(1), only if acclamation is available |
| 2100-01-30 | e7 nomination-procedure notice (at least 30 days before) | law, 5115(a) |
| 2100-01-30 to 2100-02-22 | e8 reminder window (between 7 and 30 days before) | law, 5103(b)(2) |
| 2100-02-03 | last day to amend the election rules or let a member change voting method (90 days before the election) | law, 5105(h)(4)(B)(iii), 5105(i)(1)(A) |
| 2100-03-02 | e11 pre-ballot notice (at least 30 days before ballots are distributed) | law, 5115(b) |
| 2100-04-03 | e12 last day to deliver ballots (not less than 30 days before the voting deadline) | law, 5115(c) |
| 2100-05-19 | e16 results notice (within 15 days of the election) | law, 5120(b) |

## 10. Acceptance criteria

1. Each definition above loads from the `Procedure` rows plus the added step kinds, and every step has a kind, a role, and a basis for every clock it carries.
2. No `decision` step can be completed from the run page. It becomes `done` only when `data/board/decisions.json` holds a decision with outcome `approved` or `denied` for the linked agenda item; `tabled`, `continued`, and `referred` leave it `waiting`.
3. The run page has no control labeled approve, adopt, vote, or send. A `plan` step ends in the Approvals screen; a mailing, a posting, and a delivery are a `person` step attested with a date.
4. A run for a meeting with no delivery on record by the notice-by date shows the LEGAL state, recites CIV 4920(a), and opens a follow-up; it does not mark the clock met.
5. A notice "file" never meets a clock; only a delivery (or a send with follow-ups listed) does (`record_stages`).
6. A `rule-change` run schedules its decision meeting no earlier than the first meeting at least 28 days after the notice's delivery; `r11` is blocked otherwise.
7. An emergency rule change skips r6 to r10 and r17 with a recorded reason; a not-emergency path cannot skip them.
8. A `rule-change` adoption notice step shows its due day as 15 days after the decision (law, 4360(c)) and the reversal window as 30 days after general notice (4365(b)).
9. A reversal request opens an `election` run; r19 does not complete until it ends.
10. An `election` run refuses a date plan in which a rule amendment falls inside the 90-day window of 5105(h)(4)(B)(iii), and moves an election whose notice day has passed.
11. A nomination's acknowledgment step shows the seven-business-day clock (5103(c)) and opens a follow-up if it passes.
12. A `hearing` run refuses to mark h10 ready when h8 shows no delivery by the notice-by day; the page says "the hearing must move".
13. A `hearing` run's list row and URL carry an opaque id, a state, and a date; they carry no address, name, or matter. A director reads what an officer reads at the same level.
14. A `hearing` decision step shows the decision-notice due day (`noticeDueBy`, 14 days) and goes overdue past it.
15. Executive-session material appears only in the private view; elsewhere the step reads the 4935 subject in the statute's words.
16. A `law-review` run lists a lead only with the statute recited first and jason's reading labeled; it creates no `Conflict` row; the row is a profile edit a person commits.
17. A `duty-schedule` run refuses `done` on a duty with no name or evidence, and keeps d8 blocked while the unowned list is non-empty.
18. An `owners-manual` run fails o7 on an unlabeled difference and never writes a Doc without a recorded approval.
19. Reopening a run re-checks every done step's evidence against its store; a moved store shows "changed since" with the difference and writes a `changed` event.
20. Every link in this page resolves to a file under `docs/`.
