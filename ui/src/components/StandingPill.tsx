import { Badge } from "./Badge";
import { glyphForStatus } from "../lib/statusGlyph";
import { STANDINGS, STANDING_ORDER, type Standing, type StandingCounts } from "../lib/citations";

/** A cited section's standing against the authorities shelf, in its word. The color repeats the word and never replaces
 * it; a gap is a warn tone, never bad, because a gap is a lead and not a finding. The meaning is the pill's title. A code
 * the server sends that this build does not know is shown as its own words, neutral. */
export function StandingPill({ standing }: { standing: Standing | string }) {
  const s = STANDINGS[standing as Standing];
  if (!s) return <Badge>{String(standing).replace(/_/g, " ").toLowerCase()}</Badge>;
  return (
    <span title={s.meaning}>
      <Badge tone={s.tone} glyph={glyphForStatus(s.word, s.tone)}>{s.word}</Badge>
    </span>
  );
}

/** Counts by standing: the bar is decoration and the list beside it says every number in words, the table twin a screen
 * reader reads. A standing with none is left out; with nothing cited it says so. */
export function StandingStrip({ counts, label = "Sections by standing" }: { counts: StandingCounts | null | undefined; label?: string }) {
  const present = STANDING_ORDER.filter((s) => (counts?.[s] ?? 0) > 0);
  const total = present.reduce((n, s) => n + (counts?.[s] ?? 0), 0);
  if (!total) return <p className="muted">No section cited.</p>;
  return (
    <div className="standing-strip" role="group" aria-label={label}>
      <div className="standing-bar" aria-hidden>
        {present.map((s) => (
          <span key={s} className={`standing-seg standing-${STANDINGS[s].tone}`} style={{ flexGrow: counts?.[s] ?? 0 }} />
        ))}
      </div>
      <ul className="standing-list">
        {present.map((s) => (
          <li key={s}>
            <StandingPill standing={s} /> <span className="num">{counts?.[s]}</span>
          </li>
        ))}
        <li className="muted">{total} in all</li>
      </ul>
    </div>
  );
}
