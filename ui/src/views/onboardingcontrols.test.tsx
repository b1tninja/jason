import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import {
  CONTRACT_LIMIT, EMPTY_PAGE, NONE_SUGGESTED_PAGE, RESERVE, SECOND_PERSON, SUGGESTED_PAGE, proposedAnswer,
} from "../lib/controls.fixtures";
import { OnboardingControlsStep, SEEN_KEY } from "./OnboardingControls";
import { SetupTab } from "./OnboardingSetup";

interface Call { url: string; method: string; body?: unknown }
type Write = { status: number; body: unknown } | ((key: string) => Promise<{ status: number; body: unknown }>);

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const BY_KEY = { [RESERVE.key]: RESERVE, [CONTRACT_LIMIT.key]: CONTRACT_LIMIT, [SECOND_PERSON.key]: SECOND_PERSON } as const;

/** A made-up server: the suggestions (each read pops the next answer; the last repeats), the write for each control, the session. */
function serve(opts: { list?: unknown[]; writes?: Record<string, Write>; session?: Record<string, unknown>; setup?: unknown } = {}) {
  const calls: Call[] = [];
  const list = [...(opts.list ?? [SUGGESTED_PAGE])];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const method = init?.method ?? "GET";
    if (u.startsWith("/api/session"))
      return json(200, { token: "t", header: "X-Jason-Token", signedIn: { name: "A. Secretary", role: "secretary" }, ...(opts.session ?? {}) });
    if (method === "POST") {
      const key = decodeURIComponent(u.split("/").pop() ?? "");
      calls.push({ url: u, method, body: JSON.parse(String(init?.body)) });
      const w = opts.writes?.[key] ?? { status: 200, body: proposedAnswer(BY_KEY[key as keyof typeof BY_KEY]) };
      const got = typeof w === "function" ? await w(key) : w;
      return json(got.status, got.body);
    }
    calls.push({ url: u, method });
    if (u.startsWith("/api/controls")) {
      const next = list.length > 1 ? list.shift()! : list[0];
      return json(200, next);
    }
    if (u.startsWith("/api/onboarding-session") && opts.setup) return json(200, opts.setup);
    return json(404, { error: "not here" });
  }));
  return calls;
}

beforeEach(() => { resetServerSession(); localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetServerSession(); localStorage.clear(); });

const posts = (calls: Call[]) => calls.filter((c) => c.method === "POST");

async function shown() {
  render(<OnboardingControlsStep />);
  await screen.findByRole("heading", { level: 3, name: "Money" });
}

describe("the onboarding controls step", () => {
  it("reads the suggestions and shows them grouped by family, with each provision under a disclosure", async () => {
    const calls = serve();
    await shown();
    expect(calls[0].url).toBe("/api/controls?state=suggested");
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent).filter((t) => ["Money", "Contracts", "Onboarding"].includes(t ?? "")))
      .toEqual(["Money", "Contracts", "Onboarding"]);
    const money = screen.getByRole("region", { name: "Money suggestions" });
    expect(within(money).getByRole("link", { name: RESERVE.title })).toBeInTheDocument();
    expect(within(money).getByText("suggested")).toBeInTheDocument();
    // the provision is the stored words, whole, under a disclosure; the row never says it is in force
    expect(within(money).getByText("The provision, whole")).toBeInTheDocument();
    expect(within(money).getByText(RESERVE.basis.words)).toBeInTheDocument();
    expect(document.querySelector(".control-list")?.textContent).not.toMatch(/in force/i);
    // optional: said so, and the card names no gate it holds
    expect(screen.getByText(/Optional, and no gate waits on it/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Take these to the board" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not now" })).toBeInTheDocument();
    // the one button does the proposing: a row has no Propose of its own
    expect(screen.queryByRole("button", { name: /^Propose/ })).toBeNull();
    expect(posts(calls)).toHaveLength(0);                       // reading wrote nothing
  });

  it("takes each suggestion to the board one at a time, reports each result, and adopts nothing", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => { release = r; });
    const calls = serve({
      list: [SUGGESTED_PAGE, NONE_SUGGESTED_PAGE],
      writes: { [RESERVE.key]: async (k) => { await gate; return { status: 200, body: proposedAnswer(BY_KEY[k as keyof typeof BY_KEY]) }; } },
    });
    await shown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Take these to the board" }));
    const group = screen.getByRole("group", { name: "Take these to the board" });
    expect(group).toHaveTextContent(/these 3 suggestions/);
    expect(group).toHaveTextContent(/adopts nothing and changes no rule/);
    await user.click(within(group).getByRole("button", { name: "Yes, do it" }));
    // the first write is held: the second has not been sent (one at a time)
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 30));
    expect(posts(calls)).toHaveLength(1);
    expect(posts(calls)[0]).toMatchObject({ url: `/api/write/controls/${RESERVE.key}`, body: { act: "propose" } });
    release();
    await waitFor(() => expect(posts(calls)).toHaveLength(3));
    expect(posts(calls).map((c) => c.url)).toEqual([RESERVE, CONTRACT_LIMIT, SECOND_PERSON].map((c) => `/api/write/controls/${c.key}`));
    expect(posts(calls).every((c) => JSON.stringify(c.body) === JSON.stringify({ act: "propose" }))).toBe(true);
    const results = await screen.findByTestId("controls-results");
    await waitFor(() => expect(within(results).getAllByRole("listitem")).toHaveLength(3));
    for (const c of [RESERVE, CONTRACT_LIMIT, SECOND_PERSON]) {
      const li = within(results).getByText(c.title).closest("li") as HTMLElement;
      expect(within(li).getByRole("link", { name: `control-${c.key}` })).toHaveAttribute("href", `#/actions?item=control-${c.key}`);
    }
    // the list is read again and nothing is suggested now; the results stay, and no act but propose was ever sent
    await waitFor(() => expect(calls.filter((c) => c.method === "GET" && c.url.startsWith("/api/controls"))).toHaveLength(2));
    expect(await screen.findByTestId("controls-results")).toBeInTheDocument();
    expect(screen.queryByTestId("controls-none")).toBeNull();
    expect(screen.queryByRole("button", { name: "Take these to the board" })).toBeNull();
    expect(JSON.stringify(posts(calls))).not.toMatch(/adopt|decline|defer|retire/);
  });

  it("reports a refusal in the server's words and goes on with the rest", async () => {
    const calls = serve({
      writes: { [CONTRACT_LIMIT.key]: { status: 400, body: { error: "contract-limit was declined with no date to ask again" } } },
    });
    await shown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Take these to the board" }));
    await user.click(within(screen.getByRole("group", { name: "Take these to the board" })).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts(calls)).toHaveLength(3));
    const results = await screen.findByTestId("controls-results");
    await waitFor(() => expect(within(results).getAllByRole("listitem")).toHaveLength(3));
    const bad = within(results).getByText(CONTRACT_LIMIT.title).closest("li") as HTMLElement;
    expect(bad).toHaveTextContent("refused: contract-limit was declined with no date to ask again");
    expect(within(results).getByText(SECOND_PERSON.title).closest("li")).toHaveTextContent(`control-${SECOND_PERSON.key}`);
  });

  it("stops at a sign-in refusal and says the rest were not tried", async () => {
    const calls = serve({ writes: { [RESERVE.key]: { status: 403, body: { error: "A. Owner may not put a control before the board" } } } });
    await shown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Take these to the board" }));
    await user.click(within(screen.getByRole("group", { name: "Take these to the board" })).getByRole("button", { name: "Yes, do it" }));
    const results = await screen.findByTestId("controls-results");
    await waitFor(() => expect(within(results).getAllByRole("listitem")).toHaveLength(3));
    expect(posts(calls)).toHaveLength(1);
    expect(within(results).getByText(RESERVE.title).closest("li")).toHaveTextContent("refused: A. Owner may not put a control before the board");
    expect(within(results).getByText(CONTRACT_LIMIT.title).closest("li")).toHaveTextContent(/not tried/);
  });

  it("'Not now' hides the suggestions, remembers it in this browser, and says nothing was adopted", async () => {
    serve();
    await shown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Not now" }));
    const seen = await screen.findByTestId("controls-seen");
    expect(seen).toHaveTextContent(/^Seen \d{4}-\d{2}-\d{2}; nothing adopted\./);
    expect(localStorage.getItem(SEEN_KEY)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(screen.queryByRole("button", { name: "Take these to the board" })).toBeNull();
    // opened again in this browser, it stays dismissed and does not ask the server
    cleanup();
    const calls = serve();
    render(<OnboardingControlsStep />);
    expect(await screen.findByTestId("controls-seen")).toBeInTheDocument();
    expect(calls.filter((c) => c.url.startsWith("/api/controls"))).toHaveLength(0);
    // and it can be brought back
    await user.click(screen.getByRole("button", { name: "Show them again" }));
    await screen.findByRole("heading", { level: 3, name: "Money" });
    expect(localStorage.getItem(SEEN_KEY)).toBeNull();
  });

  it("works when the browser's storage cannot be used", async () => {
    vi.stubGlobal("localStorage", {
      getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); },
    });
    serve();
    await shown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Not now" }));
    expect(await screen.findByTestId("controls-seen")).toBeInTheDocument();          // dismissed for this page, remembered nowhere
  });

  it("shows the Controls screen's empty state when the documents' duties have not been read", async () => {
    serve({ list: [{ ...EMPTY_PAGE, controls: [], families: [] }] });
    render(<OnboardingControlsStep />);
    expect(await screen.findByTestId("controls-empty")).toHaveTextContent("jason has not read your governing documents. Ingest them from Onboarding.");
    expect(screen.queryByRole("button", { name: "Take these to the board" })).toBeNull();
    expect(screen.getByRole("button", { name: "Not now" })).toBeInTheDocument();
  });

  it("says so, quietly, when the documents were read and nothing is suggested", async () => {
    serve({ list: [NONE_SUGGESTED_PAGE] });
    render(<OnboardingControlsStep />);
    expect(await screen.findByTestId("controls-none")).toHaveTextContent("has no control to suggest");
    expect(screen.queryByRole("button", { name: "Take these to the board" })).toBeNull();
  });

  it("is a note, not an alert, when the suggestions cannot be read (the step is only an aid)", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => String(url).startsWith("/api/session")
      ? json(200, { token: "t", header: "X-Jason-Token", signedIn: { name: "A. Secretary" } })
      : json(403, { error: "Only the board and the manager open the controls." })));
    render(<OnboardingControlsStep />);
    const note = await screen.findByTestId("controls-unread");
    expect(note).toHaveTextContent("Only the board and the manager open the controls.");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button", { name: "Take these to the board" })).toBeNull();
  });

  it("gives an administrator viewing as someone else the sentence in place of the button", async () => {
    serve({ session: { acting: { name: "B. Director", role: "director" } } });
    await shown();
    expect(await screen.findByText(/Viewing as B. Director \(admin view\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Take these to the board" })).toBeNull();
  });
});

describe("in the Setup tab", () => {
  const gate = (stage: string, open: boolean) => ({ stage, title: `The ${stage} gate`, open, opensWhen: "", waiting: [], checks: [] });
  const setup = {
    found: true, title: "Onboarding: Example Village HOA", asOf: "2099-10-04T12:00:00+00:00", stage: "ingest",
    progress: { present: 1, partial: 0, missing: 0 }, groups: [],
    gates: [gate("start", true), gate("ingest", false), gate("establish", false), gate("operate", false), gate("adopt", false)],
    counts: { open: 0, answeredNotApplied: 0, notYetInQueue: 0 }, items: [], next: [], nextTotal: 0, answered: [],
    apply: { command: "jason onboard --apply", note: "Run by a person." }, caveats: [],
  };

  it("is one optional card before the checklist, and the gates do not change with it", async () => {
    serve({ setup });
    render(<SetupTab />);
    const checklist = await screen.findByRole("heading", { name: "The checklist" });
    const step = await screen.findByRole("heading", { name: "Controls jason suggests from your documents" });
    expect(step.compareDocumentPosition(checklist) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();   // the card comes before the checklist
    await screen.findByRole("heading", { level: 3, name: "Money" });
    const gates = screen.getByRole("list", { name: "The five gates" });
    expect(within(gates).getAllByRole("listitem")).toHaveLength(5);
    expect(within(gates).getAllByRole("listitem")[1]).toHaveAttribute("aria-current", "step");         // still the ingest gate
    expect(gates).not.toHaveTextContent(/control/i);
  });
});
