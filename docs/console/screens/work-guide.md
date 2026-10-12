# Work: the step guide (enable, remind, guide)

The step panel of the run page, extended · `#/work/<definition>/<id>` · phase 2, after the Work screens; **the panel's guide, enable strip, and nudge line are built** (see "As built, phase 1" below), the away dialog and the list marks are not · CLI: `jason workflow --guide`, `--due`, `--snooze`, `--claim`, `--away` · model: [../../workflows/person-steps.md](../../workflows/person-steps.md) · every person step: [../../workflows/person-steps-inventory.md](../../workflows/person-steps-inventory.md)

The design brief for the design agent is [../design-brief-person-steps.md](../design-brief-person-steps.md).

## In the console

`RunStepPanel` is built ([work.md](work.md), "Layout: one run"): the step's title, its state and who it waits on, **why**, **look at** (evidence chips), the **command** with Copy, and the act (Mark done, skip, not applicable, note). It shows one `why` sentence and a command string, and it says nothing about whether *this* viewer can act, when the step is due for them, who else sees it when it is late, or what to do if they are stuck. `StartRun` and the office views ([office-views.md](office-views.md)) are built beside it.

**This spec is the whole step panel as proposed**, and two small additions around it: the nudge marks on the lists that already exist (Work, Today's "Your work", the office bands), and an away dialog on the office view. It reads, and writes only the small acts below, in the signed-in person's name. It never sends, files, or mails anything. The records it reads are the definition's `Support` ([person-steps.md](../../workflows/person-steps.md), section 4); a step with none shows the derived minimum (section "When a step has no guidance").

## Purpose and personas

A person opens a step and needs, in this order: *can I do this, when is it due, and what exactly do I do?* The panel answers the three in one screen, the act always in reach.

- **Manager:** most steps; opens the panel to do the thing, with the command in hand.
- **Secretary:** records the board's decisions and postings; needs the motion, the record to point to, and the meeting.
- **Treasurer, president, vice president, director:** the board's steps; a director covering for an office needs the words even when the act is not theirs.
- **The person covering an absent office:** sees the step, the instruction, and "Only the secretary can record this", and who to ask. Gets no authority.
- **Administrator:** reads guidance coverage on the definition page; never acts for anyone.
- **Counsel:** reads the panel's evidence on grant. No step.
- **Owner:** never sees this screen.

## Data

`work-run` (built) gains three objects per step; one new loader and four small writes.

| Part | Source | Loader or write |
|---|---|---|
| `enable` | the roster (`Community.officers()`), the away log, the claims (notes), `controls.effective.step_gates`, the integrations' status (names only), the step's `needs` | `GET /api/work-run` (step `enable`: `state`, `holders[]` as `{office, vacant, away?, cover?}`, `missing[]`, `secondPerson`, `terminalOnly`) |
| `nudge` | `jason.workflows.nudge`, a pure function of the folded run, the roster, the away log, the board's reminder preferences, and the day | `GET /api/work-run` (step `nudge`: `band`, `word`, `due`, `basis`, `days`, `escalatedTo`, `snoozedUntil`, `covering`, `claim`) |
| `guide` | the step's `Support.guides`, with the SOP step's `do`, `check`, `refs`, `lessons` where the field is empty; each `look_at` read; each `cite` recited from the authorities shelf at the run's date | `GET /api/work-run` (step `guide`: `instruction`, `why`, `lookAt[]` as `{label, count, rows[], refs[], asOf, unavailable}`, `rule[]` as `{key, words, version, source, reading, missing}`, `checklist[]`, `commands[]` as `{text, filled, note, terminalOnly}`, `lessons[]` as `{key, status}`, `doneWhen`, `record`, `blocked`, `notApplicable`, `ask[]` as `{office, holder, vacant, away}`, `sop`) |
| Lines for a person | the nudges for an office, grouped: `mine`, `escalated`, `covering`; counts only for `quiet` | `GET /api/work-due?office=&within=&asOf=` (new; the same as `jason workflow --due`) |
| Away | `data/workflows/away.jsonl` | `office-view` gains `away[]` (`{office, from, until, cover}`); `POST /api/write/work-away` with `{act: "away"/"end", office, from, until, cover?}` |
| The small acts | `snooze`, `claim` (and release), `blocked` (a note with `blocked: true`), `away` | `POST /api/write/work/<definition>/<id>` with `{act, step, ...}`; the signer's name is enforced; a `by` naming someone else is a 403 |

A list never carries an owner's contact details or an answer. A `look_at` row is a title and a count at the viewer's data level; an id and a link, never a copy. A step in a held run outside the private view answers `held_page` and nothing in the three objects.

## Layout: the step panel

Wide screen (the right column of the run page; the rail is on the left, [work.md](work.md)):

```
+--------------------------------------------------------------------------------------------+
| 9  Read the returned forms                                                 needs a person  |
| YOURS: you hold the manager office. Nothing is missing.                                    |
| Due Oct 23 [DOCUMENTS]  ·  DUE SOON, 3 days      Snooze...   I'm on it                      |
+--------------------------------------------------------------------------------------------+
| DO THIS                                                                                    |
| Read each form that has arrived, say what it answers, and confirm the reading when it is   |
| right.                                                                                     |
| Why: an owner's answer counts only once a person confirms the reading.                     |
+--------------------------------------------------------------------------------------------+
| LOOK AT                                                          as of Oct 20, 9:12        |
|  Forms that arrived since the last read   4      [Open in Responses]                       |
|    Form 1042 · Form 1043 · Form 1045 · Form 1046                                           |
|  Read and not yet confirmed               2      [Open in Responses]                       |
+--------------------------------------------------------------------------------------------+
| THE RULE                                                                                   |
| CIV 9999(b)  (the words in force on Oct 20, 2099)                       [Open the section] |
|  | <the section's operative words, whole, from the stored text, with its citation>         |
|  Caveat: jason's consolidated text is not an official restatement.                         |
| jason's reading: answers are entered before the reports go out.                            |
+--------------------------------------------------------------------------------------------+
| CHECK BEFORE YOU GO ON                                                                     |
|  [x] Each reading matches the form on the screen        required                           |
|  [ ] A form for the wrong unit is set aside, not confirmed                                 |
|  [ ] Nothing is marked an answer until you confirm it   required                           |
+--------------------------------------------------------------------------------------------+
| THE COMMAND                                                                                |
|  1  jason responses --list --new                                              [Copy]       |
|  2  jason responses --read ID --by A. Manager                                 [Copy]       |
|  3  jason responses --confirm ID --by A. Manager                              [Copy]       |
|     ID is yours to fill in. The page does not run a command.                               |
+--------------------------------------------------------------------------------------------+
| DONE WHEN                                                                                  |
| The count of forms read and not confirmed is 0. Point to: the arrivals read (a count).     |
+--------------------------------------------------------------------------------------------+
| IF YOU ARE BLOCKED                                  IF IT DOES NOT APPLY                   |
| Leave a note naming the form id and what is         This step is required: it has no       |
| wrong with it. The president sees it. Nothing is    not-applicable outcome.                |
| sent.   [Leave a blocked note]                                                             |
| ASK  the manager (A. Manager) · the president (S. Placeholder)                             |
+--------------------------------------------------------------------------------------------+
| LEARN MORE   jason sop owner-info-cycle (step 14) [Copy]  ·  Lesson: returns-by-the-same-  |
| rules (fixed)                                                                              |
+--------------------------------------------------------------------------------------------+
| [ Mark done... ]   Not applicable is not offered.   Skip is not offered: a legal date.     |
+--------------------------------------------------------------------------------------------+
```

- **The enable strip** is one line with the state word and glyph; under it the reason, and for every state but "ready" what would change it. It is never collapsed.
- **The nudge line** is the due date with its basis word, the band word (the digest's: LEGAL, OVERDUE, due soon, open, needs a date), days to or past the date, and the holder's small controls (Snooze, I'm on it). A legal step has no Snooze.
- **Do this** is the instruction; **Why** is the one sentence. Neither is collapsed.
- **Look at** shows each read with its count, its as-of age (`AgeStamp`), at most five row titles, and "Open in NAME" for the owning screen at the right filter. A read that cannot read says "could not read: REASON" and shows no count. The panel never says "nothing to look at" for an unavailable read.
- **The rule** recites each cite whole (`Recitation`), then jason's reading in a `ReadingLabel`. A proposed policy shows "Proposed, not adopted." A cite the shelf cannot resolve shows "The words of CITE are not on the shelf here." and the command that puts them there; no paraphrase.
- **The checklist** is real checkboxes. A `required` item must be ticked before the Mark done dialog can confirm. Unrequired ticks stay in the browser (storage wrapped, since it can be unavailable) and are not state of the run.
- **The command** is an ordered list with Copy on each line, the filled placeholders, and the unfilled ones marked "fill in". A terminal-only line says why.
- **Done when** is the test and, beneath it, the record the attestation must point to.
- **If you are blocked / If it does not apply / Ask**: two columns on a wide screen, stacked on a narrow one. "Ask" shows the office and its holder as the roster holds it, "Vacant" or "away until Oct 20", never a phone or an email.
- **Learn more** is last and quiet: the SOP address with Copy, the lessons with their status.
- **The act row** is the last element of the panel and sticks to the bottom of the viewport on a narrow screen. It shows only the acts the viewer may make, each disabled-with-reason where it is not offered, never hidden.

### The states of the enable strip

| State | Words | Under it | Act row |
|---|---|---|---|
| ready | "Yours: you hold the OFFICE office. Nothing is missing." | | Mark done (and skip, not applicable where declared) |
| not yours | "Waiting on the OFFICE." | who holds it, who to ask; the instruction and evidence stay readable | none; "Only the OFFICE can do this. You are the OFFICE2." |
| not ready | "Waits on step N: TITLE." | link to the step | none |
| needs an integration | "Needs PayHOA signed in." (name only) | the screen or command that connects it | Mark done stays off |
| needs a second person | "Needs a second person: the OFFICE or another director." | the first act is recorded as a note; the step stays open | "Record my part" (a `Confirm`) |
| terminal only | "A person does this at a terminal." | the command with Copy | none before the record exists |
| away cover | "Covering for the OFFICE until Oct 20." | what the cover may and may not do (below) | only the acts the viewer's own offices hold |
| vacant | "No one holds the OFFICE office." | a finding for the board; the escalation office is shown | none |
| claimed | "A. Manager is on it since Oct 9." | "Release" for the claimant | unchanged |
| viewing as | "Viewing as NAME (admin view): go back to yourself first." | | none |
| paused / draft | the run's reason / "The run has not been opened." | no clock runs | none |
| done / skipped / not applicable | "Done by NAME on Oct 9." etc. | the record, as a chip | "Reopen" where allowed |
| held | the definition's general title and "Open the private view to see this run." | nothing else | none |

**Covering for an absent office** reads, under the strip: "You can read this and ask. Only the secretary can record the board's decisions, and the secretary is away until Oct 20. Ask the president to bring it to the board." Covering never grants a role.

## Layout: nudge marks on the lists

On every list that shows a run or a step, the same mark: the band word beside the due date and its basis word. No new screen.

```
Work > Yours
  Owner information 2099   Step 22: Enter the answers         LEGAL     due Oct 23 [LAW]
  Bill attach: Oct         Step 4: Review the attachments     OVERDUE   due Oct 14 [PERSON]  6 days late
  Backflow test            Step 3: Read the vendor's report   due soon  due Nov 1  [COUNTERPARTY]
  Quarterly review         Step 2: Set the review date        needs a date
Work > Escalated to you
  Quarterly review         Step 5 (the treasurer): Record notes   OVERDUE   4 days late
Today > Your work   (the five nearest, then "All your steps (9 open)")
Office band         "Waiting on the treasurer"  (the same lines; a vacant office shows "Vacant")
```

- **Escalated to you** and **Covering for the OFFICE** are separate headings under "Your work", after the person's own lines. A line there says whose step it is, how late, and the last note. Nothing is sent to anyone.
- A **per-item** step is one line with a count and the worst item's date: "14 letters: 3 not done; the earliest due Oct 14."
- The **dock's red count** adds the person's steps in LEGAL and OVERDUE. It opens nothing.
- **`jason workflow --due`** prints the same lines for a terminal ([person-steps.md](../../workflows/person-steps.md), section 6.3).

## Layout: the away dialog

On the office view, "Away..." for an office the viewer holds. A small `Confirm`:

```
Record that the treasurer is away
From [2099-10-12]   Until [2099-10-26]   Covered by [the president v]
This is kept as the office and two dates. No reason is asked. Steps for the treasurer
will be shown to the president, who can read them and ask; the president does not gain
the treasurer's authority. A legal date that falls in these dates will show to the whole
board from today.
[ Record ]  [ Cancel ]
```

A recorded absence shows as a banner on the office view ("The treasurer is away until Oct 26; the president is covering") with "End it". The dialog refuses an `until` before `from`, and asks for a cover only from the offices the roster names.

## When a step has no guidance

A step with no `Support` still shows: the enable strip (always derivable), the nudge line (from its clock), **Do this** from the SOP step's `do` or the title, **Why**, **Look at** from its evidence chips and the SOP step's `check`, **The command** as written, **Done when** from its `record`, **Learn more** from the SOP address and the procedure step's lessons, and the blocked and ask lines in their standing words. No sentence apologises for the missing guidance. The **definition page** (`#/work/definitions`, "Read") shows each step's guidance coverage as words ("instruction, rule, checklist, look-at") for an administrator, so the gap is visible where it is fixed.

## Components

Built: `RunStepPanel`, `WorkflowRail`, `RunRow`, `Command`, `Confirm`, `Doc`, `DueDate`, `Recitation`, `ReadingLabel`, `Pill`, `Glyph`, `StepStateWord`, `BasisPill`, `ControlStepNotice`, `OfficeLens`. Specified, not yet built: `TerminalStep`, `AgeStamp`. **Built in phase 1** (all in `ui/src/components/StepGuide.tsx`, styled in `ui/src/styles/work-guide.css`): `StepEnable` (as `StepEnableStrip`), `StepNudge` (as `StepNudgeLine`), `GuideSection`, `LookAtList`, `RuleBlock`, `GuideChecklist` (with `useChecklist`), `CommandList`, `AskOffices`, `NudgeWord`, and `ClaimButton`. **Not built:** `AwayDialog`, `AwayBanner`, `DueList`. The table lists the whole set:

| Component | What it is | States |
|---|---|---|
| `StepEnable` | the enable strip | the twelve states above, each a word and a glyph |
| `StepNudge` | the nudge line: due date, basis, band word, days, Snooze, I'm on it | quiet, due soon, due today, overdue, legal, needs a date, snoozed, escalated, covering |
| `GuideSection` | a titled, collapsible region of the guide (open by default on a wide screen) | open, collapsed, empty (not drawn) |
| `LookAtList` | one read: label, count, as-of, up to five row titles, open-in link | counted, empty-and-read (a count of 0 with its as-of), unavailable |
| `RuleBlock` | `Recitation` plus `ReadingLabel`, the version in force, the caveat | recited, proposed policy, not on the shelf |
| `GuideChecklist` | checkboxes with `required` marks | none ticked, some, all required ticked |
| `CommandList` | ordered `Command` rows with filled and unfilled placeholders | filled, fill-in, terminal-only |
| `AskOffices` | offices with holder, vacant, away | holder, vacant, away |
| `NudgeWord` | a `Pill` preset for LEGAL, OVERDUE, due soon, open, needs a date | five words, each with a glyph |
| `AwayDialog`, `AwayBanner` | record and show an absence | recorded, ended, refused |
| `DueList` | the grouped lines for Today and `work-due` | mine, escalated, covering, empty |

## Actions

| Control | Does | Approval? |
|---|---|---|
| Mark done | `attest`, with the record the step asks for and the required checklist items ticked; says what will be recorded and under what name | A `Confirm`; the step's gates apply |
| Skip, Not applicable | as built; the words come from `blocked` and `not_applicable` | A `Confirm` with a reason; a legal step has no skip |
| Leave a blocked note | a `note` with `blocked: true`; moves the nudge to the escalation office | A `Confirm` with text |
| I'm on it / Release | a `note` with `claim: true` | A `Confirm`, one line |
| Snooze | a `note` with `snooze_until`; refused on a legal step, beyond the due date, or beyond 14 days | A `Confirm` with a date |
| Away / End it | the away log, as the holder (or an administrator for them) | A `Confirm` |
| Copy, Open in NAME, Ask | read only | No |

The panel makes no plan, queues no job, sends no message, and records no decision. Where a step's work is another screen's ([work.md](work.md), "Where a step's work happens"), the panel shows that screen's state and links to it.

## States

- **Loading:** a skeleton of the strip and the first section; "reading the run on disk".
- **A read cannot read:** that `LookAtList` says "could not read: REASON" with the as-of of the last good read, if any; the rest of the panel stands.
- **A cite is not on the shelf:** the `RuleBlock` says so and gives the export command; the rest stands.
- **A role the viewer does not hold:** the act row is drawn disabled with the sentence; the server refuses the same act with a 403 naming the office.
- **The run moved while the panel was open:** the Mark done dialog refuses with "this run changed since you opened it" and offers a reload (the writer's `expect`).
- **A step with a legal clock past due:** the nudge line reads LEGAL with the law's words recited in the rule block and a link to the follow-up if a person opened one.
- **Offline or a failed write:** the dialog keeps the text typed and says nothing was recorded.
- **Empty:** a section with nothing to show is not drawn (no "None"), except Look at when a read returned 0 (drawn, with its count and as-of) and Ask when no office resolves (drawn: "No one is named for this. Tell the president.").

## Mobile and narrow screens

Under 720 px: one column. The enable strip and the nudge line are the first two blocks and never collapse. The act row sticks to the bottom (at least 44 by 44 px targets, 8 px apart). Do this and Why are open; Look at, The rule, Check, The command, Done when, Blocked, Learn more are collapsed to their heading with a count ("Look at (2 reads)"). A command line scrolls horizontally inside its own box with Copy fixed at the end, so a long command never widens the page. The rail becomes the run page's collapsed "Step 9 of 25" header. Dialogs are full-height sheets.

## Accessibility

- The panel is a region labelled by the step title; each section is a heading in order (h3 inside the panel), so a screen reader can jump section to section.
- Every state is a **word and a glyph**, never colour alone: the band words, the enable states, the basis words.
- Checkboxes are native, each labelled; `required` is in the label text, not only a colour or an asterisk.
- Copy announces "Copied" in a polite live region; a disabled act has `aria-disabled` and its reason is the control's description, reachable by keyboard.
- A recorded act moves focus to a confirmation heading; Esc closes a dialog and returns focus to the control that opened it; a dialog traps focus.
- A date in the Snooze and Away dialogs is a labelled date input with a typed alternative and its format shown.
- Contrast meets the console's tokens in the light and the dark theme; the recited statute block keeps its quote style in both.
- Motion: the spinner of a running read stops under reduced motion; nothing flashes to draw attention to a nudge. A LEGAL line is distinguished by its word and its position, not by animation.
- Nothing times out: a panel left open does not expire a draft of text typed in a dialog.

## Privacy

- **Directors and officers read the same panel at the same level.** What differs is the act row, from the viewer's offices.
- **Held runs** (`Visibility.HELD`): outside the private view the panel, the nudge marks, the Today and office bands, the digest line, and `--due` carry the definition's general title, the state, the office, the date and its basis word, and nothing else. A step's title shows only where the definition sets `public_title`. Inside the private view the whole panel shows, and each opening is a line in `access/served.jsonl` under the run id.
- **Administrator runs** appear for an administrator only, in no one else's bands or counts.
- **Look-at rows** are at the viewer's level: titles and counts, never an owner's answer or contact detail. Rows are never copied into the run.
- **A claim, a snooze, a blocked note** keep a name and a time in the history, as every note does; none carries a reason beyond the person's one line, and the dialog says to leave names and units out.
- **Absence** is an office and two dates, never a reason; visible to the board's offices and the manager.
- The owner view never reads `work-run`, `work-due`, or the away log (`OWNER_SOURCES` does not list them). Counsel reads a run's evidence on grant.
- No `/api/file` link, no absolute path, and no frame of an outside host.

## Copy: fixed words

Use exactly. Placeholders in capitals are filled by the page.

| Place | Words |
|---|---|
| Strip, ready | "Yours: you hold the OFFICE office. Nothing is missing." |
| Strip, not yours | "Waiting on the OFFICE." |
| Strip, not ready | "Waits on step N: TITLE." |
| Strip, second person | "Needs a second person: the OFFICE or another director." |
| Strip, terminal | "A person does this at a terminal." |
| Strip, cover | "Covering for the OFFICE until DATE." |
| Strip, vacant | "No one holds the OFFICE office." |
| Strip, viewing as | "Viewing as NAME (admin view): go back to yourself first." |
| Nudge | "Due DATE [BASIS]" with LEGAL, OVERDUE, due soon, open, or needs a date |
| Proposed number | "proposed, not the law's" |
| Section headings | "Do this", "Look at", "The rule", "Check before you go on", "The command", "Done when", "If you are blocked", "If it does not apply", "Ask", "Learn more" |
| Rule, reading | "jason's reading" (or "The board reads this to mean" where adopted) |
| Rule, missing | "The words of CITE are not on the shelf here." |
| Read, failed | "could not read: REASON" |
| Blocked note | "Leave a blocked note. The OFFICE sees it. Nothing is sent." |
| Not applicable, none | "This step is required: it has no not-applicable outcome." |
| Skip, none (legal) | "Skip is not offered: this step is required by the law." |
| Cover refusal | "You can read this and ask. Only the OFFICE can ACT, and the OFFICE is away until DATE. Ask the OFFICE2 to bring it to the board." |
| Snooze refusal | "A legal date cannot be snoozed." |
| Done by | "Done by NAME on DATE." |
| Claim | "NAME is on it since DATE." |

## Acceptance criteria

1. `GET /api/work-run` for a step carries `enable`, `nudge`, and `guide`; signed out is a 401; the owner view is refused; a held run outside the private view carries none of the three.
2. The enable state is the first applicable of the ordered list in [person-steps.md](../../workflows/person-steps.md), section 5.2; the same fixture gives the same state for a director and an officer who hold the same offices.
3. A step the viewer's offices do not hold shows its instruction and evidence and no enabled act; the server refuses the act with a 403 naming the office.
4. A cover sees an absent office's step, the instruction, and the refusal sentence, and cannot attest a step whose role they do not hold.
5. A vacant office shows "No one holds the OFFICE office" and the step also appears for the escalation office the same day.
6. Every nudge shows a basis word; a proposed number is labelled "proposed, not the law's" and never drawn as a stamp.
7. A law clock on the step renders its statute words in a `RuleBlock` before any reading, and a LEGAL line cannot be snoozed.
8. A cite the shelf cannot resolve renders "not on the shelf here" and no paraphrase; the page never quotes from memory.
9. A `required` checklist item blocks the Mark done confirmation until ticked, and the attestation records "checked: N of N".
10. Copy copies the filled command; an unfilled placeholder is marked "fill in"; the page runs nothing.
11. A read that cannot read shows "could not read: REASON" and no count; the panel does not say "nothing to look at".
12. A per-item step is one line with a count in every list; the panel lists the items.
13. A snooze is a `note` event; it is refused on a legal step, past the due date, and past 14 days; the escalation office's line is unchanged.
14. A blocked note moves the nudge to the escalation office, leaves the holder's line, and sends nothing.
15. A recorded absence moves the holder's nudges to the cover, shows the banner on the office view, and grants no role.
16. A held run's nudge, Today line, office line, digest line, and `--due` line show the general title only outside the private view; an act on a held run is the 404 a missing run gets.
17. A director reads the same panel an officer reads at the same level, and no list carries an owner's contact details or an answer.
18. At 375 px width the strip, the nudge line, and the act row are visible without scrolling the page sideways; a long command scrolls inside its own box.
19. Every control is reachable by keyboard; every state is a word and a glyph; focus moves to the confirmation after an act; reduced motion stops the spinner.
20. A step with no `Support` renders the derived minimum with no apology, and the definition page lists the gap for an administrator.
21. The page and its loaders make no call to PayHOA, Google, Zoom, or a mail service; a test with those clients patched to raise passes.

## As built, phase 1

Built: the three objects on each person step of `GET /api/work-run` (`enable`, `nudge`, `guide`; person, decision, and note-ended wait steps only; a held run outside the private view carries none), the panel in the order of the layout above, the fixed words of "Copy: fixed words" for the strip's states and the nudge line, the claim (`POST /api/write/work/<definition>/<id>` with `{act: "claim", step, release?}`; "I'm on it" and "Release"), and the definition page's guidance coverage in words (`guidance` on each step of `GET /api/work-definitions?key=`). Acceptance criteria 1 to 3, 6 to 11, 16 (the panel and the loader; `--due` too), 17, 19 (in part), 20, and 21 hold in the code and are tested. Behaviour the build chose:

- **A required checklist item** is ticked in the page each time the panel opens (it is a check made before Mark done, never kept); an unrequired tick is kept in this browser, wrapped in a try for storage that is not there. While a required item is open the Mark done control is disabled and the panel says how many are left. The attestation's `what` reads "STEP TITLE; checked: N of N required".
- **A terminal-only step** says "A person does this at a terminal." and still shows Mark done with its required record, since the page cannot know the record exists.
- **A step that is done, skipped, or superseded** opens with Do this only; the other sections are collapsed to their headings.
- **A long recited section** scrolls inside its own bordered region (keyboard focusable), not clamped; the whole text is in the region.
- **The lists** (Work, Today, the office bands), the digest section, snooze, the blocked note, the away dialog and cover, and the `work-due` loader are not built: they are phase 2. The CLI has `jason workflow --due --for NAME` meanwhile.

## Decisions for the user

Settled by the board's rules of 2026-10-11: directors and officers have the same access; the secretary records the board's decisions; jason sends, files, and mails nothing on its own; the console may save Gmail drafts and never send.

Still to confirm (the full list is in [person-steps.md](../../workflows/person-steps.md), section 13):
1. Whether "I'm on it" (a claim) ships in the first phase; it is a note and cheap, but it adds a name to the list.
2. Whether the covering person's lines sit under "Your work" (recommended, under their own heading) or only on the office view.
3. Whether the Look at section is collapsed on a wide screen once a step is `done` (recommended: yes; the evidence chips remain).
