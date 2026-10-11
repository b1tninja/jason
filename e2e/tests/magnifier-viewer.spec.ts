import type { Page } from "@playwright/test";
import { expect, signIn, test } from "./fixtures";

// The magnifier's second mode (docs/pdf-splitter.md, section 5.12): a fixed viewer in a screen corner, so the eyes do not follow a lens.
const viewer = (page: Page) => page.locator(".split-viewer");
const finder = (page: Page) => page.locator(".split-viewfinder");
const lens = (page: Page) => page.locator(".split-loupe");
const pic = (page: Page, n: number) => page.locator(`[data-cell][data-page="${n}"] .split-pic`);
const viewButton = (page: Page) => page.getByRole("button", { name: "View", exact: true });
const overflow = (page: Page) => page.evaluate(() => ({ doc: document.documentElement.scrollWidth - window.innerWidth, body: document.body.scrollWidth - window.innerWidth }));
const strip = (page: Page) => viewer(page).locator("[data-role=title]");

async function chooseFixed(page: Page) {
  await viewButton(page).click();
  await page.getByRole("menuitemradio", { name: "Mode: fixed corner viewer" }).click();
}
async function hoverPage(page: Page, n: number, dx = 0.5, dy = 0.5) {
  const b = (await pic(page, n).boundingBox())!;
  await page.mouse.move(b.x + b.width * dx, b.y + b.height * dy);
  return b;
}

test.describe("the fixed corner viewer on the demo draft", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test.beforeEach(async ({ page }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    await expect(page.locator('[data-cell][data-page="3"] img')).toHaveAttribute("data-state", "ready");
    await chooseFixed(page);
    await expect(page.locator(".split-live")).toContainText("fixed viewer");
  });

  test("stays in one place across hovers over different pages, larger than the cell, and the lens stays away", async ({ page }) => {
    const cell = await hoverPage(page, 3);
    await expect(viewer(page)).toBeVisible();
    await expect(viewer(page)).toHaveAttribute("role", "region");
    await expect(viewer(page)).toHaveAttribute("aria-label", "Magnified page");
    await expect(viewer(page).locator(".split-viewer-pic")).toHaveAttribute("aria-label", "Magnified page 3");
    await expect(viewer(page)).toHaveAttribute("data-size", "sharp");
    await expect(strip(page)).toHaveText("Page 3");
    await expect(viewer(page).locator("[data-role=zoom]")).toHaveText(/^[\d.]+ times zoom$/);
    await expect(viewer(page)).toHaveAttribute("data-zoom", "3");
    await expect(lens(page)).toBeHidden();
    const first = (await viewer(page).boundingBox())!;
    expect(first.width, "the picture is larger than the cell").toBeGreaterThan(cell.width * 2);
    const vp = page.viewportSize()!;
    expect(first.x + first.width).toBeLessThanOrEqual(vp.width);
    expect(first.y + first.height).toBeLessThanOrEqual(vp.height);
    expect(first.x, "bottom right").toBeGreaterThan(vp.width / 2);
    expect(first.y).toBeGreaterThan(vp.height / 3);
    await hoverPage(page, 5);
    await expect(strip(page)).toHaveText("Page 5");
    await hoverPage(page, 4, 0.2, 0.3);
    await expect(strip(page)).toHaveText("Page 4");
    expect(await viewer(page).boundingBox()).toEqual(first);
    await expect(viewer(page)).toHaveAttribute("data-size", "sharp");
    expect(Number(await viewer(page).getAttribute("data-px"))).toBeGreaterThan(await page.locator('[data-cell][data-page="4"] img').evaluate((i: HTMLImageElement) => i.naturalWidth));
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
    // the picture area never takes the pointer
    expect(await viewer(page).locator(".split-viewer-pic").evaluate((e) => getComputedStyle(e).pointerEvents)).toBe("none");
  });

  test("a viewfinder on the hovered thumbnail shows the magnified area, and the whole-page view drops it", async ({ page }) => {
    const cell = await hoverPage(page, 3, 0.5, 0.5);
    await expect(finder(page)).toBeVisible();
    const f = (await finder(page).boundingBox())!;
    expect(f.width).toBeGreaterThan(8);
    expect(f.x).toBeGreaterThanOrEqual(cell.x - 2);
    expect(f.x + f.width).toBeLessThanOrEqual(cell.x + cell.width + 2);
    expect(await finder(page).evaluate((e) => getComputedStyle(e).pointerEvents)).toBe("none");
    await hoverPage(page, 3, 0.9, 0.9);
    await expect.poll(async () => (await finder(page).boundingBox())!.y).toBeGreaterThan(f.y);
    await viewer(page).getByRole("button", { name: "Whole page" }).click({ force: true });
    await expect(viewer(page).locator("[data-role=zoom]")).toHaveText("Whole page");
    await expect(viewer(page)).toHaveAttribute("data-view", "page");
    await expect(finder(page)).toBeHidden();
    await expect(viewer(page).getByRole("button", { name: "Whole page" })).toHaveAttribute("aria-pressed", "true");
  });

  test("hops to the opposite corner when the pointer stays under it, and not when asked not to", async ({ page }) => {
    await hoverPage(page, 3);
    await expect(viewer(page)).toBeVisible();
    const home = (await viewer(page).boundingBox())!;
    // the pointer goes under the panel (on the page grid beneath it, if there is one, else the stage)
    const under = { x: home.x + home.width / 2, y: home.y + home.height / 2 };
    await page.mouse.move(under.x, under.y);
    await page.waitForTimeout(100);
    expect((await viewer(page).boundingBox())!.x, "not yet").toBe(home.x);
    await expect(viewer(page)).toHaveAttribute("data-corner", "top-left", { timeout: 3000 });
    await expect.poll(async () => (await viewer(page).boundingBox())!.x).toBeLessThan(home.x / 2);
    const work = (await page.locator(".split-work").boundingBox())!;
    expect((await viewer(page).boundingBox())!.y, "inside the grid's stage").toBeGreaterThanOrEqual(work.y);
    await expect(page.locator(".split-live")).toContainText("Viewer moved to the top left corner.");
    // choose not to hop: it stays
    await viewButton(page).click();
    await page.getByRole("menuitemcheckbox", { name: "Do not hop (keep the viewer in its corner)" }).click();
    await page.mouse.move(5, 300);
    await page.mouse.move(150, 200);
    await page.waitForTimeout(700);
    expect((await viewer(page).boundingBox())!.x).toBeLessThan(home.x / 2);
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
  });

  test("stays after the pointer leaves the grid; Pin freezes it on a page; Esc hides it", async ({ page }) => {
    await hoverPage(page, 3);
    await expect(viewer(page)).toHaveAttribute("data-size", "sharp");
    await page.mouse.move(640, 5);
    await page.waitForTimeout(400);
    await expect(viewer(page)).toBeVisible();
    await expect(strip(page)).toHaveText("Page 3");
    // pin it (the buttons are reachable; the pointer on them does not make the panel hop away)
    await viewer(page).getByRole("button", { name: "Pin" }).click();
    await expect(viewer(page).getByRole("button", { name: "Pin" })).toHaveAttribute("aria-pressed", "true");
    await expect(strip(page)).toHaveText("Pinned to page 3");
    await expect(page.locator(".split-live")).toContainText("Viewer pinned to page 3");
    await hoverPage(page, 6);
    await page.waitForTimeout(300);
    await expect(strip(page)).toHaveText("Pinned to page 3");
    await expect(viewer(page).locator(".split-viewer-pic")).toHaveAttribute("aria-label", "Magnified page 3");
    await viewer(page).getByRole("button", { name: "Pin" }).click();
    await hoverPage(page, 6);
    await expect(strip(page)).toHaveText("Page 6");
    await page.keyboard.press("Escape");
    await expect(viewer(page)).toBeHidden();
    await expect(finder(page)).toBeHidden();
    await page.mouse.move(640, 5);
    await hoverPage(page, 7);
    await expect(viewer(page)).toBeVisible();
    // the toggle hides it too
    await page.keyboard.press("e");
    await expect(viewer(page)).toBeHidden();
    await expect(page.locator(".split-live")).toHaveText("Magnifier off.");
  });

  test("the keyboard: the focused page at the centre, Alt and arrows pan, every control is reachable with a visible focus", async ({ page }) => {
    const cell = page.locator('button.split-cell-btn[data-page="3"]');
    await cell.focus();
    await page.keyboard.press("Alt+ArrowRight");
    await expect(viewer(page)).toBeVisible();
    await expect(strip(page)).toHaveText("Page 3");
    const bg1 = await viewer(page).locator(".split-viewer-pic").evaluate((e: HTMLElement) => e.style.backgroundPosition);
    await page.keyboard.press("Alt+ArrowDown");
    await expect.poll(() => viewer(page).locator(".split-viewer-pic").evaluate((e: HTMLElement) => e.style.backgroundPosition)).not.toBe(bg1);
    await page.keyboard.press("ArrowRight");
    await expect(strip(page)).toHaveText("Page 4");
    for (const name of ["Whole page", "Pin", "Hide"]) {
      await viewer(page).getByRole("button", { name, exact: true }).focus();
      const o = await viewer(page).getByRole("button", { name, exact: true }).evaluate((e) => getComputedStyle(e).outlineStyle);
      expect(o, `${name} shows its focus`).not.toBe("none");
    }
    await viewer(page).getByRole("button", { name: "Pin" }).focus();
    await page.keyboard.press("Enter");
    await expect(strip(page)).toHaveText("Pinned to page 4");
    await expect(page.locator(".split-shell")).not.toHaveAttribute("data-focus", "true");          // Enter and the letter keys on the panel are not the screen's
    const grip = viewer(page).getByRole("button", { name: /Resize the viewer/ });
    const before = (await viewer(page).boundingBox())!.width;
    await grip.focus();
    await page.keyboard.press("ArrowUp");
    await expect.poll(async () => (await viewer(page).boundingBox())!.width).toBeGreaterThan(before);
    await page.keyboard.press("Escape");
    await expect(viewer(page)).toBeHidden();
  });

  test("View menu: corner, size, region or whole page; remembered for the tab; the panel stays in the window", async ({ page }) => {
    await viewButton(page).click();
    await page.getByRole("menuitemradio", { name: "Viewer corner: top right" }).click();
    await viewButton(page).click();
    await page.getByRole("menuitemradio", { name: /Viewer size: large/ }).click();
    await hoverPage(page, 3);
    await expect(viewer(page)).toHaveAttribute("data-corner", "top-right");
    const b = (await viewer(page).boundingBox())!;
    expect(b.width, "larger than the medium size, as far as the stage's height allows").toBeGreaterThan(380);
    const vp = page.viewportSize()!;
    const work = (await page.locator(".split-work").boundingBox())!;
    expect(b.y, "at the top of the grid's stage").toBeLessThan(work.y + 40);
    expect(b.x + b.width).toBeLessThanOrEqual(vp.width);
    await viewButton(page).click();
    await expect(page.getByRole("menuitemradio", { name: "Mode: fixed corner viewer" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("menuitemradio", { name: "Viewer corner: top right" })).toHaveAttribute("aria-checked", "true");
    await page.keyboard.press("Escape");
    await page.mouse.move(640, 880);
  });

  test("it keeps out of the compare drawer and works in focus mode", async ({ page }) => {
    await page.locator('button.split-cell-btn[data-page="6"]').focus();
    await page.keyboard.press("c");
    const drawer = page.locator('.split-drawer[data-drawer="inspect"]');
    await expect.poll(async () => { const d = await drawer.boundingBox(); return !!d && d.x + d.width <= 1280; }).toBe(true);
    const fig = page.locator(".split-figure").filter({ hasText: "This page" }).locator(".split-figure-pic");
    await expect(fig.locator("img")).toHaveAttribute("data-state", "ready");
    const fb = (await fig.boundingBox())!;
    await page.mouse.move(fb.x + fb.width / 2, fb.y + Math.min(fb.height, 300) / 2);
    await expect(viewer(page)).toBeVisible();
    await expect(strip(page)).toHaveText("Page 6");
    const v = (await viewer(page).boundingBox())!;
    const d = (await drawer.boundingBox())!;
    expect(v.x + v.width <= d.x + 1 || v.x >= d.x + d.width - 1, "not over the drawer").toBe(true);
    await page.mouse.move(640, 5);
    await page.keyboard.press("c");
    await page.keyboard.press("f");
    await expect(page.locator(".split-shell")).toHaveAttribute("data-focus", "true");
    await hoverPage(page, 2);
    await expect(viewer(page)).toBeVisible();
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
  });
});

test.describe("the fixed viewer on a phone and a tablet", () => {
  test.describe("phone", () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

    test("is a band of about 40 percent above the action bar, inside the window, with no overflow", async ({ page }) => {
      await signIn(page, "A Manager", "setup/split/demo");
      await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
      await viewButton(page).click();
      await page.getByRole("menuitemradio", { name: "Album" }).click();
      await viewButton(page).click();
      await page.getByRole("menuitemradio", { name: "Mode: fixed corner viewer" }).click();
      await page.getByRole("toolbar", { name: "Actions" }).getByRole("button", { name: "Magnifier" }).click();
      const thumb = page.locator('[data-cell][data-page="8"] .split-pic');
      await expect(thumb.locator("img")).toHaveAttribute("data-state", "ready");
      await thumb.scrollIntoViewIfNeeded();
      const b = (await thumb.boundingBox())!;
      const x = b.x + b.width / 2, y = b.y + b.height / 2;
      const cdp = await page.context().newCDPSession(page);
      const touch = (type: string, px: number, py: number) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" ? [] : [{ x: px, y: py }] });
      await touch("touchStart", x, y);
      await page.waitForTimeout(450);
      await expect(viewer(page)).toBeVisible();
      await expect(viewer(page)).toHaveAttribute("data-mode", "band");
      await expect(strip(page)).toHaveText("Page 8");
      const band = (await viewer(page).boundingBox())!;
      const bar = (await page.getByRole("toolbar", { name: "Actions" }).boundingBox())!;
      expect(band.y + band.height).toBeLessThanOrEqual(bar.y + 1);
      expect(band.x).toBeGreaterThanOrEqual(0);
      expect(band.x + band.width).toBeLessThanOrEqual(390.5);
      expect(Math.abs(band.height / 844 - 0.4)).toBeLessThan(0.06);
      expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
      await touch("touchEnd", 0, 0);
      await page.waitForTimeout(300);
      await expect(viewer(page)).toBeVisible();                   // the last page stays in the band
      await expect(page.locator('button.split-cell-btn[data-page="8"]')).toHaveAttribute("aria-pressed", "false");
    });
  });

  test.describe("tablet", () => {
    test.use({ viewport: { width: 820, height: 1000 } });

    test("is a corner panel in the window, with no overflow", async ({ page }) => {
      await signIn(page, "A Manager", "setup/split/demo");
      await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
      await chooseFixed(page);
      const b = (await pic(page, 2).boundingBox())!;
      await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
      await expect(viewer(page)).toBeVisible();
      await expect(viewer(page)).toHaveAttribute("data-mode", "corner");
      const v = (await viewer(page).boundingBox())!;
      expect(v.x + v.width).toBeLessThanOrEqual(820);
      expect(v.y + v.height).toBeLessThanOrEqual(1000);
      expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
    });
  });
});

test.describe("the fixed viewer, reduced motion and colour schemes", () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });

  test("has no transition under reduced motion, and reads in dark and light", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    await chooseFixed(page);
    await hoverPage(page, 3);
    await expect(viewer(page)).toBeVisible();
    expect(await viewer(page).evaluate((e) => getComputedStyle(e).transitionDuration)).toMatch(/^0s/);
    for (const scheme of ["dark", "light"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      const c = await viewer(page).evaluate((e) => ({ bg: getComputedStyle(e).backgroundColor, fg: getComputedStyle(e).color }));
      expect(c.bg).not.toBe(c.fg);
    }
  });
});
