# Journeys

Six walks through the console, step by step, with the screen each step touches. They test the screen specs ([screens/](screens/README.md)) against real work: if a step needs something no screen offers, a spec is missing it.

The people are fake: Jane Example (manager), Casey Sample (treasurer), Jordan Example (director), Sam Placeholder (Secretary), Riley Test (director). The association is Example Village HOA. Dates are in 2099.

Each step names its screen in brackets, and its CLI equivalent where one exists. The screen names are the specs'; [information-architecture.md](information-architecture.md#the-specs-screens-mapped) maps each to its console route (Today is `#/digest`, Meetings & minutes is `#/meetings` and its neighbors, and so on). A step on a screen with no counterpart yet (Members & units, Notices, Governing documents, the onboarding session) walks the proposed screen.

## (a) The manager applies the owner-information answers

Owners have been answering the year's owner-information form. Jane Example brings PayHOA up to date, leaves the board's questions for the board, and lets the requests that are fully recorded complete.

1. **See it is time.** [Today] The digest's requests section and the cycle's deadline show "answers in PayHOA by Nov 1: 29 days left". No approval of this kind is open.
2. **Read the owners.** [Members & units] The owners table: 21 answered this cycle, 12 with an election on file, 12 with no election. The next-action column shows "2 writes" for most answered owners and "held" for one.
3. **Plan.** [Terminal → Approvals] Jane runs `jason approvals plan owner-info-tags --by "Jane Example"`. It reads PayHOA live once: units, people, the form's signed-in submissions. The plan appears in the Approvals inbox, beside the letters.
4. **Review.** [Approvals → one approval] The approval opens `planned`:
   - 10 approvable writes for 4 owners, grouped by unit. Each shows before → after, the reason in the planner's words ("no election on file: the law sends first-class mail (4040(a)(2))", "this cycle's answer (payhoa:678)"), the rule with **recite**, and its evidence chips.
   - Under two units, a dependent line: "Then: complete request 678, comment emailed to the owner (waits on the 2 writes above)", reciting the board's owner-information rule row.
   - **Held for the board (2):** two occupancy-tag writes, each with its board item and next meeting. No checkbox.
   - **For a person (1):** "Unit 12: enter the mailing address in PayHOA", with a link to the owner in PayHOA.
   - **Test accounts left out (1).**
   - Cost: "No cost: tag writes and a status change."
5. **Read the rule behind the default.** [Approvals → Governing documents] Jane opens **recite** on a mail-tag write. The recitation of Civil Code 4040(a)(2) shows, then jason's reading of it, labeled. She returns to the approval with focus on the row she left.
6. **Approve some.** [Approvals] Jane approves the groups for Units 12 and 15, and Unit 14's mail-tag write. For Unit 21 she rejects the email-tag write with the reason "owner called; wants mail too, will re-answer". The completion under Unit 21 now shows "Will stay open: a write it needs was rejected."
7. **Hold the board items.** [Approvals] The two writes jason held are not hers to decide; she opens the board item from the held banner to check it is on the Oct 15 agenda [Meetings & minutes]. One more write, Unit 14's unit tag, is allowed by the rules but touches a question the board raised last month; she presses **Hold for the board** on it with the reason "board asked to see unit-tag changes first". On submit the hold is recorded and the row reads "held for the board by Jane Example", with the `jason board` command that proposes its board item for the agenda (automatic once the engine proposes it).
8. **Submit.** [Approvals] The approve bar reads "Approve 8 of 10 changes as Jane Example" (1 rejected, 1 held by her). The name is pre-filled; she submits. The status becomes **partially approved**. The audit log records each item's decision and the submission with fingerprint `3f9a02c1d4e7`.
9. **Apply.** [Approvals] With jason-web started with `--allow-apply`, Jane presses **Apply 8 changes now**; without it, she runs the command the page shows, `jason approvals apply apr-… --yes --by "Jane Example"`. Either way the engine:
   - takes the store lock and the PayHOA lock;
   - re-plans on a fresh live read;
   - compares each approved item's basis. All match;
   - writes the 8 tags, logging each intent and result;
   - runs the completion check with the rejected and held writes as pending. Unit 15's request has nothing left, so it is completed with the board's comment, which PayHOA emails to the owner. Unit 12's stays open until a person enters the mailing address; Unit 14's and Unit 21's stay open too.
10. **Read the result.** [Approvals] The result panel: "Applied 8 of 8 writes. Completed 1 request; the owner was emailed the board's comment. 3 requests stay open: Unit 12 (a person enters the mailing address), Unit 14 (a write held for the board), Unit 21 (a write was rejected)." Skipped: "3 held for the board · 1 rejected · 1 for a person". The status is **applied**.
11. **Do the person's task.** [PayHOA, outside the console] Jane enters Unit 12's mailing address in PayHOA. The next plan finds nothing left for Unit 12 and offers its request's completion, which Jane approves like any other item.

**If the live state moved.** At step 9, if Unit 14's owner had submitted a new answer since the review, the re-plan's basis for Unit 14 differs. Nothing is written. The approval becomes **superseded**; a new one opens with Unit 14's items marked "changed since review" and the earlier decisions shown as hints. Jane reviews Unit 14 again, submits, and applies.

**What makes it safe to stop.** Each step before 9 changes only the approvals store. Closing the browser at any point loses nothing; the approval waits in the queue.

## (b) A second person confirms a high-stakes onboarding answer

The question "Which version of the declaration is in force?" decides the words jason recites everywhere. Jordan Example answers it; Casey Sample confirms.

1. **The question surfaces.** [Today] Next questions: "Which version of the declaration is in force? Unblocks: 2 clocks, gate establish." Marked high stakes.
2. **Answer.** [Onboarding] Jordan opens the question card. The evidence: two recorded instruments in the library and a restated text. jason's suggestion is marked, not selected. Jordan picks "the restated declaration of 2090, with Amendment 2", and saves as Jordan Example. (`jason onboard --answer ID 2 --by "Jordan Example"`.)
3. **jason says what happens next.** [Onboarding] "Saved. A high-stakes answer is applied only after a second person confirms it." The question moves to **Waiting on a second person**. The nav's Onboarding count gains one.
4. **Jordan tries to confirm.** [Onboarding] The confirm panel is shown to Jordan with "You gave this answer, so you cannot confirm it." If the name field is filled with "jordan example " anyway, the server refuses: "Jordan Example gave this answer, so Jordan Example cannot confirm it. A second person confirms."
5. **The second person reads first.** [Onboarding → Governing documents → Records & library] Casey opens the question, reads the evidence chips (the recorded instruments, the restated text's recitation), and compares the restated text with the amendment in a diff.
6. **Confirm.** [Onboarding] Casey types "Casey Sample" (the field starts empty: retyping is the point of this step) and presses **Confirm the answer**. The panel shows both people, with times: answered by Jordan Example, confirmed by Casey Sample.
7. **Apply.** [Terminal] The answered-not-applied count shows the command: `jason onboard --apply`. The manager runs it; the answer becomes a record, and the living document is rebuilt on the confirmed base.
8. **If the answer changes later.** [Onboarding] A new answer clears the confirmation. The question returns to waiting, with "The answer changed, so the earlier confirmation no longer applies."

## (c) The Secretary prepares a meeting

Sam Placeholder, the Secretary, prepares the Oct 7 board meeting and, after it, the minutes.

1. **The notice clock.** [Today → Meetings & minutes] Today shows "[LEGAL] Notice of the Oct 7 meeting: 4 days left (Civil Code 4920)". On the watch, the Oct 7 row: notice by Oct 3, "none on record yet", owned by the Secretary's assignment, due Oct 3.
2. **Read what the notice requires.** [Notices → the catalog] The board-meeting requirement, recited: recipients, methods, the clock, the content, and the governing documents' clauses, each with jason's reading labeled apart. The stricter clock governs.
3. **The agenda.** [Plan a meeting, `#/agenda`] Jane Example chooses the items, their order, and the motions; jason reports only computed checks. The notice is a letter drafted into Approvals, and Sam, the Secretary, approves its words there. Writing the agenda Doc is a `jason board` command a person runs.
4. **Post the notice.** [Outside the console] Sam posts the agenda and notice where the association posts general notices, and the individual notices go out to the members who asked for them, through the commands that guard each send. Sam records where the send was logged on the letter.
5. **Record the posting.** [Meetings & minutes] On the Oct 7 notice clock, **Record a posting**. Sam fills "where and when" ("Posted on the clubhouse board, Oct 2, 9:00") and the name (pre-filled), and saves. The clock now reads "on record in time". (`jason notices board-meeting-2099-10-07 --mark-general --posted "..." --by "Sam Placeholder"`.)
6. **After the meeting: the minutes clock.** [Meetings & minutes] The watch shows the minutes due Nov 6 under Civil Code 4950(a), "none on record yet".
7. **Draft the minutes.** [Meetings & minutes] After `jason meetings --sync` brings in the Zoom record, Sam runs `jason board --minutes 2099-10-07`, the command the page shows. The local model runs preflight, takes the GPU lock, and drafts from the open session only. The draft opens with "DRAFT", every line for the Secretary to check.
8. **Read the checks.** [Meetings & minutes] Beside the draft, under "jason's checks":
   - "Quorum: the record shows 3 of 5 directors in office on the call…; a quorum is 3. Standing: present."
   - "1 line(s) name a subject the open minutes give only by its general nature (Civil Code 4935): read each before the draft is shared…" with a link to the line.
   - "Blanks left for the Secretary: 5."
9. **Fill the blanks.** [Outside the console] Sam edits the draft in the association's minutes Doc from memory and the recording, fills each "unknown", and rewrites the flagged line in general terms. Back in the console, **Re-check** runs the checks again without the model: "0 lines name a confidential subject."
10. **Make the draft available.** [Outside the console, then Meetings & minutes] Sam makes the draft minutes available to members, marked DRAFT, and records it: **Record the minutes made available**, with the evidence "Draft minutes posted to the owners' portal, Oct 20". The minutes clock reads "on record in time".
11. **The board approves the minutes.** [Next meeting, outside the console] The board approves the Oct 7 minutes at its November meeting. jason never approves minutes.
12. **The approval reaches the record.** [Meetings & minutes] After the November minutes are on file and the catalog is rebuilt, the Oct 7 meeting's stages show "approved: stated in the minutes of Nov 18". If the November agenda only listed the approval with no words saying it passed, it shows "listed, not stated".

## (d) A board member asks "what does the rule say?"

Riley Test, a director, wants to know whether an owner may rent a unit for two weeks.

1. **Ask.** [Governing documents] In the cite box Riley types "Declaration 7.3" and presses **Cite**. (`jason cite "Declaration 7.3"`.)
2. **The words first.** [Governing documents] The recitation: "Section 7.3. Leasing. An Owner may lease…", the words whole, with the passage that answers the question marked; the citation; "as amended Mar 12, 2097, on Oct 3, 2099"; and the caveat "jason's consolidated text, not an official restatement. The recorded instrument governs."
3. **The defined terms.** [Governing documents] "Owner" and "Unit" link to their definitions, each recited from its own section, under "the document's definition governs the word here (Civil Code 1644)".
4. **The readings, labeled apart.** [Governing documents] Below, in the readings band:
   - "The board's reading · adopted Jun 10, 2098": "thirty (30) days" is calendar days from the start of the lease.
   - "jason's reading": a two-week rental is under the minimum. "A reading, not legal advice. The words above govern."
   Riley can see at a glance which words are the document's, which are the board's, and which are jason's.
5. **In force when?** [Governing documents] Riley sets **As of** to a date before the 2097 amendment. The earlier words show, with "These are not the words in force on Oct 3, 2099" and a link to today's.
6. **Who relies on it?** [Governing documents] **Cited by** lists the rules section that repeats it, a conflict row, and the schedule's rental review, each with how the cited words stand now.
7. **A conflict?** [Governing documents] The conflict row: the provision, the statute above it with the day it took effect, the part that yields, how it is applied meanwhile, and "for counsel". The caveat: "jason notes a conflict; only the board, counsel, or an amendment resolves one."
8. **Take it to the meeting.** [Governing documents] **Copy the words with citation** copies the recitation and the caveat together, never the words alone.

## (e) A notice bounces

The owner-information notice went out by email and mail. Two emails bounced.

1. **The sync.** [Notices] Jane runs the sync the page shows, `jason notices owner-info-2099 --sync`. It reads PayHOA's communications log and writes only jason's ledger.
2. **The follow-ups owed.** [Today, Notices] Today shows "[LEGAL] owner-info-2099: 2 owed a resend by law (CIV 4041(e)); 46 of 48 reached". On the notice's page, band 4 (Delivery): "Owed: 2 members, resend by first-class mail [required; CIV 4041(e), 4040(a)(2)]". Counts only.
3. **Who.** [Notices] With the private view on (reason: "resend the bounced notices"), the member rows show the two units and their attempts: "email bounced". No names or addresses.
4. **The requirement.** [Notices] Band 1 recites 4041(e)'s words, so the resend's reason is the law's words, not jason's.
5. **Plan the resend.** [Notices → Approvals] **Plan a resend** plans `payhoa.owner-info.mail-batch` for the two units with `--resend`. The approval shows two letters, the PDF's sha256, the recipients by unit, and the cost: "2 letters · 4 pages each · $4.08 estimated, charged to the association". Approver: two people.
6. **First signature.** [Approvals] Jane approves both and submits: "Approve 2 of 2 letters as Jane Example". Status: approved, waiting on a second person.
7. **Second signature.** [Today → Approvals] Casey Sample sees "Waiting on you as second person". Casey reads the letters, the recipients, and the cost, and confirms. A confirm by Jane is refused.
8. **Apply, with no undo.** [Approvals] Jane presses Apply. Because a letter cannot be recalled, apply asks her to type the count: "This mails 2 letters and charges the association $4.08. A letter cannot be recalled once it is mailed. Type 2 to apply." The re-plan reads the recipients and addresses again; they match. The batch sends.
9. **The result.** [Approvals] "Mailed 2 letters." Each letter's communication id is in `data/mailroom/sent.jsonl` and the batch ledger; the audit log links them.
10. **The ledger catches up.** [Notices] The next sync reads the resend's batch, named with the same key. Band 4: "48 of 48 reached." The digest line clears.

**If an address is bad.** A letter that comes back shows as "returned": delivered on deposit (4050(b)), but the member is asked for an address. That ask is a message, a task for a person until a message kind exists.

## (f) Onboarding a new association from an empty profile

A manager takes on Example Village HOA, which jason has never served.

1. **Write the profile package.** [Terminal] `jason onboard --new example-village --name "Example Village HOA" --county "Example County"`. jason writes a `Community` subclass from its templates, empty rule-row modules, and an empty private-facts file `data/spec/example-village.json`. It refuses a key that collides with anything. The console does not do this step: it writes source files, which a person reviews and commits.
2. **Point jason at it.** [Terminal] Set `JASON_PROFILE=example-village` and start the console: `jason-web`, then open `http://127.0.0.1:8080`. The portal (`#/communities`) shows the new profile as active.
3. **The empty state.** [Today] Every digest section is unavailable. Today shows one panel: "jason has no stores for this profile yet. Start with Onboarding."
4. **The first gate.** [Onboarding] The stepper: start is open. Progress: every item missing. The next questions are FACT questions: the association's legal name as recorded, its fiscal year, its bank, the board's members. Each says where its answer goes.
5. **Public records.** [Onboarding] **Look up public records** runs a read-only search of the county recorder's index for the association's name. Each find becomes a FACT question with the found value as its suggestion, marked as a lead.
6. **Answer the facts.** [Onboarding] The manager answers, signed. A bank signers answer is high stakes and waits for a second person. A password typed by mistake is refused: "This looks like a secret: it gives a password. Put it in Keeper, and answer with the Keeper record's name."
7. **Take in the documents.** [Records & library] `jason ingest` with the prior manager's zip, the command the page shows. It inventories, reads, classifies, and finds versions. The report: files, duplicates, kinds, proposed books and folders, and the questions. **Park the questions**, answer the ones that need a kind or a folder [Onboarding], then **Plan: copy into the library**, which a person approves [Approvals].
8. **Map the books.** [Onboarding] MAP questions ask which document fills each book ("No document is mapped to the Declaration…") and which folder holds each 5200 record. Each answer becomes a proposed change to the profile.
9. **Apply.** [Terminal] `jason onboard --apply` merges private facts (with a backup and a diff) and writes profile proposals as patches under `data/onboarding/proposals/`. [Onboarding] The proposals show, read-only.
10. **Apply the proposals.** [Terminal] A person reads each patch and applies it with `git apply`, then commits. jason never changes the profile itself.
11. **The gates open.** [Onboarding] As items turn present and questions are answered, `StageSteps` shows each gate open in turn: start, ingest, establish, operate, adopt. A gate is jason's reading; the board decides what is done.
12. **Operating.** [Today] With every gate open, the onboarding session shrinks to one line, and Today shows the digest.

## What the journeys found

Gaps in the specs or the code. The open ones are also in [mvp.md](mvp.md#open-decisions):
- **(a)** Two kinds of "held" meet on one screen: the planner's held class and a person's hold decision. The words keep them apart ("held for the board" against "held for the board by NAME"); a usability test should confirm people read the difference.
- **(c)** Recording a posting writes `notice_ledger.set_general` or `record_completion`, neither of which is an action kind. As built, the engine has no signed kind: a signed `data/` record stays the task's own write with `by` ([approval-workflow.md](approval-workflow.md#8-the-action-kind-registry)).
- **(e)** Asking a member for an address after a returned letter has no message kind.
- **(b), (f)** `jason onboard --apply` stays in the terminal. Whether the console offers it is open.
- **Requests** `jason request-comment` posts a comment that PayHOA emails to the owner, with no dry run or `--yes` (lesson `google-writes-without-yes`). The console does not offer it until it has a gate.
- **(a)** A person's hold is recorded by the engine, but proposing its board item is not yet automatic; until it is, the page shows the `jason board` command that proposes it.
