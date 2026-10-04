import { Card, Caveats, DataTable, DueDate, Embed, Findings, Pill, RemoteView, type Audience, type Column } from "../components";
import { useApi } from "../lib/useApi";
import { disclosureCols, type Disclosure } from "./OwnerDigestView";
import type { Calendar, Obligation } from "./types";

const ORDER = ["overdue", "no evidence", "due soon", "upcoming", "done late", "done", "listed", "no store shows it"];
const rank = (s: string) => { const i = ORDER.indexOf(s); return i < 0 ? ORDER.length : i; };

interface Embeds { found: boolean; note?: string; calendarId: string; timeZone: string }

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

/** The owner view of the annual disclosures (`GET /api/calendar?view=owner`): what every member receives each year, when
 * it is due, and the day the delivery ledger shows it went out. Not the association's deadlines (taxes, filings,
 * inspections) or their standings, which are the board's. */
export function OwnerDisclosures() {
  const r = useApi<{ found?: boolean; note?: string; asOf: string; disclosures: Disclosure[]; caveats?: string[] }>("/api/calendar?view=owner");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={`Annual disclosures as of ${d.asOf}`}>
            {d.note && <p className="muted">{d.note}</p>}
            <DataTable rows={d.disclosures} columns={disclosureCols} rowKey={(x) => x.key} searchable={false} />
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

/** The recurring deadlines, overdue first. A payment is evidence a thing was done, not proof. The owner view is
 * `OwnerDisclosures`. */
export function CalendarView({ audience = "board" }: { audience?: Audience } = {}) {
  if (audience === "owner") return <OwnerDisclosures />;
  return <BoardCalendar />;
}

function BoardCalendar() {
  const r = useApi<Calendar>("/api/calendar");
  const embeds = useApi<Embeds>("/api/embeds");
  const em = embeds.status === "ready" && embeds.data.found !== false && embeds.data.calendarId ? embeds.data : null;
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
            {em && (
              <Card title="The calendar jason writes to">
                <Embed a={{ kind: "calendar", ref: em.calendarId, title: "Association calendar", opts: { mode: "MONTH", tz: em.timeZone } }} height={520} load="mount" />
                <p className="muted">The deadlines above are what jason computed; the calendar is where <code>jason calendar --yes</code> wrote them. A viewer must already be allowed to see it.</p>
              </Card>
            )}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
