import { afterEach, describe, expect, it, vi } from "vitest";
import { demoFacts, demoSuggestions } from "./splitDemo";
import { documentNumbers, everyNth, lqipUrl, marksIn, nextMark, segmentsOf, splitAtRestarts, splitOnBlanks, startsOf, unionStarts } from "./splitModel";
import { LoadError, ThumbLoader } from "./splitThumbs";
import {
  FAST_PX_PER_S, budgetFor, centerPage, layoutOf, liveCells, motionOf, pagesIn, priorityOf, scrollFor, visibleTracks,
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
    expect(f.pending.get("/pic/tiny/4")!.signal.aborted).toBe(true);
    expect(f.loader.stats().aborted).toBe(1);
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
