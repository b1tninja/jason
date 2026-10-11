# Design brief: the splitter, seventh cut

A brief to the design project, written 2026-10-11 for the seventh cut. The sixth cut drew the splitter as a three-panel page ([reconciliation-sixth-cut.md](reconciliation-sixth-cut.md), section 1, "Split document"). Since then the build changed a great deal from live use. This brief says what the build now does, state by state, so the designer can reproduce it; what felt wrong in use and must be solved better by design; the interaction models to explore; the tokens, rules, accessibility and performance limits that bind any drawing; what to deliver; and what not to redo. It follows the pattern of [design-brief-limits.md](design-brief-limits.md) and [design-brief-forms.md](design-brief-forms.md).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, case number, or private fact, and made-up samples only ("Example Village HOA", "example-scan.pdf", "A. Operator", "123 Main St").

Sources of truth, in the order to read them: [screens/split.md](screens/split.md) (the built screen), [../pdf-splitter.md](../pdf-splitter.md) sections 3, 5.2 to 5.12 and 9.5 to 9.7 (the design and the decisions taken), [reconciliation-sixth-cut.md](reconciliation-sixth-cut.md) (what the sixth cut returned and what the build kept), and the code: `ui/src/views/SplitEditor.tsx`, `SplitMenus.tsx`, `SplitDrawer.tsx`, `SplitRail.tsx`, `SplitFlags.tsx`, `SplitReview.tsx`, `SplitPanes.tsx`, `PageGrid.tsx`, `Loupe.tsx`, `LibraryBrowser.tsx`, `split.css`. Where this brief and the code differ, the code is right; say so.

## 1. The idea, and the person

A **splitter** takes one long scanned PDF (a stack of unrelated papers) and lets a person say where each document starts. jason proposes starts from signals it can measure (a title line, a page-number restart, a blank page, a letterhead); a person marks, accepts, or rejects; the review step cuts the file into parts and files them. The original is never changed.

The person is an officer, a manager, or an administrator, at a desk with a mouse and keyboard far more often than on a phone, sitting down to work through a file of 40 to 400 pages, sometimes thousands. They know the papers; jason does not. The job is a long, repetitive, visual judgement: **is this page the first page of a new document?** The best screen is the one on which that judgement is fast and the mistakes are cheap to see and undo.

The routes, the roles, and the writes are built and are not the design's to change: `#/setup/split` (start and drafts), `#/setup/split/<id>` (a draft), `#/setup/split/demo` (a made-up draft with no server; `?pages=3000` for a long one). Board only; the owner view is refused. Every write is a person's act through `Confirm`, named. jason proposes; a person confirms.

## 2. What the build does now: a state-by-state inventory

Draw each of these, on made-up data, so the seventh cut starts from what exists. The detail is in [screens/split.md](screens/split.md); this list is the minimum a drawing must reproduce or knowingly replace. "Replace" means: say so in the note (section 10) and say why.

### 2.1 The start page (`#/setup/split`)

1. **Three source tabs:** From this computer (a file chooser; base64 up to the registry's upload limit, shown in its own words), From the library, From Drive. **Check the file** is a dry run (pages, size, the limit's words); **Open it** keeps a copy and makes a draft.
2. **Library browser.** A search box (Enter or Search), chips for kind and for source with counts (pressed shown by a check and a heavier outline), selects for Text and Drafts, a sort with a reverse button, More filters (smallest page count, changed on or after, changed on or before). A table: name (a radio), kind, pages, size, changed, text held or not, a **draft exists** badge linking to the draft. A confidential file is named by its kind and cannot be chosen outside the private view. A file this machine does not hold says so. 50 at a time, **Show 50 more**. On a phone each file is a card.
3. **Drive source.** One button opens the record chooser's dialog (Drive and Paste a link; a PDF is a radio; other types listed off with why; Escape picks nothing). Not connected: the sentence and the command a person runs.
4. **Drafts below,** with a status word (draft, confirmed, applied, stale, declined) and a link each; a confidential file's label masked as the server sent it.
5. **Refusals:** too many pages (the limit's words), over the upload limit, unreadable (encrypted or damaged), the owner view.

### 2.2 The draft: frame and layout

6. **Frame.** One column filling the window under the console's header: title, file label (masked if confidential), a summary line (pages, save state as a word, segment count, open suggestions, flagged segments), a **toolbar**, a **strip of numbered segment chips**, the **pages**, a **bottom bar** (page slider with ticks, "Go to").
7. **Toolbar.** One tab stop (arrow keys, Home, End). Menus: **Draft** (all drafts, undo, redo, save state with Retry or Restore, Review and split), **View** (the four views, scroll across, larger and smaller pages, fill the width with whole columns and the count, show suggestions, flags and rejected, focus, drawers and their side and pin, magnifier and its zoom), **Mark** (suggest, accept N at High, accept N at Medium or better, every Nth page, split on blank pages, at page-number restarts, clear all my marks with the count), **Pages** (the menu for the page in focus, find and fix sideways pages, next and previous start, first, last, jump), **Help** (the key map). Direct controls: the size slider, Undo, Redo, **Segments**, **Compare**, **Magnifier**, **Focus**, **Review and split**. A menu item that does a bulk act states its count in its own label.
8. **Focus mode** (`F`): the console's header and menu are hidden; the splitter is the window. Esc leaves it after closing anything else.
9. **Drawers.** Segments (left or right, a choice), Compare (right), Review (right; a bottom sheet on a phone). Overlay from an edge without shrinking the pages; open from the toolbar, a key (`S`, `C`), or an **edge tab** (tap, or a drag toward the pages); close on Esc, Close, the grip (tap or drag back), or the scrim. From 1200 px **Pin open** docks one drawer beside the pages, which reflow. The segments drawer opens by itself, docked, from 1400 px. The choices are kept for the tab.
10. **By width:** 1400 and up; 1200 to 1399; 720 to 1199 (drawers overlay, nothing docks); under 720 (a single **View** menu, Undo, Redo, Focus; a bottom action bar of Mark, Pages, Segments, Compare, Review and split; every drawer a full-width bottom sheet).

### 2.3 The views

11. **Album.** A windowed grid of fixed-size cells filling the width with whole columns (a slider, 64 to 220 px). Top-level documents have a 30 px **numbered band** ("Document N", "starts at page P", page count, a guess at the title) before their pages; a document's pages start on a new row; every second band is tinted and hatched. A cell has: the picture, a page number, a foot with glyph and word states, a start bar and tag ("Start N", "Nested start" as a double bar), a suggestion as a dashed accent border with "Suggested, High" (heavier dashes at High, dots at Low), a grip to drag a start, a lock on page 1, a turn glyph and "Sideways", "Measuring…" until its facts arrive.
12. **Filmstrip.** The current page large, a 96 px strip of the whole file (windowed), the slider with ticks (a start, a dashed tick per suggestion, a grey run for blanks). A tap on the strip goes to a page and does not mark; Enter marks.
13. **Scroll.** One page at a time, down or across.
14. **List.** The segments and open suggestions as rows (number, range, thumbnail, title, source, the first flag, accept and reject on a suggestion, level and title edits, merge, nest). Windowed. The phone default.
15. **Compare drawer.** This page, the page before, the first page of the segment before, previous and next page, the segment's first page, Fit, 800 px, enlarged, full screen.
16. **Magnifier.** A 220 px lens that follows the pointer over any page picture, 2 to 6 times, the cell's own picture at once and the sharp one swapped in place after 150 ms; never takes a click; `E` toggles; `Alt` and the wheel zooms; keyboard `Alt` and arrows; on touch a 350 ms hold then drag. On by default where a pointer hovers, off on touch.

### 2.4 Marking, suggestions, flags

17. **Marking.** Tap or click toggles a start; shift-click selects a range without marking; right click, `L`, or a 500 ms long press opens the page menu (start, nested start, remove, accept, reject, why, show larger, selection acts, turn, reload the picture); the grip drags a start (the grid scrolls at its edge); `[` and `]` move it a page. Page 1 is locked and says why.
18. **Suggestions.** Dashed in the accent (never the warning colour, which belongs to a clock), a reason, accept, reject, accept at High, accept at Medium or better, show rejected. Never automatic. One undo step each.
19. **Flags.** Per segment, a glyph and words: Blank only, Repeats segment N, Repeated by segment N, N sideways pages, May be over the size limit (an estimate, said to be one), Slot already filled, May hold more than one document. The rail row shows the first flag and "+2 more" opening every flag as a sentence with its acts (Go to page, Fix these N pages, Review these pages, Go to segment N). A **Review these pages** bar walks pages one at a time and marks nothing until **Mark page N as a start**.
20. **Sideways and rotate.** A measured fact: a turn glyph and the word; page menu offers Fix sideways, Turn 90, 180, 270, Do not turn. A scan with no text layer is never called sideways. Turns go to the new files only.

### 2.5 Saving, errors, review

21. **Saving states in words:** saving, saved with the time, offline (marks held on this device, Retry), not saved after a server error (kept, Retry), a 409 with both copies and **Keep mine**, **Keep theirs**, **Merge boundaries**, read only after apply, restore of held marks.
22. **Pictures:** instant local previews drawn by the browser for a file chosen on this computer ("Preview from this computer", the server's copy made in the background); the server draws for a library or Drive file. Resolution follows the displayed size (96, 200, 400, 800, 1600 px), replaced in place once the size settles. "Measuring…" until facts arrive. If the browser cannot be trusted to draw, a line says so.
23. **Review** (drawer): counts that must add up, where the new files go (As each part is labelled, Held, Library, Slots, and a per-part choice), the first page of each part (loaded only while on screen), a title field with the kind as a guess ("looks like: invoice, a guess"; hidden if confidential), the part's flags, pages to turn, pages to leave out, collisions and duplicates in words; **Preview the split** (a dry run) then one confirm labelled "Write N files as NAME"; a result listing filled, taken in by the library, held with reason, skipped, failed, turned. A note says the library does not run OCR in the request.
24. **Demo states** to draw against: the 120-page demo draft; `?pages=3000`; pages 19, 61 and 66 sideways; a segment whose slot is already full; pages 72 to 73 repeating 45 to 46; the whole file over a made-up size limit.

## 3. What felt wrong in live use (to be solved better by design)

These are the findings from using the build. Each is a problem to solve, not a description of a fix; section 5 offers models to explore, and the design may find others.

1. **Crowding.** A toolbar with five menus and seven direct controls, a chip strip, a bottom bar and a slider, all before the first page. At 1200 px the pages feel like the leftover. Which controls are used every minute (mark, advance, undo, magnify) and which once per file (suggest, every Nth, review)? The chrome should follow that split.
2. **Eye travel.** The decision (is this a first page?) is made on one page, but its evidence is elsewhere: the page before is in the compare drawer, the page's reason and flags in the segments drawer or a dialog, the count in the summary line, the save state in the summary line, the action in the toolbar. A person's eyes cross the screen for every mark. The evidence for a mark should sit next to the page being judged.
3. **Reading fine detail.** Deciding whether a page is a first page often turns on a letterhead, a date, a heading, a small "Page 1 of 3". A 200 px cell shows layout, not text. The magnifier helps, but a lens that follows the pointer hides the neighbours, covers the cell you are marking, and does not suit a keyboard or touch. The compare drawer shows the right pictures but costs a drawer.
4. **Discoverability of keys and menus.** The key map is under Help and `?`. A new person marks by click and never learns `A`, `X`, `N`, `P`, `[`, `]`, `S`, `C`, `F`, `E`. Menu items are one level deep and hold every bulk act. Which keys earn an on-screen hint where they act, and how is it shown without more noise?
5. **Phone ergonomics.** The bottom bar's five buttons are 48 px tall and fit, but a thumb cannot reach the menu bar at the top, the magnifier's hold-and-drag competes with scrolling and the long-press menu, and marking by tap is accident-prone near the edge. The phone is a review device (accept, reject, check a part), not a marking device, until the design shows otherwise. Say what it is for.
6. **"Measuring…" and server-versus-local pictures.** A cell shows a placeholder from the 16 by 16 facts picture, then the local or tiny picture, then a sharper one when the size settles, and facts (blank, sideways, flags, suggestions) arrive in chunks of 300 as the window reaches them. The result flickers: a cell changes sharpness, gains a flag, loses "Measuring…", and a segment's flag appears a second after the page was marked. How should "not known yet" be told apart from "none", and how can a picture upgrade in place with no visible change except clarity?
7. **Many flags and suggestions at once.** A 226-page file with 40 parts can carry 40 start tags, 20 suggestions, a dozen flags, several sideways pages, a repeat, and a slot already filled. Cells then wear a bar, a tag, a dashed border, a grip, a turn glyph, a lock, a page number and a foot. The rule is that nothing is colour alone, yet the sum is noise. What is shown at a glance, what on hover or focus, and what only in the segments list?
8. **The review of a 226-page file with 40 parts.** The review is a drawer with a table of 40 rows, each with a thumbnail, a title field, a kind guess, flags, a Filing choice, turns and blanks. It is long, it hides the pages, and the last look at each start is a small thumbnail. A person must be able to skim 40 parts, spot the three that need a decision, fix them, and confirm once, with the arithmetic visible and no part surprising them. The route from "the counts add up" to "write" should be short when nothing is wrong and obvious when something is.
9. **Placing the segments list.** A drawer closes when the person turns to the pages, so the structure of the file (what is where) is hidden exactly when it is needed. The chip strip is too small to read titles and ranges on 40 parts.
10. **Undo is invisible.** Undo and Redo are the server's stack, but the person cannot see what an undo will undo. After a bulk act (accept 11, clear 3) there is no visible receipt except the summary line.

## 4. Interaction models to explore

The design is asked to draw each of these on made-up data, say what it costs and what it gives, and recommend one, or a combination. A recommendation is the design's own; the build team decides whether to take it. Each must keep the pages the largest thing on screen.

### 4.1 A persistent bottom filmstrip with one big page

The current page large above (a letter fills most of the height); a persistent strip of 96 px neighbours below (not a drawer), with the segment bands visible as bars on the strip and the page before shown at the left of the big page as a half-width ghost. Marking is on the big page or the strip. Questions: what does the album become (a view, or the default for a "survey" pass)? How does it work at 1200 px, 1400 px, and on a tablet in portrait? Where do the flags and the reason go (beside the big page)?

### 4.2 A two-pane compare: the page before and the page after

Two pages side by side at a fixed size, the page and the page before (and optionally the page after), always present in a "decide" layout, with a page-turner (`N`/`P`, arrows) that advances one page and marks nothing until asked. The compare drawer's three pictures are the seed. Questions: which pairs matter (this and before; this and the first page of the segment before; this and after)? How does it show "do these two look like one document?" faster than the current compare drawer?

### 4.3 A keyboard-first cull mode

Photo-culling tools make one key mark and advance. For this task: one key says "this is a first page" and moves to the next page, another says "this is not" (or simply advance), accept and reject suggestions in the same flow, `U` undoes the last one and goes back. The pages are large; the strip shows the decisions made so far; a counter says "page 37 of 226, 12 starts so far". Questions: what is the smallest key set; how does the screen show the mode (so a person never types a key meant for another mode); how are suggestions walked ("the next suggested start" as a queue); how does the mode end and hand over to the review; how does it behave with a touch screen, where the same flow is two big buttons?

### 4.4 Magnifier placement patterns

Compare and draw: (a) the lens that follows the pointer (built); (b) a **fixed-corner viewer** that shows the spot under the pointer in a pane docked to a corner or an edge, so the cursor and the cell stay visible (built as an option); (c) a pane beside the big page that shows the top third of the page at reading size, since a first page is judged by its head; (d) a click-to-pin zoom that keeps the same spot while the person steps through pages (to compare the same corner of two pages); (e) a hold-to-peek key (Space held, or `Z`) for a keyboard user. State for each: pointer, keyboard, and touch behaviour; what it covers; and the cost in picture sizes (section 8).

### 4.5 A "document stack" metaphor for segments

Instead of numbered bands on a grid, show segments as **stacks of papers**: each document a small stack (a fan of its first, second and last page edges, a thickness for its page count), laid out left to right and top to bottom, with a stack's first page on top. Marking a start splits a stack in two; merging joins them; a nested document sits inside its parent as a smaller stack. Questions: does the stack make "how many documents, how long" faster to read than bands? How do 40 stacks of 1 to 30 pages look at 1200 px? Can a stack be opened to its pages (an inline expansion) without losing the place? Is it a view of its own, the review's body, or the segments drawer's body? It must work in the windowed model of section 8 (fixed-size stack cells are required).

### 4.6 Other models the design may propose

A split-screen with the album on the left and the big page on the right; a "queue" of only the suggested and the flagged pages; a heat strip across the top that shows where jason is unsure. Mark each as proposed.

## 5. Tokens, glyphs, and components to use

Use the console's vocabulary ([components.md](components.md), [design-brief-limits.md](design-brief-limits.md) section 4 for the attention ladder and the line language). Do not draw a component the console already has.

- **Components:** `Glyph` (the pinned Lucide subset in `ui/src/lib/glyphData.ts`; one meaning per glyph), `Pill` (a word with its tone and its attention glyph), `Badge`, `Findings` (a flag list a person reads, each row carrying the question-mark glyph; "a finding is something jason could not settle alone"), `Confirm` (every write; spelled out, naming the person), `Caveats`, `Command` and `TerminalStep` for anything a person runs.
- **Glyphs in use by the splitter today:** `lock` and `file-lock` (a locked first page, a confidential file), `circle-dashed` (proposed), `triangle-alert` (a finding that needs a look), `info`, `clock`, `refresh-cw` (reload, retry), `arrow-left-right` (turn, compare), `folder-open`, `file-text`, `pencil` (edit), `circle-check`, `ban`. If a state needs a new glyph, name it, the meaning it carries, and whether it replaces one in use.
- **Line language:** solid is recorded (a start a person marked), dashed is proposed (a suggestion), filled is yours to act on. Keep it.
- **Attention ladder:** a suggestion is proposed, not a clock; it takes the accent, never the warning colour. A flag is a lead, not an alarm; a segment that "may hold more than one document" is not red. "Measuring…" is a quiet word, not a spinner over the whole screen.
- **Tokens, not hues:** the console's theme tokens only (`--ink`, `--bg`, `--panel`, `--paper`, `--line`, `--rule`, `--accent`, `--warn`), light and dark. Fonts per [design-brief-fonts-and-theme.md](design-brief-fonts-and-theme.md).
- **Never colour alone.** Every state is a word and a glyph or a line weight. A start is a bar and the words "Start N"; a suggestion is dashed and says "Suggested" with its band; the first page of a band carries the number as words.

## 6. Rules no drawing may break

- **No invented numbers.** Every figure drawn comes from the build or is plainly a sample. The sixth cut's "About 3 minutes for 41 pages" and "up to 25 MB" were invented and are not to return. A page size limit, a picture size, or a time is the registry's or the server's word. Samples are plainly fake and listed (section 9).
- **No real facts.** No association, street, vendor, bank, case number, person. Sample files are "example-scan.pdf" and the like. A made-up document title is a kind ("Invoice", "Meeting notice"), not a party.
- **Recite the rule; label the reading.** Where the screen states why a segment may be a document (a signal, a page number restart, a title line), it says what was measured, as a reading, and whose ("jason read a title line on this page"). It never presents a guess as a fact. The kind of a part is "looks like: invoice, a guess". Where the screen quotes a limit, it uses the registry's words. No statute text is invented; any law shown comes through `Recitation` from the stored shelf.
- **jason proposes; a person confirms.** Nothing is marked, moved, turned, left out, filed, or written because of a suggestion or a flag. Accept, reject, mark, fix, and write are each a person's act. No "fix it for me", no auto-advance that marks, no default that moves pages.
- **Board only.** Officers, managers, administrators. The owner view is refused. No screen is drawn for an owner.
- **A confidential file shows no content.** Its label is masked, the kind guess and the titles are hidden, the page alt text is the page number only, and the library names it by its kind. Draw one confidential state.
- **The original is untouched.** Turns and leaves-out apply to the new files only; say so near them.
- **A missing fact is a miss.** A page whose facts have not arrived is "not measured yet", never "not blank" and never "no flags". A zero says when it was true.
- **A write is one confirm, labelled with the change** ("Write 11 files as Example Scan"), never "OK". Preview, then confirm; what is confirmed is what was previewed.
- **Never delete or hide what exists.** A rejected suggestion is hidden by a toggle, not lost.

## 7. Accessibility requirements

All of [../pdf-splitter.md](../pdf-splitter.md) 5.8 stands. The seventh cut must also show:

- **Operable without a pointer,** including cull mode, the magnifier (`Alt` and arrows), the drawers, and the review. A visible focus ring on every state, never removed.
- **Roles and names.** The grid is a grid with row and column counts; a cell is a button with a name built from facts ("Page 37, content. Starts segment 3. Press Enter to remove the start"); the slider is a `slider` with `aria-valuetext` ("Page 37 of 226, segment 3"); a drawer is a dialog or a region with a heading and moves focus in and back; a menu is a menu with the arrow keys; the lens is `role="img"` named "Magnified page N".
- **Live regions** (polite) for saving, "N suggestions found", bulk results, magnifier on or off and zoom, and the cull flow's "Marked page 37 as a start, now on page 38". Never assertive for a routine act.
- **No colour alone, no motion beyond the scroll** (`prefers-reduced-motion`: no slide, no fade, no picture cross-fade). Marker contrast 3:1 against the page in both themes, text 4.5:1.
- **Touch targets 44 px** (the drag grip and the edge tab included), and a visible handle when a page is focused.
- **Zoom and reflow.** At 200% and 320 px the list and the review work without the page scrolling sideways (the album scrolls as its own region).
- **Screen reader order.** Say where the evidence for a mark sits in reading order (the page, its facts, its flags, its suggestion reason).
- **A key map** reachable from the keyboard, and key hints that are real text, not an image.
- **Forced colours and dark mode** drawn, not assumed.

## 8. Performance constraints the design must respect

The pages are the cost. A drawing that needs one of these broken is a proposal to change the model, not a design; say which and why.

- **Windowed lists.** Only the rows in view plus two screens either side exist (about 30 to 60 cells for a 3,000-page file). Every list the design draws (album, strip, list, review, segments) must work windowed.
- **Fixed cell sizes.** The scroll length is arithmetic, not measured. Cells are fixed-size per layout; band headers are fixed-height rows (30 px). A design that needs a cell to change height with its content (a variable-height row, an inline expansion that pushes the rest down, a stack whose height depends on its page count) must propose a fixed-size alternative or say how a window of unknown heights would be computed.
- **No state per cell.** One set of handlers on the grid; a cell is a memoised element of primitives. A cell may not hold its own open/closed state, its own hover popover, or its own request.
- **Picture sizes are a ladder:** 96, 200, 400, 800, 1600 px, one server-drawn size per rung (the server's largest is 1600 px, about 190 dpi on a letter); for a file chosen on this computer, the browser draws up to 300 dpi and 3300 px. A cell asks for the rung that fits its displayed size; the memory budget caps the step (a count and a decoded-pixel budget, halved on a phone or a device with 2 GB or less). The design may not assume a native-resolution picture, a vector page, or unbounded zoom. At most six requests are in flight; a fast scroll asks for 96 px only, the rest 120 ms after it settles.
- **Facts arrive in chunks of 300** as the window reaches them. Anything the design shows from a fact (blank, sideways, repeat, flag, suggestion) must have a "not known yet" state.
- **A mark is optimistic (under 100 ms)** and saved in order with its version; the design must not wait on the server to draw a mark.
- **Budgets** ([../pdf-splitter.md](../pdf-splitter.md) 5.9): 60 fps scrolling 2,000 pages on a mid-range phone, no long task over 50 ms, no layout shift once the page count is known; 40 MB of decoded pictures on desktop, 20 MB on a phone.
- **One lens, found by a mark** (`data-loupe`); a new magnifier pattern must be one element placed with a transform, not a component per cell.

## 9. What to deliver

- **Prototype pages on made-up data,** standalone, no server, light and dark, at 375, 768, 1200 and 1440 px, in the style of the earlier cuts, with a tweaks panel for the states below. One page for each interaction model in section 4 that the design recommends, and a sketch (a drawn frame, not a working page) for those it does not.
- **A states list,** in the order of section 2, with the changes: for every state of 2.1 to 2.5, the drawing, "kept", "replaced" (and why), or "removed" (and why). Add the states the design needs and the build lacks, marked **proposed**.
- **States to draw, at minimum:** the start page with each source; a draft just opened (page count known, facts not); a draft midway (some facts, some "Measuring…"); the 226-page, 40-part case with many flags and suggestions; a segment with several flags; a sideways page; a repeated pair; a slot already filled; a confidential file; offline; a 409 conflict; the review with nothing wrong and the review with three parts needing a decision; the result of an apply with a held and a failed part; the phone in review and in cull; a cull flow from first page to hand-over; the magnifier in each placement pattern; focus mode.
- **Redlines:** spacing, sizes (touch targets, cell sizes, lens size, band height, strip height), the tokens used by name, the glyphs used by name with any new glyph and the one meaning it carries, the keys with each key's meaning, and the motion (none, or reduced-motion-safe).
- **A key map** for the recommended model: every key, its meaning, and where its hint appears on screen.
- **A list of the invented sample numbers,** so the repository can confirm none is mistaken for a registry value.
- **A short note,** in the shape of the earlier cuts' notes: what changed from the build, what is proposed and not built, each decision the design took where this brief was silent, and its answers to section 11.
- **Nothing that names an association, a street, a vendor, a bank, or a person.** Rename anything that does before it comes back.
- **Mount the pages** under Setup (`#/setup/split`, `#/setup/split/<id>`) in the design's own console so the routes and the roles match the build.

## 10. What not to redo

The build is ahead of the sixth cut's prototype on these, and a drawing that regresses them is wrong. Where the design improves one, say so in the note.

- **Do not return to a three-panel page with a permanent side rail.** The full-window layout, the focus mode, the drawers with edge handles and pin, and the chip strip came from live use: the pages need the room.
- **Keep the toolbar's single tab stop and the menus' keys** (arrows, Home, End, first letter, Esc returning focus). Keep each bulk item stating its count before it runs.
- **Keep windowing, fixed cells, and band headers as fixed-height rows.** No variable-height rows, no state per cell.
- **Keep the per-act save queue with the server's undo stack,** not a timed autosave.
- **Keep blanks and restarts as two steps** (find, then apply), because facts load in chunks.
- **Keep the suggestion's look:** dashed, in the accent, a word with its band. Not the warning colour.
- **Keep the flag model:** a glyph and a sentence, a reading and not a decision, matched by level and page range so it never shows against a segment the draft has since changed, the size flag an estimate and said to be one.
- **Keep the sideways model:** a measured fact, never claimed for a scan with no text layer, a fix only in the new files.
- **Keep the review's honesty:** the arithmetic that must add up, the preview then one labelled confirm, the Filing choice, the result listing filled, held with reason, skipped and failed, and nothing said about OCR unless the server says it.
- **Keep the 409 and offline words** (Keep mine, Keep theirs, Merge boundaries; marks held on this device).
- **Keep the pictures' ladder and the browser-drawn preview** for a file chosen on this computer. Do not assume a 1,600 px or native picture for a server draft.
- **Keep the library browser and the Drive source** on the start page (pressed chips with a check and heavier outline, the draft-exists badge, a confidential file named by its kind, the search never in a web address).
- **Keep the magnifier never taking a click,** and the touch mode's cost (the long-press menu off) stated.
- **Do not show a control that does nothing.** The local-model pass is not built; it stays out, as does "Remove page pictures" (no route).
- **Do not add a setting nobody asked for** (an accept-all threshold slider; the build has two buttons with counts).
- **Do not use the library's real names or any association fact** in a sample.

## 11. The questions to answer

Answer each in the note, with a drawing where a drawing is the answer.

1. What is the one layout for the **decision**: a page, the page before, the evidence, and the mark within one glance? What is its minimum width, and what does it become below that?
2. Which controls are **every-minute** and which are **once-per-file**, and how does the chrome change with that split (a cull mode that hides the once-per-file menus)?
3. Is **cull mode** a view, a mode the whole screen enters, or a feature of the filmstrip layout? What is the key set, how does a person know they are in it, and how does it exit to the review?
4. Where does the **segments structure** live so it is visible while marking and still leaves the pages the largest thing: a persistent strip, a docked drawer, a stack view, a second row of the filmstrip?
5. Which **magnifier placement** is the default for a mouse, for a keyboard, and for touch? When is the lens a pane rather than a follower?
6. How is **"measuring…"** drawn so a cell does not flicker (a stable placeholder, a fixed-position quiet word, a progress count in the summary line instead), and how is a **picture upgrade** shown (in place, no cross-fade, no layout change)? How is a flag that arrives late kept from jumping the layout?
7. What is the **noise budget** for a cell: the most marks a cell carries at a glance, which move to hover or focus, and which only to the segments list or the page menu?
8. How does the **review of 40 parts** skim: grouping by "nothing to decide" and "needs a decision", a keyboard route through the parts that need one, a way to see all first pages at once at readable size, and a confirm that is one step when nothing is wrong?
9. What does the **phone** do: review and accept only, a cull flow with two large buttons, or the full album? What is reachable by thumb, and where does the magnifier go?
10. How are **keys and menus discovered**: an on-screen hint beside the act, a first-use tip (once, dismissible, kept for the tab), a key legend that is always one key away? How much of it can be text rather than an overlay?
11. How is **undo made visible**: a receipt for the last act and a bulk act ("Accepted 11 suggestions. Undo"), without a toast that steals focus?
12. How should **many flags and suggestions** be summarised across the file (a heat strip, a queue of pages to review, a count by kind), as opposed to per cell?
13. Does the **document stack** metaphor beat numbered bands for the 40-part file, and in which view or panel does it earn its cost?
14. Which glyph does each state carry, and does any existing glyph carry two meanings in the splitter today (so one should be replaced)?
15. Where should the **save state** live so it is seen but not crowding the summary line, and how is a conflict told apart from an error?

## 12. Where it goes

| Part | File |
|---|---|
| The editor, the toolbar, the drawers | `ui/src/views/SplitEditor.tsx`, `SplitMenus.tsx`, `SplitDrawer.tsx`, `SplitRail.tsx`, `SplitPanes.tsx`, `splitLayout.ts`, `split.css` |
| The pages, the windowing, the pictures | `ui/src/views/PageGrid.tsx`, `splitWindow.ts`, `splitThumbs.ts`, `splitLocal.ts`, `splitPdfjs.ts` |
| The magnifier | `ui/src/views/Loupe.tsx`, `splitLoupe.ts` |
| Flags and the review | `ui/src/views/SplitFlags.tsx`, `SplitReview.tsx` |
| The start page, the library, Drive | `ui/src/views/SplitView.tsx`, `LibraryBrowser.tsx` |
| The demo | `ui/src/views/splitDemo.ts` |
| The built screen's notes | [screens/split.md](screens/split.md) |
| The design and its decisions | [../pdf-splitter.md](../pdf-splitter.md) sections 3, 5, 9.5 to 9.7 |
| What the sixth cut returned | [reconciliation-sixth-cut.md](reconciliation-sixth-cut.md) |
| The shared components and the glyphs | [components.md](components.md), `ui/src/lib/glyphData.ts` |
| The brief pattern | [design-brief-limits.md](design-brief-limits.md), [design-brief-forms.md](design-brief-forms.md) |
