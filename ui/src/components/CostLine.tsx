import { Money } from "./Money";

/** What applying the plan charges the association, before anyone approves it: the engine's `costCents` (integer cents;
 * `null` when the kind has no cost) and the planner's `summary.cost` words. Spread an approval into it:
 * `<CostLine {...approval} />`. A per-item cost shows as the sum of the approved items when the plan has no total. */
export function CostLine({ costCents, summary, items }: {
  costCents?: number | null; summary?: Record<string, unknown> | null; items?: readonly { costCents?: number; decision?: string; class?: string }[];
}) {
  const words = typeof summary?.cost === "string" ? summary.cost : "";
  const approved = (items ?? []).filter((i) => i.class === "approvable" && i.decision === "approved").reduce((n, i) => n + (i.costCents ?? 0), 0);
  const cents = typeof costCents === "number" ? costCents : approved > 0 ? approved : null;
  if (cents === null || cents === 0)
    return <p className="cost-line cost-none"><strong>Cost:</strong> {words || "no charge to the association."}</p>;
  return (
    <p className="cost-line">
      <strong>Cost:</strong> <Money cents={cents} />{typeof costCents === "number" ? "" : " for the approved changes"}
      {words && <span className="muted"> · {words}</span>}
    </p>
  );
}
