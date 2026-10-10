import { Badge } from "./Badge";
import { glyphForStatus } from "../lib/statusGlyph";

export function daysUntil(iso: string, today = new Date()): number {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return Math.round((d.getTime() - new Date(today.toDateString()).getTime()) / 86400000);
}

/** An ISO date with how far off it is; overdue reads bad, within 14 days warn. `settled` (answered, done, dropped)
 * shows the date alone: a satisfied deadline is never "overdue". */
export function DueDate({ iso, today, settled }: { iso?: string | null; today?: Date; settled?: boolean }) {
  if (!iso) return <span className="muted">—</span>;
  if (settled) return <time dateTime={iso}>{iso}</time>;
  const days = daysUntil(iso, today);
  const tone = days < 0 ? "bad" : days <= 14 ? "warn" : "neutral";
  const when = days === 0 ? "today" : days < 0 ? `${-days}d overdue` : `in ${days}d`;
  return (
    <span className="due">
      <time dateTime={iso}>{iso}</time> <Badge tone={tone} glyph={glyphForStatus(when, tone)}>{when}</Badge>
    </span>
  );
}
