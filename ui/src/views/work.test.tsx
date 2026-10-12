import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findScreen, GROUPS, SCREENS } from "../App";
import { BasisPill, OfficeRowItem, WorkflowRail } from "../components";
import { resetServerSession } from "../lib/api";
import {
  ACT_ANSWER, ACTING, ACTING_PAGE, BILL_PAGE, CONTACT_EVENT, DEFINITION_PAGE, DEFINITIONS_PAGE, ELECTION_PAGE, EMPTY_PAGE, MANAGER, PAGE, PAUSED_PAGE,
  EMPTY_ITEMS_PAGE, GROUPS_PAGE, HELD_ITEMS_PAGE, ITEMS_PAGE, NO_SUPPLY_PAGE, NO_SUPPLY_WHY, REMEDY_PAGE, SUPPLY_ANSWER, SUPPLY_DRY,
  HELD_DEF, HELD_PAGE, HELD_ROW, PENDING_PAGE, QUIET_RUN_PAGE, RUN_PAGE, START_BAD, START_DONE, START_OK, ROWS, definitionsPage, due, manyYours, row, runPage, step, workPage,
} from "../lib/work.fixtures";
import { clockWords, headingLine, itemRollUp, itemRows, parseItemLines, parseRoute, runHref, setWords } from "../lib/work";
import owned from "../ownerScreens.json";
import { WorkView } from "./WorkView";

interface Call { url: string; method: string; body?: Record<string, unknown> }
type Answer = { status?: number; body: unknown };
interface Served {
  list?: Answer;
  runs?: Record<string, Answer>;
  definitions?: Answer;
  writes?: Answer[];
  session?: Record<string, unknown>;
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ELECTION_ID = "run-5f6a7b8c9d";
const OI_ID = "run-0a1b2c3d4e";

/** A made-up server: the list, the runs by id, the catalog, the write (its answers in order), and the session. */
function serve(s: Served = {}) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const method = init?.method ?? "GET";
    if (u.startsWith("/api/session"))
      return json(200, { token: "t", header: "X-Jason-Token", signedIn: { name: MANAGER, role: "manager" }, ...(s.session ?? {}) });
    if (method === "POST") {
      const body = JSON.parse(String(init?.body));
      calls.push({ url: u, method, body });
      if (u.endsWith("/start")) {            // the dry run checks the dates; the real one starts the draft
        if (body.dryRun) return json(200, body.dates?.answer_by === "2099-10-01" ? START_BAD : START_OK);
        return json(200, START_DONE);
      }
      const w = (s.writes ?? []).shift() ?? { status: 200, body: ACT_ANSWER };
      return json(w.status ?? 200, w.body);
    }
    calls.push({ url: u, method });
    if (u.startsWith("/api/work-run")) {
      const id = new URLSearchParams(u.split("?")[1]).get("id") ?? "";
      const a = s.runs?.[id] ?? { body: RUN_PAGE };
      return json(a.status ?? 200, a.body);
    }
    if (u.startsWith("/api/work-definitions")) {
      const a = s.definitions ?? { body: DEFINITIONS_PAGE };
      return json(a.status ?? 200, a.body);
    }
    if (u.startsWith("/api/work")) {
      const a = s.list ?? { body: PAGE };
      return json(a.status ?? 200, a.body);
    }
    return json(404, { error: "not here" });
  }));
  return calls;
}

beforeEach(() => { resetServerSession(); window.location.hash = ""; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

const list = async (hash = "#/work") => {
  window.location.hash = hash;
  render(<WorkView />);
  await screen.findByRole("heading", { level: 1, name: "Work" });
};
const open = async (id = OI_ID, def = "owner-info-cycle", name = "Owner information 2099") => {
  window.location.hash = `#/work/${def}/${id}`;
  render(<WorkView />);
  await screen.findByRole("heading", { level: 1, name });
};
const group = (name: string) => screen.getByRole("region", { name: new RegExp(`^${name}`) });
const writes = (calls: Call[]) => calls.filter((c) => c.method === "POST");

describe("Work, the list", () => {
  it("draws the four groups in order under the loader's heading counts, one row a run", async () => {
    serve();
    await list();
    expect(screen.getByText("7 open runs · 2 are yours · 1 is due this week · 1 is past a legal date")).toBeInTheDocument();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent?.replace(/\s*\d+ runs?$/, ""));
    expect(headings.slice(0, 4)).toEqual(["Yours", "Waiting on others", "Waiting on a clock", "The board"]);
    expect(within(group("Yours")).getAllByRole("link")).toHaveLength(2);
    expect(within(group("The board")).getAllByRole("link")).toHaveLength(2);
    const oi = within(group("Yours")).getByRole("link", { name: /Owner information 2099/ });
    expect(oi).toHaveAttribute("href", "#/work/owner-info-cycle/run-0a1b2c3d4e");
    expect(oi).toHaveTextContent("Step 6 of 12: Read the returned forms");
    expect(oi).toHaveTextContent("Your move: the manager");
  });

  it("puts a legal date before any other and a run with no date last, in the loader's order", async () => {
    const rows = [
      row({ id: "run-a", definition: "d", label: "No date", group: "yours" }),
      row({ id: "run-b", definition: "d", label: "Person date", group: "yours", due: due("2099-10-10", "person", 1) }),
      row({ id: "run-c", definition: "d", label: "Legal date", group: "yours", due: due("2099-11-30", "law", 52, { cite: "EX 1" }) }),
    ];
    serve({ list: { body: workPage(rows) } });
    await list();
    const labels = within(group("Yours")).getAllByRole("link").map((a) => a.querySelector(".work-row-label")?.textContent);
    expect(labels).toEqual(["Legal date", "Person date", "No date"]);
  });

  it("shows each due date with its basis word, and a proposed date as proposed, not as a stamp", async () => {
    const rows = [...ROWS, row({ id: "run-p", definition: "d", label: "Proposed run", group: "others", due: due("2099-12-12", "proposed policy", 64) })];
    serve({ list: { body: workPage(rows) } });
    await list();
    const words = (name: string) => within(screen.getByRole("link", { name: new RegExp(name) })).getByText(/^(LEGAL|DOCUMENTS|COUNTERPARTY|PROPOSED|PERSON)/).textContent;
    expect(words("Owner information 2099")).toBe("DOCUMENTS");
    expect(words("Bill attach")).toBe("PERSON");
    expect(words("Annual backflow")).toBe("COUNTERPARTY");
    expect(words("Rule change")).toBe("LEGAL");
    expect(words("Proposed run")).toContain("PROPOSED");
    expect(within(screen.getByRole("link", { name: /Proposed run/ })).getByText("PROPOSED").closest(".basis-pill")).toHaveClass("basis-proposed");
    expect(screen.queryAllByText(/stamp/i)).toHaveLength(0);
  });

  it("flags a run past a legal date in words", async () => {
    serve();
    await list();
    const e = screen.getByRole("link", { name: /Election 2099/ });
    expect(e).toHaveTextContent("Past a legal date (EX 321.2)");
    expect(e).toHaveTextContent("overdue");
    expect(within(screen.getByRole("link", { name: /Rule change/ })).queryByText(/Past a legal date/)).toBeNull();
  });

  it("folds a long group after five rows, with its count", async () => {
    serve({ list: { body: workPage(manyYours(15)) } });
    await list();
    const g = group("Yours");
    expect(g).toHaveTextContent("15 runs");
    expect(within(g).getAllByRole("link")).toHaveLength(5);
    await userEvent.click(within(g).getByRole("button", { name: "Show all 15 runs" }));
    expect(within(g).getAllByRole("link")).toHaveLength(15);
  });

  it("says plainly when no run is open, loading, and what the server refused", async () => {
    serve({ list: { body: EMPTY_PAGE } });
    await list();
    expect(screen.getByText(/No runs are open\. Start one from Start a run\./)).toBeInTheDocument();
    cleanup();
    serve({ list: { status: 403, body: { error: "The treasurer's office does not open the runs at this level." } } });
    render(<WorkView />);
    expect(screen.getByRole("status")).toHaveTextContent("reading the runs on disk");
    expect((await screen.findByRole("alert")).textContent).toContain("The treasurer's office does not open the runs at this level.");
  });

  it("answers a signed-out reader with the server's sentence and the sign-in link", async () => {
    serve({ list: { status: 401, body: { error: "Sign in to read the runs.", signIn: "/auth/google" } } });
    window.location.hash = "#/work";
    render(<WorkView />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Sign in to read the runs.");
    expect(within(alert).getByRole("link", { name: "Sign in with Google" })).toHaveAttribute("href", expect.stringContaining("/auth/google"));
  });

  it("filters through the loader: whose move, the definition, and due", async () => {
    const calls = serve();
    await list();
    await userEvent.selectOptions(screen.getByLabelText("Whose move"), "mine");
    await waitFor(() => expect(calls.some((c) => c.url.includes("mine=1"))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText("Workflow"), "hearing");
    await waitFor(() => expect(calls.some((c) => c.url.includes("definition=hearing"))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText("Due"), "legal");
    await waitFor(() => expect(calls.some((c) => c.url.includes("due=legal"))).toBe(true));
    expect(writes(calls)).toEqual([]);
  });

  it("reads its filters from the address, so Today's link lands on the viewer's own runs", async () => {
    const calls = serve();
    await list("#/work?mine=1");
    expect(calls[0].url).toBe("/api/work?mine=1");
    expect(screen.getByLabelText("Whose move")).toHaveValue("mine");
  });
});

describe("Work, one run: the page", () => {
  it("reads the run with GET only, focuses the title, and shows no path, file link, or frame", async () => {
    const calls = serve();
    await open();
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1 }).querySelector("span"));
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
    expect(calls[0].url).toBe("/api/work-run?definition=owner-info-cycle&id=run-0a1b2c3d4e");
    const html = document.body.innerHTML;
    expect(html).not.toContain("/api/file");
    expect(html).not.toContain("<iframe");
    expect(html).not.toMatch(/[A-Za-z]:\\/);
    expect(html).not.toContain("secrets");
  });

  it("groups the rail by phase with a state word and glyph, marks the current step, and folds the finished phases", async () => {
    serve();
    await open();
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    const phases = within(rail).getAllByRole("heading", { level: 3 }).map((h) => h.textContent?.replace(/\s+/g, " ").trim());
    expect(phases).toEqual(["▸ Prepare 2 of 2 done", "▾ Send 2 of 3 done", "▾ Collect 0 of 5 done", "▾ Close 0 of 2 done"]);
    expect(within(rail).getByRole("button", { name: /Prepare/ })).toHaveAttribute("aria-expanded", "false");
    const here = within(rail).getByRole("button", { name: /Read the returned forms/ });
    expect(here).toHaveAttribute("aria-current", "step");
    expect(here).toHaveTextContent("needs a person");
    expect(here.querySelector("svg")).not.toBeNull();                                             // the glyph beside the word
    expect(within(rail).getAllByRole("button", { name: /Apply the tags|Record what the answers say/ })).toHaveLength(2);
    const group = rail.querySelector(".work-rail-group")!;
    expect(group).toHaveTextContent("response");
    expect(group).toHaveTextContent("Apply the tags");
    expect(group).toHaveTextContent("Record what the answers say");
  });

  it("shows a child run as one row that links to its run once the run's definition is known", async () => {
    serve({ list: { body: workPage([row({ id: "run-7b8c9d0e1f", definition: "notice-delivery", label: "Notice delivery", group: "others" }), row({ id: "run-8c9d0e1f2a", definition: "mailroom-batch", label: "Mailroom batch 1", group: "others" })]) } });
    await open();
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    await waitFor(() => expect(within(rail).getByRole("link", { name: "Child run: Notice delivery" })).toHaveAttribute("href", "#/work/notice-delivery/run-7b8c9d0e1f"));
    expect(within(rail).getByRole("link", { name: "Child run: Mailroom batch 1" })).toHaveAttribute("href", "#/work/mailroom-batch/run-8c9d0e1f2a");
    expect(rail).toHaveTextContent("(done)");
    expect(rail).toHaveTextContent("(waiting)");
  });

  it("shows the changed-since banner before the rail, and the step reads changed since", async () => {
    serve();
    await open();
    const banner = screen.getByRole("region", { name: "Changed since" });
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    expect(banner.compareDocumentPosition(rail) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(banner).toHaveTextContent("Step 3, Plan the owner-information send");
    expect(banner).toHaveTextContent("file:forms/campaigns.json");
    expect(banner).toHaveTextContent("1a2b3c4d5e6f");
    expect(within(rail).getByRole("button", { name: /Plan the owner-information send/ })).toHaveTextContent("changed since");
    cleanup();
    serve({ runs: { [OI_ID]: { body: QUIET_RUN_PAGE } } });
    await open();
    expect(screen.queryByRole("region", { name: "Changed since" })).toBeNull();
  });

  it("recites a legal clock's statute words before jason's labeled reading, with every clock's basis word", async () => {
    serve();
    await open();
    const clocks = screen.getByRole("heading", { level: 2, name: "Clocks" }).closest("section")!;
    expect(clocks).toHaveTextContent("Answers by");
    expect(clocks).toHaveTextContent("DOCUMENTS");
    expect(clocks).toHaveTextContent("LEGAL");
    const recitation = clocks.querySelector("figure.recitation")!;
    const reading = clocks.querySelector("aside.reading")!;
    expect(recitation).toHaveTextContent("The association shall send a second notice to each member not later than 30 days");
    expect(recitation).toHaveTextContent("EX 123.4(a)");
    expect(recitation.compareDocumentPosition(reading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(reading).toHaveTextContent("jason's reading");
    expect(reading).toHaveTextContent("jason's reading, not the provision");
    expect(recitation).toHaveTextContent("not an official restatement");
  });

  it("says a run is past a legal date in the law's words and recites them", async () => {
    serve({ runs: { [ELECTION_ID]: { body: ELECTION_PAGE } } });
    await open(ELECTION_ID, "election", "Election 2099");
    expect(screen.getAllByText(/Past a legal date/).length).toBeGreaterThan(0);
    const clocks = screen.getByRole("heading", { level: 2, name: "Clocks" }).closest("section")!;
    expect(clocks).toHaveTextContent("Past a legal date: 7 days ago");
    expect(clocks.querySelector("figure.recitation")).toHaveTextContent("The board shall appoint an inspector of elections before ballots are sent.");
  });

  it("lists the history newest first and shows no contact detail", async () => {
    serve({ runs: { [OI_ID]: { body: runPage({ history: [CONTACT_EVENT, ...RUN_PAGE.history] }) } } });
    await open();
    const history = screen.getByRole("heading", { level: 2, name: "History" }).closest("section")!;
    const items = within(history).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("noted on the run");
    expect(items[items.length - 1]).toHaveTextContent("opened the run");
    expect(history.textContent).not.toMatch(/@/);
    expect(history.textContent).not.toMatch(/555-123-4567/);
    expect(history).toHaveTextContent("[email]");
    expect(history).toHaveTextContent("[phone]");
  });

  it("tells what opening the run would record, and that this page writes nothing", async () => {
    const calls = serve({ runs: { [OI_ID]: { body: PENDING_PAGE } } });
    await open();
    expect(screen.getByText(/Opening the run now would record 1 event/)).toBeInTheDocument();
    expect(screen.getByText(/found by this read, not yet recorded/)).toBeInTheDocument();
    expect(writes(calls)).toEqual([]);
  });

  it("banners a paused run with its reason, and a 404 and a refusal in the server's words", async () => {
    serve({ runs: { [OI_ID]: { body: PAUSED_PAGE } } });
    await open();
    expect(screen.getByRole("note", { name: "" })).toBeDefined();
    expect(screen.getByText(/Paused: waiting for the board's reply on the list/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pause" })).toBeNull();
    cleanup();
    serve({ runs: { [OI_ID]: { status: 404, body: { error: "no run run-0a1b2c3d4e of owner-info-cycle" } } } });
    window.location.hash = `#/work/owner-info-cycle/${OI_ID}`;
    render(<WorkView />);
    expect(await screen.findByText(/no run run-0a1b2c3d4e of owner-info-cycle/)).toBeInTheDocument();
    cleanup();
    serve({ runs: { [OI_ID]: { status: 403, body: { error: "Only the board's offices and the manager open the runs." } } } });
    window.location.hash = `#/work/owner-info-cycle/${OI_ID}`;
    render(<WorkView />);
    expect((await screen.findByRole("alert")).textContent).toContain("Only the board's offices and the manager open the runs.");
  });
});

describe("Work, one run: the step", () => {
  it("opens on the current step: its why, the command, the evidence as documents, and the clock with its basis", async () => {
    serve();
    await open();
    const panel = screen.getByRole("heading", { level: 2, name: "6. Read the returned forms" }).closest("section")!;
    expect(panel).toHaveTextContent("Your move");
    expect(panel).toHaveTextContent("An owner's answer counts only once a person confirms the reading");
    expect(panel).toHaveTextContent("jason responses --list --state new");
    expect(within(panel).getByRole("button", { name: "Copy command" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: /Open campaigns\.json/ })).toBeInTheDocument();
    expect(panel).toHaveTextContent("Clock: Answers by");
    expect(panel).toHaveTextContent("DOCUMENTS");
  });

  it("marks a person's step done with the record it asks for, sending the act, the step, the record, and the run's n, and no name", async () => {
    const calls = serve();
    await open();
    const panel = screen.getByRole("heading", { level: 2, name: "6. Read the returned forms" }).closest("section")!;
    const first = within(panel).getByRole("button", { name: "Mark done" });
    expect(first).toBeDisabled();                                                                // the record is required
    expect(within(panel).getByText("The record: the count of forms read is required.")).toBeInTheDocument();
    await userEvent.type(within(panel).getByLabelText("The record: the count of forms read"), "4 forms read");
    await userEvent.click(within(panel).getByRole("button", { name: "Mark done" }));
    expect(writes(calls)).toEqual([]);                                                           // one click writes nothing
    const group = within(panel).getByRole("group", { name: "Mark done" });
    expect(group).toHaveTextContent(`under the name ${MANAGER}`);
    expect(group).toHaveTextContent("4 forms read");
    await userEvent.click(within(group).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].url).toBe("/api/write/work/owner-info-cycle/run-0a1b2c3d4e");
    expect(writes(calls)[0].body).toEqual({ act: "attest", step: "oi.read-forms", record: "4 forms read", expect: 9 });
    expect(writes(calls)[0].body).not.toHaveProperty("by");
    expect(await screen.findByRole("status")).toHaveTextContent("Recorded:");
    await waitFor(() => expect(calls.filter((c) => c.url.startsWith("/api/work-run")).length).toBeGreaterThan(1)); // the run is read again
  });

  it("offers no Mark done on a plan or a decision, and links to the screen that owns the act", async () => {
    const calls = serve();
    await open();
    await userEvent.click(within(screen.getByRole("navigation", { name: "Steps of this run" })).getByRole("button", { name: /Plan the owner-information send/ }));
    let panel = screen.getByRole("heading", { level: 2, name: /3\. Plan the owner-information send/ }).closest("section")!;
    expect(within(panel).queryByRole("button", { name: /Mark done|Answer/ })).toBeNull();
    expect(within(panel).getByRole("link", { name: "Review in Approvals" })).toHaveAttribute("href", "#/approvals");
    expect(panel).toHaveTextContent("ap-2099-0031");
    expect(panel).toHaveTextContent("applied");
    expect(panel).toHaveTextContent("A plan is decided and applied in Approvals; the run reads the result.");
    await userEvent.click(screen.getByRole("button", { name: /Prepare/ }));                       // a phase with every step done is folded
    await userEvent.click(screen.getByRole("button", { name: /The board adopts the cycle/ }));
    panel = screen.getByRole("heading", { level: 2, name: /2\. The board adopts the cycle/ }).closest("section")!;
    expect(within(panel).queryByRole("button", { name: /Mark done|Answer|approve|vote|adopt/i })).toBeNull();
    expect(panel).toHaveTextContent("Adopt the 2099 owner information cycle");
    expect(panel).toHaveTextContent("adopted");
    expect(panel).toHaveTextContent("B. Secretary");
    expect(within(panel).getByRole("link", { name: "Read in Decisions" })).toHaveAttribute("href", "#/decisions");
    expect(writes(calls)).toEqual([]);
    cleanup();
    serve({ runs: { [ELECTION_ID]: { body: ELECTION_PAGE } } });
    await open(ELECTION_ID, "election", "Election 2099");
    const undecided = screen.getByRole("heading", { level: 2, name: /Appoint the inspector/ }).closest("section")!;
    expect(within(undecided).getByRole("link", { name: "Record in Decisions" })).toHaveAttribute("href", "#/decisions");
    expect(within(undecided).queryByRole("button", { name: /Mark done|approve|vote|adopt|Skip/i })).toBeNull();
    expect(undecided).toHaveTextContent("Not recorded yet");
  });

  it("shows a step that is not the viewer's as waiting on its office, with the server's sentence and no act", async () => {
    serve();
    await open();
    await userEvent.click(screen.getByRole("button", { name: /Close the cycle/ }));
    const panel = screen.getByRole("heading", { level: 2, name: /12\. Close the cycle/ }).closest("section")!;
    expect(panel).toHaveTextContent("Waiting on the secretary");
    expect(within(panel).queryByRole("button", { name: /Mark done|Skip this step|Reopen/ })).toBeNull();
    expect(panel).toHaveTextContent("Only the secretary may skip this step.");
  });

  it("does not offer a skip on a legal step and shows the server's sentence in its place", async () => {
    serve();
    await open();
    const panel = screen.getByRole("heading", { level: 2, name: "6. Read the returned forms" }).closest("section")!;
    expect(within(panel).queryByRole("button", { name: /Skip/ })).toBeNull();
    expect(panel.querySelector('[data-act="skip"]')).toHaveTextContent("Skip is not offered: this step is required by the law.");
  });

  it("skips where the definition allows, with a reason", async () => {
    const skippable = step({ id: "oi.read-forms", n: 1, of: 1, title: "A skippable step", kind: "person", role: "manager", state: "needs a person", phase: "x",
      phaseTitle: "X", current: true, yours: true, skip: { roles: ["manager"], reasonRequired: true }, acts: ["attest", "skip"] });
    const calls = serve({ runs: { [OI_ID]: { body: runPage({ phases: [{ key: "x", title: "X", steps: ["oi.read-forms"] }], steps: [skippable], changed: [], clocks: [], links: [] }) } } });
    await open();
    const panel = screen.getByRole("heading", { level: 2, name: "1. A skippable step" }).closest("section")!;
    expect(within(panel).getByRole("button", { name: "Skip this step" })).toBeDisabled();
    await userEvent.type(within(panel).getByLabelText("Why it is skipped"), "Not needed this year");
    await userEvent.click(within(panel).getByRole("button", { name: "Skip this step" }));
    await userEvent.click(within(within(panel).getByRole("group", { name: "Skip" })).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].body).toEqual({ act: "skip", step: "oi.read-forms", reason: "Not needed this year", expect: 9 });
  });

  it("notes an arrival on a wait only where the step offers it", async () => {
    const calls = serve();
    await open();
    await userEvent.click(screen.getByRole("button", { name: /Answers by/ }));
    const panel = screen.getByRole("heading", { level: 2, name: /9\. Answers by/ }).closest("section")!;
    await userEvent.click(within(panel).getByRole("button", { name: "Note an arrival" }));
    await userEvent.click(within(panel).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].body).toEqual({ act: "arrived", step: "oi.answers-by", expect: 9 });
  });

  it("answers a branch a person decides, with the path chosen", async () => {
    const branch = step({ id: "oi.choose", n: 1, of: 1, title: "Is the cycle complete?", kind: "branch", role: "manager", state: "needs a person", phase: "x",
      phaseTitle: "X", current: true, yours: true, choices: ["complete", "extend"], acts: ["attest"] });
    const calls = serve({ runs: { [OI_ID]: { body: runPage({ phases: [{ key: "x", title: "X", steps: ["oi.choose"] }], steps: [branch], changed: [], clocks: [], links: [] }) } } });
    await open();
    await userEvent.click(screen.getByRole("radio", { name: "extend" }));
    await userEvent.click(screen.getByRole("button", { name: "Answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].body).toEqual({ act: "attest", step: "oi.choose", choice: "extend", expect: 9 });
  });

  it("shows the server's refusal as given, and a stale run with a way to read it again", async () => {
    const calls = serve({ writes: [{ status: 409, body: { error: "the run has moved on (it is at 10, you saw 9); read it again", expected: 9, actual: 10 } }] });
    await open();
    const panel = screen.getByRole("heading", { level: 2, name: "6. Read the returned forms" }).closest("section")!;
    await userEvent.type(within(panel).getByLabelText("The record: the count of forms read"), "4 forms read");
    await userEvent.click(within(panel).getByRole("button", { name: "Mark done" }));
    await userEvent.click(within(panel).getByRole("button", { name: "Yes, do it" }));
    const alert = await within(panel).findByRole("alert");
    expect(alert).toHaveTextContent("the run has moved on (it is at 10, you saw 9); read it again");
    const before = calls.filter((c) => c.url.startsWith("/api/work-run")).length;
    await userEvent.click(within(alert).getByRole("button", { name: "Read the run again" }));
    await waitFor(() => expect(calls.filter((c) => c.url.startsWith("/api/work-run")).length).toBe(before + 1));
  });

  it("gives an administrator viewing as someone else one sentence and no act", async () => {
    serve({ runs: { [OI_ID]: { body: ACTING_PAGE } } });
    await open();
    expect(screen.getAllByText(ACTING).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Viewing as A\. Secretary \(admin view\): go back to yourself first/).length).toBeGreaterThan(0);
    for (const name of [/^Pause$/, /^Note$/, /^Cancel$/, /Mark done/, /Skip this step/]) expect(screen.queryByRole("button", { name })).toBeNull();
  });

  it("keeps the rail's step for a phone as one collapsed header that opens the list", async () => {
    render(<WorkflowRail page={RUN_PAGE} selected="oi.read-forms" onSelect={() => {}} href={() => null} compact />);
    const head = screen.getByRole("button", { name: "Step 6 of 12: Read the returned forms" });
    expect(head).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(head);
    expect(head).toHaveAttribute("aria-expanded", "true");
  });
});

describe("Work, the run's own acts", () => {
  it("pauses with a reason, in a dialog, and sends it without a name", async () => {
    const calls = serve();
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));
    const dialog = await screen.findByRole("dialog", { name: "Pause this run" });
    expect(within(dialog).getByRole("button", { name: "Pause" })).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Why it is paused"), "Waiting on the board");
    await userEvent.click(within(dialog).getByRole("button", { name: "Pause" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].body).toEqual({ act: "pause", reason: "Waiting on the board", expect: 9 });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("cancels with a reason, naming every open step and child run, and the yes a legal clock needs", async () => {
    const calls = serve();
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    const dialog = await screen.findByRole("dialog", { name: "Cancel this run" });
    expect(dialog).toHaveTextContent("3 open steps and 2 child runs");
    for (const t of ["Read the returned forms", "Mailroom batch 1", "Answers by"]) expect(dialog).toHaveTextContent(t);
    expect(dialog).toHaveTextContent("legal clock");
    await userEvent.type(within(dialog).getByLabelText("Why it is cancelled"), "Superseded by a new cycle");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel the run" }));
    expect(within(dialog).getByRole("group", { name: "Cancel" })).toHaveTextContent("It leaves 3 open steps and 2 child runs");
    await userEvent.click(within(dialog).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].body).toEqual({ act: "cancel", reason: "Superseded by a new cycle", yes: true, expect: 9 });
  });

  it("resumes a paused run with a Confirm and no reason, and notes with text", async () => {
    const calls = serve({ runs: { [OI_ID]: { body: PAUSED_PAGE } } });
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Resume" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0].body).toEqual({ act: "resume", expect: 9 });
    await userEvent.click(screen.getByRole("button", { name: "Note" }));
    const dialog = await screen.findByRole("dialog", { name: "Add a note to the run" });
    await userEvent.type(within(dialog).getByLabelText("The note"), "Checked the list");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add the note" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(2));
    expect(writes(calls)[1].body).toEqual({ act: "note", text: "Checked the list", expect: 9 });
  });

  it("prints the history oldest first with the evidence addresses, for the board's record", async () => {
    serve({ runs: { [OI_ID]: { body: runPage({ history: [{ ...RUN_PAGE.history[0], detail: { evidence: [{ address: "file:forms/campaigns.json", hash: "9f8e7d6c5b4a3c2d" }] } }, ...RUN_PAGE.history.slice(1)] }) } } });
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Print the history" }));
    const sheet = screen.getByRole("region", { name: "The history, for printing" });
    const items = sheet.querySelectorAll(":scope > ol > li");
    expect(items[0]).toHaveTextContent("opened the run");
    expect(items[items.length - 1]).toHaveTextContent("found that what step 3");
    expect(items[items.length - 1]).toHaveTextContent("file:forms/campaigns.json");
    expect(within(sheet).getByRole("button", { name: "Print" })).toBeInTheDocument();
  });
});

describe("Work, what can be run", () => {
  it("lists every definition once under its family, with the DRIFTED word and the sentence, and counts the drift", async () => {
    serve();
    window.location.hash = "#/work/definitions";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "What can be run" });
    expect(screen.getByText("4 workflows in 2 families · 1 has drifted from their procedure")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent).slice(0, 2)).toEqual(["Members", "Money"]);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Owner information cycle", "Respond to a request", "Hearing", "Bill attachment"]);
    const respond = document.querySelector('[data-key="respond"]')!;
    expect(respond).toHaveTextContent("DRIFTED");
    expect(respond).toHaveTextContent("respond.11: the procedure no longer has step 11");
    expect(document.querySelector('[data-key="owner-info-cycle"]')).toHaveTextContent("In step with it.");
    expect(document.querySelector('[data-key="owner-info-cycle"]')).toHaveTextContent("has a legal clock");
  });

  it("offers Start only where the viewer's office may start, and names the role that can otherwise", async () => {
    serve();
    window.location.hash = "#/work/definitions";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "What can be run" });
    const hearing = document.querySelector<HTMLElement>('[data-key="hearing"]')!;
    expect(within(hearing).queryByRole("link", { name: "Start" })).toBeNull();
    expect(hearing).toHaveTextContent("Started by the manager or the secretary");
    const oi = document.querySelector<HTMLElement>('[data-key="owner-info-cycle"]')!;
    expect(within(oi).getByRole("link", { name: "Start" })).toHaveAttribute("href", "#/work/start?definition=owner-info-cycle");
    expect(within(oi).getByRole("link", { name: "Read" })).toHaveAttribute("href", "#/work/definitions?key=owner-info-cycle");
  });

  it("has no control that edits a definition, and says when none is registered", async () => {
    serve();
    window.location.hash = "#/work/definitions";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "What can be run" });
    const names = screen.queryAllByRole("button").map((b) => b.textContent);
    expect(names.filter((n) => /edit|save|delete|rename|change/i.test(n ?? ""))).toEqual([]);
    cleanup();
    serve({ definitions: { body: definitionsPage([]) } });
    render(<WorkView />);
    expect(await screen.findByText("No workflows are registered.")).toBeInTheDocument();
  });

  it("reads one definition as a page: its steps, kinds, roles, clocks and basis, and the statute it cites, recited", async () => {
    serve({ definitions: { body: DEFINITION_PAGE } });
    window.location.hash = "#/work/definitions?key=owner-info-cycle";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "Owner information cycle" });
    const table = screen.getByRole("table");
    expect(within(table).getByText("Read the returned forms")).toBeInTheDocument();
    expect(table).toHaveTextContent("a person's step");
    expect(table).toHaveTextContent("required by the law");
    expect(table).toHaveTextContent("LEGAL");
    expect(table).toHaveTextContent("DOCUMENTS");
    expect(document.querySelector("figure.recitation")).toHaveTextContent("The association shall send a second notice");
    expect(screen.queryByRole("button", { name: /edit|save/i })).toBeNull();
  });
});

describe("Work, start a run", () => {
  it("checks the dates on the server before it starts, shows the sentence beside the date, then starts a draft with the yes", async () => {
    const calls = serve();
    window.location.hash = "#/work/start?definition=owner-info-cycle";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "Start a run" });
    expect(screen.getByLabelText("What to run")).toHaveValue("owner-info-cycle");
    await userEvent.type(screen.getByLabelText("What it is about"), "campaign:OI-2099");
    fireEvent.change(screen.getByLabelText("Answers by"), { target: { value: "2099-10-01" } });
    await waitFor(() => expect(writes(calls).some((c) => c.body?.dryRun === true && (c.body?.dates as Record<string, string>)?.answer_by === "2099-10-01")).toBe(true));
    const bad = await screen.findByText(/leave room for one correction before the answer-by date/);
    expect(bad.closest("p")).toHaveAttribute("role", "alert");
    expect(screen.getByLabelText("Answers by")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Start the run" })).toBeDisabled();
    expect(writes(calls).every((c) => c.body?.dryRun === true)).toBe(true);                   // nothing started yet
    fireEvent.change(screen.getByLabelText("Answers by"), { target: { value: "2099-10-23" } });
    fireEvent.change(screen.getByLabelText("Send on"), { target: { value: "2099-10-05" } });
    await userEvent.click(screen.getByRole("checkbox", { name: /legal clock/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Start the run" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Start the run" }));
    expect(screen.getByRole("group", { name: "Start" })).toHaveTextContent(`under the name ${MANAGER}`);
    expect(screen.getByRole("group", { name: "Start" })).toHaveTextContent("No clock runs until the run is opened");
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls).some((c) => !c.body?.dryRun)).toBe(true));
    const started = writes(calls).find((c) => !c.body?.dryRun)!;
    expect(started.url).toBe("/api/write/work/owner-info-cycle/start");
    expect(started.body).toEqual({ definition: "owner-info-cycle", subject: "campaign:OI-2099", label: "", dates: { answer_by: "2099-10-23", send: "2099-10-05" }, yes: true });
    await waitFor(() => expect(window.location.hash).toBe("#/work/owner-info-cycle/run-9d0e1f2a3b"));
  });

  it("refuses to start in another person's name", async () => {
    serve({ session: { acting: { name: "A. Secretary", role: "secretary" } } });
    window.location.hash = "#/work/start";
    render(<WorkView />);
    expect(await screen.findByText(/Viewing as A\. Secretary \(admin view\): go back to yourself first/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start the run" })).toBeNull();
  });
});

describe("Work, a held run", () => {
  it("lists a held run by the definition's general title, its state, and where it opens, with no step number, label, or citation", async () => {
    serve({ list: { body: workPage([...ROWS, HELD_ROW]) } });
    await list();
    const held = screen.getByRole("link", { name: /A member's hearing/ });
    expect(held).toHaveAttribute("href", "#/work/hearing/run-9e8d7c6b5a");
    expect(held.closest("li")).toHaveAttribute("data-held", "true");
    expect(held).toHaveTextContent("Open the private view to see this run.");
    expect(held).toHaveTextContent("a step");
    expect(held).not.toHaveTextContent(/Step \d+ of/);
    expect(held).toHaveTextContent("LEGAL");
    const plain = screen.getByRole("link", { name: /Owner information 2099/ });
    expect(plain.closest("li")).not.toHaveAttribute("data-held");
    expect(plain).toHaveTextContent("Step 6 of 12: Read the returned forms");
  });

  it("opens a held run as a note, its state, and its date, with no steps, no acts, and no history", async () => {
    serve({ runs: { "run-9e8d7c6b5a": { body: HELD_PAGE } } });
    await open("run-9e8d7c6b5a", "hearing", "A member's hearing");
    expect(screen.getByRole("note")).toHaveTextContent("Open the private view to see this run.");
    expect(screen.getByRole("note")).toHaveAttribute("data-held", "true");
    expect(screen.getByText("a step")).toBeInTheDocument();
    for (const name of ["Pause", "Note", "Cancel", "Open the run", "Print the history"]) expect(screen.queryByRole("button", { name })).toBeNull();
    expect(screen.queryByRole("heading", { name: "History" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Clocks" })).toBeNull();
    expect(document.body).not.toHaveTextContent(/Opened \d/);
  });

  it("names the sentence that says a held definition starts only in the private view, and offers no Start", async () => {
    serve({ definitions: { body: definitionsPage([HELD_DEF, ...DEFINITIONS_PAGE.definitions]) } });
    window.location.hash = "#/work/definitions";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "What can be run" });
    const held = document.querySelector<HTMLElement>('[data-key="hearing"]')!;
    expect(within(held).queryByRole("link", { name: "Start" })).toBeNull();
    expect(held).toHaveTextContent("starts only in the private view");
  });

  it("does not let the start form go on for a definition the server says is not startable here", async () => {
    serve({ definitions: { body: definitionsPage([HELD_DEF]) } });
    window.location.hash = "#/work/start?definition=hearing";
    render(<WorkView />);
    await screen.findByRole("heading", { level: 1, name: "Start a run" });
    expect(await screen.findByText(/starts only in the private view/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("What it is about"), "hearing:H-1");
    expect(screen.getByRole("button", { name: "Start the run" })).toBeDisabled();
  });
});

describe("Work, the pieces", () => {
  it("gives the five basis words a glyph each, and shows a word it does not know plainly", () => {
    render(<>{["law", "documents", "counterparty", "proposed policy", "person", "made up"].map((b) => <BasisPill key={b} basis={b} />)}</>);
    const pills = Array.from(document.querySelectorAll(".basis-pill"));
    expect(pills.map((p) => p.textContent?.replace(": proposed, not the law's", ""))).toEqual(["LEGAL", "DOCUMENTS", "COUNTERPARTY", "PROPOSED", "PERSON", "made up"]);
    expect(pills.slice(0, 5).every((p) => p.querySelector("svg"))).toBe(true);
    expect(pills[5].querySelector("svg")).toBeNull();
    expect(pills[3]).toHaveTextContent("proposed, not the law's");
  });

  it("parses the address: the list with its filters, a run, the catalog, and starting", () => {
    expect(parseRoute("work")).toMatchObject({ page: "list" });
    expect(parseRoute("work?mine=1&due=legal")).toEqual({ page: "list", filters: { definition: "", role: "", due: "legal", state: "", mine: true, q: "" } });
    expect(parseRoute("work/owner-info-cycle/run-0a1b2c3d4e")).toEqual({ page: "run", definition: "owner-info-cycle", id: "run-0a1b2c3d4e" });
    expect(parseRoute("work/definitions")).toEqual({ page: "definitions", key: "" });
    expect(parseRoute("work/definitions?key=hearing")).toEqual({ page: "definitions", key: "hearing" });
    expect(parseRoute("work/start?definition=hearing")).toEqual({ page: "start", definition: "hearing" });
    expect(runHref("owner-info-cycle", "run-1")).toBe("#/work/owner-info-cycle/run-1");
  });

  it("words the heading from the loader's counts and does not compute the past-legal one", () => {
    expect(headingLine({ open: 1, yours: 1, dueThisWeek: 0, pastLegal: 0, others: 0, clock: 0, board: 0, overdue: 0 })).toBe("1 open run · 1 is yours · 0 are due this week · 0 are past a legal date");
  });

  it("links a run row on Today to the run, and a row with no definition stays text", () => {
    const base = { type: "run", text: "Example cycle 2099: Approve the sample", id: "run-1", screen: "" };
    const { rerender } = render(<ul><OfficeRowItem row={{ ...base, definition: "example-cycle" }} /></ul>);
    expect(screen.getByRole("link", { name: "Open the run" })).toHaveAttribute("href", "#/work/example-cycle/run-1");
    rerender(<ul><OfficeRowItem row={base} /></ul>);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("is registered as the Work group, for the board's offices and the manager, never an owner screen", () => {
    const s = SCREENS.find((x) => x.id === "work");
    expect(s?.group).toBe("Work");
    expect(GROUPS).toContain("Work");
    expect(s?.owner).toBeFalsy();
    expect(s?.roles).toEqual(["officer", "manager", "administrator"]);
    expect(Object.keys(owned.screens)).not.toContain("work");
    expect(findScreen("work")?.id).toBe("work");
    expect(findScreen("work/owner-info-cycle/run-0a1b2c3d4e")?.id).toBe("work");
    expect(findScreen("work/definitions")?.id).toBe("work");
  });

  it("keeps a bill's plan step the treasurer's: waiting on the approvals engine, no act", async () => {
    serve({ runs: { "run-1b2c3d4e5f": { body: BILL_PAGE } } });
    await open("run-1b2c3d4e5f", "bill-attach", "Bill attach: Example Electric, Oct");
    const panel = screen.getByRole("heading", { level: 2, name: /1\. Approve the attachments/ }).closest("section")!;
    expect(panel).toHaveTextContent("Waiting on the approvals engine");
    expect(panel).toHaveTextContent("in review");
    expect(within(panel).queryByRole("button", { name: /Mark done|Skip/ })).toBeNull();
  });
});


// -- item sets, step groups, and a remedy (engine round three) ---------------------------------------------------------------

const ITEMS_ID = "run-1100aa22bb";
const GROUPS_ID = "run-2200bb33cc";
const REMEDY_ID = "run-3300cc44dd";

describe("Work, item sets: the table, the roll-up, and the clocks", () => {
  it("draws one row for each item with its state, its clock, and when it is due, in words", async () => {
    serve({ runs: { [ITEMS_ID]: { body: ITEMS_PAGE } } });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "2. Decide each request" }).closest("section")!;
    const table = within(panel).getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Item", "State", "Clock", "Due"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(12);
    expect(within(rows[0]).getByRole("rowheader")).toHaveTextContent("req:01");
    expect(rows[0]).toHaveTextContent("done");
    expect(rows[0]).toHaveTextContent("met");
    expect(rows[3]).toHaveTextContent("req:04");
    expect(rows[3]).toHaveTextContent("needs a person");
    expect(rows[3]).toHaveTextContent("late by 3 days");               // a word, not only a colour
    expect(rows[3]).toHaveAttribute("data-late", "true");
    expect(rows[4]).toHaveTextContent("late by 1 day");
    expect(rows[8]).toHaveTextContent("due in 5 days");
    expect(rows[8]).not.toHaveAttribute("data-late");
    expect(within(rows[3]).getByText("late by 3 days").closest("span")?.querySelector("svg")).not.toBeNull();   // with a glyph beside it
    expect(within(panel).getByRole("region", { name: "Items of step 2, Decide each request" })).toHaveAttribute("tabindex", "0");   // scrolls by keyboard
  });

  it("rolls the items up: 3 of 12 done, 2 late", async () => {
    serve({ runs: { [ITEMS_ID]: { body: ITEMS_PAGE } } });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "2. Decide each request" }).closest("section")!;
    expect(within(panel).getByText("3 of 12 done, 2 late")).toBeInTheDocument();
    // the rail says it too
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    expect(rail).toHaveTextContent("3 of 12 items done");
  });

  it("draws the clocks of a step's items as one card, not twelve, with the count late and the nearest date", async () => {
    serve({ runs: { [ITEMS_ID]: { body: ITEMS_PAGE } } });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const clocks = screen.getByRole("heading", { level: 2, name: "Clocks" }).closest("section")!;
    const cards = clocks.querySelectorAll("li.work-clock");
    expect(cards).toHaveLength(1);
    expect(cards[0]).toHaveAttribute("data-item-clocks", "12");
    expect(cards[0]).toHaveTextContent("2 late");
    expect(cards[0]).toHaveTextContent("one clock for each of its 12 items");
    expect(cards[0]).toHaveTextContent("next due");
    expect(cards[0]).toHaveTextContent("PERSON");
    expect(clocks.textContent).not.toContain("req:04");
  });

  it("folds a long table after fifty items and shows the rest on request", async () => {
    const ids = Array.from({ length: 60 }, (_, i) => `req:${i + 100}`);
    const base = ITEMS_PAGE.steps[1];
    const page = { ...ITEMS_PAGE, clocks: [], steps: [ITEMS_PAGE.steps[0], { ...base, items: ids.map((item) => ({ item, state: "needs a person" })) }] };
    serve({ runs: { [ITEMS_ID]: { body: page } } });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "2. Decide each request" }).closest("section")!;
    expect(within(panel).getAllByRole("row")).toHaveLength(51);
    const more = within(panel).getByRole("button", { name: "Show all 60 items" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(more);
    expect(within(panel).getAllByRole("row")).toHaveLength(61);
    expect(within(panel).getByRole("button", { name: "Show the first 50" })).toHaveAttribute("aria-expanded", "true");
  });
});

describe("Work, item sets: supplying items", () => {
  it("says a set with no items is empty and what the step waits for, and offers the form", async () => {
    serve({ runs: { [ITEMS_ID]: { body: EMPTY_ITEMS_PAGE } } });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "1. Decide each request" }).closest("section")!;
    expect(within(panel).getByText("No items have been supplied to the set requests yet. This step waits until some are.")).toBeInTheDocument();
    expect(within(panel).queryByRole("table")).toBeNull();
    expect(within(panel).getByRole("heading", { level: 3, name: "Supply items" })).toBeInTheDocument();
  });

  it("gives the server's sentence, and no form, to a viewer who may not supply", async () => {
    serve({ runs: { [ITEMS_ID]: { body: NO_SUPPLY_PAGE } } });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "1. Decide each request" }).closest("section")!;
    expect(panel).toHaveTextContent(NO_SUPPLY_WHY);
    expect(within(panel).queryByRole("heading", { name: "Supply items" })).toBeNull();
    expect(within(panel).queryByRole("button", { name: "Check the list" })).toBeNull();
  });

  it("checks the list on the server first, then records it as one act with the run's n and no name", async () => {
    const calls = serve({ runs: { [ITEMS_ID]: { body: EMPTY_ITEMS_PAGE } }, writes: [{ body: SUPPLY_DRY }, { body: SUPPLY_ANSWER }] });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "1. Decide each request" }).closest("section")!;
    const check = within(panel).getByRole("button", { name: "Check the list" });
    expect(check).toBeDisabled();                                                       // nothing typed
    await userEvent.type(within(panel).getByLabelText("Item ids for the set requests, one to a line"), "req:20{enter}req:21{enter}{enter}req:01");
    expect(within(panel).getByText("3 ids typed.")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Check the list" }));
    expect(await within(panel).findByText(/2 new items would be added; 1 already in the set \(req:01\)\. Nothing is recorded yet\./)).toBeInTheDocument();
    expect(writes(calls)).toHaveLength(1);
    expect(writes(calls)[0].body).toEqual({ act: "supply-items", dryRun: true, set: "requests", items: ["req:20", "req:21", "req:01"] });
    await userEvent.click(within(panel).getByRole("button", { name: "Supply 2 items" }));
    const group = within(panel).getByRole("group", { name: "Supply" });
    expect(group).toHaveTextContent(`under the name ${MANAGER}`);
    expect(group).toHaveTextContent("2 new items");
    expect(writes(calls)).toHaveLength(1);                                              // one click writes nothing
    await userEvent.click(within(group).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(2));
    expect(writes(calls)[1].body).toEqual({ act: "supply-items", set: "requests", items: ["req:20", "req:21", "req:01"], expect: 9 });
    expect(writes(calls)[1].body).not.toHaveProperty("by");
    expect(await screen.findByText(/Recorded: .*supplied 2 items to the set requests/)).toBeInTheDocument();
    await waitFor(() => expect(calls.filter((c) => c.url.startsWith("/api/work-run")).length).toBeGreaterThan(1));      // the run is read again
  });

  it("shows the server's own refusal of a name and offers no record", async () => {
    const refusal = "'Jane Doe' is not an item id: letters, digits, and : _ . # / - only, at most 64 characters (an opaque handle, never a name or an address)";
    const calls = serve({ runs: { [ITEMS_ID]: { body: EMPTY_ITEMS_PAGE } }, writes: [{ status: 400, body: { error: refusal } }] });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "1. Decide each request" }).closest("section")!;
    await userEvent.type(within(panel).getByLabelText("Item ids for the set requests, one to a line"), "Jane Doe");
    await userEvent.click(within(panel).getByRole("button", { name: "Check the list" }));
    const alert = await within(panel).findByRole("alert");
    expect(alert).toHaveTextContent(refusal);
    expect(within(panel).queryByRole("button", { name: /^Supply \d/ })).toBeNull();
    expect(writes(calls)).toHaveLength(1);
  });

  it("asks the server again when the list changes after a check", async () => {
    serve({ runs: { [ITEMS_ID]: { body: EMPTY_ITEMS_PAGE } }, writes: [{ body: SUPPLY_DRY }] });
    await open(ITEMS_ID, "request-month", "Requests, October");
    const panel = screen.getByRole("heading", { level: 2, name: "1. Decide each request" }).closest("section")!;
    const ids = within(panel).getByLabelText("Item ids for the set requests, one to a line");
    await userEvent.type(ids, "req:20");
    await userEvent.click(within(panel).getByRole("button", { name: "Check the list" }));
    await within(panel).findByRole("button", { name: "Supply 2 items" });
    await userEvent.type(ids, "{enter}req:22");
    expect(within(panel).queryByRole("button", { name: /^Supply \d/ })).toBeNull();           // the check is stale: ask again
    expect(within(panel).getByRole("button", { name: "Check the list" })).toBeEnabled();
  });
});

describe("Work, step groups", () => {
  it("draws a titled group as a collapsible section, open where it holds the current step and shut where it is not yet reached", async () => {
    serve({ runs: { [GROUPS_ID]: { body: GROUPS_PAGE } } });
    await open(GROUPS_ID, "group-flow", "Group flow, October");
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    const intake = within(rail).getByRole("button", { name: /Intake/ });
    const board = within(rail).getByRole("button", { name: /The board/ });
    expect(intake).toHaveAttribute("aria-expanded", "true");
    expect(board).toHaveAttribute("aria-expanded", "false");
    expect(intake).toHaveTextContent("needs a person");
    expect(intake).toHaveTextContent("0 of 2 done");
    expect(board).toHaveTextContent("not started");
    expect(within(rail).getByRole("list", { name: "Intake steps" })).not.toHaveAttribute("hidden");
    expect(rail.querySelector('ol[aria-label="The board steps"]')).toHaveAttribute("hidden");        // a name is not computed for a hidden list
    expect(within(rail).queryByRole("button", { name: /3 Decide/ })).toBeNull();              // hidden steps are not reachable
  });

  it("opens and closes a group from the keyboard, and the person's choice stays", async () => {
    serve({ runs: { [GROUPS_ID]: { body: GROUPS_PAGE } } });
    await open(GROUPS_ID, "group-flow", "Group flow, October");
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    const board = within(rail).getByRole("button", { name: /The board/ });
    board.focus();
    await userEvent.keyboard("{Enter}");
    expect(board).toHaveAttribute("aria-expanded", "true");
    expect(within(rail).getByRole("button", { name: /3\s*Decide/ })).toBeInTheDocument();
    await userEvent.keyboard(" ");
    expect(board).toHaveAttribute("aria-expanded", "false");
    const intake = within(rail).getByRole("button", { name: /Intake/ });
    await userEvent.click(intake);
    expect(intake).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps a run that declares no groups exactly as it was", async () => {
    serve();
    await open();
    const rail = screen.getByRole("navigation", { name: "Steps of this run" });
    expect(rail.querySelectorAll("[data-group]")).toHaveLength(0);
  });
});

describe("Work, a remedy", () => {
  it("says on the remedy step that it remedies the failed check above, which stays recorded as failed", async () => {
    serve({ runs: { [REMEDY_ID]: { body: REMEDY_PAGE } } });
    await open(REMEDY_ID, "remedy-flow", "Remedy flow, October");
    const panel = screen.getByRole("heading", { level: 2, name: "2. Complete the roster" }).closest("section")!;
    expect(within(panel).getByText("This step is the remedy for the failed check above; the check stays recorded as failed.", { exact: false })).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Go to the check: step 1, The roster is complete" }));
    const check = screen.getByRole("heading", { level: 2, name: "1. The roster is complete" }).closest("section")!;
    expect(check).toHaveTextContent("This check failed and stays recorded as failed.");
    expect(check).toHaveTextContent("Step 2, Complete the roster, is its remedy and is open");
    expect(check).toHaveTextContent("This step failed: the roster is incomplete");
  });
});

describe("Work, a held run's items", () => {
  it("shows a count of items and no id outside the private view", async () => {
    serve({ runs: { [ITEMS_ID]: { body: HELD_ITEMS_PAGE } } });
    await open(ITEMS_ID, "hearing", "A member's hearing");
    expect(screen.getByText(/12 items; their ids show only in the private view/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/req:\d/);
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Supply items" })).toBeNull();
  });
});

describe("Work, the item words", () => {
  it("words a clock without colour", () => {
    expect(clockWords({ status: "overdue", days: -3 })).toEqual({ text: "late by 3 days", late: true });
    expect(clockWords({ status: "overdue", days: -1 })).toEqual({ text: "late by 1 day", late: true });
    expect(clockWords({ status: "due", days: 0 })).toEqual({ text: "due today", late: false });
    expect(clockWords({ status: "upcoming", days: 5 })).toEqual({ text: "due in 5 days", late: false });
    expect(clockWords({ status: "satisfied", days: 2 })).toEqual({ text: "met", late: false });
    expect(clockWords({ status: "not applicable, recorded", days: 2 })).toEqual({ text: "not applicable, recorded", late: false });
    expect(clockWords({ status: "undated", days: null })).toEqual({ text: "no date yet", late: false });
    expect(clockWords(null)).toEqual({ text: "no clock", late: false });
  });

  it("rolls a step's items up by the loader's own clocks", () => {
    const rows = itemRows(ITEMS_PAGE.steps[1], ITEMS_PAGE.clocks);
    expect(itemRollUp(rows)).toBe("3 of 12 done, 2 late");
    expect(itemRollUp([])).toBe("0 of 0 done");
    expect(itemRollUp([{ item: "a", state: "failed", clock: null, words: "no clock", late: false }, { item: "b", state: "skipped", clock: null, words: "no clock", late: false }]))
      .toBe("0 of 2 done, 1 failed, 1 skipped");
  });

  it("reads item ids one to a line, once each, in order", () => {
    expect(parseItemLines(" a \r\n\r\nb\na\n  \nc d\n")).toEqual(["a", "b", "c d"]);          // a line is one id: the server refuses "c d"
    expect(parseItemLines("")).toEqual([]);
    expect(setWords("requests")).toBe("the set requests");
    expect(setWords("")).toBe("the run's own items");
  });
});
