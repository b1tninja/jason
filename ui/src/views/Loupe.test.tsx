import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Loupe, type LoupeProps } from "./Loupe";
import type { Sharp } from "./splitLoupe";

// jsdom has no PointerEvent
if (typeof window.PointerEvent === "undefined") {
  class PointerEventStub extends MouseEvent {
    pointerType: string; pointerId: number;
    constructor(type: string, init: MouseEventInit & { pointerType?: string; pointerId?: number } = {}) { super(type, init); this.pointerType = init.pointerType ?? "mouse"; this.pointerId = init.pointerId ?? 1; }
  }
  Object.defineProperty(window, "PointerEvent", { value: PointerEventStub, configurable: true });
}

const RECT = { left: 100, top: 100, width: 124, height: 160, right: 224, bottom: 260, x: 100, y: 100, toJSON: () => ({}) };

function Pages({ n = 3 }: { n?: number }) {
  return (
    <div id="grid">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="split-cell" data-cell="" data-page={i + 1}>
          <button type="button" className="split-cell-btn">
            <span className="split-pic" data-loupe={i + 1}><img alt="" src={`data:image/svg+xml,page${i + 1}`} /></span>
          </button>
        </div>
      ))}
      <p id="elsewhere">elsewhere</p>
    </div>
  );
}

function sharp(url = "blob:sharp"): Sharp { return { url, width: 1600, height: 2070, px: 1600, best: true }; }

function setup(over: Partial<LoupeProps> = {}) {
  const load = vi.fn(async (_p: number, _px: number, _s: AbortSignal) => sharp());
  const props: LoupeProps = { enabled: true, touchMode: false, zoom: 3, onZoom: vi.fn(), load, budget: { count: 3, bytes: 1e9 }, maxPx: 1600, announce: vi.fn(), ...over };
  const r = render(<><Pages /><Loupe {...props} /></>);
  document.querySelectorAll("img").forEach((img) => { img.getBoundingClientRect = () => RECT as DOMRect; });
  const lens = () => document.querySelector<HTMLElement>(".split-loupe")!;
  return { ...r, props, load, lens };
}

const move = (target: Element, x = 150, y = 180, pointerType = "mouse") => act(() => { target.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: x, clientY: y, pointerType })); });
const frames = (ms = 20) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("the lens", () => {
  it("shows over a page picture, named for the page, and never takes a pointer event", async () => {
    const { lens } = setup();
    expect(lens().hidden).toBe(true);
    await move(document.querySelector(".split-pic img")!);
    await frames();
    expect(lens().hidden).toBe(false);
    expect(lens().getAttribute("role")).toBe("img");
    expect(lens().getAttribute("aria-label")).toBe("Magnified page 1");
    expect(lens().style.pointerEvents).toBe("none");
    expect(lens().dataset.size).toBe("cell");                       // the cell's own picture, until the sharp one arrives
    expect(lens().style.backgroundImage).toContain("page1");
  });

  it("swaps to the sharp picture in place after the dwell", async () => {
    const { lens, load } = setup();
    await move(document.querySelector(".split-pic img")!);
    await frames(100);
    expect(load).not.toHaveBeenCalled();
    await frames(100);
    expect(load).toHaveBeenCalledTimes(1);
    expect(load.mock.calls[0][0]).toBe(1);
    expect(lens().hidden).toBe(false);
    expect(lens().dataset.size).toBe("sharp");
    expect(lens().style.backgroundImage).toContain("blob:sharp");
  });

  it("goes when the pointer leaves the pages, and asks for nothing if it left before the dwell", async () => {
    const { lens, load } = setup();
    await move(document.querySelector(".split-pic img")!);
    await frames(60);
    await move(document.getElementById("elsewhere")!);
    await frames(400);
    expect(lens().hidden).toBe(true);
    expect(load).not.toHaveBeenCalled();
  });

  it("follows the pointer to another page, and flips to the left near the right edge", async () => {
    const { lens } = setup();
    const imgs = document.querySelectorAll(".split-pic img");
    await move(imgs[0], 150, 180);
    await frames();
    const first = lens().style.transform;
    await move(imgs[1], window.innerWidth - 10, 180);
    await frames();
    expect(lens().getAttribute("aria-label")).toBe("Magnified page 2");
    expect(lens().style.transform).not.toBe(first);
    const x = Number(/translate3d\((-?\d+)px/.exec(lens().style.transform)![1]);
    expect(x).toBeLessThan(window.innerWidth - 10 - 18);          // on the pointer's left
    expect(x + 220).toBeLessThanOrEqual(window.innerWidth - 6);
  });

  it("is placed by a transform in an animation frame: a burst of moves is one placement", async () => {
    const { lens } = setup();
    const img = document.querySelector(".split-pic img")!;
    await move(img);
    await frames();
    const spy = vi.spyOn(img, "getBoundingClientRect");
    act(() => { for (let i = 0; i < 20; i++) img.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 130 + i, clientY: 190, pointerType: "mouse" })); });
    await frames();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(lens().style.left).toBe("");
    expect(lens().style.top).toBe("");
  });

  it("is not there at all when the magnifier is off", async () => {
    const { lens, load } = setup({ enabled: false });
    await move(document.querySelector(".split-pic img")!);
    await frames(400);
    expect(document.querySelector(".split-loupe")?.hasAttribute("hidden") ?? true).toBe(true);
    expect(lens()?.hidden ?? true).toBe(true);
    expect(load).not.toHaveBeenCalled();
  });

  it("hides on Escape, and stays hidden over the same page until the pointer goes elsewhere", async () => {
    const { lens } = setup();
    const imgs = document.querySelectorAll(".split-pic img");
    await move(imgs[0]);
    await frames();
    const seen = vi.fn();
    document.addEventListener("keydown", seen);
    act(() => { imgs[0].dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })); });
    expect(lens().hidden).toBe(true);
    expect(seen).not.toHaveBeenCalled();                             // Escape is the magnifier's while the lens shows: the screen's handlers are not asked
    await move(imgs[0], 160, 190);
    await frames();
    expect(lens().hidden).toBe(true);
    await move(imgs[1]);
    await frames();
    expect(lens().hidden).toBe(false);
    document.removeEventListener("keydown", seen);
  });

  it("changes the zoom with Alt and the wheel, but leaves the plain wheel to scroll", async () => {
    const { lens, props } = setup();
    await move(document.querySelector(".split-pic img")!);
    await frames();
    const plain = new WheelEvent("wheel", { deltaY: -100, bubbles: true, cancelable: true });
    act(() => { document.dispatchEvent(plain); });
    expect(plain.defaultPrevented).toBe(false);
    expect(props.onZoom).not.toHaveBeenCalled();
    const alt = new WheelEvent("wheel", { deltaY: -100, altKey: true, bubbles: true, cancelable: true });
    act(() => { document.dispatchEvent(alt); });
    expect(alt.defaultPrevented).toBe(true);
    expect(props.onZoom).toHaveBeenCalledWith(3.5);
    expect(props.announce).toHaveBeenCalledWith("Magnifier 3.5 times");
    expect(lens()).toBeTruthy();
  });

  it("shows beside the focused page with Alt and an arrow key, and announces it politely", async () => {
    const { lens, props } = setup();
    const btn = document.querySelector<HTMLElement>(".split-cell-btn")!;
    btn.focus();
    act(() => { btn.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", altKey: true, bubbles: true, cancelable: true })); });
    await frames();
    expect(lens().hidden).toBe(false);
    expect(lens().dataset.mode).toBe("beside");
    expect(lens().getAttribute("aria-label")).toBe("Magnified page 1");
    expect(props.announce).toHaveBeenCalledWith(expect.stringContaining("Magnifier on page 1"));
    const before = lens().style.backgroundPosition;
    act(() => { btn.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", altKey: true, bubbles: true, cancelable: true })); });
    await frames();
    expect(lens().style.backgroundPosition).not.toBe(before);        // the spot moved
    act(() => { btn.dispatchEvent(new KeyboardEvent("keydown", { key: "=", altKey: true, bubbles: true, cancelable: true })); });
    expect(props.onZoom).toHaveBeenCalledWith(3.5);
  });

  it("shows the lens beside a page the keyboard has just moved to", async () => {
    const { lens } = setup();
    const btns = document.querySelectorAll<HTMLElement>(".split-cell-btn");
    btns[0].focus();
    act(() => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    btns[1].focus();
    await frames();
    expect(lens().hidden).toBe(false);
    expect(lens().getAttribute("aria-label")).toBe("Magnified page 2");
    expect(lens().dataset.mode).toBe("beside");
  });
});

describe("the guarantee: the lens never blocks the page it magnifies", () => {
  it("captures no pointer, and cancels no press, click or drag, so a click through it marks as it would without it", async () => {
    const capture = vi.fn();
    (Element.prototype as unknown as { setPointerCapture: unknown }).setPointerCapture = capture;
    const { lens } = setup();
    const img = document.querySelector(".split-pic img")!;
    await move(img);
    await frames();
    expect(lens().hidden).toBe(false);
    const seen: string[] = [];
    const grid = document.getElementById("grid")!;
    for (const t of ["pointerdown", "pointerup", "click", "contextmenu", "dblclick"]) grid.addEventListener(t, () => seen.push(t));
    const events = ["pointerdown", "pointerup", "click", "dblclick"].map((t) => (t.startsWith("pointer") ? new PointerEvent(t, { bubbles: true, cancelable: true, pointerType: "mouse" }) : new MouseEvent(t, { bubbles: true, cancelable: true })));
    act(() => { for (const e of events) img.dispatchEvent(e); });
    expect(seen).toEqual(["pointerdown", "pointerup", "click", "dblclick"]);
    expect(events.every((e) => !e.defaultPrevented)).toBe(true);
    expect(capture).not.toHaveBeenCalled();
    expect(lens().hidden).toBe(false);                               // and the lens stays up while the person clicks
  });

  it("does not read its source for a pointer-capture call at all", async () => {
    const mod = await import("./Loupe?raw");
    expect(String((mod as { default: string }).default)).not.toMatch(/setPointerCapture|releasePointerCapture/);
  });
});

describe("touch", () => {
  const touch = (type: string, target: Element, x: number, y: number) => act(() => { target.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerType: "touch", pointerId: 7 })); });

  it("shows the lens above the finger after a hold, never before, and never at all when the finger moves first", async () => {
    document.elementFromPoint = () => document.querySelector(".split-pic img");
    const { lens } = setup({ touchMode: true, enabled: false });
    const img = document.querySelector(".split-pic img")!;
    await touch("pointerdown", img, 150, 300);
    await frames(200);
    expect(lens().hidden).toBe(true);
    await touch("pointermove", img, 190, 300);                        // moved past the slop: a scroll
    await frames(300);
    expect(lens().hidden).toBe(true);
    await touch("pointerup", img, 190, 300);

    await touch("pointerdown", img, 150, 300);
    await frames(400);
    expect(lens().hidden).toBe(false);
    expect(lens().dataset.mode).toBe("touch");
    const y = Number(/translate3d\(-?\d+px, (-?\d+)px/.exec(lens().style.transform)![1]);
    expect(y + 220).toBeLessThan(300);                               // above the finger
    await touch("pointermove", img, 160, 310);
    await frames();
    expect(lens().hidden).toBe(false);
    await touch("pointerup", img, 160, 310);
    await frames();
    expect(lens().hidden).toBe(true);
  });

  it("swallows the click that ends a hold, and only that one", async () => {
    document.elementFromPoint = () => document.querySelector(".split-pic img");
    setup({ touchMode: true, enabled: false });
    const img = document.querySelector(".split-pic img")!;
    const clicked = vi.fn();
    document.getElementById("grid")!.addEventListener("click", clicked);
    await touch("pointerdown", img, 150, 300);
    await frames(400);
    await touch("pointerup", img, 150, 300);
    act(() => { img.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })); });
    expect(clicked).not.toHaveBeenCalled();
    await frames(800);
    act(() => { img.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })); });
    expect(clicked).toHaveBeenCalledTimes(1);
  });

  it("does nothing for a touch when the magnify mode is off", async () => {
    const { lens } = setup({ touchMode: false, enabled: true });
    const img = document.querySelector(".split-pic img")!;
    await touch("pointerdown", img, 150, 300);
    await frames(600);
    expect(lens().hidden).toBe(true);
  });
});
