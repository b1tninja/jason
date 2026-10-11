/** The magnifier's logic (docs/pdf-splitter.md, section 5.12): where the lens goes, how far it zooms, and how its sharp picture is fetched.
 * Pure helpers and one small class; nothing here touches React or the page, so each rule is tested with a fake loader and fake timers. */

export const LOUPE_ZOOM_MIN = 2;
export const LOUPE_ZOOM_MAX = 6;
export const LOUPE_ZOOM_DEFAULT = 3;
export const LOUPE_ZOOM_STEP = 0.5;
export const LENS_PX = 220;
/** the pointer rests this long on a page before its sharp picture is asked for */
export const DWELL_MS = 150;
/** a finger held still this long (inside the magnify mode) starts the lens */
export const HOLD_MS = 350;
/** a finger that moves farther than this before the hold is over is a scroll, not a hold */
export const HOLD_SLOP_PX = 8;
/** the sharpest picture a browser-drawn page is asked for: 300 dpi on a letter page (the drawing itself never goes past 300 dpi) */
export const LOUPE_MAX_PX = 3300;
/** what the server can give (its largest size) */
export const SERVER_MAX_PX = 1600;

export interface Pt { x: number; y: number }
export interface Box { left: number; top: number; width: number; height: number }

export function clampZoom(z: number): number {
  if (!Number.isFinite(z)) return LOUPE_ZOOM_DEFAULT;
  const stepped = Math.round(z / LOUPE_ZOOM_STEP) * LOUPE_ZOOM_STEP;
  return Math.min(LOUPE_ZOOM_MAX, Math.max(LOUPE_ZOOM_MIN, stepped));
}

/** The next zoom a step away (`dir` 1 or -1), held to 2x through 6x. */
export function stepZoom(z: number, dir: 1 | -1): number { return clampZoom(clampZoom(z) + dir * LOUPE_ZOOM_STEP); }

/** "3x", "2.5x" */
export function zoomWords(z: number): string { return `${Number.isInteger(z) ? z : z.toFixed(1)} times`; }

/** The part of an `<img>` box the page itself covers (`object-fit: contain`): the picture is centred and keeps its shape. */
export function contentBox(box: Box, natural: { w: number; h: number } | null): Box {
  if (!natural || natural.w <= 0 || natural.h <= 0 || box.width <= 0 || box.height <= 0) return box;
  const s = Math.min(box.width / natural.w, box.height / natural.h);
  const w = natural.w * s, h = natural.h * s;
  return { left: box.left + (box.width - w) / 2, top: box.top + (box.height - h) / 2, width: w, height: h };
}

/** Where on the page the pointer is, as fractions of the page's width and height (held to the page). */
export function fractionIn(pt: Pt, page: Box): Pt {
  const f = (v: number, lo: number, len: number) => (len > 0 ? Math.min(1, Math.max(0, (v - lo) / len)) : 0.5);
  return { x: f(pt.x, page.left, page.width), y: f(pt.y, page.top, page.height) };
}

/** The lens picture: the page drawn `zoom` times as wide as it is on screen, placed so the spot `at` (fractions of the page) is in the lens's centre. */
export function lensBackground(at: Pt, page: Box, zoom: number, lens: number): { width: number; height: number; x: number; y: number } {
  const width = page.width * zoom, height = page.height * zoom;
  return { width, height, x: lens / 2 - at.x * width, y: lens / 2 - at.y * height };
}

export type Placement = "pointer" | "touch" | "beside";
export interface Placed { x: number; y: number; flipX: boolean; flipY: boolean }

/** The lens's top-left corner, kept inside the viewport.
 * - `pointer`: down and to the right of the pointer; on the left of it when there is no room at the right, above it when none below.
 * - `touch`: above the finger (centred on it), below when there is no room above, so the finger never covers it.
 * - `beside`: beside a box (the focused page), on its right, else its left, else below, else above.
 * It is finally held inside the viewport, so it always shows whole. */
export function placeLens(at: Pt | Box, lens: number, view: { w: number; h: number }, mode: Placement, gap = 18): Placed {
  const m = 6;
  let x: number, y: number, flipX = false, flipY = false;
  if (mode === "beside") {
    const b = at as Box;
    x = b.left + b.width + gap; y = b.top + b.height / 2 - lens / 2;
    if (x + lens > view.w - m) {
      flipX = true; x = b.left - gap - lens;
      if (x < m) { x = b.left + b.width / 2 - lens / 2; y = b.top + b.height + gap; if (y + lens > view.h - m) { flipY = true; y = b.top - gap - lens; } }
    }
  } else if (mode === "touch") {
    const p = at as Pt;
    x = p.x - lens / 2; y = p.y - gap - lens - 28;
    if (y < m) { flipY = true; y = p.y + gap + 28; }
  } else {
    const p = at as Pt;
    x = p.x + gap; y = p.y + gap;
    if (x + lens > view.w - m) { flipX = true; x = p.x - gap - lens; }
    if (y + lens > view.h - m) { flipY = true; y = p.y - gap - lens; }
  }
  const hold = (v: number, len: number) => Math.max(m, Math.min(v, len - m - lens));
  return { x: hold(x, view.w), y: hold(y, view.h), flipX, flipY };
}

/** The lens is no bigger than the window leaves room for. */
export function lensSize(view: { w: number; h: number }, want = LENS_PX): number { return Math.max(96, Math.min(want, view.w - 12, view.h - 12)); }

/** The size of picture to ask for so the lens is sharp: the page's width on screen times the zoom times the screen's pixel ratio, up to the most the source can give. */
export function sharpPixels(pageLongest: number, zoom: number, dpr: number, max: number): number {
  const need = Math.ceil(pageLongest * zoom * dpr);
  return Math.min(max, Math.max(SERVER_MAX_PX, need));
}

// ---- the sharp pictures

/** One sharp picture, as the source gave it. `best` says nothing sharper exists (the server's largest size, or the page's own detail), so it is never asked for again. */
export interface Sharp { url: string; width: number; height: number; px: number; best: boolean }
export type SharpLoader = (page: number, px: number, signal: AbortSignal) => Promise<Sharp>;
export interface Budget { count: number; bytes: number }

/** A few sharp pictures at a time: at most `count`, and at most `bytes` of decoded pixels (width x height x 4), the same memory the thumbnails are held to. */
export function loupeBudget(megabytes: number, small: boolean): Budget {
  return { count: small ? 2 : 3, bytes: Math.round(Math.min(160, Math.max(24, megabytes * 0.5)) * 1e6) };
}

type Timers = { set: (fn: () => void, ms: number) => unknown; clear: (h: unknown) => void };
const realTimers: Timers = { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as ReturnType<typeof setTimeout>) };

export interface FeedOpts {
  load: SharpLoader;
  /** called when a page's sharp picture is ready (the lens swaps to it) */
  onSharp: (page: number, s: Sharp) => void;
  /** called with the reason when a picture could not be had (the lens keeps the picture it has) */
  onFail?: (page: number, why: string) => void;
  /** a picture leaves the cache */
  release?: (s: Sharp) => void;
  budget: Budget;
  dwellMs?: number;
  timers?: Timers;
}

/** What the lens shows. It waits `dwellMs` on a page before asking for the sharp picture, asks for one at a time, drops the request when the
 * pointer leaves or goes to another page, and keeps the last few pictures. */
export class LoupeFeed {
  private cache = new Map<number, Sharp>();
  private bytes = 0;
  private page = 0;
  private px = 0;
  private timer: unknown = null;
  private ctl: AbortController | null = null;
  private ctlPage = 0;
  private o: FeedOpts;
  private timers: Timers;
  counts = { requested: 0, aborted: 0, hits: 0 };

  constructor(o: FeedOpts) { this.o = o; this.timers = o.timers ?? realTimers; }

  /** The picture held for a page that is sharp enough for `px` (or the sharpest there is), and counts as used. */
  peek(page: number, px: number): Sharp | undefined {
    const s = this.cache.get(page);
    if (!s || !(s.best || s.px >= px)) return undefined;
    this.cache.delete(page); this.cache.set(page, s);
    return s;
  }

  /** The pointer is on `page`, which needs a picture of `px` pixels. Returns a held picture at once; otherwise asks for one after the dwell. */
  hover(page: number, px: number): Sharp | undefined {
    const held = this.peek(page, px);
    if (held) { this.counts.hits += 1; if (this.page !== page) this.cancel(); this.page = page; this.px = px; return held; }
    if (page === this.page && px <= this.px && (this.timer !== null || this.ctl)) return undefined;     // already waiting for this one
    this.cancel();
    this.page = page; this.px = px;
    this.timer = this.timers.set(() => { this.timer = null; this.start(page, px); }, this.o.dwellMs ?? DWELL_MS);
    return undefined;
  }

  /** The pointer left the pages: nothing is waited for and nothing is fetched. */
  leave(): void { this.cancel(); this.page = 0; this.px = 0; }

  get inflight(): boolean { return this.ctl !== null; }
  get waiting(): boolean { return this.timer !== null; }
  get held(): number[] { return [...this.cache.keys()]; }
  get heldBytes(): number { return this.bytes; }

  dispose(): void {
    this.leave();
    for (const s of this.cache.values()) this.o.release?.(s);
    this.cache.clear(); this.bytes = 0;
  }

  private cancel(): void {
    if (this.timer !== null) { this.timers.clear(this.timer); this.timer = null; }
    if (this.ctl) { this.ctl.abort(); this.ctl = null; this.counts.aborted += 1; }
  }

  private start(page: number, px: number): void {
    const ctl = new AbortController();
    this.ctl = ctl; this.ctlPage = page;
    this.counts.requested += 1;
    this.o.load(page, px, ctl.signal).then(
      (s) => {
        if (this.ctl !== ctl) { this.o.release?.(s); return; }                 // cancelled meanwhile
        this.ctl = null;
        this.keep(page, s);
        this.o.onSharp(page, s);
      },
      (e: unknown) => {
        if (this.ctl !== ctl) return;
        this.ctl = null;
        if (e instanceof DOMException && e.name === "AbortError") return;
        this.o.onFail?.(this.ctlPage, e instanceof Error ? e.message : "The sharp picture could not be had");
      },
    );
  }

  private keep(page: number, s: Sharp): void {
    const old = this.cache.get(page);
    if (old) { this.bytes -= old.width * old.height * 4; if (old.url !== s.url) this.o.release?.(old); this.cache.delete(page); }
    this.cache.set(page, s);
    this.bytes += s.width * s.height * 4;
    // the least recently used go first; the one just kept stays however big it is
    for (const k of [...this.cache.keys()]) {
      if (this.cache.size <= this.o.budget.count && this.bytes <= this.o.budget.bytes) break;
      if (k === page) continue;
      const v = this.cache.get(k)!;
      this.cache.delete(k); this.bytes -= v.width * v.height * 4;
      this.o.release?.(v);
    }
  }
}

// ---- whether the magnifier is on

/** The setting, or the device's own answer when none was chosen: on for a mouse or trackpad (a fine pointer that hovers), off for touch. */
export function magnifierOn(pref: boolean | null | undefined, fineHover: boolean): boolean { return typeof pref === "boolean" ? pref : fineHover; }

export const FINE_HOVER = "(hover: hover) and (pointer: fine)";

// ---- where the sharp picture comes from

export interface SharpSources {
  /** a file drawn in this browser: a finer drawing, or null when the browser is not the source for this page */
  drawLarge?: (page: number, px: number, signal: AbortSignal) => Promise<{ url: string; px: number } | null>;
  /** the server's largest picture (1600 px) as an address a picture can be made from */
  server: (page: number, signal: AbortSignal) => Promise<string>;
  /** the picture's own size once it can be drawn (the browser's decoder) */
  decode?: (url: string, signal: AbortSignal) => Promise<{ w: number; h: number }>;
}

/** The browser's own decoder: resolves when the picture can be painted, with its size. */
export function decodeImage(url: string, signal: AbortSignal): Promise<{ w: number; h: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const stop = () => reject(new DOMException("aborted", "AbortError"));
    if (signal.aborted) return stop();
    signal.addEventListener("abort", stop, { once: true });
    const ok = () => { signal.removeEventListener("abort", stop); resolve({ w: img.naturalWidth, h: img.naturalHeight }); };
    const bad = () => { signal.removeEventListener("abort", stop); reject(new Error("The sharp picture could not be drawn")); };
    img.onerror = bad;
    img.src = url;
    if (typeof img.decode === "function") img.decode().then(ok, () => { if (img.complete && img.naturalWidth) ok(); else bad(); });
    else img.onload = ok;
  });
}

/** The loader the lens uses: a browser-drawn page at up to `px` pixels, else the server's largest size. A page the browser could not draw
 * falls back to the server's, as a cell's does. */
export function sharpLoader(src: SharpSources): SharpLoader {
  return async (page, px, signal) => {
    let url = "", asked = SERVER_MAX_PX;
    const big = src.drawLarge ? await src.drawLarge(page, px, signal) : null;
    if (big) { url = big.url; asked = big.px; }
    else url = await src.server(page, signal);
    let size: { w: number; h: number };
    try { size = await (src.decode ?? decodeImage)(url, signal); } catch (e) { releaseUrl(url); throw e; }
    const longest = Math.max(size.w, size.h);
    // nothing sharper exists when the source gave all it has: the server's largest size, or a drawing that stopped at the page's own detail
    const best = !big || asked >= LOUPE_MAX_PX || longest < asked - 1;
    return { url, width: size.w, height: size.h, px: big ? Math.min(asked, longest || asked) : SERVER_MAX_PX, best };
  };
}

export function releaseUrl(url: string): void { if (url.startsWith("blob:") && typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url); }
export function releaseSharp(s: Sharp): void { releaseUrl(s.url); }

// ---- the fixed viewer (section 5.12, second mode): a panel in a screen corner that shows the page under the pointer

export type MagMode = "lens" | "fixed";
export type Corner = "bottom-right" | "bottom-left" | "top-right" | "top-left";
export type ViewerView = "region" | "page";
export type ViewerSize = "small" | "medium" | "large";
export const CORNERS: Corner[] = ["bottom-right", "bottom-left", "top-right", "top-left"];
export const CORNER_WORDS: Record<Corner, string> = { "bottom-right": "Bottom right", "bottom-left": "Bottom left", "top-right": "Top right", "top-left": "Top left" };
/** the picture area of the panel, in CSS px (the panel adds its header strip) */
export const VIEWER_SIZES: Record<ViewerSize, number> = { small: 260, medium: 360, large: 480 };
export const VIEWER_DEFAULT_PX = 360;
export const VIEWER_MIN_PX = 160;
export const VIEWER_MAX_PX = 720;
export const VIEWER_HEAD_PX = 58;
/** the pointer must stay under the panel this long before the panel hops to the other corner */
export const HOP_MS = 280;
/** the phone's band takes this share of the window's height */
export const PHONE_BAND = 0.4;
export const VIEWER_MARGIN = 12;

export function clampViewerPx(px: number): number {
  if (!Number.isFinite(px)) return VIEWER_DEFAULT_PX;
  return Math.min(VIEWER_MAX_PX, Math.max(VIEWER_MIN_PX, Math.round(px)));
}

export function oppositeCorner(c: Corner): Corner {
  return ({ "bottom-right": "top-left", "top-left": "bottom-right", "bottom-left": "top-right", "top-right": "bottom-left" } as const)[c];
}

export function isCorner(v: unknown): v is Corner { return typeof v === "string" && (CORNERS as string[]).includes(v); }

/** The part of `a` that is inside `b` (never negative). */
export function intersectBox(a: Box, b: Box): Box {
  const left = Math.max(a.left, b.left), top = Math.max(a.top, b.top);
  const right = Math.min(a.left + a.width, b.left + b.width), bottom = Math.min(a.top + a.height, b.top + b.height);
  return { left, top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
}

/** The room the panel may use: the grid's stage (which already leaves out a docked drawer), held inside the window. */
export function stageBox(stage: Box | null, view: { w: number; h: number }): Box {
  const win: Box = { left: 0, top: 0, width: view.w, height: view.h };
  return stage ? intersectBox(stage, win) : win;
}

/** An open overlay drawer takes its side of the stage: the panel is kept out of it. A drawer that is not a side or a bottom sheet is ignored. */
export function avoidDrawer(stage: Box, drawer: Box, view: { w: number; h: number }): Box {
  const d = intersectBox(drawer, stage);
  if (d.width < 8 || d.height < 8) return stage;
  const tall = d.height >= stage.height * 0.8, wide = d.width >= stage.width * 0.8;
  if (tall && !wide) {
    const left = d.left + d.width / 2 < stage.left + stage.width / 2;
    return left ? { ...stage, left: d.left + d.width, width: stage.left + stage.width - (d.left + d.width) }
      : { ...stage, width: d.left - stage.left };
  }
  if (wide && !tall && d.top + d.height / 2 > view.h / 2) return { ...stage, height: d.top - stage.top };
  return stage;
}

/** The picture area's side, and the panel's whole size, for a wanted size: no bigger than the room leaves. */
export function viewerSize(want: number, stage: Box, margin = VIEWER_MARGIN): { pic: number; w: number; h: number } {
  const room = Math.min(stage.width - 2 * margin, stage.height - 2 * margin - VIEWER_HEAD_PX);
  const pic = Math.max(96, Math.min(clampViewerPx(want), Math.floor(room)));
  return { pic, w: pic, h: pic + VIEWER_HEAD_PX };
}

/** The panel's top-left corner for a corner of the stage, held inside it. */
export function cornerPlacement(corner: Corner, stage: Box, w: number, h: number, margin = VIEWER_MARGIN): Pt {
  const right = corner.endsWith("right"), bottom = corner.startsWith("bottom");
  const x = right ? stage.left + stage.width - w - margin : stage.left + margin;
  const y = bottom ? stage.top + stage.height - h - margin : stage.top + margin;
  return { x: Math.max(stage.left, Math.round(x)), y: Math.max(stage.top, Math.round(y)) };
}

/** The phone's band: a fixed share of the window's height, full width, just above the action bar (or the window's bottom). */
export function phoneBand(view: { w: number; h: number }, barTop: number | null, share = PHONE_BAND, margin = 6): Box & { pic: number } {
  const bottom = Math.min(view.h, barTop ?? view.h) - margin;
  const height = Math.max(VIEWER_HEAD_PX + 60, Math.round(view.h * share));
  const top = Math.max(0, bottom - height);
  return { left: margin, top, width: Math.max(96, view.w - 2 * margin), height: bottom - top, pic: Math.max(60, bottom - top - VIEWER_HEAD_PX) };
}

export function underPanel(pt: Pt, panel: Box, pad = 10): boolean {
  return pt.x >= panel.left - pad && pt.x <= panel.left + panel.width + pad && pt.y >= panel.top - pad && pt.y <= panel.top + panel.height + pad;
}

/** The corner the panel should hop to: the opposite one, when the pointer is under it and hopping is allowed; otherwise nothing. */
export function hopTarget(corner: Corner, pt: Pt, panel: Box, allowed: boolean, pad = 10): Corner | null {
  return allowed && underPanel(pt, panel, pad) ? oppositeCorner(corner) : null;
}

/** The region the panel shows: the page drawn `zoom` times as wide as on screen, with the spot `at` in the panel's centre, kept so the panel
 * never shows beyond the page's edge (a page narrower than the panel is centred). `cx`/`cy` are the spot actually centred. */
export function regionView(at: Pt, page: Box, zoom: number, w: number, h: number): { width: number; height: number; x: number; y: number; cx: number; cy: number } {
  const width = page.width * zoom, height = page.height * zoom;
  const centre = (f: number, len: number, view: number) => (len <= view ? 0.5 : Math.min(1 - view / 2 / len, Math.max(view / 2 / len, f)));
  const cx = centre(at.x, width, w), cy = centre(at.y, height, h);
  return { width, height, x: w / 2 - cx * width, y: h / 2 - cy * height, cx, cy };
}

/** The rectangle to draw on the hovered thumbnail so a person sees which part the panel magnifies (on screen, in the page's own pixels). */
export function viewfinderRect(at: Pt, page: Box, zoom: number, w: number, h: number): Box {
  const r = regionView(at, page, zoom, w, h);
  const vw = Math.min(page.width, w / zoom), vh = Math.min(page.height, h / zoom);
  return { left: page.left + r.cx * page.width - vw / 2, top: page.top + r.cy * page.height - vh / 2, width: vw, height: vh };
}

/** The whole page fitted inside the panel's picture area, centred (a background's size and position). */
export function pageFit(natural: { w: number; h: number } | null, page: Box, w: number, h: number): { width: number; height: number; x: number; y: number } {
  const aw = natural && natural.w > 0 ? natural.w : page.width, ah = natural && natural.h > 0 ? natural.h : page.height;
  const s = aw > 0 && ah > 0 ? Math.min(w / aw, h / ah) : 1;
  const width = aw * s, height = ah * s;
  return { width, height, x: (w - width) / 2, y: (h - height) / 2 };
}

/** Which page the panel shows. It keeps the last page seen when the pointer leaves, and, pinned, ignores every other page. */
export class ViewerTarget {
  page = 0;
  pinned = false;
  /** a page is under the pointer or has the focus; false when a pin keeps the panel on another page */
  see(page: number): boolean {
    if (this.pinned && this.page && page !== this.page) return false;
    this.page = page;
    return true;
  }
  /** Pin to the page shown (nothing to pin before one is shown), or let go. Returns the new state. */
  pin(on = !this.pinned): boolean {
    this.pinned = on && this.page > 0;
    return this.pinned;
  }
  clear(): void { this.page = 0; this.pinned = false; }
  words(): string { return this.page ? (this.pinned ? `Pinned to page ${this.page}` : `Page ${this.page}`) : "No page"; }
}
