/** The windowing math of the page grid (docs/pdf-splitter.md, section 3.4): fixed-size cells, so the scroll length is computed with no
 * measuring, and only the tracks (rows when it scrolls down, columns when it scrolls across) in view plus a buffer exist as elements.
 * Pure functions; the tests run them on a synthetic 3,000-page file. */

export type Axis = "y" | "x";

export interface Layout {
  axis: Axis;
  /** cells across the scroll direction: columns of a downward grid, 1 for a row that scrolls across */
  perTrack: number;
  /** the size of a track along the scroll direction, gap included */
  track: number;
  tracks: number;
  /** the scroll length */
  total: number;
  cellW: number;
  cellH: number;
  gap: number;
}

export interface LayoutIn { axis?: Axis; count: number; width: number; cellW: number; cellH: number; gap?: number }

/** The layout of `count` cells in a view `width` px wide (the cross size for "x" is the cell height, so `perTrack` is 1). */
export function layoutOf({ axis = "y", count, width, cellW, cellH, gap = 8 }: LayoutIn): Layout {
  if (axis === "x") {
    const track = cellW + gap;
    return { axis, perTrack: 1, track, tracks: count, total: count * track, cellW, cellH, gap };
  }
  const perTrack = Math.max(1, Math.floor((Math.max(width, cellW) + gap) / (cellW + gap)));
  const tracks = Math.ceil(count / perTrack);
  const track = cellH + gap;
  return { axis, perTrack, track, tracks, total: tracks * track, cellW, cellH, gap };
}

export interface Win { first: number; last: number }

/** The tracks to build: those in view, plus `buffer` viewports above and below (the design's "two screens"). `last` is inclusive;
 * an empty list is `{first: 0, last: -1}`. */
export function visibleTracks(l: Layout, scroll: number, viewport: number, buffer = 2): Win {
  if (l.tracks === 0) return { first: 0, last: -1 };
  const pad = Math.max(0, buffer) * viewport;
  const first = Math.max(0, Math.floor((scroll - pad) / l.track));
  const last = Math.min(l.tracks - 1, Math.ceil((scroll + viewport + pad) / l.track) - 1);
  return { first, last: Math.max(first, last) };
}

/** The 1-based pages in a window of tracks. */
export function pagesIn(l: Layout, w: Win, count: number): { first: number; last: number } {
  if (w.last < w.first) return { first: 1, last: 0 };
  return { first: w.first * l.perTrack + 1, last: Math.min(count, (w.last + 1) * l.perTrack) };
}

/** How many cells exist for a window: what `visibleTracks` costs, never what the file holds. */
export function liveCells(l: Layout, w: Win, count: number): number {
  const p = pagesIn(l, w, count);
  return Math.max(0, p.last - p.first + 1);
}

/** The scroll offset that puts a page's track in view, moving as little as it can (`start` aligns it to the top instead). */
export function scrollFor(l: Layout, page: number, scroll: number, viewport: number, start = false): number {
  const t = Math.floor((page - 1) / l.perTrack);
  const top = t * l.track, bottom = top + l.track;
  if (start) return Math.max(0, Math.min(top, Math.max(0, l.total - viewport)));
  if (top < scroll) return top;
  if (bottom > scroll + viewport) return Math.max(0, bottom - viewport);
  return scroll;
}

/** The page at the middle of the viewport: what the loader measures distance from. */
export function centerPage(l: Layout, scroll: number, viewport: number, count: number): number {
  const t = Math.min(l.tracks - 1, Math.max(0, Math.floor((scroll + viewport / 2) / l.track)));
  return Math.min(count, Math.max(1, t * l.perTrack + Math.ceil(l.perTrack / 2)));
}

// ---------------------------------------------------------------------------------------------------------------- scroll speed

export interface Motion { at: number; offset: number; dir: -1 | 0 | 1; speed: number }

/** Direction and speed from two scroll samples (px per second). Used on animation frames; a flick or a scrollbar drag is fast. */
export function motionOf(prev: { at: number; offset: number } | null, at: number, offset: number): Motion {
  if (!prev || at <= prev.at) return { at, offset, dir: 0, speed: 0 };
  const d = offset - prev.offset;
  return { at, offset, dir: d > 0 ? 1 : d < 0 ? -1 : 0, speed: Math.abs(d) / ((at - prev.at) / 1000) };
}

/** Above this the loader asks for nothing but the smallest pictures, for the cells under the viewport. */
export const FAST_PX_PER_S = 2500;
/** After this long without a scroll the pictures that were held back are asked for. */
export const SETTLE_MS = 120;

// ---------------------------------------------------------------------------------------------------------------- image budget

export interface Budget { tiny: number; small: number; large: number }

/** Decoded pictures held at once (about 12 MB of pixels at the design's sizes); halved on a small or low-memory device. */
export function budgetFor(env: { width: number; deviceMemory?: number } = { width: typeof window === "undefined" ? 1024 : window.innerWidth }): Budget {
  const small = env.width < 480 || (env.deviceMemory !== undefined && env.deviceMemory <= 2);
  return small ? { tiny: 75, small: 30, large: 2 } : { tiny: 150, small: 60, large: 3 };
}

/** A request's urgency: smaller is sooner. Pages ahead of the way the person is scrolling beat pages behind at the same distance. */
export function priorityOf(page: number, center: number, dir: -1 | 0 | 1, size: "tiny" | "small" | "large"): number {
  const d = page - center;
  const ahead = dir === 0 || Math.sign(d) === dir || d === 0;
  const klass = size === "tiny" ? 0 : size === "small" ? 0.5 : 0.25;
  return Math.abs(d) * (ahead ? 1 : 1.6) + klass;
}
