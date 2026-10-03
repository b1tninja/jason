import { Card, DataTable, EmptyState, Money, Stat, type Column } from "./components";
import { isCentsKey, titleCase } from "./lib/format";

type Row = Record<string, unknown>;
export type Digest = Record<string, unknown>;

const isRows = (v: unknown): v is Row[] => Array.isArray(v) && v.length > 0 && v.every((x) => x && typeof x === "object" && !Array.isArray(x));
const isScalar = (v: unknown): v is string | number | boolean => ["string", "number", "boolean"].includes(typeof v);

function cell(key: string, v: unknown) {
  if (typeof v === "number" && isCentsKey(key)) return <Money cents={v} />;
  if (v == null) return "";
  return isScalar(v) ? String(v) : JSON.stringify(v);
}

function columnsFor(rows: Row[]): Column<Row>[] {
  const keys = [...new Set(rows.flatMap(Object.keys))];
  return keys.map((key) => ({
    key,
    header: titleCase(key),
    align: rows.every((r) => typeof r[key] === "number") ? "right" : "left",
    render: (r: Row) => cell(key, r[key]),
    value: (r: Row) => (typeof r[key] === "number" ? (r[key] as number) : String(r[key] ?? "")),
  }));
}

/** Renders a tool result without knowing its shape: scalars become stats, row lists become tables. */
export function DigestView({ digest }: { digest: Digest }) {
  const entries = Object.entries(digest);
  const stats = entries.filter(([, v]) => isScalar(v));
  const lists = entries.filter(([, v]) => Array.isArray(v));
  return (
    <div className="stack">
      {stats.length > 0 && (
        <div className="stats">
          {stats.map(([k, v]) => (
            <Stat key={k} label={titleCase(k)} value={cell(k, v)} />
          ))}
        </div>
      )}
      {lists.map(([k, v]) => (
        <Card key={k} title={`${titleCase(k)} (${(v as unknown[]).length})`}>
          {isRows(v) ? <DataTable rows={v} columns={columnsFor(v)} /> : <EmptyState />}
        </Card>
      ))}
    </div>
  );
}
