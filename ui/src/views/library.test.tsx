import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { LibraryBrowser } from "./LibraryBrowser";
import { filtersOn, kindWord, NO_QUERY, sourceWord, type LibraryAnswer, type LibraryFile, type LibraryQuery } from "./libraryModel";
import { SplitView, resetDemo } from "./SplitView";

beforeEach(() => { resetServerSession(); resetDemo(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

// Made-up files in the shape the library loader returns; no real service is called.
const file = (over: Partial<LibraryFile>): LibraryFile => ({
  id: "101", name: "Alpha Minutes.pdf", kind: "minutes", source: "payhoa", sourceLabel: "PayHOA", pages: 12, size: 412_000, modified: "2099-06-01", added: "",
  hasText: true, draft: null, held: false, copies: 1, onDisk: true, openable: true, why: "", opens: "", ...over,
});
const FILES: LibraryFile[] = [
  file({}),
  file({ id: "102", name: "Beta Budget.pdf", kind: "budget", source: "ingest", sourceLabel: "Taken in by hand", pages: 40, size: 3_100_000, modified: "2099-05-02", hasText: false }),
  file({ id: "103", name: "Gamma Scan.pdf", kind: "", pages: 300, size: 52_000_000, modified: "2099-07-09", draft: { id: "a1b2c3d4", status: "draft" }, copies: 2 }),
  file({ id: "", name: "a confidential file (kind: bank statement)", kind: "bank_statement", held: true, openable: false, opens: "opens in the private view", draft: null }),
  file({ id: "105", name: "Missing.pdf", onDisk: false, openable: false, pages: null, size: null, modified: "", why: "this machine does not hold the file; fetch it first (jason ingest)" }),
];
const answer = (over: Partial<LibraryAnswer> = {}): LibraryAnswer => ({
  found: true, files: FILES, total: FILES.length, next: null, uncounted: 0, sort: "modified", order: "desc", empty: "",
  counts: { kinds: { minutes: 2, budget: 1, "(none)": 1, bank_statement: 1 }, sources: { payhoa: 4, ingest: 1 }, files: 5, all: 5, noText: 1, withDraft: 1, notHere: 1 },
  caveats: ["This is what jason's library holds on this machine."], ...over,
});

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
const listCalls = (calls: Call[]) => calls.filter((c) => c.url === "/api/write/library/files");

describe("the model", () => {
  it("says a kind and a source in words and counts the filters on", () => {
    expect(kindWord("bank_statement")).toBe("bank statement");
    expect(kindWord("(none)")).toBe("unclassified");
    expect(kindWord("")).toBe("unclassified");
    expect(sourceWord("ingest")).toBe("Taken in by hand");
    expect(filtersOn(NO_QUERY)).toBe(0);
    expect(filtersOn({ ...NO_QUERY, q: " a ", kind: "minutes", sort: "name" })).toBe(2);
  });
});

describe("the library browser", () => {
  const fetcher = (a: LibraryAnswer = answer()) => vi.fn(async (_q: LibraryQuery, _page?: string) => a);

  it("lists each file with its kind, pages, size, date, text, and draft, and says what it cannot open and why", async () => {
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={fetcher()} />);
    const table = await screen.findByRole("table", { name: /Files in the library/ });
    const alpha = within(table).getByText("Alpha Minutes.pdf").closest("tr")!;
    expect(alpha).toHaveTextContent("minutes");
    expect(alpha).toHaveTextContent("12");
    expect(alpha).toHaveTextContent("412 KB");
    expect(alpha).toHaveTextContent("2099-06-01");
    expect(alpha).toHaveTextContent("text held");
    expect(alpha).toHaveTextContent("PayHOA");
    const beta = within(table).getByText("Beta Budget.pdf").closest("tr")!;
    expect(beta).toHaveTextContent("no text held");
    expect(beta).toHaveTextContent("Taken in by hand");
    const gamma = within(table).getByText("Gamma Scan.pdf").closest("tr")!;
    expect(gamma).toHaveTextContent("draft exists");
    expect(gamma).toHaveTextContent("filed 2 times");
    expect(within(gamma).getByRole("link", { name: /Continue the draft draft of Gamma Scan\.pdf/ })).toHaveAttribute("href", "#/setup/split/a1b2c3d4");
    const held = within(table).getByText(/a confidential file \(kind: bank statement\)/).closest("tr")!;
    expect(held).toHaveTextContent("opens in the private view");
    expect(within(held).getByRole("radio")).toBeDisabled();
    const gone = within(table).getByText("Missing.pdf").closest("tr")!;
    expect(gone).toHaveTextContent("this machine does not hold the file");
    expect(within(gone).getByRole("radio")).toBeDisabled();
    expect(screen.getByTestId("lib-count")).toHaveTextContent("5 of 5 files shown");
    expect(screen.getByText("This is what jason's library holds on this machine.")).toBeInTheDocument();
  });

  it("chooses a file by its radio button or by a click on its row, and says which is selected in words", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const { rerender } = render(<LibraryBrowser selectedId="" onSelect={onSelect} fetcher={fetcher()} />);
    await user.click(await screen.findByRole("radio", { name: /Alpha Minutes\.pdf/ }));
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ id: "101" }));
    await user.click(screen.getByText("Beta Budget.pdf").closest("tr")!);
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ id: "102" }));
    await user.click(screen.getByText(/a confidential file/).closest("tr")!);
    expect(onSelect).toHaveBeenCalledTimes(2);                                       // a file that cannot be opened is not selectable
    rerender(<LibraryBrowser selectedId="102" onSelect={onSelect} fetcher={fetcher()} />);
    const row = screen.getByText("Beta Budget.pdf").closest("tr")!;
    expect(row).toHaveTextContent("selected");
    expect(within(row).getByRole("radio")).toBeChecked();
  });

  it("filters by the kind and source chips, which show their counts and say pressed", async () => {
    const user = userEvent.setup();
    const f = fetcher();
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={f} />);
    const kinds = await screen.findByRole("group", { name: "Kind of document" });
    expect(within(kinds).getByRole("button", { name: "All kinds (5)" })).toHaveAttribute("aria-pressed", "true");
    expect(within(kinds).getByRole("button", { name: "unclassified (1)" })).toBeInTheDocument();
    expect(within(kinds).getByRole("button", { name: "bank statement (1)" })).toBeInTheDocument();
    await user.click(within(kinds).getByRole("button", { name: "minutes (2)" }));
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "minutes" }), ""));
    expect(within(kinds).getByRole("button", { name: "minutes (2)" })).toHaveAttribute("aria-pressed", "true");
    const sources = screen.getByRole("group", { name: "Where the file came from" });
    await user.click(within(sources).getByRole("button", { name: "Taken in by hand (1)" }));
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "minutes", source: "ingest" }), ""));
    await user.click(screen.getByRole("button", { name: "Clear 2 filters" }));
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "", source: "" }), ""));
    await user.click(within(kinds).getByRole("button", { name: "unclassified (1)" }));
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "(none)" }), ""));
  });

  it("searches on Enter with the name, pages, and dates, and sorts and reverses", async () => {
    const user = userEvent.setup();
    const f = fetcher();
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={f} />);
    await screen.findByRole("table");
    await user.type(screen.getByLabelText("Search by file name"), "alpha{Enter}");
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ q: "alpha" }), ""));
    await user.click(screen.getByText("More filters"));
    await user.type(screen.getByLabelText("Smallest page count"), "20");
    await user.type(screen.getByLabelText("Changed on or after"), "2099-01-01");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ q: "alpha", minPages: "20", since: "2099-01-01" }), ""));
    await user.selectOptions(screen.getByLabelText("Sort by"), "pages");
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "pages" }), ""));
    await user.click(screen.getByRole("button", { name: /Descending: largest or latest first/ }));
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ order: "asc" }), ""));
    await user.selectOptions(screen.getByLabelText("Text"), "no");
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ text: "no" }), ""));
    await user.selectOptions(screen.getByLabelText("Drafts"), "yes");
    await waitFor(() => expect(f).toHaveBeenLastCalledWith(expect.objectContaining({ draft: "yes" }), ""));
  });

  it("shows 50 more by the server's token and keeps the rows it has", async () => {
    const user = userEvent.setup();
    const f = vi.fn(async (_q: LibraryQuery, page?: string) => page
      ? answer({ files: [file({ id: "201", name: "Second Page.pdf" })], total: 6, next: null })
      : answer({ files: FILES.slice(0, 2), total: 6, next: "2" }));
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={f} />);
    expect(await screen.findByTestId("lib-count")).toHaveTextContent("2 of 6 files shown");
    await user.click(screen.getByRole("button", { name: "Show 50 more" }));
    await screen.findByText("Second Page.pdf");
    expect(f).toHaveBeenLastCalledWith(expect.objectContaining({}), "2");
    expect(screen.getByText("Alpha Minutes.pdf")).toBeInTheDocument();
    expect(screen.getByTestId("lib-count")).toHaveTextContent("3 of 6 files shown");
    expect(screen.queryByRole("button", { name: "Show 50 more" })).not.toBeInTheDocument();
  });

  it("drops a slow answer that arrives after a newer question", async () => {
    const user = userEvent.setup();
    const slow: { resolve?: (a: LibraryAnswer) => void } = {};
    let n = 0;
    const f = vi.fn((_q: LibraryQuery) => {
      n += 1;
      if (n === 2) return new Promise<LibraryAnswer>((r) => { slow.resolve = r; });           // the second question is slow
      return Promise.resolve(answer({ files: [file({ id: `30${n}`, name: n === 1 ? "First.pdf" : "Newest.pdf" })], total: 1 }));
    });
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={f} />);
    await screen.findByText("First.pdf");
    await user.click(screen.getByRole("button", { name: "minutes (2)" }));                 // slow: still in flight
    await user.click(screen.getByRole("button", { name: "PayHOA (4)" }));  // the newer question answers first
    await screen.findByText("Newest.pdf");
    slow.resolve?.(answer({ files: [file({ id: "399", name: "Stale.pdf" })], total: 1 }));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(3));
    expect(screen.queryByText("Stale.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("Newest.pdf")).toBeInTheDocument();
  });

  it("says there is no library, with the command, and an empty result in the server's words", async () => {
    render(<LibraryBrowser selectedId="" onSelect={() => undefined}
      fetcher={fetcher(answer({ found: false, files: [], total: 0, why: "jason has no library on this machine yet.", command: "jason library" }))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("jason has no library on this machine yet.");
    expect(screen.getByText("jason library")).toBeInTheDocument();
    cleanup();
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={fetcher(answer({ files: [], total: 0, empty: "Nothing in the library matches. Clear a filter or the search." }))} />);
    expect(await screen.findByText("Nothing in the library matches. Clear a filter or the search.")).toBeInTheDocument();
  });

  it("shows a failed request as the server said it", async () => {
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={vi.fn(async () => { throw new Error("The splitter is the board's."); })} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The splitter is the board's.");
  });

  it("tells how many files have no page count when a pages filter leaves them out", async () => {
    render(<LibraryBrowser selectedId="" onSelect={() => undefined} fetcher={fetcher(answer({ uncounted: 7 }))} />);
    expect(await screen.findByTestId("lib-count")).toHaveTextContent("7 files have no page count yet");
  });
});

describe("opening a library file from the start screen", () => {
  it("searches by POST (the name is never in a URL), chooses a file, checks it, and opens it", async () => {
    const user = userEvent.setup();
    const calls = serve({
      "/api/split-sessions": { sessions: [] },
      "/api/limits": { limits: [] },
      "/api/write/library/files": answer(),
      "/api/write/split/new": (b: Record<string, unknown> | undefined) => b?.dryRun
        ? { body: { dryRun: true, would: { act: "open", pages: 12, size: 412000, by: "Ada Admin", keeps: "a copy of the file under the splitter's own folder and a draft session" }, note: "A dry run: nothing was kept." } }
        : { body: { ok: true, session: { id: "0a1b2c3d" } } },
    });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByText(/No drafts yet/);
    await user.click(screen.getByRole("button", { name: "From the library" }));
    expect(screen.queryByLabelText("Library file id")).not.toBeInTheDocument();
    await screen.findByRole("table", { name: /Files in the library/ });
    await user.type(screen.getByLabelText("Search by file name"), "alpha minutes{Enter}");
    await waitFor(() => expect(listCalls(calls).some((c) => c.body?.q === "alpha minutes")).toBe(true));
    expect(calls.every((c) => !c.url.toLowerCase().includes("alpha"))).toBe(true);
    expect(screen.getByRole("button", { name: "Check the file" })).toBeDisabled();
    await user.click(await screen.findByRole("radio", { name: /Alpha Minutes\.pdf/ }));
    expect(screen.getByText(/Chosen: Alpha Minutes\.pdf, 12 pages/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check the file" }));
    expect(await screen.findByRole("region", { name: "What opening will do" })).toHaveTextContent("12 pages");
    expect(calls.find((c) => c.url === "/api/write/split/new")!.body).toMatchObject({ act: "open", dryRun: true, ref: { kind: "library", id: "101" } });
    await user.click(screen.getByRole("button", { name: "Open it for splitting" }));
    await waitFor(() => expect(window.location.hash).toBe("#/setup/split/0a1b2c3d"));
  });
});

describe("opening a Drive file from the start screen", () => {
  const item = (over: Record<string, unknown>) => ({
    id: "1DriveFileAbCdEf", name: "Made Up Scan.pdf", type: "pdf", mime: "application/pdf", size: 5_000_000, modified: "2099-06-01", parents: [], owner: "Pat Owner",
    sharedDrive: false, readable: true, why: "", held: false, opens: "", children: null, doc: "", jason: { inLibrary: "", kind: "", ruleCovers: false, pinnedFor: [] }, ...over,
  });
  const LISTING = {
    found: true, driveConnected: true, account: "jason@example.org", parent: { name: "My Drive", path: [{ name: "My Drive" }] }, drives: [], empty: "", next: null,
    items: [item({ id: "1FolderAbCdEfGh", name: "Records", type: "folder", mime: "application/vnd.google-apps.folder", size: null }), item({}),
            item({ id: "1SheetAbCdEfGh", name: "Roster Sheet", type: "sheet", mime: "application/vnd.google-apps.spreadsheet", size: null })],
  };
  const open = (dry: boolean) => dry
    ? { dryRun: true, would: { act: "open", pages: null, size: 5000000, by: "Ada Admin", source: "drive", keeps: "a copy of the file under the splitter's own folder and a draft session", fetches: "one read of the file from Drive; the original is never changed", pagesCounted: "when the file is read" }, note: "A dry run: nothing was read or kept." }
    : { ok: true, session: { id: "0a1b2c3d" } };

  it("chooses a PDF in the shared Drive dialog (folders open, other types are off, no folder binding), checks it, and opens it", async () => {
    const user = userEvent.setup();
    const calls = serve({
      "/api/split-sessions": { sessions: [] }, "/api/limits": { limits: [] },
      "/api/write/drive/list": LISTING,
      "/api/write/split/new": (b: Record<string, unknown> | undefined) => ({ body: open(!!b?.dryRun) }),
    });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByText(/No drafts yet/);
    await user.click(screen.getByRole("button", { name: "From Drive" }));
    expect(screen.getByRole("button", { name: "Check the file" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Choose a PDF in Drive" }));
    const dialog = await screen.findByRole("dialog", { name: "Choose a PDF in Drive to split" });
    expect(within(dialog).queryByRole("tab", { name: "From this computer" })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("tab", { name: "Drive" })).toBeInTheDocument();
    expect(within(dialog).getByRole("tab", { name: "Paste a link" })).toBeInTheDocument();
    expect(await within(dialog).findByRole("button", { name: "Open the folder Records" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /Choose this folder/ })).not.toBeInTheDocument();
    const sheet = within(dialog).getByRole("radio", { name: /Roster Sheet/ });
    expect(sheet).toBeDisabled();
    expect(within(dialog).getByText(/The splitter takes a PDF; this is a sheet/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("radio", { name: /Made Up Scan\.pdf/ }));
    await user.click(within(dialog).getByRole("button", { name: "Pick" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByText(/Chosen in Drive:/)).toHaveTextContent("Made Up Scan.pdf, 5.0 MB");
    await user.click(screen.getByRole("button", { name: "Check the file" }));
    const preview = await screen.findByRole("region", { name: "What opening will do" });
    expect(preview).toHaveTextContent("One read of the file from Drive; the original is never changed.");
    expect(preview).toHaveTextContent("Its pages are counted when it is read.");
    expect(preview).not.toHaveTextContent("null pages");
    expect(calls.find((c) => c.url === "/api/write/split/new")!.body).toMatchObject({ act: "open", dryRun: true, ref: { kind: "drive", id: "1DriveFileAbCdEf" } });
    await user.click(screen.getByRole("button", { name: "Open it for splitting" }));
    await waitFor(() => expect(window.location.hash).toBe("#/setup/split/0a1b2c3d"));
    expect(calls.filter((c) => c.url === "/api/write/split/new")).toHaveLength(2);
  });

  it("closes on Escape and picks nothing", async () => {
    const user = userEvent.setup();
    serve({ "/api/split-sessions": { sessions: [] }, "/api/limits": { limits: [] }, "/api/write/drive/list": LISTING });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByText(/No drafts yet/);
    await user.click(screen.getByRole("button", { name: "From Drive" }));
    await user.click(screen.getByRole("button", { name: "Choose a PDF in Drive" }));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByText("No file chosen yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check the file" })).toBeDisabled();
  });

  it("says when Drive is not connected, with the command, and shows a refusal in the server's words", async () => {
    const user = userEvent.setup();
    let mode: "off" | "refused" = "off";
    serve({
      "/api/split-sessions": { sessions: [] }, "/api/limits": { limits: [] }, "/api/write/drive/list": LISTING,
      "/api/write/split/new": () => mode === "off"
        ? { body: { found: false, driveConnected: false, why: "jason cannot read Drive: it has no Google sign-in on this machine.", command: "jason google sign-in --name drive --interactive" } }
        : { status: 400, body: { error: "This file is 150 MB; the largest jason fetches is 100 MB. Nothing was copied." } },
    });
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    await screen.findByText(/No drafts yet/);
    await user.click(screen.getByRole("button", { name: "From Drive" }));
    await user.click(screen.getByRole("button", { name: "Choose a PDF in Drive" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("radio", { name: /Made Up Scan\.pdf/ }));
    await user.click(within(dialog).getByRole("button", { name: "Pick" }));
    await user.click(screen.getByRole("button", { name: "Check the file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("it has no Google sign-in");
    expect(screen.getByText("jason google sign-in --name drive --interactive")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check the file" })).toBeEnabled();
    mode = "refused";
    await user.click(screen.getByRole("button", { name: "Check the file" }));
    await waitFor(() => expect(screen.getAllByRole("alert").some((a) => a.textContent?.includes("the largest jason fetches is 100 MB. Nothing was copied."))).toBe(true));
  });
});
