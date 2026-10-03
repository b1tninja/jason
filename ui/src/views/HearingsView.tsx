import { Badge, Card, DataTable, DueDate, Findings, RemoteView, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { Hearing, Hearings } from "./types";

const cols: Column<Hearing>[] = [
  { key: "start", header: "Hearing", render: (h) => <>{h.start.slice(0, 16).replace("T", " ")}{h.scheduled ? <> <Badge tone="good">zoom</Badge></> : <> <Badge>no meeting</Badge></>}</> },
  { key: "address", header: "Unit" },
  { key: "noticeBy", header: "Notice by (5855(a))", render: (h) => <>{h.noticeOn ? <Badge tone="good">{`delivered ${h.noticeOn}`}</Badge> : <DueDate iso={h.noticeBy} />}</>, value: (h) => h.noticeBy },
  { key: "decisionByIfHeld", header: "Decision by (5855(f))", render: (h) => <DueDate iso={h.decisionByIfHeld} /> },
  { key: "standing", header: "Where it stands" },
  { key: "problems", header: "Problems", render: (h) => <Findings items={h.problems ?? []} empty="none" />, value: (h) => h.problems?.length ?? 0 },
];

/** The disciplinary hearings a person planned, against the 5855 clocks. Directors only; jason never sends the notice or decides. */
export function HearingsView() {
  const r = useApi<Hearings>("/api/hearings");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <p className="notice notice-warn">Confidential: for directors. A hearing needs the notice ten days ahead and the written decision within fourteen days of the board's action. jason schedules a meeting only when a person runs the command, never sends the notice, and never decides discipline.</p>
          <Card title={`Hearings (${d.hearings.length})`}>
            <DataTable rows={[...d.hearings].sort((a, b) => b.start.localeCompare(a.start))} columns={cols} searchable={false} />
          </Card>
        </div>
      )}
    </RemoteView>
  );
}
