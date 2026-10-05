import { Badge } from "./Badge";
import type { GlyphName } from "./Glyph";

/** `findings: string[]` with `ok`, or `gaps: string[]`: a flag list a person reads, never a verdict. Each row carries the
 * question mark (a finding is something jason could not settle alone); `glyph` names another, `false` leaves it off. */
export function Findings({ items, ok, empty = "nothing flagged", glyph = "circle-question-mark" }: {
  items?: readonly string[] | null; ok?: boolean; empty?: string; glyph?: GlyphName | false;
}) {
  if (!items?.length) return ok === false ? null : <span className="muted">{empty}</span>;
  return (
    <ul className="findings">
      {items.map((f, i) => (
        <li key={i}>
          <Badge tone="warn" glyph={glyph || undefined}>flag</Badge> {f}
        </li>
      ))}
    </ul>
  );
}
