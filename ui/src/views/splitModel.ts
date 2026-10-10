/** The PDF splitter's records and pure helpers (docs/pdf-splitter.md, sections 2 and 5): the shapes the server answers in, the
 * segments a set of starts makes (the same reading as `SplitSession.segments`), and the bulk acts a person can preview.
 * Nothing here touches the DOM, the network, or React. */

export type Size = "tiny" | "small" | "large";
export const SIZE_PX: Record<Size, number> = { tiny: 96, small: 200, large: 800 };

export interface PageFact {
  n: number; width: number; height: number; rotation: number;
  blank: "content" | "blank" | "marked" | string;
  has_text: boolean; words: number; chars?: number; dpi?: number; colour?: string; codec?: string;
  header?: string; footer?: string; label: [number, number] | null; title?: string; date?: string; lang?: string; lqip?: string; pending?: boolean;
}
export interface Start { page: number; level: number; by?: string; at?: string; source?: string; suggestion?: string }
export interface SignalRow { signal: string; weight: number; said: string }
export type Band = "High" | "Medium" | "Low";
export interface Suggestion {
  id: string; page: number; level: number; confidence: number; band: Band | string; tier: string; signals: SignalRow[]; why: string;
  reader: string; state: "open" | "accepted" | "rejected" | "edited" | string;
}
export interface SegmentRow {
  key: string; path: string; start: number; end: number; pages: number; level: number; parent: string; source: string;
  labels: Record<string, string>;
}
export interface SessionView {
  id: string; status: "draft" | "confirmed" | "applied" | "stale" | "declined" | string; version: number; created: string; updated: string; by: string;
  source: { sha256: string; size: number; pages: number; kind: string; ref: string; confidential: boolean };
  counts: { pages: number; segments: number; nested: number; boundaries: number; suggestionsOpen: number; undo: number; redo: number };
  boundaries: Start[]; segments: SegmentRow[]; suggestions: Suggestion[];
  confirmed: Record<string, string>; applied: Record<string, unknown>; suggestedAt: string; notes: string[];
}
export interface SessionAnswer extends SessionView {
  renderer?: string; sizes?: string[]; confidential?: boolean; facts?: PageFact[]; review?: Review;
  limits?: { maxPages: number; suggestEnabled: boolean; draftDays: number; maxParts: number }; caveats?: string[];
}
export interface ListedSession {
  id: string; status: string; pages: number; segments: number; suggestionsOpen: number; updated: string; by: string; confidential: boolean; kind: string; label: string;
}
export interface ReviewPart {
  segment: string; level: number; start: number; end: number; ordinal: number; slot: string; title: string; kind: string | null; pages: [number, number][];
  count: number; name: string; action: string; why?: string; of?: string; sha256?: string; size?: number;
}
export interface Review {
  id: string; status: string; version: number; sourcePages: number; files: number; parts: ReviewPart[]; dropped: number[]; pagesInFiles: number;
  totalsOk: boolean; problems: string[]; collisions: string[]; duplicates: string[]; held: string[]; result: string; caveats?: string[];
}
export interface ApplyAnswer {
  dryRun?: boolean; ok?: boolean; note?: string; would?: { act: string; id: string; by: string; files: number }; review?: Review;
  filled?: unknown[]; held?: { segment: string; ordinal?: number }[]; skipped?: { segment: string; action: string; why?: string; of?: string }[];
  failed?: { segment: string; why: string }[]; dropped?: number[]; autoRead?: boolean;
}
export interface ActAnswer {
  ok?: boolean; act: string; version?: number; changed?: boolean; session?: SessionView; accepted?: number; rejected?: number; added?: number;
  cleared?: number; undone?: boolean; redone?: boolean; review?: Review; dryRun?: boolean; suggestions?: number; count?: number;
}

// ---------------------------------------------------------------------------------------------------------------- routes

export const SPLIT_BASE = "setup/split";
export const DEMO_ID = "demo";

/** `setup/split` is the list and the entry points; `setup/split/<id>` is one draft (an id is 8 hex digits; `demo` is the made-up
 * 120-page draft that needs no server). A file's name is never in a route. */
export function parseSplitRoute(hash: string): { id: string; query: URLSearchParams } {
  const [path, q = ""] = hash.split("?");
  const rest = path.replace(/^\/+/, "").split("/").slice(2).join("/");
  return { id: decodeURIComponent(rest), query: new URLSearchParams(q) };
}
export const splitRoute = (id = "") => `#/${SPLIT_BASE}${id ? `/${encodeURIComponent(id)}` : ""}`;

// ---------------------------------------------------------------------------------------------------------------- segments

export interface Seg { key: string; start: number; end: number; level: number; no: number }

/** The segments a set of starts makes: page 1 is always a start at level 0; a segment ends the page before the next start at its own
 * or a shallower level, and a parent's range still holds its children's pages (as the server reads them). `no` numbers the top-level
 * documents 1, 2, 3 and is 0 for a nested one. */
export function segmentsOf(starts: ReadonlyMap<number, number>, pages: number): Seg[] {
  const rows = [...starts.entries()].filter(([p]) => p !== 1 && p >= 1 && p <= pages).sort((a, b) => a[0] - b[0]);
  rows.unshift([1, 0]);
  const out: Seg[] = [];
  let top = 0;
  const stack: Seg[] = [];
  const kids = new Map<string, number>();
  for (let i = 0; i < rows.length; i++) {
    const [page, level] = rows[i];
    let end = pages;
    for (let j = i + 1; j < rows.length; j++) if (rows[j][1] <= level) { end = rows[j][0] - 1; break; }
    while (stack.length && stack[stack.length - 1].level >= level) stack.pop();
    let key: string;
    if (level === 0) { top += 1; key = `s${top}`; }
    else {
      const parent = stack.length ? stack[stack.length - 1].key : "s0";
      kids.set(parent, (kids.get(parent) ?? 0) + 1);
      key = `${parent}.${kids.get(parent)}`;
    }
    const seg: Seg = { key, start: page, end: Math.max(page, end), level, no: level === 0 ? top : 0 };
    out.push(seg);
    stack.push(seg);
  }
  return out;
}

/** For each page (1-based index), the number of the top-level document it falls in. One pass; used for the bands and the status line. */
export function documentNumbers(starts: ReadonlyMap<number, number>, pages: number): Uint16Array {
  const out = new Uint16Array(pages + 1);
  let no = 1;
  for (let p = 1; p <= pages; p++) {
    if (p > 1 && starts.get(p) === 0) no += 1;
    out[p] = no;
  }
  return out;
}

export function startsOf(boundaries: readonly Start[]): Map<number, number> {
  const m = new Map<number, number>();
  for (const b of boundaries) m.set(b.page, b.level);
  m.set(1, 0);
  return m;
}

export const sameStarts = (a: ReadonlyMap<number, number>, b: ReadonlyMap<number, number>): boolean => {
  if (a.size !== b.size) return false;
  for (const [k, v] of a) if (b.get(k) !== v) return false;
  return true;
};

/** The sorted pages that start a document or a suggestion, for `n` and `p` to walk. */
export function marksIn(starts: ReadonlyMap<number, number>, suggestions: readonly Suggestion[]): number[] {
  const set = new Set<number>(starts.keys());
  for (const s of suggestions) if (s.state === "open") set.add(s.page);
  return [...set].sort((a, b) => a - b);
}

export function nextMark(marks: readonly number[], from: number, dir: 1 | -1): number | null {
  if (dir === 1) return marks.find((m) => m > from) ?? null;
  for (let i = marks.length - 1; i >= 0; i--) if (marks[i] < from) return marks[i];
  return null;
}

/** The union of two sets of starts (the "merge boundaries" choice of a conflict): a page in both keeps the shallower level. */
export function unionStarts(a: ReadonlyMap<number, number>, b: ReadonlyMap<number, number>): Map<number, number> {
  const out = new Map(a);
  for (const [p, l] of b) out.set(p, out.has(p) ? Math.min(out.get(p)!, l) : l);
  return out;
}

// ---------------------------------------------------------------------------------------------------------------- bulk acts

/** The pages `every Nth` would add across `first..last`: every Nth page from `first`, not already a start and never page 1. */
export function everyNth(first: number, last: number, every: number, starts: ReadonlyMap<number, number>): number[] {
  if (every < 1 || first > last) return [];
  const out: number[] = [];
  for (let p = first; p <= last; p += every) if (p !== 1 && !starts.has(p)) out.push(p);
  return out;
}

export type BlankKeep = "before" | "after" | "drop";
export interface BlankPlan { marks: number[]; drop: number[]; blanks: number; share: number; duplexLooking: boolean }

/** Split on blank pages: each run of blank pages followed by a content page. `before` marks the page after the run (the blanks stay with the
 * document before); `after` marks the run's first page (they stay with the document after); `drop` marks the page after the run and lists the
 * blanks to leave out. Where over a quarter of the pages are blank they look like the backs of pages, and the plan says so. */
export function splitOnBlanks(facts: (PageFact | undefined)[], pages: number, keep: BlankKeep): BlankPlan {
  const marks: number[] = [];
  const drop: number[] = [];
  let blanks = 0;
  for (let p = 1; p <= pages; p++) if (facts[p]?.blank === "blank") blanks += 1;
  let p = 1;
  while (p <= pages) {
    if (facts[p]?.blank === "blank") {
      let q = p;
      while (q + 1 <= pages && facts[q + 1]?.blank === "blank") q += 1;
      if (q < pages) {
        if (keep === "after") { if (p > 1) marks.push(p); }
        else marks.push(q + 1);
        if (keep === "drop") for (let k = p; k <= q; k++) drop.push(k);
      } else if (keep === "drop") for (let k = p; k <= q; k++) drop.push(k);
      p = q + 1;
    } else p += 1;
  }
  const share = pages ? blanks / pages : 0;
  return { marks: [...new Set(marks)].filter((m) => m > 1), drop, blanks, share, duplexLooking: share > 0.25 };
}

/** Split at page-number restarts: a page whose printed number is 1 ("1 of 7") starts a document. */
export function splitAtRestarts(facts: (PageFact | undefined)[], pages: number): number[] {
  const out: number[] = [];
  for (let p = 2; p <= pages; p++) if (facts[p]?.label && facts[p]!.label![0] === 1) out.push(p);
  return out;
}

/** The ids of open suggestions at or above a confidence that a bulk accept would take (never a model-only one). */
export function acceptable(suggestions: readonly Suggestion[], minimum: number): Suggestion[] {
  return suggestions.filter((s) => s.state === "open" && s.confidence >= minimum && s.reader !== "model");
}

// ---------------------------------------------------------------------------------------------------------------- words

export const BAND_GLYPH: Record<string, string> = { High: "●●●", Medium: "●●○", Low: "●○○" };

export function stateWord(f: PageFact | undefined): string {
  if (!f || f.pending) return "not measured yet";
  const parts: string[] = [];
  if (f.blank === "blank") parts.push("blank");
  else if (f.blank === "marked") parts.push("marked");
  if (!f.has_text && f.blank !== "blank") parts.push("no text layer");
  return parts.join(", ") || "content";
}

/** The alt text of a page picture, from its facts and never from the image (a confidential file's is the page number alone). */
export function pageAlt(n: number, f: PageFact | undefined, confidential: boolean): string {
  if (confidential) return `Page ${n}`;
  const bits = [`Page ${n}`, stateWord(f)];
  if (f?.title) bits.push(`first line: ${f.title}`);
  return bits.join("; ");
}

/** The words for a page's cell: its number, what it is, and whether it starts a segment. */
export function cellLabel(n: number, f: PageFact | undefined, level: number, no: number, sug: Suggestion | undefined, confidential: boolean): string {
  const bits = [pageAlt(n, f, confidential)];
  if (n === 1) bits.push(`Starts segment 1. The first page always starts a segment`);
  else if (level >= 0) bits.push(level > 0 ? `Starts a nested segment inside segment ${no}. Press Enter to remove the start` : `Starts segment ${no}. Press Enter to remove the start`);
  else if (sug && sug.state === "open") bits.push(`Suggested start, ${String(sug.band).toLowerCase()} confidence. Press A to accept, X to reject, Enter to mark it yourself`);
  else bits.push(`Segment ${no}. Press Enter to make this page start a segment`);
  return bits.join(". ");
}

export function sizeText(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  if (bytes >= 1e3) return `${Math.round(bytes / 1e3)} KB`;
  return `${bytes} bytes`;
}

/** A page range in words: "pages 15-22 (8)" or "page 9". */
export function rangeWords(start: number, end: number): string {
  return start === end ? `page ${start}` : `pages ${start}-${end} (${end - start + 1})`;
}

// ---------------------------------------------------------------------------------------------------------------- LQIP

const lqipCache = new Map<string, string>();

/** A 16 by 16 greyscale picture (256 bytes as hex) as an 8-bit BMP data URL: a placeholder with no canvas and no request. "" when the
 * hex is not 512 digits. Cached by the hex. */
export function lqipUrl(hex: string | undefined): string {
  if (!hex || hex.length !== 512) return "";
  const hit = lqipCache.get(hex);
  if (hit) return hit;
  const W = 16, rowBytes = 16, pixelOffset = 14 + 40 + 256 * 4, size = pixelOffset + rowBytes * W;
  const b = new Uint8Array(size);
  const dv = new DataView(b.buffer);
  b[0] = 0x42; b[1] = 0x4d;
  dv.setUint32(2, size, true); dv.setUint32(10, pixelOffset, true);
  dv.setUint32(14, 40, true); dv.setInt32(18, W, true); dv.setInt32(22, W, true); dv.setUint16(26, 1, true); dv.setUint16(28, 8, true);
  dv.setUint32(46, 256, true);
  for (let i = 0; i < 256; i++) { const o = 54 + i * 4; b[o] = b[o + 1] = b[o + 2] = i; }
  for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) b[pixelOffset + (W - 1 - y) * rowBytes + x] = parseInt(hex.slice((y * W + x) * 2, (y * W + x) * 2 + 2), 16) || 0;
  let bin = "";
  for (let i = 0; i < b.length; i++) bin += String.fromCharCode(b[i]);
  const url = `data:image/bmp;base64,${btoa(bin)}`;
  if (lqipCache.size > 4000) lqipCache.clear();
  lqipCache.set(hex, url);
  return url;
}
