import { useState } from "react";
import { Badge, Card, Caveats, Command, DataTable, RemoteView, type Column } from "../components";
import { RegisterGrid, type RegisterColumn, type RegisterLogEntry, type RegisterRow } from "../components/RegisterGrid";
import { useApi } from "../lib/useApi";
import { useHash } from "../lib/useHash";
import "./registers.css";

interface Listed {
  key: string; title: string; tab: string; confidential: boolean; about: string; columns: RegisterColumn[]; boardColumns: string[];
  snapshot: boolean; savedAt: string | null; rows: number; pending: number; notInSpecification?: boolean;
}
interface Listing { found?: boolean; note?: string; count: number; registers: Listed[]; caveats?: string[] }
interface One {
  found?: boolean; note?: string; key: string; title: string; confidential: boolean; about: string; savedAt: string | null;
  columns: RegisterColumn[]; keyColumn: string; rows: RegisterRow[]; log: RegisterLogEntry[]; pending: number; inSpecification: boolean;
  syncCommand: string; caveats?: string[];
}

function when(iso: string | null | undefined): string {
  return iso ? String(iso).replace("T", " ").slice(0, 16) : "never";
}

/** The registers the specification lists, each with whether a snapshot is on disk and when it was synced. */
export function RegisterList({ go }: { go: (key: string) => void }) {
  const r = useApi<Listing>("/api/registers");
  const cols: Column<Listed>[] = [
    { key: "title", header: "Register", render: (x) => <span className="row wrap"><button className="link" onClick={() => go(x.key)}>{x.title}</button>{x.confidential && <Badge tone="warn">confidential</Badge>}{x.notInSpecification && <Badge tone="neutral">not in the specification</Badge>}</span>, value: (x) => x.title },
    { key: "boardColumns", header: "The board writes", value: (x) => x.boardColumns.join(", "), render: (x) => x.boardColumns.length ? <span className="row wrap">{x.boardColumns.map((c) => <Badge key={c} tone="good">{c}</Badge>)}</span> : <span className="muted">nothing</span> },
    { key: "rows", header: "Rows", align: "right", value: (x) => x.rows },
    { key: "pending", header: "Pending sync", align: "right", value: (x) => x.pending, render: (x) => x.pending ? <Badge tone="warn">{String(x.pending)}</Badge> : <span className="muted">0</span> },
    { key: "savedAt", header: "Snapshot", value: (x) => x.savedAt ?? "", render: (x) => x.snapshot ? <span>{when(x.savedAt)}</span> : <span className="muted">none yet</span> },
  ];
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={`Registers (${d.count})`}>
            <p className="muted">Each register is a Google Sheet jason and the board keep together, shown here from the local snapshot the last sync saved. The board's columns are edited here and logged; jason's are read-only.</p>
            {d.registers.length === 0 ? <p className="muted">{d.note || "The specification lists no registers."}</p> : <DataTable rows={d.registers} columns={cols} searchable={false} />}
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

/** One register: its grid, the sync command, and its log. */
export function RegisterPage({ keyName, back }: { keyName: string; back: () => void }) {
  const r = useApi<One>(`/api/registers?key=${encodeURIComponent(keyName)}`);
  const [by, setBy] = useState("");
  const [pending, setPending] = useState<number | null>(null);
  return (
    <RemoteView r={r}>
      {(d) => {
        const n = pending ?? d.pending;
        return (
          <div className="stack">
            <Card title={d.title} actions={<span className="row wrap">
              {d.confidential && <Badge tone="warn">confidential</Badge>}
              {n > 0 && <Badge tone="warn">{`${n} pending sync`}</Badge>}
              <label>Your name <input aria-label="Your name" value={by} onChange={(e) => setBy(e.target.value)} placeholder="for the log" /></label>
              <button onClick={back}>All registers</button>
            </span>}>
              {d.about && <p className="muted">{d.about}</p>}
              <p className="muted">Snapshot saved {when(d.savedAt)}.{d.note ? ` ${d.note}.` : ""}{!d.inSpecification && " This register is no longer in the specification; its snapshot is shown as it was."}</p>
              <RegisterGrid registerKey={d.key} columns={d.columns} rows={d.rows} log={d.log} by={by} onSaved={() => setPending((p) => (p ?? d.pending) + 1)} />
            </Card>
            <Command cmd={d.syncCommand} note="Pushes the board's edits to the Sheet and saves a fresh snapshot. The page never runs it." />
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}

export function RegistersView() {
  const [hash, go] = useHash("registers");
  const key = hash.startsWith("registers/") ? decodeURIComponent(hash.slice("registers/".length)) : "";
  if (key) return <RegisterPage keyName={key} back={() => go("registers")} />;
  return <RegisterList go={(k) => go(`registers/${encodeURIComponent(k)}`)} />;
}
