import { Badge, Card, DataTable, Findings, Pill, RemoteView, Tabs, Timeline, type Column } from "../components";
import { useState } from "react";
import { useApi } from "../lib/useApi";
import type { AssociationRecords, Governing, Inventory, InventoryRecord, Lifecycle } from "./types";

const governingCols: Column<Governing>[] = [
  { key: "recorded", header: "Recorded" },
  { key: "number", header: "Instrument" },
  { key: "filing", header: "Filing" },
  { key: "role", header: "Role" },
  { key: "phase", header: "Phase" },
  { key: "delivery", header: "Delivery", render: (r) => <Badge>{r.delivery}</Badge> },
  { key: "status", header: "Status", render: (r) => <Pill word={r.status} meaning={r.supersededBy ? `superseded by ${r.supersededBy}` : undefined} /> },
];

const lifecycleCols: Column<Lifecycle>[] = [
  { key: "opened", header: "Opened", value: (r) => String(r.opened ?? "") },
  { key: "process", header: "Process", value: (r) => String(r.process ?? "") },
  { key: "number", header: "Instrument", value: (r) => String(r.number ?? "") },
  { key: "status", header: "Status", render: (r) => <Pill word={String(r.status ?? "")} />, value: (r) => String(r.status ?? "") },
  { key: "closed", header: "Closed", value: (r) => String(r.closed ?? "") },
];

const inventoryCols: Column<InventoryRecord>[] = [
  { key: "record", header: "Record (CIV 5200)", render: (r) => <span title={r.meaning}>{r.record.replace(/_/g, " ")}</span> },
  { key: "citation", header: "Citation" },
  { key: "retention", header: "Retention" },
  { key: "files", header: "Files", align: "right" },
  { key: "classified", header: "Classified", align: "right" },
  { key: "newest", header: "Newest" },
  { key: "gap", header: "Gap", render: (r) => (r.gap ? <Findings items={[r.gap]} /> : <Badge tone="good">kept</Badge>) },
];

function Instruments() {
  const r = useApi<AssociationRecords>("/api/association-records");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title="Governing instruments">
            <Timeline
              events={d.governing.map((g) => ({
                id: g.number, date: g.recorded, title: <>{g.filing} <span className="muted">{g.number}</span></>,
                detail: [g.role, g.phase && `phase ${g.phase}`, g.supersededBy && `superseded by ${g.supersededBy}`].filter(Boolean).join(" · "),
                tone: g.supersededBy ? "neutral" : "good",
              }))}
            />
            <DataTable rows={d.governing} columns={governingCols} />
          </Card>
          <Card title="Developer deliveries (10 CCR 2792.23)">
            <ul className="deliveries">
              {d.deliveries.map((s) => (
                <li key={s.delivery}>
                  <Badge tone={s.missing.length ? "bad" : s.found.length ? "good" : "neutral"}>{s.delivery}</Badge>{" "}
                  {s.found.length ? <span>{s.found.join(", ")}</span> : <span className="muted">none found</span>}
                  <Findings items={s.missing} ok />
                </li>
              ))}
            </ul>
          </Card>
          <Card title={`Liens the association placed (${d.placed.length})`}>
            <DataTable rows={d.placed} columns={lifecycleCols} />
          </Card>
          <Card title={`Recorded against the association (${d.against.length})`}>
            <DataTable rows={d.against} columns={lifecycleCols} />
          </Card>
          {d.unplaced.length > 0 && (
            <Card title={`Unplaced instruments (${d.unplaced.length})`}>
              <p className="muted">Recorded under the association's name and tied to no delivery or phase: read each and place it.</p>
              <DataTable rows={d.unplaced} columns={[{ key: "recorded", header: "Recorded" }, { key: "number", header: "Instrument" }, { key: "filing", header: "Filing" }, { key: "recordedBy", header: "Recorded by" }]} />
            </Card>
          )}
        </div>
      )}
    </RemoteView>
  );
}

function InventoryView() {
  const r = useApi<Inventory>("/api/records-inventory");
  return (
    <RemoteView r={r}>
      {(d) => (
        <Card title={`Records under Civil Code 5200 (${d.count})`} actions={<Badge tone={d.gaps.length ? "bad" : "good"}>{`${d.gaps.length} gaps`}</Badge>}>
          <p className="muted">Where the specification keeps each record and how many files are there. A gap is a record with nothing pinned or nothing on hand.</p>
          <DataTable rows={d.records} columns={inventoryCols} searchable={false} />
        </Card>
      )}
    </RemoteView>
  );
}

export function AssociationRecordsView() {
  const [tab, setTab] = useState("inventory");
  return (
    <Tabs
      active={tab}
      onChange={setTab}
      tabs={[
        { id: "inventory", label: "Records inventory", content: <InventoryView /> },
        { id: "instruments", label: "Recorded instruments", content: <Instruments /> },
      ]}
    />
  );
}
