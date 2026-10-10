import { Badge, Card, DataTable, EmptyState, Findings, IngestCitations, Pill, RemoteView, Stat, type CitationsData, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { LibraryStatus, Readings } from "./types";

function Bars({ data, total }: { data: Record<string, number>; total: number }) {
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <ul className="bars">
      {rows.map(([k, n]) => (
        <li key={k}>
          <span className="bar-label">{k}</span>
          <span className="bar" style={{ width: `${total ? (100 * n) / total : 0}%` }} aria-hidden />
          <span className="num">{n}</span>
        </li>
      ))}
    </ul>
  );
}

const readingCols: Column<Readings["readings"][number]>[] = [
  { key: "recorded", header: "Recorded" },
  { key: "number", header: "Instrument" },
  { key: "kind", header: "Kind", render: (r) => <Badge>{r.kind.replace(/_/g, " ")}</Badge> },
  { key: "title", header: "Title" },
  { key: "phase", header: "Phase" },
  { key: "pages", header: "Pages", align: "right" },
  { key: "flags", header: "Flags", value: (r) => [r.unsigned && "unsigned", r.unrecordedCopy && "unrecorded copy"].filter(Boolean).join(" "),
    render: (r) => <Findings items={[r.unsigned && "unsigned copy", r.unrecordedCopy && "unrecorded copy"].filter(Boolean) as string[]} /> },
];

export function IngestionView() {
  const lib = useApi<LibraryStatus>("/api/library-status");
  const rd = useApi<Readings>("/api/document-readings");
  const cites = useApi<CitationsData>("/api/citations?source=ingest&limit=500");
  return (
    <div className="stack">
      <RemoteView r={lib}>
        {(d) => (
          <>
            <div className="stats">
              <Stat label="Files in the library" value={d.files} hint={`${d.distinctFiles} distinct`} />
              <Stat label="Unclassified" value={d.unclassified.length} hint="no rule or model placed them" />
              <Stat label="Records covered" value={Object.keys(d.byRecord).length} hint="of the CIV 5200 kinds" />
            </div>
            <div className="grid-2">
              <Card title="How each file was classified">
                <p className="muted">Name rule, then phrase rule, then the local model. A miss after all three stays a miss.</p>
                <Bars data={d.byMethod} total={d.distinctFiles} />
              </Card>
              <Card title="By kind">
                <Bars data={d.byKind} total={d.distinctFiles} />
              </Card>
            </div>
            <Card title={`Unclassified files (${d.unclassified.length})`}>
              {d.unclassified.length ? (
                <DataTable rows={d.unclassified.map((p) => ({ path: p }))} columns={[{ key: "path", header: "Path" }]} />
              ) : (
                <EmptyState>Every file was placed.</EmptyState>
              )}
            </Card>
          </>
        )}
      </RemoteView>
      <RemoteView r={rd}>
        {(d) => (
          <Card title={`Governing and annexation extracts read (${d.count})`} actions={<Pill word={d.unreadable.length ? "unreadable" : "readable"} meaning={`${d.unreadable.length} unreadable`} />}>
            <p className="muted">What each recorded copy's text says about itself. A reading is evidence; the specification's pin is the record.</p>
            <DataTable rows={d.readings} columns={readingCols} />
            {d.unreadable.length > 0 && (
              <details>
                <summary>{d.unreadable.length} files could not be read</summary>
                <ul className="muted">{d.unreadable.map((p) => <li key={p}>{p}</li>)}</ul>
              </details>
            )}
          </Card>
        )}
      </RemoteView>
      <RemoteView r={cites}>
        {(d) => (
          <Card title={`Statutes the last ingest cites (${d.total})`}>
            <IngestCitations data={d} />
          </Card>
        )}
      </RemoteView>
    </div>
  );
}
