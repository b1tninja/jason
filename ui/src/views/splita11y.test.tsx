import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConsoleShell, type ConsoleScreen } from "../components/ConsoleShell";
import { resetServerSession } from "../lib/api";
import { SplitView, resetDemo } from "./SplitView";
import { countFrom } from "./SplitPanes";
import { demoFacts } from "./splitDemo";
import { GRID_HINT, cellLabel, cellNote, cellWords, type Suggestion } from "./splitModel";

// The splitter's accessibility, in the parts jsdom can check (docs/pdf-splitter-accessibility.md); the browser run is e2e/tests/a11y.spec.ts.

beforeEach(() => { resetServerSession(); resetDemo(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; document.title = ""; });

const cell = (page: number) => document.querySelector<HTMLElement>(`button.split-cell-btn[data-page="${page}"]`)!;
async function openDemo() {
  window.location.hash = "#/setup/split/demo";
  render(<SplitView />);
  await screen.findByRole("grid", { name: "Pages" });
  await waitFor(() => expect(cell(1)).toBeTruthy());
}
const saved = () => waitFor(() => expect(document.querySelector('[data-save="saved"]')).toBeTruthy());
const high: Suggestion = { id: "g1", page: 4, band: "High", score: 0.9, state: "open", signals: [], why: "x" } as unknown as Suggestion;

describe("a cell's words (D6, D10)", () => {
  it("names a cell with the words it shows, in the order it shows them, and nothing else", () => {
    const f = demoFacts(120);
    expect(cellLabel(1, f[0], 0, 1, undefined, false)).toBe("Page 1, Start 1, S1");
    expect(cellLabel(2, f[1], -1, 1, undefined, false)).toBe("Page 2, S1");
    expect(cellLabel(4, f[3], -1, 1, high, false)).toBe("Page 4, Suggested, High, S1");
    expect(cellLabel(9, f[8], -1, 1, undefined, false)).toBe("Page 9, Blank, S1");
    expect(cellLabel(10, f[9], 1, 2, undefined, false)).toBe("Page 10, Nested start, S2");
    expect(cellLabel(19, f[18], -1, 1, undefined, false, 90)).toBe("Page 19, Sideways, Turn 90°, S1");
    expect(cellLabel(5, undefined, -1, 0, undefined, false)).toBe("Page 5, Measuring…");
    expect(cellLabel(5, f[4], 0, 3, undefined, false, undefined, true)).toBe("Page 5, Start 3");     // a strip shows the number and the tag only
  });

  it("keeps the first line, the segment, and the keys out of the name: the description has them, and the keys are said once", () => {
    const f = demoFacts(120);
    const titled = f.find((x) => x.title)!;
    expect(cellLabel(titled.n, titled, -1, 1, undefined, false)).not.toMatch(/first line|Press|Enter/i);
    expect(cellNote(titled.n, titled, -1, 1, undefined, false)).toContain(`First line: ${titled.title}`);
    expect(cellNote(titled.n, titled, -1, 1, undefined, true)).not.toContain("First line");               // a confidential file's first line is never said
    expect(cellNote(1, f[0], 0, 1, undefined, false)).toMatch(/first page always starts a segment/);
    expect(cellNote(10, f[9], 0, 2, undefined, false)).toMatch(/Starts segment 2/);
    expect(GRID_HINT).toMatch(/Enter or Space marks/);
  });

  it("holds the shown words in the name: every word the cell draws is in what it is called", () => {
    const f = demoFacts(120);
    for (let n = 1; n <= 60; n++) {
      const fact = f[n - 1];
      for (const level of [-1, 0, 1]) for (const turn of [undefined, 180] as const) {
        const w = cellWords(fact, level, 2, level < 0 ? high : undefined, turn);
        const name = cellLabel(n, fact, level, 2, level < 0 ? high : undefined, false, turn);
        for (const word of [w.tag, w.sideways, w.state, w.turned, w.seg, w.measuring ? "Measuring…" : ""].filter(Boolean)) expect(name, `page ${n}`).toContain(word);
      }
    }
  });
});

describe("the grid", () => {
  it("is described once by the keys, names each row by its pages, gives each cell its column, and says the pressed state with aria-pressed", async () => {
    await openDemo();
    const grid = screen.getByRole("grid", { name: "Pages" });
    expect(grid).toHaveAccessibleDescription(GRID_HINT);
    const row = within(grid).getAllByRole("row")[1];
    expect(row.getAttribute("aria-label")).toMatch(/^Pages 1 to \d+$|^Page 1$/);
    expect(cell(1).closest("[role=gridcell]")).toHaveAttribute("aria-colindex", "1");
    expect(cell(2).closest("[role=gridcell]")).toHaveAttribute("aria-colindex", "2");
    expect(cell(1)).toHaveAttribute("aria-pressed", "true");
    expect(cell(2).getAttribute("aria-label")).not.toMatch(/Press|Enter/);
  });

  it("is a grid of one row in the filmstrip: the cells have a row, and each says its column", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: "View" }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Filmstrip" }));
    const strip = await screen.findByRole("grid", { name: "Pages, as a strip" });
    expect(strip).toHaveAttribute("aria-rowcount", "1");
    expect(strip).toHaveAttribute("aria-colcount", "120");
    const cells = within(strip).getAllByRole("gridcell");
    expect(cells.length).toBeGreaterThan(3);
    for (const c of cells) {
      expect(c.closest("[role=row]")).toBeTruthy();
      expect(c.getAttribute("aria-colindex")).toBe(c.dataset.page);
    }
  });

  it("names no drawer in aria-controls while the drawer is not there", async () => {
    const user = userEvent.setup();
    await openDemo();
    const compare = screen.getByRole("button", { name: /^Compare$/ });
    expect(compare).not.toHaveAttribute("aria-controls");
    await user.click(compare);
    await screen.findByRole("complementary", { name: "Compare pages" });
    expect(compare).toHaveAttribute("aria-controls", "split-drawer-inspect");
    expect(document.getElementById("split-drawer-inspect")).toBeTruthy();
    for (const e of Array.from(document.querySelectorAll("[aria-controls]"))) expect(document.getElementById(e.getAttribute("aria-controls")!), e.outerHTML.slice(0, 80)).toBeTruthy();
  });

  it("sets the page title from the screen and the draft, never from a file name", async () => {
    await openDemo();
    await waitFor(() => expect(document.title).toBe("Split document: Draft, 120 pages - jason"));
  });
});

describe("moving a start (D4)", () => {
  it("moves a start with ] again and again, the screen's focus going with it", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(10).focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(cell(10)).toHaveAttribute("aria-pressed", "true"));
    for (const to of [11, 12, 13]) {
      await user.keyboard("]");
      await waitFor(() => expect(cell(to)).toHaveAttribute("aria-pressed", "true"));
      await waitFor(() => expect(cell(to).getAttribute("tabindex")).toBe("0"));
    }
    expect(cell(10)).toHaveAttribute("aria-pressed", "false");
    expect(cell(12)).toHaveAttribute("aria-pressed", "false");
    await user.keyboard("[[");
    await waitFor(() => expect(cell(12)).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByText(/Page 12 of 120/)).toBeInTheDocument();
    await saved();
  });

  it("does not move the focus onto a page that already starts a segment", async () => {
    const user = userEvent.setup();
    await openDemo();
    for (const p of [10, 11]) { cell(p).focus(); await user.keyboard("{Enter}"); await waitFor(() => expect(cell(p)).toHaveAttribute("aria-pressed", "true")); }
    cell(10).focus();
    await user.keyboard("]");
    await waitFor(() => expect(screen.getByText("Page 11 already starts a segment.", { selector: ".split-live" })).toBeInTheDocument());
    expect(cell(10)).toHaveAttribute("aria-pressed", "true");
    expect(cell(10).getAttribute("tabindex")).toBe("0");
  });

  it("offers one page earlier, one page later, and a page number in the page menu, with words for a page that is not there", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(20).focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(cell(20)).toHaveAttribute("aria-pressed", "true"));
    fireEvent.contextMenu(cell(20));
    let menu = await screen.findByRole("dialog", { name: "Page 20" });
    await user.click(within(menu).getByRole("button", { name: /^Move this start one page later \(to page 21\)/ }));
    await waitFor(() => expect(cell(21)).toHaveAttribute("aria-pressed", "true"));
    expect(cell(20)).toHaveAttribute("aria-pressed", "false");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Page 20" })).toBeNull());
    fireEvent.contextMenu(cell(21));
    menu = await screen.findByRole("dialog", { name: "Page 21" });
    await user.click(within(menu).getByRole("button", { name: /^Move this start one page earlier \(to page 20\)/ }));
    await waitFor(() => expect(cell(20)).toHaveAttribute("aria-pressed", "true"));
    fireEvent.contextMenu(cell(20));
    menu = await screen.findByRole("dialog", { name: "Page 20" });
    const field = within(menu).getByLabelText("Move this start to page");
    await user.type(field, "500");
    await user.click(within(menu).getByRole("button", { name: "Move" }));
    expect(await within(menu).findByRole("alert")).toHaveTextContent("from 2 to 120");
    expect(field).toHaveAttribute("aria-invalid", "true");
    await user.clear(field);
    await user.type(field, "25");
    await user.click(within(menu).getByRole("button", { name: "Move" }));
    await waitFor(() => expect(cell(25)).toHaveAttribute("aria-pressed", "true"));
    expect(cell(20)).toHaveAttribute("aria-pressed", "false");
    await saved();
  });

  it("offers no move for the first page, a page that is not a start, or a draft that cannot be changed", async () => {
    await openDemo();
    fireEvent.contextMenu(cell(1));
    let menu = await screen.findByRole("dialog", { name: "Page 1" });
    expect(within(menu).queryByRole("button", { name: /^Move this start/ })).toBeNull();
    fireEvent.keyDown(menu, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    fireEvent.contextMenu(cell(30));
    menu = await screen.findByRole("dialog", { name: "Page 30" });
    expect(within(menu).queryByRole("button", { name: /^Move this start/ })).toBeNull();
  });
});

describe("dialogs hold the focus (D2, D3)", () => {
  it("keeps Tab and Shift Tab inside the keyboard map, brings back focus that lands outside, and returns it to the page on Escape", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(7).focus();
    await user.keyboard("?");
    const dialog = await screen.findByRole("dialog", { name: "Keyboard map" });
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
    for (let i = 0; i < 6; i++) { await user.tab(); expect(dialog.contains(document.activeElement), `Tab ${i}`).toBe(true); }
    await user.tab({ shift: true });
    expect(dialog.contains(document.activeElement)).toBe(true);
    cell(7).focus();                                                                    // something outside takes the focus
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(cell(7));
  });

  it("closes the keyboard map with Escape from outside the dialog, and by its Close button, and gives the focus back each time", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(7).focus();
    await user.keyboard("?");
    await screen.findByRole("dialog", { name: "Keyboard map" });
    fireEvent.keyDown(document.body, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(cell(7));
    await user.keyboard("?");
    await user.click(within(await screen.findByRole("dialog", { name: "Keyboard map" })).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(cell(7));
  });

  it("returns the focus to the Help menu's button when the map was opened from its menu", async () => {
    const user = userEvent.setup();
    await openDemo();
    const help = screen.getByRole("button", { name: "Help" });
    await user.click(help);
    await user.click(await screen.findByRole("menuitem", { name: /Keyboard map/ }));
    await screen.findByRole("dialog", { name: "Keyboard map" });
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(help);
  });

  it("returns the focus to the flags button that opened the flags dialog", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: /^Segments \d/ }));
    const more = await waitFor(() => { const b = document.querySelector<HTMLElement>(".split-flag-more"); expect(b).toBeTruthy(); return b!; });
    more.focus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: /^Flags for/ });
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(more);
  });
});

describe("the way past the navigation (D8)", () => {
  const SCREENS: ConsoleScreen[] = [{ id: "digest", label: "Board digest", group: "Overview" }, { id: "setup/split", label: "Split document", group: "Setup" }];
  const shell = (current: string) => render(
    <ConsoleShell wordmark="W" legal="L" groups={["Overview", "Setup"]} screens={SCREENS} current={current} onGo={vi.fn()} audience="board" onAudience={vi.fn()}>
      <div role="grid" aria-label="Pages" tabIndex={-1} /><p>body</p>
    </ConsoleShell>,
  );

  it("is the first control on a draft, named for the pages, and moves the focus to them without changing the route", async () => {
    window.location.hash = "#/setup/split/demo";
    shell("setup/split");
    const link = screen.getByRole("link", { name: "Skip to the pages" });
    expect(document.body.querySelector("a, button, input, select")).toBe(link);
    await userEvent.click(link);
    expect(document.activeElement).toBe(screen.getByRole("grid", { name: "Pages" }));
    expect(window.location.hash).toBe("#/setup/split/demo");
  });

  it("is named for the main column on the start page, and is not on the console's other screens", async () => {
    window.location.hash = "#/setup/split";
    const { unmount } = shell("setup/split");
    await userEvent.click(screen.getByRole("link", { name: "Skip to the main content" }));
    expect(document.activeElement).toBe(document.getElementById("console-main"));
    unmount();
    shell("digest");
    expect(screen.queryByRole("link", { name: /^Skip to/ })).toBeNull();
  });
});

describe("announcements (D9)", () => {
  it("does not read the save aloud: the save line is plain text, and the one polite region carries the act", async () => {
    const user = userEvent.setup();
    await openDemo();
    const save = document.querySelector("[data-save]")!;
    expect(save.closest("[aria-live], [role=status], [role=alert]")).toBeNull();
    cell(14).focus();
    await user.keyboard("{Enter}");
    await saved();
    expect(await screen.findByText("Page 14 now starts a segment.", { selector: ".split-live" })).toBeInTheDocument();
    expect(Array.from(document.querySelectorAll("[role=status]")).map((e) => e.textContent).join(" ")).not.toMatch(/\d{1,2}:\d{2}/);
  });
});

describe("a count out of range is corrected aloud (D16)", () => {
  it("keeps a value in range silent, and names the range and the value used otherwise", () => {
    expect(countFrom("3", 1, 500)).toEqual({ n: 3, note: "" });
    expect(countFrom("", 1, 500)).toEqual({ n: 1, note: "" });
    expect(countFrom("0", 1, 500)).toEqual({ n: 1, note: "Enter a whole number from 1 to 500. Using 1." });
    expect(countFrom("900", 1, 500).n).toBe(500);
    expect(countFrom("2.5", 1, 500).note).toMatch(/whole number/);
  });
});
