import { daysUntil } from "./DueDate";

export interface ClockStage { key: string; label: string; date: string; authority?: string; done?: boolean }

/** A statutory timeline as stages in date order, with today's position: past stages muted, the next one marked,
 * an overdue stage (past and not done) red. Dates are the record; the page decides nothing. */
export function Clock({ stages, today }: { stages: ClockStage[]; today?: Date }) {
  const now = today ?? new Date();
  const sorted = [...stages].sort((a, b) => a.date.localeCompare(b.date));
  const nextIndex = sorted.findIndex((s) => daysUntil(s.date, now) >= 0 && !s.done);
  return (
    <ol className="clock" aria-label="timeline">
      {sorted.map((s, i) => {
        const d = daysUntil(s.date, now);
        const state = s.done ? "done" : d < 0 ? "overdue" : i === nextIndex ? "next" : "ahead";
        const when = s.done ? "done" : d === 0 ? "today" : d < 0 ? `${-d}d ago` : `in ${d}d`;
        return (
          <li key={s.key} className={`clock-${state}`} data-state={state}>
            <time dateTime={s.date}>{s.date}</time>
            <div><strong>{s.label}</strong>{s.authority && <span className="muted"> {s.authority}</span>}<div className="muted">{when}</div></div>
          </li>
        );
      })}
    </ol>
  );
}
