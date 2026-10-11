import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DWELL_MS, LOUPE_MAX_PX, LoupeFeed, SERVER_MAX_PX, clampZoom, contentBox, fractionIn, lensBackground, lensSize, loupeBudget, magnifierOn, placeLens, sharpLoader,
  sharpPixels, stepZoom, zoomWords, type Sharp,
} from "./splitLoupe";

const view = { w: 1000, h: 700 };

describe("where the lens goes", () => {
  it("sits down and to the right of the pointer", () => {
    expect(placeLens({ x: 100, y: 100 }, 220, view, "pointer")).toMatchObject({ x: 118, y: 118, flipX: false, flipY: false });
  });
  it("flips to the left near the right edge and above near the bottom", () => {
    const p = placeLens({ x: 900, y: 650 }, 220, view, "pointer");
    expect(p.flipX).toBe(true); expect(p.flipY).toBe(true);
    expect(p.x).toBe(900 - 18 - 220); expect(p.y).toBe(650 - 18 - 220);
  });
  it("always stays whole inside the viewport", () => {
    for (const [x, y] of [[0, 0], [999, 0], [0, 699], [999, 699], [500, 350]]) {
      for (const mode of ["pointer", "touch"] as const) {
        const p = placeLens({ x, y }, 220, view, mode);
        expect(p.x).toBeGreaterThanOrEqual(6); expect(p.y).toBeGreaterThanOrEqual(6);
        expect(p.x + 220).toBeLessThanOrEqual(view.w - 6); expect(p.y + 220).toBeLessThanOrEqual(view.h - 6);
      }
    }
  });
  it("rides above a finger, so the finger never covers it, and goes below only when there is no room above", () => {
    const up = placeLens({ x: 500, y: 500 }, 220, view, "touch");
    expect(up.y + 220).toBeLessThan(500); expect(up.flipY).toBe(false);
    const low = placeLens({ x: 500, y: 100 }, 220, view, "touch");
    expect(low.flipY).toBe(true); expect(low.y).toBeGreaterThan(100);
  });
  it("stands beside the focused page: right, else left, else below", () => {
    const right = placeLens({ left: 100, top: 100, width: 120, height: 160 }, 220, view, "beside");
    expect(right.x).toBeGreaterThan(220);
    const left = placeLens({ left: 800, top: 100, width: 120, height: 160 }, 220, view, "beside");
    expect(left.flipX).toBe(true); expect(left.x + 220).toBeLessThanOrEqual(800);
    const narrow = placeLens({ left: 100, top: 100, width: 200, height: 160 }, 220, { w: 340, h: 700 }, "beside");
    expect(narrow.y).toBeGreaterThanOrEqual(260);
  });
  it("is no bigger than the window leaves room for", () => {
    expect(lensSize({ w: 1000, h: 700 })).toBe(220);
    expect(lensSize({ w: 200, h: 700 })).toBe(188);
    expect(lensSize({ w: 50, h: 50 })).toBe(96);
  });
});

describe("the picture inside the lens", () => {
  it("finds the page inside a box that letterboxes it", () => {
    const b = contentBox({ left: 0, top: 0, width: 200, height: 100 }, { w: 100, h: 100 });
    expect(b).toEqual({ left: 50, top: 0, width: 100, height: 100 });
    expect(contentBox({ left: 5, top: 5, width: 10, height: 10 }, null)).toEqual({ left: 5, top: 5, width: 10, height: 10 });
  });
  it("reads the pointer as fractions of the page, held to the page", () => {
    const page = { left: 100, top: 100, width: 100, height: 200 };
    expect(fractionIn({ x: 150, y: 200 }, page)).toEqual({ x: 0.5, y: 0.5 });
    expect(fractionIn({ x: 0, y: 900 }, page)).toEqual({ x: 0, y: 1 });
  });
  it("draws the page zoom times as wide with the spot at the lens's centre", () => {
    const page = { left: 0, top: 0, width: 124, height: 160 };
    const bg = lensBackground({ x: 0.5, y: 0.5 }, page, 3, 220);
    expect(bg.width).toBe(372); expect(bg.height).toBe(480);
    expect(bg.x).toBeCloseTo(110 - 186); expect(bg.y).toBeCloseTo(110 - 240);
    const corner = lensBackground({ x: 0, y: 0 }, page, 3, 220);
    expect(corner.x).toBe(110); expect(corner.y).toBe(110);
  });
  it("asks for the pixels the lens will show, never fewer than the server's largest, never more than the source can give", () => {
    expect(sharpPixels(160, 3, 1, LOUPE_MAX_PX)).toBe(SERVER_MAX_PX);
    expect(sharpPixels(700, 4, 2, LOUPE_MAX_PX)).toBe(LOUPE_MAX_PX);
    expect(sharpPixels(700, 4, 2, SERVER_MAX_PX)).toBe(SERVER_MAX_PX);
    expect(sharpPixels(500, 3, 1.5, LOUPE_MAX_PX)).toBe(2250);
  });
});

describe("the zoom", () => {
  it("is held to 2 through 6 in half steps", () => {
    expect(clampZoom(1)).toBe(2); expect(clampZoom(9)).toBe(6); expect(clampZoom(3.2)).toBe(3); expect(clampZoom(3.3)).toBe(3.5);
    expect(clampZoom(NaN)).toBe(3);
    expect(stepZoom(6, 1)).toBe(6); expect(stepZoom(2, -1)).toBe(2); expect(stepZoom(3, 1)).toBe(3.5); expect(stepZoom(3, -1)).toBe(2.5);
  });
  it("is said in words", () => { expect(zoomWords(3)).toBe("3 times"); expect(zoomWords(2.5)).toBe("2.5 times"); });
});

describe("whether the magnifier is on", () => {
  it("follows the device until a person chooses", () => {
    expect(magnifierOn(null, true)).toBe(true);
    expect(magnifierOn(undefined, false)).toBe(false);
    expect(magnifierOn(false, true)).toBe(false);
    expect(magnifierOn(true, false)).toBe(true);
  });
});

// ---- the feed, with a fake loader and fake timers

let n = 0;
const pic = (px = 1600, best = true, w = 800, h = 1000): Sharp => ({ url: `blob:${++n}`, width: w, height: h, px, best });

function rig(budget = { count: 3, bytes: 1e9 }) {
  const calls: { page: number; px: number; signal: AbortSignal; done: (s: Sharp) => void; fail: (e: unknown) => void }[] = [];
  const got: [number, Sharp][] = [];
  const released: string[] = [];
  const feed = new LoupeFeed({
    load: (page, px, signal) => new Promise<Sharp>((done, fail) => { calls.push({ page, px, signal, done, fail }); }),
    onSharp: (p, s) => got.push([p, s]),
    release: (s) => released.push(s.url),
    budget,
  });
  return { feed, calls, got, released };
}
const flush = async () => { for (let i = 0; i < 4; i++) await Promise.resolve(); };

describe("the sharp pictures", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("asks nothing until the pointer has rested on a page for the dwell", () => {
    const { feed, calls } = rig();
    feed.hover(4, 1600);
    vi.advanceTimersByTime(DWELL_MS - 1);
    expect(calls).toHaveLength(0);
    vi.advanceTimersByTime(1);
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ page: 4, px: 1600 });
  });

  it("asks nothing when the pointer leaves first, and aborts what is in flight", () => {
    const { feed, calls } = rig();
    feed.hover(4, 1600);
    vi.advanceTimersByTime(100);
    feed.leave();
    vi.advanceTimersByTime(500);
    expect(calls).toHaveLength(0);
    feed.hover(5, 1600);
    vi.advanceTimersByTime(DWELL_MS);
    expect(feed.inflight).toBe(true);
    feed.leave();
    expect(calls[0].signal.aborted).toBe(true);
    expect(feed.inflight).toBe(false);
  });

  it("has one request in flight: a new page aborts the old one", () => {
    const { feed, calls } = rig();
    feed.hover(1, 1600); vi.advanceTimersByTime(DWELL_MS);
    feed.hover(2, 1600);
    expect(calls[0].signal.aborted).toBe(true);
    vi.advanceTimersByTime(DWELL_MS);
    expect(calls.filter((c) => !c.signal.aborted)).toHaveLength(1);
    expect(calls[1].page).toBe(2);
  });

  it("does not ask twice for a page it is already waiting for or fetching", () => {
    const { feed, calls } = rig();
    feed.hover(7, 1600); feed.hover(7, 1600); vi.advanceTimersByTime(DWELL_MS);
    feed.hover(7, 1600); feed.hover(7, 1600); vi.advanceTimersByTime(DWELL_MS * 2);
    expect(calls).toHaveLength(1);
  });

  it("hands the picture to the lens when it arrives, and a late one for a page left is dropped and released", async () => {
    const { feed, calls, got, released } = rig();
    feed.hover(3, 1600); vi.advanceTimersByTime(DWELL_MS);
    const a = pic(); calls[0].done(a); await flush();
    expect(got).toEqual([[3, a]]);
    feed.hover(8, 1600); vi.advanceTimersByTime(DWELL_MS);
    const late = pic(); calls[1].done(late);
    feed.hover(9, 1600);
    await flush();
    expect(got).toHaveLength(1);
    expect(released).toContain(late.url);
  });

  it("returns a held picture at once, with no request", async () => {
    const { feed, calls } = rig();
    feed.hover(3, 1600); vi.advanceTimersByTime(DWELL_MS);
    const a = pic(); calls[0].done(a); await flush();
    expect(feed.hover(3, 1600)).toBe(a);
    vi.advanceTimersByTime(1000);
    expect(calls).toHaveLength(1);
  });

  it("asks again for a sharper picture when a larger zoom needs one, but never for a page whose best is held", async () => {
    const { feed, calls } = rig();
    feed.hover(3, 1600); vi.advanceTimersByTime(DWELL_MS);
    calls[0].done(pic(1600, false)); await flush();
    expect(feed.hover(3, 2400)).toBeUndefined();
    vi.advanceTimersByTime(DWELL_MS);
    expect(calls).toHaveLength(2);
    expect(calls[1].px).toBe(2400);
    calls[1].done(pic(2400, true)); await flush();
    expect(feed.hover(3, 3300)).toBeDefined();
    expect(calls).toHaveLength(2);
  });

  it("keeps the last few: the least recently used goes first and is released", async () => {
    const { feed, calls, released } = rig({ count: 2, bytes: 1e12 });
    const held: Record<number, Sharp> = {};
    for (const p of [1, 2, 3]) {
      feed.hover(p, 1600); vi.advanceTimersByTime(DWELL_MS);
      held[p] = pic(); calls[calls.length - 1].done(held[p]); await flush();
      if (p === 2) feed.hover(1, 1600);                     // page 1 is used again, so page 2 is the older
    }
    expect(feed.held.sort()).toEqual([1, 3]);
    expect(released).toEqual([held[2].url]);
  });

  it("is held to a byte budget as well, and the picture just kept stays however large", async () => {
    const { feed, calls, released } = rig({ count: 10, bytes: 5_000_000 });      // 800 x 1000 x 4 = 3.2 MB each
    for (const p of [1, 2]) { feed.hover(p, 1600); vi.advanceTimersByTime(DWELL_MS); calls[calls.length - 1].done(pic()); await flush(); }
    expect(feed.held).toEqual([2]);
    expect(released).toHaveLength(1);
    expect(feed.heldBytes).toBe(3_200_000);
    feed.hover(3, 1600); vi.advanceTimersByTime(DWELL_MS); calls[calls.length - 1].done(pic(1600, true, 4000, 5000)); await flush();
    expect(feed.held).toEqual([3]);
  });

  it("releases everything when it is disposed", async () => {
    const { feed, calls, released } = rig();
    feed.hover(1, 1600); vi.advanceTimersByTime(DWELL_MS);
    const a = pic(); calls[0].done(a); await flush();
    feed.dispose();
    expect(released).toEqual([a.url]);
    expect(feed.held).toEqual([]);
  });

  it("reports a failure and keeps going", async () => {
    const failed: [number, string][] = [];
    const calls: { fail: (e: unknown) => void }[] = [];
    const feed = new LoupeFeed({ load: () => new Promise<Sharp>((_, fail) => { calls.push({ fail }); }), onSharp: () => undefined, onFail: (p, w) => failed.push([p, w]), budget: { count: 2, bytes: 1e9 } });
    feed.hover(5, 1600); vi.advanceTimersByTime(DWELL_MS);
    calls[0].fail(new Error("nope")); await flush();
    expect(failed).toEqual([[5, "nope"]]);
    expect(feed.inflight).toBe(false);
  });
});

describe("the memory budget", () => {
  it("holds fewer pictures on a small device, and never more than a fraction of the thumbnails' memory", () => {
    expect(loupeBudget(128, false)).toEqual({ count: 3, bytes: 64_000_000 });
    expect(loupeBudget(128, true).count).toBe(2);
    expect(loupeBudget(8, false).bytes).toBe(24_000_000);
    expect(loupeBudget(4000, false).bytes).toBe(160_000_000);
  });
});

describe("the loader", () => {
  const decode = async () => ({ w: 1600, h: 2070 });
  it("uses the browser's own finer drawing when there is one, and says when nothing sharper exists", async () => {
    const load = sharpLoader({ drawLarge: async () => ({ url: "blob:big", px: 3300 }), server: async () => "blob:srv", decode: async () => ({ w: 2550, h: 3300 }) });
    const s = await load(2, 3300, new AbortController().signal);
    expect(s).toMatchObject({ url: "blob:big", px: 3300, best: true });
    const part = sharpLoader({ drawLarge: async () => ({ url: "blob:big", px: 2400 }), server: async () => "blob:srv", decode: async () => ({ w: 1855, h: 2400 }) });
    expect((await part(2, 2400, new AbortController().signal)).best).toBe(false);
  });
  it("stops at the page's own detail: a drawing smaller than asked is the best there is", async () => {
    const load = sharpLoader({ drawLarge: async () => ({ url: "blob:big", px: 3300 }), server: async () => "blob:srv", decode: async () => ({ w: 1700, h: 2200 }) });
    expect(await load(1, 3300, new AbortController().signal)).toMatchObject({ best: true, px: 2200 });
  });
  it("falls back to the server's largest size when the browser did not draw the page", async () => {
    const server = vi.fn(async () => "blob:srv");
    const load = sharpLoader({ drawLarge: async () => null, server, decode });
    expect(await load(4, 3300, new AbortController().signal)).toMatchObject({ url: "blob:srv", px: SERVER_MAX_PX, best: true });
    expect(server).toHaveBeenCalledWith(4, expect.anything());
    const plain = sharpLoader({ server, decode });
    expect((await plain(4, 1600, new AbortController().signal)).best).toBe(true);
  });
  it("releases a picture it could not decode", async () => {
    const revoke = vi.fn(); const orig = URL.revokeObjectURL; URL.revokeObjectURL = revoke;
    try {
      const load = sharpLoader({ server: async () => "blob:broken", decode: async () => { throw new Error("bad"); } });
      await expect(load(1, 1600, new AbortController().signal)).rejects.toThrow("bad");
      expect(revoke).toHaveBeenCalledWith("blob:broken");
    } finally { URL.revokeObjectURL = orig; }
  });
});
