import { Badge } from "./Badge";
import { lookOf } from "../lib/controls";

/** A control's standing as a word and a glyph, never colour alone (a `Pill` preset: the same `Badge` parts, with the tone
 * and mark the standing sets). `standing` is the loader's key: suggested, proposed, in-force, in-force-roster-lacks,
 * adopted-not-in-force, declined, deferred, retired. The two adopted-but-not-binding cases read apart: "adopted, takes
 * effect DATE" (the date has not come; a calendar) and "in force, the roster cannot satisfy it" (the date has come; the acts
 * it governs are refused, never relaxed). `word` is the loader's own sentence, shown beside the short word (`detail`) so
 * the page invents none. A standing the page does not know is shown as the loader's word, plainly. */
export function ControlStateWord({ standing, word, effective = "", detail = false }: {
  standing: string; word?: string; effective?: string; detail?: boolean;
}) {
  const look = lookOf(standing, effective);
  if (!look) return <span className="control-state"><Badge>{(word || standing || "unknown").toLowerCase()}</Badge></span>;
  return (
    <span className="control-state" data-standing={standing}>
      <span title={word || undefined}><Badge tone={look.tone} glyph={look.glyph}>{look.word}</Badge></span>
      {detail && word && <span className="muted control-state-words"> {word}</span>}
    </span>
  );
}
