import { Badge } from "./Badge";
import type { GlyphName } from "./Glyph";
import { toneOf } from "../lib/tones";
import { glyphForStatus } from "../lib/statusGlyph";

/** A status or standing word with its tone, and its meaning on hover when the record carries one. It carries the attention
 * glyph for its word or tone (`glyphForStatus`); `glyph` names another, and `false` leaves it off. */
export function Pill({ word, meaning, glyph }: { word: string | null | undefined; meaning?: string; glyph?: GlyphName | false }) {
  if (!word) return null;
  const text = String(word).replace(/_/g, " ").toLowerCase();
  const tone = toneOf(text);
  return (
    <span title={meaning}>
      <Badge tone={tone} glyph={glyph === false ? undefined : glyph ?? glyphForStatus(text, tone)}>{text}</Badge>
    </span>
  );
}
