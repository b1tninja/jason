# Building with jason-ui

jason-ui is the component set of a read-only console for a homeowners association's board and manager. It shows
what the association's records say and never decides: a reading, a match, or a gap is a lead, not a finding.
Keep that voice in anything you build with it.

## Setup

No provider and no wrapper. Load `styles.css` once (it imports `_ds_bundle.css`); every component is styled by the
global classes and the `:root` tokens in that file. Components come from `window.JasonUI.*`. React 18. Two faces:
`system-ui` for what is scanned (labels, tables, controls) and `var(--serif)` (Newsreader, which `styles.css` loads,
falling back to Georgia) for what is read: titles, letters, decision questions, stat figures. Figures are tabular
everywhere.

## Styling idiom: tokens and a small class vocabulary, no utility system

The look is a clerk's desk: paper on a desk, rules instead of boxes, two-pixel corners, ink chrome. Colour is spent in
three places only: the community accent on the primary button and headings, selection and focus, and status (always
with a word). The tokens are CSS custom properties on `:root`, with a dark variant under `prefers-color-scheme: dark`.
Use them in inline styles or small CSS; never hard-code a color or a radius.

| Token | Use |
|---|---|
| `--bg`, `--panel` | the desk (page background), paper (cards, tables, letters) |
| `--paper` | a second sheet: drawer heads, letter feet, chips, a hovered row |
| `--ink`, `--muted` | text and chrome, secondary text and labels |
| `--line` | hairlines inside paper (row dividers) |
| `--rule` | rules that bound a thing: card edges, table heads, the nav rail, lanes |
| `--r` | every corner (2px); never round to a pill |
| `--serif`, `--label` | the reading face; the size of small-caps labels (uppercase, +7% tracking, weight 600) |
| `--accent` | the one action color (primary buttons, active tab) |
| `--good`, `--warn`, `--bad` | standings: done / due soon / overdue |

Layout glue is a handful of global classes from `styles.css`: `.stack` (vertical gap), `.row` + `.wrap` (flex
row), `.grid-2`, `.grid-3`, `.stats` (a stat tile row; widen with `gridTemplateColumns: "repeat(auto-fill,
minmax(200px, 1fr))"` when a tile holds six-figure money), `.muted`, `.num` (right-aligned tabular numbers),
`.chip` (an inline code chip), `.notice`, `.notice-warn`, `.notice-error` (paper with one 3px edge in its tone).
Buttons: a bare `<button>` is the secondary style (ink on paper, a rule border); `className="primary"` is the one
accent button; `className="link"` is an underlined text button. A heading (`h1`-`h3`) takes the community's brand
font, else the serif.

## The components and how they fit

- **Meaning words**: `Pill` for a status or standing word (`word`, optional `meaning` for hover); its tone comes
  from the word (open/overdue/done...). `Badge` for a category or count: a single string child, tone optional.
- **Numbers**: `Money` takes integer cents (`6120` is $61.20); never pass dollars. `Stat` is a tile (`label`,
  `value`, `hint`). `DueDate` takes an ISO date and shows "in 7d" / "3d overdue"; pass `today` in tests.
- **Lists of flags**: `Findings` (`items: string[]`, `empty` text) for questions a person reads; `Evidence`
  (`items`) for records and commands cited; `Caveats` (`items`) for the tool's caveats, always visible, never
  behind a toggle.
- **Data**: `DataTable` (`rows`, `columns: [{key, header, render?, value?, align?}]`, sortable, a filter box over
  five rows). `Kanban` (`lanes`, `items`, `laneOf`, `keyOf`, `render`) for anything with a status per row; it is
  wide, give it the full width. `Timeline` (`events: [{id, date, title, detail?, tone?}]`) for dated steps.
- **Frames**: `AppShell` (`title`, `nav`, children), `Card` (`title`, `actions`, children), `Tabs` (`tabs`,
  `active`, `onChange`; controlled).
- **Remote state**: `RemoteView` takes `r` from `useApi` and a `children(data)` function; it handles loading,
  error with Retry, the tool's own `found: false` note, and a view that throws on an unexpected shape (it then
  shows the raw data). `Loading`, `ErrorNotice`, `EmptyState` are the pieces on their own.
- **Writes**: `Confirm` (`summary`, `onConfirm`, `busy`, `label`): two clicks, the change spelled out. Armed, it is
  a dashed stamp with its `label` ("Confirm", "Record", "Send") hanging on the top edge and the summary first. Use
  it in front of anything that writes.

## The console pieces (board loop, meetings, dock)

Brand tokens the theme adds, all with fallbacks: `--on-accent`, `--accent-2`, `--brand-font`, `--brand-weight`,
`--brand-case`, `--brand-tracking`, `--hero`, `--hero-ink`, `--hero-muted`, `--hero-line`. Use
`font-family: var(--brand-font, var(--serif))` for a wordmark or a heading; `ScreenHeader` (`title`, `summary`, `actions`)
already does, so start a screen with it. `ConsoleShell` (`wordmark`, `legal`, `groups`, `screens`, `current`,
`onGo`, `audience`, `onAudience`, `session`, `dock`, children) is the whole frame: grouped left nav, Board / Owner
switch, dock toolbar.

- **Letters and approvals**: `DraftLetter` (`letter`, `me`, `people`, `onStage`, `readonly`) walks draft → saved →
  awaiting approval → approved → sent, every step a `Confirm` under the person's name; the approved stage shows a
  `Command`, never a send button. `ApprovalsInbox` (`letters`, `me`, `people`, `onAction`) groups them.
  `Checklist` (`items: {label, ready}[]`) is read-only required contents; `ConfirmList` when a person must tick.
- **Meetings**: `DecisionBrief` (`decision: {question, criteria, options, facts}`) lays out lettered options and
  never recommends; put it above a `DecisionCard`. `AgendaWizard` (`plan`, `onSave`) with `ReadinessRow`
  (`candidate`) and `DriveAttach` (`files`, `onChange`) plan a meeting. `MeetingStage` (`wordmark`, `item`,
  `content`, `caption`, `progress`) is a 16:9 stage on `--hero`; `HostPanel` (`room`, `onAction`, `me`) is its
  sidebar. `RollCall` takes `present`, `recused`, `threshold`; `Clock` stages take `who`, `note`, `evidence`,
  `decision`.
- **Dock**: `DockToolbar` (`open`, `onToggle`, `counts`, `audience`) and `Drawer` (`id`, `title`, `pinned`,
  `canDock`, `onPin`, `onUnpin`, `onClose`) frame `DeadlineList`, `ActionRegister`, `Scratchpad`, `AskPanel`, each
  taking `go` and `me`. `BoardFields` (`item`, `onSaved`) and `RequestForm` (`kinds`, `onSent`) are the two
  small forms.

## The approvals engine pieces

Each takes the approvals engine's own JSON (an `Approval` with its `items`, `decisions`, `first`, `second`; audit lines;
`cite_document`'s result), so a real `jason approvals show ID --json` renders as it is.

- **The plan**: `PlanReview` (`approval`, `me`, `audit`, `recheck`, `now`, and `onDecide`/`onSubmit`/`onConfirmSecond`/
  `onDecline`/`onApply`/`onWithdraw`/`onCheck`) is the whole review. Its parts stand alone: `WriteRow` (`item`,
  `selectable`, `checked`, `onToggle`, `waits`; a checkbox only on an approvable item), `HeldNote` (`items`; "Held for the
  board" as jason's policy finding, solid, apart from "Held for the board by NAME", dashed), `ChangedBanner`
  (`approval`, `recheck`, `now`; a change blocks approval), `ApproveBar` (`approval`, `selected`, `me`; reject and hold
  need a reason; the button says "Approve 5 of 8 changes as NAME"), `SecondConfirm` (`approval`; the first signer and the
  requester are refused), `CostLine` (spread an approval: `costCents`, `summary`), `ApplyResult` (`approval`),
  `AuditLog` (`entries`, `approval`, `chain`).
- **Words and readings**: `Recitation` (`citation`, `mark`) quotes stored words whole; `ReadingLabel` (`whose`: jason,
  board, counsel, open) follows it and never stands in for it.
- **Onboarding**: `QuestionCard` (`question`, `rank`, `me`, `onAnswer`; jason's suggestion labeled, never chosen) and
  `StageSteps` (`gates`, `current`).

jason appears only as the planner ("Planned by jason, asked by NAME"); every decision, signature, and apply names a
person, and each goes through `Confirm`.

## Marks: `Glyph`, `Stamp`, `Seal`, `RoutingTag`

- **`Glyph`** (`name`, `size`, `label`): one meaning per glyph (`GLYPH_META`), always beside its word, in the text's
  colour; decorative unless `label` names one that stands alone. 16px inline, 20 in nav and buttons, 24 in headers.
- **`Stamp`** (`word`, `by`, `date`, `sentRef`, `size`, `tilt`): what a **person** decided, in the motion's own word
  (`STAMP_WORDS`: carried, failed, approved, denied, adopted, tabled, continued, referred, withdrawn, sent). `sent`
  needs `sentRef`, the record of the sending. `tilt={0}` in a table.
- **`Seal`** (`word`, `detail`, `instrument`, `date`, `inline`): what **jason** did (`SEAL_WORDS`: proposes, suggests,
  needs-approval, waiting-on, read, drafted, reminded, filed, could-not-confirm, not-sure, not-jason, wont-send). A
  county filing is `read` with its `instrument`. A gap is *not confirmed*, never a red "missing".
- **`RoutingTag`** (`owner: {role, name?, adoption?}`) and `RoutingTags` (`owners`): whose desk, from the roster the
  server resolved; "unassigned" when nothing did. Never pass words to be matched.
- Stamps and seals never share a word. There is no `draft`, `confidential`, or `recorded` mark.

## Documents: always `Doc`

A screen that names a document (a letter, a scan, a statute, a Google Doc, a PayHOA request, a recording) shows it with
`Doc`, fed a document reference, never with a raw link, an `<img>` or `<iframe>` of a file, or a path as text.

- **The reference** (`doc`): `{address, name, kind, level?, source?, readAt?, thumb?, original?, refreshable?, stale?}`.
  `address` is what jason resolves: `"file:board/minutes-draft-2099-10-21.md"`, `"drive:ID"`, `"library:ID"`,
  `"payhoa:submission:1234"`, `"CIV 4920(a)"`. `kind` is `submission`, `pdf`, `image`, `text`, `audio`, `table`, or
  `file`. `level` is `P0` to `P3`; `source` names the copy ("Recorded copy", "Drive copy", "Scan").
- **Variants**: `<Doc doc={ref} variant="chip" />` inside a sentence or a table cell; `"row"` in a list of documents;
  `"card"` (a paper thumbnail with Preview, read again, and the original's link) in a grid or a document column;
  `"inline"` when the document is the screen's subject. `DocList` (`docs`, `variant`, `title`) lists several.
- **States are words, never a broken image**: signed out, not allowed (the server's reason), needs the private view,
  no copy yet, changed in the source, not on disk. Opening is a named, logged view; a P2 or P3 inline document waits
  for "Show the document". Pass `signedIn` and `evidence` to render a state without a server.
- **Never frame Google, PayHOA, or Gmail.** The original opens in a new tab from the card. `DocumentViewer` is the
  pop-out a `Doc` opens; `PrivateSwitch` (`view`, `name`, `onOpen`) opens P3 material for a stated reason.

## Inspections, portals, and notices

Twelve pieces show what a paper points to, a vendor's report portal, a program's notice, and the life-safety watchlist. Each
takes a loader's payload as props and fetches nothing; samples are plainly fake.

- **`DocumentCodes`** (`codes`, `decoderMissing`, `installCommand`, `onOpenLink`, `onOpenPortal`) lists the QR codes read off a
  document. A link shows its host first and never opens on one click: opening is a second step that shows the host again.
- **`ReportPortalCard`** (`portal`, `onSync`, `onPlanFiling`) with `PortalReportRow` and `HoldingChips` (`holdings`): a vendor's
  public portal, each report held (library, Drive) or not filed. A protected portal is a stop for a person, never an error.
- **`FilingPlan`** (`plan`, `onConfirmFile`, `busy`, `running`) shows every row and count before the one `Confirm` that writes; a
  copy leaves the original, a move keeps the file's id, and nothing deletes.
- **`NoticeClock`** (`clock`) counts a notice's days from every date it could run from, side by side, and picks none.
- **`AssemblyRegister`** (`assemblies`, `discrepancies`) and **`Discrepancy`** (`discrepancy`) keep each source in its own column;
  a difference is shown, never settled. **`TesterCheck`** (`check`) says "listed", never certified, and shows no contact.
- **`TextGrade`** (`grade`) marks a recital as the Legislature's, official, a digest, quoted by a notice, or not found; a digest
  stays visible beside its words. **`WatchRow`** (`item`) shows overdue, unknown, partly answered, current, or not applicable:
  unknown never reads as not done. **`NotOursNotice`** marks mail for another party.
- A document in any of them is an evidence entry: a `Doc` reference, a command, or the name as text. Never build one as a link.

## One idiomatic screen

```jsx
const { Card, DataTable, Money, Pill, Findings, Caveats } = window.JasonUI;

function PaymentsWithQuestions({ payments }) {
  const columns = [
    { key: "date", header: "Date" },
    { key: "payee", header: "Payee" },
    { key: "amountCents", header: "Amount", align: "right", render: (p) => <Money cents={p.amountCents} /> },
    { key: "standing", header: "Standing", render: (p) => <Pill word={p.standing} /> },
    { key: "findings", header: "Questions", value: (p) => p.findings.length, render: (p) => <Findings items={p.findings} empty="none" /> },
  ];
  return (
    <div className="stack">
      <Card title="Payments with questions">
        <p className="muted">Each finding is a question for the treasurer; jason changes nothing in PayHOA.</p>
        <DataTable rows={payments} columns={columns} />
      </Card>
      <Caveats items={["A match is a lead, not proof."]} />
    </div>
  );
}
```
