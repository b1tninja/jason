import { HoldingChips } from "./HoldingChips";
import { Pill } from "./Pill";
import { HELD_MEANINGS, KIND_MEANINGS, type HeldWord, type PortalReport } from "../lib/inspections";

const HELD_GLYPH: Record<HeldWord, "circle-check" | "info" | "circle-dashed"> = {
  "library and drive": "circle-check", "library only": "info", "drive only": "info", "not filed": "circle-dashed",
};

/** One report a portal lists: its day, the portal's own name for it, the inspector, what kind it is, and where it is held
 * (library, Drive, both, or "not filed", which is the loader's word and a lead). A record of completion is shown as that,
 * never as an inspection. A report the site's name check refused says "held back" with the check's reason. */
export function PortalReportRow({ report: r }: { report: PortalReport }) {
  return (
    <article className="insp-report" data-held={r.held} data-kind={r.kind}>
      <header className="row wrap">
        <time dateTime={r.day}><strong>{r.day}</strong></time>
        <span>{r.template}</span>
        <Pill word={r.kind} meaning={KIND_MEANINGS[r.kind]} glyph={r.kind === "inspection" ? "file-check" : "file-text"} />
        <Pill word={r.held} meaning={HELD_MEANINGS[r.held]} glyph={HELD_GLYPH[r.held]} />
        {r.refused && <Pill word="held back" meaning="A check refused to file it. See the reason." glyph="octagon-alert" />}
      </header>
      <p className="muted">{r.site} · {r.inspector}</p>
      {r.refused && <p role="note" className="notice notice-warn">Held back: {r.refused}.</p>}
      <HoldingChips holdings={r.holdings} />
    </article>
  );
}
