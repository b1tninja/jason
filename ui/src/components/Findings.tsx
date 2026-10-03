import { Badge } from "./Badge";

/** `findings: string[]` with `ok`, or `gaps: string[]`: a flag list a person reads, never a verdict. */
export function Findings({ items, ok, empty = "nothing flagged" }: { items?: readonly string[] | null; ok?: boolean; empty?: string }) {
  if (!items?.length) return ok === false ? null : <span className="muted">{empty}</span>;
  return (
    <ul className="findings">
      {items.map((f, i) => (
        <li key={i}>
          <Badge tone="warn">flag</Badge> {f}
        </li>
      ))}
    </ul>
  );
}
