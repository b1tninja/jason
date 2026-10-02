# Meetings, resolutions, and elections

Models for the `meetings` group, in four modules under `jason.community.models`:

| Module | Model | Kind |
| --- | --- | --- |
| `meetings` | `meeting-agenda` | `agenda` |
| `meetings` | `meeting-minutes` | `minutes`, and annual meeting minutes filed as a `notice` |
| `meetings` | `executive-session` | `executive_session` |
| `meetings` | `committee-report` | `committee_report` |
| `meetings_elections` | `election-results` | `election_results` |
| `meetings_elections` | `secret-ballot` | `ballot` |
| `meetings_elections` | `pre-ballot-notice` | `notice` (Pro Elections' pre-ballot notice) |
| `meetings_notices` | `notice` | `notice` (everything else) |
| `meetings_resolutions` | `board-resolution` | `resolution` |

For a `notice`, the models are tried in that order: minutes, then the pre-ballot notice, then the general notice.

## Coverage

Per-kind counts come from `jason models`. This association's findings are in its private notes (mystique/notes/document-models/meetings.md).

## Shared parsing

The association's agendas and minutes are one Google Docs template exported to PDF:

- **Header.** The association, the meeting ("Regular Meeting of the Board of Directors", "Special ...", "Annual Membership Meeting", "Executive Session of the Board of Directors"), "To be held on" (agenda) or "Held on" (minutes), the date and time, and the Zoom details. Some exports print this block at the bottom of page one.
- **Items.** Roman-numeral items (`I.`, `II.`), with `i.`/`ii.`, `A.`/`B.`, or `1.`/`2.` sub-items, bulleted notes, and linked file names.
- **Running footer.** It repeats the association, "(Zoom)", the meeting title, and the date. `strip_furniture` removes it before the items are read.

`parse_items` returns `AgendaItem(number, title, subitems, notes, attachments)`. It stops at the Zoom summary ("Quick recap", "Summary", "Next steps"), the decorum rules, or an appendix. `meeting_header` reads the meeting type (`MeetingType`), the body (`MeetingBody`), the date, the time, whether the meeting is by teleconference, whether there is a dial-in, the meeting ID, a physical location if one is named, and the DRAFT mark.

The former manager's agenda (The Helsing Group, January 2024) numbers its items 1 to 7: consent, review, action, discussion, member comment, and adjournment, with lettered sub-items. It reads with `layout = "manager"`.

Cross-checks read the classified library on disk (`jason.tasks.library`), matching files by period. An annual meeting is matched by year and name. They say nothing when there is no library.

## Agenda

**Record** (`Agenda`):

- **The meeting:** `layout`, `preparer`, `meeting_type`, `body`, `meeting_date`, `meeting_time`.
- **How to attend:** `teleconference`, `dial_in`, `meeting_id`, `physical_location`, `tech_assistance`, `individual_delivery_reminder`.
- **Posting:** `posted_on`, when the text shows it; `notice_sent` and `notice_subject`, the PayHOA email notice for the meeting, from the communications log `jason meetings` saves (`data/payhoa/communications.json`), not from the text. A subject without a year ("March 17th") takes the year nearest the day it went out; a "(Preview)" send is not a notice.
- **Items:** `items`, `executive_topics`, `member_comment`, `next_meeting`, and `prior_minutes` (the dates of the minutes listed for approval).
- **Items the law shapes:** `borrowing_notice`, `rule_change_items`, `acclamation_item`.

| Finding | Severity | Authority | When |
| --- | --- | --- | --- |
| `notice-late` | problem | CIV 4920(a), (b) | The posted date is fewer than 4 days before the meeting (2 days for executive session only). |
| `notice-sent-late` | check | CIV 4920(a), (b), 4045 | PayHOA's notice email went out fewer than 4 days before a board meeting (2 for executive session only). A posting the annual policy statement designates may have come sooner. |
| `members-notice` | check | Corp. Code 7511(a) | PayHOA's notice email for a members' meeting went out fewer than 10 days before it. The inspector's pre-ballot notice, which names the counting meeting, may have served. |
| `posting-date-not-shown` | info or check | CIV 4920(a), (d) | A board agenda that does not say when it was posted, with no notice email found. It is a check when PayHOA's log covers the meeting's date. |
| `teleconference-notice` | check | CIV 4090(b), 4926(a)(1), (4) | No physical location, and the agenda lacks a help contact (phone and email), the individual-delivery reminder, or a dial-in. |
| `ballot-count-online` | check | CIV 4926(b), 5120(a) | An annual meeting that counts ballots, with no physical location. |
| `borrowing-notice` | check | CIV 5515(a), (b) | A Notice of Intent to Borrow item without the reasons, the repayment options, or the special-assessment statement. |
| `rule-change` | check | CIV 4355(a), 4360(a), (b) | A rule or policy item. If it adopts a covered operating rule, it needs 28 days' notice. |
| `acclamation-names` | check | CIV 5103(e) | An acclamation item that does not name the candidates. |
| `executive-topic` | check | CIV 4935(a) | An executive session topic outside litigation, contracts, discipline, personnel, assessments or payment plans, or foreclosure. |
| `no-member-comment` | info | CIV 4925(b) | A board agenda with no open forum item. |
| `no-minutes-on-file` | check | CIV 4950(a), 5210(a)(2) | More than 30 days after the meeting, and no minutes for it in the library. |
| `prior-minutes-not-on-file` | check | CIV 5200(a)(8), 5210(a)(2) | Minutes listed for approval that the library lacks. |

## Minutes

**Layouts** (`MinutesLayout`):

- `annotated_agenda`: the secretary's notes under each agenda item (2024 to early 2025).
- `ai_summary`: the agenda followed by a Zoom AI "Quick recap / Next steps / Summary" (mid 2025 on).
- `no_quorum`: a one-page record that the meeting lacked a quorum (August and September 2025).
- `narrative`: prose minutes with attendance, motions, and adjournment. None is in the library yet; the test covers it.

**Record** (`Minutes`):

- **The meeting:** `meeting_type`, `body`, `meeting_date`, `meeting_time`, `teleconference`, `physical_location`.
- **Status:** `draft`, `approved_on`, `called_to_order`, `adjourned`.
- **Attendance:** `quorum`, `quorum_note`, `directors_count` (a summary's "reached quorum with four directors attending"; it names no one), `directors_present`, `directors_absent`, `others_present`. The quorum reads from what the text says: "reached quorum", "confirming a quorum", "all board members were present", or "one more board member ... then joined"; "despite the lack of quorum" or "three board members were needed ... waiting for" leaves it open, with the sentence in `quorum_note`.
- **Proceedings:** `items`, and `actions`. Each `Action` has its text, an `Outcome` (approved, denied, or tabled), the amount in cents, the mover, the seconder, the yes/no/abstain counts, whether it was unanimous, and whether it was a roll call.
- **Prior minutes:** `prior_minutes`, `prior_minutes_approved`.
- **Executive session:** `executive_session`, `executive_topics`, `executive_summary`, `executive_detail`. The minutes copy the agenda's "Adjourn to Executive Session", so `executive_session` means the session was planned; a summary that puts it off ("the need for future executive sessions") sets it false. A summary sentence that names the session's 4935 subject ("reconvene ... for an executive session to address a disciplinary hearing") is the general note. `executive_detail` is a summary that recounts the session ("During the executive session, the board discussed ...").
- **The rest:** `reserve_transfer`, `ai_summary`, `next_steps`, `next_meeting`, `has_proceedings`.

| Finding | Severity | Authority | When |
| --- | --- | --- | --- |
| `minutes-draft` / `draft-after-next-meeting` | info / check | CIV 4950(a) | Marked DRAFT. It is a check once the next meeting, where the minutes would be approved, has passed. |
| `minutes-due` | info | CIV 4950(a) | Within 30 days of the meeting. |
| `no-quorum` / `quorum-question` / `quorum-not-shown` | info / check / check | Bylaws 7.10, 10.10 | The meeting lacked a quorum; actions sit beside a quorum sentence that doubts it ("despite the lack of quorum", "needed ... waiting for"); or formal minutes record actions with no attendance. |
| `membership-not-shown` | check | Bylaws 10.10 | Minutes of a members' meeting that record business but not the memberships present or represented. |
| `no-proceedings` | check | Bylaws 10.10 | The minutes only repeat the agenda. |
| `no-roll-call` | check | CIV 4926(a)(3) | Board actions at a teleconference meeting with no physical location, and no roll call recorded. Not for an AI summary (see `ai-summary`) or a members' meeting (4926(a)(3) is the directors' vote). |
| `votes-not-recorded` | check | none | Actions with no vote count (when `no-roll-call` does not already apply). |
| `ai-summary` | check or info | Bylaws 10.10, CIV 4926(a)(3) | The proceedings are a Zoom AI summary. It is a check when the summary tells of decisions but not who attended, the quorum, or each director's vote (by roll call at a Zoom-only meeting). The summary retells the call; it is never expected to hold a roll call, so this one finding stands in for `no-roll-call`, `quorum-not-shown`, and `votes-not-recorded`. |
| `executive-session-not-noted` | check | CIV 4935(e) | A planned executive session with no general note in these minutes or the next ones in the library. |
| `executive-detail` | check | CIV 4935(a), (e) | The AI summary in the open minutes recounts what the executive session discussed. |
| `reserve-transfer` / `reserve-transfer-finding` | info / check | CIV 5515(c), (d) | A transfer from reserves, with or without when and how it is repaid. |
| `no-agenda-on-file` / `agenda-on-file` | check / info | CIV 4920(d), 5200(a)(8) | Whether the library has an agenda for the same date. |
| `not-on-agenda` | check | CIV 4930(a) | Items in the minutes that the library's agenda for that date lacks. |
| `filed-as-notice` | info | none | Minutes the library classifies as a notice. |

## Executive session, committee report

- **`ExecutiveSession`:** `meeting_date`, `meeting_time`, `draft`, `parent_meeting`, `topics`, `subjects` (the `ExecutiveSubject` members), and `unlisted_topics`. Findings: `executive-topic` (CIV 4935(a)), `executive-only-notice` when the session stands alone (CIV 4920(b)(2)), and `note-in-open-minutes` (CIV 4935(e), 5200(a)(8)).
- **`CommitteeReport`:** `committee`, `year`, `report_date`, `proposals` (each with its title and prices in cents), and `recommendation`. It has no statutory checks.

## Resolutions

The association's template is signed through Acrobat Sign:

- **Title block:** "SPECIAL RESOLUTION [NUMBER n]", "Relating to ...".
- **Body:** the WHEREAS recitals, then NOW, THEREFORE, BE IT RESOLVED.
- **Signatures:** an IN WITNESS WHEREOF block signed by the President and Treasurer. E-signature stamps print as "Name (Mon d, yyyy hh:mm PST)".
- **RESOLUTION ACTION RECORD:** the type, number, what it pertains to, the mover and seconder, each director's YES/NO/ABSTAIN, and the Secretary's attestation.

The form's filled values print in one of two ways. They may appear in place ("X YES"), as in the 2023 resolutions. Or they may appear after the page, in form order: the type, number, and what it pertains to; the mover and seconder; the directors' names where the form left them blank; then one mark per director. Two names after the page are the mover and seconder, five are the directors, and seven are both.

**Record** (`Resolution`):

- **What it is:** `resolution_type` (`ResolutionType`), `number`, `title`, and `subject` (`ResolutionSubject`: borrow reserves, invest reserves, meeting schedule, foreclosure, excess income, or other).
- **What it says:** `whereas`, `resolved`, `amounts` (cents), and `statutes`.
- **Adoption:** `adopted_on`, from "adopted at a meeting held", the date in the number, or DATED.
- **Signatures:** `signers` (each block and its e-signature date) and `e_signatures`.
- **Action record:** `action_record`, `motion_by`, `seconded_by`, `votes` (`DirectorVote`: office, name, `Vote`), and `vote_marks`.
- **Attestation:** `attested_by`, `attested_on`, `attestation_signed`.
- **Exhibits:** `exhibits`.

| Finding | Severity | Authority | When |
| --- | --- | --- | --- |
| `unsigned` / `signature-missing` | check | none | No signature, or no signature for a named signer, appears in the text. |
| `no-vote-record` | check | CIV 4910(a) | There is no action record. |
| `vote` / `vote-short` | info / check | none | The YES count, and whether it falls short of a majority of the directors listed. |
| `vote-marks` / `no-votes-marked` | check | none | Marks the text cannot tie to a column, or empty boxes. |
| `no-mover` | info | none | The mover and seconder are blank. |
| `attestation-unsigned` | check | none | The Secretary's attestation has no signature in the text. |
| `borrowing-reasons`, `borrowing-repayment` | check | CIV 5515(c) | A borrowing resolution without the reasons, or without when and how it is repaid. |
| `borrowing-special-assessment`, `borrowing-notice` | check | CIV 5515(a), (b) | A borrowing resolution that does not say whether a special assessment may be considered, or does not recite the meeting notice. |
| `restore-reserves` | info | CIV 5515(d) | The date one year after adoption. |
| `on-agenda` / `not-on-agenda` / `no-agenda-on-file` | info / check / check | CIV 4930(a), 5200(a)(8) | Whether the adoption meeting's agenda in the library carries the item. |

## Elections (Pro Elections LLC)

**Records:**

- **`ElectionResults`**, from the "Official Election Results" page (2023 on) and the "Post-Election Results and Meeting Notice" (2021, acclamation):
  - **The election:** inspector, inspector's name, election, date.
  - **Turnout:** ownership units, ballots received, quorum achieved.
  - **Results:** seats, candidates (votes, elected, tie-break), measures (yes, no, no response, outcome), acclamation, term, certification.
  - **The inspector's timeline:** call for candidates, reminder, nomination deadline, pre-ballot notice, ballot package, tally.
- **`Ballot`:**
  - **The ballot:** secret, seats, cumulative voting, maximum votes, candidates, measures.
  - **Return and count:** due date and time, the count's date, time, and place, whether the count is online.
  - **Quorum:** the ballots required and the quorum rule.
  - **Checks on the face:** the rules phrase, voter identification, amendment text.
- **`PreBallotNotice`:** notice date, ballots-mailed date, candidates, seats, the corrections deadline, the return deadline, time, and address, the count's date and time, whether it is online, the reconvene statement and quorum, and voter-list verification.

| Finding | Severity | Authority | When |
| --- | --- | --- | --- |
| `no-inspector` / `not-certified` | check | CIV 5110 | The results name no inspector, or carry no certification. |
| `nomination-notice` / `pre-ballot-notice` / `ballot-timing` | problem | CIV 5115(a), (b), (c); 5105(h)(4) | The inspector's own timeline shows less than 30 days. |
| `acclamation-notices` / `acclamation-reminder` | check or problem | CIV 5103(b) | Seated by acclamation without the 90-day initial notice, or without the reminder 7 to 30 days before the deadline. |
| `results-notice` | info | CIV 5120(b) | The date 15 days after the election. |
| `results-in-minutes` / `results-not-in-minutes` / `results-minutes-not-on-file` | info / check / check | CIV 5120(b) | Whether the board's next meeting (within four months) has minutes in the library, and whether they take up the election. |
| `keep-election-materials` | info | CIV 5200(c), 5125 | Within one year of the election. |
| `turnout`, `tie-break`, `unit-count`, `seats-filled` | info / check | CIV 5110(c)(1) | The facts on the results page. |
| `voter-identified` | problem | CIV 5115(c) | The ballot face asks for a name, unit, address, or signature. |
| `rules-phrase` | check | CIV 5105(h)(4)(B) | The ballot lacks "The rules governing this election may be found here:". |
| `ballot-count-online` | check | CIV 4926(b), 5120(a) | The count is online with no physical place. |
| `pre-ballot-late`, `no-return-address` | problem | CIV 5115(b), (b)(1) | The notice came fewer than 30 days before the ballots, or gives no return address. |
| `no-reconvene-statement` | check | CIV 5115(b)(6) | The notice lacks the 20 percent reconvened-meeting statement. |
| `voter-list` | info | CIV 5105(a)(7) | The last day members can verify their voter-list entries. |

## Notices

`NoticeType` sorts the library's notices:

- **Hearing:** a violation and a disciplinary hearing.
- **Violation:** a violation letter without a hearing.
- **Litigation disclosure.**
- **Work:** access closed for maintenance.
- **Announcement.**
- **Meeting.**
- **Recorded instrument:** the builder's Right to Repair Act election, recorded in 2019, which is filed as a notice.

**Record** (`Notice`): `notice_type`, `title`, the letter's own `notice_date` (the date at its head, before the salutation), `signed_by`, and the governing-document `provisions` and `statutes` cited. The facts of each sub-type sit in that sub-type's record, and the others stay empty:

- **`violation`** (`Violation`): the fine in cents, whether privileges may be suspended, and the `hearing` (`Hearing`: date, time, place, the right to attend and address the board, a written response, a continuance).
- **`litigation`** (`Litigation`): the case number, court, filing date, a "not a party to any pending litigation" statement, and how it was delivered.
- **`work`** (`Work`): the day, the hours access closes, the contractor, and whether vehicles are towed.
- **`event`** (`Event`): a meeting or announced event's date, time, and teleconference.
- **`recording`** (`Recording`): the document number, the recording date, and the pages.

Owners' names and addresses are not kept, nor the case name (it names private persons).

| Finding | Severity | Authority | When |
| --- | --- | --- | --- |
| `hearing-notice-content` | problem | CIV 5855(b) | A hearing notice without the date, time, place, alleged violation, or right to attend and address the board. |
| `hearing-notice-late` / `hearing-notice-date` | problem / check | CIV 5855(a) | Dated fewer than 10 days before the hearing, or undated. |
| `case-not-tracked` / `filing-date-differs` | check | none | A litigation letter names a case the specification's `legal_cases` lacks, or a filing date other than the case record's. |
| `no-litigation-contradicted` | check | none | A letter says the association is not a party to pending litigation, dated on or after a suit the specification records the association filed or defends, before it closed. |
| `recorded-instrument`, `litigation` | info | none | The facts. |

## What the real files show

This association's findings are in its private notes (mystique/notes/document-models/meetings.md).

## What the text cannot show

- **Posting.** When or how an agenda was posted, and whether the notice email carried the teleconference content the agenda lacks. PayHOA's log gives when the email went out and to how many, not its body.
- **Attendance in a summary.** Who joined the call; Zoom's participant list has it, not the minutes.
- **Signatures.** Wet or image signatures and stamps.
- **Marks.** Which column an after-page mark belongs to.
- **Votes.** How each director voted when the minutes are a summary.
- **The posted agenda.** Whether the library's agenda is the version posted. `not-on-agenda` is a lead, not a determination.
- **Timeline.** Election dates the inspector's timeline does not print.
- **Delivery.** Whether a hearing notice was delivered 10 days ahead, when the letter is undated.
