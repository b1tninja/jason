import { Glyph } from "./Glyph";
import { BasisPill } from "./BasisPill";
import { DueDate } from "./DueDate";
import { Pill } from "./Pill";
import { HELD_WORDS, runHref, type WorkRow } from "../lib/work";

/** Whose move it is, in words, for the group the run is in: "Your move: the manager", "Waiting on the member's reply". */
export function moveWords(r: WorkRow): string {
  if (r.paused) return `Paused${r.pausedReason ? `: ${r.pausedReason}` : ""}`;
  const w = r.waitingOn;
  if (!w) return "";
  const detail = w.detail ? ` (${w.detail})` : "";
  if (r.group === "yours") return `Your move: ${w.word}${detail}`;
  if (r.group === "board") return `The board decides; ${w.role ? `the ${w.role}` : "a person"} records`;
  return `Waiting on ${w.word}${detail}`;
}

/** Whether the run is past a date the law set: the loader's own flag, or a legal date whose days are behind us. */
export const isPastLegal = (r: WorkRow): boolean => r.pastLaw || !!(r.due && r.due.legal && r.due.days !== null && r.due.days < 0);

/** One open run in the list. The whole width is the link to the run. It carries the run's own label, the step and where it
 * stands, whose move it is, the due date with its basis, and the age; never a subject, an item, or a name. A held run seen
 * outside the private view (`row.held`) carries the definition's general title and its state, and says where it opens. */
export function RunRow({ row, today }: { row: WorkRow; today?: Date }) {
  const past = isPastLegal(row);
  const c = row.current;
  const due = row.due;
  return (
    <li className={`work-row${past ? " work-row-past" : ""}`} data-run={row.id} data-held={row.held ? "true" : undefined}>
      <a className="work-row-link" href={runHref(row.definition, row.id)}>
        <span className="work-row-main">
          <span className="work-row-label">{row.label || row.id}</span>
          <span className="work-row-def muted">{row.held ? HELD_WORDS : row.definitionTitle}</span>
        </span>
        <span className="work-row-step">
          {c.title ? (row.held && !c.n ? <>{c.title}</> : <>Step {c.n} of {c.of}: {c.title}</>) : <>No open step</>}
        </span>
        <span className="work-row-move"><Pill word={row.state} /> <span>{moveWords(row)}</span></span>
        <span className="work-row-due">
          {due ? (
            <>
              <DueDate iso={due.date} today={today} />
              {due.label && <span className="muted work-row-due-label"> {due.label}</span>}{" "}
              <BasisPill basis={due.basis} label={due.basisLabel} />
              {due.cite && <span className="muted"> {due.cite}</span>}
            </>
          ) : <span className="muted">No date</span>}
          {past && (
            <strong className="work-past">
              <Glyph name="triangle-alert" size="1em" /> Past a legal date{due?.cite ? ` (${due.cite})` : ""}
            </strong>
          )}
        </span>
        <span className="work-row-age muted">
          {row.age.days === null ? "" : `open ${row.age.days} ${row.age.days === 1 ? "day" : "days"}`}
        </span>
      </a>
    </li>
  );
}
