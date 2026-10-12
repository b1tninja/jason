import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import * as pick from "../lib/pick";
import { HeldPanel, PickOutcome } from "./PickPanels";
import { PickStart } from "./PickStart";
import { SplitView, resetDemo } from "./SplitView";

vi.mock("../lib/pick", async (orig) => ({ ...(await orig<typeof import("../lib/pick")>()), navigateTo: vi.fn() }));

beforeEach(() => { resetServerSession(); resetDemo(); pick.resetPickReturn(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); window.location.hash = ""; vi.mocked(pick.navigateTo).mockClear(); });

interface Call { url: string; method: string; body?: Record<string, unknown> }
type Reply = { status?: number; body: unknown };
/** A made-up server: the session says whether picking is on; each other route answers a fixed reply or a function of the body. */
function serve(session: Record<string, unknown>, routes: Record<string, unknown | ((b: Record<string, unknown> | undefined) => Reply)> = {}) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    if (u.startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn: { name: "A Manager", role: "treasurer" }, ...session }), { status: 200 });
    calls.push({ url: u, method, body });
    const key = Object.keys(routes).find((k) => u.startsWith(k));
    const r = key ? routes[key] : { error: "no route" };
    const out: Reply = typeof r === "function" ? (r as (b: Record<string, unknown> | undefined) => Reply)(body) : { body: r };
    return new Response(JSON.stringify(out.body), { status: out.status ?? 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}

const ON = { pick: { enabled: true, start: "/auth/google/pick", result: "/api/drive/pick/result" } };
const SHA_A = "a".repeat(64), SHA_B = "b".repeat(64);
const row = (o: Partial<pick.PickRow>): pick.PickRow => ({ outcome: "held", reason: "", words: "Read once and held. The original in Drive was not changed.", heldId: SHA_A, size: 20480, pages: 13, name: "Minutes.pdf", ...o });
const REFUSED = (reason: string, words: string, name = ""): pick.PickRow => row({ outcome: "refused", reason, words, heldId: "", size: 0, pages: 0, name });
const result = (rows: pick.PickRow[], purpose = "split", error = ""): pick.PickResult => ({ purpose: purpose as pick.PickPurpose, slot: "", error, report: rows.length ? { dryRun: false, counts: {}, rows } : null });

describe("the button", () => {
  it("says in words what will happen, then leaves for the server's start route with the current route and the purpose", async () => {
    serve(ON);
    window.location.hash = "#/setup/records/records%2F5200%2Fminutes";
    render(<PickStart purpose="slot" slot="records/5200/minutes" />);
    const button = await screen.findByRole("button", { name: "Choose from my Google Drive" });
    expect(screen.getByText(/Google will ask which files to share with jason\. jason reads each file once and keeps a copy; it writes nothing to Drive and does not keep your Google sign-in\./)).toBeTruthy();
    expect(button.getAttribute("aria-describedby")).toBeTruthy();
    await userEvent.click(button);
    const url = String(vi.mocked(pick.navigateTo).mock.calls[0][0]);
    const q = new URL(url, "http://x").searchParams;
    expect(url.startsWith("/auth/google/pick?")).toBe(true);
    expect(q.get("next")).toBe("#/setup/records/records%2F5200%2Fminutes");
    expect(q.get("slot")).toBe("records/5200/minutes");
    expect(q.get("purpose")).toBe("slot");
    expect(url).not.toMatch(/token|code|file/i);
  });

  it("is a calm line, with who can turn it on, when the community has it off or the session says nothing", async () => {
    serve({ pick: { enabled: false, start: "/auth/google/pick", result: "/api/drive/pick/result" } });
    render(<PickStart purpose="split" />);
    expect(await screen.findByText(/Picking from your own Drive is off for this community/)).toBeTruthy();
    expect(screen.getByText(/administrator can turn it on/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Setup, Limits" }).getAttribute("href")).toBe("#/setup/limits");
    expect(screen.queryByRole("button", { name: "Choose from my Google Drive" })).toBeNull();
    cleanup(); resetServerSession();
    serve({});
    render(<PickStart purpose="split" />);
    expect(await screen.findByText(/is off for this community/)).toBeTruthy();
  });

  it("is on the splitter's From Drive tab", async () => {
    serve(ON, { "/api/split-sessions": { sessions: [], limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 } }, "/api/limits": { limits: [] } });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await userEvent.click(await screen.findByRole("button", { name: "From Drive" }));
    expect(await screen.findByRole("button", { name: "Choose from my Google Drive" })).toBeTruthy();
  });
});

describe("coming back from Google", () => {
  const two = [row({}), row({ outcome: "already held", words: "Already held; nothing new was kept.", heldId: SHA_B, name: "Bylaws.pdf", pages: 2, size: 900 }),
    REFUSED("folder", "That is a folder. A folder picked here does not give jason its files: choose the PDFs themselves. Nothing was kept.", "Records"),
    REFUSED("too_large", "That file is 900 MB; the largest jason reads is 200 MB.", "Huge scan.pdf"),
    REFUSED("not_pdf", "jason takes a PDF here, and that is a Google Doc. Nothing was kept.", "Agenda"),
    REFUSED("no_access", "The account cannot open this file. Nothing was kept.")];

  const START = { "/api/split-sessions": { sessions: [], limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 } }, "/api/limits": { limits: [] }, "/api/approvals": { people: [] } };

  async function back(routes: Record<string, unknown | ((b: Record<string, unknown> | undefined) => Reply)>, token = "tok-123456789012345678") {
    window.history.replaceState(null, "", `/?pick=${token}#/setup/split`);
    const calls = serve(ON, { ...START, ...routes });
    render(<SplitView />);
    return calls;
  }

  it("reads the token once, removes it from the address at once, and lists every row in jason's words", async () => {
    const calls = await back({ "/api/drive/pick/result": result(two) });
    const heading = await screen.findByRole("heading", { name: "What you picked from Google Drive" });
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("#/setup/split");
    const reads = calls.filter((c) => c.url === "/api/drive/pick/result");
    expect(reads).toHaveLength(1);
    expect(reads[0]).toMatchObject({ method: "POST", body: { token: "tok-123456789012345678" } });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    const status = screen.getAllByRole("status").find((s) => /kept/.test(s.textContent ?? ""));
    expect(status?.textContent).toMatch(/2 of 6 files kept\. 4 files refused; each says why/);
    const list = screen.getByRole("list", { name: "Files you picked" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(6);
    expect(items[0].textContent).toMatch(/File 1: Minutes\.pdf.*Kept.*13 pages, 20 KB/);
    expect(items[1].textContent).toMatch(/Already kept.*2 pages/);
    expect(items[2].textContent).toMatch(/Refused: a folder.*choose the PDFs themselves/);
    expect(items[3].textContent).toMatch(/Refused: too large.*900 MB/);
    expect(items[4].textContent).toMatch(/Refused: not a pdf/i);
    expect(items[5].textContent).toMatch(/File 6 .*Refused: no access/);
    for (const i of [2, 3, 4, 5]) expect(within(items[i]).queryByRole("button")).toBeNull();      // a refused row has no button
    expect(within(items[0]).getByRole("button", { name: "Check the file: file 1" })).toBeTruthy();
  });

  it("reads once even if the screen mounts again", async () => {
    const calls = await back({ "/api/drive/pick/result": result(two.slice(0, 1)) });
    await screen.findByRole("heading", { name: "What you picked from Google Drive" });
    cleanup();
    render(<SplitView />);
    await screen.findByRole("heading", { name: "What you picked from Google Drive" });
    expect(calls.filter((c) => c.url === "/api/drive/pick/result")).toHaveLength(1);
  });

  it("closes the list and does not bring it back", async () => {
    await back({ "/api/drive/pick/result": result(two.slice(0, 1)) });
    await userEvent.click(await screen.findByRole("button", { name: "Close this list" }));
    expect(screen.queryByRole("heading", { name: "What you picked from Google Drive" })).toBeNull();
    cleanup();
    render(<SplitView />);
    await screen.findByRole("heading", { name: "Open a PDF" });
    expect(screen.queryByRole("heading", { name: "What you picked from Google Drive" })).toBeNull();
  });

  it("opens a held row as a draft: a dry run first in the server's words, then the open, then the draft's route", async () => {
    const calls = await back({
      "/api/drive/pick/result": result(two.slice(0, 1)),
      "/api/write/split/new": (b: Record<string, unknown> | undefined) => ({ body: b?.dryRun
        ? { ok: true, dryRun: true, would: { act: "open", pages: 13, size: 20480, by: "A Manager", keeps: "a copy under the splitter's own folder and a draft session" }, note: "A dry run: nothing was kept." }
        : { ok: true, session: { id: "d1e2f3a4" } } }),
    });
    await userEvent.click(await screen.findByRole("button", { name: "Check the file: file 1" }));
    expect(await screen.findByText(/13 pages, 20 KB\. It keeps a copy under the splitter's own folder/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Open it for splitting: file 1" }));
    await waitFor(() => expect(window.location.hash).toBe("#/setup/split/d1e2f3a4"));
    const opens = calls.filter((c) => c.url === "/api/write/split/new");
    expect(opens.map((c) => c.body?.dryRun)).toEqual([true, false]);
    expect(opens[0].body).toMatchObject({ act: "open", ref: { kind: "held", id: SHA_A }, by: "A Manager" });
  });

  it("says in words that the pick is over when the server has no such result", async () => {
    await back({ "/api/drive/pick/result": () => ({ status: 404, body: { error: "No such result (it is read once, and it expires). Choose from Drive again." } }) });
    expect(await screen.findByRole("heading", { name: "That pick is over" })).toBeTruthy();
    expect(screen.getByText(/already read, or it has expired\. Choose again\./)).toBeTruthy();
    expect(window.location.search).toBe("");
  });

  it("shows a result that is an error with no files whole, for Google refused, nothing picked, or a state that ran out", async () => {
    const words = "Nothing was picked: Google's Picker was closed or the permission was not given.";
    await back({ "/api/drive/pick/result": result([], "split", words) });
    expect(await screen.findByRole("heading", { name: "Nothing was kept" })).toBeTruthy();
    expect(screen.getByText(words)).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Files you picked" })).toBeNull();
  });

  it("asks for a sign-in when the session ended, and says the files already read are held", async () => {
    await back({ "/api/drive/pick/result": () => ({ status: 401, body: { error: "Sign in to continue.", signIn: "/auth/google" } }) });
    expect(await screen.findByRole("heading", { name: "Sign in to see what you picked" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign in with Google" }).getAttribute("href")).toContain("/auth/google");
    expect(screen.getByText(/already read are held/)).toBeTruthy();
  });

  it("ignores a return that is for a record slot on the splitter's page", async () => {
    await back({ "/api/drive/pick/result": result(two.slice(0, 1), "slot") });
    await screen.findByRole("heading", { name: "Open a PDF" });
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("heading", { name: "What you picked from Google Drive" })).toBeNull();
  });

  it("says the whole list was kept when every file was", async () => {
    await back({ "/api/drive/pick/result": result([row({}), row({ heldId: SHA_B, name: "B.pdf" })]) });
    await screen.findByRole("heading", { name: "What you picked from Google Drive" });
    expect(screen.getAllByRole("status").some((s) => /^2 files kept\.$/.test(s.textContent ?? ""))).toBe(true);
  });
});

describe("what jason holds", () => {
  it("lists copies by number and size, with no name or id, and holds back a confidential copy", async () => {
    serve(ON, {
      "/api/split-sessions": { sessions: [], limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 } }, "/api/limits": { limits: [] },
      "/api/drive-held": { found: true, total: 2, copies: [
        { n: 1, id: SHA_A, size: 20480, pages: 13, day: "2026-10-03", confidential: false, held: false },
        { n: 2, id: "", size: null, pages: null, day: "2026-10-01", confidential: true, held: true }] },
    });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    const list = await screen.findByRole("list", { name: "Copies held from Drive" });
    const items = within(list).getAllByRole("listitem");
    expect(items[0].textContent).toMatch(/Copy 1 13 pages, 20 KB, picked 2026-10-03/);
    expect(items[0].textContent).not.toContain(SHA_A);
    expect(within(items[0]).getByRole("button", { name: "Check this copy: copy 1" })).toBeTruthy();
    expect(items[1].textContent).toMatch(/Copy 2.*confidential.*held back/);
    expect(within(items[1]).queryByRole("button")).toBeNull();
  });

  it("draws nothing when there are none", async () => {
    serve(ON, { "/api/split-sessions": { sessions: [], limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 } }, "/api/limits": { limits: [] }, "/api/drive-held": { found: true, total: 0, copies: [] } });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByRole("heading", { name: "Open a PDF" });
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("heading", { name: "Picked from Drive" })).toBeNull();
  });
});

describe("a held row for a record slot", () => {
  const SLOT = { key: "records/5200/minutes", title: "Board minutes", cardinality: "series" as const, source: "" };

  it("asks for the period, previews, then keeps the copy and pins it as an upload by its held address", async () => {
    const calls = serve(ON, { "/api/write/records/": (b: Record<string, unknown> | undefined) => ({ body: { ok: true, dryRun: !!b?.dryRun, would: { act: "upload", size: 20480 }, pin: "p-1a2b3c4d" } }) });
    const done = vi.fn();
    render(<HeldPanel slot={SLOT} row={row({})} n={1} by="A Manager" onDone={done} onBack={() => undefined} />);
    expect(screen.getByRole("button", { name: "Preview the pin" }).hasAttribute("disabled")).toBe(true);
    await userEvent.type(screen.getByLabelText(/Period this file is for/), "2099-06");
    await userEvent.click(screen.getByRole("button", { name: "Preview the pin" }));
    await userEvent.click(await screen.findByRole("button", { name: "Keep file 1 and pin it to Board minutes" }));
    await waitFor(() => expect(done).toHaveBeenCalled());
    const writes = calls.filter((c) => c.url.startsWith("/api/write/records/"));
    expect(writes[0].url).toBe("/api/write/records/records/5200/minutes");
    expect(writes.map((c) => c.body?.dryRun)).toEqual([true, false]);
    expect(writes[1].body).toMatchObject({ act: "upload", heldId: SHA_A, name: "Minutes.pdf", period: "2099-06", by: "A Manager" });
    expect(writes[1].body).not.toHaveProperty("base64");
  });

  it("shows a row's pin button only when the screen gives one", () => {
    const { rerender } = render(<PickOutcome value={{ kind: "result", result: result([row({})], "slot") }} onClose={() => undefined} />);
    expect(screen.queryByRole("button", { name: /Pin/ })).toBeNull();
    rerender(<PickOutcome value={{ kind: "result", result: result([row({})], "slot") }} onClose={() => undefined} action={(_r, n) => <button type="button">{`Pin it ${n}`}</button>} />);
    expect(screen.getByRole("button", { name: "Pin it 1" })).toBeTruthy();
  });
});
