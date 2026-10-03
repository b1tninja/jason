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
