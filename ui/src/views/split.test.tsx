import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findScreen, SCREENS } from "../App";
import { ApiError, resetServerSession } from "../lib/api";
import owned from "../ownerScreens.json";
import { PageGrid, type GridApi } from "./PageGrid";
import { SplitView, resetDemo } from "./SplitView";
import type { ActBody, SplitBackend } from "./splitApi";
import { DemoBackend } from "./splitDemo";
import { FactsCache } from "./splitFacts";
import { parseSplitRoute, splitRoute, type SessionView } from "./splitModel";
import { SplitStore } from "./splitStore";
import { ThumbLoader } from "./splitThumbs";
import { createRef } from "react";

// jsdom has no PointerEvent: a stand-in that carries pointerType, so touch and mouse can be told apart
if (typeof window.PointerEvent === "undefined") {
  class PointerEventStub extends MouseEvent {
    pointerType: string;
    constructor(type: string, init: MouseEventInit & { pointerType?: string } = {}) { super(type, init); this.pointerType = init.pointerType ?? "mouse"; }
  }
  Object.defineProperty(window, "PointerEvent", { value: PointerEventStub, configurable: true });
}

beforeEach(() => { resetServerSession(); resetDemo(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); window.location.hash = ""; });

// ---- a stubbed server for the start screen: made-up drafts and limits, no real service

interface Call { url: string; method: string; body?: Record<string, unknown> }
function serve(routes: Record<string, unknown | ((body: Record<string, unknown> | undefined) => { status?: number; body: unknown })>) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    if (u.startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn: { name: "Ada Admin", role: "administrator" } }), { status: 200 });
    calls.push({ url: u, method, body });
    const key = Object.keys(routes).find((k) => u.startsWith(k));
    const r = key ? routes[key] : { error: "no route" };
    const out = typeof r === "function" ? (r as (b: Record<string, unknown> | undefined) => { status?: number; body: unknown })(body) : { body: r };
    return new Response(JSON.stringify(out.body), { status: out.status ?? 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}

const LISTED = [
  { id: "a1b2c3d4", status: "draft", pages: 412, segments: 7, suggestionsOpen: 9, updated: "2099-10-04T10:42:00", by: "Ada Admin", confidential: false, kind: "upload", label: "412 pages, 5f3a9c01" },
  { id: "e5f6a7b8", status: "applied", pages: 60, segments: 4, suggestionsOpen: 0, updated: "2099-10-01T08:00:00", by: "Ada Admin", confidential: true, kind: "library", label: "a confidential file" },
  { id: "c9d0e1f2", status: "stale", pages: 30, segments: 2, suggestionsOpen: 0, updated: "2099-09-20T08:00:00", by: "Jo Example", confidential: false, kind: "upload", label: "30 pages, 77aa11bb" },
];

describe("the start screen", () => {
  it("lists the drafts with their status in words, a link to each, and a link to the demo", async () => {
    serve({ "/api/split-sessions": { sessions: LISTED, limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 }, caveats: ["A suggestion is jason's guess."] }, "/api/limits": { limits: [] } });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    const table = await screen.findByRole("table", { name: "Split drafts, newest first" });
    const draft = within(table).getByRole("link", { name: "Open the draft 412 pages, 5f3a9c01" });
    expect(draft).toHaveAttribute("href", "#/setup/split/a1b2c3d4");
    const row = draft.closest("tr")!;
    expect(row).toHaveTextContent("draft");
    expect(row).toHaveTextContent("412");
    expect(within(table).getByText("applied")).toBeInTheDocument();
    expect(within(table).getByText("stale: the file changed")).toBeInTheDocument();
    expect(within(table).getByText("a confidential file")).toBeInTheDocument();                  // masked as the server sent it
    expect(screen.getByRole("link", { name: /Try it on a made-up 120-page file/ })).toHaveAttribute("href", "#/setup/split/demo");
    expect(screen.getByText(/Files of up to 3000 pages open here/)).toBeInTheDocument();
    expect(screen.getByText("A suggestion is jason's guess.")).toBeInTheDocument();
  });

  it("checks an uploaded file with a dry run in the server's words, then opens it", async () => {
    const user = userEvent.setup();
    const calls = serve({
      "/api/split-sessions": { sessions: [] },
      "/api/limits": { limits: [{ key: "upload.max_bytes", value: 100e6, words: "100 MB" }] },
      "/api/write/split/new": (b: Record<string, unknown> | undefined) => b?.dryRun
        ? { body: { dryRun: true, would: { act: "open", pages: 12, size: 4096, by: "Ada Admin", keeps: "a copy of the file under the splitter's own folder and a draft session" }, note: "A dry run: nothing was kept." } }
        : { body: { ok: true, resumed: false, session: { id: "0a1b2c3d" } } },
    });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByText(/No drafts yet/);
    await user.upload(screen.getByLabelText("PDF file"), new File(["%PDF-1.4 made up"], "scan.pdf", { type: "application/pdf" }));
    await user.click(await screen.findByRole("button", { name: "Check the file" }));
    const preview = await screen.findByRole("region", { name: "What opening will do" });
    expect(preview).toHaveTextContent("12 pages");
    expect(preview).toHaveTextContent("A dry run: nothing was kept.");
    const dry = calls.find((c) => c.url === "/api/write/split/new")!;
    expect(dry.body).toMatchObject({ act: "open", dryRun: true, ref: { kind: "upload", name: "scan.pdf" } });
    expect(typeof (dry.body!.ref as { base64: string }).base64).toBe("string");
    await user.click(screen.getByRole("button", { name: "Open it for splitting" }));
    await waitFor(() => expect(window.location.hash).toBe("#/setup/split/0a1b2c3d"));
  });

  it("shows a refusal as the server said it, and refuses a file over the upload limit before sending it", async () => {
    const user = userEvent.setup();
    const calls = serve({
      "/api/split-sessions": { sessions: [] },
      "/api/limits": { limits: [{ key: "upload.max_bytes", value: 10, words: "10 bytes" }] },
      "/api/write/split/new": () => ({ status: 400, body: { error: "This file has 5000 pages; the splitter opens files of up to 3000. Nothing was changed." } }),
    });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByText(/No drafts yet/);
    await user.click(screen.getByRole("button", { name: "From the library" }));
    await user.type(screen.getByLabelText("Library file id"), "lib-1");
    await user.click(screen.getByRole("button", { name: "Check the file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This file has 5000 pages; the splitter opens files of up to 3000. Nothing was changed.");
    await user.click(screen.getByRole("button", { name: "From this computer" }));
    await user.upload(screen.getByLabelText("PDF file"), new File(["%PDF-1.4 too large for the cap"], "big.pdf", { type: "application/pdf" }));
    expect(await screen.findByText(/the largest upload is 10 bytes/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check the file" })).toBeDisabled();
    expect(calls.filter((c) => c.url === "/api/write/split/new")).toHaveLength(1);        // only the library check went out
  });
});

describe("the route", () => {
  it("is a Setup screen for officers, managers, and administrators; never an owner screen", () => {
    const s = SCREENS.find((x) => x.id === "setup/split");
    expect(s?.group).toBe("Setup");
    expect(s?.roles).toEqual(["officer", "manager", "administrator"]);
    expect(s?.owner).toBeFalsy();
    expect(Object.keys(owned.screens)).not.toContain("setup/split");
  });
  it("lands a draft's route, by whole path, on the splitter, and reads the id from it", () => {
    expect(findScreen("setup/split")?.id).toBe("setup/split");
    expect(findScreen("setup/split/a1b2c3d4")?.id).toBe("setup/split");
    expect(findScreen("setup/split/demo")?.id).toBe("setup/split");
    expect(findScreen("setup/limits")?.id).toBe("setup/limits");
    expect(parseSplitRoute("setup/split/a1b2c3d4?x=1").id).toBe("a1b2c3d4");
    expect(parseSplitRoute("setup/split").id).toBe("");
    expect(splitRoute("a1b2c3d4")).toBe("#/setup/split/a1b2c3d4");
  });
});

// ---- the demo draft: the interactions, with no server

const cell = (page: number) => document.querySelector<HTMLElement>(`button.split-cell-btn[data-page="${page}"]`)!;
async function openDemo() {
  window.location.hash = "#/setup/split/demo";
  render(<SplitView />);
  await screen.findByRole("grid", { name: "Pages" });
  await waitFor(() => expect(cell(1)).toBeTruthy());
}
const saved = () => waitFor(() => expect(document.querySelector('[data-save="saved"]')).toBeTruthy());

describe("marking pages in the demo", () => {
  it("opens a made-up 120-page draft with only the pages near the view built", async () => {
    await openDemo();
    expect(screen.getByText("Demo")).toBeInTheDocument();
    expect(screen.getByText("120 pages")).toBeInTheDocument();
    const cells = document.querySelectorAll("[data-cell]").length;
    expect(cells).toBeGreaterThan(10);
    expect(cells).toBeLessThan(120);
    expect(cell(1)).toHaveAccessibleName(/Page 1.*Starts segment 1.*first page always starts a segment/);
    expect(cell(5)).toHaveAccessibleName(/Press Enter to make this page start a segment|Suggested start/);
  });

  it("marks and unmarks a page by a tap, at once, and saves it", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(10));
    expect(cell(10)).toHaveAttribute("aria-pressed", "true");                         // before the server has answered
    expect(cell(10)).toHaveAccessibleName(/Starts segment 2/);
    expect(cell(10).closest("[data-cell]")).toHaveAttribute("data-start", "top");
    await saved();
    expect(screen.getByText(/2 segments/)).toBeInTheDocument();
    await user.click(cell(10));
    expect(cell(10)).toHaveAttribute("aria-pressed", "false");
    await saved();
    expect(screen.getByText(/1 segment\b/)).toBeInTheDocument();
  });

  it("says the first page always starts a segment, and does not remove it", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(1));
    expect(await screen.findByText("The first page always starts a segment.", { selector: ".split-live" })).toBeInTheDocument();
    expect(cell(1)).toHaveAttribute("aria-pressed", "true");
  });

  it("selects a range with shift and click without marking it, then offers every Nth page in it", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(3));
    await user.keyboard("{Shift>}");
    await user.click(cell(8));
    await user.keyboard("{/Shift}");
    expect(screen.getByText(/6 pages selected \(3 to 8\)/)).toBeInTheDocument();
    expect(cell(8)).toHaveAttribute("aria-pressed", "false");                         // selected, not marked
    expect(cell(6).closest("[data-cell]")).toHaveAttribute("data-selected", "true");
    await user.click(screen.getByText("More"));
    expect(screen.getByRole("button", { name: /^Add \d+ starts?$/ })).toBeEnabled();
  });

  it("toggles with Enter, undoes with z, redoes with y, and walks the starts with n and p", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(12).focus();
    await user.keyboard("{Enter}");
    expect(cell(12)).toHaveAttribute("aria-pressed", "true");
    await saved();
    await user.keyboard("z");
    await waitFor(() => expect(cell(12)).toHaveAttribute("aria-pressed", "false"));
    await user.keyboard("y");
    await waitFor(() => expect(cell(12)).toHaveAttribute("aria-pressed", "true"));
    await saved();
    cell(12).focus();
    await user.keyboard("p");
    await waitFor(() => expect(cell(12).getAttribute("tabindex")).toBe("-1"));         // the focus moved to the start or suggestion before
  });

  it("moves between pages with the arrow keys and keeps one tab stop", async () => {
    const user = userEvent.setup();
    await openDemo();
    cell(1).focus();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    await waitFor(() => expect(cell(3).getAttribute("tabindex")).toBe("0"));
    expect(document.querySelectorAll('button.split-cell-btn[tabindex="0"]')).toHaveLength(1);
    await user.keyboard("{ArrowDown}");
    const cols = Number(document.querySelector("[role=grid]")!.getAttribute("aria-colcount"));
    await waitFor(() => expect(cell(3 + cols).getAttribute("tabindex")).toBe("0"));
  });

  it("opens the page menu on a right click and a long press, and marks from it", async () => {
    const user = userEvent.setup();
    await openDemo();
    fireEvent.contextMenu(cell(14));
    const menu = await screen.findByRole("dialog", { name: "Page 14" });
    await user.click(within(menu).getByRole("button", { name: "Starts a segment" }));
    await waitFor(() => expect(cell(14)).toHaveAttribute("aria-pressed", "true"));
    expect(screen.queryByRole("dialog", { name: "Page 14" })).toBeNull();
    await saved();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    fireEvent.pointerDown(cell(20), { pointerType: "touch", clientX: 5, clientY: 5 });
    act(() => { vi.advanceTimersByTime(520); });
    vi.useRealTimers();
    expect(await screen.findByRole("dialog", { name: "Page 20" })).toBeInTheDocument();
    fireEvent.click(cell(20));                                                         // the click that follows a long press is ignored
    expect(cell(20)).toHaveAttribute("aria-pressed", "false");
  });

  it("does not open the menu when a touch moves (a scroll) before the press is long", async () => {
    await openDemo();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    fireEvent.pointerDown(cell(21), { pointerType: "touch", clientX: 5, clientY: 5 });
    fireEvent.pointerMove(cell(21), { pointerType: "touch", clientX: 5, clientY: 60 });
    act(() => { vi.advanceTimersByTime(600); });
    vi.useRealTimers();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows a suggestion dashed, with its band and its reason, and accepts or rejects it", async () => {
    const user = userEvent.setup();
    await openDemo();
    const dashed = document.querySelector<HTMLElement>('[data-sug="High"]')!;
    expect(dashed).toBeTruthy();
    expect(within(dashed).getByText(/Suggested, High/)).toBeInTheDocument();           // a word, not just a dash
    const page = Number(dashed.dataset.page);
    expect(dashed.querySelector("button")).toHaveAccessibleName(/Suggested start, high confidence/);
    await user.click(screen.getByText("Suggest"));
    await user.click(screen.getByRole("button", { name: /Accept \d+ at High confidence/ }));
    await waitFor(() => expect(cell(page)).toHaveAttribute("aria-pressed", "true"));
    expect(cell(page)).toHaveAccessibleName(/Starts segment/);
    await saved();
    expect(document.querySelector(`[data-cell][data-page="${page}"][data-sug]`)).toBeNull();
  });

  it("changes the view and keeps the page in view: filmstrip, scroll, list", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: "Filmstrip" }));
    expect(await screen.findByRole("group", { name: "Pages, as a strip" })).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 120/, { selector: "strong" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Scroll" }));
    expect(await screen.findByRole("grid", { name: "Pages, one at a time" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Scroll across" }));
    expect(await screen.findByRole("group", { name: "Pages, one at a time" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "List" }));
    const list = await screen.findByRole("region", { name: "Segments and suggested starts" });
    expect(within(list).getAllByRole("listitem").length).toBeGreaterThan(3);           // segment 1 and the suggestions
  });

  it("jumps to a page from the Go to field", async () => {
    const user = userEvent.setup();
    await openDemo();
    const field = screen.getByLabelText("Go to page");
    await user.clear(field);
    await user.type(field, "90{Enter}");
    await waitFor(() => expect(cell(90)).toBeTruthy());
    expect(cell(90).getAttribute("tabindex")).toBe("0");
    expect(screen.getByLabelText("Page")).toHaveValue("90");
    expect(screen.getByLabelText("Page")).toHaveAttribute("aria-valuetext", expect.stringMatching(/^Page 90 of 120, segment 1/));
  });

  it("opens the compare pane with the page before, and the key map on ?", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(5));
    await user.click(screen.getByRole("button", { name: "Compare" }));
    const pane = await screen.findByRole("region", { name: "Compare pages" });
    expect(within(pane).getByText("The page before")).toBeInTheDocument();
    expect(within(pane).getByText("This page")).toBeInTheDocument();
    await user.click(within(pane).getByRole("button", { name: "800 px" }));
    expect(pane.querySelector("[data-zoom=full]")).toBeTruthy();
    cell(5).focus();
    await user.keyboard("?");
    const help = await screen.findByRole("dialog", { name: "Keyboard map" });
    expect(within(help).getByText("Z and Shift Z")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("marks every Nth page from the More menu after showing how many it adds", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByText("More"));
    fireEvent.change(screen.getByLabelText("Every how many pages"), { target: { value: "30" } });
    const add = screen.getByRole("button", { name: "Add 3 starts" });                  // pages 31, 61, 91
    await user.click(add);
    await waitFor(() => expect(screen.getByText(/4 segments/)).toBeInTheDocument());
    await saved();
  });

  it("asks before splitting on blank pages that look like the backs of pages", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByText("More"));
    await user.click(screen.getByRole("button", { name: "Find blank pages" }));
    const status = await screen.findByText(/blank pages \(\d+%\)\. This adds/);
    expect(status).toHaveTextContent("4 blank pages");
    expect(screen.queryByText(/look like the backs of pages/)).toBeNull();             // 4 of 120 is not duplex
    await user.click(screen.getByRole("button", { name: "Split on blank pages" }));
    await waitFor(() => expect(screen.getByText(/5 segments/)).toBeInTheDocument());
  });
});

describe("the review step in the demo", () => {
  it("shows what would be written, previews the apply as a dry run, then writes only on a confirm", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(5));
    await saved();
    await user.click(screen.getAllByRole("button", { name: "Review and split" })[0]);
    expect(await screen.findByRole("heading", { name: "Review: 2 documents from 120 pages" })).toHaveFocus();
    expect(screen.getByText("Pages add up")).toBeInTheDocument();
    expect(screen.getByText(/120 pages in files \+ 0 left out = 120 of 120/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: /The files this split would make/ });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Preview the split" }));
    const preview = await screen.findByRole("region", { name: "What the split will do" });
    expect(preview).toHaveTextContent("2 new files");
    expect(preview).toHaveTextContent("A dry run: nothing was written.");
    expect(screen.queryByText("The split was written")).toBeNull();
    await user.click(screen.getByRole("button", { name: /^Write 2 files/ }));
    expect(await screen.findByRole("heading", { name: "The split was written" })).toBeInTheDocument();
    expect(screen.getByText("The original was not changed.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to the pages" }));
    await waitFor(() => expect(screen.getAllByText(/This split is applied/).length).toBeGreaterThan(0));
  });

  it("leaves blank pages out only when asked, and the totals still add", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(5));
    await saved();
    await user.click(screen.getAllByRole("button", { name: "Review and split" })[0]);
    await screen.findByRole("heading", { name: /^Review:/ });
    await user.click(screen.getByRole("button", { name: "Find the blank pages" }));
    const box = await screen.findByRole("checkbox", { name: /Leave out the 4 blank pages/ });
    await user.click(box);
    expect(await screen.findByText(/4 pages are left out of every new file/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/116 pages in files \+ 4 left out = 120 of 120/)).toBeInTheDocument());
  });
});

describe("a draft with a thousand pages", () => {
  async function mountGrid(pages: number, loader?: ThumbLoader) {
    const backend = new DemoBackend({ pages });
    const store = new SplitStore(backend, "demo");
    await store.load();
    const facts = new FactsCache(backend, "demo", pages);
    const l = loader ?? new ThumbLoader({ urlOf: (p, s) => backend.thumbUrl("demo", p, s) });
    const ref = createRef<GridApi>();
    const ui = (focus = 1) => (
      <PageGrid ref={ref} count={pages} axis="y" variant="album" cellW={124} label="Pages" snap={store.getSnapshot()} facts={facts} loader={l} focus={focus} selection={null}
        confidential={false} onActivate={() => undefined} onMenu={() => undefined} onMove={() => undefined} onFocusPage={() => undefined} />
    );
    const view = render(ui());
    return { view, ref, loader: l, facts, store, backend };
  }

  it("builds a few dozen cells for 3,000 pages, wherever the scroll is, and stays quick", async () => {
    const { view, ref } = await mountGrid(3000);
    const grid = view.container.querySelector<HTMLElement>("[role=grid]")!;
    expect(Number(grid.getAttribute("aria-rowcount"))).toBeGreaterThan(300);
    const live = () => view.container.querySelectorAll("[data-cell]").length;
    expect(live()).toBeLessThan(100);
    const start = performance.now();
    for (let i = 0; i < 30; i++) {
      grid.scrollTop = i * 17000 % 500000;
      fireEvent.scroll(grid);
      await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
      expect(live()).toBeLessThan(100);
    }
    expect(performance.now() - start).toBeLessThan(6000);
    ref.current!.scrollToPage(3000);
    await waitFor(() => expect(view.container.querySelector('[data-cell][data-page="3000"]')).toBeTruthy());
    expect(view.container.querySelector('[data-cell][data-page="1"]')).toBeNull();
    const info = ref.current!.windowInfo();
    expect(info.live).toBeLessThan(100);
    expect(info.last).toBe(3000);
  });

  it("asks for the pictures of the window only, and holds no more than its budget", async () => {
    const { view, loader } = await mountGrid(3000);
    await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
    const s = loader.stats();
    expect(s.attached).toBeLessThan(100);
    expect(s.cached.tiny).toBeLessThanOrEqual(150);
    expect(s.requested).toBeLessThan(250);                                              // not 3,000
    expect(view.container.querySelectorAll("img").length).toBeLessThan(100);
  });

  it("drops the pictures of cells that scroll away, and aborts what had not arrived", async () => {
    const calls: string[] = [];
    const aborted: string[] = [];
    const slow = (url: string, signal: AbortSignal) => new Promise<string>((_resolve, reject) => {
      calls.push(url);
      signal.addEventListener("abort", () => { aborted.push(url); reject(new DOMException("aborted", "AbortError")); });
    });
    const backend = new DemoBackend({ pages: 3000 });
    const { view, ref } = await mountGrid(3000, new ThumbLoader({ urlOf: (p, s) => backend.thumbUrl("demo", p, s), fetcher: slow }));
    const grid1 = view.container.querySelector<HTMLElement>("[role=grid]")!;
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    grid1.scrollTop = 400000;
    fireEvent.scroll(grid1);
    ref.current!.scrollToPage(2500, true);
    await waitFor(() => expect(view.container.querySelector('[data-cell][data-page="2500"]')).toBeTruthy());
    expect(aborted.length).toBeGreaterThan(0);                                          // the first screen's requests were let go
  });

  it("says a page could not be drawn, in the server's words, in the cell", async () => {
    const { LoadError } = await import("./splitThumbs");
    const backend = new DemoBackend({ pages: 40 });
    const failing = (_url: string) => Promise.reject(new LoadError(403, "The pictures of a confidential file need the private view."));
    const { view } = await mountGrid(40, new ThumbLoader({ urlOf: (p, s) => backend.thumbUrl("demo", p, s), fetcher: failing }));
    await waitFor(() => expect(view.container.querySelector(".split-cell-note")?.textContent).toBe("The pictures of a confidential file need the private view."));
  });
});

// ---- the draft's queue: conflicts, a lost connection, a refusal

function stub(onAct: (body: ActBody, n: number) => Promise<unknown>): SplitBackend {
  const base = new DemoBackend();
  let n = 0;
  return {
    demo: true, thumbUrl: (id, p, s) => base.thumbUrl(id, p, s), list: () => base.list(), open: () => base.open(),
    session: (id, q) => base.session(id, q),
    act: async (id, body) => { n += 1; const r = await onAct(body, n); return (r ?? base.act(id, body)) as never; },
  };
}
const mine = (store: SplitStore) => [...store.getSnapshot().starts.keys()].sort((a, b) => a - b);

describe("saving: conflicts, a lost connection, a refusal", () => {
  it("holds the queue on a 409, shows both copies, and keeps mine, theirs, or the union", async () => {
    const theirs: SessionView = { ...(await new DemoBackend().session("demo")), version: 9, updated: "2099-10-04T10:00:00", by: "Jo Example", boundaries: [{ page: 1, level: 0 }, { page: 40, level: 0 }] } as never;
    const make = () => stub(async (b, n) => {
      if (n === 1) throw new ApiError("The draft changed since you opened it.", 409, { conflict: true, current: theirs });
      const rows = ((b.boundaries as [number, number][] | undefined) ?? []).map(([page, level]) => ({ page, level }));
      return { ok: true, act: b.act, version: 10, session: { ...theirs, version: 10, boundaries: rows } };
    });
    const a = new SplitStore(make(), "demo");
    await a.load();
    a.mark([10]);
    await waitFor(() => expect(a.getSnapshot().save).toBe("conflict"));
    expect(a.getSnapshot().conflict?.message).toMatch(/draft changed/);
    expect(mine(a)).toEqual([1, 10]);                                                  // my page is still there on the screen
    a.keepTheirs();
    expect(mine(a)).toEqual([1, 40]);
    expect(a.getSnapshot().save).toBe("saved");

    const b = new SplitStore(make(), "demo");
    await b.load();
    b.mark([10]);
    await waitFor(() => expect(b.getSnapshot().save).toBe("conflict"));
    b.keepMine(true);                                                                  // merge: every start from both
    await b.idle();
    await waitFor(() => expect(b.getSnapshot().save).toBe("saved"));
    expect(mine(b)).toEqual([1, 10, 40]);
  });

  it("keeps the marks when the connection is lost, says so, and sends them when it is back", async () => {
    let up = false;
    const s = new SplitStore(stub(async () => { if (!up) throw new TypeError("Failed to fetch"); return undefined; }), "demo");
    await s.load();
    s.mark([7]);
    await waitFor(() => expect(s.getSnapshot().save).toBe("offline"));
    expect(s.getSnapshot().message).toMatch(/You are offline/);
    expect(mine(s)).toEqual([1, 7]);
    expect(sessionStorage.getItem("jason-split-unsaved-demo")).toContain("[7,0]");
    up = true;
    s.retry();
    await waitFor(() => expect(s.getSnapshot().save).toBe("saved"));
    expect(mine(s)).toEqual([1, 7]);
    expect(sessionStorage.getItem("jason-split-unsaved-demo")).toBeNull();
  });

  it("puts a page back the way the server has it when the server refuses, and says why in its words", async () => {
    const s = new SplitStore(stub(async (b) => { if (b.act === "mark") throw new ApiError("page 7 is not in a file of 5 pages", 400, {}); return undefined; }), "demo");
    await s.load();
    s.mark([7]);
    expect(mine(s)).toEqual([1, 7]);
    await waitFor(() => expect(s.getSnapshot().message).toBe("page 7 is not in a file of 5 pages"));
    await waitFor(() => expect(mine(s)).toEqual([1]));
    expect(s.getSnapshot().save).toBe("saved");                                         // nothing is waiting to be sent
  });

  it("holds a change the server could not take (a 5xx), says it is not saved, and sends it again on a retry", async () => {
    let broken = true;
    const s = new SplitStore(stub(async () => { if (broken) throw new ApiError("Service unavailable", 503, {}); return undefined; }), "demo");
    await s.load();
    s.mark([7]);
    await waitFor(() => expect(s.getSnapshot().save).toBe("error"));
    expect(mine(s)).toEqual([1, 7]);                                                    // kept, not reverted
    broken = false;
    s.retry();
    await waitFor(() => expect(s.getSnapshot().save).toBe("saved"));
    expect(mine(s)).toEqual([1, 7]);
  });

  it("sends each change in order with the version it started from", async () => {
    const seen: { act: string; version?: number }[] = [];
    const s = new SplitStore(stub(async (b) => { seen.push({ act: b.act, version: b.version }); return undefined; }), "demo");
    await s.load();
    s.mark([4]); s.mark([9]); s.unmark([4]);
    await s.idle();
    await waitFor(() => expect(s.getSnapshot().save).toBe("saved"));
    expect(seen.map((x) => x.act)).toEqual(["mark", "mark", "unmark"]);
    expect(seen.map((x) => x.version)).toEqual([1, 2, 3]);
    expect(mine(s)).toEqual([1, 9]);
  });

  it("refuses a change to a split that is not a draft", async () => {
    const backend = new DemoBackend();
    await backend.act("demo", { act: "decline" });
    const s = new SplitStore(backend, "demo");
    await s.load();
    s.mark([4]);
    expect(s.getSnapshot().readOnly).toBe(true);
    expect(s.getSnapshot().message).toBe("This split is declined; only a draft can be changed.");
    expect(mine(s)).toEqual([1]);
  });
});
