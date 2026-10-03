import { Card, Caveats, DataTable, DueDate, Findings, Pill, RemoteView, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { Calendar, Obligation } from "./types";

const ORDER = ["overdue", "no evidence", "due soon", "upcoming", "done late", "done", "listed", "no store shows it"];
const rank = (s: string) => { const i = ORDER.indexOf(s); return i < 0 ? ORDER.length : i; };

const cols: Column<Obligation>[] = [
  { key: "standing", header: "Standing", render: (r) => <Pill word={r.standing} meaning={r.note} />, value: (r) => rank(r.standing) },
  { key: "name", header: "Obligation" },
  { key: "authority", header: "Authority" },
  { key: "rule", header: "Rule" },
  { key: "next", header: "Next", render: (r) => <DueDate iso={r.next} />, value: (r) => r.next ?? "9999" },
  { key: "lastDone", header: "Last shown done", value: (r) => r.lastDone ?? "" },
  { key: "history", header: "Past deadlines", value: (r) => r.history.length,
    render: (r) => <Findings items={r.history.filter((h) => h.standing && h.standing !== "done").map((h) => `${h.deadline ?? h.date}: ${h.standing}${h.daysLate ? ` (${h.daysLate}d late)` : ""}`)} empty={r.history.length ? `${r.history.length} on time` : "none shown"} /> },
];

/** The recurring deadlines, overdue first. A payment is evidence a thing was done, not proof. */
export function CalendarView() {
  const r = useApi<Calendar>("/api/calendar");
  return (
    <RemoteView r={r}>
      {(d) => {
        const rows = [...d.obligations].sort((a, b) => rank(a.standing) - rank(b.standing) || (a.next ?? "9999").localeCompare(b.next ?? "9999"));
        const counts = rows.reduce<Record<string, number>>((m, o) => ((m[o.standing] = (m[o.standing] ?? 0) + 1), m), {});
        return (
          <div className="stack">
            <Card title={`Deadlines as of ${d.asOf}`} actions={<span className="row wrap">{Object.entries(counts).map(([s, n]) => <span key={s}><Pill word={s} /> {n}</span>)}</span>}>
              <DataTable rows={rows} columns={cols} searchable={false} />
            </Card>
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
