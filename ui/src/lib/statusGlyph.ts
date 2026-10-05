import type { GlyphName } from "../components/Glyph";
import type { Tone } from "../components/Badge";

/** The attention glyph for a status or standing word: what the word says, then what its tone says. Neutral words carry
 * none: a neutral badge is a label, not a status. The six attention glyphs and their meanings are in `GLYPH_META`
 * (info, clock, triangle-alert, octagon-alert, circle-check, circle-dashed). */
const BY_WORD: Record<string, GlyphName> = {
  missing: "circle-dashed", "no evidence": "circle-dashed", absent: "circle-dashed",
  blocked: "octagon-alert", rejected: "octagon-alert", refused: "octagon-alert",
};

const BY_TONE: Partial<Record<Tone, GlyphName>> = { good: "circle-check", warn: "clock", bad: "triangle-alert" };

export function glyphForStatus(word: string | null | undefined, tone: Tone): GlyphName | undefined {
  const text = String(word ?? "").toLowerCase().replace(/_/g, " ");
  return BY_WORD[text] ?? BY_TONE[tone];
}
