import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findScreen, SCREENS } from "../App";
import { resetServerSession } from "../lib/api";
import owned from "../ownerScreens.json";
import { RecordsView } from "./RecordsView";
import { parseRoute, slotRoute, sizeWords, type DriveListing, type Holder, type SlotPageData, type SlotRow, type SlotsPage } from "./recordTypes";

beforeEach(() => resetServerSession());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

// Made-up slots, files, and people in the shapes the loaders return; no real service is called.
const row = (over: Partial<SlotRow>): SlotRow => ({
  key: "example/policy", title: "Example policy", group: "records", requires: ["CIV 9999"], cardinality: "one", state: "empty", stateWord: "empty", held: 0, cells: 0,
  periods: [], confidential: false, hidden: "", source: "document kinds", gate: "", kinds: ["policy"], pins: 0, candidates: 0, collision: false, problem: "",
  waitsOn: [], closed: false, bindings: 0, ...over,
});
const LIST: SlotsPage = {
  found: true, asOf: "2099-10-05", profile: "example", driveConnected: null, driveCatalog: { files: 120, syncedAt: "2099-10-01T00:00:00" },
  counts: { total: 4, byState: { empty: 2, picked: 0, uploaded: 0, classified: 0, read: 1, confirmed: 0, notApplicable: 0, doesNotExist: 0, waiting: 0, problem: 1 }, held: 1, hidden: 1 },
  states: [{ value: "empty", word: "empty", meaning: "nobody has spoken for this slot (not: the record does not exist)" }, { value: "read", word: "read", meaning: "jason's readers ran" },
           { value: "problem", word: "problem", meaning: "reads as another kind" }, { value: "picked", word: "picked", meaning: "" }],
  groups: [
    { key: "records", title: "Association records", law: "CIV 9999", opensGate: "ingest", counts: { total: 3, held: 1, answered: 0, inHand: 2, hidden: 0 }, slots: [
      row({}), row({ key: "records/9999/minutes", title: "Meeting minutes", cardinality: "series", state: "read", stateWord: "read", pins: 2, held: 1,
                     periods: [{ period: "2099", state: "read" }, { period: "2098", state: "empty" }], cells: 2, confidential: true }),
      row({ key: "example/map", title: "Example map", state: "problem", stateWord: "problem", problem: "reads as a deed, not a map", pins: 1, collision: true }),
    ] },
    { key: "delivery", title: "Developer deliveries", law: "", opensGate: "", counts: { total: 1, held: 0, answered: 0, inHand: 0, hidden: 1 }, slots: [
      row({ key: "example/plan", title: "Example plan set", group: "delivery", requires: [], hidden: "no plan set for a conversion" }),
    ] },
  ],
  biggestUnknowns: [{ key: "example/policy", title: "Example policy", why: "the ingest gate waits on it", blocks: ["example/map"] }],
  caveats: ["A slot's state is jason's reading of records."],
};

const holder = (over: Partial<Holder>): Holder => ({
  pin: "p-1", origin: "person", source: "a person", kind: "drive", name: "Policy 2099.pdf", ref: "1AbC", period: "", by: "Jane Example", at: "2099-10-03",
  note: "", state: "read", stateWord: "read", held: false, opens: "",
  reading: { found: true, readsAs: "policy", readers: ["name rule"], tier: "suggested", read: true, confirmedBy: "", confirmedAt: "" },
  problem: "", wrongSlot: null,
  readback: { readAt: "2099-10-04T10:00:00+00:00", readBy: "Jane Example", sha256: "ab12cd34ef56", size: 412345, type: "application/pdf",
    readers: { "name rule": "policy", "phrase rule": "policy" }, method: "RULE", tier: "likely", readsAs: "policy", text: { source: "pdf text", chars: 9120 },
    alreadyFiled: false, preflight: { pages: 6, blank: 1, withText: 5, suspectShare: 0.02, recommend: [{ action: "re-read", pages: "3", reason: "faint scan" }] },
    segments: null, findings: [{ code: "blank pages", text: "1 blank page(s), kept in the original" }], changed: null, split: null, history: [], held: false },
  ...over,
});
const SLOT = (over: Partial<SlotPageData> = {}): SlotPageData => ({
  ...row({}), found: true, why: "jason's own design needs it", existence: { possible: true, answer: null }, shelf: ["governing"], record: "", delivery: "",
  holders: [holder({})], bindings: [], more: null, specificationFolders: [], holding: null, collisions: [], candidates: [],
  standing: { pinned: 1, read: 1, duties: [{ anchor: "Keep the policy", keeps: "the adopted policy", cadence: "annual", when: "January", sections: "CIV 9999", produce: "a list", because: "it cites CIV 9999", command: "jason duties --brief \"Keep the policy\"" }],
    conflicts: { count: 1, open: 1, held: false, items: [{ key: "c1", provision: "Article 9", authority: "CIV 9999", status: "open", clarity: "plain", open: true, boardItem: "item-7", because: "it cites CIV 9999" }] },
    programs: { available: false, items: [], why: "the program catalog is not built" }, caveats: ["A duty listed here is a lead for the board."] },
  acts: { pickFile: true, answer: true, unpin: true, pickFolder: true, read: true, keep: false, repin: true, more: false, reopen: false, upload: true, replace: false, split: false, ack: false, why: "" },
  log: [{ at: "2099-10-03T00:00:00", by: "Jane Example", act: "pick", pin: "p-1" }],
  commands: { slot: "jason records --slot example/policy" }, caveats: ["A confidential file is held back."], ...over,
});

interface Call { url: string; method: string; body?: Record<string, unknown> }
type Route = (c: Call) => unknown;
function serve(route: Route) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const u = String(url);
    if (u.startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn: { name: "Ada Admin", role: "administrator" } }), { status: 200 });
    const call: Call = { url: u, method, body: init?.body ? JSON.parse(String(init.body)) : undefined };
    if (method === "POST") calls.push(call);
    const out = route(call);
    if (out instanceof Response) return out;
    if (out === undefined) return new Response(JSON.stringify({ error: `no route ${method} ${u}` }), { status: 404 });
    return new Response(JSON.stringify(out), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
const refuse = (status: number, error: string) => new Response(JSON.stringify({ error }), { status, headers: { "Content-Type": "application/json" } });
const at = (key: string) => { window.location.hash = `#/setup/records/${encodeURIComponent(key)}`; };
const SLOT_URL = "/api/write/records/example/policy";

describe("the routes", () => {
  it("is a Setup screen for officers, managers, and administrators, never an owner screen", () => {
    const s = SCREENS.find((x) => x.id === "setup/records");
    expect(s?.group).toBe("Setup");
    expect(s?.roles).toEqual(["officer", "manager", "administrator"]);
    expect(s?.owner).toBeFalsy();
    expect(Object.keys(owned.screens)).not.toContain("setup/records");
  });

  it("lands a slot's route, with its key URL-encoded, on the Records screen", () => {
    expect(findScreen("setup/records")?.id).toBe("setup/records");
    expect(findScreen("setup/records/records%2F5200%2Fminutes")?.id).toBe("setup/records");
    expect(findScreen("setup/records/records/5200/minutes")?.id).toBe("setup/records");
    expect(findScreen("setup/limits")?.id).toBe("setup/limits");
    expect(findScreen("actions/anything")?.id).toBe("actions");
  });

  it("reads a slot key out of the hash and puts none of a file's name in it", () => {
    expect(slotRoute("records/5200/minutes")).toBe("#/setup/records/records%2F5200%2Fminutes");
    expect(parseRoute("setup/records/records%2F5200%2Fminutes?state=empty").key).toBe("records/5200/minutes");
    expect(parseRoute("setup/records/records%2F5200%2Fminutes?state=empty").query.get("state")).toBe("empty");
    expect(parseRoute("setup/records").key).toBe("");
    expect(sizeWords(412345)).toBe("403 KB");
  });
});

describe("the checklist", () => {
  const page = () => serve((c) => (c.url.startsWith("/api/record-slots") ? LIST : undefined));

  it("shows the slots by group with a count for each state, each row in words with its law and next step", async () => {
    page();
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    const table = await screen.findByRole("table", { name: "Association records: 3 slots, by state" });
    const minutes = within(table).getByText("Meeting minutes").closest("tr")!;
    expect(minutes).toHaveTextContent("read");
    expect(minutes).toHaveTextContent("2099: read");
    expect(minutes).toHaveTextContent("2098: empty");
    expect(minutes).toHaveTextContent("1 held back");
    expect(within(table).getByText("Meeting minutes")).toHaveAttribute("href", "#/setup/records/records%2F9999%2Fminutes");
    const map = within(table).getByText("Example map").closest("tr")!;
    expect(map).toHaveTextContent("reads as a deed, not a map");
    expect(map).toHaveTextContent("two holders");
    const counts = screen.getByRole("region", { name: "Slots by state" });
    expect(within(counts).getByRole("button", { name: /^2 empty/ })).toBeInTheDocument();
    expect(within(counts).getByRole("button", { name: /^1 problem/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "The biggest unknowns first" })).toBeInTheDocument();
    expect(screen.getByText("the ingest gate waits on it", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("A slot's state is jason's reading of records.")).toBeInTheDocument();
  });

  it("says what the profile hid, and what a slot with no law is", async () => {
    page();
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    await screen.findByRole("table", { name: /Association records/ });
    await userEvent.setup().click(screen.getByRole("heading", { name: "Developer deliveries" }));
    expect(await screen.findByText(/hidden by the profile: no plan set for a conversion/)).toBeInTheDocument();
    expect(screen.getByText("jason's own design")).toBeInTheDocument();
  });

  it("counts each group as N of M held or answered, names the gate it opens, and keeps the server's order", async () => {
    page();
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    const group = (await screen.findByRole("heading", { name: "Association records" })).closest("summary")!;
    expect(group).toHaveTextContent("2 of 3 held or answered, CIV 9999; opens the ingest gate; 1 file held back as confidential");
    expect(group).not.toHaveTextContent("answered, 1 held back");
    expect(screen.getByRole("heading", { name: "Developer deliveries" }).closest("summary")).toHaveTextContent("0 of 0 held or answered, 1 hidden by the profile");
    const rows = within(screen.getByRole("table", { name: /Association records/ })).getAllByRole("row").slice(1).map((r) => r.getAttribute("data-slot"));
    expect(rows).toEqual(["example/policy", "records/9999/minutes", "example/map"]);
  });

  it("filters to the confidential slots and puts the whole list back", async () => {
    page();
    window.location.hash = "#/setup/records";
    const user = userEvent.setup();
    render(<RecordsView />);
    const chip = await screen.findByRole("button", { name: "Confidential (1)" });
    expect(chip).toHaveAttribute("aria-pressed", "false");
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("table", { name: "Association records: 1 slots, by state" })).toBeInTheDocument();
    expect(screen.queryByText("Example map")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show every slot" }));
    expect(await screen.findByText("Example map")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confidential (1)" })).toHaveAttribute("aria-pressed", "false");
  });

  it("warns above the list when Drive is not connected, and says when every slot is held or answered", async () => {
    serve((c) => (c.url.startsWith("/api/record-slots") ? { ...LIST, driveConnected: false, driveWhy: "jason has no Drive sign-in.", driveCommand: "jason sign-in --name example", allInHand: true } : undefined));
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    const banner = await screen.findByText(/jason has no Drive sign-in/);
    expect(banner.closest("[role=alert]")).toHaveTextContent("jason sign-in --name example");
    expect(screen.getByText(/Every slot is held or answered/)).toBeInTheDocument();
  });

  it("says neither when Drive is unknown and slots remain empty", async () => {
    page();
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    await screen.findByRole("table", { name: /Association records/ });
    expect(screen.queryByText(/Every slot is held or answered/)).toBeNull();
    expect(screen.queryByText(/jason cannot read Drive/)).toBeNull();
  });

  it("filters by a state chip and puts the whole list back", async () => {
    page();
    window.location.hash = "#/setup/records";
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: /^1 problem/ }));
    const table = screen.getByRole("table", { name: "Association records: 1 slots, by state" });
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(screen.queryByText("Meeting minutes")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show every slot" }));
    expect(await screen.findByText("Meeting minutes")).toBeInTheDocument();
  });

  it("opens a first run with a note when nothing has been picked", async () => {
    serve((c) => (c.url.startsWith("/api/record-slots") ? { ...LIST, counts: { ...LIST.counts, byState: { ...LIST.counts.byState, empty: 4, read: 0, problem: 0 } } } : undefined));
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    expect(await screen.findByText(/Nothing has been picked yet/)).toBeInTheDocument();
  });

  it("gives the server's note when the checklist is not there", async () => {
    serve(() => ({ found: false, note: "no checklist yet" }));
    window.location.hash = "#/setup/records";
    render(<RecordsView />);
    expect(await screen.findByText("no checklist yet")).toBeInTheDocument();
  });
});

describe("a slot", () => {
  const open = (data: SlotPageData, extra?: Route) => {
    at(data.key);
    return serve((c) => (c.url.startsWith("/api/record-slot?key=") ? data : extra?.(c)));
  };

  it("recites what requires it, shows the holder and the four lines of the reading, the standing block, and the trail", async () => {
    const calls = open(SLOT());
    render(<RecordsView />);
    expect(await screen.findByRole("heading", { level: 1, name: "Example policy" })).toBeInTheDocument();
    expect(screen.getByText("CIV 9999", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText(/stored copy, never a paraphrase/)).toBeInTheDocument();
    const card = screen.getByText("Policy 2099.pdf", { selector: "strong.record-holder-name" }).closest("li")!;
    expect(card).toHaveTextContent("Pinned by Jane Example, 2099-10-03");
    expect(card).toHaveTextContent("jason read it as policy (likely; name rule: policy; phrase rule: policy)");
    expect(within(card).getByText("agrees")).toBeInTheDocument();
    expect(card).toHaveTextContent("403 KB");
    expect(card).toHaveTextContent("6, 1 blank, 5 with a text layer, 2% of the text layer doubtful");
    expect(card).toHaveTextContent("re-read pages 3: faint scan");
    expect(within(card).getByRole("list", { name: "What jason found" })).toHaveTextContent("1 blank page(s)");
    expect(screen.getByText("Keep the policy")).toBeInTheDocument();
    expect(screen.getByText(/Article 9/)).toBeInTheDocument();
    expect(screen.getByText(/Unavailable: the program catalog is not built/)).toBeInTheDocument();
    const log = screen.getByRole("table", { name: "Acts on this slot" });
    expect(within(log).getByText("2099-10-03")).toBeInTheDocument();
    expect(calls).toHaveLength(0);                                   // reading a slot writes nothing
  });

  it("recites the stored words of what requires it, and says in words what is not on the shelf", async () => {
    open(SLOT({ requires: ["CIV 9999(a)", "CIV 8888"], recitals: [
      { requires: "CIV 9999(a)", found: true, citation: "CIV 9999", text: "(a) Made-up operative words.", inForce: "the 2099 publication", caveat: "jason's consolidated text is not an official restatement.",
        note: "jason could not isolate CIV 9999(a) in the stored words, so the whole of CIV 9999 is recited." },
      { requires: "CIV 8888", found: false, citation: "CIV 8888", reason: "not_on_shelf", detail: "jason holds no stored words for this citation" },
    ] }));
    render(<RecordsView />);
    const section = (await screen.findByRole("heading", { name: "What requires it" })).closest("section")!;
    expect(within(section).getByText("(a) Made-up operative words.")).toBeInTheDocument();
    expect(section).toHaveTextContent("jason's consolidated text is not an official restatement.");
    expect(section).toHaveTextContent("so the whole of CIV 9999 is recited");
    expect(section).toHaveTextContent("Not found: CIV 8888");
    expect(section).toHaveTextContent("Nothing is quoted.");
  });

  it("puts a wrong-slot alert above everything else on the slot page, not inside the holder", async () => {
    open(SLOT({ holders: [holder({ wrongSlot: { readsAs: "deed", expects: ["policy"], fits: [], acts: ["keep"] } })] }));
    render(<RecordsView />);
    const alert = await screen.findByRole("alert");
    const requires = screen.getByRole("heading", { name: "What requires it" });
    expect(alert.compareDocumentPosition(requires) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(alert.closest(".record-holder")).toBeNull();
  });

  it("shows a confidential file masked, with no id and a way to open it", async () => {
    open(SLOT({ confidential: true, holders: [holder({ name: "a confidential file (kind: legal)", held: true, opens: "opens in the private view", ref: "",
      readback: { ...holder({}).readback!, held: true, findings: [] } })] }));
    render(<RecordsView />);
    expect(await screen.findByText("a confidential file (kind: legal)", { selector: ".record-holder-name" })).toBeInTheDocument();
    expect(screen.getAllByText(/opens in the private view/).length).toBeGreaterThan(0);
    expect(screen.getByText("held back")).toBeInTheDocument();
    expect(screen.getByText(/Its findings are held back outside the private view/)).toBeInTheDocument();
  });

  it("shows a wrong-slot pick first, and moves it with a preview then a confirm, recorded as the signed-in person", async () => {
    const wrong = holder({ state: "problem", stateWord: "problem", problem: "reads as a deed", wrongSlot: { readsAs: "deed", expects: ["policy"], fits: [{ key: "example/deed", title: "Example deed" }], acts: ["repin", "keep", "unpin"] },
      reading: { found: true, readsAs: "deed", readers: ["name rule"], tier: "suggested", read: true, confirmedBy: "", confirmedAt: "" },
      readback: { ...holder({}).readback!, readsAs: "deed", tier: "suggested", readers: { "name rule": "deed", "phrase rule": null } } });
    const calls = open(SLOT({ holders: [wrong], acts: { ...SLOT().acts, keep: true } }), (c) =>
      c.url === SLOT_URL ? (c.body?.dryRun ? { ok: true, dryRun: true, would: { act: "repin", from: "example/policy", to: "example/deed", by: "Ada Admin" }, note: "A dry run: nothing was written." } : { ok: true, pin: "p-9" }) : undefined);
    const user = userEvent.setup();
    render(<RecordsView />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This may be the wrong slot.");
    expect(alert).toHaveTextContent("jason reads it as deed (suggested)");
    expect(alert).toHaveTextContent("It fits: Example deed.");
    await user.click(within(alert).getByRole("button", { name: /^Pin it to Example deed/ }));
    expect(screen.getByRole("heading", { name: "Move Policy 2099.pdf to the slot it fits" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Preview the move" }));
    expect(calls[0].url).toBe(SLOT_URL);
    expect(calls[0].body).toMatchObject({ act: "repin", pin: "p-1", to: "example/deed", by: "Ada Admin", dryRun: true });
    const region = await screen.findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("Recorded as Ada Admin");
    expect(within(region).getByText("example/deed", { selector: "dd" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pin Policy 2099.pdf to Example deed instead" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1].body).toMatchObject({ act: "repin", dryRun: false });
    expect(await screen.findByText(/Recorded as Ada Admin\./)).toBeInTheDocument();
  });

  it("keeps a pick anyway only with a reason, and drops the preview when the reason changes", async () => {
    const wrong = holder({ wrongSlot: { readsAs: "deed", expects: ["policy"], fits: [], acts: ["keep", "unpin"] } });
    const calls = open(SLOT({ holders: [wrong] }), (c) => (c.url === SLOT_URL ? { ok: true, dryRun: true, would: { act: "keep" }, note: "dry" } : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Keep it here anyway" }));
    const preview = screen.getByRole("button", { name: "Preview" });
    expect(preview).toBeDisabled();
    await user.type(screen.getByLabelText(/Why this file belongs here/), "It is the adopted copy");
    await user.click(preview);
    expect(calls[0].body).toMatchObject({ act: "keep", pin: "p-1", note: "It is the adopted copy" });
    await screen.findByRole("region", { name: "What will be recorded" });
    await user.type(screen.getByLabelText(/Why this file belongs here/), "!");
    expect(screen.queryByRole("region", { name: "What will be recorded" })).toBeNull();
  });

  it("shows a refusal in the server's words and writes nothing", async () => {
    const said = "A pick names who made it. Nothing was written.";
    open(SLOT(), (c) => (c.url === SLOT_URL ? refuse(400, said) : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Unpin Policy 2099.pdf" }));
    await user.click(screen.getByRole("button", { name: "Preview the unpin" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(said);
    expect(screen.queryByRole("region", { name: "What will be recorded" })).toBeNull();
  });

  it("records none exists with where the person looked, then reopens it", async () => {
    const calls = open(SLOT({ holders: [] }), (c) => (c.url === SLOT_URL ? { ok: true, dryRun: !!c.body?.dryRun, would: { act: "answer", answer: "none" } } : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Answer: none, not applicable, or waiting" }));
    const preview = screen.getByRole("button", { name: "Preview the answer" });
    expect(preview).toBeDisabled();
    await user.type(screen.getByLabelText("Where you looked (required)"), "The binder and the old manager's files");
    await user.click(preview);
    expect(calls[0].body).toMatchObject({ act: "answer", value: "none", note: "The binder and the old manager's files", dryRun: true });
    await user.click(await screen.findByRole("button", { name: "Record that Example policy does not exist" }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "answer", dryRun: false }));
  });

  it("shows a standing answer with its words and offers to reopen it", async () => {
    open(SLOT({ holders: [], existence: { possible: true, answer: { id: "a1", answer: "none", word: "does not exist", by: "Jane Example", at: "2099-10-02", reason: "Looked in the binder", who: "", source: "person", held: false } },
      acts: { ...SLOT().acts, reopen: true } }));
    render(<RecordsView />);
    expect(await screen.findByText(/by Jane Example, 2099-10-02: Looked in the binder/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reopen the answer" })).toBeInTheDocument();
  });

  it("previews a read with its size, then queues a job and watches it until it is done", async () => {
    const calls = open(SLOT(), (c) => {
      if (c.url === SLOT_URL && c.body?.dryRun) return { ok: true, dryRun: true, reads: [{ pin: "p-1", slot: "example/policy", ok: true, plan: { name: "Policy 2099.pdf", size: 412345, willFetch: true }, reads: "the file, in jason's store" }], note: "A dry run: nothing was fetched." };
      if (c.url === SLOT_URL) return { ok: true, queued: true, job: 7, command: "jason records --read example/policy --yes" };
      if (c.url.startsWith("/api/jobs?job=7")) return { found: true, job: { id: 7, status: "done", summary: "read 1 file" } };
      return undefined;
    });
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Read again: Policy 2099.pdf" }));
    await user.click(screen.getByRole("button", { name: "Show what would be read" }));
    const region = await screen.findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("Policy 2099.pdf, 403 KB");
    expect(region).toHaveTextContent("It would be fetched into jason's store.");
    await user.click(screen.getByRole("button", { name: "Queue the reading of Policy 2099.pdf" }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "read", dryRun: false }));
    expect(await screen.findByText(/The reading is queued as job 7/)).toBeInTheDocument();
    expect(await screen.findByText("job 7: done")).toBeInTheDocument();
  });

  it("names a failed job and keeps the pick", async () => {
    open(SLOT(), (c) => {
      if (c.url === SLOT_URL && c.body?.dryRun) return { ok: true, dryRun: true, reads: [] };
      if (c.url === SLOT_URL) return { ok: true, queued: true, job: 8 };
      if (c.url.startsWith("/api/jobs?job=8")) return { found: true, job: { id: 8, status: "failed", summary: "Drive refused" } };
      return undefined;
    });
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Read again: Policy 2099.pdf" }));
    await user.click(screen.getByRole("button", { name: "Show what would be read" }));
    await user.click(await screen.findByRole("button", { name: "Queue the reading of Policy 2099.pdf" }));
    expect(await screen.findByText("job 8: failed")).toBeInTheDocument();
    expect(screen.getByText(/The reading failed/)).toBeInTheDocument();
  });

  it("acknowledges a changed file", async () => {
    const changed = { ...holder({}).readback!, changed: { at: "2099-10-05", diff: [{ fact: "size", before: 100, after: 200 }] } };
    const calls = open(SLOT({ holders: [holder({ readback: changed })], acts: { ...SLOT().acts, ack: true } }), (c) => (c.url === SLOT_URL ? { ok: true, dryRun: !!c.body?.dryRun, would: { act: "ack" } } : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    expect(await screen.findByText(/The file changed since it was read/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Acknowledge the change to Policy 2099.pdf" }));
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await user.click(await screen.findByRole("button", { name: "Record that I have seen the change" }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "ack", pin: "p-1", dryRun: false }));
  });

  it("replaces a pick in one step and shows both halves in the dry run", async () => {
    const calls = open(SLOT(), (c) => (c.url === SLOT_URL ? (c.body?.dryRun
      ? { ok: true, dryRun: true, would: { act: "replace" }, first: { would: { act: "pick", slot: "example/policy" }, note: "pin the new file" }, then: { would: { act: "unpin", pin: "p-1" }, note: "unpin the old one" }, note: "A dry run." }
      : { ok: true, pin: "p-2", replaced: "p-1" }) : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Replace Policy 2099.pdf" }));
    await user.type(screen.getByLabelText("Drive link or id"), "https://drive.google.com/file/d/NEW/view");
    await user.click(screen.getByRole("button", { name: "Preview both halves" }));
    expect(calls[0].body).toMatchObject({ act: "replace", pin: "p-1", file: "https://drive.google.com/file/d/NEW/view", dryRun: true });
    const region = await screen.findByRole("region", { name: "What will be recorded" });
    expect(within(region).getByRole("heading", { name: "First" })).toBeInTheDocument();
    expect(within(region).getByRole("heading", { name: "Then" })).toBeInTheDocument();
    expect(region).toHaveTextContent("pin the new file");
    expect(region).toHaveTextContent("unpin the old one");
    await user.click(screen.getByRole("button", { name: "Pin the new file and unpin Policy 2099.pdf" }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "replace", dryRun: false }));
    expect(await screen.findByText(/The new file is pinned and the old one unpinned/)).toBeInTheDocument();
  });

  it("confirms the parts of a combined scan with a slot for each, shows a collision, and writes only what was named", async () => {
    const proposal = [
      { segment: "s1", pages: [1, 34] as [number, number], kind: "declaration", tier: "suggested", readers: ["rules"], slots: [{ key: "example/declaration", title: "Example declaration" }], confirmed: false },
      { segment: "s2", pages: [35, 41] as [number, number], kind: "amendment", tier: "likely", readers: ["rules", "phrase"], slots: [{ key: "example/amendment", title: "Example amendment", held: true }], confirmed: false },
    ];
    const scan = holder({ readback: { ...holder({}).readback!, segments: { documents: 2, proposes: true, proposal }, split: { parts: 2, confirmed: [], declined: false, open: true } } });
    const calls = open(SLOT({ holders: [scan], acts: { ...SLOT().acts, split: true } }), (c) => (c.url === SLOT_URL ? (c.body?.dryRun
      ? { ok: true, dryRun: true, would: { act: "split" }, parts: [
          { segment: "s1", pages: [1, 34], slot: "example/declaration", action: "fill", fits: true },
          { segment: "s2", pages: [35, 41], slot: "example/amendment", action: "collision", why: "example/amendment already holds a file", kept: "the file already there; this part was not written" }] }
      : { ok: true, filled: [{}] }) : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    expect(await screen.findByText(/A combined scan: 2 documents proposed/)).toBeInTheDocument();
    expect(screen.getAllByText("proposed only")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Confirm the split of Policy 2099.pdf" }));
    const preview = screen.getByRole("button", { name: "Preview the split" });
    expect(preview).toBeDisabled();                                                          // a part not named fills nothing
    await user.selectOptions(screen.getByLabelText("Slot for pages 1 to 34"), "example/declaration");
    await user.selectOptions(screen.getByLabelText("Slot for pages 35 to 41"), "example/amendment");
    expect(screen.getByRole("option", { name: "Example amendment (already holds a file)" })).toBeInTheDocument();
    await user.click(preview);
    expect(calls[0].body).toMatchObject({ act: "split", pin: "p-1", dryRun: true, parts: [{ segment: "s1", slot: "example/declaration" }, { segment: "s2", slot: "example/amendment" }] });
    const region = await screen.findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("a collision, so this part is not written");
    await user.click(screen.getByRole("button", { name: "Confirm 2 parts of Policy 2099.pdf" }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "split", dryRun: false }));
  });

  it("declines a proposed split", async () => {
    const scan = holder({ readback: { ...holder({}).readback!, segments: { documents: 2, proposes: true, proposal: [] }, split: { parts: 2, confirmed: [], declined: false, open: true } } });
    const calls = open(SLOT({ holders: [scan] }), (c) => (c.url === SLOT_URL ? { ok: true, dryRun: !!c.body?.dryRun, would: { act: "split" } } : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Decline the split of Policy 2099.pdf" }));
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await user.click(await screen.findByRole("button", { name: "Record that this file is one document" }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "split", decline: true, dryRun: false }));
  });

  it("binds a folder, shows the proposed rule's text, and applies nothing", async () => {
    const calls = open(SLOT({ holders: [] }), (c) => (c.url === SLOT_URL ? { ok: true, dryRun: true, would: { act: "bind" }, proposal: { kind: "sync rule", record: "x", text: "SyncRule(\n    id=DocumentRule.<choose>,\n)", note: "The rule's id is the association's to choose." } } : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Bind a Drive folder" }));
    await user.type(screen.getByLabelText("Drive folder link or id"), "FOLDER1");
    await user.click(screen.getByRole("button", { name: "Continue to the preview" }));
    await user.click(screen.getByRole("button", { name: "Preview the binding" }));
    expect(calls[0].body).toMatchObject({ act: "bind", folder: "FOLDER1", dryRun: true });
    const region = await screen.findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("Nothing is applied here.");
    expect(region).toHaveTextContent("SyncRule(");
    expect(calls).toHaveLength(1);
  });
});

describe("the Drive chooser", () => {
  const TOP: DriveListing = { found: true, driveConnected: true, account: "jason@example.org", parent: { name: "My Drive", path: [{ name: "My Drive" }] },
    items: [
      { id: "F1", name: "Records", type: "folder", size: null, modified: "2099-09-01", owner: "", sharedDrive: false, readable: true, why: "", held: false, opens: "", doc: "", jason: {} },
      { id: "D1", name: "Policy 2099.pdf", type: "PDF", size: 412345, modified: "2099-09-30", owner: "Jane Example", sharedDrive: false, readable: true, why: "", held: false, opens: "", doc: "",
        jason: { inLibrary: "policy", ruleCovers: true, pinnedFor: ["example/map"] } },
      { id: "", name: "a confidential file (kind: legal)", type: "PDF", size: 100, modified: "2099-09-30", owner: "", sharedDrive: false, readable: true, why: "", held: true, opens: "opens in the private view", doc: "", jason: { kind: "legal" } },
      { id: "D3", name: "Locked.pdf", type: "PDF", size: 100, modified: "2099-09-30", owner: "", sharedDrive: false, readable: false, why: "not shared with jason's account", held: false, opens: "", doc: "", jason: {} },
    ], drives: [{ name: "Shared records", id: "SD1", type: "drive" }], empty: "", next: null };
  const INSIDE: DriveListing = { ...TOP, parent: { name: "Records", path: [{ name: "My Drive" }, { name: "Records" }] }, drives: [],
    items: [{ id: "D2", name: "Minutes 2099-06.doc", type: "Doc", size: 5000, modified: "2099-06-30", owner: "", sharedDrive: false, readable: true, why: "", held: false, opens: "", doc: "A Doc: jason keeps a Word copy; the Doc stays the original.", jason: {} }] };
  const drive = (extra?: Route): Route => (c) => {
    if (c.url.startsWith("/api/record-slot?key=")) return SLOT({ holders: [] });
    if (c.url === "/api/limits") return { limits: [{ key: "upload.max_bytes", value: 100e6, words: "100 MB" }] };
    if (c.url === "/api/write/drive/list") return c.body?.parent === "F1" ? INSIDE : TOP;
    return extra?.(c);
  };
  const choose = async (user: ReturnType<typeof userEvent.setup>) => {
    at("example/policy");
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Choose from Drive" }));
    return screen.findByRole("dialog", { name: "Choose a file from Drive for Example policy" });
  };

  it("lists Drive through POST reads (no name or id in a URL), opens a folder, and says whose eyes jason has", async () => {
    const calls = serve(drive());
    const user = userEvent.setup();
    const dialog = await choose(user);
    expect(await within(dialog).findByText(/jason's Drive account \(jason@example.org\) can see these files/)).toBeInTheDocument();
    expect(within(dialog).getByText("shared drive")).toBeInTheDocument();
    expect(within(dialog).getByText(/already in the library as policy/)).toBeInTheDocument();
    expect(within(dialog).getByText(/in a folder a sync rule covers/)).toBeInTheDocument();
    expect(within(dialog).getByRole("radio", { name: /Policy 2099\.pdf/ })).toBeEnabled();
    expect(within(dialog).getByRole("radio", { name: /a confidential file/ })).toBeDisabled();
    expect(within(dialog).getByRole("radio", { name: /Locked\.pdf/ })).toBeDisabled();
    expect(within(dialog).getByText(/jason cannot open this file: not shared with jason's account/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Open the folder Records" }));
    expect(await within(dialog).findByText("Minutes 2099-06.doc")).toBeInTheDocument();
    expect(within(dialog).getByText(/jason keeps a Word copy/)).toBeInTheDocument();
    expect(within(dialog).getByRole("navigation", { name: "Folder path" })).toHaveTextContent("My Drive / Records");
    expect(within(dialog).getByRole("button", { name: "Records" })).toHaveAttribute("aria-current", "page");
    expect(calls.every((c) => c.url.startsWith("/api/write/drive/") && !c.url.includes("F1"))).toBe(true);
    expect(calls[1].body).toMatchObject({ parent: "F1" });
  });

  it("picks a file: select it, preview the pick, then confirm, with nothing moved", async () => {
    const calls = serve(drive((c) => (c.url === SLOT_URL ? (c.body?.dryRun ? { ok: true, dryRun: true, would: { act: "pick", slot: "example/policy" }, note: "A dry run." } : { ok: true, pin: "p-5", written: "spec/example/records.json" }) : undefined)));
    const user = userEvent.setup();
    const dialog = await choose(user);
    expect(within(dialog).getByRole("button", { name: "Pick" })).toBeDisabled();
    await user.click(await within(dialog).findByRole("radio", { name: /Policy 2099\.pdf/ }));
    expect(within(dialog).getByText("selected")).toBeInTheDocument();
    expect(within(dialog).getByText("1 file selected for Example policy: Policy 2099.pdf")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Pick" }));
    expect(within(dialog).getByText(/It moves, copies, renames, and shares nothing in Drive/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Preview the pick" }));
    const pick = calls.find((c) => c.url === SLOT_URL)!;
    expect(pick.body).toMatchObject({ act: "pick", file: "D1", by: "Ada Admin", dryRun: true });
    await user.click(await within(dialog).findByRole("button", { name: "Pin Policy 2099.pdf to Example policy" }));
    await waitFor(() => expect(calls.filter((c) => c.url === SLOT_URL)).toHaveLength(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByText(/Recorded as Ada Admin\./)).toBeInTheDocument();
  });

  it("searches by name in a request body, never in a URL", async () => {
    const calls = serve(drive((c) => (c.url === "/api/write/drive/search" ? { ...TOP, items: [TOP.items![1]], drives: [] } : undefined)));
    const user = userEvent.setup();
    const dialog = await choose(user);
    await user.type(within(dialog).getByLabelText("Search by file name"), "Policy");
    await user.click(within(dialog).getByRole("button", { name: "Search" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/write/drive/search")).toBe(true));
    expect(calls.find((c) => c.url === "/api/write/drive/search")!.body).toMatchObject({ q: "Policy" });
    expect(calls.every((c) => !c.url.includes("Policy"))).toBe(true);
    expect(await within(dialog).findByRole("button", { name: "Back to folders" })).toBeInTheDocument();
  });

  it("tells a Drive that is not connected, with the command, and leaves the upload tab", async () => {
    serve((c) => (c.url === "/api/write/drive/list" ? { found: false, driveConnected: false, why: "jason has no Drive sign-in.", command: "jason google sign-in --name drive --interactive" } : drive()(c)));
    const user = userEvent.setup();
    const dialog = await choose(user);
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("jason has no Drive sign-in.");
    expect(within(dialog).getByText("jason google sign-in --name drive --interactive")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("tab", { name: "From this computer" }));
    expect(within(dialog).getByLabelText(/^File \(a PDF/)).toBeInTheDocument();
  });

  it("closes on Escape and says nothing was picked, returning focus to the button", async () => {
    serve(drive());
    const user = userEvent.setup();
    await choose(user);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(await screen.findByText("Nothing was picked.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Choose from Drive" })).toHaveFocus());
  });

  it("moves between its sources with the arrow keys", async () => {
    serve(drive());
    const user = userEvent.setup();
    const dialog = await choose(user);
    const tabs = within(dialog).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Drive", "Paste a link", "From this computer"]);
    tabs[0].focus();
    await user.keyboard("{ArrowRight}");
    expect(within(dialog).getByRole("tab", { name: "Paste a link" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(within(dialog).getByRole("tab", { name: "From this computer" })).toHaveAttribute("aria-selected", "true");
  });

  it("looks a pasted link up, reads out what was found, and picks it by the pasted text", async () => {
    const calls = serve(drive((c) => {
      if (c.url === "/api/write/drive/resolve") return { found: true, kind: "file", id: "ZZ", name: "Bylaws 2099.pdf", type: "PDF", size: 400000, modified: "2099-09-30", readable: true, held: false, ownerDomain: "example.org", jason: {} };
      if (c.url === SLOT_URL) return { ok: true, dryRun: true, would: { act: "pick" } };
      return undefined;
    }));
    const user = userEvent.setup();
    const dialog = await choose(user);
    await user.click(within(dialog).getByRole("tab", { name: "Paste a link" }));
    await user.type(within(dialog).getByLabelText("Drive link or id"), "https://drive.google.com/file/d/ZZ/view");
    await user.click(within(dialog).getByRole("button", { name: "Look it up" }));
    expect(await within(dialog).findByText(/Found:/)).toHaveTextContent("Found: Bylaws 2099.pdf, a PDF, 391 KB, modified 2099-09-30, owned in example.org.");
    expect(calls.find((c) => c.url === "/api/write/drive/resolve")!.body).toEqual({ ref: "https://drive.google.com/file/d/ZZ/view" });
    await user.click(within(dialog).getByRole("button", { name: "Pick this file for Example policy" }));
    await user.click(within(dialog).getByRole("button", { name: "Preview the pick" }));
    expect(calls.find((c) => c.url === SLOT_URL)!.body).toMatchObject({ act: "pick", file: "https://drive.google.com/file/d/ZZ/view" });
  });

  it("says in a sentence that a pasted link is not found or not Drive's", async () => {
    serve(drive((c) => (c.url === "/api/write/drive/resolve" ? { found: false, driveConnected: true, why: "That is not a Drive link." } : undefined)));
    const user = userEvent.setup();
    const dialog = await choose(user);
    await user.click(within(dialog).getByRole("tab", { name: "Paste a link" }));
    await user.type(within(dialog).getByLabelText("Drive link or id"), "https://example.org/x");
    await user.click(within(dialog).getByRole("button", { name: "Look it up" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("That is not a Drive link.");
  });

  it("offers a pasted folder as a binding, not a pick", async () => {
    serve(drive((c) => (c.url === "/api/write/drive/resolve" ? { found: true, kind: "folder", id: "F9", name: "Minutes", type: "folder", size: null, modified: "2099-01-01", readable: true, held: false, offer: "Choose this folder to read its files as candidates for the slot.", jason: {} } : undefined)));
    const user = userEvent.setup();
    const dialog = await choose(user);
    await user.click(within(dialog).getByRole("tab", { name: "Paste a link" }));
    await user.type(within(dialog).getByLabelText("Drive link or id"), "F9");
    await user.click(within(dialog).getByRole("button", { name: "Look it up" }));
    expect(await within(dialog).findByRole("button", { name: "Choose this folder for Example policy" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /Pick this file/ })).toBeNull();
  });

  it("uploads from this computer: shows the limit, previews the bytes, confirms, and queues the reading", async () => {
    const calls = serve(drive((c) => {
      if (c.url === SLOT_URL && c.body?.dryRun) return { ok: true, dryRun: true, would: { act: "upload", size: 22, type: "pdf", sha256: "abc123", writes: "spec/example/records.json" }, already: false, note: "A dry run: nothing was kept." };
      if (c.url === SLOT_URL) return { ok: true, pin: "p-8", job: 11, queued: true };
      if (c.url.startsWith("/api/jobs?job=11")) return { found: true, job: { id: 11, status: "queued" } };
      return undefined;
    }));
    const user = userEvent.setup();
    const dialog = await choose(user);
    await user.click(within(dialog).getByRole("tab", { name: "From this computer" }));
    expect(await within(dialog).findByText(/The largest file allowed here is 100 MB/)).toBeInTheDocument();
    const preview = within(dialog).getByRole("button", { name: "Preview the upload" });
    expect(preview).toBeDisabled();
    await user.upload(within(dialog).getByLabelText(/^File \(a PDF/), new File(["%PDF-1.4 hello world\n"], "scan.pdf", { type: "application/pdf" }));
    expect(await within(dialog).findByText(/Chosen:/)).toHaveTextContent("scan.pdf");
    await user.click(preview);
    const body = calls.find((c) => c.url === SLOT_URL)!.body!;
    expect(body).toMatchObject({ act: "upload", name: "scan.pdf", dryRun: true });
    expect(atob(String(body.base64))).toBe("%PDF-1.4 hello world\n");
    const region = await within(dialog).findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("sha256");
    await user.click(within(dialog).getByRole("button", { name: "Keep scan.pdf and pin it to Example policy" }));
    expect(await screen.findByText(/The reading is queued as job 11/)).toBeInTheDocument();
    expect(await screen.findByText("job 11: queued")).toBeInTheDocument();
  });

  it("warns that a file is over the limit, points to Drive, and leaves the refusal to the server", async () => {
    const calls = serve(drive((c) => (c.url === SLOT_URL ? refuse(400, "Refused: upload.max_bytes: 150 MB is above the 100 MB limit. Nothing was saved.") : undefined)));
    const user = userEvent.setup();
    const dialog = await choose(user);
    await user.click(within(dialog).getByRole("tab", { name: "From this computer" }));
    await within(dialog).findByText(/The largest file allowed here is 100 MB/);
    const big = new File(["x"], "huge.pdf", { type: "application/pdf" });
    Object.defineProperty(big, "size", { value: 150e6 });
    await user.upload(within(dialog).getByLabelText(/^File \(a PDF/), big);
    expect(await within(dialog).findByText(/over the 100 MB limit/)).toHaveTextContent("Larger files belong on Drive");
    await user.click(within(dialog).getByRole("button", { name: "Preview the upload" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Refused: upload.max_bytes: 150 MB is above the 100 MB limit.");
    expect(calls.filter((c) => c.url === SLOT_URL)).toHaveLength(1);
  });

  it("asks for a period when the slot is a series", async () => {
    at("records/9999/minutes");
    serve((c) => (c.url.startsWith("/api/record-slot?key=") ? SLOT({ key: "records/9999/minutes", title: "Meeting minutes", cardinality: "series", holders: [] }) : drive()(c)));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Choose from Drive" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("checkbox", { name: /Policy 2099\.pdf/ }));
    await user.click(within(dialog).getByRole("button", { name: "Pick" }));
    expect(within(dialog).getByRole("button", { name: "Preview the pick" })).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Period this file is for/), "2099-06");
    expect(within(dialog).getByRole("button", { name: "Preview the pick" })).toBeEnabled();
  });
});

describe("choosing several files in one pick", () => {
  const files = ["A1", "A2", "A3", "A4", "A5"].map((id, i) => ({ id, name: `Minutes 2099-0${i + 1}.pdf`, type: "PDF", size: 1000, modified: "2099-09-30", owner: "", sharedDrive: false, readable: true, why: "", held: false, opens: "", doc: "", jason: {} }));
  const LIST: DriveListing = { found: true, driveConnected: true, account: "jason@example.org", parent: { name: "My Drive", path: [{ name: "My Drive" }] }, items: [...files, { ...files[0], id: "L1", name: "Locked.pdf", readable: false, why: "not shared with jason's account" }], drives: [], empty: "", next: null };
  const PARTS = [
    { n: 1, action: "pin", period: "2099-01", entry: "", note: "" },
    { n: 2, action: "already", period: "2099-02", pin: "p-2", why: "this file is already pinned here" },
    { n: 3, action: "collision", period: "2099-03", why: "example/policy already holds a different file for 2099-03: it was left alone" },
    { n: 4, action: "duplicate", period: "2099-04", why: "named twice in this request" },
    { n: 5, action: "refused", period: "", why: "example/policy is a series: name this file's period" },
  ];
  const COUNTS = { pin: 1, already: 1, collision: 1, duplicate: 1, refused: 1 };
  const go = async (user: ReturnType<typeof userEvent.setup>, slot: Partial<SlotPageData>, write?: Route) => {
    const calls = serve((c) => {
      if (c.url.startsWith("/api/record-slot?key=")) return SLOT({ holders: [], ...slot });
      if (c.url === "/api/limits") return { limits: [] };
      if (c.url === "/api/write/drive/list") return LIST;
      return write?.(c);
    });
    at("example/policy");
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Choose from Drive" }));
    return { calls, dialog: await screen.findByRole("dialog", { name: "Choose a file from Drive for Example policy" }) };
  };

  it("offers checkboxes for a series, counts the files chosen, and keeps a locked file out", async () => {
    const user = userEvent.setup();
    const { dialog } = await go(user, { cardinality: "series" });
    const boxes = await within(dialog).findAllByRole("checkbox");
    expect(boxes).toHaveLength(6);
    expect(within(dialog).queryByRole("radio")).toBeNull();
    expect(within(dialog).getByRole("checkbox", { name: /Locked\.pdf/ })).toBeDisabled();
    expect(within(dialog).getByText(/Up to 100 files go in one pick/)).toBeInTheDocument();
    expect(within(dialog).getByText("No file selected for Example policy")).toBeInTheDocument();
    await user.click(boxes[0]); await user.click(boxes[1]);
    expect(within(dialog).getByText("2 files selected for Example policy")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Clear the selection" }));
    expect(within(dialog).getByText("No file selected for Example policy")).toBeInTheDocument();
  });

  it("keeps one radio for a slot that holds one file", async () => {
    const user = userEvent.setup();
    const { dialog } = await go(user, { cardinality: "one" });
    expect((await within(dialog).findAllByRole("radio")).length).toBe(6);
    expect(within(dialog).queryByRole("checkbox")).toBeNull();
  });

  it("sends one act with every file, and shows each file's result in words, the rows left alone included", async () => {
    const user = userEvent.setup();
    const { calls, dialog } = await go(user, { cardinality: "series" }, (c) => (c.url === SLOT_URL
      ? (c.body?.dryRun ? { ok: true, dryRun: true, would: { act: "pick" }, parts: PARTS, counts: COUNTS, note: "A dry run: nothing was written." }
        : { ok: true, pins: ["p-9"], pin: "p-9", parts: PARTS.map((p) => (p.action === "pin" ? { ...p, pin: "p-9" } : p)), counts: COUNTS }) : undefined));
    for (const b of await within(dialog).findAllByRole("checkbox")) if (!(b as HTMLInputElement).disabled) await user.click(b);
    await user.click(within(dialog).getByRole("button", { name: "Pick 5 files" }));
    const preview = within(dialog).getByRole("button", { name: "Preview the pick of 5 files" });
    expect(preview).toBeDisabled();
    expect(within(dialog).getByText("Name the period each file is for.")).toBeInTheDocument();
    for (let i = 1; i <= 5; i += 1) await user.type(within(dialog).getByLabelText(new RegExp(`^Period this file is for.*Minutes 2099-0${i}\\.pdf$`)), `2099-0${i}`);
    await user.click(preview);
    const writes = () => calls.filter((c) => c.url === SLOT_URL);
    expect(writes()[0].body).toMatchObject({ act: "pick", by: "Ada Admin", dryRun: true });
    expect(writes()[0].body?.files).toEqual([
      { file: "A1", period: "2099-01", entry: "" }, { file: "A2", period: "2099-02", entry: "" }, { file: "A3", period: "2099-03", entry: "" },
      { file: "A4", period: "2099-04", entry: "" }, { file: "A5", period: "2099-05", entry: "" },
    ]);
    const region = await within(dialog).findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("5 files named: 1 to pin, 1 already pinned, 1 in a collision, 1 named twice, 1 refused.");
    const rows = within(region).getAllByRole("listitem");
    expect(rows).toHaveLength(5);
    expect(rows[0]).toHaveTextContent("Will be pinned. File 1: Minutes 2099-01.pdf (2099-01)");
    expect(rows[1]).toHaveTextContent("Already pinned here. File 2: Minutes 2099-02.pdf (2099-02) this file is already pinned here.");
    expect(rows[2]).toHaveTextContent("Left alone: a collision. File 3");
    expect(rows[2]).toHaveTextContent("it was left alone");
    expect(rows[3]).toHaveTextContent("Left alone: named twice. File 4");
    expect(rows[4]).toHaveTextContent("Refused. File 5: Minutes 2099-05.pdf example/policy is a series: name this file's period");
    await user.click(within(dialog).getByRole("button", { name: "Pin 1 of 5 files to Example policy" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(writes()[1].body).toMatchObject({ act: "pick", dryRun: false });
    expect(await screen.findByText(/1 of 5 files were pinned; 1 already pinned, 1 in a collision, 1 named twice, 1 refused\./)).toBeInTheDocument();
    const left = screen.getByRole("list", { name: "Files left alone" });
    expect(within(left).getAllByRole("listitem")).toHaveLength(4);
    expect(left).toHaveTextContent("Refused. File 5: Minutes 2099-05.pdf");
  });

  it("will not confirm when no file would be written, and says so", async () => {
    const user = userEvent.setup();
    const { dialog } = await go(user, { cardinality: "several", source: "document kinds" }, (c) => (c.url === SLOT_URL
      ? { ok: true, dryRun: true, parts: [{ n: 1, action: "already", why: "this file is already pinned here" }, { n: 2, action: "refused", why: "not a file link" }], counts: { already: 1, refused: 1 } } : undefined));
    const boxes = await within(dialog).findAllByRole("checkbox");
    await user.click(boxes[0]); await user.click(boxes[1]);
    await user.click(within(dialog).getByRole("button", { name: "Pick 2 files" }));
    await user.click(within(dialog).getByRole("button", { name: "Preview the pick of 2 files" }));
    expect(await within(dialog).findByRole("button", { name: "Pin 0 of 2 files to Example policy" })).toBeDisabled();
    expect(within(dialog).getByText("No file would be written, so there is nothing to confirm.")).toBeInTheDocument();
  });

  it("shows a refusal of the whole act in the server's words and writes nothing", async () => {
    const user = userEvent.setup();
    const { dialog } = await go(user, { cardinality: "several", source: "document kinds" }, (c) => (c.url === SLOT_URL ? refuse(400, "one pick takes at most 100 files (what the chooser lists at a time); pick the rest in another act") : undefined));
    const boxes = await within(dialog).findAllByRole("checkbox");
    await user.click(boxes[0]); await user.click(boxes[1]);
    await user.click(within(dialog).getByRole("button", { name: "Pick 2 files" }));
    await user.click(within(dialog).getByRole("button", { name: "Preview the pick of 2 files" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("one pick takes at most 100 files");
  });
});

describe("which holder is current", () => {
  const two = (over: Partial<SlotPageData> = {}) => SLOT({
    state: "problem", stateWord: "problem", collision: true,
    holders: [holder({ pin: "p-1", name: "Policy 2099 draft.pdf" }), holder({ pin: "p-2", origin: "specification", source: "sync rule", name: "Policy 2099 final.pdf", by: "" })],
    collisions: [{ slot: "example/policy", note: "Two files hold this slot.", holders: [
      { pin: "p-1", origin: "person", source: "a person", by: "Jane Example", at: "2099-10-03" }, { pin: "p-2", origin: "specification", source: "sync rule", by: "", at: "" }] }],
    ...over,
  });
  const open = (data: SlotPageData, write?: Route) => { at(data.key); return serve((c) => (c.url.startsWith("/api/record-slot?key=") ? data : write?.(c))); };
  const PATCH = { kind: "profile change", text: "# Proposed for the profile (a person applies it; jason edits nothing).\n#   remove: pin p-2 (sync rule)\n", note: "The profile changes only by a patch a person applies. Until then the slot still shows two holders." };

  it("asks for a reason, previews, shows the patch text with the profile unedited, and says two holders remain", async () => {
    const calls = open(two(), (c) => (c.url === SLOT_URL
      ? (c.body?.dryRun ? { dryRun: true, would: { act: "current", slot: "example/policy", pin: "p-1", unpins: [], patchFor: ["p-2"] }, patch: PATCH, note: "A dry run: nothing was written." }
        : { dryRun: false, ok: true, current: "cu-1", pin: "p-1", unpinned: [], patch: PATCH, stillTwo: true }) : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    const alert = (await screen.findAllByRole("alert")).find((a) => a.textContent?.includes("Two holders"))!;
    await user.click(within(alert).getByRole("button", { name: "Which is current: Policy 2099 draft.pdf" }));
    expect(within(alert).getByRole("button", { name: "Which is current: Policy 2099 final.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Say that Policy 2099 draft.pdf is the current one" })).toHaveFocus();
    const preview = screen.getByRole("button", { name: "Preview which holder is current" });
    expect(preview).toBeDisabled();
    expect(screen.getByText("Write why this one is current.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Why this one is current (required)"), "The board adopted the final.");
    await user.click(preview);
    expect(calls[0].body).toMatchObject({ act: "current", pin: "p-1", note: "The board adopted the final.", by: "Ada Admin", dryRun: true });
    const region = await screen.findByRole("region", { name: "What will be recorded" });
    expect(region).toHaveTextContent("The profile is not edited here: a person applies it.");
    expect(within(region).getByLabelText("Proposed change to the profile")).toHaveTextContent("remove: pin p-2");
    await user.click(screen.getByRole("button", { name: "Record that Policy 2099 draft.pdf is current for Example policy" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1].body).toMatchObject({ act: "current", dryRun: false });
    const status = await screen.findByText(/Recorded which holder is current\./);
    expect(status).toHaveTextContent("The profile is not edited, and two holders remain until a person applies the change below to it.");
    expect(status.className).toContain("notice-warn");
    expect(screen.getAllByLabelText("Proposed change to the profile").length).toBeGreaterThan(0);
  });

  it("says which pins were unpinned when only the person's own pins were the others", async () => {
    const calls = open(two(), (c) => (c.url === SLOT_URL
      ? (c.body?.dryRun ? { dryRun: true, would: { act: "current", pin: "p-2", unpins: ["p-1"], patchFor: [] }, patch: null } : { dryRun: false, ok: true, current: "cu-2", pin: "p-2", unpinned: ["p-1"], patch: null, stillTwo: false }) : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Which is current: Policy 2099 final.pdf" }));
    await user.type(screen.getByLabelText("Why this one is current (required)"), "Final wins.");
    await user.click(screen.getByRole("button", { name: "Preview which holder is current" }));
    await user.click(await screen.findByRole("button", { name: "Record that Policy 2099 final.pdf is current for Example policy" }));
    const status = await screen.findByText(/Recorded which holder is current\./);
    expect(status).toHaveTextContent("1 other pin was unpinned; the files stay.");
    expect(status).not.toHaveTextContent("two holders remain");
    expect(calls[0].body).toMatchObject({ pin: "p-2" });
  });

  it("shows the server's refusal and writes nothing", async () => {
    open(two(), (c) => (c.url === SLOT_URL ? refuse(400, "example/policy has no two holders to settle: nothing to choose between") : undefined));
    const user = userEvent.setup();
    render(<RecordsView />);
    await user.click(await screen.findByRole("button", { name: "Which is current: Policy 2099 draft.pdf" }));
    await user.type(screen.getByLabelText("Why this one is current (required)"), "x");
    await user.click(screen.getByRole("button", { name: "Preview which holder is current" }));
    expect(await screen.findByText("example/policy has no two holders to settle: nothing to choose between")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /is current for Example policy/ })).toBeNull();
  });
});

describe("a bound folder's counts", () => {
  const bound = (over: Partial<SlotPageData> = {}) => SLOT({ holders: [], bindings: [{ id: "b-1", name: "Example folder", by: "Jane Example", at: "2099-10-01" }, { id: "b-2", name: "Other folder", by: "Jane Example", at: "2099-10-02" }], ...over });
  const COUNTS = { slot: "example/policy", caveats: ["Counts come from the folder's last listing, not from Drive now."], bindings: [
    { binding: "b-1", slot: "example/policy", by: "Jane Example", at: "2099-10-01", listed: true, listedAt: "2099-10-04T09:00:00", more: true, files: 12, here: 5, elsewhere: 3, nowhere: 4, pinned: 6, read: 2, notPinned: 6, held: 1 },
    { binding: "b-2", slot: "example/policy", by: "Jane Example", at: "2099-10-02", listed: false, note: "This folder has not been listed yet. Browse it in the chooser (POST /api/write/drive/bound), and the counts appear." },
  ] };
  const urls = () => (fetch as unknown as { mock: { calls: [string][] } }).mock.calls.map((c) => String(c[0]));

  it("says each count in words, says 'not listed yet' for a folder never listed, and makes no Drive call", async () => {
    at("example/policy");
    serve((c) => (c.url.startsWith("/api/record-slot?key=") ? bound() : c.url === "/api/record-bindings?key=example%2Fpolicy" ? COUNTS : undefined));
    render(<RecordsView />);
    const list = await screen.findByRole("list", { name: "Counts for Example folder" });
    expect(list).toHaveTextContent("12 files when the folder was last listed, 2099-10-04.");
    expect(list).toHaveTextContent("5 read as this slot's kind (here), 3 as another slot's (elsewhere), 4 as none (nowhere).");
    expect(list).toHaveTextContent("6 pinned for some slot, 6 not pinned; 2 of the pinned read by jason.");
    expect(list).toHaveTextContent("1 held back (confidential; no id kept).");
    expect(list).toHaveTextContent("The folder holds more than the one page listed");
    expect(screen.getByText("not listed yet")).toBeInTheDocument();
    expect(screen.getByText(/This folder has not been listed yet\. Browse it in the chooser/)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Counts for Other folder" })).toBeNull();
    expect(screen.getByText("Counts come from the folder's last listing, not from Drive now.")).toBeInTheDocument();
    expect(urls().some((u) => u.includes("/api/write/drive/"))).toBe(false);
  });

  it("keeps the folder listed when the counts cannot be read, and says so", async () => {
    at("example/policy");
    serve((c) => (c.url.startsWith("/api/record-slot?key=") ? bound() : c.url.startsWith("/api/record-bindings") ? refuse(500, "the keep is unreadable") : undefined));
    render(<RecordsView />);
    expect(await screen.findByText("Example folder")).toBeInTheDocument();
    expect(await screen.findByText(/The counts could not be read: the keep is unreadable/)).toBeInTheDocument();
  });

  it("asks for no counts when no folder is bound", async () => {
    at("example/policy");
    serve((c) => (c.url.startsWith("/api/record-slot?key=") ? SLOT({ holders: [] }) : undefined));
    render(<RecordsView />);
    await screen.findByRole("heading", { name: "Choose a file" });
    expect(urls().some((u) => u.includes("record-bindings"))).toBe(false);
  });
});
