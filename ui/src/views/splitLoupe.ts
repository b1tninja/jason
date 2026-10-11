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
