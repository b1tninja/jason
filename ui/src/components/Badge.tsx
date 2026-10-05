import { Glyph, type GlyphName } from "./Glyph";

export type Tone = "neutral" | "good" | "warn" | "bad";

/** A short word with its tone. `glyph` puts a mark beside the word (16px, the word stays the label); a badge never gets one
 * by default, because a badge may be a count or a kind. `Pill` and `DueDate` are the status components and choose theirs. */
export function Badge({ tone = "neutral", glyph, children }: { tone?: Tone; glyph?: GlyphName; children: string }) {
  return (
    <span className={`badge badge-${tone}`}>
      {glyph && <Glyph name={glyph} size="1em" className="badge-glyph" />}
      {children}
    </span>
  );
}
