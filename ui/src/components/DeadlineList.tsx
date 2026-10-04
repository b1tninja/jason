import { Badge } from "./Badge";
import { Clock, type ClockStage } from "./Clock";
import { DueDate } from "./DueDate";
import { RemoteView } from "./Remote";
import { Caveats } from "./Caveats";
import { useApi } from "../lib/useApi";
import { screenLabel } from "./Dock";

/** `owners` are the offices the profile's assignments name for the duty (empty: unassigned); an older server leaves them out. */
export interface DeadlineOwner { role: string; owner: string; assignment: string; adoption: string }
export interface DeadlineRow { id: string; title: string; date: string; days: number; authority: string; standing: string; note: string; screen: string; owner?: string; owners?: DeadlineOwner[] }

function ownerWords(row: DeadlineRow): string {
  if (!row.owners) return "";
  if (!row.owners.length) return "unassigned";
  return row.owners.map((o) => o.owner + (o.adoption === "adopted" ? "" : ` (${o.adoption})`)).join(", ");
}
export interface Deadlines {
  found?: boolean; note?: string; asOf: string; today?: string;
  groups: { key: string; label: string; rows: DeadlineRow[] }[];
  clock: ClockStage[]; counts: { overdue: number; soon: number; later: number }; caveats?: string[];
}

/** The calendar's deadlines as Overdue, Next 14 days, Later, each row a DueDate, the office that owns its duty (or
 * "unassigned"), and a link to the screen that works it, with the 45 days around today as a Clock under a disclosure. The dates are what jason computed; a payment is
 * evidence a thing was done, not proof. */
export function DeadlineList({ go }: { go: (screen: string) => void }) {
  const r = useApi<Deadlines>("/api/dock?part=deadlines");
  return (
    <RemoteView r={r}>
      {(d) => {
        const today = d.today ? new Date(d.today + "T00:00:00") : undefined;
        return (
          <div className="stack dock-panel">
            <div className="row wrap">
              <Badge tone="bad">{`${d.counts.overdue} overdue`}</Badge>
              <Badge tone="warn">{`${d.counts.soon} in 14 days`}</Badge>
              <Badge>{`${d.counts.later} later`}</Badge>
            </div>
            {d.groups.map((g) => (
              <section key={g.key} className="dock-group" aria-label={g.label}>
                <h3 className="dock-h">{g.label}</h3>
                {g.rows.length === 0 && <p className="muted dock-empty">Nothing here.</p>}
                {g.rows.map((row) => (
                  <div key={row.id} className="dock-row">
                    <span className="dock-row-main">
                      <button type="button" className="link dock-link" onClick={() => go(row.screen)}>{row.title}</button>
                      <span className="dock-sub">{[row.authority, ownerWords(row), screenLabel(row.screen)].filter(Boolean).join(" · ")}</span>
                    </span>
                    <span className="dock-when"><DueDate iso={row.date} today={today} /></span>
                  </div>
                ))}
              </section>
            ))}
            <details>
              <summary className="muted dock-sub">The next 45 days as a clock</summary>
              <div className="dock-clock">{d.clock.length ? <Clock stages={d.clock} today={today} /> : <p className="muted">No deadline within 45 days.</p>}</div>
            </details>
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
