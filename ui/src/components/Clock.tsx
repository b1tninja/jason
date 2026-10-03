import { daysUntil } from "./DueDate";
import { Evidence } from "./Evidence";

export interface ClockStage {
  key: string;
  label: string;
  /** ISO day. A stage without one (a collection step whose day is set by the step before it) keeps its given place. */
  date?: string;
  authority?: string;
  done?: boolean;
  /** Who acts: "board", "manager", "owner", "board with counsel". */
  who?: string;
  note?: string;
  /** Records, commands, and paths the stage rests on; rendered with Evidence. */
  evidence?: string[];
  /** Where jason stops: the board decides. Marked with a warn diamond, never another color. */
  decision?: boolean;
}

export type ClockState = "done" | "next" | "ahead" | "overdue";

/** Display order: dated stages sort by date among themselves; an undated stage keeps its position in the given list
 * (it takes the slot it was given, and the dated stages fill the other slots in date order). So an undated step
 * between two dated ones stays between them, and never falls to the end. */
export function orderStages<S extends { date?: string }>(stages: readonly S[]): S[] {
  const dated = stages.filter((s) => s.date).sort((a, b) => (a.date as string).localeCompare(b.date as string));
  let d = 0;
  return stages.map((s) => (s.date ? dated[d++] : s));
}

/** A statutory timeline as stages with today's position. Markers: done filled good, next an accent ring with the
 * label in bold, ahead a line ring, overdue bad, a decision a warn diamond. Dates are the record; the page decides nothing. */
export function Clock({ stages, today }: { stages: ClockStage[]; today?: Date }) {
  const now = today ?? new Date();
  const sorted = orderStages(stages);
  const days = (s: ClockStage) => (s.date ? daysUntil(s.date, now) : null);
  // the next stage: the first not done and not already past (an undated stage is never past)
  const nextIndex = sorted.findIndex((s) => !s.done && (days(s) ?? 0) >= 0);
  return (
    <ol className="clock" aria-label="timeline">
      {sorted.map((s, i) => {
        const d = days(s);
        const state: ClockState = s.done ? "done" : d !== null && d < 0 ? "overdue" : i === nextIndex ? "next" : "ahead";
        const when = s.done ? "done" : d === null ? "" : d === 0 ? "today" : d < 0 ? `${-d}d ago` : `in ${d}d`;
        const actor = [s.who, s.authority].filter(Boolean).join(" · ");
        return (
          <li key={s.key} className={`clock-${state}${s.decision ? " clock-decision" : ""}`} data-state={state} data-decision={s.decision ? "true" : undefined}>
            <span className="clock-marker" aria-hidden="true" />
            {s.date ? <time dateTime={s.date}>{s.date}</time> : <span className="clock-undated muted">no date yet</span>}
            <div>
              <strong>{s.label}</strong>
              {s.decision && <span className="clock-decides"> the board decides</span>}
              {actor && <div className="muted clock-actor">{actor}</div>}
              {s.note && <div className="clock-note">{s.note}</div>}
              {when && <div className="muted">{when}</div>}
              <Evidence items={s.evidence} label="" />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
