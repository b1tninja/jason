import { Badge, Card, Caveats, DataTable, DocumentPreview, EvidenceVersion, Findings, Pill, ReadAllFromDrive, RemoteView, Tabs, Timeline, type Column, type DriveKind } from "../components";
import { useState } from "react";
import { useApi } from "../lib/useApi";
import type { AssociationRecords, Governing, GoverningDocumentRow, GoverningDocuments, Inventory, InventoryRecord, Lifecycle } from "./types";

const DRIVE_KINDS: readonly string[] = ["doc", "sheet", "slides", "pdf", "image", "drive"];
const after = (address: string | undefined, prefix: string) => (address && address.startsWith(prefix) ? address.slice(prefix.length) : "");
/** The Drive id of a row's Drive copy (its `drive:` address), or "". */
export const governingDriveId = (r: GoverningDocumentRow) => after(r.driveCopy?.address, "drive:");

/** When the document took effect, as the specification knows it: recorded, else adopted, else written. */
function dated(r: GoverningDocumentRow): string {
  return r.recorded ? `recorded ${r.recorded}` : r.adopted ? `adopted ${r.adopted}` : r.written ? `written ${r.written}` : "";
}

const governingDocCols: Column<GoverningDocumentRow>[] = [
  { key: "title", header: "Document", render: (r) => (
    <span className="stack-tight">
      <strong>{r.title}</strong>
      {r.number && <span className="muted"> {r.number}</span>}
      {r.confidential && <> <Badge tone="warn">Confidential</Badge></>}
    </span>
  ) },
  { key: "kindWord", header: "Kind", render: (r) => (r.kindWord ? <Badge>{r.kindWord}</Badge> : <span className="muted">not classified</span>) },
  { key: "recorded", header: "Recorded or adopted", value: (r) => r.recorded || r.adopted || r.written, render: (r) => dated(r) || <span className="muted">unknown</span> },
  { key: "copies", header: "Copies", value: () => "", render: (r) => (
    <DocumentPreview name={r.title} labelled path={after(r.recordedCopy?.address, "file:")} driveId={governingDriveId(r)}
      kind={(DRIVE_KINDS.includes(r.driveKind) ? r.driveKind : "doc") as DriveKind} />
  ) },
];

/** The association's governing documents, each with its copies side by side: the recorded PDF on disk (the copy that
 * governs a recorded instrument) and the Drive file (a working copy), and "Read every governing document from Drive" for
 * those with a Drive file. A confidential one is listed only in the private view; the list says how many it held back. */
export function GoverningDocumentsList({ data }: { data: GoverningDocuments }) {
  const [version, setVersion] = useState(0);
  return (
    <Card title={`Governing documents (${data.count})`}>
      <p className="muted">The recorded copy governs a recorded instrument; a Google Doc in Drive is a working copy. Each opens as jason's copy, and each view is logged.</p>
      <ReadAllFromDrive driveIds={data.rows.map(governingDriveId)} what="governing document" batch="governing" onDone={() => setVersion((v) => v + 1)} />
      {data.heldBack > 0 && <p className="muted">{data.note ?? `${data.heldBack} held back (confidential); open the private view to see them.`}</p>}
      {data.rows.length === 0 && data.note && !data.heldBack && <p className="muted">{data.note}</p>}
      <EvidenceVersion.Provider value={version}>
        <DataTable rows={data.rows} columns={governingDocCols} searchable={false} />
      </EvidenceVersion.Provider>
      <Caveats items={data.caveats ?? []} />
    </Card>
  );
}

function GoverningDocumentsTab() {
  const r = useApi<GoverningDocuments>("/api/governing-documents");
  return <RemoteView r={r}>{(d) => <GoverningDocumentsList data={d} />}</RemoteView>;
}

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
        { id: "governing", label: "Governing documents", content: <GoverningDocumentsTab /> },
        { id: "instruments", label: "Recorded instruments", content: <Instruments /> },
      ]}
    />
  );
}
