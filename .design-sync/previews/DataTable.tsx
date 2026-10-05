import { DataTable, Money, Pill, Findings } from "jason-ui";

type Row = { date: string; payee: string; amountCents: number; category: string; standing: string; findings: string[] };

const rows: Row[] = [
  { date: "2026-09-02", payee: "Valley Landscape Co.", amountCents: 185000, category: "Landscaping", standing: "ok", findings: [] },
  { date: "2026-09-05", payee: "City Water Utility", amountCents: 412377, category: "Water", findings: ["no attachment on the payment"], standing: "review" },
  { date: "2026-09-11", payee: "Pacific Elevator Service", amountCents: 96000, category: "Elevator", findings: ["amount not printed on the invoice", "possible double payment: see 2026-08-11"], standing: "review" },
  { date: "2026-09-15", payee: "Harbor Insurance Agency", amountCents: 1240000, category: "Insurance", findings: [], standing: "ok" },
  { date: "2026-09-19", payee: "Sunrise Pool Care", amountCents: 52500, category: "Pool", findings: [], standing: "ok" },
  { date: "2026-09-22", payee: "ABC Pest Management", amountCents: 18900, category: "Pest control", findings: ["other vendor on the attachment"], standing: "review" },
];

const columns = [
  { key: "date", header: "Date" },
  { key: "payee", header: "Payee" },
  { key: "amountCents", header: "Amount", align: "right" as const, render: (r: Row) => <Money cents={r.amountCents} /> },
  { key: "category", header: "Category" },
  { key: "findings", header: "Questions", value: (r: Row) => r.findings.length, render: (r: Row) => <Findings items={r.findings} empty="none" /> },
];

/** Six payments with questions for the treasurer: sortable headers, a filter box (shown when more than five rows). */
export const PaymentsWithQuestions = () => <DataTable rows={rows} columns={columns} caption="Payments, September" />;

/** Under six rows the filter box is hidden; a right-aligned money column stays tabular. */
export const SmallTable = () => (
  <DataTable
    searchable={false}
    rows={rows.slice(0, 3)}
    columns={[
      { key: "payee", header: "Payee" },
      { key: "standing", header: "Standing", render: (r: Row) => <Pill word={r.standing === "ok" ? "done" : "due soon"} /> },
      { key: "amountCents", header: "Amount", align: "right" as const, render: (r: Row) => <Money cents={r.amountCents} /> },
    ]}
  />
);

/** No rows at all: the empty state, not an empty grid. */
export const Empty = () => <DataTable rows={[] as Row[]} columns={columns} />;

type Pay = { date: string; payee: string; kind: "check" | "ach" | "card"; cents: number };
const pays: Pay[] = [
  { date: "2026-09-02", payee: "Valley Landscape Co.", kind: "check", cents: 185000 },
  { date: "2026-09-05", payee: "City Water Utility", kind: "ach", cents: 412377 },
  { date: "2026-09-11", payee: "Pacific Elevator Service", kind: "card", cents: 96000 },
  { date: "2026-09-15", payee: "Harbor Insurance Agency", kind: "ach", cents: 1240000 },
];

/** `kind: "money"` takes integer cents, right-aligns and shows dollars with no render; a `glyph` accessor puts the payment kind's mark beside the word. */
export const MoneyAndGlyphColumns = () => (
  <DataTable
    searchable={false}
    rows={pays}
    caption="Payments by kind"
    columns={[
      { key: "date", header: "Date", kind: "date" },
      { key: "payee", header: "Payee" },
      { key: "kind", header: "Kind", glyph: (r: Pay) => ({ check: "file-text", ach: "landmark", card: "banknote" } as const)[r.kind] },
      { key: "cents", header: "Amount", kind: "money" },
    ]}
  />
);
