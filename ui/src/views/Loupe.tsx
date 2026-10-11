import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  HOLD_MS, HOLD_SLOP_PX, LOUPE_ZOOM_MIN, LoupeFeed, contentBox, fractionIn, lensBackground, lensSize, placeLens, sharpPixels, stepZoom, zoomWords,
  type Budget, type Placement, type Pt, type Sharp, type SharpLoader,
} from "./splitLoupe";

/** The magnifier (docs/pdf-splitter.md, section 5.12). One lens element, reused for every page and every view: a page picture marks itself
 * with `data-loupe="<page>"` (the grid's cells and the compare figure), and this component, which listens on the document, finds the page
 * under the pointer, the held finger, or the focused cell. The lens never takes a pointer event (`pointer-events: none`), never captures the
 * pointer, and never cancels a press, so a click or a drag through it marks the page as it would without it. It is placed with a transform in
 * an animation frame; nothing here is React state, so a moving pointer costs no render. */

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
}

interface Hold { id: number; x: number; y: number; timer: ReturnType<typeof setTimeout> | null; active: boolean; from: Element | null }

const ARROWS: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
const KEY_NAV = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown", "Tab"]);

export function Loupe(p: LoupeProps) {
  const lens = useRef<HTMLDivElement>(null);
  const live = useRef(p);
  live.current = p;
  const wanted = p.enabled || p.touchMode;

  useEffect(() => {
    const el = lens.current;
    if (!el || !wanted) return;
    const s = {
      page: 0, img: null as HTMLImageElement | null, pt: { x: 0, y: 0 } as Pt, touch: false,
      kb: false, fx: 0.5, fy: 0.5, escPage: 0, raf: 0, shown: false, ask: "", url: "", lastKey: -Infinity, noClickUntil: 0, lastWheel: -Infinity,
      hold: null as Hold | null,
    };
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

    const draw = () => {
      s.raf = 0;
      const L = live.current;
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

    /** Take `from` as the page under the pointer; false when it is not a page picture (or a start is being dragged). */
    const aim = (from: Element | null): boolean => {
      const t = from?.closest?.<HTMLElement>("[data-loupe]") ?? null;
      if (!t || t.closest("[data-dragging]")) return false;
      const page = Number(t.dataset.loupe);
      const img = t.querySelector("img");
      if (!page || !img) return false;
      if (page !== s.page) { s.page = page; s.ask = ""; s.url = ""; }
      if (page !== s.escPage) s.escPage = 0;
      s.img = img;
      return true;
    };

    const away = () => { s.escPage = 0; s.kb = false; hide(); };

    // ---- mouse and pen: the lens follows the pointer over a page
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") { touchMove(e); return; }
      if (!live.current.enabled) return;
      s.kb = false; s.touch = false;
      s.pt = { x: e.clientX, y: e.clientY };
      if (!aim(e.target as Element | null)) { if (s.page) away(); return; }
      schedule();
    };
    const onOut = (e: PointerEvent) => { if (e.pointerType !== "touch" && !e.relatedTarget) away(); };
    const onScroll = () => { if (s.shown && !s.touch) { el.hidden = true; s.shown = false; feed.leave(); s.ask = ""; } };

    // ---- the keyboard
    const onKey = (e: KeyboardEvent) => {
      const L = live.current;
      if (!L.enabled) return;
      if (e.key === "Escape" && s.shown) {
        s.escPage = s.page; s.kb = false; el.hidden = true; s.shown = false; feed.leave(); s.ask = "";
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
        if (starting) { s.fx = 0.5; s.fy = 0.5; s.escPage = 0; L.announce(`Magnifier on page ${s.page}, ${zoomWords(L.zoom)}. Alt and the arrow keys move it, Alt and plus or minus zoom, Escape hides it.`); }
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
      const pic = t.querySelector("[data-loupe]");
      if (!pic) return;
      s.escPage = 0; s.kb = true; s.touch = false; s.fx = 0.5; s.fy = 0.5; s.page = 0;
      if (aim(pic)) schedule();
    };
    const onFocusOut = (e: FocusEvent) => { if (s.kb && !(e.relatedTarget as Element | null)?.closest?.(".split-cell-btn")) away(); };

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
        if (aim(h.from)) schedule(); else clearHold();
      }, HOLD_MS);
      s.hold = h;
    };
    const touchMove = (e: PointerEvent) => {
      const h = s.hold;
      if (!h || h.id !== e.pointerId) return;
      if (!h.active) { if (Math.hypot(e.clientX - h.x, e.clientY - h.y) > HOLD_SLOP_PX) clearHold(); return; }
      s.pt = { x: e.clientX, y: e.clientY };
      // a touch is captured by the page it began on, so the page under the finger is asked of the document
      if (aim(document.elementFromPoint(e.clientX, e.clientY))) schedule();
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

    const onZoomed = () => { s.ask = ""; schedule(); };
    el.addEventListener("loupe-zoom", onZoomed);
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
      el.removeEventListener("loupe-zoom", onZoomed);
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
      if (s.raf) cancelAnimationFrame(s.raf);
      el.hidden = true;
      feed.dispose();
    };
    // the lens is rebuilt when the source of pictures or the budget changes (a different draft); the rest is read live
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted, p.budget.count, p.budget.bytes, p.load]);

  // a change of zoom redraws the lens where it stands
  useEffect(() => { lens.current?.dispatchEvent(new Event("loupe-zoom")); }, [p.zoom]);

  if (typeof document === "undefined") return null;
  return createPortal(<div ref={lens} className="split-loupe" role="img" aria-label="Magnified page" hidden style={{ pointerEvents: "none" }} data-zoom-min={LOUPE_ZOOM_MIN} />, document.body);
}
