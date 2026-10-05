import { Glyph } from "./Glyph";

/** The tool's caveats, repeated as the MCP docs ask. Never hidden behind a toggle. Each carries the note mark: a caveat is
 * information, not an alarm. */
export function Caveats({ items }: { items?: readonly string[] | null }) {
  if (!items?.length) return null;
  return (
    <aside className="caveats" aria-label="Caveats">
      {items.map((c, i) => (
        <p key={i}>
          <Glyph name="info" size="1em" className="caveat-glyph" />
          {c}
        </p>
      ))}
    </aside>
  );
}
