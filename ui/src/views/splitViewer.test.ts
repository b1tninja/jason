import { describe, expect, it } from "vitest";
import {
  ViewerTarget, avoidDrawer, clampViewerPx, cornerPlacement, hopTarget, oppositeCorner, pageFit, phoneBand, regionView, stageBox, underPanel, viewerSize,
  viewfinderRect,
} from "./splitLoupe";
import { DEFAULT_PREFS, loadPrefs, savePrefs } from "./splitLayout";

describe("the fixed viewer: corners and the stage", () => {
  const stage = { left: 0, top: 100, width: 1000, height: 600 };
  it("sits in the chosen corner of the stage with a margin", () => {
    expect(cornerPlacement("bottom-right", stage, 360, 396)).toEqual({ x: 1000 - 360 - 12, y: 100 + 600 - 396 - 12 });
    expect(cornerPlacement("top-left", stage, 360, 396)).toEqual({ x: 12, y: 112 });
    expect(cornerPlacement("top-right", stage, 360, 396)).toEqual({ x: 628, y: 112 });
    expect(cornerPlacement("bottom-left", stage, 360, 396)).toEqual({ x: 12, y: 292 });
  });
  it("the opposite corner is the diagonal one", () => {
    expect(oppositeCorner("bottom-right")).toBe("top-left");
    expect(oppositeCorner("top-left")).toBe("bottom-right");
    expect(oppositeCorner("bottom-left")).toBe("top-right");
    expect(oppositeCorner("top-right")).toBe("bottom-left");
  });
  it("is held inside the stage (and so the window), whatever the stage's shape", () => {
    const st = stageBox({ left: 300, top: -50, width: 2000, height: 900 }, { w: 1000, h: 700 });
    expect(st).toEqual({ left: 300, top: 0, width: 700, height: 700 });
    for (const c of ["bottom-right", "bottom-left", "top-right", "top-left"] as const) {
      const sz = viewerSize(480, st);
      const p = cornerPlacement(c, st, sz.w, sz.h);
      expect(p.x).toBeGreaterThanOrEqual(st.left); expect(p.y).toBeGreaterThanOrEqual(st.top);
      expect(p.x + sz.w).toBeLessThanOrEqual(st.left + st.width); expect(p.y + sz.h).toBeLessThanOrEqual(st.top + st.height);
    }
  });
  it("shrinks to fit a small stage and never below a readable size", () => {
    expect(viewerSize(480, { left: 0, top: 0, width: 300, height: 700 }).pic).toBe(276);
    expect(viewerSize(480, { left: 0, top: 0, width: 1000, height: 200 }).pic).toBe(118);
    expect(viewerSize(480, { left: 0, top: 0, width: 100, height: 100 }).pic).toBe(96);
    expect(clampViewerPx(10)).toBe(160); expect(clampViewerPx(9999)).toBe(720); expect(clampViewerPx(NaN)).toBe(360);
  });
  it("keeps out of an open overlay drawer: a side drawer takes its side, a bottom sheet the bottom, a small one nothing", () => {
    const v = { w: 1000, h: 700 };
    const st = { left: 0, top: 0, width: 1000, height: 700 };
    expect(avoidDrawer(st, { left: 0, top: 0, width: 300, height: 700 }, v)).toEqual({ left: 300, top: 0, width: 700, height: 700 });
    expect(avoidDrawer(st, { left: 650, top: 0, width: 350, height: 700 }, v)).toEqual({ left: 0, top: 0, width: 650, height: 700 });
    expect(avoidDrawer(st, { left: 0, top: 400, width: 1000, height: 300 }, v)).toEqual({ left: 0, top: 0, width: 1000, height: 400 });
    expect(avoidDrawer(st, { left: 10, top: 10, width: 100, height: 100 }, v)).toEqual(st);
    expect(avoidDrawer(st, { left: 2000, top: 0, width: 300, height: 700 }, v)).toEqual(st);
  });
  it("on a phone is a band of about 40 percent just above the action bar, inside the window", () => {
    const b = phoneBand({ w: 390, h: 844 }, 780);
    expect(b.left).toBe(6); expect(b.width).toBe(378);
    expect(b.top + b.height).toBe(774);
    expect(Math.abs(b.height - 844 * 0.4)).toBeLessThanOrEqual(2);
    expect(b.pic).toBe(b.height - 58);
    const low = phoneBand({ w: 390, h: 300 }, 250);
    expect(low.top).toBeGreaterThanOrEqual(0); expect(low.top + low.height).toBeLessThanOrEqual(300);
  });
});

describe("the fixed viewer: hopping", () => {
  const panel = { left: 600, top: 300, width: 360, height: 396 };
  it("is under the panel inside its footprint and a little around it", () => {
    expect(underPanel({ x: 700, y: 400 }, panel)).toBe(true);
    expect(underPanel({ x: 595, y: 400 }, panel)).toBe(true);
    expect(underPanel({ x: 400, y: 400 }, panel)).toBe(false);
  });
  it("names the opposite corner only when the pointer is under it and hopping is allowed", () => {
    expect(hopTarget("bottom-right", { x: 700, y: 400 }, panel, true)).toBe("top-left");
    expect(hopTarget("bottom-right", { x: 700, y: 400 }, panel, false)).toBeNull();
    expect(hopTarget("bottom-right", { x: 100, y: 100 }, panel, true)).toBeNull();
  });
});

describe("the fixed viewer: the region and the viewfinder", () => {
  const page = { left: 100, top: 200, width: 124, height: 160 };
  it("centres the spot, and keeps the region on the page near an edge", () => {
    const mid = regionView({ x: 0.5, y: 0.5 }, page, 6, 360, 360);
    expect(mid.width).toBe(744); expect(mid.height).toBe(960);
    expect(mid.x).toBeCloseTo(180 - 372); expect(mid.y).toBeCloseTo(180 - 480);
    const corner = regionView({ x: 0, y: 0 }, page, 6, 360, 360);
    expect(corner.x).toBeCloseTo(0); expect(corner.y).toBeCloseTo(0);
    const far = regionView({ x: 1, y: 1 }, page, 6, 360, 360);
    expect(far.x).toBeCloseTo(360 - 744); expect(far.y).toBeCloseTo(360 - 960);
  });
  it("centres a page narrower than the panel", () => {
    const r = regionView({ x: 0.1, y: 0.9 }, page, 2, 360, 600);
    expect(r.cx).toBe(0.5); expect(r.cy).toBe(0.5);
  });
  it("draws the viewfinder as the panel's share of the thumbnail: panel size over zoom, inside the page", () => {
    const f = viewfinderRect({ x: 0.5, y: 0.5 }, page, 6, 360, 360);
    expect(f.width).toBeCloseTo(60); expect(f.height).toBeCloseTo(60);
    expect(f.left).toBeCloseTo(100 + 62 - 30); expect(f.top).toBeCloseTo(200 + 80 - 30);
    for (const at of [{ x: 0, y: 0 }, { x: 1, y: 1 }, { x: 0.02, y: 0.97 }]) {
      const r = viewfinderRect(at, page, 6, 360, 360);
      expect(r.left).toBeGreaterThanOrEqual(page.left - 1e-9); expect(r.top).toBeGreaterThanOrEqual(page.top - 1e-9);
      expect(r.left + r.width).toBeLessThanOrEqual(page.left + page.width + 1e-9); expect(r.top + r.height).toBeLessThanOrEqual(page.top + page.height + 1e-9);
    }
    // it is the same region the panel's background shows
    const reg = regionView({ x: 0.25, y: 0.75 }, page, 6, 360, 360);
    const vf = viewfinderRect({ x: 0.25, y: 0.75 }, page, 6, 360, 360);
    expect((vf.left - page.left) / page.width).toBeCloseTo(-reg.x / reg.width);
    expect((vf.top - page.top) / page.height).toBeCloseTo(-reg.y / reg.height);
  });
  it("covers the whole thumbnail when the panel shows all of it", () => {
    const f = viewfinderRect({ x: 0.3, y: 0.3 }, page, 2, 360, 360);
    expect(f).toEqual({ left: 100, top: 200, width: 124, height: 160 });
  });
  it("fits the whole page inside the panel, centred", () => {
    const f = pageFit({ w: 1600, h: 2070 }, page, 360, 360);
    expect(f.height).toBeCloseTo(360); expect(f.width).toBeCloseTo(360 * 1600 / 2070);
    expect(f.x).toBeCloseTo((360 - f.width) / 2); expect(f.y).toBeCloseTo(0);
    expect(pageFit(null, page, 360, 360).height).toBeCloseTo(360);
  });
});

describe("the fixed viewer: which page it shows", () => {
  it("keeps the last page seen: nothing clears it when the pointer leaves", () => {
    const t = new ViewerTarget();
    expect(t.words()).toBe("No page");
    expect(t.see(3)).toBe(true);
    expect(t.page).toBe(3);
    expect(t.words()).toBe("Page 3");
    expect(t.see(7)).toBe(true);
    expect(t.page).toBe(7);
  });
  it("pinned, ignores every other page and says so", () => {
    const t = new ViewerTarget();
    expect(t.pin()).toBe(false);                    // nothing to pin yet
    t.see(4);
    expect(t.pin()).toBe(true);
    expect(t.see(9)).toBe(false);
    expect(t.page).toBe(4);
    expect(t.see(4)).toBe(true);
    expect(t.words()).toBe("Pinned to page 4");
    expect(t.pin()).toBe(false);
    expect(t.see(9)).toBe(true);
    expect(t.words()).toBe("Page 9");
  });
});

describe("the viewer's preferences", () => {
  it("default to the lens, and keep a fixed viewer's choices for the tab", () => {
    expect(loadPrefs("none-yet")).toMatchObject({ magMode: "lens", magCorner: "bottom-right", magPx: 360, magView: "region", magHop: true });
    savePrefs("t1", { ...DEFAULT_PREFS, magMode: "fixed", magCorner: "top-left", magPx: 480, magView: "page", magHop: false });
    expect(loadPrefs("t1")).toMatchObject({ magMode: "fixed", magCorner: "top-left", magPx: 480, magView: "page", magHop: false });
    sessionStorage.setItem("jason-split-layout-bad", JSON.stringify({ magMode: "x", magCorner: "middle", magPx: 99999, magView: 3 }));
    expect(loadPrefs("bad")).toMatchObject({ magMode: "lens", magCorner: "bottom-right", magPx: 720, magView: "region" });
  });
});
