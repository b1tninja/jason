# The console handoff's sixth cut, reconciled with what is built

The design agent's sixth cut (2026-10-10) adds two prototype pages on made-up data, the splitter (`split-document/SplitDocument.dc.html`) and the record checklist (`record-checklist/RecordChecklist.dc.html`), with a short note (`jason-console/SIXTH-CUT.md`). The rest of the folder repeats the fifth cut ([handoff-reconciliation-5.md](handoff-reconciliation-5.md)) and the corrections already applied ([handoff-reconciliation.md](handoff-reconciliation.md)).

The build team had already built both screens from the same specs: [screens/split.md](screens/split.md) (design: [../pdf-splitter.md](../pdf-splitter.md) section 5), [screens/records.md](screens/records.md) ([handoff-record-intake.md](handoff-record-intake.md), [../record-intake.md](../record-intake.md)) and [screens/limits.md](screens/limits.md) ([../instance-limits.md](../instance-limits.md)). This page compares the two sets, lists what to take from the design, and says what the design and the backend each still lack.

How this was read: the two `.dc.html` files were read as text only (markup, styles, script, copy); nothing was opened or run. Neither page is mounted in `JasonConsole.dc.html`, and `HANDOFF.md` and `CLAUDE-CODE-BRIEF.md` have no sixth-cut entry, so both are standalone prototypes. The design's sample data is all in the script, and its page pictures are drawn stand-ins.

## In one paragraph

The built screens are ahead of the prototypes on behavior and honesty: the prototypes have no server, no windowing, no limits, no job watching, no replace, read, keep, acknowledge or bind acts, no standing block, and their statute text is sample words. The prototypes are ahead in four places that matter: **segment bands** in the album (spec 5.3 asks for them and the build has only an alternating tint), **the wrong-slot notice first on the slot page**, **the suggestion drawn as "proposed" with the accent and a dashed line** (the build uses the warning colour, which the attention ladder reserves for a clock), and a handful of small readings of the data the build already receives but does not show (the gate a group opens, "N of M held or answered", the existence question's words, a Drive-not-connected banner on the list). Everything else matches or the build is better. The design returned no Limits screen.

## 1. Element by element

Verdicts: **matches**; **adopt** (the design is better); **keep** (the build is better, tell the design); **decide** (a conflict that needs the user).

### Split document

| Design element | Built element | Verdict |
|---|---|---|
| Frame: `h1`, file label (masked when confidential), save state as a word, counts line, `aria-live` | `ScreenHeader`, `split-counts` with the same words and an extra confidential badge | matches |
| Rail at 1200 px and wider; bottom sheet below, opened from a bar with the count; one View menu under 720 px | `wide` media query, `split-sheet`, bar button with count, `<select>` under 720 px | matches |
| Sheet bar also carries the **Review and split** button | Review is in the toolbar and in the rail foot only; the sheet bar has the count only | adopt (small): on a phone the primary act is a scroll away |
| Start marker: solid bar, "Starts N"; page 1 shows a lock | Left border, tag "Start N" (nested: double border, "Nested start"), lock on page 1 | matches; word: use "Starts N" as the spec says |
| Suggestion marker: **dashed bar in the accent**, "Suggested · High" | Dashed border in `--warn`, tag "Suggested, High" | adopt: foundations section 1 gives warn to "a clock inside 14 days" and section 2 gives dashed to "proposed". A suggestion is the second, not the first |
| Album with **numbered segment bands**: a header per segment (number, range, title, source of the start), pages in the band, alternate bands tinted | Windowed grid of fixed cells with `data-band` alternation and a number in each start tag; no header, no gap between segments | adopt: spec 5.3 says "a segment's pages sit on a tinted strip with the segment number at the start and a gap before the next". Cost is in the windowing arithmetic (section 2) |
| Filmstrip: big page, a strip of 15 neighbours, a tap on the strip goes to the page and does **not** mark; Enter or the button marks | Same: `onActivate` returns after focusing in the filmstrip; 96 px strip is a windowed `PageGrid`; the big page is `Figure` | matches (the build's strip spans the whole file; the design's only 15 neighbours) |
| Scroll view: two pages, Previous and Next | One page at a time down or across (`Scroll across`), windowed | keep |
| List: a row per segment, thumbnail, title, range, source, `why` when jason reads more than one document, Merge with previous, Nest inside previous; suggestions as dashed rows | `SegmentList`: the same rows, level and title edits, accept and reject on suggestion rows, windowed, phone default | matches; the "may hold more than one document" line is a gap (section 4) |
| Compare pane **beside** the pages at every width: the page, the page before, the first page of the segment before | `ComparePane` under the pages: the same three pictures, Fit, 800 px and enlarged zoom | decide (small): beside is better on a wide screen and wrong at 375 px. Recommend beside at 1200 px and wider, stacked below that. CSS only |
| Size slider 72 to 220, Undo and Redo with glyphs, labels hidden under 720 px | Size slider 64 to 220, Undo and Redo as words | keep the words; the glyphs are an option (the foundations keep icons to Close and the reorder arrows) |
| **More** menu: every Nth with a live count, blanks, restarts, accept at High, show rejected, "Check with the local model" disabled with its reason, clear marks. Each item states its count in a line before it runs and is one undo step | **Suggest** menu (suggest, accept at High, accept at Medium or better, show rejected) and **More** (every Nth, blanks with stay-before, stay-after or leave out and the duplex check, restarts, clear behind a `Confirm`). Blanks and restarts are two steps: find, then apply, because facts load in chunks | keep the build's structure and options; adopt the design's one-line "what it will do, how many" copy on each button (for blanks and restarts, after the find) |
| Bulk "Accept all suggestions at High (n)" in the rail header | Accept at High and at Medium or better in the Suggest menu; none in the rail | adopt (small): put the High button in the rail's suggestion header as the design does |
| "Check with the local model" shown, disabled, "Not in this design" | Not built; not shown | keep (do not show a control that does nothing; show it when the pass exists). The line "About 3 minutes for 41 pages" in the design is an invented figure |
| Keys: the build's list, minus `[` `]`, `Y`, Page Up and Down | Full list in `KEYS` | keep |
| Shift-click selects without marking; right click or `L` opens the page menu | Same, plus a 500 ms long press and the grip to drag a start | keep |
| Page menu: start, nested start, merge with previous, accept, reject, "Why", show larger, selection acts | `PageMenu` dialog: the same, plus make top-level, "Why was this suggested?" with the signals, reload the picture | keep |
| Review: per-part title field, **kind as a guess**, thumbnail, a flag with a glyph per row (slot filled, duplicate, "more than one document") | Table: part, first page (lazy), pages, title, "What happens" in words (held, fills, collision, duplicate); no kind | adopt the kind: `ReviewPart.kind` is already in the payload. The glyph on a flagged row is a small gain for the same reason |
| Review: blanks checkbox ("Leave out 4 blank pages (22, 40, 72, 88)"), arithmetic line "adds up" | Same (found by a button), `Pages add up` badge, the totals line | matches |
| Review: "Pages 61 and 66 are sideways; rotate them in the new files only" | Nothing | adopt only after a backend gap is closed (section 4): the apply has no rotation |
| Review: **Filing** radio group: leave in held uploads / file by the library's classification / fill record slots (not designed) | No choice; the server decides per part and the row says what it did | decide (section 3) |
| Review: dry run, then one `Confirm` "Write N files as NAME"; result lists filled, held, skipped, failed | Preview then a primary button spelled "Write N files as NAME"; result lists the same; a Decline split `Confirm`; partial results offer "Review again to finish the rest" | keep |
| States as tweaks: offline (apply disabled with the reason), a second editor's copy (Keep mine / Keep theirs / Merge boundaries) | Offline notice with Retry, save error, 409 conflict with the same three buttons and the pages only in each copy, restore of held marks, read-only after apply | keep; the design's "Two copies of this draft. NAME changed it at 10:44" names the other editor and the time, which the build also shows (`by`, `updated`) |
| Tweak props: `connection`, `confidential`, `startView` | `#/setup/split/demo` and `?pages=` | adopt (small): see the demo hook in section 3 |
| Start screen, drafts list | Start screen (upload or library id, dry-run check), drafts with status words | keep (the design says "the drafts list is the start screen; not in this design") |
| Page pictures are drawn SVG | `/api/split/thumb`, windowed loader, placeholders from the facts | keep |

### Records, the slot page and the Drive chooser

| Design element | Built element | Verdict |
|---|---|---|
| Progress block: "9 of 15 held" large, "N answered without a file", "of the 5200 records: X of Y held", a pill per state with its count (not clickable) | A button per state with its count that filters (pressed), "Counts as a table", the held-back and hidden totals in words | keep the build's filters; adopt the "N of M held" headline and the per-law line once the server sends them (section 4) |
| "The biggest unknowns" list: slot title, why, links | Same, plus "N other slots wait on it", from the server | keep |
| Filter chips: All, Missing, Waiting, Problems, Confidential | State buttons (every state) and a group `<select>`; no Confidential filter | adopt the Confidential filter (small): `confidential` is already on each row |
| Rows sorted by state priority (problem, empty, waiting, then the rest) | Server order | decide (small): a stable server order is easier to find a slot in; a problem should not hide. Recommend: keep server order and open any group with a problem (already done) |
| Group as a disclosure; summary: title, "N of M held or answered", law, **"opens the ingest gate"**; a one-line note | Disclosure; summary: title, count, law, "N held back, N answered" | adopt: `opensGate` is in the payload and unused; and "held back" means a confidential file here but "held" means a file in the design's words, which reads as two different things |
| Table: slot, state, held, law, next step; a series' periods as chips; a mobile card layout | Table: slot (cardinality, closed, hidden by the profile), state (word, glyph, problem, periods, two holders), files, required by, next step; stacked cards under 720 px | matches |
| "writes through Key documents" under a recorded-instrument slot | Not shown | adopt (small): handoff-record-intake says there is no second writer; the line tells the person which |
| Eleven state words with glyphs (`SlotWord`), including **held** as a state | Ten states plus a "held back" badge on a holder | keep (the build's reading is the spec's table: held describes a file's level, not a slot's progress) |
| Drive banner above the list when not connected or the scope is missing, with the command | Only inside the chooser (`NotConnected`) | adopt (small): `driveConnected` is already on the list's payload |
| "Every slot is held or answered. The gates are jason's reading..." | Not shown | adopt (small), with the flag computed by the server |
| Slot page order: **wrong-slot alert first**, the Recitation, holders, collision, split proposal, folder binding, candidates, waiting, answer, existence, "Is there another?", acts, trail | "What requires it" (citation chips and "words come from `jason cite`"), collisions, holders (the wrong-slot alert inside its holder card), your answer, choose a file, bound folders, candidates, standing, history, terminal commands | adopt the first two: lift the wrong-slot alert above everything (it is `role="alert"` and the spec says first), and recite the law with `Recitation` (section 4, `requires[].recital`) |
| Holder card: `Doc` chip, who and when, a pending list of steps while it reads, the four-line reading (`PickReading`), `ReadingLabel` | `HolderCard` with `Reading` (the four lines, preflight facts, findings, a changed-file diff), `JobWatch` (queued, running, done, failed, cancelled), Read, Replace, Unpin, Keep, Repin, Acknowledge | keep |
| `CollisionNote`: two holders, each with where it comes from and a "This is current" `Confirm` | An alert naming both holders; "Unpin the one that is not current"; the server answers "not built yet" to the `current` act | keep for now; the design shows what the `current` act should look like once the backend writes it (the patch for the profile named in the result) |
| `SplitProposal`: parts with checkbox, kind, tier, pages, slot, a note ("a newer version is offered; nothing is replaced"), link "Open it in the splitter", "It is one document" | `SplitPanel`: each part with pages, slot choice and collisions, decline | adopt the link to the splitter (small): the split's entry from a slot is a join the splitter doc lists as phase 5 |
| `FolderBinding` card: file counts (read, here, elsewhere, nowhere), a file that reads as another slot's kind is offered for that slot, the proposed sync rule as a patch command | Bound folders list ("candidates, never pins"), the proposed rule's text in the bind preview | keep; adopt the counts line when the server sends them (the sample payload in the handoff has `read`, `here`, `elsewhere`, `nowhere`) |
| Existence answer inline: a radio group in the question's words ("Does the association hold one for each year?"), the field that fits each answer, one `Confirm` | A button opens `AnswerPanel` (none, not applicable, waiting, with the note rules) | adopt the question's words (small); the panel's flow can stay |
| "Is there another?": "Three amendments are pinned. Is there another? Yes / No, this is all" | "There is another" and "This is all" buttons | adopt the count in the question (small) |
| Acts row: Choose from Drive, Paste a link, From this computer, Unpin | Same three, plus **Bind a Drive folder** | keep |
| Dialog: a source tab row; Drive tab with the account line, a drive `<select>`, a live search over the account, breadcrumb, `listbox` with `aria-multiselectable` for a slot that takes several, jason's note on each row, a cannot-open row disabled with why, a shared drive jason is not in, an empty search; a footer "N files selected for X" and Pick | Same tabs (arrow keys, Home, End); a search by POST, breadcrumb, shared drives as links, **Show more**, a **radio group (one file)**, jason's notes, unreadable rows disabled, "Choose this folder for X", the footer, focus return, Escape says "Nothing was picked" | keep (the search never puts a name in a web address); adopt multi-select for a slot that takes several, once the writer takes more than one file (section 4) |
| "Paste a link": a Find it button, found, folder, not Drive, cannot open | The same, read-only, read aloud | matches |
| "From this computer": "up to **25 MB**", hash first 12, "kept in jason's store, not sent anywhere" | The cap from `upload.max_bytes` (`GET /api/limits`), the once-only override for the administrator with a reason | keep: the design's 25 MB is an invented figure. Tell the design |
| Not signed in and scope missing as tweaks (with `jason login`, `jason drive --login`) | `NotConnected`: the server's sentence and command | matches; the build has no distinct scope-missing view; add it when the server says which scopes were granted |
| Trail: date and a sentence | Table of day, who, act, pin; never emptied | keep |
| (Not in the design) standing block (duties, conflicts, programs), Replace, Read with a job, Keep with a reason, Repin, Acknowledge, terminal commands, caveats, history | Built | keep; tell the design these exist |

### Limits

The sixth cut has no Limits page, and nothing else in the folder draws the limits table, a "Why" disclosure, the editor with a preview and a confirm, or the nearest-value button (the only mention of a limit is the chooser's invented "25 MB"). Verdict: **keep the build** ([screens/limits.md](screens/limits.md)); ask the design for its pass, and tell it the table's columns (the limit, what is in effect in words, source word and glyph, allowed range, last change, actions) and the two scopes (Setup and Instance).

### Brand, theme and foundations

`design-foundations/` (attention ladder, line language, Lucide subset pinned to one version, roles, theme presets), `glyphs/` and `community-profile/` are carried in. The glyphs the two pages use (undo, redo, sparkles, lock, copy, split, circle-dashed, list-checks, eye-off, hourglass, folder-open, ban, triangle-alert, chevron-right, file-text, link, upload, folder, search, check) are all in `ui/src/lib/glyphData.ts`. There is no earlier copy to compare, so a change since the fifth cut cannot be listed; the only difference found that touches the built screens is the colour of a suggestion (above).

## 2. What to adopt, in order of value

| # | Adoption | Files | Size | Risk |
|---|---|---|---|---|
| 1 | **Lift the wrong-slot alert to the top of the slot page** and recite the law with `Recitation` in "What requires it" (needs the recital from the server, gap B1) | `ui/src/views/RecordsView.tsx` (`SlotScreen`, `WrongSlotNotice`), `records.css`; backend `src/jason/tasks/record_slots.py` | S for the alert, M with the recital | Low. The alert already has `role="alert"`; the recital is the AGENTS rule "recite the rule" |
| 2 | **Segment bands in the album**: break the row at each segment start, a header line (number, range, title, source of the start), alternate tint, a gap | `ui/src/views/PageGrid.tsx`, `splitWindow.ts` (rows are no longer closed-form: use prefix sums over the segments), `split.css`, `splitwindow.test.ts`, `split.test.tsx` | L | Medium to high: the scroll length, "the page in view stays in view" on a view switch, and the 3,000-page live-element test all rest on the closed-form row arithmetic. Keep fixed-size cells and add fixed-height header rows so it stays arithmetic |
| 3 | **Suggestions in the accent, dashed** (tag, border, rail rows, ticks), not `--warn` | `ui/src/views/split.css` (lines for `data-sug`, `.split-sug-tag`, `.tick-sug`, `.split-row-item[data-kind="sug"]`, `.split-menu-why`) | S | Low. The word "Suggested, High" and the dash already carry the meaning, so contrast is the only check |
| 4 | **Review: show the kind as a guess** in each part (and a glyph on a flagged row); keep the title field | `ui/src/views/SplitReview.tsx`, `split.css`, `split.test.tsx` | S | Low. Say "(a guess)" and never fill a field the person did not touch |
| 5 | **The list's small readings**: the gate a group opens in its summary; "N of M held or answered" in place of "held back"; the Drive-not-connected banner; the "every slot is held or answered" line; the Confidential filter; the "writes through Key documents" line | `RecordsView.tsx` (`ChecklistScreen`), `recordTypes.ts`, `records.test.tsx`; backend for the all-answered flag | S each | Low |
| 6 | Existence question and "Is there another?" in the design's words (with the count) | `RecordActs.tsx`, `RecordPanels.tsx`, `RecordsView.tsx` | S | Low |
| 7 | Accept-at-High in the rail's suggestion header; **Review and split** on the phone sheet bar; "what it will do" lines | `ui/src/views/SplitEditor.tsx`, `SplitRail.tsx` | S | Low |
| 8 | Compare pane beside the pages at 1200 px and wider, stacked below | `split.css`, `SplitEditor.tsx` | S | Low |
| 9 | Demo states: `#/setup/split/demo?state=offline` and `?state=conflict`, `?confidential=1`, so each state can be looked at with no server | `splitDemo.ts`, `SplitView.tsx`, `split.test.tsx` | S | Low |
| 10 | Multi-select in the Drive chooser for a slot that takes several, as a `listbox` with `aria-multiselectable` (the handoff asks for it) | `DriveChooser.tsx`, `RecordPanels.tsx`; backend `record_slots.write` | M | Medium: one confirm for N picks must be N pins or one act with N files, and a collision in one of them must not stop the others |
| 11 | Rail flags per segment (slot already filled, duplicate, may hold more than one document) | `SplitRail.tsx`, `SplitEditor.tsx` | M | Medium: needs the review's collisions and duplicates before the review (gap B3) and a "more than one document" reading from the segmentation (gap B4) |
| 12 | Sort rows by problem first, per group | `RecordsView.tsx` | S | Low, but see the decision in section 3 |

Nothing to adopt for Limits.

## 3. The open questions, answered

The design answered three for itself ("jason's chooser only; groups by gate; a group's summary is N of M held or answered, never a status"). The recommendation column is what to do in the build.

| Question | Design's answer | Build today | Recommendation |
|---|---|---|---|
| **Autosave granularity** | One simulated save about 0.9 s after the last change; the state word moves from "Saving…" to "Draft saved 10:42"; Review waits for it | Each act is sent in order with its version; the server holds the undo stack; the state word is the same | Keep the build's per-act queue (the server's undo stack needs each act). The spec's "one request per 1.5 s of quiet" is superseded; update [../pdf-splitter.md](../pdf-splitter.md) 5.9 |
| **Rail below 1200 px** | Hidden; a bottom sheet (up to 72 vh) opened from a bar with the counts and the Review button | The same, 78 vh, the bar has the counts | Matches; add Review to the bar |
| **A tap on the filmstrip's strip** | Goes to the page and does not mark; Enter or the button marks | The same | Matches |
| **Accept-all threshold** | One button at High with its count; no slider | High and Medium or better, two buttons, each with its count, never a slider | Keep two buttons (a threshold slider adds a setting nobody asked for); add "Reject all below" only if testers ask |
| **Slot assignment in the review** | A "Fill record slots" choice, marked "Not in this design" | The server decides per part: fills a slot, held, collision kept in the store, duplicate skipped | Keep v1 as built. Slot assignment per part belongs on the slot page (`SplitProposal`, which already chooses a slot for each part); the splitter files to the library or holds. Add the three-way Filing choice only when the apply takes a `filing` value (gap B5), and then as the design draws it |
| **Kind guesses** | Shown as "kind: X (guess)" on each part | Not shown | Show it (adoption 4); editing it is for later |
| **The demo hook** | Three props that switch states | A route, with a page-count query | Both: add states to the route (adoption 9) |
| **The 1,600 px picture** | Not drawn | Not built; compare zooms an 800 px picture | Do not build now: the cache and renderer cost is large and the zoom is for judging "is this a first page", which 800 px does |
| **The nearest-value field in Limits** | Not designed | A "Use 200 MB" button fills the field; the person still previews and confirms | Keep. Ask the design to draw it |
| **Google's Picker** | Not used; "jason's chooser only" | Not built | **A decision for the user.** The design's answer is for the design only; the handoff names it as a person's decision (a script, a browser token and a switch on the integrations screen). Recommendation: jason's chooser only until a community asks |
| **Groups: by gate or by law** | By subject, with the gate in each summary; the summary is a count, never a status | By subject with the law; the gate not shown | Keep the server's groups, show the gate (adoption 5). "By gate" as a primary grouping would hide the law each record answers |

One more the design raises by sorting rows: whether a group lists its problems first. Recommendation: no. The order is the server's (gate, then a statute, then the key), a group with a problem opens, and a problem count shows in the summary.

## 4. What the backend cannot yet serve

| # | Gap | Where it shows | Closest thing today |
|---|---|---|---|
| B1 | `requires[].recital` (the stored words, the version in force, the caveat) on `GET /api/record-slot` | Slot page "What requires it" as a `Recitation` | `requires` is a list of citation strings; the handoff's sample shape has the recital, the task does not send it (`src/jason/tasks/record_slots.py`) |
| B2 | Group and page counts the design shows: slots that hold a file ("held" in the design's sense, not "held back"), the same for the 5200 group, an `allAnswered` flag, and a `blocks` reason per group | Progress headline, group summaries, the all-answered line | `counts.held` is confidential held-back; `answered` exists |
| B3 | A cheap per-segment flag (slot filled, duplicate) before the review | Rail flags | Only `act: review` returns collisions and duplicates |
| B4 | A "this segment may hold more than one document" reading per segment | Rail, list, review flag | The suggestions mark where a start may be; nothing marks a segment that spans a boundary jason did not suggest |
| B5 | `filing` on the apply (`held`, `library`, `slots`) and, for slots, a slot per part | The review's Filing group | The apply classifies and the review says what it did |
| B6 | Rotate on apply and a "sideways" fact | "Pages 61 and 66 are sideways; rotate them in the new files only" | `PageFact.rotation` is the PDF's rotation entry, not what is on the page; `render_page` can rotate a picture; the cut does not |
| B7 | More than one file in one `pick` (or an array of picks as one preview and confirm) | Multi-select in the chooser | One `file` per pick |
| B8 | The `current` act for a collision (the superseding data pin and a patch for the profile) | `CollisionNote` "This is current" | The server answers "not built yet" |
| B9 | A folder binding's counts (read, here, elsewhere, nowhere) and "this file reads as another slot's kind" | The binding card | Bindings list name, who and when |
| B10 | A scope-missing answer that names the scopes granted | The chooser's second not-connected state | `NotConnected` shows the server's sentence |
| B11 | The local model pass on a draft (spec 4.4) | "Check with the local model" | Not built; the control stays out |
| B12 | The named other editor on a live draft (not only on a 409) | "Another person is editing" | The conflict shows the other copy's `by` and time after a refusal |
| B13 | A measured time for the model pass | The design's "about 3 minutes for 41 pages" | Nothing measures it, so nothing may say it |

## 5. The rest of the sixth cut

| Item | Decision for the user |
|---|---|
| The fourteen fifth-cut screens | Already reconciled in [handoff-reconciliation-5.md](handoff-reconciliation-5.md). The folder carries `FIFTH-CUT.md` unchanged; confirm the files themselves are unchanged before reading them again (a hash compare against the fifth zip, if kept) |
| `FIFTH-CUT.md` known issues (a generated card page sets a white body under a dark scheme; `--stamp-tilt` lacks its kind annotation) | Still open; fix in the card template and the token file, no decision needed |
| The two new pages are not mounted in the design's own console and `HANDOFF.md` has no entry | Ask the design to mount them under Setup so the routes and the roles match the build (`#/setup/split`, `#/setup/records`) |
| The sample association in the design's theme files, brand pages and `FOUNDATIONS.md` is the real profile's name, and the checklist page's account line and domain are the profile's real domain | Ask the design to rename the sample association and use `example.org`; none of these files may enter the repo as they are (section 6) |
| Theme presets use six web fonts from a font service | Decide whether the console may load them (a request to a third party for every viewer) or the presets are limited to system fonts; the console loads no third-party script today |
| The attention ladder in `FOUNDATIONS.md` (levels 0 to 5, "jason's own findings stop at level 2", "one stop per screen") | Adopt as the written rule for new screens; audit the built screens against it as a separate job |
| Line language (solid recorded, dashed proposed, filled yours to act on) | Adopt; it is why the suggestion colour changes (adoption 3). The built `Badge` and `Timeline` markers are not yet audited against it |
| Role table (administrator holds no office; a manager cannot record a lien) | Already applied in earlier cuts; no change |
| Glyph set: Lucide pinned and vendored as a subset | Matches `glyphData.ts`; no change |
| No Limits screen | Ask the design to draw Limits (section 1) |

## 6. Content that conflicts with AGENTS.md

| Where in the design | What it does | Rule | Fix |
|---|---|---|---|
| `RecordChecklist` dialog and paste/resolve copy | Names jason's Drive account as an address on the profile's real domain | Facts are data; no association's facts in general material | Replace with `jason@example.org`; the build reads the account from the server |
| `RecordChecklist` upload tab | "up to 25 MB" is hard-coded | No invented numbers; limits come from the registry (`upload.max_bytes`) | The build shows the registry's words; the design should say "the largest file jason accepts" |
| `RecordChecklist` header | Breadcrumb "Overview › Onboarding · NAME Community Association" with the profile's real name | The same | Use a plainly fake name |
| Design theme and brand files, `FOUNDATIONS.md` | Name the profile's association as a preset | The same | Rename; keep out of the repo until done |
| `RecordChecklist` collision text | Names a path inside the profile's package as the source of a code pin | The same; code never names a profile | Say "a code pin in the profile" |
| `RecordChecklist` `RULES` | Gives statute text as sample words for four sections, marked "sample words for the design" in the recitation's own field | "Only stored words"; never quote from memory | The build recites the shelf (`jason cite`) and shows the date of the export; the sample text must not be copied |
| `SplitDocument` "More" menu | "About 3 minutes for 41 pages" | No invented numbers | Remove until the pass can measure it |
| `SplitDocument` review | "Pages 61 and 66 are sideways; rotate them", a fix the apply cannot perform | jason proposes what it can do | Hold until gap B6 |
| `RecordChecklist` | Collision "This is current" says "A patch is offered for the profile" | The profile changes only by a patch a person applies | Matches the rule; the backend does not write it yet (B8) |
| Both pages | Every write is a `Confirm` naming the person; the wait-on-someone row says "jason sent nothing; the request list writes the letter and a person sends it" | jason proposes, a person acts; sending is a person's act | Matches |
| `RecordChecklist` existence answers | Fields for where you looked and why it does not apply; empty is not none | "Missing is an answer" | Matches |
| Both pages | Names of people in sample data | Plainly fake | They are; keep them out of any fixture that is checked in with a real name |
