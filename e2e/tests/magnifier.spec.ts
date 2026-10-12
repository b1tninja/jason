import path from "node:path";
import type { Page } from "@playwright/test";
import { expect, signIn, test } from "./fixtures";

// The magnifier (docs/pdf-splitter.md, section 5.12): a lens that follows the pointer over a page, shows the spot in the sharpest picture, and
// never takes the click. The demo needs no server; a file chosen on this computer is drawn finer by the browser; a server draft is asked for
// the server's 1600 px size.
const sample = path.join(process.env.E2E_DATA ?? "", "e2e", "sample.pdf");

const lens = (page: Page) => page.locator(".split-loupe");
const pic = (page: Page, n: number) => page.locator(`[data-cell][data-page="${n}"] .split-pic`);
const viewButton = (page: Page) => page.getByRole("button", { name: "View", exact: true });
const overflow = (page: Page) => page.evaluate(() => ({ doc: document.documentElement.scrollWidth - window.innerWidth, body: document.body.scrollWidth - window.innerWidth }));
const cellPx = (page: Page, n: number) => page.locator(`[data-cell][data-page="${n}"] img`).evaluate((i: HTMLImageElement) => Math.max(i.naturalWidth, i.naturalHeight));
const lensPx = async (page: Page) => Number(await lens(page).getAttribute("data-px"));

test.describe("the magnifier on the demo draft", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test.beforeEach(async ({ page }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    await expect(page.locator('[data-cell][data-page="3"] img')).toHaveAttribute("data-state", "ready");
  });

  test("a lens follows the pointer over a page, swaps to a larger picture in place, and goes when the pointer leaves", async ({ page }, info) => {
    const box = (await pic(page, 3).boundingBox())!;
    const t0 = Date.now();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await expect(lens(page)).toBeVisible();
    await expect(lens(page)).toHaveAttribute("aria-label", "Magnified page 3");
    await expect(lens(page)).toHaveAttribute("role", "img");
    await expect(lens(page)).toHaveAttribute("data-size", "sharp");
    const sharpMs = Date.now() - t0;
    info.annotations.push({ type: "hover-to-sharp (demo)", description: `${sharpMs} ms` });
    expect(await lensPx(page), "the lens uses a picture larger than the cell's").toBeGreaterThan(await cellPx(page, 3));
    // it shows a spot of the page at the zoom: the lens picture is 3 times the cell's width
    const bgSize = await lens(page).evaluate((e: HTMLElement) => e.style.backgroundSize);
    expect(Math.round(parseFloat(bgSize))).toBeGreaterThanOrEqual(Math.round(box.width * 2.9));
    expect(await lens(page).evaluate((e) => getComputedStyle(e).pointerEvents)).toBe("none");
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
    // it stays inside the window, near the right and bottom edges too
    const vp = page.viewportSize()!;
    await page.mouse.move(vp.width - 12, vp.height - 12);
    const edge = await lens(page).boundingBox();
    if (edge) { expect(edge.x).toBeGreaterThanOrEqual(0); expect(edge.y).toBeGreaterThanOrEqual(0); expect(edge.x + edge.width).toBeLessThanOrEqual(vp.width); expect(edge.y + edge.height).toBeLessThanOrEqual(vp.height); }
    // leaving the pages hides it
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await expect(lens(page)).toBeVisible();
    await page.mouse.move(5, 5);
    await expect(lens(page)).toBeHidden();
  });

  test("a click through the lens marks the page exactly as it does without one, and the lens stays", async ({ page }) => {
    const cell = page.locator('button.split-cell-btn[data-page="5"]');
    const marks = async () => (await page.getByLabel("Draft summary").innerText()).match(/(\d+) segments?/)![1];
    await viewButton(page).focus();
    await page.keyboard.press("e");                                   // off
    await expect(page.getByRole("button", { name: "Magnifier" }).first()).toHaveAttribute("aria-pressed", "false");
    await cell.click();
    await expect(cell).toHaveAttribute("aria-pressed", "true");
    const without = await marks();
    await page.keyboard.press("z");
    await expect(cell).toHaveAttribute("aria-pressed", "false");
    await page.keyboard.press("e");                                   // on
    const box = (await pic(page, 5).boundingBox())!;
    await page.mouse.move(box.x + 30, box.y + 40);
    await expect(lens(page)).toBeVisible();
    await page.mouse.down(); await page.mouse.up();
    await expect(cell).toHaveAttribute("aria-pressed", "true");
    expect(await marks()).toBe(without);
    await expect(lens(page)).toBeVisible();
    await page.keyboard.press("z");
    await expect(cell).toHaveAttribute("aria-pressed", "false");
    // shift-click still selects a range under the lens
    await cell.click();
    await pic(page, 8).click({ modifiers: ["Shift"] });
    await expect(page.locator(".split-selbar")).toContainText("4 pages selected");
    await page.mouse.move(5, 5);
  });

  test.use({ repeatCeiling: 6 });                                 // the test reloads the page
  test("E turns it on and off (M is the merge key), with the state in words, and the choice is kept for the tab", async ({ page }) => {
    const box = (await pic(page, 2).boundingBox())!;
    await viewButton(page).focus();
    await page.keyboard.press("e");
    await expect(page.locator(".split-live")).toHaveText("Magnifier off.");
    await page.mouse.move(box.x + 20, box.y + 20);
    await page.waitForTimeout(400);
    await expect(lens(page)).toBeHidden();
    await viewButton(page).click();
    await expect(page.getByRole("menuitemcheckbox", { name: "Magnifier (off)" })).toHaveAttribute("aria-checked", "false");
    await page.keyboard.press("Escape");
    await page.reload();
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    await expect(page.getByRole("button", { name: "Magnifier" }).first()).toHaveAttribute("aria-pressed", "false");
    await viewButton(page).focus();
    await page.keyboard.press("e");
    await expect(page.locator(".split-live")).toContainText("Magnifier on.");
    const again = (await pic(page, 2).boundingBox())!;
    await page.mouse.move(again.x + 20, again.y + 20);
    await expect(lens(page)).toBeVisible();
    // the key list says where it is
    await page.keyboard.press("?");
    await expect(page.getByRole("dialog", { name: "Keyboard map" })).toContainText("Magnifier on or off");
    await page.keyboard.press("Escape");
  });

  test("Alt and the wheel zoom from 2 to 6 times, the plain wheel scrolls, and Escape hides the lens", async ({ page }) => {
    const box = (await pic(page, 3).boundingBox())!;
    await page.mouse.move(box.x + 40, box.y + 50);
    await expect(lens(page)).toBeVisible();
    expect(await lens(page).getAttribute("data-zoom")).toBe("3");
    await page.keyboard.down("Alt");
    await page.mouse.wheel(0, -100);
    await expect(lens(page)).toHaveAttribute("data-zoom", "3.5");
    await page.waitForTimeout(100);
    for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, -100); await page.waitForTimeout(90); }
    await expect(lens(page)).toHaveAttribute("data-zoom", "6");
    for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, 100); await page.waitForTimeout(90); }
    await expect(lens(page)).toHaveAttribute("data-zoom", "2");
    await page.keyboard.up("Alt");
    await expect(page.locator(".split-live")).toContainText("Magnifier 2 times");
    await page.keyboard.press("Escape");
    await expect(lens(page)).toBeHidden();
    await page.mouse.move(5, 5);
  });

  test("with the keyboard the lens stands beside the focused page, Alt and the arrows move the spot, and it has no effect on the marks", async ({ page }) => {
    const cell = page.locator('button.split-cell-btn[data-page="3"]');
    await cell.focus();
    await page.keyboard.press("Alt+ArrowRight");
    await expect(lens(page)).toBeVisible();
    await expect(lens(page)).toHaveAttribute("data-mode", "beside");
    await expect(lens(page)).toHaveAttribute("aria-label", "Magnified page 3");
    await expect(page.locator(".split-live")).toContainText("Magnifier on page 3");
    const bg1 = await lens(page).evaluate((e: HTMLElement) => e.style.backgroundPosition);
    await page.keyboard.press("Alt+ArrowDown");
    await expect.poll(() => lens(page).evaluate((e: HTMLElement) => e.style.backgroundPosition)).not.toBe(bg1);          // placed in an animation frame
    await page.keyboard.press("Alt+=");
    await expect(lens(page)).toHaveAttribute("data-zoom", "3.5");
    // arrow keys to another page: the lens goes with the focus
    await page.keyboard.press("ArrowRight");
    await expect(lens(page)).toHaveAttribute("aria-label", "Magnified page 4");
    await expect(page.locator('button.split-cell-btn[data-page="4"]')).toHaveAttribute("aria-pressed", "false");
    await page.keyboard.press("Escape");
    await expect(lens(page)).toBeHidden();
  });

  test("the toolbar button and the View menu say the state with a check or a word, and the zoom can be set there", async ({ page }) => {
    const btn = page.getByRole("toolbar", { name: "Splitter controls" }).getByRole("button", { name: "Magnifier" });
    await expect(btn).toHaveAttribute("aria-pressed", "true");
    await btn.click();
    await expect(btn).toHaveAttribute("aria-pressed", "false");
    await viewButton(page).click();
    await expect(page.getByRole("menuitemradio", { name: /Magnifier zoom: 4 times/ })).toHaveAttribute("aria-disabled", "true");
    await page.keyboard.press("Escape");
    await btn.click();
    await viewButton(page).click();
    await page.getByRole("menuitemradio", { name: /Magnifier zoom: 5 times/ }).click();
    const box = (await pic(page, 3).boundingBox())!;
    await page.mouse.move(box.x + 40, box.y + 50);
    await expect(lens(page)).toHaveAttribute("data-zoom", "5");
    await page.mouse.move(5, 5);
  });

  test("it works over the compare drawer's figure and in focus mode", async ({ page }) => {
    await page.locator('button.split-cell-btn[data-page="6"]').focus();
    await page.keyboard.press("c");
    const fig = page.locator(".split-figure").filter({ hasText: "This page" }).locator(".split-figure-pic");
    await expect(fig.locator("img")).toHaveAttribute("data-state", "ready");
    await expect.poll(async () => { const b = await fig.boundingBox(); return !!b && b.x + b.width <= 1280; }).toBe(true);     // the drawer has slid in
    const box = (await fig.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height, 300) / 2);
    await expect(lens(page)).toHaveAttribute("aria-label", "Magnified page 6");
    await expect(lens(page)).toHaveAttribute("data-size", "sharp");
    await page.mouse.move(5, 5);
    await page.keyboard.press("c");
    await page.keyboard.press("f");
    await expect(page.locator(".split-shell")).toHaveAttribute("data-focus", "true");
    const cell = (await pic(page, 2).boundingBox())!;
    await page.mouse.move(cell.x + 20, cell.y + 20);
    await expect(lens(page)).toBeVisible();
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
    await page.mouse.move(5, 5);
  });

  test("in the filmstrip the strip's thumbnails are magnified too", async ({ page }) => {
    await viewButton(page).click();
    await page.getByRole("menuitemradio", { name: "Filmstrip" }).click();
    await expect(page.locator(".split-film")).toBeVisible();
    const thumb = page.locator('.split-film [data-cell][data-page="2"] .split-pic');
    await expect(thumb.locator("img")).toHaveAttribute("data-state", "ready");
    const box = (await thumb.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await expect(lens(page)).toHaveAttribute("aria-label", "Magnified page 2");
    await page.mouse.move(5, 5);
  });
});

test.describe("the magnifier on a file chosen on this computer", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("the browser draws the page finer on demand, in place, with no request to the server", async ({ page, watch }, info) => {
    await signIn(page, "A Manager", "setup/split");
    await page.locator("#split-file").setInputFiles(sample);
    await expect(page.locator(".split-pictures")).toHaveAttribute("data-pictures", "browser");
    await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
    const img = page.locator('[data-cell][data-page="2"] img');
    await expect(img).toHaveAttribute("data-state", "ready");
    const box = (await pic(page, 2).boundingBox())!;
    const t0 = Date.now();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await expect(lens(page)).toBeVisible();
    await expect(lens(page)).toHaveAttribute("data-size", "sharp", { timeout: 15_000 });
    info.annotations.push({ type: "hover-to-sharp (local file, 1600 px)", description: `${Date.now() - t0} ms` });
    const first = await lensPx(page);
    expect(first).toBeGreaterThanOrEqual(1500);
    expect(first).toBeGreaterThan(await cellPx(page, 2));
    expect(await lens(page).evaluate((e: HTMLElement) => e.style.backgroundImage.startsWith('url("blob:'))).toBe(true);

    // bigger cells and the strongest zoom ask for more than the server could give: up to the page's own 300 dpi
    await page.mouse.move(5, 5);
    await page.getByLabel("Thumbnail size").fill("220");
    await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.dataset.size), { timeout: 15_000 }).toBe("medium");
    await viewButton(page).click();
    await page.getByRole("menuitemradio", { name: /Magnifier zoom: 6 times/ }).click();
    const big = (await pic(page, 2).boundingBox())!;
    const t1 = Date.now();
    await page.mouse.move(big.x + big.width / 2, big.y + big.height / 2);
    await expect(lens(page)).toHaveAttribute("data-zoom", "6");
    await expect.poll(() => lensPx(page), { timeout: 20_000 }).toBeGreaterThan(1600);
    info.annotations.push({ type: "hover-to-sharp (local file, beyond 1600 px)", description: `${Date.now() - t1} ms` });
    expect(watch.calls.filter((c) => c.url.startsWith("/api/split/thumb")), "a picture was asked of the server").toEqual([]);

    // a click through the lens marks the page
    const two = page.locator('button.split-cell-btn[data-page="2"]');
    await page.mouse.down(); await page.mouse.up();
    await expect(two).toHaveAttribute("aria-pressed", "true");
    await page.mouse.move(5, 5);
    await expect(lens(page)).toBeHidden();
    await expect.poll(() => page.evaluate(() => window.location.hash), { timeout: 20_000 }).toMatch(/^#\/setup\/split\/[0-9a-f]{8,16}$/);
  });
});

test.describe("the magnifier on a server draft", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("the server's largest picture (1600 px) is asked for after the dwell, once, and is kept", async ({ page, watch }) => {
    await page.request.get("/__e2e/limit?key=split.client_render&value=off");
    try {
      await signIn(page, "A Manager", "setup/split");
      await page.locator("#split-file").setInputFiles(sample);
      await page.getByRole("button", { name: "Check the file" }).click();
      await page.getByRole("button", { name: "Open it for splitting" }).click();
      await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
      const img = page.locator('[data-cell][data-page="3"] img');
      await expect(img).toHaveAttribute("data-state", "ready");
      const huge = () => watch.calls.filter((c) => c.url.includes("size=huge") && c.url.includes("page=3"));
      expect(huge()).toHaveLength(0);
      const box = (await pic(page, 3).boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await expect(lens(page)).toHaveAttribute("data-size", "sharp", { timeout: 15_000 });
      expect(await lensPx(page)).toBeGreaterThan(await cellPx(page, 3));
      expect(huge()).toHaveLength(1);
      // away and back: the picture is held, not fetched again
      await page.mouse.move(5, 5);
      await expect(lens(page)).toBeHidden();
      await page.mouse.move(box.x + box.width / 2 + 3, box.y + box.height / 2);
      await expect(lens(page)).toHaveAttribute("data-size", "sharp");
      expect(huge()).toHaveLength(1);
      // a pointer that only passes over a page does not ask for its picture
      const other = (await pic(page, 9).boundingBox())!;
      await page.mouse.move(other.x + 10, other.y + 10);
      await page.mouse.move(5, 5);
      await page.waitForTimeout(400);
      expect(watch.calls.filter((c) => c.url.includes("size=huge") && c.url.includes("page=9") && c.status === 200)).toHaveLength(0);
    } finally {
      await page.request.get("/__e2e/limit?key=split.client_render");
    }
  });
});

test.describe("the magnifier on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("is off until asked, and has a visible button in the bottom bar that says its state", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    const btn = page.getByRole("toolbar", { name: "Actions" }).getByRole("button", { name: "Magnifier" });
    await expect(btn).toBeVisible();
    await expect(btn).toHaveAttribute("aria-pressed", "false");
    await btn.click();
    await expect(btn).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".split-live")).toContainText("Press and hold a page, then drag");
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
    const bar = await page.getByRole("toolbar", { name: "Actions" }).boundingBox();
    expect(bar!.x + bar!.width).toBeLessThanOrEqual(390.5);
  });

  test("press and hold a page, then drag: the lens rides above the finger, scrolling and tapping are untouched, and lifting marks nothing", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    await page.getByRole("button", { name: "View", exact: true }).click();
    await page.getByRole("menuitemradio", { name: "Album" }).click();
    await page.getByRole("toolbar", { name: "Actions" }).getByRole("button", { name: "Magnifier" }).click();
    const cell = page.locator('button.split-cell-btn[data-page="8"]');
    const thumb = page.locator('[data-cell][data-page="8"] .split-pic');
    await expect(thumb.locator("img")).toHaveAttribute("data-state", "ready");
    await thumb.scrollIntoViewIfNeeded();
    const b = (await thumb.boundingBox())!;
    const x = b.x + b.width / 2, y = b.y + b.height / 2;
    const cdp = await page.context().newCDPSession(page);
    const touch = (type: string, px: number, py: number) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" ? [] : [{ x: px, y: py }] });

    // a quick drag is a scroll: no lens
    await touch("touchStart", x, y);
    await touch("touchMove", x, y + 30);
    await page.waitForTimeout(500);
    await expect(lens(page)).toBeHidden();
    await touch("touchEnd", 0, 0);

    // hold, then drag
    const t0 = Date.now();
    await touch("touchStart", x, y);
    await page.waitForTimeout(420);
    await expect(lens(page)).toBeVisible();
    expect(Date.now() - t0).toBeGreaterThanOrEqual(350);
    await expect(lens(page)).toHaveAttribute("data-mode", "touch");
    await expect(lens(page)).toHaveAttribute("aria-label", "Magnified page 8");
    await touch("touchMove", x + 6, y + 6);
    await touch("touchMove", x + 10, y + 12);
    const lb = (await lens(page).boundingBox())!;
    expect(lb.y + lb.height, "the finger covers the lens").toBeLessThan(y + 12);
    expect(lb.x).toBeGreaterThanOrEqual(0); expect(lb.x + lb.width).toBeLessThanOrEqual(390);
    await touch("touchEnd", 0, 0);
    await expect(lens(page)).toBeHidden();
    await expect(cell).toHaveAttribute("aria-pressed", "false");               // lifting after a hold marks nothing
    await expect(page.getByRole("dialog", { name: "Page 8" })).toHaveCount(0);   // and opens no page menu
    await page.waitForTimeout(700);

    // a tap still marks
    await page.touchscreen.tap(x, y);
    await expect(cell).toHaveAttribute("aria-pressed", "true");
    expect(await overflow(page)).toEqual({ doc: 0, body: 0 });
  });
});
