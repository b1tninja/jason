# The form workbench: specs for the design agent

The UX that pairs with the form decomposer (`jason form-decompose PDF [--out DIR]`, being built): a person checks what
jason took apart from a PDF form, compares it with a template already in the profile, sees it re-rendered, and follows
it through the fuzzer, the layout lab, and scans read back. It is written for the design agent, in the vocabulary of
jason-ui (`.design-sync/conventions.md`). The forms themselves are in [forms.md](forms.md); the console's map is
[web-ui-decisions.md](web-ui-decisions.md). Written October 5, 2026.

## The rules the screens keep

These come from [AGENTS.md](../AGENTS.md), [forms.md](forms.md), and [web-ui-decisions.md](web-ui-decisions.md). A design
that breaks one is wrong however it looks.

- **The decomposer decides nothing.** Every title, kind, option, `ReadAs`, help line, and required flag is an
  inference with its evidence beside it. The page says "jason read this as", never "this is".
- **No legal authority, ever.** `FormQuestion.authority` and `FormTemplate.authority` stay empty in every decomposition.
  The workbench has no input for them and suggests none. The inspector shows a fixed line: "The law that asks for this
  question is added by a person, in the profile."
- **The page writes no Python and no profile file.** The `FormTemplate` source is shown for a person to copy into
  `mystique/forms.py` and review there. The only thing the page saves is the person's corrections to a decomposition,
  in jason's own store (as canvases are), through `Confirm`.
- **Commands copy, never run.** Running the decomposer, the vision pass, the fuzzer, and the lab is a `Command` block, or
  a job a person queues with `--confirm NAME` ([jobs.md](jobs.md)).
- **A reading is evidence.** A scan read back is shown for a person to confirm. It is recorded only through the
  owner-information confirmations (`#/owner-info`).
- **Never show a reader what a copy was sent with.** The scan screen shows the reading first. The comparison with what
  was sent is a separate column, after the reading, with every hint marked "+hint".
- **Model jobs are visible.** A vision pass runs `local_ai.preflight`, waits for the GPU lock, loads the model, reads,
  and unloads. Each step shows, including "waiting for the GPU" and "failed preflight: short of commit".
- **Made-up data in previews.** Fixtures use plainly fake names and the `example` domains ("Pat Example",
  "123 Main St", `pat@example.com`). No owner's answers and no profile facts go in a preview.
- **Board audience only.** None of these screens has `owner: true`. A scan's readings are personal data.

## The screen: `#/forms`

A new screen, "Forms", in the Governance group beside "Owner information" and "Templates". It starts with
`ScreenHeader` ("Forms", the summary "Take a PDF form apart, check it, and test it", no actions). Below that is a form
picker and `Tabs`:

| Tab | What it answers | Data |
|---|---|---|
| Decompose | What jason read from this PDF, and why | `/api/form-decompose?source=…` |
| Compare | How it differs from a template in the profile | the same, with `against=KEY` |
| Render | How it looks re-drawn in the form's `FormStyle` | page images from `form_render` |
| Fuzz | How its answers read back from made-up scans | `data/forms/fuzz/<form>/` |
| Lab | Which layout reads best | `data/forms/lab/` |
| Scans | What a returned scan says, field by field | `form_reader.read_scan` output |

The picker lists the profile's templates (`FormKey` members) and the decompositions on disk
(`data/forms/decompose/<slug>/`), each with its source kind. A decomposition not yet in the profile is marked
`Badge tone="warn"` "not in the profile". Picking one sets the hash (`#/forms?form=<slug>&tab=decompose`), so a shared
link lands on the same view.

## The shapes the page reads

The decomposer's report is the contract. The backend writes it beside the layout JSON as `report.json`, and a loader
in `src/jason/web/extra/` serves it. Coordinates are PDF points from the page's top left, as in `form_layout`.

```ts
type Rect = [number, number, number, number];            // x0, y0, x1, y1
type SourceKind = "fillable" | "flat" | "scanned";
type Basis = "widget" | "tooltip" | "printed" | "wording" | "font" | "geometry" | "ocr" | "model" | "person";

interface Decomposition {
  found?: boolean; note?: string;                         // RemoteView's empty state
  slug: string; savedAt: string;
  source: { path: string; kind: SourceKind; pages: number; widgets: number };
  pages: { index: number; width: number; height: number; image: string }[];  // image: a PNG under data/, for /api/file
  sections: { title: string; page: number; rect: Rect }[];
  questions: DecomposedQuestion[];
  signature: { text: string; dated: boolean; page: number; rect: Rect } | null;
  items: DetectedItem[];                                  // everything found, used or not
  warnings: DecomposeWarning[];
  python: string;                                         // the FormTemplate source, corrections applied
  layoutPath: string;                                     // the FormLayout JSON under data/
  run: { steps: RunStep[] };
  command: string;                                        // the command that made it
  caveats: string[];
}

interface DecomposedQuestion {
  key: string; number: string; title: string; section: string;
  kind: "short" | "paragraph" | "choice" | "checkbox" | "date" | "email" | "phone";
  options: { label: string; key: string; field: string }[];
  reads: "text" | "name" | "address" | "contact" | "email" | "phone" | null;
  help: string; required: boolean; lines: number;
  fields: string[];                                       // FieldBox names in the layout
  rect: Rect; page: number;                               // the question's whole area
  why: { decided: "title" | "kind" | "options" | "reads" | "help" | "required" | "lines" | "section";
         value: string; basis: Basis; detail: string }[];
  corrected: string[];                                    // which of the above a person changed
}

interface DetectedItem {
  id: string; page: number; rect: Rect;
  kind: "heading" | "title" | "help" | "line" | "text-widget" | "box" | "radio" | "signature" | "date" | "other";
  text: string; usedBy: string;                           // a question key, or "" for unused
}

interface DecomposeWarning { id: string; target: string; text: string;
  kind: "unnamed-widget" | "radio-or-boxes" | "orphan" | "low-reading" | "duplicate-title" | "no-signature" | "no-title" }

interface RunStep { step: "load" | "widgets" | "text" | "ocr" | "preflight" | "gpu" | "model" | "unload" | "infer" | "emit";
  state: "done" | "running" | "waiting" | "skipped" | "failed"; detail: string }
```

`basis` is the provenance word the console already prefers to a made-up number ([web-ui-decisions.md](web-ui-decisions.md):
"Most provenance is a method word"). The page shows no confidence score that the backend doesn't give.

The scan, fuzz, and lab tabs read shapes that already exist: `ScanReading` (`fields` with `value`, `how`, `confidence`;
`anchors`, `residual`, `reference`, `reference_how`, `notes`), the fuzz report and corpus, and the lab's
`search-<date>.jsonl` and `benchmark-<date>.json`.

## Shared vocabulary

**Item kinds on the page.** The overlay draws each kind with its own outline and a one-letter tag, so color is never the
only difference. Colors are tokens only.

| Kind | Outline | Tag | Token |
|---|---|---|---|
| Section heading | thick solid | S | `--ink` |
| Question title | solid | Q | `--accent` |
| Help line | dotted | H | `--muted` |
| Writing line or text field | solid bottom edge only | T | `--accent` |
| Check box | square, solid | ☐ | `--accent` |
| Radio group | rounded, dashed around the group | ◉ | `--accent` |
| Signature or date line | double bottom edge | ✎ | `--ink` |
| Unused (found, not part of any question) | thin dashed | ? | `--warn` |

**Basis words** are a `Badge` with no tone: "widget", "tooltip", "printed", "wording", "font", "geometry", "ocr",
"model", "person". `ocr` and `model` get `tone="warn"`, because they read from pixels. `person` marks a correction.

**Kinds and `ReadAs`** show as the enum's word, lower case, in a `Badge`: "choice", "checkbox", "reads: email".

## New components

Each entry gives the props, the states, how it behaves, and the preview cells for design-sync. Shapes are the ones
above. Every component takes data as props and fetches nothing; the views wrap them in `RemoteView`.

### `PageOverlay`

A form page as an image, with boxes drawn over it. Three tabs use it: Decompose, Render, and Scans.

- **Props:** `page: {image, width, height}`, `boxes: {id, rect, kind, label?, tone?}[]`, `selected?: string`,
  `onSelect?(id)`, `zoom?: "fit" | number`, `dim?: boolean` (fades everything but the selected box's question).
- **Behavior:**
  - The image scales to the column width, and boxes scale from points.
  - Hovering a box shows its label. Clicking selects it and calls `onSelect`.
  - The selected box gets a 2px `--accent` ring, and the page scrolls it into view when the selection changes elsewhere.
  - Zoom is fit, 100%, or 200%. At 200% the page pans by drag and by arrow keys.
  - Multi-page forms show a strip of page thumbnails above it, each with a count of its boxes and warnings.
- **Accessibility:** boxes are focusable in reading order (page, then top to bottom, then left to right). Enter selects.
  Each has an `aria-label` of the form "Q 3, question title, How should notices be delivered?".
- **States:** an image that fails to load shows `ErrorNotice` with the path. A page with no boxes shows the image and
  "nothing found on this page".
- **Preview cells:** a fillable page (inline SVG of a made-up two-question page), a flat page with an unused item, a
  selected box with `dim`, and 200% zoom. Use a `data:` SVG, not a PDF: the capture has no PDF viewer (NOTES.md).

### `QuestionOutline`

The decomposition as a numbered list, grouped under its section headings. It is the reviewer's table of contents.

- **Props:** `sections`, `questions`, `signature`, `warnings`, `selected?`, `onSelect?(key)`, `filter?: "all" | "flagged" | "corrected"`.
- **A row:** the number, the title (truncated to one line, full on hover), the kind badge, the `reads` badge when set,
  "required" in `--muted`, a `Badge tone="warn"` with the row's warning count, and a "corrected" badge when a person
  changed it.
- **The signature line** is the last row, set apart, with "dated" when the form asks for a date.
- **Behavior:** it stays in sync with `PageOverlay` in both directions. The filter is a three-button segmented control.
  Up and down move the selection.
- **Preview cells:** a two-section form of eight questions with one flagged and one corrected, "flagged" filtered, and
  an empty decomposition (the `found: false` note).

### `QuestionInspector`

One question in full: what jason read, why, and the person's corrections.

- **Props:** `question`, `items` (its detected items), `onCorrect?(key, patch)`, `busy?`, `readonly?`.
- **Layout:** a `Card` titled with the number and title. A `.fields` grid holds:
  - **Title.**
  - **Kind:** the seven `QuestionKind` words. "Choice" and "checkbox" carry a one-line explanation: one answer, or any
    number of answers.
  - **Options:** label, key, and the field each maps to. A choice question's options come from a radio group's
    on-states; a checkbox question's come from its separate boxes.
  - **Reads as:** the six `ReadAs` words and "follows the kind".
  - **Help.**
  - **Required.**
  - **Lines:** a multi-line answer's count of writing lines.
  - **Section.**
  - **Authority:** a fixed line in place of a field (see the rules).
- **The why list** sits under each field. It shows the `why` rows for that decision: the value, the basis badge, and the
  detail. For example: "choice · widget · radio group `delivery` with 3 on-states"; "reads: email · printed · the title
  contains 'email'"; "help · font · italic 9 pt line under the title". When two sources disagree, both rows show and
  the field gets a `warn` mark.
- **Corrections:**
  - Editing a field marks it changed. "Save corrections" is a `Confirm` that spells the changes out ("Kind: checkbox →
    choice; Reads as: text → name").
  - After the save, the why list adds a "person" row, and the Python source updates.
  - "Revert" restores what jason read.
  - There is no delete. A question that is not a question is marked "not a question" (its items become unused), so the
    decision is kept.
- **Merge and split:**
  - "Merge with next" joins two questions into one multi-line answer.
  - "Split" turns one box group into separate questions.
  - Both go through the same `Confirm`.
- **Preview cells:**
  - a fillable radio question with tooltip evidence;
  - a flat question with "check all that apply" wording;
  - a scanned question with `ocr` evidence and a disagreement;
  - a corrected question;
  - `readonly`.

### `ReviewQueue`

The warnings as a to-do list a person works through. Each row opens its question.

- **Props:** `warnings`, `onPick(target)`, `done?: string[]`.
- **Rows, by kind:**
  - "Field `Text12` has no name or tooltip, and no printed text near it" (unnamed widget).
  - "These 3 boxes could be one choice or separate boxes: no 'check one' wording" (radio or boxes).
  - "Box found with no question near it" (orphan).
  - "OCR read this title with low agreement" (low reading).
  - "Two questions read 'Name'" (duplicate title).
  - "No signature line found" (no signature).
- **Behavior:** clicking a row selects its question in the outline, the overlay, and the inspector. A row a person has
  corrected moves to a "handled" group but doesn't disappear. The header counts open rows: "4 to look at".
- **Not** `Findings`: those rows are plain strings that don't navigate. This has a target and a kind.
- **Preview cells:** six rows, one of each kind; two handled; none open ("nothing left to look at").

### `StepRail`

The decomposer's run as a row of steps, so a person can see what kind of source it was and where a model job stands.

- **Props:** `kind: SourceKind`, `steps: RunStep[]`.
- **Steps shown by kind:**
  - **fillable:** load → widgets → text → infer → emit.
  - **flat:** load → text → infer → emit.
  - **scanned:** load → ocr → preflight → GPU → model → unload → infer → emit. The model steps show "skipped" when no
    vision pass was asked for.
- **States:** done (`--good` tick), running (spinner and the detail: "reading page 2 of 2"), waiting (`--warn`: "waiting
  for the GPU lock: held by job 41"), skipped (`--muted`), failed (`--bad`, with the detail: "preflight: 6 GB of commit
  free, 9 GB needed"). After a model step, "unload" must show done. If it fails, the rail says the model is still
  loaded and shows `Command` `jason local-ai`.
- **Preview cells:** fillable done, flat done, scanned without a model, scanned waiting for the GPU, scanned with a
  failed preflight, scanned done.

### `SourceBlock`

The emitted Python or JSON, read-only, to copy.

- **Props:** `code`, `language: "python" | "json"`, `filename`, `note?`, `marks?: number[]` (lines a correction changed).
- **Behavior:**
  - Monospace, with line numbers. Corrected lines get a left bar in `--accent`.
  - A Copy button works like `Command`'s ("copied" for 1.5 s). No syntax-highlighting library: keywords are bold, and
    strings and comments are `--muted`.
  - A long block scrolls inside a 480px frame.
- **The note under the Python:** "Paste into `mystique/forms.py` and review it there. The authority is empty on
  purpose." The JSON block names its path under `data/`.
- **Preview cells:** a short `FormTemplate` (three questions, fake titles), the same with two marked lines, and a layout
  JSON excerpt.

### `TemplateDiff`

A decomposition compared with a template in the profile, question by question. It is the round trip: decompose a form
jason built, and the result should match the definition it was built from.

- **Props:** `rows: {status: "same" | "changed" | "added" | "missing", ours?: DecomposedQuestion, theirs?: {key, title,
  kind, options, reads, help, required, lines, section}, diffs: {field, ours, theirs}[]}[]`, `summary: {same, changed,
  added, missing}`, `against: string`.
- **Layout:**
  - A `.stats` row of the four counts. "Same" is `--good`. The others use plain numbers; they are leads, not failures.
  - Below it, a `DataTable` with one row per question: status `Pill`, number, title, and the fields that differ.
  - A row opens to a two-column field table (decomposed | in the profile), with the differing cells marked.
  - Authority is left out of the diff and noted once: "The profile's authority is not compared; the decomposer never
    reads one."
- **Matching:** by key, then by title likeness. A match by likeness says so in the row ("matched by title").
- **Preview cells:** a perfect round trip (all same), one with a kind difference and a help difference, and one with an
  added and a missing question.

### `RenderCompare`

The source page beside the same form re-drawn by `form_render` in a `FormStyle`.

- **Props:** `before: {image, width, height}`, `after: {image, width, height}`, `mode?: "side" | "slider" | "blink"`,
  `style: {write_height, line_gray, typed_size}`, `lint?: string[]`.
- **Modes:**
  - **Side:** two columns, scrolled together.
  - **Slider:** one frame with a draggable divider.
  - **Blink:** alternates every 600 ms while held, and pauses when the user prefers reduced motion.
- **Above the frames,** the style values as text: "22 pt writing space · 60% gray lines · typed 10 pt".
- **Under the frames,** the `jason form-fuzz --lint` results as `Findings`.
- **Preview cells:** side, slider at 50%, and lint with two findings (writing space under 22 pt; a monospaced label).

### `ScanReadback`

One returned scan, read against the form's layout. It is evidence for a person and is never recorded from here.

- **Props:** `page`, `layout` (field boxes), `reading: ScanReading`, `sent?: Record<string,string>` (compared after
  reading only), `selected?`, `onSelect?`.
- **The alignment strip:**
  - The printed lines matched (`anchors`) and the mean error (`residual`, points).
  - The state: "aligned" under 4 points (`MAX_RESIDUAL`), or `--bad` "not aligned: nothing read" over it.
  - Whether the page was read turned round.
  - The marker and how it was read (`reference_how`). "disagree" shows `--warn`, and the marker is not used.
- **On the page,** each field box shows its value as a small label. Marked boxes are filled with a tick. Fields read by
  the model are outlined dashed.
- **The table** (`DataTable`) has a row per field:
  - field;
  - read value;
  - how (`mark`, `ocr`, `model` badge);
  - confidence (a thin bar, plus the number to two places);
  - after hints (the value and "+hint" when changed);
  - what was sent (only when `sent` is given, in its own last column, headed "Sent (compared after reading)");
  - status: same, changed, or added.
- **Notes** from the reading show as `Caveats`. A fixed caveat says: "A reading is evidence for a person. Confirm it in
  Owner information."
- **Preview cells:**
  - a clean typed scan;
  - a handwritten scan with model readings;
  - a phone scan that did not align;
  - an edited pre-filled copy with one "+hint" and one change;
  - a marker that disagrees.

### `FuzzMatrix`

The fuzzer's report as a grid: where reading fails, by question and by how the form was filled and scanned.

- **Props:** `rows` (questions), `cols` (fill × scan profile: typed, hand, cursive, prefilled, edited × clean, office,
  home, phone, fax, upside-down), `cells: {raw, hinted, cases}`, `swallowed: number`, `onPick(row, col)`.
- **A cell** shows hinted share right as a percent, with raw → hinted on hover. Tone comes from a three-step scale: 90%
  and up uses `--good`, 70–90% `--warn`, and under 70% `--bad`. The number is always printed in the cell, so color
  isn't the only signal.
- **Swallowed changes** is a `Stat` above the grid. It must read 0. Anything else is `--bad` with "a hint replaced an
  owner's change".
- **Picking a cell** lists its failing cases (seed, what was filled, what was read) and shows `Command`
  `jason form-fuzz --replay`.
- **Preview cells:** a small 4 × 6 grid, a cell picked, and swallowed 1.

### Lab table (no new component)

The Lab tab is a `DataTable` over the lab's evaluations, with the columns of [form-design.md](form-design.md): layout,
readable, written answers, on print, outside, height, ¢ a letter. The best row gets `Badge tone="good"` "best". A row
opens a strip of the layout's sample images (`form-lab --sample`) with the responder named under each. The commands to
run more are `Command` blocks. Use `Money` for the cents column.

## The Decompose tab, put together

On a wide screen (1200px or more), three columns: `QuestionOutline` (280px), `PageOverlay` (flexible), and
`QuestionInspector` (420px). Above them, the `StepRail` and a `.stats` row:
- pages;
- questions;
- sections;
- warnings open;
- corrected.

Below them:
- `ReviewQueue`;
- `SourceBlock` (Python, then JSON, in `Tabs`);
- the `Command` that re-runs `jason form-decompose PDF --out DIR`;
- `Caveats`.

Under 1200px, the outline becomes a drawer opened from the header, and the inspector moves below the page.

Selecting anywhere selects everywhere: a row in the outline, a box on the page, a warning in the queue, or a row in the
diff.

The tab's fixed caveats:
- "Each question is jason's reading of the PDF. Check it before it goes in the profile."
- "The authority is left empty; a person adds the law that asks for a question."
- "A scanned form's titles are OCR or a model's reading and may be wrong."

## What the backend needs for this

The decomposer task should produce these. They are listed so it is built with the UI in mind:

- `report.json` in the shape above, beside the layout JSON, with a `why` row for every decision and a `warnings` list.
- A PNG of each page under `data/forms/decompose/<slug>/pages/`, for `PageOverlay` through `/api/file`.
- A corrections store (`data/forms/decompose/<slug>/corrections.json`) written through the existing
  `/api/write/<store>/<key>` route, and applied when the Python and layout are emitted. The source PDF is never changed.
- A compare function (decomposition against a `FormTemplate`) that returns `TemplateDiff`'s rows, also usable from the
  command line.
- A loader in `src/jason/web/extra/` for each tab's data, with `found: false` and a note when nothing is on disk.

## Open questions for a person

- **Scope of corrections.** Should a correction in the workbench also be offered as a Python patch, or is copying the
  regenerated source enough?
- **Where the form picker draws from.** Should it list only decompositions, or every PDF under the library's forms
  folder with a "decompose" command beside it?
- **Scans tab audience.** It shows owners' answers. Should it require the same sign-in as approvals, or is the board
  audience enough?
