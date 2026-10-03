import { Badge } from "./Badge";

export function daysUntil(iso: string, today = new Date()): number {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return Math.round((d.getTime() - new Date(today.toDateString()).getTime()) / 86400000);
}

/** An ISO date with how far off it is; overdue reads bad, within 14 days warn. */
export function DueDate({ iso, today }: { iso?: string | null; today?: Date }) {
  if (!iso) return <span className="muted">—</span>;
  const days = daysUntil(iso, today);
  const tone = days < 0 ? "bad" : days <= 14 ? "warn" : "neutral";
  const when = days === 0 ? "today" : days < 0 ? `${-days}d overdue` : `in ${days}d`;
  return (
    <span className="due">
      <time dateTime={iso}>{iso}</time> <Badge tone={tone}>{when}</Badge>
    </span>
  );
}
