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

// ---------------------------------------------------------------------------------------------------------------- bands

/** A document of the album: a header row, then its pages in rows that start at its first page (so a band never shares a row with
 * the page of another). Rows differ in height (a band is shorter than a row of pages), so the offsets are prefix sums, built once
 * per layout and searched in log time; nothing is measured. docs/pdf-splitter.md, section 5.3. */
export interface BandDoc { no: number; start: number; end: number; label?: string }

export interface Banded {
  layout: Layout;
  docs: readonly BandDoc[];
  /** a band's height, gap included */
  bandTrack: number;
  rows: number;
  /** tops[r] is the offset of row r; tops[rows] is the scroll length */
  tops: Float64Array;
  /** the row index of each document's band */
  docRow: Int32Array;
  total: number;
}

/** Bands over a downward layout. `docs` must be sorted and together cover pages 1..count. */
export function bandedLayout(l: Layout, docs: readonly BandDoc[], bandH: number): Banded {
  const bandTrack = bandH + l.gap;
  const per = Math.max(1, l.perTrack);
  let rows = 0;
  for (const d of docs) rows += 1 + Math.max(1, Math.ceil((d.end - d.start + 1) / per));
  const tops = new Float64Array(rows + 1);
  const docRow = new Int32Array(docs.length);
  let r = 0, y = 0;
  docs.forEach((d, i) => {
    docRow[i] = r;
    tops[r++] = y; y += bandTrack;
    const n = Math.max(1, Math.ceil((d.end - d.start + 1) / per));
    for (let k = 0; k < n; k++) { tops[r++] = y; y += l.track; }
  });
  tops[rows] = y;
  return { layout: l, docs, bandTrack, rows, tops, docRow, total: y };
}

/** The last index below n in a sorted array whose value is <= v (0 when none). */
function floorIndex(a: ArrayLike<number>, n: number, v: number): number {
  let lo = 0, hi = n - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (a[mid] <= v) lo = mid; else hi = mid - 1; }
  return Math.max(0, lo);
}

/** The row at a scroll offset. */
export function rowAt(b: Banded, y: number): number {
  return b.rows === 0 ? 0 : floorIndex(b.tops, b.rows, Math.max(0, y));
}

/** The rows to build: those in view plus `buffer` viewports either side (as `visibleTracks`). */
export function visibleRows(b: Banded, scroll: number, viewport: number, buffer = 2): Win {
  if (b.rows === 0) return { first: 0, last: -1 };
  const pad = Math.max(0, buffer) * viewport;
  const first = rowAt(b, scroll - pad);
  const last = rowAt(b, scroll + viewport + pad);
  return { first, last: Math.max(first, last) };
}

export interface RowInfo { kind: "band" | "cells"; doc: number; first: number; last: number; top: number; height: number }

/** What a row holds: a band (the document), or the pages `first..last`. */
export function rowInfo(b: Banded, r: number): RowInfo {
  const doc = floorIndex(b.docRow, b.docs.length, r);
  const d = b.docs[doc];
  const k = r - b.docRow[doc];
  const top = b.tops[r];
  if (k === 0) return { kind: "band", doc, first: d.start, last: d.start - 1, top, height: b.bandTrack - b.layout.gap };
  const first = d.start + (k - 1) * b.layout.perTrack;
  return { kind: "cells", doc, first, last: Math.min(d.end, first + b.layout.perTrack - 1), top, height: b.layout.cellH };
}

/** The document a page is in (its index in `docs`). */
export function docOfPage(b: Banded, page: number): number {
  let lo = 0, hi = b.docs.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (b.docs[mid].start <= page) lo = mid; else hi = mid - 1; }
  return lo;
}

/** The row that holds a page. */
export function rowOfPage(b: Banded, page: number): number {
  const d = docOfPage(b, page);
  return b.docRow[d] + 1 + Math.max(0, Math.floor((page - b.docs[d].start) / b.layout.perTrack));
}

/** The 1-based pages in a window of rows (a band holds none). */
export function bandedPagesIn(b: Banded, w: Win, count: number): { first: number; last: number } {
  if (w.last < w.first || b.rows === 0) return { first: 1, last: 0 };
  let r = w.first;
  while (r <= w.last && rowInfo(b, r).kind === "band") r++;
  let q = w.last;
  while (q >= r && rowInfo(b, q).kind === "band") q--;
  if (q < r) return { first: 1, last: 0 };
  return { first: rowInfo(b, r).first, last: Math.min(count, rowInfo(b, q).last) };
}

/** The scroll offset that puts a page in view, moving as little as it can. `start` aligns it to the top, and a page in the first row
 * of its document takes the band above it too, so the number it belongs to shows. */
export function bandedScrollFor(b: Banded, page: number, scroll: number, viewport: number, start = false): number {
  const r = rowOfPage(b, page);
  const d = docOfPage(b, page);
  const top = r - b.docRow[d] === 1 ? b.tops[b.docRow[d]] : b.tops[r];
  const bottom = b.tops[r + 1];
  if (start) return Math.max(0, Math.min(top, Math.max(0, b.total - viewport)));
  if (top < scroll) return top;
  if (bottom > scroll + viewport) return Math.max(0, bottom - viewport);
  return scroll;
}

/** The offset of a document's band: a jump to a segment. */
export function bandedScrollForDoc(b: Banded, doc: number, viewport: number): number {
  const i = Math.max(0, Math.min(b.docs.length - 1, doc));
  return Math.max(0, Math.min(b.tops[b.docRow[i]] ?? 0, Math.max(0, b.total - viewport)));
}

/** The page at the middle of the viewport. */
export function bandedCenterPage(b: Banded, scroll: number, viewport: number, count: number): number {
  if (b.rows === 0) return 1;
  let r = rowAt(b, scroll + viewport / 2);
  let info = rowInfo(b, r);
  if (info.kind === "band") { r = Math.min(b.rows - 1, r + 1); info = rowInfo(b, r); if (info.kind === "band") return Math.min(count, info.first); }
  return Math.min(count, Math.max(1, info.first + Math.ceil((info.last - info.first + 1) / 2) - 1));
}

/** The page `rows` rows below (or above) a page, in the same column, skipping the bands: what the arrow keys use. */
export function bandedRowStep(b: Banded, page: number, rows: number, count: number): number {
  const col = (page - b.docs[docOfPage(b, page)].start) % b.layout.perTrack;
  let r = rowOfPage(b, page);
  const dir = rows < 0 ? -1 : 1;
  for (let n = Math.abs(rows); n > 0; n--) {
    let next = r + dir;
    while (next >= 0 && next < b.rows && rowInfo(b, next).kind === "band") next += dir;
    if (next < 0 || next >= b.rows) break;
    r = next;
  }
  const info = rowInfo(b, r);
  if (info.kind === "band") return page;
  return Math.min(count, info.first + Math.min(col, info.last - info.first));
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
