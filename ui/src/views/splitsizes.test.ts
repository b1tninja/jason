import { describe, expect, it } from "vitest";
import { SIZE_PX, figureSizes, sizeFor, sizesFor, stepWithin, type Size } from "./splitModel";
import { ThumbLoader } from "./splitThumbs";
import { budgetFor, pixelMegabytes } from "./splitWindow";

/** Pictures follow the displayed size: CSS size x pixel ratio, rounded up to the next step, held to the memory budget. */

describe("the size a cell needs", () => {
  it("is the next step at or above the longest displayed side in device pixels", () => {
    expect(sizeFor(90, 1)).toBe("tiny");
    expect(sizeFor(97, 1)).toBe("small");
    expect(sizeFor(189 * 1.5, 1)).toBe("medium");                 // a 189 x 285 cell: the 285 side needs more than the 200 px picture
    expect(sizeFor(285, 1)).toBe("medium");
    expect(sizeFor(285, 2)).toBe("large");                         // on a 2x screen the same cell needs 570 device pixels
    expect(sizeFor(285, 3)).toBe("huge");                          // 855 device pixels pass the 800 step
    expect(sizeFor(520 * 1.294, 2)).toBe("huge");                  // a one-page-at-a-time cell on a 2x screen
    expect(sizeFor(5000, 3)).toBe("huge");                         // never past the ladder
  });

  it("never goes above the cap, and a cap is a ceiling not a floor", () => {
    expect(sizeFor(5000, 2, "large")).toBe("large");
    expect(sizeFor(100, 1, "small")).toBe("small");
    expect(sizeFor(10, 1, "huge")).toBe("tiny");
  });

  it("asks for a quick low-resolution picture first and the sharp one with it", () => {
    expect(sizesFor(285, 2, "huge")).toEqual(["tiny", "large"]);
    expect(sizesFor(60, 1, "huge")).toEqual(["tiny"]);
    expect(sizesFor(285, 2, "small")).toEqual(["tiny", "small"]);  // the memory cap holds it to a smaller one
  });

  it("gives the compare pane the sharpest picture the zoom needs", () => {
    expect(figureSizes("full", 700, 1)).toEqual(["small", "large"]);
    expect(figureSizes("enlarged", 700, 1)).toEqual(["small", "huge"]);
    expect(figureSizes("fit", 600, 2)).toEqual(["small", "huge"]);
    expect(figureSizes("fit", 300, 1)).toEqual(["small", "medium"]);
  });
});

describe("the memory budget caps the size", () => {
  it("lets few cells be sharp and many cells be smaller", () => {
    expect(stepWithin(1, 128)).toBe("huge");
    expect(stepWithin(30, 128)).toBe("large");                     // 30 cells at 800 px hold about 59 MB of decoded pixels
    expect(stepWithin(100, 128)).toBe("medium");                   // 100 cells at 800 px would hold about 197 MB
    expect(stepWithin(200, 48)).toBe("small");                     // never below the album's readable size
    expect(SIZE_PX[stepWithin(12, 128)]).toBeGreaterThanOrEqual(SIZE_PX[stepWithin(60, 128)]);
  });

  it("is smaller on a phone or a low-memory device", () => {
    expect(pixelMegabytes({ width: 1200 })).toBeGreaterThan(pixelMegabytes({ width: 390 }));
    expect(pixelMegabytes({ width: 1200, deviceMemory: 2 })).toBe(pixelMegabytes({ width: 390 }));
  });

  it("is kept by the loader: pictures off screen are released past the budget, those on screen never", async () => {
    const urls: string[] = [];
    let n = 0;
    const loader = new ThumbLoader({
      urlOf: (p, s) => `${s}:${p}`, fetcher: async () => { const u = `blob:${++n}`; urls.push(u); return u; }, budget: { ...budgetFor({ width: 1200 }), huge: 1 },
    });
    const on = document.createElement("img");
    loader.attach(on, 1, ["huge"]);
    await new Promise((r) => setTimeout(r, 5));
    for (let p = 2; p <= 5; p++) { const el = document.createElement("img"); const off = loader.attach(el, p, ["huge"]); await new Promise((r) => setTimeout(r, 5)); off(); await new Promise((r) => setTimeout(r, 2)); }
    expect(loader.stats().cached.huge).toBeLessThanOrEqual(2);
    expect(on.dataset.state).toBe("ready");
    expect(on.src).toBe("blob:1");
    loader.clear();
  });
});

describe("upgrading in place", () => {
  it("keeps the quick picture on screen, never blank, until the sharp one arrives", async () => {
    const gates = new Map<string, () => void>();
    const loader = new ThumbLoader({
      urlOf: (p, s) => `${s}:${p}`, concurrency: 4,
      fetcher: (key) => new Promise<string>((resolve) => { gates.set(key, () => resolve(`blob:${key}`)); }),
    });
    const el = document.createElement("img");
    const seen: string[] = [];
    const watch = () => seen.push(`${el.dataset.size ?? ""}|${el.src}`);
    const detach = loader.attach(el, 7, ["tiny", "small"]);
    gates.get("tiny:7")!(); await new Promise((r) => setTimeout(r, 0)); watch();
    expect(el.dataset.size).toBe("tiny");
    // the cell is enlarged: the same picture element is attached again for a sharper size
    detach();
    loader.attach(el, 7, ["tiny", "medium"]);
    watch();
    expect(el.src).toBe("blob:tiny:7");                            // still the quick picture, nothing cleared
    expect(el.dataset.state).toBe("ready");
    gates.get("medium:7")!(); await new Promise((r) => setTimeout(r, 0)); watch();
    expect(el.dataset.size).toBe("medium");
    expect(el.src).toBe("blob:medium:7");
    expect(seen.every((s) => s.includes("blob:"))).toBe(true);     // at no point was the picture empty
    // a sharper picture already held is used at once when the size returns
    expect((["tiny", "medium"] as Size[]).every((s) => loader.stats().cached[s] === 1)).toBe(true);
    loader.clear();
  });

  it("does not ask for a size the cell no longer wants", async () => {
    const asked: string[] = [];
    const loader = new ThumbLoader({ urlOf: (p, s) => `${s}:${p}`, concurrency: 1, fetcher: (key) => { asked.push(key); return new Promise<string>(() => undefined); } });
    const el = document.createElement("img");
    const off = loader.attach(el, 3, ["tiny", "huge"]);
    off();
    await new Promise((r) => setTimeout(r, 5));
    expect(loader.stats().queued).toBe(0);
    loader.clear();
  });
});
