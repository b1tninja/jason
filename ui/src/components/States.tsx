import type { ReactNode } from "react";
import { Glyph, type GlyphName } from "./Glyph";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="muted">
      {label}
    </p>
  );
}

export function ErrorNotice({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="notice notice-error">
      <span>{error}</span>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}

/** Nothing to show, said plainly: an empty screen is usually good news. `glyph` is the screen's own mark at 32px, muted;
 * there is no illustration. */
export function EmptyState({ children = "Nothing to show.", glyph }: { children?: ReactNode; glyph?: GlyphName }) {
  return (
    <p className={glyph ? "muted empty-state" : "muted"}>
      {glyph && <Glyph name={glyph} size={32} className="empty-glyph" />}
      {children}
    </p>
  );
}
