# Design brief: members' requests (`#/requests`) and the onboarding session, each as a run in Work

One page of orientation for the design agent, for two specs: [screens/requests.md](screens/requests.md) (members' requests, their clocks, and the `jason respond` family) and [screens/onboarding.md](screens/onboarding.md) (the onboarding session, its five gates, and the change-of-manager branch), plus how each is a long run in [screens/work.md](screens/work.md). It does not repeat the specs; it says what to read in what order, each screen and component to draw, what is built and what has no view, and a made-up community to draw against. Where this page and a spec disagree, the spec's "Checked against the code" notes in section G win and this page is corrected.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, or private fact; made-up samples only ("123 Main St", "Example County", "Example Alarm").

## A. The idea, and the rules that run through it

**The idea, in seven sentences.**

1. A member's request (architectural, records, maintenance, a question) arrives in PayHOA or by email and starts a clock. The Requests screen answers one question: **which clock runs on each request, who set it, and what is the next step?**
2. A clock has an author: the law, the governing documents, or a **proposed policy** (the law and the documents are silent, and the board has not adopted a number). The screen says which, in words, on every date.
3. jason computes the clock and drafts the first words. A person answers, and the board decides what is reserved to it. **jason never approves, denies, or assigns a request**, and the screen has no such control.
4. Onboarding takes an association on. Its screen answers: **which gate is closed, what does it wait on, and which question, once answered, opens the most?** A gate is jason's reading of the checklist, never a button.
5. An onboarding answer is a person's, signed with a name. A high-stakes answer (which text is in force, whether an instrument was recorded, the bank signers) waits for a **second, different person** before a third person applies it at a terminal.
6. Both are long tasks. In Work each is a run: `respond-request` (one run per request, 21 steps, a path chosen by kind) and `onboard` (one run per association, 35 steps in five gate phases, plus a change-of-manager branch). The Work run page is the rail; these two screens are the step panels' destinations.
7. Everything on these screens is a lead, a reading, or a person's record. Nothing sends, files, mails, posts, or completes a request from here.

**The rules** (each is in a spec; a screen that breaks one is wrong):

- **Directors and officers have the same access to information** (the board's decision of 2026-10-11). There is **no director-only or counts-only view**. The server decides what a viewer's office opens (P0 to P3) and the page renders it. The specs' older lines that list a role as "no access" or a director as "counts" are superseded: see decision F9.
- **A response clock is the law's or the documents' words, recited.** The operative words come first, whole, with the version in force and the caveat that jason's text is not an official restatement (`Recitation`); jason's reading follows in a `ReadingLabel`. A clock that comes from policy is labeled **"proposed, not the law's"** wherever it shows, ranks after a statute's or the documents' clock, and gives the owner no date.
- **A made-up due day is never drawn.** A kind with no rule is "open, no clock", with "No rule sets a clock for this kind. If one should, it is a proposal for the board." A business-day clock skips weekends and not holidays, so the day shown is the earliest it can fall, and the screen says so beside it.
- **A reading is evidence until a person confirms it.** A kind read from an email subject says "Read from the subject; check it". A suggested answer is "jason's suggestion", never pre-selected. A located document is "a lead, not a pin".
- **No owner contact detail or answer in a list.** Unit label, kind, and role only. An emailed request's sender is a name; the address is P2, masked, one field revealed, logged. A request's title can name a person, so it is held from the treasurer except on money kinds. An onboarding answer's value is never shown again once recorded, except to the one who gave it or is confirming it.
- **Executive-session kinds** (payment plan, hearing request, internal dispute, ADR) are counted and listed by their general words only outside the private view.
- **State is a word and a glyph, never colour alone.** Standing words are the code's own: "answered on time", "answered late (N days)", "answered", "OVERDUE (N days)", "due soon" (within five days), "open", "open, no clock".
- **Every count says how old its source is.** "Synced Oct 3, 06:00" for the PayHOA catalog. A zero beside an old check is "Nothing new as of Oct 3", never a bare zero.
- **The owner view never sees these screens.** Neither loader is in `OWNER_SOURCES`. An owner asks for records through `#/records-requests?view=owner`, as built.
- **jason proposes; the board adopts.** Where no rule answers a request, the finding goes to the board's canvas, not into a guess ("Where the law is silent, write it down").

## B. Reading order

1. [screens/requests.md](screens/requests.md) and [screens/onboarding.md](screens/onboarding.md), whole.
2. This page's section D (components) beside section H (the sample).
3. [workflows/members-cycles.md](../workflows/members-cycles.md) section 2.4 (`respond-sweep`, `respond-request`, `respond-policy`), 4 (the clocks and their basis) and 5.3 (the request run drawn); [workflows/documents-records.md](../workflows/documents-records.md) section 2.4 (`onboard`, the ST/IN/ES/OP/AD/CM steps) and 9 (a sample run).
4. [design-brief-work.md](design-brief-work.md) for `RunRow`, `WorkflowRail`, `RunStepPanel`, `ClockStrip`, `BasisPill`: this page uses them and does not redraw them.
5. [handoff-responses.md](handoff-responses.md) (the arrivals lane and `ScanReview`), [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) and [handoff-followups.md](handoff-followups.md) (the cycle's funnel and follow-ups), [handoff-held-setup-roster.md](handoff-held-setup-roster.md) (`GateRail`, `PendingAnswer`, `HeldRow`), [handoff-directory-consent.md](handoff-directory-consent.md) (one onboarding checklist item).
6. [../response-standards-design.md](../response-standards-design.md) for the standard each kind's rule row is part of; [../onboarding.md](../onboarding.md) for the gates, the checks, and the conversation prompts.

## C. The screens

### C1. Requests: the list (`#/requests`, Overview group)

A table over `member-requests`: `#`, kind, unit, received, **clock** (length, its basis word, a `BasisPill`), due, standing, next (the rule's first step, with its owner role). Sorted as the loader sorts: open first, then by due day, the sooner the higher; a policy clock sorts after a statute's within one urgency. Heading line: "14 open: 2 overdue, 3 due soon, 9 open · last 12 months: 41 answered, 37 on time" with `AgeStamp` ("Synced Oct 3, 06:00") and the command `jason respond` with Copy. Filters: kind, standing, owner (a role). Below the table, verbatim: "Email kinds come from subjects; a proposed clock is a target until the board adopts it." Below that, "Emailed requests not in PayHOA (2)": subject in quotes, sender name, likely request, and the command that enters it (the Drafts screen's). A band for held kinds: "3 executive-session matters" with the `PrivateGate`. Draw loading, "Requests are unavailable: no PayHOA requests on disk. Run `jason sync-catalog`", "No open requests. 41 answered in the last 12 months, 37 on time", a filter that matches nothing, and 40 rows.

### C2. One request (`#/requests?id=`)

Top to bottom, six bands. **Title row:** id, kind (with "Read from the subject; check it" when `classifiedBy` says so), unit, standing. **The clock:** received, due with days left, the basis, "Set by: the governing documents · owner: the board"; then the `Recitation` of the rule's authority, then a `ReadingLabel` ("jason's reading: the 45 days run from the day the request was received"); a business-day clock adds "no holiday subtracted: the earliest this day can fall". **The response standard that applies:** the kind's rule row as a card (kind, clock and its source, authority, business or calendar days, owning assignment, first step, acknowledgment target, note) with its adoption word: a statute's row reads "the law's"; a documents row names its section; a policy row reads **"proposed, not the law's"**. **PayHOA's fields beside jason's:** PayHOA's own due date and tags shown next to the computed due day, never replacing it. **Where the answer is written (leads):** passages, library files by name, precedents (unit and kind only), with the caveat verbatim: "Each source is a lead to read, not a ruling; a precedent shows past handling, not this matter's facts." **The acknowledgment draft:** exactly the loader's `draft` text, unedited, labeled "for a person to read and send", with Copy and the sentence "Send it from PayHOA, on the request's page" (or the Gmail-draft command for an emailed one). Also a **timeline** (`Clock`/`Timeline`): received, acknowledged, due, answered, closed, each dated and each with who set it. And a **Work link**: "Run: respond-request (step 6 of 21)" when the run exists.

States to draw: no clock (kind `question`); a policy clock not adopted (the draft gives no date); already acknowledged ("Acknowledged Sep 3", no draft); overdue on a statute clock (the clock's words recited, "Past the date: 7 days", the follow-up it opened); a kind read wrongly (a person's reclassification is a later entry, the old kind stays in the history); a records request (a link to `#/records-requests`, which keeps its own stages); an executive-session kind (held).

**The response inbox lane, linked.** A request that is a **campaign's owner-information request** has a second life as a form that owners answer in four ways ([handoff-responses.md](handoff-responses.md)). Where the page's subject is such a request, a `ResponseLaneLink` shows "47 of 107 answered · 3 new · checked 2 h ago" (counts with their age, never a bare zero), links to the arrivals lane and the funnel, and names the campaign. It is a link, not an embed: the arrivals lane, `ScanReview`, and the funnel are their own screens. **Word hazard:** "request" means two things here, a member's request that comes in (this screen) and the request jason sends out (the campaign). Use "member request" and "the owner-information request" in full, never "request" alone in a heading (decision F2).

### C3. Onboarding: the session (the Setup tab of `#/onboarding`)

Built; draw it as built, then add what is missing. Top: the title, then `StageSteps` for the five gates (start, ingest, establish, operate, adopt), each "Gate open" or "Gate closed" with what it waits on in words (items by name with their status, and "2 questions"), `aria-current="step"` on the stage being worked; the caveat "A gate is jason's reading of the checklist; the board decides what is done." Then progress (present, partial, missing; by group). Then **"Waiting on a second person"** (each: the question, who answered and when, never the value unless the viewer gave it or is the second person; "Your full name" and the refusal for the same name: "Jordan Example gave this answer, so Jordan Example cannot confirm it. A second person confirms."). Then **Next questions** in the loader's order, each a `QuestionCard`: kind (FACT, MAP, the intake kinds) and "high stakes"; the question; **what answering unblocks** (checklist items, gates, records, legal clocks, sections: "Unblocks: checklist 'bank signers' (missing) · gate establish · 1 clock"); the evidence (a lead from the library, labeled a lead); the choices numbered, jason's suggestion marked "suggested" and **never pre-selected**; **where the answer goes** (the three sentences: private facts; a proposed change for a person to apply; only a Keeper record's name); "Answered by NAME"; Save. A connection item shows its terminal command and no field. A standing question (a change of office, a term) is marked "standing". Then **Answered, not yet applied** with `jason onboard --apply` and Copy, then **Proposals** (patch files a person applies with `git apply`; jason never changes the profile). When every gate is open the whole top shrinks to "Every stage gate is open. The association is operating."

Neighbours, linked and not redrawn: **Find the association** (the county directory, the located documents, "a lead, not a pin"; its located items become FACT questions here), Key documents, Recorded instruments, the Request list, and the directory-consent checklist item ("4 of 7 seats answered", status jason's reading).

**Second-person confirmation, as a flow.** Draw four states of one high-stakes answer: (1) answered by A, `Seal` "waiting on a second person"; (2) the viewer is A: no confirm control, "You gave this answer, so someone else confirms it"; (3) the viewer is B: `Confirm` "Confirm A's answer to ID as B, the second person. Nothing is applied until a person runs `jason onboard --apply`."; (4) confirmed, waiting to be applied. A new answer after a confirmation clears it, and the question returns to state 1 with "The answer changed, so the earlier confirmation no longer applies." A secret-like answer is refused with the reason, and the field is cleared.

### C4. The change-of-manager branch

**Not in [screens/onboarding.md](screens/onboarding.md); only in the `onboard` workflow** (steps CM-1 to CM-4) and the SOP's steps 18 and 19. Draw it as a band of the onboarding run, shown only when the run's first fork is "change of manager" (a new association skips it, with the step reading `skipped: new association`). Four steps: **CM-1** read the outgoing agreement (its term, its non-renewal and termination clauses, what it owes at transition) with **both edges of each notice window** written down before any notice goes ("earliest Sep 2, latest Nov 1; basis: the agreement"); **CM-2** the board decides whether to give notice (a `decision` step: the motion, mover, second, each director's vote by name, recusals, outcome, read from the decision record, with **no vote control**; "added by the workflow design", since the SOP assumes the decision); **CM-3** send the notice by the delivery the clause names and keep proof (a person's step); **CM-4** before the termination date: request the records, confirm the board's portal access, tell each vendor (three person dates; **no law clock**: the stored statutes name no handover deadline). The agreement's windows are **documents**-basis dates, never `law`. The transition's request list is the existing Request list tab.

### C5. Each as a run in Work

Use [design-brief-work.md](design-brief-work.md)'s list, rail, and step panels. What these two add:

- **`respond-request/ID`.** The rail runs RQ-01 to RQ-22 (21 steps; RQ-09 is not defined) grouped as classify, answer, decide, close. The path chosen at RQ-08 shows; the other branches grey as "not applicable". A `decision` step (RQ-16 the board decides; RQ-04 no rule sets a clock) shows the motion and the record and **no approve control**. A `person` step (RQ-07 send it) shows the acknowledgment text to copy and the `Command`; it is done when a person says so. RQ-21 (waiting on the member) pauses the run, and **only a policy clock pauses**: a pause on a statute or documents clock is refused unless the cited words allow it (the control reads as refused, with the sentence). The clocks strip is C2's clock band.
- **`respond-sweep`.** A weekly run whose RQ-02 opens one `respond-request` per request id (idempotent). On Work it is one row; its children show in the links band.
- **`onboard/<profile>`.** 35 steps in five gate phases (ST-1 to ST-7 start, IN-1 to IN-7 ingest, ES-1 to ES-7 establish, with ES-3b, OP-1 to OP-4 operate, AD-1 to AD-5 adopt) plus CM-1 to CM-4. Each gate row is a `check` whose result is the gate computed now; **a done gate that closes again reopens with a "changed since" line**, and no step passes a gate. Child runs (`ingest`, `record-slot`, `document-intake`, `founding-documents`) are one row each that links; a child never completes its parent's step. Terminal-only steps (ES-5 apply, ES-6 `git apply`) show the `Command` and a "Done in a terminal" attestation. ES-3 opens the question card in place; ES-4 is the second-person step and shows who may and who may not. The clocks strip for the run: "Prior manager's first date, Oct 15 (person)"; **no legal clock runs**, and the strip says so.
- **The Work row for each.** "Request 2099-1050 · records · Step 9 of 21: record the member's agreement to the cost", due, `BasisPill` `law`, "Waiting on the member". "Onboarding: Oakview · Step 20 of 35: a second person confirms", `person`, "Yours" for B and "Waiting on others" for A.

## D. The shared components, each once

Reuse (built): `StageSteps`, `QuestionCard`, `SecondConfirm`, `Confirm`, `Command`, `Evidence`, `Seal`, `Pill`, `Badge`, `Clock`, `Timeline`, `DueDate`, `Recitation`, `ReadingLabel`, `Caveats`, `DataTable`, `Tabs`, `Card`, `Stat`, `RemoteView`, `HeldNote`, `Glyph`, `StandingPill` (it is for citations, not request standing: do not reuse its words). Specified, not built (draw from the built parts and say so): `TerminalStep`, `AgeStamp`, `GateRail`, `PendingAnswer`, `HeldRow`, `PrivateGate`, `BasisPill`, `ChannelMark`.

| Component | What it is | Data (real field names) | States |
|---|---|---|---|
| `RequestRow` | One row of C1 | `id, kind, unit, title, received, due, clock, clockSource, owner, acknowledged, answered, closed, standing, next, classifiedBy` | each standing word; held kind; email vs PayHOA; kind read from a subject |
| `StandingWord` | Standing as a word and a glyph | `standing` (the code's strings) | the seven words; an unknown word shown plainly |
| `RequestClock` | C2's clock band | `clock, clockSource, due, rule.authority`, a recitation, a reading | statute; documents; policy (proposed); none; business-day note; past |
| `ResponseStandardCard` | The rule row that applies | a `ResponseRule`: `kind, source, authority, days, business_days, assignment, first_step, acknowledge_days, note` | the law's; a documents clause; proposed; none. `adoption`, `adopted`, `pauses` are **designed, not built**: draw them as absent, not as "unadopted" |
| `LeadList` | Where the answer is written | `sources{passages, files, precedents}` | none; some; precedent held to unit and kind; the verbatim caveat |
| `AckDraft` | The acknowledgment | `draft, send, acknowledged` | draft (no date for a policy clock); already acknowledged; email (Gmail-draft command) |
| `ResponseLaneLink` | Counts of a campaign's arrivals, aged | `new_responses.inbox, checked, outstanding_responses` | fresh; stale; never checked; no campaign |
| `SessionHeader` | The gates and progress | `title, progress, groups[], stage, gates[]{stage,title,open,opensWhen,waiting[],checks[]}, questions{open,byKind,answeredNotApplied}` | one gate closed; all open; the session cannot be built (the error and "Check the profile with `jason spec`") |
| `NextQuestions` | The ranked list | `next[]{id,kind,subject,question,choices,suggestion,evidence,unblocks,highStakes,standing,connect,serves}` | new vs queued; connect item; secret refused; no questions |
| `SecondPersonFlow` | The four states of C3 | `intake_questions(awaiting_confirmation)`: `answeredBy, answeredAt, confirmedBy, highStakes` | the four states; refused same name; cleared on a new answer |
| `ProposalsBand` | Patch files awaiting a person | `data/onboarding/proposals/` | none; some. Read-only; **not built** |
| `ChangeOfManagerBand` | C4 | the workflow's CM steps | not applicable; each step's state; a window with both edges |
| `WindowEdges` | A notice window's two dates | two dates, basis `documents`, the clause | both written; one missing (blocks CM-3) |

**Fixed words** (use exactly): "proposed, not the law's", "open, no clock", "for a person to read and send", "Read from the subject; check it", "Each source is a lead to read, not a ruling", "A gate is jason's reading of the checklist; the board decides what is done", "jason's suggestion", "suggested", "high stakes", "waiting on a second person", "A second person confirms", "Unblocks", "Answered, waiting to be applied", "Waiting on the NAME/OFFICE", "Review in Approvals", "Record in Decisions".

## E. Glyphs

Use the console's existing glyphs: `clock`, `hourglass`, `triangle-alert`, `check`/`circle-check`, `lock`, `user`, `circle-dashed` (not yet checked), `circle-question-mark` (unknown kind), `scroll-text`/`book-open` (a recitation), `scale` (the law), `proposal` (a proposed clock), `cosign` (the second person), `exec-session` and `held-proposed` (held), `notice`, `board`, `key` (a connection item), `list-checks` (the checklist). New ones only where none can say it, each named for the idea: *a clock authored by the documents* (against the law's `scale` and a proposal's `proposal`); *no clock* (a dashed circle with no hands); *a gate* (open and closed, a latch, not a lock, since `lock` means held); *a branch not taken* (a struck arrow). One glyph, one meaning: a gate that is closed is not a held item.

## F. Decisions that are the design's, in one list

1. **Requests list and a request page: two routes or a master and detail pane** on a wide screen (recommended: a right panel, as for an arrival, since the clock and the draft need the room).
2. **How "request" is told apart** from the owner-information request (the campaign); the words in headings, the link text, and the Work row.
3. **How the clock block is ordered** when a request has both PayHOA's due date and jason's (recommended: jason's first, PayHOA's labeled beside it, a difference flagged in words).
4. **How a proposed clock looks** at a glance without colour: the `proposal` glyph and "proposed, not the law's" in text; a statute's reads "the law's".
5. **Standing filter default:** open, ordered as the loader sends it.
6. **How the gates show on a phone:** the five stages as a vertical list with the closed one open (recommended), versus a stepper.
7. **Where "unblocks" sits** on a question card: above the question (recommended, since it is why the question ranks) or below.
8. **How the second-person flow reads to the answerer:** the absent control with its sentence (recommended), versus a disabled button.
9. **Roles on the requests spec** (see section G, last row): draw the screen as the same for officers and directors, with the server deciding the level.
10. **The branch band:** a band of the onboarding run shown only for a change of manager (recommended), versus a fork at "Start a run".
11. **Print:** the acknowledgment draft and a request's clock band as a letterhead-free page for the board's packet.

These are not the design's: the board's numbers where the law is silent (acknowledge in how many days, how long to answer a maintenance request); the membership-list clock (counsel reads 5210(b)(6) with Corporations Code 8330); whether a pause stops a clock; whether `onboard` closes on a person's attestation (AD-5) or only when the five gates read open; whether a change-of-manager decision step belongs in the definition.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Requests list, one request, clock band, leads, acknowledgment draft | **Draw from section H.** Data is built: `jason respond`, MCP `member_requests` and `acknowledgment_draft` over `responses.handle`; `member_requests` has `sources`. | The loader `member-requests` and the view: **neither exists** (no key in `web/sources.py`, no `requests` in `SCREENS`) |
| Emailed requests PayHOA lacks | Built: `request-links` loader, `DraftsView`, `InboxView` (PayHOA requests pending) | Joining them into the Requests band |
| Records requests | Built: `records-requests` loader and writer, `RecordsRequestsView`, owner view | Joining it to the PayHOA request it duplicates (two records of one request) |
| Response standard card | Draw the rule row as built (10 fields) | `adoption`, `adopted`, `pauses`, `member_words`, `--standards`, `--metrics`, `--overdue`, the Service screen: design only |
| Acknowledgment sent | A copy-and-command only | `jason request-comment` has no dry run and no `--yes`, and no approvals kind (`acknowledgment` case of `gmail-drafts`, `payhoa-request-create`) |
| The arrivals lane a request links to | Loaders built: `responses`, `response`, `outstanding-responses`, `campaign-status`, `followups` | **No view reads any of them**; `ResponseLaneLink` links to a screen that does not exist yet |
| Onboarding Setup tab | **Built** (`OnboardingSetup.tsx`; `GET /api/onboarding-session`; write `POST /api/write/intake/<id>` takes `by`) | The proposals band; the "waiting on a second person" band as its own card (the build folds it into "Answered, waiting to be applied"); applying in the console (terminal only) |
| Find the association, key documents, recorded instruments, request list | Built tabs | `FindAssociation` passes no `questionHref`: its third card shows `jason onboard --questions` |
| Change of manager | Draw from the workflow (C4) | Nothing is built: no screen, no loader; the SOP steps exist (`jason sop onboard`); CM-2 is added by the workflow design |
| Work runs (`respond-request`, `respond-sweep`, `onboard`) | Draw from section H | `jason.workflows` is a pure library (types, store, fold, resume, step kinds, `validate`); **no definition is registered** for these, and there are no `work`, `work-run` loaders or `#/work` view |
| Roles | The server's `access.SEE_RULES` | [screens/requests.md](screens/requests.md) says "Secretary, reviewer, counsel: no access" and a director reads board kinds only; that predates 2026-10-11 and is to be corrected |

## H. A made-up community to design against

"Oakview" (dates plainly made up; today is Oct 11, 2099; the loaders send ISO dates).

**Requests** (the list; open unless noted):

| # | Kind | Unit | Received | Clock | Basis | Due | Standing | Next | The point it makes |
|---|---|---|---|---|---|---|---|---|---|
| 2099-1042 | architectural application | 123 Main St | Sep 1 | 45 days | documents | Oct 16 | due soon | the board | The documents' clock, recited; the board decides; no approve control |
| 2099-1050 | records request | 456 Oak Ln | Sep 20 | 10 business days | statute | Oct 4 | OVERDUE (7 days) | send | A recited clock (5210(b)(1) "within 10 business days following the association's receipt of the request"), earliest-day note, link to records requests |
| email:EX1 | maintenance request | (not found) | Sep 12 | 5 days | proposed policy | Sep 17 | OVERDUE (24 days) | acknowledge | **Proposed, not the law's**; read from the subject; no date in the draft |
| 2099-1055 | question | 789 Elm Ct | Oct 8 | none | none | none | open, no clock | answer | "No rule sets a clock"; a finding for the board |
| 2099-1031 | solar application | 12 Example Ct | Aug 2 | the statute's | statute | Sep 1 | answered on time | none | Closed, with the 12-month summary |
| (held) | payment plan request | one unit | Oct 3 | the statute's | statute | held | held | held | Counted, general words only |
| email:EX2 | complaint | 321 Pine Way | Oct 9 | none | none | none | open, no clock | acknowledge | Leads with a precedent shown as "unit and kind only" |

Summary line: 14 open (2 overdue, 3 due soon, 9 open); last 12 months 41 answered, 37 on time. Emailed requests PayHOA lacks: 2 ("Gate code not working", from a sender named by display name). The 2099-1042 acknowledgment draft: "Thank you. The Association received your architectural application on September 1, 2099, and it is being reviewed. Under [placeholder citation, documents], the Association will respond by October 16, 2099. The Board decides applications at its meetings; we will let you know the meeting it is on. - Oakview Example Association." The maintenance request's draft has no date. A campaign-linked page: "Owner information 2099 · 47 of 107 answered · 3 new · checked 2 h ago".

**Onboarding** ("Oakview Example Association", profile key `oakview`, opened Oct 1 by Jane Example; 86 items: 51 present, 14 partial, 21 missing):

| Gate | State | Waits on |
|---|---|---|
| start | open | none |
| ingest | open | none |
| establish | closed (working now) | insurance policies (partial); bank signers (missing); 2 questions |
| operate | closed (ahead) | the board rule; the roster |
| adopt | closed (ahead) | operating rules; the governing set |

Questions to draw: (1) "Who are the signers on the association's bank accounts?" FACT, high stakes, priority 9, unblocks "bank signers (missing) · gate establish · 1 clock", evidence "the library holds 2 bank statement files", choices 1 "Director A and Director B" (suggested) and 2, "in my own words", answer goes "in the private facts, never the specification"; (2) "Which version of the declaration is in force?" answered by Jordan Example (high stakes), waiting on a second person; Casey Sample may confirm, Jordan Example may not; (3) a MAP question (which book a document fills); (4) a connection item (the management software's sign-in: the command, no field); (5) a standing question (a change of office); (6) an answer that looks like a secret, refused. Answered, not yet applied: 4. Proposals: 2 patch files.

**The change-of-manager branch:** the outgoing agreement (made-up "Example Management Agreement") ends Dec 31, 2099. Notice no sooner than 120 days and no later than 60 days before the term's end: edges **Sep 2** and **Nov 1** (basis: the agreement). CM-2 the board decides: motion read from the decision record (mover, second, votes by name, one recusal, outcome), the secretary records it. CM-4's three person dates: records Oct 15, portal access Nov 1, vendors Nov 15 (all `person`).

**Runs in Work:** `respond-request/2099-1050` (RQ-12 "waiting on the member's agreement to the cost", the 5210 clock still running with both dates shown; the member has an 18000-cent estimate under the cap); `respond-request/2099-1042` (RQ-16 the board decides: Group "The board", due Oct 16, `documents`); `onboard/oakview` (ES-4 "a second person confirms", Casey Sample's move, Jordan Example's step waiting; ST-5 blocked on the Google sign-in; a **changed since** banner: "the declaration's pinned file changed on Oct 9 (size and page count); ES-2 reopened"); `respond-sweep` (weekly, children 14 open).
