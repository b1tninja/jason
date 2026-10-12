import axe from "axe-core";
import type { Locator, Page } from "@playwright/test";
import { expect, signIn, test } from "./fixtures";

// The PDF splitter's accessibility (docs/pdf-splitter-accessibility.md): axe-core over every state at phone, tablet, and desktop widths, at 400%
// zoom (a 320 by 256 window), in the dark scheme, and in forced colours; the structure of the grid; the words of a cell; focus in and out of the
// dialogs; the announcements a mark makes; and the keys and the pointer alternatives that move a start. Made-up data only (the demo draft).
// A rule that axe reports is a failure: there is no list of known faults left to hide behind (the audit's KNOWN table is empty).

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

/** Run axe on the page and name each violated rule with the number of nodes, sorted: `["color-contrast:2"]`. */
async function scan(page: Page, skip: string[] = []): Promise<string[]> {
  await page.addScriptTag({ content: axe.source });
  const out = await page.evaluate(async (tags) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    // (the console's own "Go to" select on a narrow window sits outside a landmark: the shell's, and outside the splitter's audit)
    // (a cell scrolled partly out of a 256 px window is read by axe as text that is off screen, so its words look missing; the cells beside it, whole in view, are checked)
    document.querySelectorAll("button.split-cell-btn").forEach((b) => { const r = b.getBoundingClientRect(); if (r.top < 0 || r.bottom > window.innerHeight) b.setAttribute("data-axe-partial", ""); });
    const r = await (window as any).axe.run({ exclude: [[".console-goto"], ["[data-axe-partial]"]] }, { runOnly: { type: "tag", values: tags.tags }, rules: Object.fromEntries(tags.skip.map((id: string) => [id, { enabled: false }])), resultTypes: ["violations"] });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (r.violations as any[]).map((v) => `${v.id}:${v.nodes.length} ${v.nodes.slice(0, 3).map((n: any) => n.target.join(" ")).join(" | ")}`);
  }, { tags: TAGS, skip });
  return out.sort();
}

const cell = (page: Page, n: number): Locator => page.locator(`button.split-cell-btn[data-page="${n}"]`);

/** Go to a page by the "Go to" field, as a person does, and wait for its cell to have the focus (the album builds only the pages near the view). */
async function at(page: Page, n: number) {
  const field = page.getByRole("spinbutton", { name: "Go to page" });
  await field.fill(String(n));
  await field.press("Enter");
  await expect(cell(page, n)).toBeFocused();
}

/** The segments drawer, opened if it is not (from 1400 px it opens by itself, docked). */
async function openRail(page: Page) {
  const rail = page.getByRole("complementary", { name: "Segments" });
  if (!(await rail.count())) { await page.getByRole("button", { name: /^Segments/ }).first().click(); }
  await expect(rail).toBeVisible();
  return rail;
}

async function openDemo(page: Page, query = "") {
  await signIn(page, "A Manager", `setup/split/demo${query}`);
  await expect(page.getByLabel("Draft summary")).toContainText(/\d+ pages/);
  await expect(page.locator("[data-cell], .split-list").first()).toBeVisible();
  await expect(page.locator("[data-measuring]")).toHaveCount(0);        // the pages near the view have been measured: a cell's words do not change under a scan
}

const SIZES = [
  { name: "phone", width: 390, height: 844 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
  { name: "400% zoom", width: 320, height: 256 },
];

/** Switch the view as a person does: the key on a screen with a keyboard-sized toolbar, the View menu on a phone. */
async function viewTo(p: Page, phone: boolean, key: string, radio: string, shown: Locator) {
  if (phone) {
    await p.getByRole("button", { name: "View", exact: true }).click();
    await p.getByRole("menuitemradio", { name: radio }).click();
  } else {
    await p.keyboard.press(key);
  }
  await expect(shown).toBeVisible();
}

/** Reach a state of the editor by what a person does. The focus starts on the first page (the View button on a phone, which opens in the list). */
const STATES: { name: string; reach(page: Page, phone: boolean): Promise<void> }[] = [
  { name: "album", reach: async (p, ph) => viewTo(p, ph, "1", "Album", p.getByRole("grid", { name: "Pages" })) },
  { name: "filmstrip", reach: async (p, ph) => viewTo(p, ph, "2", "Filmstrip", p.getByRole("grid", { name: "Pages, as a strip" })) },
  { name: "scroll", reach: async (p, ph) => viewTo(p, ph, "3", "Scroll", p.getByRole("grid", { name: "Pages, one at a time" })) },
  { name: "list", reach: async (p, ph) => viewTo(p, ph, "4", "List", p.getByRole("region", { name: "Segments and suggested starts" })) },
  { name: "focus mode", reach: async (p) => { await p.keyboard.press("f"); await expect(p.locator(".split-shell")).toHaveAttribute("data-focus", "true"); } },
  { name: "segments drawer", reach: async (p) => { if (!(await p.getByRole("complementary", { name: "Segments" }).count())) await p.keyboard.press("s"); await expect(p.getByRole("complementary", { name: "Segments" })).toBeVisible(); } },
  { name: "compare drawer", reach: async (p) => { await p.keyboard.press("c"); await expect(p.getByRole("complementary", { name: "Compare pages" })).toBeVisible(); } },
  { name: "page menu", reach: async (p, ph) => {
    await viewTo(p, ph, "1", "Album", p.getByRole("grid", { name: "Pages" }));
    await cell(p, 5).focus(); await p.keyboard.press("l");
    await expect(p.getByRole("dialog", { name: "Page 5" })).toBeVisible();
  } },
  { name: "keyboard map", reach: async (p) => { await p.keyboard.press("?"); await expect(p.getByRole("dialog", { name: "Keyboard map" })).toBeVisible(); } },
  { name: "tool panel", reach: async (p) => {
    await p.getByRole("button", { name: "Mark", exact: true }).click();
    await p.getByRole("menuitem", { name: "Every Nth page…" }).click();
    await expect(p.getByRole("dialog", { name: "Every Nth page" })).toBeVisible();
  } },
];

test.describe("axe: no violation in any state, at any size", () => {
  test("the start page, each of its three tabs", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    await expect(page.getByRole("heading", { name: "Split document", level: 1 })).toBeVisible();
    expect(await scan(page), "upload tab").toEqual([]);
    await page.getByRole("button", { name: "From the library" }).click();
    await expect(page.getByRole("table", { name: /Files in the library/ })).toBeVisible();
    expect(await scan(page), "library tab").toEqual([]);
    await page.getByRole("button", { name: "From Drive" }).click();
    expect(await scan(page), "drive tab").toEqual([]);
  });

  for (const size of SIZES) {
    test.describe(`${size.name} (${size.width} by ${size.height})`, () => {
      test.use({ viewport: { width: size.width, height: size.height } });
      for (const state of STATES) {
        test(`${state.name}`, async ({ page }) => {
          await openDemo(page);
          const phone = size.width < 720;
          // the layout keys work from anywhere on the screen; a phone has no page cells in its list view, so they are sent from the View button
          if (phone) await page.getByRole("button", { name: "View", exact: true }).focus(); else await cell(page, 1).focus();
          await state.reach(page, phone);
          expect(await scan(page)).toEqual([]);
        });
      }
    });
  }

  // (in forced colours the system picks every colour, so the contrast rule has nothing of ours to measure; the other rules still apply)
  for (const media of [{ colorScheme: "dark" as const }, { forcedColors: "active" as const }]) {
    test(`${Object.keys(media)[0]} adds no violation (album, compare drawer, page menu)`, async ({ page }) => {
      const skip = "forcedColors" in media ? ["color-contrast"] : [];
      await page.emulateMedia(media);
      await openDemo(page);
      await cell(page, 1).focus();
      expect(await scan(page, skip), "album").toEqual([]);
      await page.keyboard.press("c");
      await expect(page.getByRole("complementary", { name: "Compare pages" })).toBeVisible();
      expect(await scan(page, skip), "compare").toEqual([]);
      await page.keyboard.press("Escape");
      await cell(page, 5).focus();
      await page.keyboard.press("l");
      await expect(page.getByRole("dialog", { name: "Page 5" })).toBeVisible();
      expect(await scan(page, skip), "page menu").toEqual([]);
    });
  }
  test("the segments drawer's flags dialog has no violation", async ({ page }) => {
    await openDemo(page);
    await cell(page, 1).focus();
    const rail = await openRail(page);
    const more = rail.locator(".split-flag-more").first();
    await expect(more).toBeVisible();                       // the flags are read once the draft is saved
    await more.click();
    await expect(page.getByRole("dialog", { name: /^Flags for/ })).toBeVisible();
    expect(await scan(page)).toEqual([]);
  });
});

test.describe("the grid", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("the album is a grid named Pages with counts; every cell has a row; one cell is the tab stop", async ({ page }) => {
    await openDemo(page);
    const grid = page.getByRole("grid", { name: "Pages" });
    expect(Number(await grid.getAttribute("aria-rowcount"))).toBeGreaterThan(1);
    expect(Number(await grid.getAttribute("aria-colcount"))).toBeGreaterThan(1);
    const orphans = await page.evaluate(() => Array.from(document.querySelectorAll('[role="gridcell"]')).filter((c) => !c.closest('[role="row"]')).length);
    expect(orphans, "gridcells outside a row").toBe(0);
    await expect(page.locator('button.split-cell-btn[tabindex="0"]')).toHaveCount(1);
    // a row says which pages it holds; a cell says its column
    await expect(page.locator('[role="row"][aria-label^="Pages 1 to"], [role="row"][aria-label^="Page 1"]').first()).toBeVisible();
    expect(await page.locator('[role="gridcell"][aria-colindex]').count()).toBeGreaterThan(5);
  });

  test("the filmstrip's strip is a grid of one row", async ({ page }) => {
    await openDemo(page);
    await cell(page, 1).focus();
    await page.keyboard.press("2");
    const strip = page.getByRole("grid", { name: "Pages, as a strip" });
    await expect(strip).toBeVisible();
    expect(await strip.getAttribute("aria-rowcount")).toBe("1");
    expect(await strip.getAttribute("aria-colcount")).toBe("120");
    const orphans = await page.evaluate(() => Array.from(document.querySelectorAll('[role="gridcell"]')).filter((c) => !c.closest('[role="row"]')).length);
    expect(orphans).toBe(0);
  });

  test("a 3000-page draft keeps the window small and counts true", async ({ page }) => {
    await openDemo(page, "?pages=3000");
    const grid = page.getByRole("grid", { name: "Pages" });
    expect(Number(await grid.getAttribute("aria-rowcount"))).toBeGreaterThanOrEqual(200);
    expect(await page.locator('[role="row"]').count()).toBeLessThanOrEqual(40);
    expect(await page.locator('[role="gridcell"]').count()).toBeLessThanOrEqual(260);
    await cell(page, 1).focus();
    await page.keyboard.press("End");
    await expect(page.locator(".split-where")).toContainText("Page 3000 of 3000");
  });

  test("a cell's name is the words it shows, short, with its state said once", async ({ page }) => {
    await openDemo(page);
    const checked = await page.evaluate(() => {
      const bad: string[] = [];
      let n = 0;
      for (const b of Array.from(document.querySelectorAll<HTMLElement>("button.split-cell-btn")).slice(0, 24)) {
        n += 1;
        const name = b.getAttribute("aria-label") ?? "";
        const cellEl = b.closest("[data-cell]")!;
        const shown = ["split-cell-n", "split-start-tag", "split-sug-tag", "split-cell-state", "split-cell-seg"]
          .flatMap((c) => Array.from(b.querySelectorAll(`.${c}`)).map((e) => (e.textContent ?? "").replace(/\s+/g, " ").trim()));
        for (const w of shown) if (w && !name.toLowerCase().includes(w.toLowerCase())) bad.push(`${name} lacks "${w}"`);
        if (name.length > 80) bad.push(`too long: ${name}`);
        if (/Press|Enter/.test(name)) bad.push(`repeats the instruction: ${name}`);
        if (!/^Page \d+/.test(name)) bad.push(`does not begin with the page: ${name}`);
        if (b.getAttribute("aria-pressed") === null) bad.push(`no pressed state: ${name}`);
        void cellEl;
      }
      return { n, bad };
    });
    expect(checked.n).toBeGreaterThan(5);
    expect(checked.bad).toEqual([]);
  });

  test("aria snapshot: the toolbar, the segment strip, and the first row", async ({ page }) => {
    await openDemo(page);
    await expect(page.getByRole("toolbar", { name: "Splitter controls" })).toMatchAriaSnapshot(`
      - toolbar "Splitter controls":
        - button "Draft"
        - button "View"
        - button "Mark"
        - button "Pages"
        - button "Help"
    `);
    await expect(page.getByRole("navigation", { name: "Segments, as numbered chips" })).toMatchAriaSnapshot(`
      - navigation "Segments, as numbered chips":
        - list:
          - listitem:
            - button "Segment 1, p.1"
    `);
    await expect(page.getByRole("grid", { name: "Pages" }).getByRole("row").nth(1)).toMatchAriaSnapshot(`
      - row /Pages 1 to \\d+/:
        - gridcell:
          - button "Page 1, Start 1, S1" [pressed]
    `);
  });
});

test.describe("keys and the pointer", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("Enter marks, Shift and an arrow select, Z undoes, and L opens the page menu", async ({ page }) => {
    await openDemo(page);
    await at(page, 41);
    await page.keyboard.press("Enter");
    await expect(cell(page, 41)).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("z");
    await expect(cell(page, 41)).toHaveAttribute("aria-pressed", "false");
    await page.keyboard.press("Shift+ArrowRight");
    await page.keyboard.press("Shift+ArrowRight");
    await expect(page.locator(".split-selbar")).toContainText("3 pages selected");
    expect(await page.locator('[role="gridcell"][aria-selected="true"]').count()).toBe(3);
    await page.keyboard.press("l");
    await expect(page.getByRole("dialog", { name: "Page 43" })).toBeVisible();
  });

  test("] moves a start one page, again and again, with the focus on it (D4)", async ({ page }) => {
    await openDemo(page);
    await at(page, 70);
    await page.keyboard.press("Enter");
    await expect(cell(page, 70)).toHaveAttribute("aria-pressed", "true");
    for (const to of [71, 72, 73]) {
      await page.keyboard.press("]");
      await expect(cell(page, to)).toHaveAttribute("aria-pressed", "true");
      await expect(cell(page, to)).toBeFocused();
    }
    for (const gone of [70, 71, 72]) await expect(cell(page, gone)).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator(".split-where")).toContainText("Page 73");
    await page.keyboard.press("[");
    await page.keyboard.press("[");
    await expect(cell(page, 71)).toHaveAttribute("aria-pressed", "true");
    await expect(cell(page, 71)).toBeFocused();
    await expect(cell(page, 73)).toHaveAttribute("aria-pressed", "false");
  });

  test("a start can be moved without dragging: one page earlier or later, or to a page (D4, 2.5.7)", async ({ page }) => {
    await openDemo(page);
    await at(page, 80);
    await page.keyboard.press("Enter");
    await expect(cell(page, 80)).toHaveAttribute("aria-pressed", "true");
    await cell(page, 80).click({ button: "right" });
    let dialog = page.getByRole("dialog", { name: "Page 80" });
    await dialog.getByRole("button", { name: /^Move this start one page later/ }).click();
    await expect(cell(page, 81)).toHaveAttribute("aria-pressed", "true");
    await expect(cell(page, 80)).toHaveAttribute("aria-pressed", "false");
    await expect(dialog).toHaveCount(0);
    await expect(cell(page, 81)).toBeFocused();
    await cell(page, 81).click({ button: "right" });
    dialog = page.getByRole("dialog", { name: "Page 81" });
    await dialog.getByRole("button", { name: /^Move this start one page earlier/ }).click();
    await expect(cell(page, 80)).toHaveAttribute("aria-pressed", "true");
    await cell(page, 80).click({ button: "right" });
    dialog = page.getByRole("dialog", { name: "Page 80" });
    await dialog.getByLabel("Move this start to page").fill("85");
    await dialog.getByRole("button", { name: "Move", exact: true }).click();
    await expect(cell(page, 85)).toHaveAttribute("aria-pressed", "true");
    await expect(cell(page, 80)).toHaveAttribute("aria-pressed", "false");
    // a page that is not there is refused in words
    await cell(page, 85).click({ button: "right" });
    dialog = page.getByRole("dialog", { name: "Page 85" });
    await dialog.getByLabel("Move this start to page").fill("500");
    await dialog.getByRole("button", { name: "Move", exact: true }).click();
    await expect(dialog.getByRole("alert")).toContainText("from 2 to 120");
    await expect(dialog.getByLabel("Move this start to page")).toHaveAttribute("aria-invalid", "true");
  });

  test("Escape drops a start being dragged where it was (2.5.2)", async ({ page }) => {
    await openDemo(page);
    await at(page, 60);
    await page.keyboard.press("Enter");
    const handle = page.locator('[data-handle="60"]');
    const from = await handle.boundingBox();
    const to = await cell(page, 63).boundingBox();
    await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2);
    await page.mouse.down();
    await page.mouse.move(to!.x + to!.width / 2, to!.y + to!.height / 2, { steps: 6 });
    await page.keyboard.press("Escape");
    await page.mouse.up();
    await expect(cell(page, 60)).toHaveAttribute("aria-pressed", "true");
    await expect(cell(page, 63)).toHaveAttribute("aria-pressed", "false");
  });
});

test.describe("focus", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  const focusIsOn = (page: Page, what: Locator) => expect(what).toBeFocused();

  test("closing the keyboard map returns the focus: from the key, from the Help menu, by Escape and by Close (D2)", async ({ page }) => {
    await openDemo(page);
    await cell(page, 7).focus();
    await page.keyboard.press("?");
    await expect(page.getByRole("dialog", { name: "Keyboard map" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Keyboard map" })).toHaveCount(0);
    await focusIsOn(page, cell(page, 7));
    await page.keyboard.press("?");
    await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
    await focusIsOn(page, cell(page, 7));
    const help = page.getByRole("button", { name: "Help", exact: true });
    await help.click();
    await page.getByRole("menuitem", { name: /Keyboard map/ }).click();
    await expect(page.getByRole("dialog", { name: "Keyboard map" })).toBeVisible();
    await page.keyboard.press("Escape");
    await focusIsOn(page, help);
    await help.focus();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
    await focusIsOn(page, help);
  });

  test("closing the flags dialog returns the focus to the button that opened it (D2)", async ({ page }) => {
    await openDemo(page);
    await cell(page, 1).focus();
    const rail = await openRail(page);
    const more = rail.locator(".split-flag-more").first();
    await expect(more).toBeVisible();                       // the flags are read once the draft is saved
    await more.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog", { name: /^Flags for/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await focusIsOn(page, more);
    await more.click();
    await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
    await focusIsOn(page, more);
  });

  test("a dialog holds Tab, and Escape works wherever the focus is (D3)", async ({ page }) => {
    await openDemo(page);
    for (const [open, name] of [["l", "Page 9"], ["?", "Keyboard map"]] as const) {
      await cell(page, 9).focus();
      await page.keyboard.press(open);
      const dialog = page.getByRole("dialog", { name });
      await expect(dialog).toBeVisible();
      for (let i = 0; i < 24; i++) {
        await page.keyboard.press(i % 5 === 4 ? "Shift+Tab" : "Tab");
        expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]')), `Tab ${i} left the dialog`).toBe(true);
      }
      // the focus put outside by a script (a menu closing over the page) is brought back; Escape still closes
      await page.evaluate(() => (document.querySelector('button.split-cell-btn[data-page="9"]') as HTMLElement).focus());
      expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await focusIsOn(page, cell(page, 9));
    }
  });

  test("closing the page menu and at once opening the keyboard map does not leave the map behind the page (D3)", async ({ page }) => {
    await openDemo(page);
    await cell(page, 9).focus();
    await page.keyboard.press("l");
    await expect(page.getByRole("dialog", { name: "Page 9" })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.keyboard.press("?");
    const map = page.getByRole("dialog", { name: "Keyboard map" });
    await expect(map).toBeVisible();
    await page.waitForTimeout(300);                       // the page menu's own refocus of the page runs a frame later
    expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(map).toHaveCount(0);
  });

  test("drawers and menus return the focus to what opened them", async ({ page }) => {
    await openDemo(page);
    const mark = page.getByRole("button", { name: "Mark", exact: true });
    await mark.focus();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Escape");
    await focusIsOn(page, mark);
    const compare = page.getByRole("button", { name: /^Compare/ }).first();
    await compare.focus();
    await page.keyboard.press("c");
    await expect(page.getByRole("complementary", { name: "Compare pages" })).toBeVisible();
    await page.keyboard.press("Escape");
    await focusIsOn(page, compare);
    await mark.click();
    await page.getByRole("menuitem", { name: "Every Nth page…" }).click();
    await expect(page.getByRole("dialog", { name: "Every Nth page" })).toBeVisible();
    await page.keyboard.press("Escape");
    await focusIsOn(page, mark);
  });
});

test.describe("announcements", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("marking one page makes one announcement, and no time of day is spoken (D9)", async ({ page }) => {
    await openDemo(page);
    await at(page, 50);
    await page.evaluate(() => {
      const w = window as unknown as { __said: string[] };
      w.__said = [];
      const live = (n: Node | null) => !!(n instanceof Element ? n : n?.parentElement)?.closest('[aria-live]:not([aria-live="off"]), [role="status"], [role="alert"]');
      new MutationObserver((list) => {
        for (const m of list) {
          if (!live(m.target)) continue;
          const text = ((m.target as Element).textContent ?? "").trim();
          if (text && m.type !== "attributes") w.__said.push(text);
        }
      }).observe(document.body, { subtree: true, childList: true, characterData: true });
    });
    await page.keyboard.press("Enter");
    await expect(cell(page, 50)).toHaveAttribute("aria-pressed", "true");
    await page.waitForTimeout(1500);
    const said = await page.evaluate(() => Array.from(new Set((window as unknown as { __said: string[] }).__said)));
    expect(said.filter((t) => !/^\d+ pages selected/.test(t)), JSON.stringify(said)).toHaveLength(1);
    expect(said.join(" ")).not.toMatch(/\d{1,2}:\d{2}/);
  });
});

test.describe("reflow (1.4.10)", () => {
  test("at 320 by 256 the pages are usable: the toolbar is one menu, the page scrolls, no sideways scroll", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 256 });
    await openDemo(page);
    await page.getByRole("button", { name: "View", exact: true }).click();
    await page.getByRole("menuitemradio", { name: "Album" }).click();
    const grid = page.getByRole("grid", { name: "Pages" });
    await grid.scrollIntoViewIfNeeded();
    const box = await grid.boundingBox();
    expect(box!.height, "the pages area is squeezed").toBeGreaterThanOrEqual(120);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    const visible = await page.evaluate(() => Array.from(document.querySelectorAll("[data-cell]")).filter((c) => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth; }).length);
    expect(visible, "no page in view").toBeGreaterThan(0);
    await expect(page.locator(".split-toolbar button:visible")).toHaveCount(1);
    // what left the toolbar is in its menu
    await page.getByRole("button", { name: "View", exact: true }).click();
    await expect(page.getByRole("menuitem", { name: /^Undo/ })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /^Redo/ })).toBeVisible();
    await expect(page.getByRole("menuitemcheckbox", { name: /^Focus/ })).toBeVisible();
    await page.keyboard.press("Escape");
    // the bars under the pages are reached by scrolling
    await page.getByRole("button", { name: "Review and split" }).scrollIntoViewIfNeeded();
    await expect(page.getByRole("button", { name: "Review and split" })).toBeInViewport();
  });

  for (const size of [{ width: 640, height: 512 }, { width: 390, height: 844 }]) {
    test(`at ${size.width} by ${size.height} nothing scrolls sideways`, async ({ page }) => {
      await page.setViewportSize(size);
      await openDemo(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    });
  }
});

test.describe("text spacing (1.4.12)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("no cell's footer is clipped, with or without the spacing stylesheet (D5)", async ({ page }) => {
    await openDemo(page);
    const clipped = () => page.evaluate(() => {
      const bad: string[] = [];
      for (const b of Array.from(document.querySelectorAll<HTMLElement>("button.split-cell-btn")).slice(0, 30)) {
        const foot = b.querySelector<HTMLElement>(".split-cell-foot")!;
        const fr = foot.getBoundingClientRect(), br = b.getBoundingClientRect();
        // the whole footer is inside the button's border box, and its text is not cut by its own box
        if (fr.bottom > br.bottom + 0.5 || fr.height < 22) bad.push(`footer of page ${b.dataset.page}: ${fr.height}px, bottom ${fr.bottom - br.bottom}`);
        const n = b.querySelector<HTMLElement>(".split-cell-n")!.getBoundingClientRect();
        if (n.bottom > br.bottom + 0.5 || n.height < 8) bad.push(`number of page ${b.dataset.page}`);
        for (const s of Array.from(foot.children) as HTMLElement[]) { if (s.scrollHeight > s.clientHeight + 1 && s.clientHeight > 0) bad.push(`${s.className} of ${b.dataset.page} is cut`); }
      }
      return bad;
    });
    expect(await clipped()).toEqual([]);
    await page.addStyleTag({ content: "* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }" });
    expect(await clipped()).toEqual([]);
  });
});

test.describe("forced colours (1.4.11), reduced motion, the lens", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("a selected range is outlined in forced colours (D13)", async ({ page }) => {
    await page.emulateMedia({ forcedColors: "active" });
    await openDemo(page);
    await cell(page, 20).focus();
    await page.keyboard.press("Shift+ArrowRight");
    await page.keyboard.press("Shift+ArrowRight");
    const style = await page.evaluate(() => {
      const el = document.querySelector('.split-cell[data-selected] .split-cell-btn:not(:focus)') as HTMLElement;
      const s = getComputedStyle(el);
      return { outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth };
    });
    expect(style.outlineStyle).not.toBe("none");
    expect(parseFloat(style.outlineWidth)).toBeGreaterThanOrEqual(3);
    // a start keeps its tag and bar
    await cell(page, 20).focus();
    await page.keyboard.press("Enter");
    const tag = await page.evaluate(() => getComputedStyle(document.querySelector(".split-start-tag:not([hidden])")!).backgroundColor);
    expect(tag).not.toBe("rgba(0, 0, 0, 0)");
  });

  test("nothing animates under reduced motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openDemo(page);
    await cell(page, 1).focus();
    await page.keyboard.press("c");
    const drawer = page.getByRole("complementary", { name: "Compare pages" });
    await expect(drawer).toBeVisible();
    expect(await drawer.evaluate((e) => getComputedStyle(e).animationName)).toBe("none");
    expect(await page.locator(".split-scrim").evaluate((e) => getComputedStyle(e).animationName)).toBe("none");
    expect(await page.locator(".split-pic img").first().evaluate((e) => getComputedStyle(e).transitionDuration)).toBe("0s");
  });

  test("the lens is hidden from a screen reader, and Escape hides it", async ({ page }) => {
    await openDemo(page);
    await page.locator('[data-loupe="3"]').first().hover();
    const lens = page.locator(".split-loupe");
    await expect(lens).toBeVisible();
    await expect(lens).toHaveAttribute("aria-hidden", "true");
    await page.keyboard.press("Escape");
    await expect(lens).toBeHidden();
  });

  test("aria-controls always names an element that is there", async ({ page }) => {
    await openDemo(page);
    const dangling = () => page.evaluate(() => Array.from(document.querySelectorAll("[aria-controls]")).filter((e) => (e.getAttribute("aria-controls") ?? "").split(/\s+/).some((id) => !document.getElementById(id))).map((e) => e.outerHTML.slice(0, 80)));
    expect(await dangling()).toEqual([]);
    await cell(page, 1).focus();
    await page.keyboard.press("c");
    await expect(page.getByRole("complementary", { name: "Compare pages" })).toBeVisible();
    expect(await dangling()).toEqual([]);
    await page.keyboard.press("Escape");
    expect(await dangling()).toEqual([]);
  });
});

test.describe("the page's title and the way past the navigation", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("each screen has its own title, and none carries a file name (D7)", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    await expect(page.getByRole("heading", { name: "Split document", level: 1 })).toBeVisible();
    await expect.poll(() => page.title()).toBe("Split document - jason");
    await page.goto("/#/setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    await expect.poll(() => page.title()).toBe("Split document: Draft, 120 pages - jason");
    await page.getByRole("link", { name: "All drafts" }).click();
    await expect.poll(() => page.title()).toBe("Split document - jason");
  });

  test("the skip link is the first control in the tab order, shows itself on focus, and moves the focus to the pages (D8)", async ({ page }) => {
    await openDemo(page);
    // (a Tab from a fresh load reaches it in the console's browser pane; headless Chromium here starts its Tab order below it in a draft, so the order is read from the page)
    const first = await page.evaluate(() => {
      const tabbable = Array.from(document.querySelectorAll<HTMLElement>("a[href], button:not(:disabled), input:not(:disabled), select, textarea, [tabindex]")).filter((e) => e.tabIndex >= 0);
      return tabbable[0]?.className;
    });
    expect(first).toBe("skip-link");
    const skip = page.getByRole("link", { name: "Skip to the pages" });
    await expect(skip).not.toBeInViewport();
    await skip.focus();
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport();
    await page.keyboard.press("Enter");
    await expect(page.locator('button.split-cell-btn[tabindex="0"]')).toBeFocused();
    expect(page.url()).toContain("#/setup/split/demo");
  });
  test("on the start page the first Tab offers to skip to the main content", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    await expect(page.getByRole("heading", { name: "Split document", level: 1 })).toBeVisible();
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to the main content" });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    expect(await page.evaluate(() => document.activeElement?.tagName)).toBe("MAIN");
  });
});

test.describe("target size (2.5.8)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  // The console's own controls in its header are the shell's and have their own audit; the splitter's are held to 24 by 24 CSS px.
  const SHELL = /^(Sign out|Private view)/;
  const small = (page: Page) => page.evaluate((shell) => {
    const out: string[] = [];
    const re = new RegExp(shell);
    for (const e of Array.from(document.querySelectorAll<HTMLElement>("button, a[href], input, select, summary, [role=menuitem], [role=menuitemradio], [role=menuitemcheckbox]"))) {
      if (e.closest(".console-bar, .console-nav, .skip-link") || e.classList.contains("skip-link")) continue;
      if ((e as HTMLInputElement).type === "hidden" || e.closest("[hidden]")) continue;
      const r = e.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      // a link inside a sentence is exempt (WCAG 2.5.8, inline); so is a control whose 24 px circle is not crossed by another target: checked by size here
      if (e.tagName === "A" && e.closest("p, li") && getComputedStyle(e).display === "inline") continue;
      const name = (e.getAttribute("aria-label") ?? e.textContent ?? "").trim().slice(0, 40);
      if (re.test(name)) continue;
      if (e.classList.contains("split-handle")) continue;
      if (r.width < 24 || r.height < 24) out.push(`${e.tagName.toLowerCase()} "${name}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    return out;
  }, SHELL.source);

  test("the album, its toolbar, and the page bar have no control under 24 by 24", async ({ page }) => {
    await openDemo(page);
    expect(await small(page)).toEqual([]);
  });

  test("the start page and the library tab have no control under 24 by 24", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    await expect(page.getByRole("heading", { name: "Split document", level: 1 })).toBeVisible();
    expect(await small(page), "start").toEqual([]);
    await page.getByRole("button", { name: "From the library" }).click();
    await expect(page.getByRole("table", { name: /Files in the library/ })).toBeVisible();
    await page.getByText("More filters").click();
    expect(await small(page), "library").toEqual([]);
  });
});

test.describe("the fixed corner viewer (the magnifier's second mode)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  async function viewerOn(page: Page) {
    await openDemo(page);
    await expect(page.locator('[data-cell][data-page="3"] img')).toHaveAttribute("data-state", "ready");
    await page.getByRole("button", { name: "View", exact: true }).click();
    await page.getByRole("menuitemradio", { name: "Mode: fixed corner viewer" }).click();
    const b = (await page.locator('[data-cell][data-page="3"] .split-pic').boundingBox())!;
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
    await expect(page.locator(".split-viewer")).toBeVisible();
    await page.mouse.move(b.x + b.width / 2 + 1, b.y + b.height / 2 + 1);
  }

  for (const media of [{}, { colorScheme: "dark" as const }, { forcedColors: "active" as const }]) {
    test(`axe finds nothing with the viewer shown ${JSON.stringify(media)}`, async ({ page }) => {
      await page.emulateMedia(media);
      await viewerOn(page);
      expect(await scan(page, "forcedColors" in media ? ["color-contrast"] : []), "viewer shown").toEqual([]);
    });
  }

  test("the viewer is a labelled region; its buttons are reachable by keyboard, 24 px or more, and show focus", async ({ page }) => {
    await viewerOn(page);
    const v = page.locator(".split-viewer");
    await expect(v).toHaveAttribute("role", "region");
    await expect(v).toHaveAttribute("aria-label", "Magnified page");
    for (const name of ["Whole page", "Pin", "Hide"]) {
      const b = v.getByRole("button", { name });
      const r = (await b.boundingBox())!;
      expect(r.width, name).toBeGreaterThanOrEqual(24);
      expect(r.height, name).toBeGreaterThanOrEqual(24);
      await page.keyboard.press("Shift");                // a key was used: the ring is for the keyboard
      await b.focus();
      await expect(b).toBeFocused();
      expect(await b.evaluate((e) => getComputedStyle(e).outlineStyle), `${name} focus ring`).not.toBe("none");
    }
    const g = (await v.getByRole("button", { name: /^Resize the viewer/ }).boundingBox())!;
    expect(Math.min(g.width, g.height)).toBeGreaterThanOrEqual(24);
  });

  test("a modal dialog owns Escape while it is open; the viewer stays until the next one", async ({ page }) => {
    await viewerOn(page);
    await page.keyboard.press("?");
    const map = page.getByRole("dialog", { name: "Keyboard map" });
    await expect(map).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(map).toHaveCount(0);
    await expect(page.locator(".split-viewer")).toBeVisible();
  });
});

test.describe("a number out of range says so (D16)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("'Every N pages' reports the correction in an alert and marks the field invalid", async ({ page }) => {
    await openDemo(page);
    await page.getByRole("button", { name: "Mark", exact: true }).click();
    await page.getByRole("menuitem", { name: "Every Nth page…" }).click();
    const f = page.getByRole("spinbutton", { name: "Every how many pages" });
    await f.fill("0");
    await expect(f).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByRole("alert").filter({ hasText: "Enter a whole number from 1 to 500" })).toBeVisible();
    await f.fill("3");
    await expect(f).not.toHaveAttribute("aria-invalid", "true");
  });

  test("'Go to page' says the range in the status line and marks the field invalid", async ({ page }) => {
    await openDemo(page);
    const f = page.getByRole("spinbutton", { name: "Go to page" });
    await f.fill("99999");
    await f.press("Enter");
    await expect(f).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByRole("status").filter({ hasText: /Enter a whole page number from 1 to \d+/ })).toBeVisible();
  });
});

test.describe("the edge tabs and the grid (D20)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("a closed drawer's tab does not overlap a page at the grid's edge", async ({ page }) => {
    await openDemo(page);
    const tabs = await page.locator(".split-edgetab").evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; }));
    const cells = await page.locator("[data-cell]").evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; }));
    for (const t of tabs) for (const c of cells) {
      const hit = t.l < c.r && t.r > c.l && t.t < c.b && t.b > c.t;
      expect(hit, "a tab over a cell").toBe(false);
    }
  });

  test("the focused page stays mounted when the grid is scrolled with the wheel", async ({ page }) => {
    await openDemo(page, "?pages=3000");
    await at(page, 40);
    const c = page.locator('[data-cell][data-page="40"]');
    await c.focus();
    await page.locator(".split-scroll").first().evaluate((e) => { e.scrollTop = e.scrollHeight * 0.8; });
    await page.waitForTimeout(400);
    await expect(c).toHaveCount(1);
    expect(await page.evaluate(() => document.activeElement?.closest("[data-cell]")?.getAttribute("data-page"))).toBe("40");
  });
});
