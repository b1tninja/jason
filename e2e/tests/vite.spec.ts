import { expect, quiet, test } from "./fixtures";

// The console as a person runs it while developing: the Vite dev server, which proxies /api and /auth to jason-web.
test.use({ allowConsole: [/status of 401/], repeatCeiling: 4 });      // React's strict mode runs each effect twice in dev

test("Sign in with Google reaches the server through the dev proxy, not Vite's own index.html", async ({ page, request }) => {
  const res = await request.get("/auth/google?next=%23%2Fsetup%2Fsplit", { maxRedirects: 0 });
  expect(res.status()).toBe(302);
  expect(res.headers()["location"]).toMatch(/^https:\/\/accounts\.google\.com\//);
  await page.goto("/#/setup/split");
  const link = page.getByRole("link", { name: /sign in with google/i }).first();
  await expect(link).toHaveAttribute("href", /^\/auth\/google\?next=/);
});

test("the splitter, signed out, settles in the dev server too", async ({ page, watch }) => {
  await page.goto("/#/setup/split");
  await expect(page.getByText("Sign in with Google to open this.")).toBeVisible();
  await quiet(page, watch);
  const settled = watch.count();
  await page.waitForTimeout(4000);
  expect(watch.count() - settled).toBe(0);
});
