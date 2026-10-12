import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { SplitView, resetDemo } from "./SplitView";
import { DEFAULT_PREFS, dragIntent, fitCell, loadPrefs, resolveLayout, savePrefs, stripWindow } from "./splitLayout";

// jsdom has no PointerEvent: a stand-in that carries pointerType and the coordinates
if (typeof window.PointerEvent === "undefined") {
  class PointerEventStub extends MouseEvent {
    pointerType: string; pointerId: number;
    constructor(type: string, init: MouseEventInit & { pointerType?: string; pointerId?: number } = {}) { super(type, init); this.pointerType = init.pointerType ?? "mouse"; this.pointerId = init.pointerId ?? 1; }
  }
  Object.defineProperty(window, "PointerEvent", { value: PointerEventStub, configurable: true });
}

beforeEach(() => { resetServerSession(); resetDemo(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; document.documentElement.removeAttribute("data-split-focus"); });

/** a screen of this kind: the media queries the layout asks answer by this table */
function screenIs(q: { phone?: boolean; pin?: boolean; big?: boolean }) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("max-width: 719px") ? !!q.phone : query.includes("min-width: 1400px") ? !!q.big : query.includes("min-width: 1200px") ? !!q.pin : false,
    media: query, addEventListener: () => undefined, removeEventListener: () => undefined, addListener: () => undefined, removeListener: () => undefined,
  }));
}

const cell = (page: number) => document.querySelector<HTMLElement>(`button.split-cell-btn[data-page="${page}"]`)!;
async function openDemo() {
  window.location.hash = "#/setup/split/demo";
  render(<SplitView />);
  await screen.findByRole("grid", { name: "Pages" });
  await waitFor(() => expect(cell(1)).toBeTruthy());
}
const saved = () => waitFor(() => expect(document.querySelector('[data-save="saved"]')).toBeTruthy());
const drawer = (name: string) => screen.queryByRole("complementary", { name });
const layoutPrefs = () => JSON.parse(sessionStorage.getItem("jason-split-layout-demo") ?? "{}");

describe("the layout's arithmetic", () => {
  it("fills the width with whole columns of about the chosen size, never narrower than the floor", () => {
    expect(fitCell(1000, 124)).toEqual({ cols: 7, cell: 136 });
    const f = fitCell(1000, 124); expect(f.cols * f.cell + (f.cols - 1) * 8).toBeLessThanOrEqual(1000);
    expect(fitCell(300, 124).cols).toBe(2);
    expect(fitCell(50, 124)).toEqual({ cols: 1, cell: 124 });                         // narrower than one cell: one column at the chosen size
    expect(fitCell(400, 10).cell).toBeGreaterThanOrEqual(48);
    for (const w of [320, 390, 768, 1024, 1440, 1920, 2560]) {
      for (const t of [64, 92, 124, 180, 220]) {
        const { cols, cell: c } = fitCell(w, t);
        expect(cols * c + (cols - 1) * 8).toBeLessThanOrEqual(Math.max(w, t));
        expect(w - (cols * c + (cols - 1) * 8)).toBeLessThan(cols + 8);               // what is left over is only rounding
      }
    }
  });

  it("reads a drag as open or close only past the threshold and along the drawer's axis", () => {
    expect(dragIntent(3, 2, "left", false)).toBeNull();                                // a tap
    expect(dragIntent(30, 2, "left", false)).toBe("open");
    expect(dragIntent(-30, 2, "left", true)).toBe("close");
    expect(dragIntent(-30, 2, "right", false)).toBe("open");
    expect(dragIntent(30, 0, "right", true)).toBe("close");
    expect(dragIntent(0, -40, "bottom", false)).toBe("open");
    expect(dragIntent(0, 40, "bottom", true)).toBe("close");
    expect(dragIntent(30, 40, "left", false)).toBeNull();                              // mostly a scroll across the handle
    expect(dragIntent(-30, 0, "left", false)).toBeNull();                              // the wrong way for an open drawer's edge
  });

  it("keeps the preferences for the tab, and ignores what it does not know", () => {
    expect(loadPrefs("x")).toEqual(DEFAULT_PREFS);
    savePrefs("x", { ...DEFAULT_PREFS, focus: true, rail: false, railSide: "right", pinned: "inspect" });
    expect(loadPrefs("x")).toMatchObject({ focus: true, rail: false, railSide: "right", pinned: "inspect" });
    sessionStorage.setItem("jason-split-layout-y", JSON.stringify({ focus: "yes", railSide: "up", pinned: "elsewhere" }));
    expect(loadPrefs("y")).toEqual(DEFAULT_PREFS);
    sessionStorage.setItem("jason-split-layout-z", "{not json");
    expect(loadPrefs("z")).toEqual(DEFAULT_PREFS);
  });

  it("opens and docks the segments drawer by itself only on a big screen, and docks nothing on a narrow one", () => {
    expect(resolveLayout(DEFAULT_PREFS, { big: false, canPin: false })).toEqual({ railOpen: false, docked: null });
    expect(resolveLayout(DEFAULT_PREFS, { big: false, canPin: true })).toEqual({ railOpen: false, docked: null });
    expect(resolveLayout(DEFAULT_PREFS, { big: true, canPin: true })).toEqual({ railOpen: true, docked: "rail" });
    expect(resolveLayout({ ...DEFAULT_PREFS, rail: false }, { big: true, canPin: true }).railOpen).toBe(false);
    expect(resolveLayout({ ...DEFAULT_PREFS, pinned: "none" }, { big: true, canPin: true })).toEqual({ railOpen: true, docked: null });
    expect(resolveLayout({ ...DEFAULT_PREFS, pinned: "inspect" }, { big: false, canPin: false }).docked).toBeNull();
  });

  it("shows every chip up to a limit, and a run around the current one beyond it", () => {
    expect(stripWindow(10, 3)).toEqual({ from: 0, to: 10 });
    expect(stripWindow(1000, 0, 100)).toEqual({ from: 0, to: 100 });
    expect(stripWindow(1000, 500, 100)).toEqual({ from: 450, to: 550 });
    expect(stripWindow(1000, 999, 100)).toEqual({ from: 900, to: 1000 });
  });
});

describe("the segment strip and the drawers", () => {
  it("keeps the segments in a slim strip of numbered chips, and a chip jumps to its segment", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(10));
    await saved();
    const strip = screen.getByRole("navigation", { name: "Segments, as numbered chips" });
    const chips = within(strip).getAllByRole("button");
    expect(chips).toHaveLength(2);
    expect(chips[1]).toHaveAttribute("aria-current", "true");                        // page 10 has the focus
    expect(chips[1]).toHaveAccessibleName("Segment 2, p.10");
    await user.click(chips[0]);
    await waitFor(() => expect(chips[0]).toHaveAttribute("aria-current", "true"));
    expect(chips[1]).not.toHaveAttribute("aria-current");
  });

  it("opens the segments drawer on S and closes it on Esc, and gives the focus back to the page", async () => {
    const user = userEvent.setup();
    await openDemo();
    expect(drawer("Segments")).toBeNull();                                             // closed under 1400 px, with nothing built inside
    cell(4).focus();
    await user.keyboard("s");
    const d = await screen.findByRole("complementary", { name: "Segments" });
    expect(d).toHaveFocus();
    expect(within(d).getByRole("region", { name: "Segments" })).toBeInTheDocument();
    expect(layoutPrefs().rail).toBe(true);
    await user.keyboard("{Escape}");
    expect(drawer("Segments")).toBeNull();
    expect(cell(4)).toHaveFocus();
    expect(layoutPrefs().rail).toBe(false);
  });

  it("opens the compare drawer on C and on a double click, with the page before and steps to the next page", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(5).focus();
    await user.keyboard("c");
    const d = await screen.findByRole("complementary", { name: "Compare pages" });
    expect(within(d).getByText("The page before")).toBeInTheDocument();
    await user.click(within(d).getByRole("button", { name: "Next page" }));
    expect(within(d).getByText("Page 6 of 120")).toBeInTheDocument();
    await user.click(within(d).getByRole("button", { name: "Close" }));
    expect(drawer("Compare pages")).toBeNull();
    fireEvent.doubleClick(cell(9));
    const again = await screen.findByRole("complementary", { name: "Compare pages" });
    expect(within(again).getByText("Page 9 of 120")).toBeInTheDocument();
    await user.click(within(again).getByRole("button", { name: "Full screen" }));
    expect(again).toHaveAttribute("data-full");
    expect(layoutPrefs().inspectFull).toBe(true);
  });

  it("closes a drawer from its scrim, and opens it from its edge tab by a tap or by a drag past the threshold", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: /^Segments, 1\. Open/ }));
    expect(await screen.findByRole("complementary", { name: "Segments" })).toBeInTheDocument();
    await user.click(document.querySelector(".split-scrim")!);
    expect(drawer("Segments")).toBeNull();
    const tab = document.querySelector<HTMLElement>('.split-edgetab[data-for="rail"]')!;
    fireEvent.pointerDown(tab, { clientX: 5, clientY: 100 });
    fireEvent.pointerMove(tab, { clientX: 9, clientY: 101 });                          // under the threshold
    expect(drawer("Segments")).toBeNull();
    fireEvent.pointerMove(tab, { clientX: 40, clientY: 102 });
    expect(await screen.findByRole("complementary", { name: "Segments" })).toBeInTheDocument();
    // and back by a drag on its grip toward the edge
    const grip = within(screen.getByRole("complementary", { name: "Segments" })).getByRole("button", { name: /^Close the segments drawer/ });
    fireEvent.pointerDown(grip, { clientX: 200, clientY: 20 });
    fireEvent.pointerMove(grip, { clientX: 150, clientY: 21 });
    fireEvent.pointerUp(grip);
    await waitFor(() => expect(drawer("Segments")).toBeNull());
  });

  it("opens the review as a drawer, with the heading focused, and closes it on Esc unless a write is running", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(5));
    await saved();
    await user.click(screen.getAllByRole("button", { name: "Review and split" })[0]);
    const d = await screen.findByRole("complementary", { name: "Review and split" });
    expect(await within(d).findByRole("heading", { name: /^Review:/ })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(drawer("Review and split")).toBeNull();
  });
});

describe("pinning, focus, and what is shown", () => {
  it("pins a drawer open beside the pages when the screen is wide enough, and remembers it", async () => {
    screenIs({ pin: true });
    const user = userEvent.setup();
    await openDemo();
    await user.keyboard("{Escape}");
    cell(1).focus();
    await user.keyboard("s");
    const d = await screen.findByRole("complementary", { name: "Segments" });
    expect(document.querySelector(".split-stage")).not.toHaveAttribute("data-dock");
    await user.click(within(d).getByRole("button", { name: "Pin open" }));
    expect(document.querySelector(".split-stage")).toHaveAttribute("data-dock", "left");
    expect(d).toHaveAttribute("data-docked");
    expect(document.querySelector(".split-scrim")).toBeNull();                          // docked: the pages are not covered
    expect(layoutPrefs().pinned).toBe("rail");
    await user.click(within(d).getByRole("button", { name: "Unpin" }));
    expect(document.querySelector(".split-stage")).not.toHaveAttribute("data-dock");
  });

  it("docks nothing on a screen under 1200 px, and offers no pin there", async () => {
    screenIs({ pin: false });
    const user = userEvent.setup();
    await openDemo();
    cell(1).focus();
    await user.keyboard("s");
    const d = await screen.findByRole("complementary", { name: "Segments" });
    expect(within(d).queryByRole("button", { name: /Pin open|Unpin/ })).toBeNull();
  });

  it("opens and docks the segments drawer by default on a big screen", async () => {
    screenIs({ pin: true, big: true });
    await openDemo();
    const d = await screen.findByRole("complementary", { name: "Segments" });
    expect(d).toHaveAttribute("data-docked");
  });

  it("hides the console's chrome in focus mode on F, leaves it on Esc, and remembers the choice", async () => {
    const user = userEvent.setup();
    await openDemo();
    const root = document.documentElement;
    cell(2).focus();
    await user.keyboard("f");
    expect(root).toHaveAttribute("data-split-focus");
    expect(document.querySelector(".split-shell")).toHaveAttribute("data-focus");
    expect(screen.getByRole("button", { name: "Focus" })).toHaveAttribute("aria-pressed", "true");
    expect(layoutPrefs().focus).toBe(true);
    cell(2).focus();
    await user.keyboard("{Escape}");
    expect(root).not.toHaveAttribute("data-split-focus");
    expect(layoutPrefs().focus).toBe(false);
    await user.click(screen.getByRole("button", { name: "Focus" }));
    expect(root).toHaveAttribute("data-split-focus");
    cleanup();
    expect(root).not.toHaveAttribute("data-split-focus");                               // leaving the screen leaves focus mode
  });

  it("closes a drawer before it leaves focus mode on Esc", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(2).focus();
    await user.keyboard("f");
    await user.keyboard("c");
    expect(await screen.findByRole("complementary", { name: "Compare pages" })).toBeInTheDocument();
    cell(2).focus();
    await user.keyboard("{Escape}");
    expect(drawer("Compare pages")).toBeNull();
    expect(document.documentElement).toHaveAttribute("data-split-focus");
    cell(2).focus();
    await user.keyboard("{Escape}");
    expect(document.documentElement).not.toHaveAttribute("data-split-focus");
  });

  it("shows or hides the suggestions and the flags from the View menu", async () => {
    const user = userEvent.setup();
    await openDemo();
    expect(document.querySelector("[data-cell][data-sug]")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "View" }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: "Suggestions" }));
    expect(document.querySelector("[data-cell][data-sug]")).toBeNull();
    expect(layoutPrefs().showSuggestions).toBe(false);
    await user.click(screen.getByRole("button", { name: "View" }));
    expect(await screen.findByRole("menuitemcheckbox", { name: "Suggestions" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("menuitemcheckbox", { name: "Rejected suggestions" })).toHaveAttribute("aria-disabled", "true");
  });
});

describe("the toolbar and its menus", () => {
  it("has one tab stop, and the arrow keys, Home, and End move along it", async () => {
    const user = userEvent.setup();
    await openDemo();
    const bar = screen.getByRole("toolbar", { name: "Splitter controls" });
    const stops = () => Array.from(bar.querySelectorAll<HTMLElement>("[data-roving]")).filter((e) => e.tabIndex === 0 && !(e as HTMLButtonElement).disabled);
    expect(stops()).toHaveLength(1);
    const names = Array.from(bar.querySelectorAll<HTMLElement>("[data-roving]")).map((e) => e.textContent);
    expect(names.slice(0, 5).join("|")).toMatch(/^Draft.*\|View.*\|Mark.*\|Pages.*\|Help/);
    stops()[0].focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("button", { name: "View" })).toHaveFocus();
    expect(stops()).toEqual([screen.getByRole("button", { name: "View" })]);
    await user.keyboard("{End}");
    expect(screen.getAllByRole("button", { name: "Review and split" })[0]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("button", { name: "Draft" })).toHaveFocus();
  });

  it("opens a menu with the arrow keys, walks it, closes on Esc, and returns the focus to the button", async () => {
    const user = userEvent.setup();
    await openDemo();
    const mark = screen.getByRole("button", { name: "Mark" });
    mark.focus();
    expect(mark).toHaveAttribute("aria-haspopup", "menu");
    expect(mark).toHaveAttribute("aria-expanded", "false");
    await user.keyboard("{ArrowDown}");
    const menu = await screen.findByRole("menu", { name: "Mark" });
    expect(mark).toHaveAttribute("aria-expanded", "true");
    const items = within(menu).getAllByRole("menuitem");
    expect(items[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(items[2]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(items[0]).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(items[items.length - 1]).toHaveFocus();                                      // wraps
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(mark).toHaveFocus();
    expect(mark).toHaveAttribute("aria-expanded", "false");
  });

  it("goes to the next menu on Left and Right, and leaves the keys of the pages alone while a menu is open", async () => {
    const user = userEvent.setup();
    await openDemo();
    screen.getByRole("button", { name: "Mark" }).focus();
    await user.keyboard("{ArrowDown}");
    await screen.findByRole("menu", { name: "Mark" });
    await user.keyboard("{ArrowRight}");
    expect(await screen.findByRole("menu", { name: "Pages" })).toBeInTheDocument();
    expect(screen.queryByRole("menu", { name: "Mark" })).toBeNull();
    await user.keyboard("s");                                                           // the first letter, not the segments key
    expect(drawer("Segments")).toBeNull();
  });

  it("states the count of a bulk act in its item before it runs, and says why an act cannot run", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: "Mark" }));
    const menu = await screen.findByRole("menu", { name: "Mark" });
    expect(within(menu).getByRole("menuitem", { name: /^Accept \d+ at High confidence$/ })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /^Accept \d+ at Medium or better$/ })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "Clear all my marks (0)…" })).toHaveAttribute("aria-disabled", "true");
    await user.click(within(menu).getByRole("menuitem", { name: "Clear all my marks (0)…" }));   // refused: nothing opens
    expect(screen.queryByRole("dialog", { name: "Clear my marks" })).toBeNull();
    await user.keyboard("{Escape}");
    await user.click(cell(12));
    await saved();
    await user.click(screen.getByRole("button", { name: "Mark" }));
    await user.click(await screen.findByRole("menuitem", { name: "Clear all my marks (1)…" }));
    const panel = await screen.findByRole("dialog", { name: "Clear my marks" });
    expect(panel).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Clear my marks" })).toBeNull();
    expect(screen.getByRole("button", { name: "Mark" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Mark" }));
    await user.click(await screen.findByRole("menuitem", { name: "Clear all my marks (1)…" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Clear my marks" })).getByRole("button", { name: "Clear all my marks" }));
    expect(screen.getByText(/Remove all 1 of your starts/)).toBeInTheDocument();           // it asks first, and says what it will do
  });

  it("shows a choice as a check and as aria-checked, never as a colour alone", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: "View" }));
    const album = await screen.findByRole("menuitemradio", { name: "Album" });
    expect(album).toHaveAttribute("aria-checked", "true");
    expect(album).toHaveTextContent("✓");
    expect(screen.getByRole("menuitemradio", { name: "List" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("menuitemcheckbox", { name: "Scroll across" })).toHaveAttribute("aria-disabled", "true");
  });
});

describe("the phone", () => {
  it("has a bottom action bar and a single View menu, and its drawers are bottom sheets", async () => {
    screenIs({ phone: true });
    const user = userEvent.setup();
    await openDemo().catch(() => undefined);
    await screen.findByRole("toolbar", { name: "Actions" });
    const top = screen.getByRole("toolbar", { name: "Splitter controls" });
    expect(within(top).getAllByRole("button", { name: /^(Draft|View|Mark|Pages|Help)$/ }).map((b) => b.textContent)).toEqual(["View▾"]);
    const bar = screen.getByRole("toolbar", { name: "Actions" });
    expect(within(bar).getByRole("button", { name: "Mark" })).toBeInTheDocument();
    await user.click(within(bar).getByRole("button", { name: /^Segments \d/ }));
    const d = await screen.findByRole("complementary", { name: "Segments" });
    expect(d).toHaveAttribute("data-side", "bottom");
    expect(document.querySelector(".split-edgetab")).toBeNull();                          // the bar's buttons open them, not an edge tab
    await act(async () => { await user.click(within(bar).getByRole("button", { name: "Compare" })); });
    expect(drawer("Segments")).toBeNull();                                                // one sheet at a time on a phone
    expect(await screen.findByRole("complementary", { name: "Compare pages" })).toHaveAttribute("data-side", "bottom");
  });
});
