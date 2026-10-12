import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  CORNER_WORDS, HOLD_MS, HOLD_SLOP_PX, HOP_MS, LOUPE_ZOOM_MIN, LoupeFeed, VIEWER_HEAD_PX, ViewerTarget, avoidDrawer, clampViewerPx, contentBox, cornerPlacement,
  fractionIn, hopTarget, lensBackground, lensSize, oppositeCorner, pageFit, phoneBand, placeLens, regionView, sharpPixels, stageBox, stepZoom, viewerSize,
  viewfinderRect, zoomWords,
  type Box, type Budget, type Corner, type MagMode, type Placement, type Pt, type Sharp, type SharpLoader, type ViewerView,
} from "./splitLoupe";

/** The magnifier (docs/pdf-splitter.md, section 5.12). One lens element, reused for every page and every view: a page picture marks itself
 * with `data-loupe="<page>"` (the grid's cells and the compare figure), and this component, which listens on the document, finds the page
 * under the pointer, the held finger, or the focused cell. The lens never takes a pointer event (`pointer-events: none`), never captures the
 * pointer, and never cancels a press, so a click or a drag through it marks the page as it would without it. It is placed with a transform in
 * an animation frame; nothing here is React state, so a moving pointer costs no render.
 *
 * The second mode is the fixed viewer: a panel in a corner of the grid's stage (a band above the action bar on a phone) that shows the same
 * spot, or the whole page, in one place so the eyes do not follow it. It keeps the last page when the pointer leaves, can be pinned to a page,
 * and hops to the opposite corner when the pointer stays under it. Its picture area takes no pointer event; its header strip does. */

export interface LoupeProps {
  /** the magnifier is on: a mouse or pen over a page, and the keyboard */
  enabled: boolean;
  /** the magnify mode of a touch screen: press and hold on a page, then drag (set only when a person asked for the magnifier) */
  touchMode: boolean;
  zoom: number;
  onZoom(z: number): void;
  load: SharpLoader;
  budget: Budget;
  /** the most the source can give: 1600 from the server, more from a file drawn in this browser */
  maxPx: number;
  release?(s: Sharp): void;
  /** a polite announcement (the screen's live region) */
  announce(message: string): void;
  /** "lens" follows the pointer; "fixed" is a viewer panel in a screen corner (default "lens") */
  mode?: MagMode;
  corner?: Corner;
  /** the fixed viewer's picture area, in CSS px */
  size?: number;
  view?: ViewerView;
  onView?(v: ViewerView): void;
  onSize?(px: number): void;
  /** the fixed viewer hops to the opposite corner when the pointer goes under it (default true) */
  hop?: boolean;
  /** a phone: the fixed viewer is a band above the action bar */
  phone?: boolean;
}

interface Hold { id: number; x: number; y: number; timer: ReturnType<typeof setTimeout> | null; active: boolean; from: Element | null }

const ARROWS: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
const KEY_NAV = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown", "Tab"]);
const RESIZE_STEP = 24;

export function Loupe(p: LoupeProps) {
  const lens = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const viewPic = useRef<HTMLDivElement>(null);
  const viewfinder = useRef<HTMLDivElement>(null);
  const api = useRef<{ pin(): void; hideNow(): void; resize(px: number): void } | null>(null);
  const live = useRef(p);
  live.current = p;
  const wanted = p.enabled || p.touchMode;

  useEffect(() => {
    const el = lens.current;
    if (!el || !wanted) return;
    const pnl = panel.current, pic = viewPic.current, finder = viewfinder.current;
    const s = {
      page: 0, img: null as HTMLImageElement | null, pt: { x: 0, y: 0 } as Pt, touch: false,
      kb: false, fx: 0.5, fy: 0.5, escPage: 0, raf: 0, shown: false, ask: "", url: "", lastKey: -Infinity, noClickUntil: 0, lastWheel: -Infinity,
      hold: null as Hold | null,
      // the fixed viewer
      tgt: new ViewerTarget(), corner: (p.corner ?? "bottom-right") as Corner, cornerProp: "" as string, frozen: false, lastAt: null as Pt | null,
      pageBox: null as Box | null, natural: null as { w: number; h: number } | null, cellUrl: "", panelBox: null as Box | null,
      hopTimer: 0 as ReturnType<typeof setTimeout> | 0, livePx: 0, announcedShow: false,
    };
    const fixed = () => (live.current.mode ?? "lens") === "fixed";
    const feed = new LoupeFeed({
      load: (page, px, signal) => live.current.load(page, px, signal),
      onSharp: () => schedule(),
      release: (x) => live.current.release?.(x),
      budget: p.budget,
    });

    const hide = () => {
      if (s.raf) { cancelAnimationFrame(s.raf); s.raf = 0; }
      el.hidden = true; s.shown = false; s.page = 0; s.img = null; s.ask = ""; s.url = "";
      feed.leave();
    };
    const schedule = () => { if (!s.raf) s.raf = requestAnimationFrame(draw); };
    const q = <T extends Element>(sel: string) => pnl?.querySelector<T>(sel) ?? null;

    /** The room the fixed viewer may use: the grid's stage (a docked drawer already left out), without an open overlay drawer, inside the window. */
    const stageRect = (view: { w: number; h: number }): Box => {
      const w = document.querySelector(".split-work")?.getBoundingClientRect();
      let st = stageBox(w ? { left: w.left, top: w.top, width: w.width, height: w.height } : null, view);
      document.querySelectorAll<HTMLElement>(".split-drawer[data-drawer]:not([data-docked])").forEach((d) => {
        const r = d.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) st = avoidDrawer(st, { left: r.left, top: r.top, width: r.width, height: r.height }, view);
      });
      return st;
    };

    const drawFixed = (L: LoupeProps) => {
      if (!pnl || !pic || !finder) return;
      const off = () => { pnl.hidden = true; finder.hidden = true; s.shown = false; s.announcedShow = false; };
      if (!L.enabled || !s.page || s.escPage === s.page) { off(); return; }
      if (!s.tgt.page) s.tgt.see(s.page);
      const img = s.img;
      let visible = false;
      if (img && img.isConnected) {
        const r = img.getBoundingClientRect();
        if (r.width >= 4 && r.height >= 4) {
          s.natural = img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null;
          s.pageBox = contentBox({ left: r.left, top: r.top, width: r.width, height: r.height }, s.natural);
          s.cellUrl = img.currentSrc || img.src || s.cellUrl;
          visible = true;
        }
      }
      const page = s.pageBox;
      if (!page) { off(); return; }
      const view = { w: document.documentElement.clientWidth || window.innerWidth, h: window.innerHeight };
      const cornerWant = L.corner ?? "bottom-right";
      if (s.cornerProp !== cornerWant) { s.cornerProp = cornerWant; s.corner = cornerWant; }
      let picW: number, picH: number, x: number, y: number;
      if (L.phone) {
        const bar = document.querySelector(".split-actionbar")?.getBoundingClientRect();
        const band = phoneBand(view, bar && bar.height > 0 ? bar.top : null);
        picW = band.width; picH = band.pic; x = band.left; y = band.top;
      } else {
        const sz = viewerSize(s.livePx || L.size || 360, stageRect(view));
        picW = sz.pic; picH = sz.pic;
        const pl = cornerPlacement(s.corner, stageRect(view), sz.w, sz.h);
        x = pl.x; y = pl.y;
      }
      const whole = (L.view ?? "region") === "page";
      // a page narrower than the panel at this zoom would sit small in it: the page is drawn at least as wide as the panel
      const eff = Math.max(L.zoom, picW / Math.max(1, page.width));
      const at = s.kb ? { x: s.fx, y: s.fy } : s.frozen && s.lastAt ? s.lastAt : fractionIn(s.pt, page);
      s.lastAt = at;
      const dpr = window.devicePixelRatio || 1;
      const px = whole ? sharpPixels(Math.max(picW, picH), 1, dpr, L.maxPx) : sharpPixels(Math.max(page.width, page.height), eff, dpr, L.maxPx);
      const key = `${s.page}:${px}`;
      let sharp = feed.peek(s.page, px);
      if (key !== s.ask) { s.ask = key; sharp = feed.hover(s.page, px) ?? sharp; }
      const url = sharp?.url ?? s.cellUrl;
      if (url !== s.url) { s.url = url; pic.style.backgroundImage = url ? `url("${url}")` : "none"; }
      const dims = sharp ? { w: sharp.width, h: sharp.height } : s.natural;
      const bg = whole ? pageFit(dims, page, picW, picH) : regionView(at, page, eff, picW, picH);
      pnl.style.width = `${picW}px`;
      pic.style.height = `${picH}px`;
      pic.style.backgroundSize = `${bg.width}px ${bg.height}px`;
      pic.style.backgroundPosition = `${bg.x}px ${bg.y}px`;
      const wasHidden = pnl.hidden;
      if (wasHidden) pnl.dataset.settle = "1";
      pnl.style.transform = `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`;
      s.panelBox = { left: x, top: y, width: picW, height: picH + VIEWER_HEAD_PX };
      const title = q<HTMLElement>("[data-role=title]"), zoomEl = q<HTMLElement>("[data-role=zoom]");
      if (title) title.textContent = s.tgt.words();
      if (zoomEl) zoomEl.textContent = whole ? "Whole page" : `${zoomWords(eff)} zoom`;
      q("[data-act=view]")?.setAttribute("aria-pressed", String(whole));
      q("[data-act=pin]")?.setAttribute("aria-pressed", String(s.tgt.pinned));
      pic.setAttribute("aria-label", `Magnified page ${s.page}`);
      Object.assign(pnl.dataset, {
        page: String(s.page), corner: s.corner, pinned: String(s.tgt.pinned), view: whole ? "page" : "region", zoom: String(L.zoom),
        size: sharp ? "sharp" : "cell", px: sharp ? String(Math.max(sharp.width, sharp.height)) : "", mode: L.phone ? "band" : "corner",
      });
      pnl.hidden = false; s.shown = true;
      if (wasHidden) requestAnimationFrame(() => { delete pnl.dataset.settle; });
      if (wasHidden && !s.announcedShow) {
        s.announcedShow = true;
        L.announce(`Magnified page viewer, ${L.phone ? "above the action bar" : CORNER_WORDS[s.corner].toLowerCase()}. ${s.tgt.words()}.`);
      }
      // the viewfinder on the hovered thumbnail shows which part of the page the panel magnifies
      const st = L.phone ? null : stageRect(view);
      const cx = page.left + page.width / 2, cy = page.top + page.height / 2;
      const inStage = !st || (cx >= st.left && cx <= st.left + st.width && cy >= st.top && cy <= st.top + st.height);
      if (whole || !visible || !inStage) finder.hidden = true;
      else {
        const f = viewfinderRect(at, page, eff, picW, picH);
        finder.style.transform = `translate3d(${Math.round(f.left)}px, ${Math.round(f.top)}px, 0)`;
        finder.style.width = `${Math.max(4, Math.round(f.width))}px`;
        finder.style.height = `${Math.max(4, Math.round(f.height))}px`;
        finder.dataset.page = String(s.page);
        finder.hidden = false;
      }
    };

    const draw = () => {
      s.raf = 0;
      const L = live.current;
      if (fixed()) { el.hidden = true; drawFixed(L); return; }
      if (pnl && !pnl.hidden) { pnl.hidden = true; if (finder) finder.hidden = true; s.announcedShow = false; }
      const active = L.enabled || (s.touch && !!s.hold?.active);
      const img = s.img;
      if (!active || !img || !s.page || s.escPage === s.page || !img.isConnected) { el.hidden = true; s.shown = false; return; }
      const r = img.getBoundingClientRect();
      if (r.width < 4 || r.height < 4) { el.hidden = true; s.shown = false; return; }
      const page = contentBox({ left: r.left, top: r.top, width: r.width, height: r.height }, img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null);
      const view = { w: document.documentElement.clientWidth || window.innerWidth, h: window.innerHeight };
      const size = lensSize(view);
      const at = s.kb ? { x: s.fx, y: s.fy } : fractionIn(s.pt, page);
      const px = sharpPixels(Math.max(page.width, page.height), L.zoom, window.devicePixelRatio || 1, L.maxPx);
      const key = `${s.page}:${px}`;
      let sharp = feed.peek(s.page, px);
      if (key !== s.ask) { s.ask = key; sharp = feed.hover(s.page, px) ?? sharp; }
      const url = sharp?.url ?? (img.currentSrc || img.src || "");
      if (url !== s.url) { s.url = url; el.style.backgroundImage = url ? `url("${url}")` : "none"; }
      const bg = lensBackground(at, page, L.zoom, size);
      el.style.width = `${size}px`; el.style.height = `${size}px`;
      el.style.backgroundSize = `${bg.width}px ${bg.height}px`;
      el.style.backgroundPosition = `${bg.x}px ${bg.y}px`;
      const mode: Placement = s.kb ? "beside" : s.touch ? "touch" : "pointer";
      const at2 = mode === "beside" ? cellBox(img) ?? page : s.pt;
      const pl = placeLens(at2, size, view, mode);
      el.style.transform = `translate3d(${Math.round(pl.x)}px, ${Math.round(pl.y)}px, 0)`;
      el.setAttribute("aria-label", `Magnified page ${s.page}`);
      el.dataset.page = String(s.page);
      el.dataset.size = sharp ? "sharp" : "cell";
      el.dataset.zoom = String(L.zoom);
      el.dataset.mode = mode;
      el.dataset.px = sharp ? String(Math.max(sharp.width, sharp.height)) : "";
      el.hidden = false; s.shown = true;
    };

    const cellBox = (img: HTMLElement) => {
      const c = img.closest<HTMLElement>(".split-cell, .split-figure-pic") ?? img;
      const b = c.getBoundingClientRect();
      return { left: b.left, top: b.top, width: b.width, height: b.height };
    };

    /** Take `from` as the page under the pointer; false when it is not a page picture (or a start is being dragged, or the viewer is pinned elsewhere). */
    const aim = (from: Element | null): boolean => {
      const t = from?.closest?.<HTMLElement>("[data-loupe]") ?? null;
      if (!t || t.closest("[data-dragging]")) return false;
      const page = Number(t.dataset.loupe);
      const img = t.querySelector("img");
      if (!page || !img) return false;
      if (fixed() && !s.tgt.see(page)) return false;
      if (page !== s.page) { s.page = page; s.ask = ""; s.url = ""; s.pageBox = null; s.frozen = false; s.lastAt = null; }
      if (page !== s.escPage) s.escPage = 0;
      s.img = img;
      return true;
    };

    const away = () => {
      // the fixed viewer stays on the last page when the pointer or the focus leaves, so the eyes can stay on it; the lens goes
      if (fixed()) { s.kb = false; if (s.shown) { s.frozen = true; schedule(); } return; }
      s.escPage = 0; s.kb = false; hide();
    };

    /** The fixed viewer hops to the opposite corner when the pointer stays under it (never a band, a held finger, or when asked not to). */
    const checkHop = (overControls = false) => {
      const L = live.current;
      // a pointer on the panel's own header or grip is reaching for a control, not covering the page: it never makes the panel hop
      const under = (box: Box | null) => !overControls && !!box && (L.hop ?? true) && !L.phone && !s.touch && !s.kb && fixed() && s.shown && hopTarget(s.corner, s.pt, box, true) !== null;
      if (!under(s.panelBox)) { if (s.hopTimer) { clearTimeout(s.hopTimer); s.hopTimer = 0; } return; }
      if (s.hopTimer) return;
      s.hopTimer = setTimeout(() => {
        s.hopTimer = 0;
        if (!under(s.panelBox)) return;
        s.corner = oppositeCorner(s.corner);
        live.current.announce(`Viewer moved to the ${CORNER_WORDS[s.corner].toLowerCase()} corner.`);
        schedule();
      }, HOP_MS);
    };

    // ---- mouse and pen: the lens follows the pointer over a page
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") { touchMove(e); return; }
      if (!live.current.enabled) return;
      s.kb = false; s.touch = false;
      s.pt = { x: e.clientX, y: e.clientY };
      if (fixed()) {
        // over a page the viewer follows; anywhere else (a gutter, the panel, the toolbar) it keeps the last page and spot
        if (aim(e.target as Element | null)) { s.frozen = false; schedule(); } else if (s.shown) { s.frozen = true; schedule(); }
        checkHop(!!(e.target as Element | null)?.closest?.("[data-viewer]"));
        return;
      }
      if (!aim(e.target as Element | null)) { if (s.page) away(); return; }
      schedule();
    };
    const onOut = (e: PointerEvent) => { if (e.pointerType !== "touch" && !e.relatedTarget) away(); };
    const onScroll = () => {
      if (fixed()) { if (s.shown) { s.frozen = true; schedule(); } return; }
      if (s.shown && !s.touch) { el.hidden = true; s.shown = false; feed.leave(); s.ask = ""; }
    };

    // ---- the keyboard
    const onKey = (e: KeyboardEvent) => {
      const L = live.current;
      if (!L.enabled) return;
      if (e.key === "Escape" && s.shown && !document.querySelector("[role=dialog][aria-modal=true]")) { // a modal dialog owns Esc while it is open
        s.escPage = s.page; s.kb = false; el.hidden = true; s.shown = false; s.ask = "";
        if (fixed()) {
          s.tgt.pin(false);
          if (pnl) pnl.hidden = true;
          if (finder) finder.hidden = true;
          s.announcedShow = false;
          L.announce("Magnified page viewer hidden.");
        } else feed.leave();
        e.preventDefault(); e.stopPropagation();
        return;
      }
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const dir = ARROWS[e.key];
        const zoomDir = e.key === "=" || e.key === "+" || e.code === "Equal" || e.code === "NumpadAdd" ? 1 : e.key === "-" || e.key === "_" || e.code === "Minus" || e.code === "NumpadSubtract" ? -1 : 0;
        if (!dir && !zoomDir) return;
        const cell = (document.activeElement as Element | null)?.closest?.("[data-cell]");
        const target = cell?.querySelector("[data-loupe]") ?? (s.kb ? s.img?.closest("[data-loupe]") ?? null : null);
        if (!target) return;
        e.preventDefault(); e.stopPropagation();
        const starting = !s.kb;
        if (!aim(target)) return;
        s.kb = true; s.touch = false;
        if (starting) {
          s.fx = 0.5; s.fy = 0.5; s.escPage = 0;
          L.announce(`Magnifier on page ${s.page}, ${zoomWords(L.zoom)}. Alt and the arrow keys move it, Alt and plus or minus zoom, Escape hides it.`);
        }
        if (dir) { s.fx = Math.min(1, Math.max(0, s.fx + dir[0] * 0.1)); s.fy = Math.min(1, Math.max(0, s.fy + dir[1] * 0.1)); }
        if (zoomDir) { const z = stepZoom(L.zoom, zoomDir as 1 | -1); if (z !== L.zoom) { L.onZoom(z); L.announce(`Magnifier ${zoomWords(z)}`); } }
        schedule();
        return;
      }
      if (KEY_NAV.has(e.key) && !e.altKey) s.lastKey = performance.now();
    };
    // a page the keyboard has just moved to shows the lens beside it, centred on the page
    const onFocusIn = (e: FocusEvent) => {
      if (!live.current.enabled) return;
      const t = e.target as HTMLElement | null;
      if (!t?.matches?.(".split-cell-btn") || performance.now() - s.lastKey > 700) return;
      const pic2 = t.querySelector("[data-loupe]");
      if (!pic2) return;
      if (fixed() && s.tgt.pinned && Number((pic2 as HTMLElement).dataset.loupe) !== s.tgt.page) return;
      s.escPage = 0; s.kb = true; s.touch = false; s.fx = 0.5; s.fy = 0.5; s.page = 0;
      if (aim(pic2)) schedule();
    };
    const onFocusOut = (e: FocusEvent) => { if (s.kb && !(e.relatedTarget as Element | null)?.closest?.(".split-cell-btn, [data-viewer]")) away(); };

    // ---- Alt and the wheel change the zoom (the plain wheel scrolls the pages)
    const onWheel = (e: WheelEvent) => {
      if (!e.altKey || !s.shown) return;
      e.preventDefault();
      const now = performance.now();
      if (now - s.lastWheel < 70) return;
      s.lastWheel = now;
      const L = live.current;
      const z = stepZoom(L.zoom, e.deltaY < 0 ? 1 : -1);
      if (z !== L.zoom) { L.onZoom(z); L.announce(`Magnifier ${zoomWords(z)}`); }
    };

    // ---- touch: press and hold on a page, then drag; the lens rides above the finger
    const stopMove = (e: TouchEvent) => { if (s.hold?.active && e.cancelable) e.preventDefault(); };
    const clearHold = () => {
      const h = s.hold;
      if (!h) return;
      if (h.timer) clearTimeout(h.timer);
      if (h.active) { s.noClickUntil = performance.now() + 600; document.removeEventListener("touchmove", stopMove); }
      s.hold = null; s.touch = false;
    };
    const onDown = (e: PointerEvent) => {
      if (e.pointerType !== "touch" || !live.current.touchMode) return;
      clearHold();
      const from = e.target as Element | null;
      if (!from?.closest?.("[data-loupe]")) return;
      const h: Hold = { id: e.pointerId, x: e.clientX, y: e.clientY, active: false, from, timer: null };
      h.timer = setTimeout(() => {
        h.timer = null;
        if (s.hold !== h) return;
        h.active = true; s.touch = true; s.kb = false; s.pt = { x: h.x, y: h.y };
        document.addEventListener("touchmove", stopMove, { passive: false });
        if (aim(h.from)) { s.frozen = false; schedule(); } else if (!fixed()) clearHold();
      }, HOLD_MS);
      s.hold = h;
    };
    const touchMove = (e: PointerEvent) => {
      const h = s.hold;
      if (!h || h.id !== e.pointerId) return;
      if (!h.active) { if (Math.hypot(e.clientX - h.x, e.clientY - h.y) > HOLD_SLOP_PX) clearHold(); return; }
      s.pt = { x: e.clientX, y: e.clientY };
      // a touch is captured by the page it began on, so the page under the finger is asked of the document
      if (aim(document.elementFromPoint(e.clientX, e.clientY))) { s.frozen = false; schedule(); }
      else if (fixed()) { s.frozen = true; schedule(); }
      else { el.hidden = true; s.shown = false; }
    };
    const onUp = (e: PointerEvent) => {
      if (e.pointerType !== "touch" || !s.hold || s.hold.id !== e.pointerId) return;
      clearHold();
      away();
    };
    // the click that ends a hold and the menu the browser opens for a long press are not a person's marking
    const onClickCapture = (e: Event) => { if (performance.now() < s.noClickUntil) { e.stopPropagation(); e.preventDefault(); } };
    const onMenuCapture = (e: Event) => { if (s.hold?.active || performance.now() < s.noClickUntil) { e.stopPropagation(); e.preventDefault(); } };
    const onBlur = () => away();

    // ---- the fixed viewer's own controls: pin, hide, and the size (a drag on the inner corner, or the keys on it)
    const pin = () => {
      const on = s.tgt.pin();
      live.current.announce(on ? `Viewer pinned to page ${s.tgt.page}.` : "Viewer unpinned; it follows the pointer again.");
      s.ask = ""; schedule();
    };
    const hideNow = () => {
      s.escPage = s.page; s.tgt.pin(false);
      if (pnl) pnl.hidden = true;
      if (finder) finder.hidden = true;
      s.shown = false; s.announcedShow = false;
      live.current.announce("Magnified page viewer hidden.");
    };
    const resize = (px: number) => { const v = clampViewerPx(px); s.livePx = 0; live.current.onSize?.(v); live.current.announce(`Viewer ${v} pixels wide.`); schedule(); };
    api.current = { pin, hideNow, resize };
    let dragId: number | null = null;
    const grip = q<HTMLElement>("[data-act=resize]");
    const gripDown = (e: PointerEvent) => { dragId = e.pointerId; e.preventDefault(); };
    const gripMove = (e: PointerEvent) => {
      if (dragId !== e.pointerId || !s.panelBox) return;
      const b = s.panelBox;
      const right = s.corner.endsWith("right");
      const w = right ? b.left + b.width - e.clientX : e.clientX - b.left;
      s.livePx = clampViewerPx(w); schedule();
    };
    const gripUp = (e: PointerEvent) => {
      if (dragId !== e.pointerId) return;
      dragId = null;
      const v = s.livePx; s.livePx = 0;
      if (v) live.current.onSize?.(v);
      schedule();
    };
    const gripKey = (e: KeyboardEvent) => {
      const grow = e.key === "ArrowUp" || e.key === "ArrowRight" || e.key === "+" || e.key === "=";
      const shrink = e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "-" || e.key === "_";
      if (!grow && !shrink) return;
      e.preventDefault(); e.stopPropagation();
      resize((s.panelBox?.width ?? live.current.size ?? 360) + (grow ? RESIZE_STEP : -RESIZE_STEP));
    };
    grip?.addEventListener("pointerdown", gripDown);
    document.addEventListener("pointermove", gripMove, { passive: true });
    document.addEventListener("pointerup", gripUp, { passive: true });
    document.addEventListener("pointercancel", gripUp, { passive: true });
    grip?.addEventListener("keydown", gripKey);

    const onRedraw = () => { s.ask = ""; schedule(); };
    el.addEventListener("loupe-zoom", onRedraw);
    document.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerout", onOut, { passive: true });
    document.addEventListener("pointerdown", onDown, { passive: true });
    document.addEventListener("pointerup", onUp, { passive: true });
    document.addEventListener("pointercancel", onUp, { passive: true });
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    document.addEventListener("wheel", onWheel, { passive: false });
    document.addEventListener("click", onClickCapture, true);
    document.addEventListener("contextmenu", onMenuCapture, true);
    window.addEventListener("blur", onBlur);
    return () => {
      api.current = null;
      el.removeEventListener("loupe-zoom", onRedraw);
      grip?.removeEventListener("pointerdown", gripDown);
      document.removeEventListener("pointermove", gripMove);
      document.removeEventListener("pointerup", gripUp);
      document.removeEventListener("pointercancel", gripUp);
      grip?.removeEventListener("keydown", gripKey);
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerout", onOut);
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      document.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("focusin", onFocusIn);
      document.removeEventListener("focusout", onFocusOut);
      document.removeEventListener("wheel", onWheel);
      document.removeEventListener("click", onClickCapture, true);
      document.removeEventListener("contextmenu", onMenuCapture, true);
      document.removeEventListener("touchmove", stopMove);
      window.removeEventListener("blur", onBlur);
      if (s.hold?.timer) clearTimeout(s.hold.timer);
      if (s.hopTimer) clearTimeout(s.hopTimer);
      if (s.raf) cancelAnimationFrame(s.raf);
      el.hidden = true;
      if (pnl) pnl.hidden = true;
      if (finder) finder.hidden = true;
      feed.dispose();
    };
    // the lens is rebuilt when the source of pictures or the budget changes (a different draft); the rest is read live
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted, p.budget.count, p.budget.bytes, p.load]);

  // a change of zoom, mode, view, size, or corner redraws the lens or the viewer where it stands
  useEffect(() => { lens.current?.dispatchEvent(new Event("loupe-zoom")); }, [p.zoom, p.mode, p.view, p.size, p.corner, p.phone]);

  if (typeof document === "undefined") return null;
  return createPortal(
    <>
      <div ref={lens} className="split-loupe" role="img" aria-hidden="true" aria-label="Magnified page" hidden style={{ pointerEvents: "none" }} data-zoom-min={LOUPE_ZOOM_MIN} />
      <div ref={panel} className="split-viewer" role="region" aria-label="Magnified page" hidden data-viewer="" data-corner={p.corner ?? "bottom-right"}>
        <div className="split-viewer-head">
          <strong data-role="title">Page</strong>
          <span data-role="zoom" className="split-viewer-zoom" />
          <span className="split-viewer-acts">
            <button type="button" data-act="view" aria-pressed={(p.view ?? "region") === "page"} title="Show the whole page, or a magnified region"
              onClick={() => { const v = (p.view ?? "region") === "page" ? "region" : "page"; p.onView?.(v); p.announce(v === "page" ? "Viewer shows the whole page." : "Viewer shows a magnified region."); }}>Whole page</button>
            <button type="button" data-act="pin" aria-pressed="false" title="Keep the viewer on this page" onClick={() => api.current?.pin()}>Pin</button>
            <button type="button" data-act="hide" title="Hide the viewer (Esc)" onClick={() => api.current?.hideNow()}>Hide</button>
          </span>
        </div>
        <div ref={viewPic} className="split-viewer-pic" role="img" aria-label="Magnified page" />
        <button type="button" className="split-viewer-grip" data-act="resize" aria-label="Resize the viewer: drag, or use the arrow keys" title="Resize the viewer" />
      </div>
      <div ref={viewfinder} className="split-viewfinder" aria-hidden="true" hidden />
    </>,
    document.body,
  );
}
