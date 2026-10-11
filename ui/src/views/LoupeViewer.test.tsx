import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Loupe, type LoupeProps } from "./Loupe";
import type { Sharp } from "./splitLoupe";

// The fixed viewer, the magnifier's second mode (docs/pdf-splitter.md, section 5.12).
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

const sharp = (): Sharp => ({ url: "blob:sharp", width: 1600, height: 2070, px: 1600, best: true });

function setup(over: Partial<LoupeProps> = {}) {
  const load = vi.fn(async (_p: number, _px: number, _s: AbortSignal) => sharp());
  const props: LoupeProps = {
    enabled: true, touchMode: false, zoom: 3, onZoom: vi.fn(), load, budget: { count: 3, bytes: 1e9 }, maxPx: 1600, announce: vi.fn(),
    mode: "fixed", corner: "bottom-right", size: 360, view: "region", hop: true, phone: false, onView: vi.fn(), onSize: vi.fn(), ...over,
  };
  const r = render(<><Pages /><Loupe {...props} /></>);
  document.querySelectorAll("img").forEach((img) => { img.getBoundingClientRect = () => RECT as DOMRect; });
  const panel = () => document.querySelector<HTMLElement>(".split-viewer")!;
  const finder = () => document.querySelector<HTMLElement>(".split-viewfinder")!;
  const lens = () => document.querySelector<HTMLElement>(".split-loupe")!;
  const title = () => panel().querySelector("[data-role=title]")!.textContent;
  const pos = () => /translate3d\((-?\d+)px, (-?\d+)px/.exec(panel().style.transform)!.slice(1).map(Number);
  return { ...r, props, load, panel, finder, lens, title, pos };
}

const move = (target: Element, x = 150, y = 180) => act(() => { target.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: x, clientY: y, pointerType: "mouse" })); });
const frames = (ms = 20) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const imgs = () => document.querySelectorAll(".split-pic img");

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("the fixed viewer", () => {
  it("is a labelled region with a picture, shows the page under the pointer in words, and the lens stays away", async () => {
    const { panel, lens, title } = setup();
    expect(panel().hidden).toBe(true);
    await move(imgs()[0]);
    await frames();
    expect(panel().hidden).toBe(false);
    expect(panel().getAttribute("role")).toBe("region");
    expect(panel().getAttribute("aria-label")).toBe("Magnified page");
    const pic = panel().querySelector(".split-viewer-pic")!;
    expect(pic.getAttribute("role")).toBe("img");
    expect(pic.getAttribute("aria-label")).toBe("Magnified page 1");
    expect(title()).toBe("Page 1");
    expect(panel().querySelector("[data-role=zoom]")!.textContent).toBe("3 times zoom");
    expect(lens().hidden).toBe(true);
    expect((pic as HTMLElement).style.backgroundImage).toContain("page1");     // the cell's picture until the sharp one arrives
    expect(panel().dataset.size).toBe("cell");
  });

  it("swaps to the sharp picture in place after the dwell, once", async () => {
    const { panel, load } = setup();
    await move(imgs()[0]);
    await frames(100);
    expect(load).not.toHaveBeenCalled();
    await frames(100);
    expect(load).toHaveBeenCalledTimes(1);
    expect(panel().dataset.size).toBe("sharp");
    expect(panel().querySelector<HTMLElement>(".split-viewer-pic")!.style.backgroundImage).toContain("blob:sharp");
  });

  it("stays in the same place across hovers over different pages", async () => {
    const { pos, title } = setup();
    await move(imgs()[0], 150, 180);
    await frames();
    const first = pos();
    await move(imgs()[1], 160, 190);
    await frames();
    await move(imgs()[2], 140, 170);
    await frames();
    expect(title()).toBe("Page 3");
    expect(pos()).toEqual(first);
  });

  it("is in the corner chosen, inside the window", async () => {
    for (const [corner, x, y] of [["bottom-right", 652, 338], ["top-left", 12, 12], ["top-right", 652, 12], ["bottom-left", 12, 338]] as const) {
      const { pos, unmount } = setup({ corner });
      await move(imgs()[0]);
      await frames();
      expect(pos()).toEqual([x, y]);
      unmount();
      cleanup();
    }
  });

  it("keeps showing the last page when the pointer leaves the pages, and the sharp picture still arrives", async () => {
    const { panel, title, load } = setup();
    await move(imgs()[1]);
    await frames(60);
    await move(document.getElementById("elsewhere")!, 700, 500);
    await frames(300);
    expect(panel().hidden).toBe(false);
    expect(title()).toBe("Page 2");
    expect(load).toHaveBeenCalledTimes(1);                  // not cancelled by leaving
    expect(panel().dataset.size).toBe("sharp");
    act(() => { document.dispatchEvent(new PointerEvent("pointerout", { bubbles: true, pointerType: "mouse" })); });
    await frames();
    expect(panel().hidden).toBe(false);
  });

  it("pin freezes it on one page: other pages do not change it, and the strip says so", async () => {
    const { panel, title } = setup();
    await move(imgs()[0]);
    await frames();
    act(() => { fireEvent.click(panel().querySelector("[data-act=pin]")!); });
    await frames();
    expect(panel().querySelector("[data-act=pin]")!.getAttribute("aria-pressed")).toBe("true");
    expect(title()).toBe("Pinned to page 1");
    await move(imgs()[2]);
    await frames();
    expect(title()).toBe("Pinned to page 1");
    expect(panel().querySelector(".split-viewer-pic")!.getAttribute("aria-label")).toBe("Magnified page 1");
    act(() => { fireEvent.click(panel().querySelector("[data-act=pin]")!); });
    await move(imgs()[2]);
    await frames();
    expect(title()).toBe("Page 3");
  });

  it("hides on Escape (which is then not passed on), and shows again for another page", async () => {
    const { panel } = setup();
    await move(imgs()[0]);
    await frames();
    const seen = vi.fn();
    document.addEventListener("keydown", seen);
    act(() => { imgs()[0].dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })); });
    expect(panel().hidden).toBe(true);
    expect(seen).not.toHaveBeenCalled();
    await move(imgs()[0], 160, 190);
    await frames();
    expect(panel().hidden).toBe(true);
    await move(imgs()[1]);
    await frames();
    expect(panel().hidden).toBe(false);
    document.removeEventListener("keydown", seen);
  });

  it("hops to the opposite corner when the pointer stays under it, after a debounce", async () => {
    const { pos, props } = setup();
    await move(imgs()[0]);
    await frames();
    expect(pos()).toEqual([652, 338]);
    await move(document.getElementById("elsewhere")!, 800, 500);          // under the panel's footprint
    await frames(100);
    expect(pos()).toEqual([652, 338]);                                      // not yet
    await frames(300);
    expect(pos()).toEqual([12, 12]);
    expect(props.announce).toHaveBeenCalledWith("Viewer moved to the top left corner.");
    // a pointer in the middle of the window is under neither corner: it stays where it hopped
    await move(document.getElementById("elsewhere")!, 560, 600);
    await frames(600);
    expect(pos()).toEqual([12, 12]);
    // and one that goes under it again hops back
    await move(imgs()[0], 150, 180);
    await frames(400);
    expect(pos()).toEqual([652, 338]);
  });

  it("does not hop away from a pointer that is on its own controls", async () => {
    const { pos, panel } = setup();
    await move(imgs()[0]);
    await frames();
    await move(panel().querySelector("[data-act=pin]")!, 800, 400);
    await frames(800);
    expect(pos()).toEqual([652, 338]);
  });

  it("does not hop when the pointer only crosses its footprint", async () => {
    const { pos } = setup();
    await move(imgs()[0]);
    await frames();
    await move(document.getElementById("elsewhere")!, 800, 500);
    await frames(100);
    await move(imgs()[0], 150, 180);
    await frames(400);
    expect(pos()).toEqual([652, 338]);
  });

  it("does not hop when asked not to", async () => {
    const { pos } = setup({ hop: false });
    await move(imgs()[0]);
    await frames();
    await move(document.getElementById("elsewhere")!, 800, 500);
    await frames(600);
    expect(pos()).toEqual([652, 338]);
  });

  it("draws a viewfinder on the hovered thumbnail in the region view, and none for the whole page", async () => {
    const { finder, panel } = setup();
    await move(imgs()[0], 162, 180);
    await frames();
    expect(finder().hidden).toBe(false);
    expect(finder().getAttribute("aria-hidden")).toBe("true");
    expect(finder().style.pointerEvents).toBe("");                          // from the stylesheet: none
    expect(parseInt(finder().style.width)).toBeGreaterThan(0);
    expect(panel().dataset.view).toBe("region");
    cleanup();
    const whole = setup({ view: "page" });
    await move(imgs()[0], 162, 180);
    await frames();
    expect(whole.panel().dataset.view).toBe("page");
    expect(whole.finder().hidden).toBe(true);
    expect(whole.panel().querySelector("[data-role=zoom]")!.textContent).toBe("Whole page");
  });

  it("the view button asks for the other view and says its state", async () => {
    const { panel, props } = setup();
    await move(imgs()[0]);
    await frames();
    const btn = panel().querySelector("[data-act=view]")!;
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    act(() => { fireEvent.click(btn); });
    expect(props.onView).toHaveBeenCalledWith("page");
    expect(props.announce).toHaveBeenCalledWith("Viewer shows the whole page.");
  });

  it("Alt and the arrows move the region for the focused page, which it shows at the centre", async () => {
    const { panel } = setup();
    const btn = document.querySelectorAll<HTMLElement>(".split-cell-btn")[1];
    btn.focus();
    act(() => { btn.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true })); });
    act(() => { btn.dispatchEvent(new FocusEvent("focusin", { bubbles: true })); });
    await frames();
    expect(panel().hidden).toBe(false);
    expect(panel().dataset.page).toBe("2");
    const bg0 = panel().querySelector<HTMLElement>(".split-viewer-pic")!.style.backgroundPosition;
    act(() => { btn.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", altKey: true, bubbles: true, cancelable: true })); });
    await frames();
    expect(panel().querySelector<HTMLElement>(".split-viewer-pic")!.style.backgroundPosition).not.toBe(bg0);
  });

  it("on a phone is a band above the action bar, in the window and the width of it", async () => {
    const bar = document.createElement("div");
    bar.className = "split-actionbar";
    bar.getBoundingClientRect = () => ({ left: 0, top: 700, width: 1024, height: 60, right: 1024, bottom: 760, x: 0, y: 700, toJSON: () => ({}) }) as DOMRect;
    document.body.appendChild(bar);
    const { panel, pos } = setup({ phone: true });
    await move(imgs()[0]);
    await frames();
    expect(panel().dataset.mode).toBe("band");
    const [x, y] = pos();
    expect(x).toBe(6);
    expect(y + 58 + parseInt(panel().querySelector<HTMLElement>(".split-viewer-pic")!.style.height)).toBeLessThanOrEqual(700);
    expect(parseInt(panel().style.width)).toBe(1024 - 12);
    bar.remove();
  });

  it("stays out of an open overlay drawer", async () => {
    const drawer = document.createElement("aside");
    drawer.className = "split-drawer";
    drawer.setAttribute("data-drawer", "rail");
    drawer.getBoundingClientRect = () => ({ left: 700, top: 0, width: 324, height: 768, right: 1024, bottom: 768, x: 700, y: 0, toJSON: () => ({}) }) as DOMRect;
    document.body.appendChild(drawer);
    const { pos } = setup();
    await move(imgs()[0]);
    await frames();
    const [x] = pos();
    expect(x + 360).toBeLessThanOrEqual(700);
    drawer.remove();
  });

  it("the resize grip has a name and the arrow keys change the size", async () => {
    const { panel, props } = setup();
    await move(imgs()[0]);
    await frames();
    const grip = panel().querySelector<HTMLElement>("[data-act=resize]")!;
    expect(grip.getAttribute("aria-label")).toMatch(/Resize the viewer/);
    act(() => { fireEvent.keyDown(grip, { key: "ArrowUp" }); });
    expect(props.onSize).toHaveBeenCalledWith(384);
    act(() => { fireEvent.keyDown(grip, { key: "ArrowDown" }); });
    expect(props.onSize).toHaveBeenLastCalledWith(336);
  });

  it("the panel's picture takes no pointer event; its controls are buttons", async () => {
    const { panel } = setup();
    await move(imgs()[0]);
    await frames();
    expect(panel().style.pointerEvents).toBe("");                           // none from the stylesheet; the strip alone is auto there
    expect(panel().querySelectorAll("button").length).toBe(4);
    for (const b of panel().querySelectorAll("button")) expect(b.getAttribute("type")).toBe("button");
  });

  it("changing the mode back to the lens hides the panel", async () => {
    const load = vi.fn(async () => sharp());
    const base: LoupeProps = { enabled: true, touchMode: false, zoom: 3, onZoom: vi.fn(), load, budget: { count: 3, bytes: 1e9 }, maxPx: 1600, announce: vi.fn(), mode: "fixed" };
    const r = render(<><Pages /><Loupe {...base} /></>);
    document.querySelectorAll("img").forEach((img) => { img.getBoundingClientRect = () => RECT as DOMRect; });
    await move(imgs()[0]);
    await frames();
    expect(document.querySelector<HTMLElement>(".split-viewer")!.hidden).toBe(false);
    r.rerender(<><Pages /><Loupe {...base} mode="lens" /></>);
    document.querySelectorAll("img").forEach((img) => { img.getBoundingClientRect = () => RECT as DOMRect; });
    await frames();
    expect(document.querySelector<HTMLElement>(".split-viewer")!.hidden).toBe(true);
    await move(imgs()[1]);
    await frames();
    expect(document.querySelector<HTMLElement>(".split-loupe")!.hidden).toBe(false);
  });
});
