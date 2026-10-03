/** The tool's caveats, repeated as the MCP docs ask. Never hidden behind a toggle. */
export function Caveats({ items }: { items?: readonly string[] | null }) {
  if (!items?.length) return null;
  return (
    <aside className="caveats" aria-label="Caveats">
      {items.map((c, i) => (
        <p key={i}>{c}</p>
      ))}
    </aside>
  );
}
