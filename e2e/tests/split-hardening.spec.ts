import type { Page } from "@playwright/test";
import { expect, libraryBusy, moveDraft, seed, signIn, test, writeSplit } from "./fixtures";

// The console's wiring for the splitter's backend hardening (docs/console/screens/split.md; docs/pdf-splitter.md 6.7 and 8.1): a confidential file's
// withheld text, a library that could not be read, the plan fingerprint, and an apply that did not finish. The server's states are made through the
// launcher's test-only routes (a library read that fails, a draft killed mid-apply, the confidential statement); made-up data only.

const BUSY = "The library could not be read just now. Nothing was changed.";
const HELD = "This file is confidential: page text, titles and reasons are hidden until the private view is open.";
const CHANGED = "The draft changed since you reviewed it: the plan is now different. Review it again.";
const BROWSER_LOG = [/Failed to load resource/];                         // the browser's own line for a 403 or a 503 it was told to expect

async function openDraft(page: Page, id: string) {
  await page.goto(`/#/setup/split/${id}`);
  await expect(page.getByLabel("Draft summary")).toContainText(/\d+ pages/);
}

async function openReview(page: Page) {
  await page.getByRole("button", { name: "Review and split" }).first().click();
  await expect(page.getByRole("heading", { name: /^Review: / })).toBeVisible();
}

test.describe("a confidential file", () => {
  test.use({ allowConsole: BROWSER_LOG, repeatCeiling: 8 });                       // opening and closing the private view reloads the console twice

  test("says in words that its text is hidden, keeps the numbers, names nothing in the title, and opens the private view from the notice", async ({ page }) => {
    await signIn(page);
    const id = await seed(page, "confidential");
    await openDraft(page, id);
    const note = page.getByRole("note", { name: "This file is confidential" });
    await expect(note).toContainText(HELD);
    await expect(page.getByLabel("Draft summary")).toContainText("1 pages");
    await expect(page.getByText("A confidential file")).toBeVisible();
    await expect(page).toHaveTitle("Split document: Draft - jason");                 // no file name, no page count
    await expect(page.getByText("Bank Statement")).toHaveCount(0);
    expect(await page.locator("[title]").evaluateAll((els) => els.map((e) => e.getAttribute("title")).join("|"))).not.toMatch(/Bank|Statement|statement/);

    await openReview(page);                                                          // the review degrades: counts and states stay, titles do not
    const review = page.locator(".split-review");
    await expect(review.getByRole("note", { name: "This file is confidential" })).toBeVisible();
    await expect(review.getByText("hidden", { exact: true })).toBeVisible();
    await expect(review.getByText("Pages add up")).toBeVisible();
    await page.keyboard.press("Escape");

    // the private view, from the notice: why and for how long, then the notice goes (the page reloads, so every screen asks again)
    await note.getByRole("button", { name: "Open the private view…" }).click();
    await page.getByRole("textbox", { name: "Why" }).fill("board review");
    await page.getByRole("button", { name: /^Open the private view as/ }).click();
    await expect(page.getByRole("region", { name: "Private view" })).toBeVisible();
    await expect(page.getByRole("note", { name: "This file is confidential" })).toHaveCount(0);
    await expect(page.getByText("Confidential", { exact: true })).toBeVisible();     // the badge stays: the file is still confidential
    await page.getByRole("button", { name: "Close private view" }).click();
    await expect(page.getByRole("note", { name: "This file is confidential" })).toBeVisible();
  });
});

test.describe("a library that could not be read", () => {
  test.use({ allowConsole: BROWSER_LOG, allowStatus: [503] });
  test.afterEach(async ({ page }) => { await libraryBusy(page, false); });

  test("opening a library file: a calm notice that counts the wait in words, then Try again opens it", async ({ page }) => {
    await signIn(page, "A Manager", "setup/split");
    await page.getByRole("button", { name: "From the library" }).click();
    await page.getByRole("table", { name: /Files in the library/ }).getByRole("radio", { name: /Combined Scan 2099\.pdf/ }).check();
    await libraryBusy(page, true);
    await page.getByRole("button", { name: "Check the file" }).click();
    await expect(page.getByText(BUSY)).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);                              // not a generic error
    await expect(page.getByRole("button", { name: /^Try again in \d+ seconds?$/ })).toBeDisabled();
    await libraryBusy(page, false);
    const again = page.getByRole("button", { name: "Try again", exact: true });
    await expect(again).toBeEnabled({ timeout: 15_000 });                              // after the server's Retry-After
    await again.click();
    await expect(page.getByRole("region", { name: "What opening will do" })).toContainText("13 pages");
    await expect(page.getByText(BUSY)).toHaveCount(0);
  });

  test("a draft opened while the library is busy is treated as confidential, says why, and its pictures wait; both clear when the library answers", async ({ page }) => {
    await signIn(page);
    const id = await seed(page, "library");
    await libraryBusy(page, true);
    await openDraft(page, id);
    await expect(page.getByRole("note", { name: "This file is confidential" })).toContainText("treated as confidential until it can be");
    await expect(page.getByText(BUSY)).toBeVisible();                                  // the pictures: a 503 with Retry-After
    await expect(page.getByRole("button", { name: /^Try again in \d+ seconds?$/ })).toBeDisabled();
    await libraryBusy(page, false);
    const again = page.getByRole("button", { name: "Try again", exact: true });
    await expect(again).toBeEnabled({ timeout: 15_000 });
    await again.click();
    await expect(page.getByText(BUSY)).toHaveCount(0);
    await expect.poll(() => page.locator('[data-cell][data-page="1"] img').evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
    await page.getByRole("button", { name: "Check again" }).click();
    await expect(page.getByRole("note", { name: "This file is confidential" })).toHaveCount(0);
  });

  test("the review says the duplicate check was skipped and blocks the write until it can run; a library that goes busy at the write is a notice too", async ({ page }) => {
    await signIn(page);
    const id = await seed(page, "library");
    await openDraft(page, id);
    await libraryBusy(page, true);
    await openReview(page);
    const skipped = page.getByRole("group", { name: "The duplicate check was skipped" });
    await expect(skipped).toContainText("The duplicate check was skipped because the library was busy; apply will refuse until it can run.");
    await page.getByRole("button", { name: "Preview the split" }).click();
    const write = page.getByRole("button", { name: /^Write 5 files/ });
    await expect(write).toBeDisabled();
    await expect(page.locator("#split-write-why")).toContainText("Writing is blocked");
    await libraryBusy(page, false);
    await skipped.getByRole("button", { name: "Check again" }).click();
    await expect(skipped).toHaveCount(0);
    await page.getByRole("button", { name: "Preview the split" }).click();
    await expect(write).toBeEnabled();
    await libraryBusy(page, true);                                                    // busy again just before the write: the server refuses it, in a notice
    await write.click();
    await expect(page.getByText(BUSY)).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await libraryBusy(page, false);
    await page.locator(".split-review").getByRole("button", { name: "Try again", exact: true }).click({ timeout: 15_000 });   // (the pictures behind the drawer have their own)
    await expect(page.getByRole("heading", { name: "The split was written" })).toBeVisible();
  });
});

test.describe("the plan fingerprint", () => {
  test.use({ allowConsole: BROWSER_LOG });                                         // the browser's own line for the 409 it was told to expect
  test("a draft that moved after the review is refused in words, the new review replaces the old, and a fresh confirm writes it", async ({ page, watch }) => {
    await signIn(page);
    const id = await seed(page, "upload");
    await openDraft(page, id);
    await openReview(page);
    await page.getByRole("button", { name: "Preview the split" }).click();
    const write = page.getByRole("button", { name: /^Write 5 files/ });
    await expect(write).toBeVisible();
    await moveDraft(page, id, [6]);                                                   // another tab marks page 6
    await write.click();
    const note = page.getByRole("group", { name: CHANGED });
    await expect(note).toContainText("Nothing was written");
    await expect(page.getByRole("heading", { name: CHANGED })).toBeFocused();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /^Review: 6 documents/ })).toBeVisible();   // the returned review is the one shown
    await expect(page.getByRole("button", { name: /^Write / })).toHaveCount(0);        // a fresh confirm is required
    const sent = watch.calls.filter((c) => c.method === "POST" && c.url === `/api/write/split/${id}`);
    expect(sent.length).toBeGreaterThan(0);
    await page.getByRole("button", { name: "Preview the split" }).click();
    await page.getByRole("button", { name: /^Write 6 files/ }).click();
    await expect(page.getByRole("heading", { name: "The split was written" })).toBeVisible();
  });

  test("the console's confirmed apply must carry the fingerprint: without one the server refuses and writes nothing", async ({ page }) => {
    await signIn(page);
    const id = await seed(page, "upload");
    const r = await writeSplit(page, id, { act: "apply", dryRun: false, confirm: true });
    expect(r.status()).toBe(400);
    expect((await r.json()).error).toContain("plan fingerprint");
    const after = await (await page.request.get(`/api/split-session?id=${id}`)).json();
    expect(after.status).toBe("draft");
  });
});

test.describe("an apply that did not finish", () => {
  test("the draft list and the draft say so in words; Finish it writes nothing until confirmed, then finishes", async ({ page }) => {
    await signIn(page);
    const id = await seed(page, "unfinished");
    await page.goto("/#/setup/split");
    const row = page.locator(`tr[data-split="${id}"]`);
    await expect(row).toContainText("An earlier apply did not finish");
    await expect(row).toContainText("2 of 5 files written");
    await row.getByRole("link").first().click();
    const panel = page.getByRole("region", { name: "An earlier apply did not finish" });
    await expect(panel).toContainText("2 of 5 files were written");
    await expect(panel).toContainText("until you choose and confirm");
    await panel.getByRole("button", { name: "Finish it" }).click();
    await expect(panel.getByRole("group", { name: "Finish it" })).toBeVisible();      // the stamp explains; nothing is written yet
    expect((await (await page.request.get(`/api/split-session?id=${id}`)).json()).unfinishedApply.written).toBe(2);
    await panel.getByRole("button", { name: "Yes, do it" }).click();
    await expect(page.getByRole("heading", { name: "The earlier apply was finished" })).toBeFocused();
    const after = await (await page.request.get(`/api/split-session?id=${id}`)).json();
    expect(after.status).toBe("applied");
    expect(after.unfinishedApply).toBeUndefined();
  });

  test("Roll it back asks first, puts the draft back as it was, and deletes nothing", async ({ page }) => {
    await signIn(page);
    const id = await seed(page, "unfinished");
    await openDraft(page, id);
    const panel = page.getByRole("region", { name: "An earlier apply did not finish" });
    await panel.getByRole("button", { name: "Roll it back" }).click();
    await panel.getByRole("button", { name: "Cancel" }).click();
    expect((await (await page.request.get(`/api/split-session?id=${id}`)).json()).unfinishedApply).toBeTruthy();   // cancelled: untouched
    await panel.getByRole("button", { name: "Roll it back" }).click();
    await panel.getByRole("button", { name: "Yes, do it" }).click();
    await expect(page.getByRole("heading", { name: "The earlier apply was rolled back" })).toBeFocused();
    await expect(page.locator('[data-note="unfinished"]')).toContainText("nothing was deleted");
    const after = await (await page.request.get(`/api/split-session?id=${id}`)).json();
    expect(after.status).toBe("draft");
    await expect(page.getByRole("button", { name: "Review and split" }).first()).toBeEnabled();      // a draft again
  });
});
