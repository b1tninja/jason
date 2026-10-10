import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Glyph } from "../components/Glyph";
import type { FactsCache } from "./splitFacts";
import { cellLabel, lqipUrl, stateWord, type PageFact, type Size, type Suggestion } from "./splitModel";
import type { Snapshot } from "./splitStore";
import type { ThumbLoader } from "./splitThumbs";
import {
  FAST_PX_PER_S, SETTLE_MS, centerPage, layoutOf, liveCells, motionOf, pagesIn, scrollFor, visibleTracks,
  type Axis, type Layout, type Win,
} from "./splitWindow";

/** The windowed page grid (docs/pdf-splitter.md, sections 3.4 and 5.3). Cells have a fixed size, so the scroll length is arithmetic; only the
 * tracks in view plus a buffer exist as elements (about forty for any file); a cell paints at once from the page's facts and asks the loader
 * for its picture; one set of event handlers sits on the grid and reads the page from the cell. Used by the Album, the Scroll views, and the
 * Filmstrip's strip. */

export type Variant = "album" | "scroll" | "strip";
export const BUFFER_VIEWPORTS = 2;
const LONG_PRESS_MS = 500;
const SIZES: Record<string, Size[]> = { ts: ["tiny", "small"], t: ["tiny"], sl: ["small", "large"], s: ["small"] };

export interface GridApi {
  scrollToPage(page: number, start?: boolean): void;
  focusPage(page: number): void;
  cols(): number;
  windowInfo(): { first: number; last: number; live: number; tracks: number; total: number };
}

export interface PageGridProps {
  count: number;
  axis: Axis;
  variant: Variant;
  /** a width in px, or "fit" for one cell as wide as the view (to `maxW`) */
  cellW: number | "fit";
  maxW?: number;
  /** a page's height over its width */
  aspect?: number;
  gap?: number;
  label: string;
  snap: Snapshot;
  facts: FactsCache;
  loader: ThumbLoader;
  focus: number;
  selection: { a: number; b: number } | null;
  confidential: boolean;
  onActivate(page: number, shift: boolean): void;
  onMenu(page: number): void;
  onMove(from: number, to: number): void;
  onFocusPage(page: number): void;
}

const CHROME = 24;

function bandWord(s: Suggestion | undefined): string { return s ? String(s.band) : ""; }

interface CellProps {
  page: number; f: PageFact | undefined; start: number; no: number; sug: Suggestion | undefined; selected: boolean; focused: boolean;
  w: number; h: number; sizes: string; confidential: boolean; loader: ThumbLoader; variant: Variant; readOnly: boolean;
}

const PageCell = memo(function PageCell({ page, f, start, no, sug, selected, focused, w, h, sizes, confidential, loader, variant, readOnly }: CellProps) {
  const img = useRef<HTMLImageElement>(null);
  const note = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = img.current;
    if (!el) return;
    return loader.attach(el, page, SIZES[sizes], {
      onState: (state, words) => { if (note.current) note.current.textContent = state === "failed" ? (words || "This page could not be drawn") : ""; },
    });
  }, [loader, page, sizes]);
  const lq = confidential ? "" : lqipUrl(f?.lqip);
  const state = stateWord(f);
  const isStart = start >= 0;
  const open = !!sug && sug.state === "open" && !isStart;
  const label = cellLabel(page, f, start, no, open ? sug : undefined, confidential);
  return (
    <div role="gridcell" aria-selected={selected} className="split-cell" data-cell="" data-page={page} data-variant={variant}
      data-start={isStart ? (start > 0 ? "nested" : "top") : undefined} data-sug={open ? bandWord(sug) : undefined} data-band={no % 2} data-selected={selected || undefined}
      data-state={f?.pending ? "pending" : f?.blank === "blank" ? "blank" : undefined} style={{ width: w, height: h }}>
      <button type="button" className="split-cell-btn" data-page={page} tabIndex={focused ? 0 : -1} aria-pressed={isStart} aria-label={label}>
        <span className="split-pic" style={{ height: h - CHROME }}>
          <span className="split-lqip" style={lq ? { backgroundImage: `url(${lq})` } : undefined} aria-hidden="true" />
          <img ref={img} alt="" draggable={false} decoding="async" />
        </span>
        <span className="split-cell-foot" aria-hidden="true">
          <span className="split-cell-n">{page}</span>
          {variant !== "strip" && state !== "content" && state !== "not measured yet" && (
            <span className="split-cell-state"><Glyph name={f?.blank === "blank" ? "file-minus" : f?.blank === "marked" ? "pencil" : "scan-line"} size={12} /> {state.startsWith("no text") ? "No text" : state === "blank" ? "Blank" : state === "marked" ? "Marked" : state}</span>
          )}
          {variant !== "strip" && no > 0 && <span className="split-cell-seg">S{no}</span>}
        </span>
        {variant !== "strip" && <span className="split-cell-note" ref={note} aria-hidden="true" />}
        {isStart && <span className="split-start-tag" aria-hidden="true">{page === 1 && <Glyph name="lock" size={11} />} {start > 0 ? "Nested start" : `Start ${no}`}</span>}
        {open && <span className="split-sug-tag" aria-hidden="true">Suggested, {bandWord(sug)}</span>}
      </button>
      {isStart && page !== 1 && !readOnly && <span className="split-handle" data-handle={page} aria-hidden="true" title="Drag to move this start"><Glyph name="arrow-left-right" size={12} /></span>}
    </div>
  );
});

export const PageGrid = forwardRef<GridApi, PageGridProps>(function PageGrid(p, ref) {
  const { count, axis, variant, aspect = 1.294, gap = 8, snap, facts, loader, focus, selection, confidential } = p;
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 720, h: 520 });
  const cw = p.cellW === "fit" ? Math.max(120, Math.min(p.maxW ?? 560, size.w - 16)) : p.cellW;
  const ch = Math.round(cw * aspect) + CHROME;
  const layout: Layout = useMemo(() => layoutOf({ axis, count, width: size.w, cellW: cw, cellH: ch, gap }), [axis, count, size.w, cw, ch, gap]);
  const layoutRef = useRef(layout); layoutRef.current = layout;
  const [win, setWin] = useState<Win>({ first: 0, last: -1 });
  const winRef = useRef(win);
  const factsVersion = useSyncExternalStore(facts.subscribe, facts.getVersion, facts.getVersion);

  const offset = () => (axis === "y" ? box.current?.scrollTop ?? 0 : box.current?.scrollLeft ?? 0);
  const viewport = () => (axis === "y" ? size.h : size.w);

  const recompute = useCallback(() => {
    const l = layoutRef.current;
    const w = visibleTracks(l, offset(), axis === "y" ? sizeRef.current.h : sizeRef.current.w, BUFFER_VIEWPORTS);
    if (w.first !== winRef.current.first || w.last !== winRef.current.last) { winRef.current = w; setWin(w); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [axis]);
  const sizeRef = useRef(size); sizeRef.current = size;

  // the box's size, as the browser lays it out
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const read = () => {
      const w = el.clientWidth || 720, h = el.clientHeight || 520;
      setSize((s) => (s.w === w && s.h === h ? s : { w, h }));
    };
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // the window follows the layout and the size
  useLayoutEffect(() => { recompute(); }, [layout, size, recompute]);

  // facts for the pages in the window
  const span = pagesIn(layout, win, count);
  useEffect(() => { facts.ensure(span.first, span.last); }, [facts, span.first, span.last]);
  useEffect(() => { loader.setView(centerPage(layout, offset(), viewport(), count), 0); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [loader, win]);

  // scroll: rAF-throttled; direction and speed steer the loader, a settled scroll asks for the held-back pictures
  const frame = useRef(0);
  const prev = useRef<{ at: number; offset: number } | null>(null);
  const avg = useRef(0);
  const settle = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (frame.current) cancelAnimationFrame(frame.current); if (settle.current) clearTimeout(settle.current); }, []);
  const onScroll = () => {
    cancelLongPress();
    if (frame.current) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = 0;
      const now = performance.now();
      const m = motionOf(prev.current, now, offset());
      prev.current = { at: m.at, offset: m.offset };
      avg.current = 0.55 * avg.current + 0.45 * m.speed;
      loader.setView(centerPage(layoutRef.current, m.offset, viewport(), count), m.dir);
      if (avg.current > FAST_PX_PER_S) loader.setFast(true);
      if (settle.current) clearTimeout(settle.current);
      settle.current = setTimeout(() => { avg.current = 0; loader.setFast(false); }, SETTLE_MS);
      recompute();
    });
  };

  const programmatic = useRef(false);                       // set while the grid itself moves the focus, so that is not read as a person's
  const latest = useRef(p); latest.current = p;
  const focusPage = useCallback((page: number) => {
    const el = box.current;
    if (!el) return;
    const l = layoutRef.current;
    const next = scrollFor(l, page, offset(), axis === "y" ? sizeRef.current.h : sizeRef.current.w);
    if (next !== offset()) { if (axis === "y") el.scrollTop = next; else el.scrollLeft = next; }
    recompute();
    requestAnimationFrame(() => {
      if (latest.current.focus !== page) return;                 // a later key moved on before the frame
      programmatic.current = true;
      el.querySelector<HTMLElement>(`button[data-page="${page}"]`)?.focus({ preventScroll: true });
      programmatic.current = false;
    });
  }, [axis, recompute]);

  useImperativeHandle(ref, () => ({
    scrollToPage(page, start = false) {
      const el = box.current;
      if (!el) return;
      const next = scrollFor(layoutRef.current, page, offset(), axis === "y" ? sizeRef.current.h : sizeRef.current.w, start);
      if (axis === "y") el.scrollTop = next; else el.scrollLeft = next;
      recompute();
    },
    focusPage,
    cols: () => layoutRef.current.perTrack,
    windowInfo: () => { const s = pagesIn(layoutRef.current, winRef.current, count); return { first: s.first, last: s.last, live: liveCells(layoutRef.current, winRef.current, count), tracks: layoutRef.current.tracks, total: layoutRef.current.total }; },
  }), [axis, count, focusPage, recompute]);

  // ---- pointer: the click, the long press, the drag of a start

  const press = useRef<{ timer: ReturnType<typeof setTimeout>; x: number; y: number } | null>(null);
  const suppress = useRef(false);
  const cancelLongPress = () => { if (press.current) { clearTimeout(press.current.timer); press.current = null; } };
  const pageOf = (t: EventTarget | null): number => {
    const c = (t as HTMLElement | null)?.closest?.("[data-cell]") as HTMLElement | null;
    return c ? Number(c.dataset.page) : 0;
  };
  const drag = useRef<{ from: number; x: number; y: number; moved: boolean; target: number; raf: number } | null>(null);
  // stable listeners (added to and removed from the window), reading the latest props through a ref
  const dragFns = useRef<{ move(e: PointerEvent): void; up(): void; cancel(): void; end(commit: boolean): void } | null>(null);
  if (!dragFns.current) {
    const end = (commit: boolean) => {
      const d = drag.current;
      if (!d) return;
      drag.current = null;
      cancelAnimationFrame(d.raf);
      box.current?.removeAttribute("data-dragging");
      box.current?.querySelectorAll("[data-drop]").forEach((e) => e.removeAttribute("data-drop"));
      window.removeEventListener("pointermove", fns.move);
      window.removeEventListener("pointerup", fns.up);
      window.removeEventListener("pointercancel", fns.cancel);
      if (commit && d.moved && d.target && d.target !== d.from) latest.current.onMove(d.from, d.target);
      window.setTimeout(() => { suppress.current = false; }, 0);
    };
    const fns = {
      end,
      up: () => end(true),
      cancel: () => end(false),
      move: (e: PointerEvent) => {
        const d = drag.current;
        if (!d) return;
        if (!d.moved && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 6) return;
        d.moved = true;
        suppress.current = true;
        box.current?.setAttribute("data-dragging", "");
        const under = typeof document.elementFromPoint === "function" ? document.elementFromPoint(e.clientX, e.clientY) : null;
        const page = pageOf(under);
        box.current?.querySelectorAll("[data-drop]").forEach((x) => x.removeAttribute("data-drop"));
        d.target = page;
        if (page) box.current?.querySelector(`[data-cell][data-page="${page}"]`)?.setAttribute("data-drop", "");
        // near an edge, scroll toward it so a start can be carried further than the view shows
        const r = box.current?.getBoundingClientRect();
        cancelAnimationFrame(d.raf);
        if (r && box.current) {
          const edge = 48, ax = latest.current.axis;
          const dx = ax === "x" ? (e.clientX < r.left + edge ? -24 : e.clientX > r.right - edge ? 24 : 0) : 0;
          const dy = ax === "y" ? (e.clientY < r.top + edge ? -24 : e.clientY > r.bottom - edge ? 24 : 0) : 0;
          if (dx || dy) {
            const step = () => { if (!drag.current || !box.current) return; box.current.scrollBy?.({ left: dx, top: dy }); d.raf = requestAnimationFrame(step); };
            d.raf = requestAnimationFrame(step);
          }
        }
      },
    };
    dragFns.current = fns;
  }
  useEffect(() => () => { dragFns.current?.end(false); }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    const t = e.target as HTMLElement;
    const handle = t.closest?.("[data-handle]") as HTMLElement | null;
    if (handle && e.button === 0) {
      drag.current = { from: Number(handle.dataset.handle), x: e.clientX, y: e.clientY, moved: false, target: 0, raf: 0 };
      window.addEventListener("pointermove", dragFns.current!.move);
      window.addEventListener("pointerup", dragFns.current!.up);
      window.addEventListener("pointercancel", dragFns.current!.cancel);
      e.preventDefault();
      return;
    }
    if (e.pointerType === "touch" || e.pointerType === "pen") {
      const page = pageOf(e.target);
      if (!page) return;
      cancelLongPress();
      press.current = { x: e.clientX, y: e.clientY, timer: setTimeout(() => { press.current = null; suppress.current = true; p.onMenu(page); }, LONG_PRESS_MS) };
    }
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (press.current && Math.hypot(e.clientX - press.current.x, e.clientY - press.current.y) > 8) cancelLongPress();
  };
  const onPointerUp = () => { cancelLongPress(); window.setTimeout(() => { suppress.current = false; }, 350); };
  const onClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest?.("[data-handle]")) return;
    if (suppress.current) { suppress.current = false; return; }
    const page = pageOf(e.target);
    if (page) p.onActivate(page, e.shiftKey);
  };
  const onContextMenu = (e: React.MouseEvent) => {
    const page = pageOf(e.target);
    if (!page) return;
    e.preventDefault();
    p.onMenu(page);
  };
  const onFocus = (e: React.FocusEvent) => {
    if (e.target === box.current) { focusPage(focus); return; }
    if (programmatic.current) return;
    const page = pageOf(e.target);
    if (page && page !== focus) p.onFocusPage(page);
  };

  const sel = selection ? { lo: Math.min(selection.a, selection.b), hi: Math.max(selection.a, selection.b) } : null;
  const cells: JSX.Element[] = [];
  const out: JSX.Element[] = [];
  for (let t = win.first; t <= win.last; t++) {
    cells.length = 0;
    for (let k = 0; k < layout.perTrack; k++) {
      const page = t * layout.perTrack + k + 1;
      if (page > count) break;
      const sizes = variant === "strip" ? "t" : variant === "scroll" ? (Math.abs(page - focus) <= 1 ? "sl" : "s") : "ts";
      cells.push(
        <PageCell key={page} page={page} f={facts.get(page)} start={snap.starts.has(page) ? snap.starts.get(page)! : -1} no={snap.docNo[page] ?? 0}
          sug={snap.sugByPage.get(page)} selected={!!sel && page >= sel.lo && page <= sel.hi} focused={page === focus} w={cw} h={ch} sizes={sizes}
          confidential={confidential} loader={loader} variant={variant} readOnly={snap.readOnly} />,
      );
    }
    out.push(axis === "y"
      ? <div key={t} role="row" aria-rowindex={t + 1} className="split-row" style={{ top: t * layout.track, height: ch, gap }}>{[...cells]}</div>
      : <div key={t} role="presentation" className="split-col" style={{ left: t * layout.track, width: cw }}>{[...cells]}</div>);
  }
  const focusLive = focus >= span.first && focus <= span.last;
  void factsVersion;
  return (
    <div ref={box} className={`split-scroll split-scroll-${axis}`} data-variant={variant} role={axis === "y" ? "grid" : "group"} aria-label={p.label}
      aria-rowcount={axis === "y" ? layout.tracks : undefined} aria-colcount={axis === "y" ? layout.perTrack : undefined} aria-multiselectable={axis === "y" ? true : undefined}
      tabIndex={focusLive ? -1 : 0} onScroll={onScroll} onClick={onClick} onContextMenu={onContextMenu} onPointerDown={onPointerDown}
      onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onFocus={onFocus}>
      <div className="split-spacer" style={axis === "y" ? { height: layout.total } : { width: layout.total, height: ch }}>{out}</div>
    </div>
  );
});
