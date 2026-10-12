import path from "node:path";
import { expect, quiet, signIn, test } from "./fixtures";

const sample = path.join(process.env.E2E_DATA ?? "", "e2e", "sample.pdf");   // five made-up documents of 3, 2, 4, 1, and 3 pages

test.describe("signed out", () => {
  test.use({ allowConsole: [/status of 401/] });          // the browser's own line for each refused read

  test("the splitter says to sign in and asks the server a bounded number of times", async ({ page, watch }) => {
    await page.goto("/#/setup/split");
    await expect(page.getByRole("heading", { name: "Split document" })).toBeVisible();
    await expect(page.getByText("Sign in with Google to open this.")).toBeVisible();
    await quiet(page, watch);
    const settled = watch.count();
    await page.waitForTimeout(5000);                      // the regression for the request storm: nothing more is asked
    expect(watch.count() - settled, "requests in five quiet seconds").toBe(0);
    expect(settled, "requests to load the page").toBeLessThanOrEqual(16);
  });

  test("the other screens settle too", async ({ page, watch }) => {
    for (const route of ["setup/records", "setup/limits", "digest"]) {
      await page.goto(`/#/${route}`);
      await quiet(page, watch);
      const before = watch.count();
      await page.waitForTimeout(2000);
      expect(watch.count() - before, `${route} asked again while idle`).toBe(0);
    }
  });
});

test.describe("signed in, the splitter", () => {
  test.describe.configure({ mode: "serial" });

  test("the start page opens and lists no drafts yet", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    await expect(page.getByText("Sign in with Google to open this.")).toHaveCount(0);
    await expect(page.getByText("No drafts yet.")).toBeVisible();
  });

  test("a PDF chosen on this computer is drawn in the browser at once, marked, saved in the background, reviewed, previewed, and written", async ({ page, watch }) => {
    await signIn(page, "A Manager", "setup/split");
    await page.locator("#split-file").setInputFiles(sample);

    // the editor opens on the file itself: the pictures are drawn in this browser, with no picture asked of the server
    await expect(page.locator(".split-pictures")).toContainText("Preview from this computer");
    await expect(page.locator(".split-pictures")).toHaveAttribute("data-pictures", "browser");
    await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
    const first = page.locator('[data-cell][data-page="1"] img');
    await expect(first).toHaveJSProperty("complete", true);
    await expect.poll(() => first.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
    await expect.poll(() => first.evaluate((i: HTMLImageElement) => i.src.startsWith("blob:"))).toBe(true);

    // the draft arrives from the server in the background; its id replaces the placeholder in the address
    await expect.poll(() => page.evaluate(() => window.location.hash), { timeout: 20_000 }).toMatch(/^#\/setup\/split\/[0-9a-f]{8,16}$/);
    await expect(page.locator('[data-measuring]')).toHaveCount(0, { timeout: 20_000 });             // every page's facts have arrived
    expect(watch.calls.filter((c) => c.url.startsWith("/api/split/thumb")), "a picture was asked of the server").toEqual([]);
    expect(watch.calls.filter((c) => c.url.startsWith("/api/split/file")), "the file was fetched back although it was chosen here").toEqual([]);

    // a click marks a start; z undoes it
    const two = page.locator('button.split-cell-btn[data-page="2"]');
    await two.click();
    await expect(two).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("z");
    await expect(two).toHaveAttribute("aria-pressed", "false");
    await two.click();
    await expect(two).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('[data-save="saved"]')).toBeVisible();

    // review, a dry run, then one confirmed write into the throwaway data folder
    await page.getByRole("toolbar", { name: "Splitter controls" }).getByRole("button", { name: "Review and split" }).click();
    await expect(page.getByRole("heading", { name: /^Review:/ })).toBeVisible();
    await page.getByRole("button", { name: "Preview the split" }).click();
    await expect(page.getByRole("region", { name: "What the split will do" })).toBeVisible();
    await page.getByRole("button", { name: /^Write \d+ files? as / }).click();
    await expect(page.getByRole("heading", { name: "The split was written" })).toBeVisible();
  });

  test("marks made before the draft reaches the server are held and sent in order once it does", async ({ page, watch }) => {
    await signIn(page, "A Manager", "setup/split");
    await page.locator("#split-file").setInputFiles(sample);
    const four = page.locator('button.split-cell-btn[data-page="4"]');
    await four.click();                                                            // at once: the page numbers are all it needs
    await expect(four).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("z");
    await expect(four).toHaveAttribute("aria-pressed", "false");
    await four.click();
    await expect(four).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('[data-save="saved"]')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: "Review and split" }).first()).toBeEnabled();
    expect(watch.calls.filter((c) => c.url.startsWith("/api/split/thumb"))).toEqual([]);
  });

  test("enlarging the cells makes the browser draw a sharper picture in place, with no request to the server", async ({ page, watch }) => {
    await signIn(page, "A Manager", "setup/split");
    await page.locator("#split-file").setInputFiles(sample);
    const one = page.locator('[data-cell][data-page="1"] img');
    await expect.poll(() => one.evaluate((i: HTMLImageElement) => i.dataset.size)).toBe("small");
    const small = await one.evaluate((i: HTMLImageElement) => i.naturalWidth + "x" + i.naturalHeight);
    await page.getByLabel("Thumbnail size").fill("220");
    await expect.poll(() => one.evaluate((i: HTMLImageElement) => i.dataset.size)).toBe("medium");
    expect(await one.evaluate((i: HTMLImageElement) => i.src.startsWith("blob:"))).toBe(true);
    expect(await one.evaluate((i: HTMLImageElement) => Math.max(i.naturalWidth, i.naturalHeight))).toBeGreaterThan(Math.max(...small.split("x").map(Number)));
    expect(watch.calls.filter((c) => c.url.startsWith("/api/split/thumb"))).toEqual([]);
    await expect.poll(() => page.evaluate(() => window.location.hash), { timeout: 20_000 }).toMatch(/^#\/setup\/split\/[0-9a-f]{8,16}$/);
  });

  test("with browser drawing off for the community the server draws every picture", async ({ page, watch }) => {
    await page.request.get("/__e2e/limit?key=split.client_render&value=off");
    try {
      await signIn(page, "A Manager", "setup/split");
      await page.locator("#split-file").setInputFiles(sample);
      await expect(page.getByText(/sample\.pdf, /)).toBeVisible();
      await page.getByRole("button", { name: "Check the file" }).click();
      await expect(page.getByRole("region", { name: "What opening will do" })).toContainText("13 pages");
      await page.getByRole("button", { name: "Open it for splitting" }).click();
      await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
      await expect(page.locator(".split-pictures")).toHaveCount(0);
      const first = page.locator('[data-cell][data-page="1"] img');
      await expect.poll(() => first.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
      expect(watch.calls.some((c) => c.url.startsWith("/api/split/thumb") && c.status === 200)).toBe(true);
      expect(watch.calls.filter((c) => c.url.startsWith("/api/split/file")), "the file was fetched although browser drawing is off").toEqual([]);
    } finally {
      await page.request.get("/__e2e/limit?key=split.client_render");
    }
  });

  for (const [name, file, codec] of [["JPEG 2000", "jpx.pdf", "JPEG 2000"], ["CCITT Group 4", "ccitt.pdf", "CCITT"]] as const) {
    test(`a ${name} scan is drawn by the browser's self-hosted decoder and is not blank`, async ({ page, watch }) => {
      await signIn(page, "A Manager", "setup/split");
      await page.locator("#split-file").setInputFiles(path.join(process.env.E2E_DATA ?? "", "e2e", file));
      await expect(page.locator(".split-pictures")).toHaveAttribute("data-pictures", "browser");
      for (const n of [1, 2, 3]) {
        const img = page.locator(`[data-cell][data-page="${n}"] img`);
        await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth), { message: `${codec} page ${n} drew` }).toBeGreaterThan(0);
        const dark = await img.evaluate(async (i: HTMLImageElement) => {
          await i.decode();
          const c = document.createElement("canvas"); c.width = i.naturalWidth; c.height = i.naturalHeight;
          const x = c.getContext("2d")!; x.drawImage(i, 0, 0);
          const d = x.getImageData(0, 0, c.width, c.height).data;
          let m = 0; for (let k = 0; k < d.length; k += 4) if (d[k] < 200) m += 1;
          return m / (c.width * c.height);
        });
        expect(dark, `${codec} page ${n} is blank`).toBeGreaterThan(0.001);
      }
      await expect.poll(() => page.evaluate(() => window.location.hash), { timeout: 20_000 }).toMatch(/^#\/setup\/split\/[0-9a-f]{8,16}$/);
      expect(watch.calls.filter((c) => c.url.startsWith("/api/split/thumb"))).toEqual([]);
    });
  }

  test.describe("when the decoders cannot be loaded", () => {
    test.use({ allowConsole: [/Failed to load resource|ERR_FAILED|net::/] });
    test("the self-test sees a blank JPEG 2000 page, says so in words, and the server draws instead", async ({ page, watch }) => {
      await page.route("**/pdfjs/wasm/**", (r) => r.abort());                    // pdf.js then draws JPEG 2000 white, or fails: either way the test fails
      await signIn(page, "A Manager", "setup/split");
      await page.locator("#split-file").setInputFiles(path.join(process.env.E2E_DATA ?? "", "e2e", "jpx.pdf"));
      await expect(page.locator(".split-pictures")).toHaveAttribute("data-why", "selftest", { timeout: 20_000 });
      await expect(page.locator(".split-pictures")).toContainText("did not draw the JPEG 2000 test page correctly");
      const first = page.locator('[data-cell][data-page="1"] img');                  // the server's picture arrives when the draft is saved
      await expect.poll(() => first.evaluate((i: HTMLImageElement) => i.naturalWidth), { timeout: 30_000 }).toBeGreaterThan(0);
      expect(watch.calls.some((c) => c.url.startsWith("/api/split/thumb") && c.status === 200)).toBe(true);
    });
  });

  test("the start page lists the draft that was opened", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    const row = page.locator("table.split-drafts tbody tr").filter({ hasText: /\b13\b/ }).first();
    await expect(row).toBeVisible();
  });

  test("the library is browsed, searched by POST, filtered, and a file opened from it", async ({ page, watch }) => {
    await signIn(page, "A Manager", "setup/split");
    await page.getByRole("button", { name: "From the library" }).click();
    const table = page.getByRole("table", { name: /Files in the library/ });
    await expect(table.getByText("Combined Scan 2099.pdf")).toBeVisible();
    await expect(table.getByText("Board Minutes 2099-06.pdf")).toBeVisible();
    await expect(page.getByTestId("lib-count")).toContainText("3 of 3 files shown");

    // a confidential file is named by its kind, has no radio to choose, and its real name appears nowhere
    const held = table.getByRole("row").filter({ hasText: "a confidential file (kind: bank statement)" });
    await expect(held.getByRole("radio")).toBeDisabled();
    await expect(page.getByText("Bank Statement 2099-06.pdf")).toHaveCount(0);

    // the chips narrow the list and say pressed; the file's page count was counted from the file
    const kinds = page.getByRole("group", { name: "Kind of document" });
    await kinds.getByRole("button", { name: "minutes (1)" }).click();
    await expect(kinds.getByRole("button", { name: "minutes (1)" })).toHaveAttribute("aria-pressed", "true");
    await expect(table.getByText("Combined Scan 2099.pdf")).toHaveCount(0);
    await expect(table.getByRole("row").filter({ hasText: "Board Minutes" })).toContainText("text held");
    await kinds.getByRole("button", { name: "All kinds (3)" }).click();
    await expect(table.getByText("Combined Scan 2099.pdf")).toBeVisible();

    // a name is searched in a POST body and never in a web address
    await page.getByLabel("Search by file name").fill("combined");
    await page.getByLabel("Search by file name").press("Enter");
    await expect(table.getByText("Board Minutes 2099-06.pdf")).toHaveCount(0);
    expect(watch.calls.some((c) => c.method === "POST" && c.url === "/api/write/library/files")).toBe(true);
    expect(watch.calls.filter((c) => c.url.toLowerCase().includes("combined")), "the name reached a web address").toEqual([]);

    // choose it by keyboard (the radio), check it, open it
    await table.getByRole("radio", { name: /Combined Scan 2099\.pdf/ }).check();
    await expect(page.getByText(/Chosen: Combined Scan 2099\.pdf, 13 pages/)).toBeVisible();
    await page.getByRole("button", { name: "Check the file" }).click();
    await expect(page.getByRole("region", { name: "What opening will do" })).toContainText("13 pages");
    await page.getByRole("button", { name: "Open it for splitting" }).click();
    await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
    // a library file is the server's to draw: its pictures come from /api/split/thumb, the PDF itself is never sent to the browser
    await expect(page.locator(".split-pictures")).toHaveCount(0);
    const lib1 = page.locator('[data-cell][data-page="1"] img');
    await expect.poll(() => lib1.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
    await quiet(page, watch);                                  // the page pictures finish loading before the page is left
    expect(watch.calls.some((c) => c.url.startsWith("/api/split/thumb") && c.status === 200), "no server picture").toBe(true);
    expect(watch.calls.filter((c) => /\.pdf|\/api\/split\/file/.test(c.url)), "a PDF was downloaded").toEqual([]);

    // enlarging the cells asks the server for a sharper picture (the cell is longer than the 200 px one covers), and shows it in place
    const before = await lib1.evaluate((i: HTMLImageElement) => i.dataset.size);
    expect(before).toBe("small");
    await page.getByLabel("Thumbnail size").fill("220");
    await expect.poll(() => lib1.evaluate((i: HTMLImageElement) => i.dataset.size), { message: "the picture was upgraded" }).toBe("medium");
    expect(watch.calls.some((c) => c.url.includes("page=1&size=medium") && c.status === 200)).toBe(true);
    await expect.poll(() => lib1.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(200);        // the 400 px picture itself
    await quiet(page, watch);

    // back at the explorer, the file says a draft exists and links to it
    await page.evaluate(() => { window.location.hash = "#/setup/split"; });
    await page.getByRole("button", { name: "From the library" }).click();
    const row = page.getByRole("table", { name: /Files in the library/ }).getByRole("row").filter({ hasText: "Combined Scan 2099.pdf" });
    await expect(row).toContainText("draft exists");
  });

  test("the demo needs no server", async ({ page, watch }) => {
    await signIn(page, "A Manager", "setup/split/demo");
    await expect(page.getByRole("note").filter({ hasText: "Made-up pages" })).toBeVisible();
    await expect(page.getByLabel("Draft summary")).toContainText("120 pages");
    expect(watch.calls.filter((c) => c.url.startsWith("/api/split")), "the demo asked the server for a draft").toEqual([]);
  });
});

test.describe("signed in, other screens", () => {
  test("Records loads", async ({ page }) => {
    await signIn(page, "A Manager", "setup/records");
    await expect(page.getByRole("heading", { name: "Records", level: 1 })).toBeVisible();
  });

  test("Limits loads", async ({ page }) => {
    await signIn(page, "A Manager", "setup/limits");
    await expect(page.getByRole("heading", { name: "Limits", level: 1 })).toBeVisible();
  });
});
