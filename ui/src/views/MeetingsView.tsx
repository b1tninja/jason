import { useState } from "react";
import { Badge, Card, Caveats, DataTable, Findings, RemoteView, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { Meeting, Meetings } from "./types";

const KINDS = ["agenda", "notice", "minutes", "transcript", "recording", "summary", "chat", "attendance"];

function Has({ has }: { has: Meeting["has"] }) {
  return (
    <span className="row wrap">
      {KINDS.filter((k) => Object.keys(has).some((h) => h.startsWith(k))).map((k) => {
        const key = Object.keys(has).find((h) => h.startsWith(k))!;
        const where = Object.entries(has[key]).map(([w, n]) => `${w} ${n}`).join(", ");
        return <span key={k} title={where}><Badge tone="good">{k}</Badge></span>;
      })}
      {!Object.keys(has).some((h) => h.startsWith("minutes")) && <Badge tone="warn">no minutes</Badge>}
    </span>
  );
}

const cols: Column<Meeting>[] = [
  { key: "date", header: "Meeting" },
  { key: "titles", header: "Titles", value: (r) => r.titles.join("; ") },
  { key: "has", header: "Records on hand", render: (r) => <Has has={r.has} />, value: (r) => Object.keys(r.has).length },
  { key: "checks", header: "Checks", render: (r) => <Findings items={r.checks} empty="none" />, value: (r) => r.checks.length },
];

/** Every meeting's records and checks (minutes 30 days on, a recording held after the minutes, a transcript into executive session). */
export function MeetingsView() {
  const r = useApi<Meetings>("/api/meetings");
  const [flagged, setFlagged] = useState(false);
  return (
    <RemoteView r={r}>
      {(d) => {
        const rows = [...d.meetings].sort((a, b) => b.date.localeCompare(a.date)).filter((m) => !flagged || m.checks.length);
        return (
          <div className="stack">
            <Card title={`Meetings (${d.meetings.length})`} actions={<label><input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} /> only with checks</label>}>
              <DataTable rows={rows} columns={cols} />
            </Card>
            {!!d.scheduleGaps?.length && (
              <Card title={`Scheduled days with no record (${d.scheduleGaps.length})`}>
                <p className="row wrap">{d.scheduleGaps.map((g) => <Badge key={g} tone="warn">{g}</Badge>)}</p>
              </Card>
            )}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
