import { afterEach, describe, expect, it, vi } from "vitest";
import { demoFacts, demoSuggestions } from "./splitDemo";
import { documentNumbers, everyNth, lqipUrl, marksIn, nextMark, segmentsOf, splitAtRestarts, splitOnBlanks, startsOf, unionStarts } from "./splitModel";
import { LoadError, ThumbLoader } from "./splitThumbs";
import {
  FAST_PX_PER_S, bandedCenterPage, bandedLayout, bandedPagesIn, bandedRowStep, bandedScrollFor, bandedScrollForDoc, budgetFor, centerPage, docOfPage, layoutOf, liveCells,
  motionOf, pagesIn, priorityOf, rowAt, rowInfo, rowOfPage, scrollFor, visibleRows, visibleTracks, type BandDoc,
} from "./splitWindow";

afterEach(() => vi.useRealTimers());

describe("the windowing math, on a synthetic 3,000-page file", () => {
  const l = layoutOf({ count: 3000, width: 1000, cellW: 124, cellH: 184 });

  it("computes the scroll length with no measuring: tracks of a fixed height", () => {
    expect(l.perTrack).toBe(7);                       // (1000 + 8) / (124 + 8)
    expect(l.tracks).toBe(Math.ceil(3000 / 7));
    expect(l.total).toBe(l.tracks * (184 + 8));
  });

  it("builds the viewport and two screens either side, and never more, wherever the scroll is", () => {
    const viewport = 600;
    for (const scroll of [0, 1234, 40000, l.total - viewport, l.total]) {
      const w = visibleTracks(l, scroll, viewport, 2);
      const live = liveCells(l, w, 3000);
      expect(live).toBeGreaterThan(0);
      expect(live).toBeLessThanOrEqual(7 * (Math.ceil((viewport * 5) / 192) + 1));   // five screens of rows at most
      expect(live).toBeLessThan(120);                // against 3,000 pages
    }
  });

  it("covers the whole file as the scroll goes from top to end, with no gap between windows", () => {
    const seen = new Set<number>();
    for (let s = 0; s <= l.total; s += 300) {
      const p = pagesIn(l, visibleTracks(l, s, 600, 0), 3000);
      for (let n = p.first; n <= p.last; n++) seen.add(n);
    }
    expect(seen.size).toBe(3000);
  });

  it("keeps a page in view by moving as little as it can, or aligns it to the top", () => {
    expect(scrollFor(l, 1, 0, 600)).toBe(0);
    expect(scrollFor(l, 3000, 0, 600)).toBe(l.total - 600);
    const t = Math.floor(99 / 7) * 192;
    expect(scrollFor(l, 100, t - 50, 600)).toBe(t - 50);               // already in view: unchanged
    expect(scrollFor(l, 100, 0, 600, true)).toBe(t);
  });

  it("names the page at the middle of the view", () => {
    expect(centerPage(l, 0, 600, 3000)).toBeGreaterThanOrEqual(1);
    expect(centerPage(l, l.total, 600, 3000)).toBeLessThanOrEqual(3000);
  });

  it("lays a row that scrolls across as one cell per track", () => {
    const x = layoutOf({ axis: "x", count: 3000, width: 800, cellW: 64, cellH: 104 });
    expect(x.perTrack).toBe(1);
    expect(x.total).toBe(3000 * 72);
    expect(liveCells(x, visibleTracks(x, 5000, 800, 2), 3000)).toBeLessThan(80);
  });

  it("handles an empty file", () => {
    const e = layoutOf({ count: 0, width: 800, cellW: 100, cellH: 100 });
    expect(visibleTracks(e, 0, 600)).toEqual({ first: 0, last: -1 });
    expect(liveCells(e, visibleTracks(e, 0, 600), 0)).toBe(0);
  });
});

describe("the album's bands, on 3,000 pages in uneven documents", () => {
  const l = layoutOf({ count: 3000, width: 1000, cellW: 124, cellH: 184 });       // 7 across, 192 per row
  const BAND = 30;                                                                // plus the 8 px gap
  // 300 documents of 1 to 19 pages, covering 1..3000 exactly
  const docs: BandDoc[] = [];
  for (let p = 1, i = 0; p <= 3000; i++) {
    const n = Math.min(3001 - p, 1 + ((i * 7) % 19));
    docs.push({ no: i + 1, start: p, end: p + n - 1, label: i % 3 ? undefined : `Title ${i + 1}` });
    p += n;
  }
  const b = bandedLayout(l, docs, BAND);

  it("puts a band at the head of every document and starts the document's pages on a new row", () => {
    expect(b.docs).toHaveLength(docs.length);
    let rows = 0;
    docs.forEach((d, i) => {
      expect(b.docRow[i]).toBe(rows);
      const info = rowInfo(b, rows);
      expect(info.kind).toBe("band");
      expect(info.doc).toBe(i);
      const first = rowInfo(b, rows + 1);
      expect(first.kind).toBe("cells");
      expect(first.first).toBe(d.start);                     // never shares a row with the document before
      rows += 1 + Math.ceil((d.end - d.start + 1) / 7);
    });
    expect(b.rows).toBe(rows);
  });

  it("sums the offsets: a band is shorter than a row of pages, and the total is the sum", () => {
    let y = 0;
    for (let r = 0; r < b.rows; r++) {
      expect(b.tops[r]).toBe(y);
      y += rowInfo(b, r).kind === "band" ? BAND + 8 : 192;
    }
    expect(b.total).toBe(y);
    expect(b.tops[b.rows]).toBe(y);
    expect(b.total).toBeGreaterThan(l.total);                // the bands and the part rows add height
  });

  it("finds the row at an offset, at row starts and one pixel before", () => {
    for (const r of [0, 1, 2, 57, 400, b.rows - 1]) {
      expect(rowAt(b, b.tops[r])).toBe(r);
      if (r > 0) expect(rowAt(b, b.tops[r] - 1)).toBe(r - 1);
    }
    expect(rowAt(b, -50)).toBe(0);
    expect(rowAt(b, b.total + 500)).toBe(b.rows - 1);
  });

  it("builds only the rows in view and two screens either side, wherever the scroll is", () => {
    const viewport = 600;
    for (const scroll of [0, 1234, 40000, b.total / 2, b.total - viewport]) {
      const w = visibleRows(b, scroll, viewport, 2);
      const span = bandedPagesIn(b, w, 3000);
      expect(w.last - w.first + 1).toBeLessThan(40);
      expect(span.last - span.first + 1).toBeLessThan(120);
      expect(w.first).toBeLessThanOrEqual(rowAt(b, scroll));
      expect(w.last).toBeGreaterThanOrEqual(rowAt(b, scroll + viewport));
    }
  });

  it("covers the whole file as the scroll goes from top to end, with no gap between windows", () => {
    const seen = new Set<number>();
    for (let s = 0; s <= b.total; s += 250) {
      const p = bandedPagesIn(b, visibleRows(b, s, 600, 0), 3000);
      for (let n = p.first; n <= p.last; n++) seen.add(n);
    }
    expect(seen.size).toBe(3000);
  });

  it("finds a page's row and document, and the row holds the page", () => {
    for (const page of [1, 2, 7, 8, 500, 1499, 2999, 3000]) {
      const r = rowOfPage(b, page);
      const info = rowInfo(b, r);
      expect(info.kind).toBe("cells");
      expect(page).toBeGreaterThanOrEqual(info.first);
      expect(page).toBeLessThanOrEqual(info.last);
      expect(docOfPage(b, page)).toBe(info.doc);
      expect(page).toBeGreaterThanOrEqual(docs[info.doc].start);
      expect(page).toBeLessThanOrEqual(docs[info.doc].end);
    }
  });

  it("scrolls to a page with the bands counted: in view stays put, otherwise the least move, or the top with `start`", () => {
    const viewport = 600;
    expect(bandedScrollFor(b, 1, 0, viewport)).toBe(0);
    const big = docs.findIndex((x, i) => i > 100 && x.end - x.start >= 14);       // a document of three rows or more
    const page = docs[big].start + 8;                                            // in its second row of pages
    const r = rowOfPage(b, page);
    expect(r - b.docRow[big]).toBe(2);
    const top = b.tops[r];
    expect(bandedScrollFor(b, page, top - 50, viewport)).toBe(top - 50);          // already in view
    expect(bandedScrollFor(b, page, 0, viewport)).toBe(b.tops[r + 1] - viewport); // from above: just enough
    expect(bandedScrollFor(b, page, b.total, viewport)).toBe(top);                // from below: its top
    expect(bandedScrollFor(b, page, 0, viewport, true)).toBe(top);
    // the first row of a document takes its band with it
    expect(bandedScrollFor(b, docs[big].start, b.total, viewport)).toBe(b.tops[b.docRow[big]]);
    expect(bandedScrollFor(b, 3000, 0, viewport, true)).toBeLessThanOrEqual(b.total - viewport);
    // a document's first page shows its band above it
    const first = docs[200].start;
    expect(bandedScrollFor(b, first, 0, viewport, true)).toBe(b.tops[b.docRow[200]]);
    // and wherever it lands, the page is in the window it builds
    for (const page of [1, 333, 1500, 2222, 3000]) {
      const at = bandedScrollFor(b, page, 0, viewport, true);
      const span = bandedPagesIn(b, visibleRows(b, at, viewport, 0), 3000);
      expect(span.first).toBeLessThanOrEqual(page);
      expect(span.last).toBeGreaterThanOrEqual(page);
    }
  });

  it("jumps to a segment: the top of its band, held inside the scroll length", () => {
    expect(bandedScrollForDoc(b, 0, 600)).toBe(0);
    expect(bandedScrollForDoc(b, 150, 600)).toBe(b.tops[b.docRow[150]]);
    expect(rowInfo(b, rowAt(b, bandedScrollForDoc(b, 150, 600))).kind).toBe("band");
    expect(bandedScrollForDoc(b, docs.length - 1, 5000)).toBe(b.total - 5000);
    expect(bandedScrollForDoc(b, 9999, 600)).toBeLessThanOrEqual(b.total - 600);       // past the end is the last
  });

  it("names the page at the middle of the view, never a band", () => {
    for (const at of [0, 777, 30000, b.total]) {
      const p = bandedCenterPage(b, at, 600, 3000);
      expect(p).toBeGreaterThanOrEqual(1);
      expect(p).toBeLessThanOrEqual(3000);
    }
    // a view centred on a band names the first page below it
    const bandTop = b.tops[b.docRow[100]];
    const under = bandedCenterPage(b, bandTop - 300 + 10, 600, 3000);
    expect(under).toBeGreaterThanOrEqual(docs[100].start);
    expect(under).toBeLessThanOrEqual(Math.min(docs[100].end, docs[100].start + 6));      // in the document's first row
  });

  it("steps a row down or up in the same column and skips the bands", () => {
    const d = docs.findIndex((x, i) => x.end - x.start >= 14 && docs[i + 1].end - docs[i + 1].start >= 3);   // three rows, then four pages
    const first = docs[d].start;
    expect(bandedRowStep(b, first + 2, 1, 3000)).toBe(first + 9);
    expect(bandedRowStep(b, first + 9, -1, 3000)).toBe(first + 2);
    // across a band: the last row of the document before, the same column or its last page
    const across = bandedRowStep(b, docs[d + 1].start + 3, -1, 3000);
    expect(across).toBeLessThanOrEqual(docs[d].end);
    expect(across).toBeGreaterThanOrEqual(docs[d].end - 6);
    expect(bandedRowStep(b, 1, -1, 3000)).toBe(1);                              // the top stays
    expect(bandedRowStep(b, 3000, 5, 3000)).toBe(3000);                         // the end stays
  });

  it("costs next to nothing in the worst case, 3,000 one-page documents: the build once, the window search per scroll event", () => {
    const worst: BandDoc[] = Array.from({ length: 3000 }, (_, i) => ({ no: i + 1, start: i + 1, end: i + 1 }));
    const t0 = performance.now();
    const w = bandedLayout(l, worst, BAND);
    const build = performance.now() - t0;
    expect(w.rows).toBe(6000);                                    // a band and a row each
    const t1 = performance.now();
    for (let i = 0; i < 10000; i++) bandedPagesIn(w, visibleRows(w, (i * 977) % w.total, 600, 2), 3000);
    const perScroll = (performance.now() - t1) / 10000;
    console.info(`bands, worst case: build ${build.toFixed(2)} ms; window + pages per scroll event ${(perScroll * 1000).toFixed(1)} us`);
    expect(build).toBeLessThan(100);
    expect(perScroll).toBeLessThan(1);                            // a frame is 16 ms
  });

  it("handles one document and a document of one page", () => {
    const one = bandedLayout(l, [{ no: 1, start: 1, end: 3000 }], BAND);
    expect(one.rows).toBe(1 + Math.ceil(3000 / 7));
    const tiny = bandedLayout(l, [{ no: 1, start: 1, end: 1 }, { no: 2, start: 2, end: 2 }], BAND);
    expect(tiny.rows).toBe(4);
    expect(rowInfo(tiny, 2).kind).toBe("band");
    expect(rowOfPage(tiny, 2)).toBe(3);
  });
});

describe("scroll speed, priority, and the image budget", () => {
  it("reads direction and speed from two samples", () => {
    expect(motionOf(null, 100, 0).speed).toBe(0);
    const m = motionOf({ at: 0, offset: 0 }, 100, 400);
    expect(m.dir).toBe(1);
    expect(m.speed).toBe(4000);
    expect(m.speed).toBeGreaterThan(FAST_PX_PER_S);
    expect(motionOf({ at: 0, offset: 500 }, 1000, 400).dir).toBe(-1);
  });

  it("asks nearest first, ahead of the scroll before behind, tiny before small", () => {
    expect(priorityOf(50, 50, 1, "tiny")).toBeLessThan(priorityOf(52, 50, 1, "tiny"));
    expect(priorityOf(55, 50, 1, "tiny")).toBeLessThan(priorityOf(45, 50, 1, "tiny"));    // ahead of the way down
    expect(priorityOf(45, 50, -1, "tiny")).toBeLessThan(priorityOf(55, 50, -1, "tiny"));  // ahead of the way up
    expect(priorityOf(50, 50, 0, "tiny")).toBeLessThan(priorityOf(50, 50, 0, "small"));
  });

  it("halves the budget on a phone or a device with 2 GB or less", () => {
    expect(budgetFor({ width: 1200 })).toEqual({ tiny: 150, small: 60, large: 3 });
    expect(budgetFor({ width: 390 })).toEqual({ tiny: 75, small: 30, large: 2 });
    expect(budgetFor({ width: 1200, deviceMemory: 2 }).small).toBe(30);
    expect(budgetFor({ width: 1200, deviceMemory: 8 }).small).toBe(60);
  });
});

// A loader whose pictures take a moment, so what is in flight can be seen.
function fixture(budget = { tiny: 150, small: 60, large: 3 }) {
  const calls: string[] = [];
  const pending = new Map<string, { resolve(u: string): void; reject(e: unknown): void; signal: AbortSignal }>();
  const fetcher = (url: string, signal: AbortSignal) => new Promise<string>((resolve, reject) => {
    calls.push(url);
    pending.set(url, { resolve, reject, signal });
    signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });
  const loader = new ThumbLoader({ urlOf: (p, s) => `/pic/${s}/${p}`, fetcher, budget, concurrency: 3 });
  const img = () => document.createElement("img");
  return { calls, pending, loader, img };
}
const flush = () => new Promise((r) => setTimeout(r, 0));

describe("the picture loader", () => {
  it("takes the page nearest the middle of the view first, and holds only a few requests at once", async () => {
    const f = fixture();
    f.loader.setView(50, 1);
    const els = [10, 49, 51, 90, 50].map((p) => ({ p, el: f.img() }));
    for (const { p, el } of els) f.loader.attach(el, p, ["tiny"]);
    expect(f.calls).toHaveLength(3);
    expect(f.calls[0]).toBe("/pic/tiny/10");           // the first attach started before the others were known
    f.pending.get("/pic/tiny/10")!.resolve("data:a");
    await flush();
    expect(f.calls[3]).toBe("/pic/tiny/50");           // then the nearest of what waits
  });

  it("sets the image source itself, tiny first and small after, with no render", async () => {
    const f = fixture();
    const el = f.img();
    f.loader.attach(el, 7, ["tiny", "small"]);
    f.pending.get("/pic/tiny/7")!.resolve("data:tiny");
    f.pending.get("/pic/small/7")!.resolve("data:small");
    await flush();
    expect(el.src).toBe("data:small");
    expect(el.dataset.size).toBe("small");
    expect(el.dataset.state).toBe("ready");
  });

  it("aborts a request when its cell leaves the window, and asks once for a page two cells want", async () => {
    const f = fixture();
    const a = f.img(), b = f.img();
    const detachA = f.loader.attach(a, 3, ["tiny"]);
    f.loader.attach(b, 3, ["tiny"]);
    expect(f.calls).toHaveLength(1);                               // one request for two cells
    detachA();
    expect(f.pending.get("/pic/tiny/3")!.signal.aborted).toBe(false);   // b still wants it
    const c = f.img();
    const detachC = f.loader.attach(c, 4, ["tiny"]);
    detachC();
    await flush();                                                 // dropped at the end of the commit, not at once
    expect(f.pending.get("/pic/tiny/4")!.signal.aborted).toBe(true);
    expect(f.loader.stats().aborted).toBe(1);
  });

  it("keeps a request in flight when its cell is replaced in the same commit (a row re-keyed by a mark above it)", async () => {
    const f = fixture();
    const old = f.img();
    const detach = f.loader.attach(old, 12, ["tiny", "small"]);
    expect(f.calls).toEqual(["/pic/tiny/12", "/pic/small/12"]);
    // React unmounts the old cell and mounts the new one in one commit: the cleanup runs first, then the new attach
    detach();
    const fresh = f.img();
    f.loader.attach(fresh, 12, ["tiny", "small"]);
    await flush();
    expect(f.calls).toEqual(["/pic/tiny/12", "/pic/small/12"]);    // asked once, not again
    expect(f.pending.get("/pic/tiny/12")!.signal.aborted).toBe(false);
    expect(f.loader.stats().aborted).toBe(0);
    f.pending.get("/pic/tiny/12")!.resolve("data:t");
    await flush();
    expect(fresh.src).toBe("data:t");
  });

  it("in a fast scroll asks for nothing but tiny pictures, and asks again for the rest when it settles", async () => {
    const f = fixture();
    const els = [1, 2, 3, 4, 5].map(() => f.img());
    els.forEach((el, i) => f.loader.attach(el, i + 1, ["tiny", "small"]));
    f.loader.setFast(true);
    const small = f.calls.filter((u) => u.startsWith("/pic/small/"));
    for (const u of small) expect(f.pending.get(u)!.signal.aborted).toBe(true);     // a small request in flight is dropped
    const before = f.calls.length;
    for (const [url, p] of [...f.pending]) if (url.startsWith("/pic/tiny/") && !p.signal.aborted) p.resolve("data:t");
    await flush();
    expect(f.calls.slice(before).some((u) => u.startsWith("/pic/small/"))).toBe(false);   // and none is asked for while fast
    f.loader.setFast(false);
    await flush();
    expect(f.calls.some((u) => u.startsWith("/pic/small/"))).toBe(true);
  });

  it("keeps no more decoded pictures than its budget, and never drops one that is on screen", async () => {
    const f = fixture({ tiny: 3, small: 2, large: 1 });
    const on = f.img();
    f.loader.attach(on, 1, ["tiny"]);
    f.pending.get("/pic/tiny/1")!.resolve("data:1");
    await flush();
    for (let p = 2; p <= 9; p++) {
      const el = f.img();
      const detach = f.loader.attach(el, p, ["tiny"]);
      f.pending.get(`/pic/tiny/${p}`)!.resolve(`data:${p}`);
      await flush();
      detach();
    }
    expect(f.loader.stats().cached.tiny).toBeLessThanOrEqual(3);
    expect(on.src).toBe("data:1");                                  // the one on screen was kept
  });

  it("says why a page could not be drawn, in the server's words, and tries again on request", async () => {
    const f = fixture();
    const el = f.img();
    const seen: string[] = [];
    f.loader.attach(el, 9, ["tiny"], { onState: (s, w) => seen.push(`${s}:${w ?? ""}`) });
    f.pending.get("/pic/tiny/9")!.reject(new LoadError(422, "This page could not be drawn"));
    await flush();
    expect(el.dataset.state).toBe("failed");
    expect(seen).toContain("failed:This page could not be drawn");
    f.loader.retry(9);
    expect(f.calls.filter((u) => u === "/pic/tiny/9")).toHaveLength(2);
  });
});

describe("segments and the bulk acts", () => {
  const starts = (rows: [number, number][]) => new Map<number, number>([[1, 0], ...rows]);

  it("makes segments from starts: page 1 always first, a segment ends the page before the next start", () => {
    const s = segmentsOf(starts([[5, 0], [9, 0]]), 12);
    expect(s.map((x) => [x.start, x.end, x.no])).toEqual([[1, 4, 1], [5, 8, 2], [9, 12, 3]]);
    expect(segmentsOf(new Map(), 3)).toEqual([{ key: "s1", start: 1, end: 3, level: 0, no: 1 }]);
  });

  it("keeps a nested start inside its parent's range", () => {
    const s = segmentsOf(starts([[4, 0], [6, 1], [9, 0]]), 12);
    expect(s.map((x) => [x.key, x.start, x.end, x.level])).toEqual([["s1", 1, 3, 0], ["s2", 4, 8, 0], ["s2.1", 6, 8, 1], ["s3", 9, 12, 0]]);
  });

  it("numbers each page's document in one pass", () => {
    const n = documentNumbers(starts([[3, 0], [4, 1], [6, 0]]), 7);
    expect([...n].slice(1)).toEqual([1, 1, 2, 2, 2, 3, 3]);          // a nested start does not start a numbered document
  });

  it("previews every Nth page: not page 1, not a page that already starts one", () => {
    expect(everyNth(1, 10, 3, starts([[4, 0]]))).toEqual([7, 10]);
    expect(everyNth(1, 10, 2, starts([]))).toEqual([3, 5, 7, 9]);
    expect(everyNth(5, 4, 2, starts([]))).toEqual([]);
  });

  it("splits on blank pages three ways, and says when the blanks look like the backs of pages", () => {
    const facts = demoFacts(120);
    const before = splitOnBlanks([undefined, ...facts], 120, "before");
    const blanks = facts.filter((f) => f.blank === "blank").length;
    expect(blanks).toBe(4);
    expect(before.blanks).toBe(blanks);
    expect(before.marks).toHaveLength(blanks);
    expect(before.marks.every((m) => facts[m - 2].blank === "blank")).toBe(true);          // the page after a blank run
    const after = splitOnBlanks([undefined, ...facts], 120, "after");
    expect(after.marks.every((m) => facts[m - 1].blank === "blank")).toBe(true);           // the first blank of a run
    const drop = splitOnBlanks([undefined, ...facts], 120, "drop");
    expect(drop.drop).toHaveLength(blanks);
    expect(before.duplexLooking).toBe(false);
    const duplex = splitOnBlanks([undefined, ...Array.from({ length: 8 }, (_, i) => ({ n: i + 1, blank: i % 2 ? "blank" : "content" }) as never)], 8, "before");
    expect(duplex.duplexLooking).toBe(true);
  });

  it("finds where the printed numbering restarts at 1", () => {
    const facts = demoFacts(120);
    const at = splitAtRestarts([undefined, ...facts], 120);
    expect(at.length).toBeGreaterThan(4);
    expect(at.every((p) => facts[p - 1].label?.[0] === 1)).toBe(true);
  });

  it("walks the starts and suggestions with n and p, and unions two copies for a merge", () => {
    const sug = demoSuggestions(demoFacts(120));
    const marks = marksIn(starts([[7, 0]]), sug);
    expect(marks[0]).toBe(1);
    expect(nextMark(marks, 1, 1)).toBe(marks[1]);
    expect(nextMark(marks, 1, -1)).toBeNull();
    expect(unionStarts(starts([[3, 1]]), starts([[3, 0], [8, 0]]))).toEqual(starts([[3, 0], [8, 0]]));
    expect(startsOf([{ page: 4, level: 0 }]).has(1)).toBe(true);
  });

  it("draws a placeholder from the 256-byte picture, with no canvas", () => {
    expect(lqipUrl("")).toBe("");
    expect(lqipUrl("ff".repeat(255))).toBe("");
    const url = lqipUrl("80".repeat(256));
    expect(url.startsWith("data:image/bmp;base64,")).toBe(true);
    expect(lqipUrl("80".repeat(256))).toBe(url);                       // cached
  });
});
