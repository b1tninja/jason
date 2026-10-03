/** Records, commands, paths, and links a row cites. A command is shown as code so it can be copied, never run from here. */
export function Evidence({ items, label = "Evidence" }: { items?: readonly string[] | null; label?: string }) {
  if (!items?.length) return null;
  return (
    <div className="evidence">
      {label && <span className="muted">{label}: </span>}
      {items.map((e, i) => (
        <code key={i} className="chip">
          {e}
        </code>
      ))}
    </div>
  );
}
