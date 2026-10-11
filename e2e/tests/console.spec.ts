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

  test("a PDF is checked, opened, marked, undone, reviewed, previewed, and written", async ({ page, watch }) => {
    await signIn(page, "A Manager", "setup/split");
    await page.locator("#split-file").setInputFiles(sample);
    await expect(page.getByText(/sample\.pdf, /)).toBeVisible();
    await page.getByRole("button", { name: "Check the file" }).click();
    await expect(page.getByRole("region", { name: "What opening will do" })).toContainText("13 pages");
    await page.getByRole("button", { name: "Open it for splitting" }).click();

    // the editor: page pictures come from /api/split/thumb (the PyMuPDF renderer)
    await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
    const first = page.locator('[data-cell][data-page="1"] img');
    await expect(first).toHaveJSProperty("complete", true);
    await expect.poll(() => first.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
    expect(watch.calls.some((c) => c.url.startsWith("/api/split/thumb") && c.status === 200)).toBe(true);

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

  test("the start page lists the draft that was opened", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    const row = page.locator("table.split-drafts tbody tr").first();
    await expect(row).toContainText("13");
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
    await quiet(page, watch);                                  // the page pictures finish loading before the page is left

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
