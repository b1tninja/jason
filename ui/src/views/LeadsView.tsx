import { useState } from "react";
import { Badge, Card, Caveats, DataTable, RemoteView, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { Lead, Leads } from "./types";

const cols: Column<Lead>[] = [
  { key: "kind", header: "Kind", render: (r) => <Badge tone="warn">{r.kind}</Badge> },
  { key: "title", header: "What" },
  { key: "detail", header: "Why it is a lead" },
  { key: "next", header: "A person would" },
  { key: "source", header: "From", render: (r) => <code className="chip">{r.source}</code> },
];

/** The one place every unpinned thing shows: a reading, a gap, a miss. Filter by kind; nothing here is a finding. */
export function LeadsView() {
  const r = useApi<Leads>("/api/leads");
  const [kind, setKind] = useState("");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={`Leads (${d.count})`}>
            <div className="row wrap" role="group" aria-label="Filter by kind">
              <button className={kind ? "" : "primary"} onClick={() => setKind("")}>all {d.count}</button>
              {Object.entries(d.counts).map(([k, n]) => (
                <button key={k} className={kind === k ? "primary" : ""} onClick={() => setKind(k)} aria-pressed={kind === k}>
                  {k} {n}
                </button>
              ))}
            </div>
            <DataTable rows={kind ? d.rows.filter((x) => x.kind === kind) : d.rows} columns={cols} />
            {d.notes.length > 0 && (
              <details>
                <summary>{d.notes.length} sources could not be read</summary>
                <ul className="muted">{d.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
              </details>
            )}
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
