import { useState, type ReactNode } from "react";
import { Badge, Confirm, DataTable, Pill, type Column } from "./index";
import { postJson } from "../lib/api";

export type RegisterOwner = "jason" | "board";
export type RegisterKind = "text" | "date" | "number" | "money" | "choice" | "checkbox" | "link";
export interface RegisterColumn { name: string; owner: RegisterOwner; kind: RegisterKind; choices: string[] }
export type RegisterRow = Record<string, unknown> & { pendingSync?: boolean; pendingColumns?: string[] };
export interface RegisterLogEntry { seen: string; key: string; column: string; before: unknown; after: unknown; by: string }
export interface RegisterWrite { key: string; rowKey: string; column: string; row: RegisterRow; note?: string }

/** A cell's value as text, the way the Sheet shows it. */
export function cellText(kind: RegisterKind, value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (kind === "checkbox") return value === true || String(value).toLowerCase() === "true" ? "yes" : "no";
  if (kind === "money" && typeof value === "number") return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return String(value);
}

function Show({ col, value }: { col: RegisterColumn; value: unknown }) {
  const text = cellText(col.kind, value);
  if (!text) return <span className="muted">—</span>;
  if (col.kind === "choice") return <Pill word={text} />;
  if (col.kind === "link" && /^https?:\/\//.test(text)) return <a href={text} target="_blank" rel="noreferrer">{text}</a>;
  return <>{text}</>;
}

/** The editor for one kind: a select for a choice, a checkbox, a date, a number, or text. */
function Input({ col, value, onChange }: { col: RegisterColumn; value: unknown; onChange: (v: unknown) => void }) {
  const label = col.name;
  if (col.kind === "choice")
    return (
      <select aria-label={label} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
        <option value="">(blank)</option>
        {col.choices.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
    );
  if (col.kind === "checkbox")
    return <input aria-label={label} type="checkbox" checked={value === true || String(value).toLowerCase() === "true"} onChange={(e) => onChange(e.target.checked)} />;
  if (col.kind === "date") return <input aria-label={label} type="date" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
  if (col.kind === "number" || col.kind === "money")
    return <input aria-label={label} type="number" step={col.kind === "money" ? "0.01" : "any"} value={value === null || value === undefined ? "" : String(value)} onChange={(e) => onChange(e.target.value)} />;
  return <input aria-label={label} type="text" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
}

/** One board-owned cell: shown plain until "edit", then its input and a Confirm with before → after. */
export function BoardCell({ registerKey, rowKey, col, value, by, onSaved }: {
  registerKey: string; rowKey: string; col: RegisterColumn; value: unknown; by: string; onSaved: (w: RegisterWrite) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<unknown>(value);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const before = cellText(col.kind, value), after = cellText(col.kind, draft);
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const w = await postJson<RegisterWrite>(`/api/write/registers/${encodeURIComponent(registerKey)}|${encodeURIComponent(rowKey)}`, { column: col.name, value: draft, by });
      onSaved(w);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (!open)
    return (
      <span className="rg-cell">
        <Show col={col} value={value} />
        <button className="link" aria-label={`Edit ${col.name} for ${rowKey}`} onClick={() => { setDraft(value); setOpen(true); }}>edit</button>
      </span>
    );
  return (
    <span className="rg-edit fields">
      <Input col={col} value={draft} onChange={setDraft} />
      {after === before ? (
        <button onClick={() => setOpen(false)} disabled={busy}>Cancel</button>
      ) : (
        <Confirm busy={busy} onConfirm={save} summary={<span><strong>{col.name}</strong> of {rowKey}: <code>{before || "(blank)"}</code> → <code>{after || "(blank)"}</code>. Saved in the snapshot and logged; the Sheet catches up at the next sync.</span>}>
          Save
        </Confirm>
      )}
      {after !== before && <button onClick={() => setOpen(false)} disabled={busy}>Cancel</button>}
      {error && <span className="notice notice-error">{error}</span>}
    </span>
  );
}

/** The register as a table: jason's columns plain, the board's editable per kind; the log below. */
export function RegisterGrid({ registerKey, columns, rows, log, by = "", onSaved }: {
  registerKey: string; columns: RegisterColumn[]; rows: RegisterRow[]; log: RegisterLogEntry[]; by?: string; onSaved?: (w: RegisterWrite) => void;
}) {
  const [patched, setPatched] = useState<Record<string, RegisterRow>>({});
  const keyName = columns[0]?.name ?? "";
  const shown = rows.map((r) => patched[String(r[keyName])] ?? r);
  const saved = (w: RegisterWrite) => {
    setPatched((p) => ({ ...p, [w.rowKey]: w.row }));
    onSaved?.(w);
  };
  const cols: Column<RegisterRow>[] = columns.map((c, i) => ({
    key: c.name,
    header: c.name,
    align: c.kind === "number" || c.kind === "money" ? "right" : "left",
    value: (r) => cellText(c.kind, r[c.name]),
    render: (r): ReactNode => {
      const rowKey = String(r[keyName] ?? "");
      if (i === 0) return <span className="rg-key">{rowKey}{r.pendingSync && <Badge tone="warn">pending sync</Badge>}</span>;
      if (c.owner === "board") return <BoardCell registerKey={registerKey} rowKey={rowKey} col={c} value={r[c.name]} by={by} onSaved={saved} />;
      return <Show col={c} value={r[c.name]} />;
    },
  }));
  return (
    <div className="stack register-grid">
      <p className="muted row wrap">
        {columns.map((c) => <Badge key={c.name} tone={c.owner === "board" ? "good" : "neutral"}>{`${c.name}: ${c.owner === "board" ? "the board's" : "jason's"}`}</Badge>)}
      </p>
      <DataTable rows={shown} columns={cols} caption={`${rows.length} row${rows.length === 1 ? "" : "s"}`} />
      <details className="rg-log" open={log.length > 0 && log.length <= 20}>
        <summary>Log ({log.length})</summary>
        {log.length === 0 ? <p className="muted">No changes logged yet.</p> : (
          <DataTable rows={log} searchable={log.length > 5} columns={[
            { key: "seen", header: "Seen", value: (e) => e.seen, render: (e) => <span className="muted">{String(e.seen).replace("T", " ").slice(0, 16)}</span> },
            { key: "key", header: keyName || "key" },
            { key: "column", header: "Column" },
            { key: "before", header: "Before", value: (e) => String(e.before ?? ""), render: (e) => <code>{String(e.before ?? "") || "(blank)"}</code> },
            { key: "after", header: "After", value: (e) => String(e.after ?? ""), render: (e) => <code>{String(e.after ?? "") || "(blank)"}</code> },
            { key: "by", header: "By" },
          ]} />
        )}
      </details>
    </div>
  );
}
