import type { ReactNode } from "react";
import { Glyph, type GlyphName } from "./Glyph";
import { glyphForStatus } from "../lib/statusGlyph";

export interface TimelineEvent {
  id: string;
  date: string; // ISO or "" for undated
  title: ReactNode;
  detail?: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
  /** What happened, as a mark beside the title: the provenance glyph (proposal, badge-check, send, stamp, undo-2, lock).
   * Absent, a good, warn, or bad event takes the attention glyph for its tone and a neutral one takes none. */
  glyph?: GlyphName;
}

/** Dated events, oldest first; undated ones go last. */
export function Timeline({ events }: { events: TimelineEvent[] }) {
  const sorted = [...events].sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999"));
  if (!sorted.length) return <p className="muted">No events.</p>;
  const glyphOf = (e: TimelineEvent) => e.glyph ?? glyphForStatus("", e.tone ?? "neutral");
  const anyGlyph = sorted.some((e) => glyphOf(e));
  return (
    <ol className="timeline">
      {sorted.map((e) => {
        const glyph = glyphOf(e);
        return (
          <li key={e.id} className={`tl tl-${e.tone ?? "neutral"}`}>
            <time dateTime={e.date || undefined} className="tl-date">
              {e.date || "undated"}
            </time>
            <div>
              <div className="tl-title">
                {glyph ? <Glyph name={glyph} size="1em" className="tl-glyph" /> : anyGlyph && <span className="tl-glyph tl-glyph-none" aria-hidden="true" />}
                {e.title}
              </div>
              {e.detail && <div className="muted">{e.detail}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
