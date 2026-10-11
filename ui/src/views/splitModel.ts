/** The PDF splitter's records and pure helpers (docs/pdf-splitter.md, sections 2 and 5): the shapes the server answers in, the
 * segments a set of starts makes (the same reading as `SplitSession.segments`), and the bulk acts a person can preview.
 * Nothing here touches the DOM, the network, or React. */

import type { GlyphName } from "../components/Glyph";

/** The steps a page picture comes in (the longest side in pixels): the server's ladder (`split_thumbs.SIZES`), which the browser's own drawing follows. */
export type Size = "tiny" | "small" | "medium" | "large" | "huge";
export const SIZE_PX: Record<Size, number> = { tiny: 96, small: 200, medium: 400, large: 800, huge: 1600 };
export const SIZE_STEPS: Size[] = ["tiny", "small", "medium", "large", "huge"];

/** The picture a cell needs: the smallest step whose pixels cover the cell's longest displayed side in device pixels (CSS size x the
 * screen's pixel ratio), never above `cap`. A picture smaller than this is only upscaled, so it is never the final one when a sharper is possible. */
export function sizeFor(cssLongest: number, dpr = 1, cap: Size = "huge"): Size {
  const need = Math.ceil(Math.max(1, cssLongest) * Math.max(1, dpr));
  const top = SIZE_STEPS.indexOf(cap);
  for (let i = 0; i <= top; i++) if (SIZE_PX[SIZE_STEPS[i]] >= need) return SIZE_STEPS[i];
  return SIZE_STEPS[top];
}

/** The largest step `cells` pictures on screen at once may be drawn at without their decoded pixels (width x height x 4 bytes, a page
 * about 1.3 times as tall as wide) passing `megabytes`. Never below "small": the album is still readable. */
export function stepWithin(cells: number, megabytes: number): Size {
  let best: Size = "small";
  for (const s of SIZE_STEPS) if (s !== "tiny" && Math.max(1, cells) * SIZE_PX[s] * SIZE_PX[s] * 0.77 * 4 <= megabytes * 1e6) best = s;
  return best;
}

/** The sizes the compare pane's figures ask for: a quick small one, then the sharp one for the zoom (800 px for "800 px", the largest for
 * "enlarged", and for "fit" whatever covers the figure's width in device pixels). */
export function figureSizes(zoom: "fit" | "full" | "enlarged", cssWidth: number, dpr: number): Size[] {
  const sharp: Size = zoom === "enlarged" ? "huge" : zoom === "full" ? "large" : sizeFor(cssWidth * 1.294, dpr, "huge");
  return sharp === "small" || sharp === "tiny" ? ["small"] : ["small", sharp];
}

/** The sizes a cell asks for: a quick low-resolution picture first, then the sharp one, in place. */
export function sizesFor(cssLongest: number, dpr: number, cap: Size): Size[] {
  const sharp = sizeFor(cssLongest, dpr, cap);
  return sharp === "tiny" ? ["tiny"] : ["tiny", sharp];
}

export interface PageFact {
  n: number; width: number; height: number; rotation: number;
  blank: "content" | "blank" | "marked" | string;
  has_text: boolean; words: number; chars?: number; dpi?: number; colour?: string; codec?: string;
  header?: string; footer?: string; label: [number, number] | null; title?: string; date?: string; lang?: string; lqip?: string; pending?: boolean;
  /** Measured from the text layer (docs/pdf-splitter.md, 9.5): the degrees clockwise the text is turned from upright as displayed (0, 90, 180, 270;
   * -1 when there is no text layer or too few letters), whether that is sideways (90 or 270), the degrees clockwise that make it upright, and
   * portrait or landscape as displayed. A scan with no text layer is never called sideways: nothing was measured. */
  turn?: number; sideways?: boolean; fix?: number; orientation?: string;
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
  renderer?: string; sizes?: string[]; confidential?: boolean; facts?: PageFact[]; review?: Review; flags?: FlagsAnswer;
  limits?: { maxPages: number; suggestEnabled: boolean; draftDays: number; maxParts: number; clientRender?: boolean; clientRenderMaxPages?: number }; caveats?: string[];
}
export interface ListedSession {
  id: string; status: string; pages: number; segments: number; suggestionsOpen: number; updated: string; by: string; confidential: boolean; kind: string; label: string;
}
export interface ReviewPart {
  segment: string; level: number; start: number; end: number; ordinal: number; slot: string; title: string; kind: string | null; pages: [number, number][];
  count: number; name: string; action: string; why?: string; of?: string; sha256?: string; size?: number;
  /** how the part is to be filed: held, library, or slot (what the server settled on, from the request and the part's own choice) */
  filing?: string;
  /** the pages of this part that are turned in the new file, and the ones measured sideways and left as they are */
  rotated?: TurnedPage[]; sideways?: SidewaysPage[];
  /** the flags the server repeats in the review (only those that are set) */
  flags?: Partial<Pick<SegmentFlags, "blankOnly" | "nearDuplicateOf" | "repeatedBy" | "overPartLimit" | "mayHoldMore">>;
}
export interface TurnedPage { page: number; degrees: number }
export interface FilingCounts { asked: string; held: number; library: number; slots: number; collisions: number; duplicates: number }
export interface Review {
  id: string; status: string; version: number; sourcePages: number; files: number; parts: ReviewPart[]; dropped: number[]; pagesInFiles: number;
  totalsOk: boolean; problems: string[]; collisions: string[]; duplicates: string[]; held: string[]; result: string; caveats?: string[];
  library?: string[]; filing?: FilingCounts; rotated?: TurnedPage[]; sidewaysLeft?: number;
}
export interface LibraryResult { segment: string; action?: string; libraryId?: string; kind?: string; size?: number; ordinal?: number }
export interface ApplyAnswer {
  dryRun?: boolean; ok?: boolean; note?: string; would?: { act: string; id: string; by: string; files: number }; review?: Review;
  filled?: unknown[]; held?: { segment: string; ordinal?: number; why?: string }[]; skipped?: { segment: string; action: string; why?: string; of?: string }[];
  failed?: { segment: string; why: string }[]; dropped?: number[]; autoRead?: boolean;
  library?: LibraryResult[]; rotated?: TurnedPage[];
  /** only when the server says so (library filing's OCR is a job that may not exist yet): a count or the list of queued parts */
  ocrQueued?: number | unknown[];
}

// ---------------------------------------------------------------------------------------------------------------- flags (docs/pdf-splitter.md, 9.5)

export interface SidewaysPage { page: number; turn: number; fix: number }
export interface MayHoldMore { page: number; score: number }
/** The server's pre-review reading of one segment: from the draft and the page facts already measured. Readings, not decisions. */
export interface SegmentFlags {
  segment: string; level: number; start: number; end: number; pages: number; measured: number;
  blankOnly: boolean; sideways: SidewaysPage[];
  /** the file's size in proportion to the pages, against the limit a slot's upload is held to: an estimate */
  estimatedBytes: number; overPartLimit: boolean; partLimit: number;
  nearDuplicateOf: string | null; repeatedBy: string[]; mayHoldMore: MayHoldMore[];
  slot: string; slotFilled: boolean; flagged: boolean;
}
export interface FlagsAnswer {
  id: string; version: number; segments: SegmentFlags[];
  counts: { blankOnly: number; nearDuplicate: number; sideways: number; overPartLimit: number; mayHoldMore: number; slotFilled: number };
  measured: { pages: number; of: number; complete: boolean };
  parts: { count: number; limit: number; over: boolean };
  caveats: string[];
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
  if (f.sideways) parts.push("sideways");
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
export function cellLabel(n: number, f: PageFact | undefined, level: number, no: number, sug: Suggestion | undefined, confidential: boolean, turn?: Turn): string {
  const bits = [pageAlt(n, f, confidential)];
  if (f?.sideways) bits.push(`${sidewaysWords(f)}${f.orientation ? `, drawn ${f.orientation}` : ""}`);
  if (turn !== undefined) bits.push(`Will be turned in the new files: ${turnWord(turn, f?.fix).toLowerCase()}`);
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

// ---------------------------------------------------------------------------------------------------------------- turning pages

/** A person's choice for one page, applied in the new files only: a number of degrees clockwise, or `fix` (the degrees the page's measured text needs). */
export type Turn = "fix" | 90 | 180 | 270;
export type Turns = Readonly<Record<number, Turn>>;
export const TURN_DEGREES: readonly (90 | 180 | 270)[] = [90, 180, 270];

/** The `rotate` a review or an apply carries: `{ "61": 90, "66": "fix" }`, or undefined when no page is to be turned. */
export function turnBody(t: Turns): Record<string, Turn> | undefined {
  const keys = Object.keys(t);
  if (!keys.length) return undefined;
  return Object.fromEntries(keys.map((k) => [k, t[Number(k)]]));
}
export function isTurn(v: unknown): v is Turn { return v === "fix" || v === 90 || v === 180 || v === 270; }

export function turnWord(t: Turn, fix?: number): string {
  return t === "fix" ? `Fix sideways${fix ? ` (turn ${fix}°)` : ""}` : `Turn ${t}°`;
}

/** What a page's measured turn means, in words ("" when it was not measured sideways). */
export function sidewaysWords(f: PageFact | undefined): string {
  if (!f?.sideways) return "";
  return `Sideways: its text is turned ${f.turn}° clockwise${f.fix ? `; turning the page ${f.fix}° clockwise makes it upright` : ""}`;
}

/** The pages measured sideways in a set of facts that have been read (a scan with no text layer is never one). */
export function sidewaysIn(facts: readonly (PageFact | undefined)[]): SidewaysPage[] {
  const out: SidewaysPage[] = [];
  for (const f of facts) if (f?.sideways) out.push({ page: f.n, turn: f.turn ?? 0, fix: f.fix ?? 0 });
  return out;
}

/** Page numbers in a list, at most `max`, with "and N more". */
export function pagesList(pages: readonly number[], max = 8): string {
  const shown = pages.slice(0, max).join(", ");
  return pages.length > max ? `${shown}, and ${pages.length - max} more` : shown;
}

// ---------------------------------------------------------------------------------------------------------------- flag words

export type FlagKey = "blankOnly" | "nearDuplicate" | "repeated" | "sideways" | "overLimit" | "slotFilled" | "mayHoldMore";
/** One flag of a segment as words and a glyph (never colour alone): a short form for the rail, a full sentence for the dialog and the review. */
export interface FlagItem { key: FlagKey; glyph: GlyphName; short: string; long: string; pages?: number[] }

export const segWord = (key: string): string => { const m = /^s(\d+)$/.exec(key); return m ? `segment ${m[1]}` : `segment ${key}`; };

type FlagInput = Partial<Pick<SegmentFlags, "blankOnly" | "nearDuplicateOf" | "repeatedBy" | "overPartLimit" | "mayHoldMore" | "sideways" | "slotFilled" | "slot" | "estimatedBytes" | "partLimit">>;

/** The flags a segment carries, in a fixed order. `partSize` is a part's exact size where the review cut it, which replaces the estimate. */
export function flagItems(f: FlagInput, partSize?: number): FlagItem[] {
  const out: FlagItem[] = [];
  if (f.blankOnly) out.push({ key: "blankOnly", glyph: "file-minus", short: "Blank only", long: "Every page of this segment is blank: it may be a separator or a stray sheet. Nothing is removed unless you leave the pages out." });
  if (f.nearDuplicateOf) out.push({ key: "nearDuplicate", glyph: "copy", short: `Repeats ${segWord(f.nearDuplicateOf)}`, long: `Most of its pages repeat pages of ${segWord(f.nearDuplicateOf)} (compared by the pages' words, or by their pictures for a scan). It may be the same document scanned twice.` });
  if (f.repeatedBy?.length) out.push({ key: "repeated", glyph: "copy", short: `Repeated by ${f.repeatedBy.map(segWord).join(", ")}`, long: `Most of the pages of ${f.repeatedBy.map(segWord).join(" and ")} repeat pages of this segment.` });
  if (f.sideways?.length) {
    const pages = f.sideways.map((x) => x.page);
    out.push({ key: "sideways", glyph: "refresh-cw", short: `${f.sideways.length} sideways ${f.sideways.length === 1 ? "page" : "pages"}`, pages,
      long: `${f.sideways.length === 1 ? "Page" : "Pages"} ${pagesList(pages)} ${f.sideways.length === 1 ? "is" : "are"} sideways: the text runs up or down the page, measured from the text layer. They can be turned in the new files; the original is not changed.` });
  }
  if (f.overPartLimit) {
    const limit = f.partLimit ? ` against the limit of ${sizeText(f.partLimit)}` : "";
    const size = partSize ? sizeText(partSize) : f.estimatedBytes ? `about ${sizeText(f.estimatedBytes)} (an estimate from the file's size in proportion to its pages)` : "over the limit";
    out.push({ key: "overLimit", glyph: "triangle-alert", short: partSize ? "Over the size limit" : "May be over the size limit", long: `Cut into its own file it would be ${size}${limit}. A slot's upload is held to that limit; the review cuts each part and says exactly.` });
  }
  if (f.slotFilled) out.push({ key: "slotFilled", glyph: "lock", short: "Slot already filled", long: `Its slot${f.slot ? ` (${f.slot})` : ""} already holds a file. The review keeps this part in the store instead; nothing is replaced.` });
  if (f.mayHoldMore?.length) {
    const pages = f.mayHoldMore.map((m) => m.page);
    out.push({ key: "mayHoldMore", glyph: "split", short: "May hold more than one document", pages,
      long: `${pages.length === 1 ? "Page" : "Pages"} ${pagesList(pages)} inside it ${pages.length === 1 ? "looks" : "look"} like the start of another document, strongest first (the same reading that makes suggestions). Nothing is marked.` });
  }
  return out;
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
