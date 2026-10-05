import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Tabs, type TabSpec } from "./Tabs";

const five: TabSpec[] = ["Setup", "Find", "Documents", "Accounts", "Gaps"].map((label) => ({ id: label.toLowerCase(), label, content: `${label} panel` }));

function Controlled({ initial = "setup" }: { initial?: string }) {
  const [active, setActive] = useState(initial);
  return <Tabs tabs={five} active={active} onChange={setActive} />;
}

describe("Tabs: keys", () => {
  it("keeps only the selected tab in the Tab order", () => {
    render(<Controlled initial="find" />);
    expect(screen.getAllByRole("tab").map((t) => t.tabIndex)).toEqual([-1, 0, -1, -1, -1]);
  });

  it("moves with Left and Right (wrapping), Home and End, selecting and focusing the tab it reaches", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    await user.click(screen.getByRole("tab", { name: "Setup" }));
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Find" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Find" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Find panel");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Gaps" })).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Setup" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Gaps" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Setup" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Setup panel");
  });
});

describe("Tabs: a row wider than its column", () => {
  // jsdom lays nothing out: the row is 300px wide, each tab 100px with 20px between, and the row's content 580px.
  const scrolled = new WeakMap<Element, number>();
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollLeft", {
      configurable: true,
      get() { return scrolled.get(this) ?? 0; },
      set(v: number) { scrolled.set(this, Math.max(0, Math.min(280, v))); },
    });
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", { configurable: true, get() { return this.getAttribute("role") === "tablist" ? 580 : 0; } });
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get() { return this.getAttribute("role") === "tablist" ? 300 : 0; } });
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      const list = this.closest('[role="tablist"]') as HTMLElement | null;
      if (this.getAttribute("role") === "tablist") return { left: 0, right: 300, top: 0, bottom: 40, width: 300, height: 40, x: 0, y: 0, toJSON() {} } as DOMRect;
      const i = list ? Array.from(list.children).indexOf(this) : 0;
      const left = i * 120 - (list?.scrollLeft ?? 0);
      return { left, right: left + 100, top: 0, bottom: 40, width: 100, height: 40, x: left, y: 0, toJSON() {} } as DOMRect;
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    for (const p of ["scrollLeft", "scrollWidth", "clientWidth"]) delete (HTMLElement.prototype as unknown as Record<string, unknown>)[p];
  });

  it("scrolls the row, not the page, to show the selected tab when it changes", async () => {
    const user = userEvent.setup();
    const pageScroll = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<Controlled />);
    const row = screen.getByRole("tablist");
    expect(row.scrollLeft).toBe(0); // Setup is in view already
    await user.click(screen.getByRole("tab", { name: "Setup" }));
    await user.keyboard("{End}"); // Gaps sits at 480–580: the row scrolls by 580 - 300 + 16, held to its 280 of overflow
    expect(row.scrollLeft).toBe(280);
    await user.keyboard("{Home}");
    expect(row.scrollLeft).toBe(0);
    expect(pageScroll).not.toHaveBeenCalled();
  });

  it("shows a selected tab that starts out of view", () => {
    render(<Controlled initial="accounts" />); // Accounts sits at 360–460
    expect(screen.getByRole("tablist").scrollLeft).toBe(460 - 300 + 16);
  });
});
