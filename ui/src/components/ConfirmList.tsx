import type { ReactNode } from "react";

export interface ConfirmRow { key: string; label: string; detail?: string; why?: string; by?: string; on?: string }

/** A checklist a person works through; what the ticks gate (a command, a next step) shows only when every row is ticked.
 * Each tick is a confirmation with a name on it, recorded by the caller. */
export function ConfirmList({ rows, who, onToggle, busy, children, empty = "Nothing to confirm." }: {
  rows: readonly ConfirmRow[]; who: string; onToggle: (row: ConfirmRow, confirmed: boolean) => void; busy?: boolean; children?: ReactNode; empty?: string;
}) {
  if (rows.length === 0) return <p className="muted">{empty}</p>;
  const done = rows.filter((r) => r.by).length;
  const all = done === rows.length;
  return (
    <div className="confirmlist">
      <p className="muted">{done} of {rows.length} confirmed{who ? "" : " · enter your name to confirm"}</p>
      <ul>
        {rows.map((r) => (
          <li key={r.key} className={r.by ? "done" : ""}>
            <label>
              <input type="checkbox" checked={!!r.by} disabled={busy || (!r.by && !who)} onChange={(e) => onToggle(r, e.target.checked)} aria-label={`confirm: ${r.label}`} />
              <span><strong>{r.label}</strong>{r.detail && <> · {r.detail}</>}{r.why && <span className="muted"> ({r.why})</span>}</span>
            </label>
            {r.by && <span className="muted"> confirmed by {r.by}{r.on ? ` on ${r.on.slice(0, 10)}` : ""}</span>}
          </li>
        ))}
      </ul>
      {all ? children : <p className="muted">The next step appears once every row is confirmed.</p>}
    </div>
  );
}
