import { test as base, expect, type Page, type Request } from "@playwright/test";

/** What the page asked of the server, and what it said to the console, for the guards every test gets. */
export interface Watch {
  /** every `/api` or `/auth` request the page made, with its status once answered (0 until then, -1 failed or aborted) */
  calls: { method: string; url: string; status: number; done: boolean }[];
  errors: string[];
  /** The `/api` requests so far. */
  count(): number;
}

export interface Options {
  /** console errors to ignore, by pattern (a signed-out page shows the browser's own line for each 401) */
  allowConsole: RegExp[];
  /** the most times one URL may be asked in a test: a refetch loop goes far past it */
  repeatCeiling: number;
}

const mine = (u: string) => { const p = new URL(u).pathname; return p.startsWith("/api") || p.startsWith("/auth"); };

export const test = base.extend<{ watch: Watch } & Options>({
  allowConsole: [[], { option: true }],
  repeatCeiling: [3, { option: true }],
  watch: [async ({ page, allowConsole, repeatCeiling }, use) => {
    const calls: Watch["calls"] = [];
    const open = new Map<Request, Watch["calls"][number]>();
    const errors: string[] = [];
    page.on("request", (r) => {
      if (!mine(r.url())) return;
      const row = { method: r.method(), url: new URL(r.url()).pathname + new URL(r.url()).search, status: 0, done: false };
      calls.push(row); open.set(r, row);
    });
    page.on("response", async (r) => {
      const row = open.get(r.request());
      if (!row) return;
      row.status = r.status();
      if (r.status() >= 500) errors.push(`${r.request().method()} ${row.url} answered ${r.status()}: ${(await r.text().catch(() => "")).slice(0, 300)}`);
    });
    page.on("requestfinished", (r) => { const row = open.get(r); if (row) row.done = true; });
    page.on("requestfailed", (r) => { const row = open.get(r); if (row) { row.done = true; row.status = -1; } });
    page.on("console", (m) => { if (m.type() === "error" && !allowConsole.some((re) => re.test(m.text()))) errors.push(m.text()); });
    page.on("pageerror", (e) => errors.push(`page error: ${e.message}`));
    const watch: Watch = { calls, errors, count: () => calls.length };
    await use(watch);
    // After the test: nothing logged as an error, nothing still pending, and no read asked over and over (a write is an act the test chose, so it is not counted).
    for (let i = 0; i < 30 && calls.some((c) => !c.done); i++) await page.waitForTimeout(100);     // a read that is merely slow gets 3 seconds
    expect(errors, "console errors").toEqual([]);
    const pending = calls.filter((c) => !c.done).map((c) => `${c.method} ${c.url}`);
    expect(pending, "requests still pending at the end").toEqual([]);
    const seen = new Map<string, number>();
    const how = new Map<string, number[]>();
    for (const c of calls) { if (c.method !== "GET") continue; const k = `${c.method} ${c.url}`; seen.set(k, (seen.get(k) ?? 0) + 1); how.set(k, [...(how.get(k) ?? []), c.status]); }
    const repeated = [...seen].filter(([, n]) => n > repeatCeiling).map(([k, n]) => `${k} x${n} (statuses ${how.get(k)!.join(", ")}; -1 is aborted)`);
    expect(repeated, `a URL asked more than ${repeatCeiling} times`).toEqual([]);
  }, { auto: true }],
});

export { expect };

/** Sign in as a roster person through the launcher's test-only route, then land on `hash` (a console route). */
export async function signIn(page: Page, name = "A Manager", hash = "") {
  await page.goto(`/__e2e/sign-in?name=${encodeURIComponent(name)}&next=${encodeURIComponent("/")}`);
  if (hash) await page.goto(`/#/${hash.replace(/^#?\/?/, "")}`);
}

/** Wait until the page has been quiet: no `/api` request started for `ms`. */
export async function quiet(page: Page, watch: Watch, ms = 800) {
  let last = -1;
  while (watch.count() !== last) { last = watch.count(); await page.waitForTimeout(ms); }
}
