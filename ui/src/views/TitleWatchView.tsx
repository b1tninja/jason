import { useState } from "react";
import { Badge, Card, Caveats, DataTable, Pill, RemoteView, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { TitleRow, TitleWatch } from "./types";

const ATTENTION = ["IN_DEFAULT", "STANDS", "STANDS_ON_PRIOR", "RELEASE_DUE"];

const cols: Column<TitleRow>[] = [
  { key: "standing", header: "Standing", render: (r) => <Pill word={r.standing} meaning={r.meaning} />, value: (r) => { const i = ATTENTION.indexOf(r.standing); return i < 0 ? 9 : i; } },
  { key: "address", header: "Unit" },
  { key: "owner", header: "Named owner", render: (r) => <>{r.owner}{r.namesakeRisk && <> <span title="the filing names a bare name shared with someone else"><Badge tone="warn">namesake?</Badge></span></>}</> },
  { key: "process", header: "Filing" },
  { key: "number", header: "Instrument" },
  { key: "recorded", header: "Recorded" },
  { key: "claimant", header: "Claimant", value: (r) => r.claimant.join(", ") },
  { key: "latestStep", header: "Latest step" },
  { key: "enforceableUntil", header: "Enforceable until", value: (r) => r.enforceableUntil || "" },
];

/** Every recorded lien against where it stands on the title today. What the index shows, not a title report. */
export function TitleWatchView() {
  const [attention, setAttention] = useState(true);
  const r = useApi<TitleWatch>(`/api/title-watch?attention=${attention}`);
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={attention ? "Liens a person acts on" : "Every lien of record"}
            actions={<label><input type="checkbox" checked={attention} onChange={(e) => setAttention(e.target.checked)} /> attention only</label>}>
            <p className="row wrap">{Object.entries(d.counts).map(([s, n]) => <span key={s}><Pill word={s} /> {n}</span>)}</p>
            <p className="muted">In default, standing against the current owner, a prior owner's lien with no sale since, and a release the association owes (CIV 5685) come first.</p>
            <DataTable rows={d.rows} columns={cols} />
          </Card>
          <Caveats items={[d.note ?? ""].filter(Boolean)} />
        </div>
      )}
    </RemoteView>
  );
}
