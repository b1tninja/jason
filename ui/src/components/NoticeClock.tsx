import { Pill } from "./Pill";
import { Glyph } from "./Glyph";
import { STANDING_MEANINGS, RUNS_FROM_MEANINGS, metWord, plural, type NoticeClockData } from "../lib/inspections";

const STANDING_GLYPH = { met: "circle-check", running: "clock", passed: "triangle-alert", unknown: "circle-question-mark" } as const;

/** A notice's days with each date they could run from, side by side: each reading's date, the days elapsed on it, and
 * whether it is met, not met, or unknown, in words. It never picks the date: no reading is first, larger, or marked, and
 * the caveat ("Which date counts is the program's to say.") is always shown. A statute's own clock carries its citation;
 * a program's notice carries its sender and its own words. Readings keep the order the loader gave them. */
export function NoticeClock({ clock }: { clock: NoticeClockData }) {
  const c = clock;
  return (
    <section className="insp-clock" aria-label={`${c.program}: ${plural(c.days, "day")}`}>
      <header className="row wrap">
        <h3>{c.program}: {plural(c.days, "day")}</h3>
        <Pill word={c.standing} meaning={STANDING_MEANINGS[c.standing]} glyph={STANDING_GLYPH[c.standing]} />
      </header>
      {c.statute
        ? <p className="muted">The statute's own clock: <cite>{c.basis}</cite></p>
        : <p className="muted">A program's notice, in its own words: <q>{c.basis}</q></p>}
      <ul className="insp-dates" aria-label="Each date the days could run from">
        {c.runsFrom.map((r) => (
          <li key={r.label} className="insp-date" data-reading={r.label}>
            <span className="insp-date-label" title={RUNS_FROM_MEANINGS[r.label]}>{r.label}</span>
            <time dateTime={r.date}>{r.date}</time>
            <span className="num">{plural(r.elapsed, "day")} elapsed</span>
            <span className="insp-date-met"><Glyph name={r.met === null ? "circle-question-mark" : r.met ? "circle-check" : "circle-x"} size="1em" /> {metWord(r.met)}</span>
          </li>
        ))}
      </ul>
      <p className="insp-clock-caveat" role="note">{c.caveat}</p>
    </section>
  );
}
