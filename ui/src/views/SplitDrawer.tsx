import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { Glyph } from "../components/Glyph";
import { dragIntent, type Side } from "./splitLayout";

/** The splitter's pull-out drawers (docs/pdf-splitter.md, section 5.9): the segments, the compare pane, and the review. A drawer overlays the
 * pages from an edge, or docks beside them when pinned. It opens from a toolbar button, a key, or its edge tab (a tap, or a drag past a
 * threshold); it closes from Esc, its Close button, its grip (a tap, or a drag back toward the edge), or the scrim. Focus goes in when it
 * opens and back to what opened it when it closes. Nothing in it is built while it is closed. */

/** Focus moves into `panel` when `open` becomes true, and returns to what had it before when `open` becomes false. */
export function useOpenFocus(open: boolean, panel: RefObject<HTMLElement>, fallback?: () => void) {
  const opener = useRef<HTMLElement | null>(null);
  const was = useRef(false);
  // read while rendering: the commit that opens the drawer may already have moved the focus (a review focuses its own heading)
  if (open && !was.current && typeof document !== "undefined") opener.current = document.activeElement as HTMLElement | null;
  was.current = open;
  const back = useRef(fallback); back.current = fallback;
  useEffect(() => {
    if (!open) return;
    const el = panel.current;
    if (el && !el.contains(document.activeElement)) el.focus({ preventScroll: true });
    return () => {
      const o = opener.current;
      if (o && o !== document.body && o.isConnected) o.focus({ preventScroll: true });
      else back.current?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
}

/** One pointer drag, from the first move past a threshold to its end; a tap that never passes it is left to the click. */
function useDrag(side: Side, open: boolean, onIntent: (i: "open" | "close") => void) {
  const start = useRef<{ x: number; y: number; id: number } | null>(null);
  const dragged = useRef(false);
  return {
    dragged,
    props: {
      onPointerDown: (e: React.PointerEvent) => {
        if (e.pointerType === "mouse" && e.button !== 0) return;
        start.current = { x: e.clientX, y: e.clientY, id: e.pointerId }; dragged.current = false;
        try { (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId); } catch { /* not every environment captures */ }
      },
      onPointerMove: (e: React.PointerEvent) => {
        const s = start.current;
        if (!s || dragged.current) return;
        const i = dragIntent(e.clientX - s.x, e.clientY - s.y, side, open);
        if (i) { dragged.current = true; onIntent(i); }
      },
      onPointerUp: () => { start.current = null; window.setTimeout(() => { dragged.current = false; }, 0); },
      onPointerCancel: () => { start.current = null; dragged.current = false; },
    },
  };
}

/** The tab at a screen edge that opens a closed drawer: a tap opens it, and so does a drag toward the middle. */
export function EdgeTab({ side, drawerId, label, count, onOpen, slot = 0 }: { side: Side; drawerId: string; label: string; count?: number; onOpen(): void; slot?: number }) {
  const drag = useDrag(side, false, () => onOpen());
  return (
    <button type="button" className="split-edgetab" data-side={side} data-slot={slot} data-for={drawerId} aria-expanded={false} aria-controls={`split-drawer-${drawerId}`}
      aria-label={`${label}${count !== undefined ? `, ${count}` : ""}. Open the ${label.toLowerCase()} drawer`} title={`${label}: tap, or drag toward the pages`}
      onClick={() => { if (!drag.dragged.current) onOpen(); }} {...drag.props}>
      <span className="split-edgetab-words" aria-hidden="true">{label}{count !== undefined ? <b>{count}</b> : null}</span>
    </button>
  );
}

export interface DrawerProps {
  id: string; label: string; open: boolean; side: Side; onClose(): void; children: ReactNode;
  /** docked beside the pages (true), or over them */
  docked?: boolean;
  /** the pin control; shown only when set (a drawer that can dock) */
  canPin?: boolean; onPin?(pin: boolean): void;
  /** the full-screen control */
  full?: boolean; onFull?(full: boolean): void;
  /** a CSS width for a side drawer (the phone's sheet is always the whole width) */
  width?: string;
  /** closing is refused for now (a write is running) */
  locked?: boolean;
  /** where focus goes if what opened the drawer is gone */
  fallbackFocus?: () => void;
  head?: ReactNode;
}

export function Drawer({ id, label, open, side, onClose, children, docked = false, canPin, onPin, full, onFull, width, locked, fallbackFocus, head }: DrawerProps) {
  const panel = useRef<HTMLElement>(null);
  useOpenFocus(open, panel, fallbackFocus);
  const drag = useDrag(side, true, (i) => { if (i === "close" && !locked) onClose(); });
  useEffect(() => {
    if (open && !docked) panel.current?.setAttribute("data-entered", "");
  }, [open, docked]);
  if (!open) return null;
  const close = () => { if (!locked) onClose(); };
  return (
    <>
      {!docked && <div className="split-scrim" data-for={id} aria-hidden="true" onClick={close} />}
      <aside ref={panel} id={`split-drawer-${id}`} className="split-drawer" data-drawer={id} data-side={side} data-docked={docked || undefined} data-full={full || undefined}
        aria-label={label} tabIndex={-1} style={width && !full && side !== "bottom" ? { width } : undefined}
        onKeyDown={(e) => { if (e.key === "Escape" && !e.defaultPrevented) { e.stopPropagation(); e.preventDefault(); close(); } }}>
        <div className="split-drawer-head">
          <button type="button" className="split-grip" aria-label={`Close the ${label.toLowerCase()} drawer`} title="Tap, or drag toward the edge, to close" disabled={locked}
            onClick={() => { if (!drag.dragged.current) close(); }} {...drag.props}>
            <Glyph name={side === "bottom" ? "chevron-down" : side === "left" ? "chevron-left" : "chevron-right"} size={16} />
          </button>
          <h2>{label}</h2>
          <div className="split-drawer-acts">
            {head}
            {canPin && <button type="button" aria-pressed={!!docked} onClick={() => onPin?.(!docked)}>{docked ? "Unpin" : "Pin open"}</button>}
            {onFull && <button type="button" aria-pressed={!!full} onClick={() => onFull(!full)}>Full screen</button>}
            <button type="button" onClick={close} disabled={locked}>Close</button>
          </div>
        </div>
        <div className="split-drawer-body">{children}</div>
      </aside>
    </>
  );
}
