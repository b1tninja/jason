import { useState } from "react";
import { Badge, Card, Caveats, Command, ConfirmList, DataTable, DueDate, Pill, RemoteView, Stat, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";

interface Write { key: string; kind: string; target: number; label: string; value: string; why: string; confirmedBy: string; confirmedOn: string }
interface ToComplete { submissionId: number; unit: string; name: string; left: string[] }
interface Owner { unit: string; name: string; status: string; delivery: string; actions: string[] }
interface Plan {
  found?: boolean; note?: string; savedAt: string; written: boolean; summary: { currentOwners?: number; byStatus?: Record<string, number>; delivery?: Record<string, number>; deadlines?: { what: string; date: string; daysLeft: number }[] };
  writes: Write[]; pending: number; allConfirmed: boolean; toComplete: ToComplete[]; owners: Owner[]; command: string; caveats?: string[];
}

/** The owner-information cycle: the PayHOA tag writes an answer calls for, confirmed one by one, then the apply command. */
export function OwnerInfoView() {
  const r = useApi<Plan>("/api/owner-info");
  const [who, setWho] = useState("");
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState<Plan | null>(null);
  const toggle = async (key: string, confirmed: boolean) => {
    setBusy(true);
    try { setLive(await postJson<Plan>(`/api/owner-info/${encodeURIComponent(key)}`, { by: who, confirmed })); } finally { setBusy(false); }
  };
  const ownerCols: Column<Owner>[] = [
    { key: "unit", header: "Unit" }, { key: "name", header: "Owner" },
    { key: "status", header: "Standing", render: (o) => <Pill word={o.status} /> },
    { key: "delivery", header: "Notices go by" },
    { key: "actions", header: "Next action", value: (o) => o.actions[0] ?? "", render: (o) => o.actions[0] ? <Badge tone="warn">{o.actions[0]}</Badge> : <span className="muted">—</span> },
  ];
  return (
    <RemoteView r={r}>
      {(fetched) => {
        const d = live ?? fetched;
        return (
          <div className="stack">
            <div className="stats">
              <Stat label="Current owners" value={d.summary.currentOwners ?? 0} hint={`plan from ${d.savedAt.slice(0, 16).replace("T", " ")}`} />
              <Stat label="Writes planned" value={d.writes.length} hint={d.written ? "written by the last run" : `${d.pending} to confirm`} />
              <Stat label="Requests to complete" value={d.toComplete.filter((t) => t.left.length === 0).length} hint={`${d.toComplete.filter((t) => t.left.length > 0).length} need a person`} />
              {(d.summary.deadlines ?? []).map((x) => <Stat key={x.what} label={x.what} value={<DueDate iso={x.date} />} />)}
            </div>
            <Card title="Writes the answers call for" actions={<label>Confirming as <input value={who} onChange={(e) => setWho(e.target.value)} placeholder="your name" /></label>}>
              <p className="muted">Each row is one PayHOA tag change (delivery preference, paper statements, a representative) that an owner's answer or election calls for. Confirm each after reading the answer; the command appears when every row is confirmed. jason writes nothing from this page.</p>
              <ConfirmList who={who} busy={busy} rows={d.writes.map((w) => ({ key: w.key, label: `${w.kind}: ${w.label}`, detail: w.value, why: w.why, by: w.confirmedBy, on: w.confirmedOn }))} onToggle={(row, c) => toggle(row.key, c)} empty={d.written ? "The last run wrote its plan; nothing stands pending." : "PayHOA is up to date for this cycle."}>
                {d.command && <Command cmd={d.command} note="Writes the confirmed tags in PayHOA, read live again at that moment, then marks each fully recorded request complete with the board's comment." />}
              </ConfirmList>
            </Card>
            <Card title={`Owners' requests (${d.toComplete.length})`}>
              <p className="muted">An owner's PayHOA request is marked complete only once everything in it is recorded; one needing a person stays open with what is left.</p>
              <DataTable rows={d.toComplete} searchable={false} columns={[
                { key: "unit", header: "Unit" }, { key: "name", header: "Owner" }, { key: "submissionId", header: "Request" },
                { key: "left", header: "Left to do", value: (t) => t.left.length, render: (t) => t.left.length ? <ul className="findings">{t.left.map((l, i) => <li key={i}>{l}</li>)}</ul> : <Badge tone="good">fully recorded</Badge> },
              ]} />
            </Card>
            <Card title={`Owners (${d.owners.length})`}>
              <DataTable rows={d.owners} columns={ownerCols} />
            </Card>
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
