# Design brief: person steps (enable, remind, guide)

One page of orientation for the design agent, for the step panel's guide and the nudges around it, specified in [screens/work-guide.md](screens/work-guide.md). It does not repeat the spec; it says what to read in what order, each screen and component to draw, what can be drawn today, and a made-up community to draw against. The model is [../workflows/person-steps.md](../workflows/person-steps.md); the screens it extends are the Work run page ([design-brief-work.md](design-brief-work.md)) and the office views ([screens/office-views.md](screens/office-views.md)). The Work screens and `RunStepPanel` are built; the guide, the enable strip, the nudges, and the away dialog are not, so draw them from the sample in section H and say so.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, or private fact; made-up samples only ("Oakview", "A. Owner", 2099 dates).

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. A **person step** is a step a human does: an act jason cannot do, or a decision the board makes and the secretary records. There are hundreds of them across the workflows, and they are most of the work.
2. The step panel answers three questions in one screen, the act always in reach: **can I do this now** (enable), **when is it due and who else sees it** (remind), and **what exactly do I do** (guide).
3. Nothing is sent. A reminder is a line that appears on a screen a person opens, in the digest they read, or in a list they print at a terminal.
4. The panel is quiet when nothing is due and plain when something is: a due date with its basis word, a band word, and the act.
5. A step is never hidden because the viewer cannot act on it: they see the words, the evidence, who holds it, and who to ask. The act is drawn disabled with the reason.
6. An absence moves the nudge to a cover, who can read and ask and gains no authority.

**The rules** (each is in the spec; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** There is no director-only or counts-only panel. The act row differs by the viewer's offices; the information does not.
- **State is a word and a glyph, never colour alone.** That covers the enable states, the band words, and the basis words.
- **Every date says whose it is**: the law's, the documents', a counterparty's, jason's proposal, or a person's. A proposed number is never drawn as a stamp ("proposed, not the law's").
- **A legal date is recited.** The statute's operative words come first, then jason's reading, labeled as a reading. A LEGAL line cannot be snoozed.
- **The page does not run a command.** It shows it, fills what it knows, and offers Copy.
- **An unreadable thing says so.** "could not read: REASON" and no count; never "nothing to look at" for a read that failed.
- **A step with no guidance is not apologised for.** It shows the derived minimum; the gap is shown to an administrator on the definition page.
- **A held matter shows its general title only** outside the private view. Draw the held panel as a title, a state, an office, a date and its basis word, and one sentence.
- **Nothing is sent, filed, mailed, or decided from here.** The acts are notes, an attestation, a snooze, a claim, and an away record.

## B. Reading order

1. [screens/work-guide.md](screens/work-guide.md): the whole panel, top to bottom, with the fixed words.
2. This page's section D (the components) beside section H (the sample).
3. [../workflows/person-steps.md](../workflows/person-steps.md) sections 4 (the guidance record), 5.2 (the twelve enable states), 6.2 (the bands), and 6.5 (escalation).
4. [screens/work.md](screens/work.md), "Layout: one run" and "Where a step's work happens", then [design-brief-work.md](design-brief-work.md), C3 (the panel by kind).
5. [approval-clarity.md](approval-clarity.md) for how a plan step's strip and its "waiting to be applied" nudge share the same surfaces.
6. [../workflows/person-steps-inventory.md](../workflows/person-steps-inventory.md) for the real range: steps with a long command, a legal clock, a per-item repeat, or nothing at all.

## C. The screens

### C1. The step panel, a step the viewer can do (wide)

Draw the layout of the spec: the title row, the enable strip, the nudge line, Do this, Look at, The rule, Check before you go on, The command, Done when, If you are blocked and If it does not apply side by side, Ask, Learn more, and the act row. The panel sits in the right column beside the rail. Draw it with a step that has all ten sections, then with only the four a derived step has (C5).

### C2. The enable strip, every state

The twelve states of the spec, each as the strip plus the act row beneath it: ready, not yours, not ready, needs an integration, needs a second person, terminal only, away cover, vacant, claimed, viewing as, paused or draft, done or skipped or not applicable, and held. Draw each once on the same step so the differences read.

### C3. The nudge line, every band

Due soon, due today, overdue, LEGAL, needs a date, open a while, snoozed, escalated (seen by the escalation office), and covering. Draw the line at its widest (with Snooze and I'm on it) and at 375 px (the controls wrap under the date). Draw a LEGAL line with the statute's words recited beneath it and no Snooze.

### C4. The lists, with the marks

Work ("Yours", then "Escalated to you"), Today's "Your work" (five nearest, then "All your steps"), and an office band ("Waiting on the treasurer", with a Vacant row). The same row everywhere: label, step, band word, due date, basis pill. Draw a per-item row ("14 letters: 3 not done; the earliest due Oct 14"), a needs-a-date row, and a covering group.

### C5. A step with no guidance

The derived panel: strip, nudge line, Do this (from the title), Why, Look at (evidence chips), the command as written, Done when (from the record), and Learn more. No apology line. Beside it, the definition page's coverage words for an administrator.

### C6. On a phone (375 px)

One column. The strip and the nudge line first and never collapsed; Do this and Why open; the other sections collapsed to a heading with a count; the act row stuck to the bottom; a long command scrolling inside its own box with Copy fixed. Draw the collapsed and one expanded section.

### C7. The away dialog and banner

The dialog of the spec (from, until, covered by, the plain sentence about what covering does), the banner on the office view ("The treasurer is away until Oct 26; the president is covering. End it."), and the cover's panel for a role-gated step with the refusal sentence.

### C8. The terminal

Not a screen, but the words must match. Set `jason workflow --due` (grouped lines with the band word and the run command) and `jason workflow --guide` (the sections as plain text) in a monospace block with the same fixed words, so a person who moves between the browser and the terminal meets the same sentences.

### C9. The reminder-drafts control card (optional)

A card on the Controls screen in the usual suggested, proposed, adopted states: "Reminder drafts: a draft email you send yourself". Draw it so it is plain that jason saves a draft and a person sends it. Draw it only if the board asks for the control; it is last in the build.

## D. The shared components, each once

Reuse (built): `RunStepPanel`, `WorkflowRail`, `RunRow`, `Command`, `Confirm`, `Doc`, `DueDate`, `Recitation`, `ReadingLabel`, `Pill`, `Glyph`, `StepStateWord`, `BasisPill`, `ControlStepNotice`, `OfficeLens`, `Tabs`, `Card`. Specified, not built (draw them from the built parts and say so): `TerminalStep`, `AgeStamp`.

| Component | What it is | Data | States |
|---|---|---|---|
| `StepEnable` | the enable strip | `enable{state, holders[], missing[], secondPerson, terminalOnly}` | the twelve states |
| `StepNudge` | due date, basis, band word, days, Snooze, I'm on it | `nudge{band, word, due, basis, days, escalatedTo, snoozedUntil, covering, claim}` | quiet, due soon, due today, overdue, legal, needs a date, snoozed, escalated, covering |
| `GuideSection` | a titled, collapsible region | `title, count?, children` | open, collapsed |
| `LookAtList` | one read | `label, count, rows[], refs[], asOf, unavailable` | counted, zero and read, unavailable |
| `RuleBlock` | `Recitation` plus `ReadingLabel` plus the version and caveat | `rule{key, words, version, source, reading, missing}` | recited, proposed policy, not on the shelf |
| `GuideChecklist` | checkboxes | `checklist[]{text, required}` | none ticked, some, all required ticked |
| `CommandList` | ordered commands with Copy | `commands[]{text, filled, note, terminalOnly}` | filled, fill-in, terminal-only |
| `AskOffices` | the offices to ask | `ask[]{office, holder, vacant, away}` | holder, vacant, away |
| `NudgeWord` | a `Pill` preset | one of LEGAL, OVERDUE, due soon, open, needs a date | five words, each with a glyph |
| `AwayDialog`, `AwayBanner` | record and show an absence | `office, from, until, cover` | recorded, ended, refused |
| `DueList` | grouped lines | `mine[], escalated[], covering[]` | each group; empty |

**Fixed words** (use exactly): "Yours: you hold the OFFICE office. Nothing is missing.", "Waiting on the OFFICE.", "Waits on step N: TITLE.", "Needs a second person", "A person does this at a terminal.", "Covering for the OFFICE until DATE.", "No one holds the OFFICE office.", "Do this", "Look at", "The rule", "Check before you go on", "The command", "Done when", "If you are blocked", "If it does not apply", "Ask", "Learn more", "jason's reading", "proposed, not the law's", "could not read: REASON", "Skip is not offered: this step is required by the law.", "Viewing as NAME (admin view): go back to yourself first." The full table is in the spec.

## E. Glyphs

Use the glyphs the console has, and the ten step-state glyphs of the Work brief. New ones only for what none can say: one each for the five band words (a flag for LEGAL, a clock past its hour for OVERDUE, a clock for due soon, a dot for open, a calendar mark for needs a date), and one each for covering (two people), away (a suitcase or a moon), vacant (an empty chair or an open circle), claimed (a hand), and snoozed (a clock with a pause). Name each for the idea. Every glyph has a word beside it.

## F. Decisions that are the design's, in one list

1. **Where Look at sits.** Directly under Do this (recommended: the person looks before they read the rule) or after The rule.
2. **How a long recited statute fits** a column: clamped to the operative words with "read the whole section" (recommended), or the whole text in a drawer.
3. **How the checklist shows progress** ("2 of 3 required ticked" beside Mark done, recommended) and what the Mark done button does while one is open (disabled with the reason).
4. **Whether the nudge line stays pinned** under the title when the panel scrolls (recommended on a narrow screen, not on a wide one).
5. **How the rail marks a nudge**: the band glyph beside the state glyph only for LEGAL and OVERDUE (recommended), or for every band.
6. **How "Escalated to you" and "Covering for" read** under "Your work": as separate headings (recommended) or as a tag on a row.
7. **The wording of the Snooze and Claim confirmations**, and whether the claimant's name shows on the rail.
8. **How the guide reads when a step is done**: collapsed, with the record shown (recommended).

These are not the design's: the escalation table, the lead time and the other defaults, whether claims ship, and whether reminder drafts exist ([../workflows/person-steps.md](../workflows/person-steps.md), section 13).

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| The panel's sections for a step with guidance (C1) | Yes, from section H | The `Support` record and the guide reads |
| The derived panel (C5) | Yes | Nothing: it reads fields that exist |
| The enable strip (C2) | Yes | The roster's holders and the away log |
| The nudge line and the list marks (C3, C4) | Yes | `jason.workflows.nudge` and the `work-due` loader |
| The away dialog and banner (C7) | Yes | The away log and the writer |
| The terminal output (C8) | Yes | `--due` and `--guide` |
| The reminder-drafts card (C9) | Only if asked | The control type and the `step-reminder` case |

## H. A made-up community to design against

"Oakview" has these steps open on 2099-10-20 (dates are plainly made up; the loaders will send ISO dates). Step titles and numbers follow the Work brief's sample and are drawn to make a point; they are not the registered definitions' own numbering (the inventory is). The viewer is the manager unless a row says otherwise. People: A. Manager (manager), S. Placeholder (secretary), R. Placeholder (treasurer), P. Placeholder (president), V. Placeholder (vice president). An owner is "A. Owner" and appears nowhere in a list.

| Step | Definition | State shown | The point it makes |
|---|---|---|---|
| Read the returned forms (step 9 of 25) | `owner-info-cycle` | ready, due Oct 23 `documents`, due soon | The full panel: all ten sections, a required checklist, three commands, a cite with a reading |
| Record the board's decision (step 3) | `owner-info-cycle` | not yours (the secretary) | The strip, the instruction and evidence still readable, who to ask |
| Enter the answers (step 22) | `owner-info-cycle` | ready, due Oct 23 `law`, LEGAL | The statute recited, no Snooze, no skip |
| Send the email batch (step 12) | `owner-info-cycle` | needs a second person | The first act recorded as a note; the step stays open |
| Mail the letters (step 16) | `owner-info-cycle` | terminal only | The command with Copy, "A person does this at a terminal.", no Mark done yet |
| Review the attachments (step 4) | `bill-attach` | overdue 6 days `person` | OVERDUE, escalated to the president after 72 hours |
| Record the review's notes | `monthly-review` | covering (the treasurer is away until Oct 26; viewer is the president) | The refusal sentence; no authority gained |
| Record the minutes' date | `board-meeting` | vacant (no secretary) | "No one holds the secretary office"; the board sees it |
| Set the review date | `monthly-review` | needs a date | A settable slot unset; the clock undated, not late |
| Test every link and QR code (step 3) | `mailroom-letter` | per item: 14 letters, 3 not done | One line with a count, the worst date |
| Connect PayHOA | `integration-connect` | needs an integration (administrator) | The integration named, no credential shown |
| A member's hearing | `hearing` | held | The general title and nothing else |
| Read the vendor's report (step 3) | `backflow-annual` | claimed by A. Manager since Oct 9 | A claim; the others' lines quiet |

A nudge list to draw (the manager, 2099-10-20): LEGAL Oakview owner information 2099, step 22, due Oct 23 `law`; OVERDUE Bill attach, step 4, due Oct 14 `person`, 6 days late; due soon Annual backflow test, step 3, due Nov 1 `counterparty`; needs a date Monthly review, step 2. Escalated to the president: Monthly review, step 5, the treasurer's, 4 days late.

An away record to draw: the treasurer, 2099-10-12 to 2099-10-26, covered by the president. Run states to draw are those of the Work brief (`draft`, `active`, `paused`, `waiting`, `done`, `cancelled`, `failed`).
