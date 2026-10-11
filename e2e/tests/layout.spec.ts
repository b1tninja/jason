import { expect, signIn, test } from "./fixtures";

// The splitter's layout on a phone, a tablet, and a desktop (docs/pdf-splitter.md, 5.9), on the made-up demo draft: no horizontal
// overflow, a focus mode that fills the window, drawers that open and close by key, and a grid that fills its width with whole columns.
// From 1400 px the segments drawer opens by itself, docked; under it, it is closed until asked for.
const SIZES = [
  { name: "phone", width: 390, height: 844 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
];

for (const size of SIZES) {
  const big = size.width >= 1400;
  test.describe(`${size.name} (${size.width} px)`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    // the layout keys work from the toolbar (a phone has no page cells in its list view), so the keys are sent from the View menu's button
    const keyHome = (page: import("@playwright/test").Page) => page.getByRole("button", { name: "View", exact: true });
    const rail = (page: import("@playwright/test").Page) => page.getByRole("complementary", { name: "Segments" });
    const compare = (page: import("@playwright/test").Page) => page.getByRole("complementary", { name: "Compare pages" });
    const open = async (page: import("@playwright/test").Page) => {
      await signIn(page, "A Manager", "setup/split/demo");
      await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    };
    const overflow = (page: import("@playwright/test").Page) => page.evaluate(() => ({ doc: document.documentElement.scrollWidth - window.innerWidth, body: document.body.scrollWidth - window.innerWidth }));

    test("the page does not scroll sideways, in the draft, in focus, and with a drawer open", async ({ page }) => {
      await open(page);
      expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
      await keyHome(page).focus();
      if (!big) await page.keyboard.press("s");
      await expect(rail(page)).toBeVisible();
      const box = await rail(page).boundingBox();
      expect(box!.width, "a drawer wider than the window").toBeLessThanOrEqual(size.width);
      expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
      await page.keyboard.press("c");
      await expect(compare(page)).toBeVisible();
      expect((await compare(page).boundingBox())!.width).toBeLessThanOrEqual(size.width);
      expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
      await page.keyboard.press("f");
      await expect(page.locator(".split-shell")).toHaveAttribute("data-focus", "true");
      expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
    });

    test("focus mode hides the console's header and menu so the splitter fills the window, and Esc leaves it", async ({ page }) => {
      await open(page);
      await expect(page.locator(".console-bar")).toBeVisible();
      await keyHome(page).focus();
      await page.keyboard.press("f");
      await expect(page.locator(".console-bar")).toBeHidden();
      await expect(page.locator(".console-nav, .console-goto")).toBeHidden();
      const shell = await page.locator(".split-shell").boundingBox();
      expect(shell!.x).toBeLessThanOrEqual(1);
      expect(shell!.y).toBeLessThanOrEqual(1);
      expect(Math.abs(shell!.width - size.width)).toBeLessThanOrEqual(1);
      expect(Math.abs(shell!.height - size.height)).toBeLessThanOrEqual(1);
      // the pages take the room under the toolbar (the docked segments drawer, on a big screen, is beside them)
      const stage = await page.locator(".split-stage").boundingBox();
      expect(stage!.width).toBeGreaterThan(size.width - 40);
      expect(stage!.height).toBeGreaterThan(size.height * (size.width < 720 ? 0.4 : 0.5));
      const work = await page.locator(".split-gridwrap").boundingBox();
      expect(work!.width).toBeGreaterThan(size.width - 40 - (big ? 420 : 0));
      expect(work!.height).toBeGreaterThan(size.height * (size.width < 720 ? 0.3 : 0.45));     // a phone keeps a bar of actions under the pages
      // remembered for the tab
      expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("jason-split-layout-demo") ?? "{}").focus)).toBe(true);
      await keyHome(page).focus();
      await page.keyboard.press("Escape");
      await expect(page.locator(".console-bar")).toBeVisible();
      await expect(page.locator(".split-shell")).not.toHaveAttribute("data-focus", "true");
    });

    test("the segments and compare drawers open and close by key and by their controls, and the focus comes back", async ({ page }) => {
      await open(page);
      const home = keyHome(page);
      await home.focus();
      if (big) {
        await expect(rail(page)).toHaveAttribute("data-docked", "true");          // open and docked by itself from 1400 px
        await page.keyboard.press("s");
        await expect(rail(page)).toHaveCount(0);
        await page.keyboard.press("s");
        await expect(rail(page)).toBeVisible();
      } else {
        await page.keyboard.press("s");
        await expect(rail(page)).toBeVisible();
        await expect(rail(page)).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(rail(page)).toHaveCount(0);
        await expect(home).toBeFocused();
      }
      await page.keyboard.press("c");
      await expect(compare(page)).toBeVisible();
      await expect(compare(page).getByText(/Page \d+ of 120/).first()).toBeVisible();
      await compare(page).getByRole("button", { name: "Close", exact: true }).click();
      await expect(compare(page)).toHaveCount(0);
      // the scrim closes one too
      await home.focus();
      await page.keyboard.press("c");
      await expect(compare(page)).toBeVisible();
      // (the docked segments drawer of a big screen sits over the scrim's left edge)
      await page.locator(".split-scrim").click({ position: { x: big ? 450 : 3, y: big ? 300 : 3 }, force: true });
      await expect(compare(page)).toHaveCount(0);
    });
  });
}

test.describe("desktop grid", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("the album's columns fill the width, and the segment strip and a menu work", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    const grid = page.getByRole("grid", { name: "Pages" });
    await expect(page.locator("[data-cell]").first()).toBeVisible();
    const g = await grid.boundingBox();
    const right = await page.evaluate(() => {
      const row = document.querySelector<HTMLElement>('[role=row][aria-rowindex] .split-cell')?.parentElement;
      const cells = Array.from(row?.querySelectorAll<HTMLElement>(".split-cell") ?? []);
      return Math.max(...cells.map((c) => c.getBoundingClientRect().right));
    });
    // the leftover is rounding and the scrollbar, never a column's worth
    expect(g!.x + g!.width - right, "room left at the right of the first row").toBeLessThan(40);
    // a menu by keyboard: the count is in the item
    const mark = page.getByRole("button", { name: "Mark", exact: true });
    await mark.focus();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("menuitem", { name: /^Accept \d+ at High confidence$/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(mark).toBeFocused();
    await expect(page.getByRole("navigation", { name: "Segments, as numbered chips" })).toBeVisible();
  });
});

// On a wide window the splitter's own screens use the whole width: the nav sits at the window's left edge and the content follows it,
// not centred under the console's 1280 px cap. This was seen on the start page, where the cap was only lifted once an editor existed.
test.describe("a wide window (2400 px)", () => {
  test.use({ viewport: { width: 2400, height: 1100 } });

  for (const route of ["setup/split", "setup/split/demo"]) {
    test(`#/${route} keeps the nav at the left edge and the content beside it`, async ({ page }) => {
      await signIn(page, "A Manager", route);
      await expect(page.locator(".console-body")).toHaveAttribute("data-screen", "setup/split");
      const box = await page.evaluate(() => {
        const rect = (s: string) => { const e = document.querySelector(s); const r = e?.getBoundingClientRect(); return r ? { x: r.x, w: r.width } : null; };
        return { body: rect(".console-body"), nav: rect("nav"), main: rect("main.console-main") };
      });
      expect(box.body!.w, "the console body is capped").toBeGreaterThan(2300);
      expect(box.nav!.x, "the nav floats toward the middle").toBeLessThan(80);
      expect(box.main!.x, "a margin between the nav and the content").toBeLessThan(320);
    });
  }
});
