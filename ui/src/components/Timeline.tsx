import type { ReactNode } from "react";

export interface TimelineEvent {
  id: string;
  date: string; // ISO or "" for undated
  title: ReactNode;
  detail?: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}

/** Dated events, oldest first; undated ones go last. */
export function Timeline({ events }: { events: TimelineEvent[] }) {
  const sorted = [...events].sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999"));
  if (!sorted.length) return <p className="muted">No events.</p>;
  return (
    <ol className="timeline">
      {sorted.map((e) => (
        <li key={e.id} className={`tl tl-${e.tone ?? "neutral"}`}>
          <time dateTime={e.date || undefined} className="tl-date">
            {e.date || "undated"}
          </time>
          <div>
            <div className="tl-title">{e.title}</div>
            {e.detail && <div className="muted">{e.detail}</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}
