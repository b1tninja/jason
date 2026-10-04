import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { AskPanel, DOC_WORDS, Scratchpad, type DocRef, type EvidenceEntry } from "../components";
import { BoardItemsView } from "./BoardItemsView";
import { DecisionsView } from "./DecisionsView";

/* The board group's screens on `Doc` (docs/console/doc-component.md): board items' evidence, decision briefs' sources,
 * and Ask's and the Scratchpad's sources render as Doc chips from the loader's references; a command is code to copy and
 * text stays text. Everything here is made up. */

const library: DocRef = { address: "library:abc1234", document: "library:abc1234", name: "Open minutes", kind: "pdf", level: "P0", source: "Library copy" };
const declaration: DocRef = { address: "file:governing/Example Declaration.pdf", document: "pdf", name: "Example Declaration.pdf", kind: "pdf", level: "P0", source: "Recorded copy" };
const statute: DocRef = { address: "CIV 4920", document: "section", name: "CIV 4920", kind: "text", level: "P0", source: "Statutes on disk" };
const refs: EvidenceEntry[] = [library, declaration, { command: "jason board --sheet" }, { text: "PayHOA: request 12" }];
const strings = ["library: Minutes/open minutes.pdf", "data/governing/Example Declaration.pdf", "jason board --sheet", "PayHOA: request 12"];

const SIGNED_IN = { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true } };
const SIGNED_OUT = { token: "t", signedIn: null, signIn: { configured: true } };
const VIEW = { kind: "text", name: "Open minutes", readAt: "", url: "", expires: "", text: "The board met.", caveats: [] };

type Route = (init?: RequestInit) => unknown;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** The server: its session, the screen's loader, and the evidence view (one POST per opening). */
function serve(routes: Record<string, Route>, { session = SIGNED_IN as object, view = (): Response => json(VIEW) } = {}) {
  const views: unknown[] = [];
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith("/api/session")) return json(session);
    if (url.startsWith("/api/evidence/view")) { views.push(JSON.parse(String(init?.body))); return view(); }
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return json({ error: `no route ${url}` }, 404);
    return json(routes[key](init));
  });
  vi.stubGlobal("fetch", f);
  return views;
}
afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

function noRawLinks(container: HTMLElement) {
  expect(container.querySelector('a[href*="/api/file"]')).toBeNull();
  expect(container.innerHTML).not.toContain("/api/file?path=");
  expect(container.innerHTML).not.toMatch(/\b[A-Z]:\\|\b[A-Z]:\/(?!\/)|\/(?:Users|home)\//);
  for (const f of Array.from(container.querySelectorAll("iframe"))) expect(f.getAttribute("src") ?? "").toMatch(/^\/api\//);
}

/** Opens the chip and answers whether one view was posted, for the address. */
async function opens(name: string, views: unknown[], address: string) {
  await userEvent.click(await screen.findByRole("button", { name: `Open ${name}` }));
  await waitFor(() => expect(views).toEqual([{ address, document: address === library.address ? library.document : "pdf", by: "A Manager" }]));
}

// --- Board action items ------------------------------------------------------------------------------------------------

const item = {
  id: "example-item", title: "A matter to decide", summary: "s", ask: "Decide it", category: "finance", priority: "high", status: "open",
  authority: "CIV 5515(d)", evidence: strings, evidenceRefs: refs, session: null, special_notice: "", due: null, opened: "2099-09-01",
  owner: "", meeting: "", notes: "", source: "jason", history: [],
};

describe("BoardItemsView: evidence as Doc chips", () => {
  async function details() {
    await userEvent.click(await screen.findByRole("button", { name: /Details/ }));
  }

  it("renders each mapped string by its kind and opens a document as one logged view", async () => {
    const views = serve({ "/api/board-items": () => ({ found: true, items: [item] }) });
    const { container } = render(<BoardItemsView />);
    await details();
    expect(screen.getByRole("button", { name: "Open Example Declaration.pdf" })).toBeInTheDocument();
    expect(screen.getByText("jason board --sheet").tagName).toBe("CODE");
    expect(screen.getByText("PayHOA: request 12")).toBeInTheDocument();
    expect(views).toEqual([]);                                     // nothing viewed on load
    noRawLinks(container);
    await opens("Open minutes", views, library.address);
    expect(await screen.findByRole("dialog")).toHaveTextContent("The board met.");
  });

  it("signed out: says to sign in and posts no view", async () => {
    const views = serve({ "/api/board-items": () => ({ found: true, items: [item] }) }, { session: SIGNED_OUT });
    render(<BoardItemsView />);
    await details();
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(await screen.findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(views).toEqual([]);
  });

  it("not allowed: the server's reason, in words", async () => {
    serve({ "/api/board-items": () => ({ found: true, items: [item] }) },
      { view: () => json({ error: "The treasurer's office doesn't open this document." }, 403) });
    render(<BoardItemsView />);
    await details();
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(await screen.findByText(/The treasurer's office doesn't open this document/)).toBeInTheDocument();
  });

  it("an older server's strings stay chips", async () => {
    serve({ "/api/board-items": () => ({ found: true, items: [{ ...item, evidenceRefs: undefined }] }) });
    render(<BoardItemsView />);
    await details();
    expect(screen.getByText("library: Minutes/open minutes.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Open minutes" })).not.toBeInTheDocument();
  });
});

// --- Decisions -------------------------------------------------------------------------------------------------------------

const candidate = {
  id: "example-item", title: "A matter to decide", ask: "Decide it", session: "open session", authority: "", priority: "high", evidence: strings,
  evidenceRefs: refs, kind: "action", include: true, motion: "", allot: 10, order: 0, packet: [], brief: null,
  readiness: { ready: false, checks: [] }, suggestion: "",
};
const plan = (c: unknown) => ({
  found: true, date: "2099-10-21", today: "2099-10-03", noticeBy: "2099-10-17", executiveNoticeBy: "2099-10-19", directors: ["A. Director"],
  decisions: [], basics: {}, zoom: {}, candidates: [c], kinds: [], formats: [], rules: [], notice: { by: "", executiveBy: "", required: [] },
  steps: [], commands: {}, updated: "", history: [], agendaMarkdown: "", caveats: [],
});

describe("DecisionsView: the brief's sources as Doc chips", () => {
  it("a written brief shows the sources as chips; the person's facts stay text; opening is one view", async () => {
    const brief = { question: "Which way?", criteria: ["Cost"], options: [{ label: "Renew", values: ["$1.00"] }, { label: "Rebid", values: ["unknown"] }], facts: ["A fact a person wrote"] };
    const views = serve({ "/api/agenda-plan": () => plan({ ...candidate, brief }) });
    const { container } = render(<DecisionsView />);
    expect((await screen.findByText("A fact a person wrote")).tagName).toBe("LI");
    expect(screen.getByText("Sources:")).toBeInTheDocument();
    expect(screen.getByText("jason board --sheet").tagName).toBe("CODE");
    noRawLinks(container);
    await opens("Open minutes", views, library.address);
  });

  it("with no brief yet, the form seeds the facts from the strings and shows the sources as chips", async () => {
    serve({ "/api/agenda-plan": () => plan(candidate) }, { session: SIGNED_OUT });
    render(<DecisionsView />);
    expect(await screen.findByLabelText("Facts on file, one per line")).toHaveValue(strings.join("\n"));
    await userEvent.click(screen.getByRole("button", { name: "Open Example Declaration.pdf" }));
    expect(await screen.findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
  });
});

// --- Ask and the Scratchpad ------------------------------------------------------------------------------------------------

const ask = {
  found: true, routedAnswer: "routed", translateCommand: "", translationStates: ["needs review"], translations: [], asks: [],
  caveats: ["Answers come from the association's records and jason's stores, and cite where each was read."],
  common: [{ question: "Where are the minutes?", screen: "records", answer: "The minutes are kept at Minutes.", routed: false,
    sources: ["records_inventory()", "CIV 4920", "Minutes/open minutes.pdf"], sourceRefs: [{ command: "records_inventory()" }, statute, library] }],
};

describe("AskPanel: sources as Doc chips", () => {
  it("a citation and a library document open; a tool call is a command", async () => {
    const views = serve({ "/api/dock?part=ask": () => ask });
    const { container } = render(<AskPanel go={() => {}} me="A Manager" />);
    await userEvent.click(await screen.findByRole("button", { name: /Where are the minutes/ }));
    const answer = screen.getByRole("article", { name: "Answer" });
    expect(within(answer).getByRole("button", { name: "Open CIV 4920" })).toBeInTheDocument();
    expect(within(answer).getByText("records_inventory()").tagName).toBe("CODE");
    expect(screen.getByText(/cite where each was read/)).toBeInTheDocument();      // the caveat stays
    noRawLinks(container);
    await opens("Open minutes", views, library.address);
  });

  it("not allowed: the server's reason", async () => {
    serve({ "/api/dock?part=ask": () => ask }, { view: () => json({ error: "The treasurer's office doesn't open this document." }, 403) });
    render(<AskPanel go={() => {}} me="A Manager" />);
    await userEvent.click(await screen.findByRole("button", { name: /Where are the minutes/ }));
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(await screen.findByText(/The treasurer's office doesn't open this document/)).toBeInTheDocument();
  });
});

describe("Scratchpad: sources as Doc chips", () => {
  const notes = {
    found: true, count: 1, statuses: ["researching", "question"], caveat: "Working notes, not association records.",
    notes: [{ id: "n1", title: "Example note", status: "question", body: "b", sources: ["CIV 4920", "library: Minutes/open minutes.pdf", "a note"],
      sourceRefs: [statute, library, { text: "a note" }], created: "2099-10-01T00:00:00+00:00", updated: "2099-10-02T00:00:00+00:00", by: "D" }],
  };

  it("saved sources open as Doc chips; one added since the save is text until saved", async () => {
    const views = serve({ "/api/dock?part=notes": () => notes });
    const user = userEvent.setup();
    const { container } = render(<Scratchpad me="A Manager" />);
    await user.click(await screen.findByRole("button", { name: /Example note/ }));
    expect(screen.getByRole("button", { name: "Open CIV 4920" })).toBeInTheDocument();
    expect(screen.getByText("a note")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Add a source"), "CIV 5550");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("CIV 5550")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open CIV 5550" })).not.toBeInTheDocument();
    noRawLinks(container);
    await opens("Open minutes", views, library.address);
  });

  it("signed out: says to sign in", async () => {
    const views = serve({ "/api/dock?part=notes": () => notes }, { session: SIGNED_OUT });
    render(<Scratchpad me="A Manager" />);
    await userEvent.click(await screen.findByRole("button", { name: /Example note/ }));
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(await screen.findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(views).toEqual([]);
  });
});
