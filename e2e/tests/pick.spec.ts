import type { Page } from "@playwright/test";
import { expect, quiet, signIn, test, type Watch } from "./fixtures";

// Choosing from the person's own Google Drive (docs/google-picker.md), through the real start and callback routes. Google is stood in for by the
// launcher (e2e/pick_fake.py): the start route leaves for /__e2e/google/pick, which checks the request the way Google's documentation describes it
// and sends the browser back with picked_file_ids and a code; Drive holds a few made-up files. Nothing reaches Google.

const SLOT = "records/5200/minutes";

async function setSwitch(page: Page, on: boolean) {
  const r = await page.request.get(`/__e2e/limit?key=pick.enabled${on ? "&value=on" : ""}`);
  expect(r.ok()).toBe(true);
}
async function scenario(page: Page, name: string) {
  const r = await page.request.get(`/__e2e/pick-scenario?name=${name}&reset=1`);
  expect(r.ok()).toBe(true);
}
/** Let what the page has asked finish. A request cut off by leaving the page is never reported as finished, and the suite's guard would call it pending. */
async function settle(page: Page, watch: Watch) {
  await quiet(page, watch, 400);
  await expect.poll(() => watch.calls.filter((c) => !c.done).length, { timeout: 20_000 }).toBe(0);
}
/** Press the button and wait until the console is back with the result list drawn. */
async function leaveAndReturn(page: Page, watch: Watch, within = page.locator("body")) {
  await settle(page, watch);
  await within.getByRole("button", { name: "Choose from my Google Drive" }).first().click();
  await expect(page.getByRole("heading").filter({ hasText: /What you picked|Nothing was kept|That pick is over/ })).toBeVisible();
}
/** The start page with the From Drive tab open. */
async function driveTab(page: Page) {
  await signIn(page, "A Manager", "setup/split");
  await page.getByRole("button", { name: "From Drive" }).click();
}

test.describe("choosing from my own Google Drive", () => {
  test.use({ repeatCeiling: 12 });            // leaving for Google and coming back loads the console again, and each load asks for the officers once
  test.beforeEach(async ({ page }) => { await setSwitch(page, true); await scenario(page, "ok"); });
  test.afterEach(async ({ page }) => { await setSwitch(page, false); });

  test("the splitter: the button explains, leaves for Google, comes back with the token gone, lists the rows, and a held row opens as a draft", async ({ page, watch }) => {
    await driveTab(page);
    await expect(page.getByText("Google will ask which files to share with jason. jason reads each file once and keeps a copy; it writes nothing to Drive and does not keep your Google sign-in.").first()).toBeVisible();
    const left: string[] = [];
    page.on("request", (r) => { if (r.isNavigationRequest()) left.push(r.url()); });
    await leaveAndReturn(page, watch);

    // it left for the (fake) Google's page with the route to come back to, and nothing else of the person's
    const start = left.find((u) => u.includes("/auth/google/pick?"))!;
    expect(new URL(start).searchParams.get("next")).toBe("#/setup/split");
    expect(new URL(start).searchParams.get("purpose")).toBe("split");
    expect(left.some((u) => u.includes("/__e2e/google/pick?"))).toBe(true);
    const sent = await (await page.request.get("/__e2e/pick-last")).json();
    expect(sent).toMatchObject({ trigger_onepick: "true", scope: "https://www.googleapis.com/auth/drive.file", access_type: "online", response_type: "code", allow_multiple: "true", mimetypes: "application/pdf" });

    // back: the token is out of the address, the heading has the focus, one status line says how it went
    expect(page.url()).not.toContain("pick=");
    expect(new URL(page.url()).hash).toBe("#/setup/split");
    await expect(page.getByRole("heading", { name: "What you picked from Google Drive" })).toBeFocused();
    await expect(page.getByRole("status").filter({ hasText: "2 files kept." })).toHaveCount(1);
    const rows = page.getByRole("list", { name: "Files you picked" }).getByRole("listitem");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toContainText("Combined Scan 2099.pdf");
    await expect(rows.nth(0)).toContainText("Kept");
    await expect(rows.nth(0)).toContainText("13 pages");

    // a held row opens as a draft: check it, then open it
    await rows.nth(0).getByRole("button", { name: "Check the file: file 1" }).click();
    await expect(rows.nth(0).getByText(/13 pages, .* It keeps a copy/)).toBeVisible();
    await rows.nth(0).getByRole("button", { name: "Open it for splitting: file 1" }).click();
    await expect(page.getByLabel("Draft summary")).toContainText("13 pages");
    expect(new URL(page.url()).hash).toMatch(/^#\/setup\/split\/[0-9a-f]{8,16}$/);
    await settle(page, watch);
  });

  test("the held copies are listed on the start page by number and size, with no name, and open as a draft", async ({ page, watch }) => {
    await driveTab(page);
    await leaveAndReturn(page, watch);
    await page.goto("/#/setup/split");
    await page.reload();
    const list = page.getByRole("list", { name: "Copies held from Drive" });
    await expect(list.getByRole("listitem")).toHaveCount(2);
    const text = await list.innerText();
    expect(text).toMatch(/Copy 1/);
    expect(text).toMatch(/\d+ pages?, [\d.]+ (KB|MB), picked 20\d\d-\d\d-\d\d/);
    expect(text).not.toMatch(/Combined Scan|Board Minutes|\.pdf/);
    await list.getByRole("listitem").first().getByRole("button", { name: /^Check this copy: copy/ }).click();
    await list.getByRole("listitem").first().getByRole("button", { name: /^Open as a draft: copy/ }).click();
    await expect(page.getByLabel("Draft summary")).toContainText(/\d+ pages/);
    await settle(page, watch);
  });

  test("a mixed pick: kept rows with buttons, each refusal in the server's words with none", async ({ page, watch }) => {
    await scenario(page, "mixed");
    await driveTab(page);
    await leaveAndReturn(page, watch);
    await expect(page.getByRole("status").filter({ hasText: "2 of 6 files kept. 4 files refused; each says why." })).toHaveCount(1);
    const rows = page.getByRole("list", { name: "Files you picked" }).getByRole("listitem");
    await expect(rows).toHaveCount(6);
    await expect(rows.nth(1)).toContainText("Refused: a folder");
    await expect(rows.nth(1)).toContainText("choose the PDFs themselves");
    await expect(rows.nth(2)).toContainText("Refused: not a pdf");
    await expect(rows.nth(3)).toContainText("Refused: too large");
    await expect(rows.nth(4)).toContainText("Refused: no access");
    for (const i of [1, 2, 3, 4]) await expect(rows.nth(i).getByRole("button")).toHaveCount(0);
    await expect(rows.nth(5)).toContainText("Kept");
    await expect(rows.nth(5).getByRole("button", { name: "Check the file: file 6" })).toBeVisible();
  });

  test("nothing picked, and Google refusing, are said whole", async ({ page, watch }) => {
    await scenario(page, "none");
    await driveTab(page);
    await leaveAndReturn(page, watch);
    await expect(page.getByRole("heading", { name: "Nothing was kept" })).toBeFocused();
    await expect(page.getByText("Nothing was picked.", { exact: true })).toBeVisible();
    await scenario(page, "denied");
    await leaveAndReturn(page, watch, page.locator(".pick-outcome"));
    await expect(page.getByText("Nothing was picked: Google's Picker was closed or the permission was not given.")).toBeVisible();
    await expect(page.getByRole("list", { name: "Files you picked" })).toHaveCount(0);
  });

  test.describe("a return that is not the one that was sent", () => {
    test.use({ allowConsole: [/status of 400/] });          // the browser's own line for the server's refusal page
    test("is refused by the server and keeps nothing", async ({ page, watch }) => {
      await scenario(page, "badstate");
      await driveTab(page);
      await settle(page, watch);
      await page.getByRole("button", { name: "Choose from my Google Drive" }).first().click();
      await expect(page.getByText("The pick did not come back as it was sent: start it again from the button.")).toBeVisible();
      await page.goto("/#/setup/split");
      await expect(page.getByRole("heading", { name: "Open a PDF" })).toBeVisible();
      await expect(page.getByRole("list", { name: "Copies held from Drive" })).toHaveCount(0);
    });
  });

  test.describe("a result already read", () => {
    test.use({ allowConsole: [/status of 404/] });          // the browser's own line for the refused re-read
    test("says the pick is over, in words, and removes the token from the address", async ({ page, watch }) => {
      let token = "";
      page.on("request", (r) => { const m = /[?&]pick=([^&#]+)/.exec(r.url()); if (m) token = m[1]; });
      await driveTab(page);
      await leaveAndReturn(page, watch);
      expect(token).not.toBe("");
      await page.goto(`/?pick=${token}#/setup/split`);
      await expect(page.getByRole("heading", { name: "That pick is over" })).toBeFocused();
      await expect(page.getByText("That pick was already read, or it has expired. Choose again.")).toBeVisible();
      expect(page.url()).not.toContain("pick=");
    });
  });

  test.describe("a record slot", () => {
    test.use({ allowConsole: [/status of 403/] });          // the browser's own line for the job queue, which is not a manager's to read
    test("the button is in the chooser, and a held row is pinned through the usual preview and confirm", async ({ page, watch }) => {
      await signIn(page, "A Manager", `setup/records/${encodeURIComponent(SLOT)}`);
      await page.getByRole("button", { name: "Choose from Drive" }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.getByRole("button", { name: "Choose from my Google Drive" })).toBeVisible();
      await expect(dialog.getByText("Loading the folder")).toHaveCount(0, { timeout: 30_000 });      // Drive's own listing has answered
      await leaveAndReturn(page, watch, dialog);
      expect(page.url()).not.toContain("pick=");
      expect(new URL(page.url()).hash).toBe(`#/setup/records/${encodeURIComponent(SLOT)}`);
      const sent = await (await page.request.get("/__e2e/pick-last")).json();
      expect(sent.state).toBeTruthy();
      await page.getByRole("button", { name: /^Pin file 2 to / }).click();     // the 2-page minutes file
      await page.getByLabel(/Period this file is for/).fill("2099-06");
      await page.getByRole("button", { name: "Preview the pin" }).click();
      await expect(page.getByRole("region", { name: "What will be recorded" })).toBeVisible();
      await page.getByRole("button", { name: /^Keep file 2 and pin it to / }).click();
      await expect(page.getByText(/Recorded as A Manager\./)).toBeVisible();
      await settle(page, watch);
    });
  });
});

test.describe("switched off", () => {
  test("a calm line says so and who can turn it on, and there is no button", async ({ page }) => {
    await setSwitch(page, false);
    await driveTab(page);
    await expect(page.getByText("Picking from your own Drive is off for this community.")).toBeVisible();
    await expect(page.getByText(/administrator can turn it on/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose from my Google Drive" })).toHaveCount(0);
    const start = await page.request.get("/auth/google/pick?next=%23%2Fsetup%2Fsplit&purpose=split", { maxRedirects: 0 });
    expect(start.status()).toBe(403);
  });
});
