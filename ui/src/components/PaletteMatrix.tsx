import { useId, useState } from "react";
import type { DocRef } from "../lib/docref";
import { Doc } from "./Doc";
import { EmptyState } from "./States";
import { Findings } from "./Findings";
import { Swatch, driftText, type PaintColor } from "./Swatch";

/** The schedule as the picture reader and the catalog check leave it (docs/console/handoff-unit-records.md). */
export interface PaintSchedule {
  title: string;
  source: DocRef;
  /** "Prepared for the developer, 2017-11-17". */
  prepared: string;
  schemes: number[];
  rows: {
    /** As printed: "ENTRY DOORS". */
    label: string;
    surface: string;
    note?: string;
    colors: Record<number, PaintColor>;
  }[];
  /** ISO day the catalog copy was fetched. */
  catalogFetched: string;
  unavailable?: boolean;
}

export const PAINT_CAPTION = "Screens and printers shift color. The number on the schedule governs.";
export const NO_SCHEDULE = "The association has no color schedule yet.";
export const NO_PAINT_ROW = "Not paint.";

const DAY = 86_400_000;

/** Whole days between an ISO day and `today`, or null when it is not a date. */
export function ageInDays(iso: string, today: Date = new Date()): number | null {
  const t = Date.parse(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(t) ? null : Math.max(0, Math.floor((today.getTime() - t) / DAY));
}

/** The catalog copy's age in words: "2 days old", "from today". */
export function copyAge(iso: string, today?: Date): string {
  const d = ageInDays(iso, today);
  if (d === null) return `fetched ${iso}`;
  return d === 0 ? "fetched today" : `${d} ${d === 1 ? "day" : "days"} old`;
}

/** Every color on the schedule that the check flagged or a person entered, in schedule order, as a sentence. */
export function drift(schedule: PaintSchedule): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of schedule.rows) {
    for (const n of schedule.schemes) {
      const c = row.colors[n];
      const text = c && driftText(c);
      if (text && !seen.has(text)) { seen.add(text); out.push(text); }
    }
  }
  return out;
}

/** The palette: surfaces down the left in the schedule's own printed words, schemes across, a real table with row and column
 * headers. The scheme toggle is a radio group that shows one scheme's column or all of them (the cells of the other schemes
 * stay in the table, hidden, so print shows every scheme). A row with no paint says so in words. A renamed, discontinued,
 * not-found or hand-entered color is flagged on its swatch and again in words under the table. The caption says the number
 * on the schedule governs. Under 720px each surface stacks to a card. Props only: no fetching. */
export function PaletteMatrix({ schedule, scheme, onSchemeChange, onOpenColor, today, command = "jason paint" }: {
  schedule?: PaintSchedule | null;
  /** Controlled scheme: a scheme number, or null for all. Omit to let the matrix keep it. */
  scheme?: number | null;
  onSchemeChange?: (scheme: number | null) => void;
  onOpenColor?: (color: PaintColor) => void;
  today?: Date;
  /** The command that prints and checks the schedule. */
  command?: string;
}) {
  const name = useId();
  const [own, setOwn] = useState<number | null>(null);
  if (!schedule) {
    return (
      <section className="paint-matrix paint-empty" aria-label="Color schedule">
        <EmptyState glyph="paint-bucket">{NO_SCHEDULE}</EmptyState>
        <p className="muted paint-empty-hint">Read a schedule from its scan with <code>{command}</code>.</p>
      </section>
    );
  }
  const chosen = scheme !== undefined ? scheme : own;
  const pick = (n: number | null) => { setOwn(n); onSchemeChange?.(n); };
  const shown = (n: number) => chosen === null || chosen === n;
  const flags = drift(schedule);
  const hasCopy = !!schedule.catalogFetched;
  return (
    <section className="paint-matrix" aria-label={schedule.title}>
      <header className="paint-head">
        <h3 className="paint-title">{schedule.title}</h3>
        <p className="muted paint-prepared">{schedule.prepared}</p>
        <div className="paint-source"><Doc doc={schedule.source} variant="chip" /></div>
      </header>

      {schedule.unavailable && (
        <p role="status" className="notice paint-unavailable">
          {hasCopy
            ? `The maker's catalog is unavailable. This shows the copy kept on disk, ${copyAge(schedule.catalogFetched, today)}.`
            : <>The maker's catalog is unavailable and no copy is kept on disk. Colors are not checked. Run <code>{command} --refresh</code>.</>}
        </p>
      )}
      {!schedule.unavailable && hasCopy && <p className="muted paint-copy">Catalog copy: {copyAge(schedule.catalogFetched, today)}.</p>}

      {schedule.schemes.length > 1 && (
        <fieldset className="paint-toggle">
          <legend>Scheme</legend>
          <label className="paint-radio"><input type="radio" name={name} checked={chosen === null} onChange={() => pick(null)} /> All schemes</label>
          {schedule.schemes.map((n) => (
            <label key={n} className="paint-radio">
              <input type="radio" name={name} checked={chosen === n} onChange={() => pick(n)} /> Scheme {n}
            </label>
          ))}
        </fieldset>
      )}

      <div className="table-wrap paint-wrap">
        <table className="paint-table">
          <caption className="paint-caption">{schedule.title}: the color for each surface, by scheme</caption>
          <thead>
            <tr>
              <th scope="col">Surface</th>
              {schedule.schemes.map((n) => <th key={n} scope="col" hidden={!shown(n)}>Scheme {n}</th>)}
            </tr>
          </thead>
          <tbody>
            {schedule.rows.map((row) => {
              const noPaint = schedule.schemes.every((n) => !row.colors[n]);
              const sameWords = row.surface.trim().toLowerCase() === row.label.trim().toLowerCase();
              return (
                <tr key={row.label}>
                  <th scope="row">
                    {row.label}
                    {!sameWords && row.surface && <span className="paint-surface">{row.surface}</span>}
                  </th>
                  {noPaint ? (
                    <td colSpan={schedule.schemes.length} className="paint-nopaint">{row.note ?? NO_PAINT_ROW}</td>
                  ) : schedule.schemes.map((n) => {
                    const c = row.colors[n];
                    return (
                      <td key={n} hidden={!shown(n)} data-label={`Scheme ${n}`}>
                        {c ? <Swatch color={c} size="card" onOpen={onOpenColor} /> : <span className="muted paint-none">No color printed</span>}
                        {c && row.note && <span className="paint-note muted">{row.note}</span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {flags.length > 0 && (
        <div className="paint-flags">
          <h4 className="paint-flags-title">Flags on this schedule</h4>
          <Findings items={flags} />
          <p className="muted">A renamed or discontinued color is a finding for the board. jason changes nothing on the schedule.</p>
        </div>
      )}
      <p className="paint-caption-text">{PAINT_CAPTION}</p>
    </section>
  );
}
