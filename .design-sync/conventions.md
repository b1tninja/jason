# Building with jason-ui

jason-ui is the component set of a read-only console for a homeowners association's board and manager. It shows
what the association's records say and never decides: a reading, a match, or a gap is a lead, not a finding.
Keep that voice in anything you build with it.

## Setup

No provider and no wrapper. Load `styles.css` once (it imports `_ds_bundle.css`); every component is styled by the
global classes and the `:root` tokens in that file. Components come from `window.JasonUI.*`. React 18. The font
is `system-ui`; there is nothing to load.

## Styling idiom: tokens and a small class vocabulary, no utility system

Colors are CSS custom properties on `:root`, with a dark variant under `prefers-color-scheme: dark`. Use them in
inline styles or small CSS; never hard-code a color.

| Token | Use |
|---|---|
| `--bg`, `--panel` | page background, card background |
| `--ink`, `--muted` | text, secondary text |
| `--line` | borders and dividers |
| `--accent` | the one action color (primary buttons, active tab) |
| `--good`, `--warn`, `--bad` | standings: done / due soon / overdue |

Layout glue is a handful of global classes from `styles.css`: `.stack` (vertical gap), `.row` + `.wrap` (flex
row), `.grid-2`, `.grid-3`, `.stats` (a stat tile row; widen with `gridTemplateColumns: "repeat(auto-fill,
minmax(200px, 1fr))"` when a tile holds six-figure money), `.muted`, `.num` (right-aligned tabular numbers),
`.chip` (an inline code chip), `.notice`, `.notice-warn`, `.notice-error`. Buttons: a bare `<button>` is the
secondary style; `className="primary"` is the one accent button; `className="link"` is a text button.

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
- **Writes**: `Confirm` (`summary`, `onConfirm`, `busy`): two clicks, the change spelled out. Use it in front of
  anything that writes.

## The console pieces (board loop, meetings, dock)

Brand tokens the theme adds, all with fallbacks: `--on-accent`, `--accent-2`, `--brand-font`, `--brand-weight`,
`--brand-case`, `--brand-tracking`, `--hero`, `--hero-ink`, `--hero-muted`, `--hero-line`. Use
`font-family: var(--brand-font, system-ui)` for a wordmark or an H1; `ScreenHeader` (`title`, `summary`, `actions`)
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
