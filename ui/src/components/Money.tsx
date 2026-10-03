import { formatCents } from "../lib/format";

/** Integer cents in, dollars out. Negative amounts are marked, never hidden by color alone. */
export function Money({ cents }: { cents: number }) {
  return <span className={`money${cents < 0 ? " money-neg" : ""}`}>{formatCents(cents)}</span>;
}
