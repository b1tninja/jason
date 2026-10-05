import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { SetupTab } from "./OnboardingSetup";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const gate = (stage: string, open: boolean, waiting: { key: string; status: string }[] = []) => ({ stage, title: `The ${stage} gate`, open, opensWhen: "", waiting, checks: [] });
const LOGIN = { commands: ["jason login"], note: "Credentials are Keeper records, signed in at a terminal." };

const session = {
  found: true, title: "Onboarding: Example Village HOA", asOf: "2026-10-04T12:00:00+00:00", stage: "start",
  progress: { present: 1, partial: 0, missing: 2 }, groups: [],
  gates: [gate("start", false, [{ key: "vault", status: "missing" }]), gate("ingest", false), gate("establish", false), gate("operate", false), gate("adopt", false)],
  counts: { open: 2, answeredNotApplied: 0, notYetInQueue: 1 },
  items: [
    { key: "minute-book", group: "records", groupTitle: "Records", title: "The minute book", why: "CIV 5200", status: "missing", findings: [{ passed: false, evidence: "private fact minute-book: not answered" }], fetch: "", byPerson: true, stages: [],
      ask: { id: "q-mb", question: "Who keeps the minute book?", record: "private facts", stakes: false, inQueue: true, state: "open" }, connect: null },
    { key: "vault", group: "access", groupTitle: "System access", title: "The password vault", why: "jason never stores a password", status: "missing", findings: [{ passed: false, evidence: "setting google_oauth_record_uid: not set" }], fetch: "jason login", byPerson: false, stages: ["start"], ask: null, connect: LOGIN },
    { key: "units", group: "members", groupTitle: "Members", title: "The units", why: "", status: "present", findings: [{ passed: true, evidence: "Community.units(): 2" }], fetch: "", byPerson: true, stages: ["start"], ask: null, connect: null },
  ],
  next: [
    { id: "q-mb", kind: "fact", subject: "fact:minute-book", question: "Who keeps the minute book?", choices: [], suggestion: "", likely: false, evidence: ["checklist minute-book is missing"], priority: 3, unblocks: { items: [{ key: "minute-book", status: "missing" }] }, serves: "minute-book", highStakes: false, inQueue: true, record: "private facts", connect: null },
    { id: "q-portal", kind: "fact", subject: "fact:prior-portal", question: "Which Keeper record holds the prior portal's sign-in?", choices: [], suggestion: "", likely: false, evidence: [], priority: 2, unblocks: {}, serves: "prior-portal", highStakes: false, inQueue: false, record: "kept in Keeper",
      connect: { commands: ['jason onboard --answer q-portal "KEEPER RECORD NAME" --by "YOUR NAME"'], note: "A Keeper record is named by its title only." } },
  ],
  nextTotal: 2, answered: [], apply: { command: "jason onboard --apply", note: "Run by a person." }, caveats: ["A gate is jason's reading of the checklist."],
};

function stub(signedIn: { name: string } | null, post?: ((url: string, body: Record<string, unknown>) => Response) | null, data: unknown = session) {
  const posts: [string, Record<string, unknown>][] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      posts.push([url, body]);
      return post ? post(url, body) : new Response("{}", { status: 200 });
    }
    if (url.startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn, signIn: { configured: true, start: "/auth/google" } }), { status: 200 });
    if (url.startsWith("/api/onboarding-session")) return new Response(JSON.stringify(data), { status: 200 });
    return new Response(JSON.stringify({ error: `unexpected ${url}` }), { status: 404 });
  }));
  return posts;
}

describe("SetupTab", () => {
  it("shows the five gates and each item's computed status, with no done button", async () => {
    stub({ name: "Sam Secretary" });
    render(<SetupTab />);
    const gates = await screen.findByRole("list", { name: "The five gates" });
    expect(within(gates).getAllByRole("listitem")).toHaveLength(5);
    expect(within(gates).getAllByRole("listitem")[0]).toHaveAttribute("aria-current", "step");
    expect(screen.getByText(/1 present, 0 partial, 2 missing/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /jason read, the checklist/ })).toBeInTheDocument();
    const row = screen.getByRole("listitem", { name: "The units" });
    expect(within(row).getByText("present")).toBeInTheDocument();
    expect(within(row).getByText("Nothing to do: its checks pass.")).toBeInTheDocument();
    expect(within(row).getByRole("img", { name: /jason read, Community.units\(\): 2/ })).toBeInTheDocument();
    const mb = screen.getByRole("listitem", { name: "The minute book" });
    expect(within(mb).getByRole("img", { name: /not confirmed, private fact minute-book: not answered/ })).toBeInTheDocument();
    expect(within(mb).getByText(/The answer goes to the private facts/)).toBeInTheDocument();
    expect(within(mb).getByRole("button", { name: "Answer it under Questions" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /done|mark|complete/i })).toBeNull();
  });

  it("groups the checklist by the server's groups, in its order", async () => {
    stub({ name: "Sam Secretary" }, null, { ...session, groups: [
      { group: "access", title: "System access", present: 0, partial: 0, missing: 1 },
      { group: "records", title: "Records", present: 0, partial: 0, missing: 1 },
      { group: "members", title: "Members", present: 1, partial: 0, missing: 0 },
    ] });
    render(<SetupTab />);
    await screen.findByRole("list", { name: "The five gates" });
    const titles = [...document.querySelectorAll("details > summary > strong")].map((s) => s.textContent);
    expect(titles).toEqual(["System access", "Records", "Members"]);
    expect(screen.getByText(/1 of 1 present, 0 partial, 0 missing · holds the start gate/)).toBeInTheDocument();
    // the group holding the gate being worked opens first
    expect(screen.getByText("System access").closest("details")).toHaveAttribute("open");
    expect(screen.getByText("Records").closest("details")).not.toHaveAttribute("open");
  });

  it("names what holds the gate being worked, a high-stakes item first and marked", async () => {
    const signers = { key: "signers", group: "board", groupTitle: "The board", title: "Bank signers", why: "CIV 5380", status: "missing", findings: [], fetch: "", byPerson: true, stages: ["operate"],
      ask: { id: "q-sg", question: "Who signs?", record: "private facts", stakes: true, standing: false, clock: "", inQueue: true, state: "open" }, connect: null };
    const fiscal = { key: "fiscal-year", group: "finance", groupTitle: "Finances", title: "The fiscal year", why: "", status: "partial", findings: [{ passed: true, evidence: "bylaws read" }, { passed: false, evidence: "Community.fiscal_year_end(): empty" }], fetch: "", byPerson: true, stages: ["operate"], ask: null, connect: null };
    stub({ name: "Sam Secretary" }, null, { ...session, stage: "operate", progress: { present: 4, partial: 1, missing: 1 },
      gates: [gate("start", true), gate("ingest", true), gate("establish", true), gate("operate", false, [{ key: "fiscal-year", status: "partial" }, { key: "signers", status: "missing" }]), gate("adopt", false)],
      items: [...session.items, signers, fiscal], next: [], nextTotal: 0 });
    render(<SetupTab />);
    const hold = await screen.findByRole("region", { name: "What holds the operate gate" });
    const rows = within(hold).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Bank signers");
    expect(within(rows[0]).getByText("high stakes")).toBeInTheDocument();
    expect(within(rows[0]).getByText("missing")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("The fiscal year");
    expect(within(rows[1]).queryByText("high stakes")).toBeNull();
    expect(within(hold).queryByRole("button", { name: /open|pass|done/i })).toBeNull();
    const item = screen.getByRole("listitem", { name: "Bank signers" });
    expect(within(item).getByText(/a second person confirms it/)).toBeInTheDocument();
    expect(within(item).getByText("jason onboard --questions --group board")).toBeInTheDocument();
    expect(screen.getByText(/No open questions for the operate gate/)).toBeInTheDocument();
  });

  it("labels a standing question standing, in the questions and on its item", async () => {
    const roster = { key: "board-roster", group: "board", groupTitle: "The board", title: "Directors and officers", why: "", status: "present", findings: [{ passed: true, evidence: "roster: 5 people" }], fetch: "", byPerson: true, stages: ["operate"],
      ask: { id: "q-br", question: "Has an office changed?", record: "private facts", stakes: true, standing: true, clock: "", inQueue: true, state: "open" }, connect: null };
    stub({ name: "Sam Secretary" }, null, { ...session, items: [...session.items, roster],
      next: [...session.next, { id: "q-br", kind: "fact", subject: "fact:board-roster", question: "Has an office changed?", choices: [], suggestion: "", likely: false, evidence: [], priority: 0, unblocks: {}, serves: "board-roster", highStakes: true, inQueue: true, record: "private facts", connect: null, standing: true }],
      nextTotal: 3 });
    render(<SetupTab />);
    const card = (await screen.findByRole("heading", { name: "Has an office changed?", level: 3 })).closest("article")!;
    expect(within(card.parentElement!).getByText("standing")).toBeInTheDocument();
    const minute = screen.getByRole("heading", { name: "Who keeps the minute book?", level: 3 }).closest("article")!;
    expect(within(minute.parentElement!).queryByText("standing")).toBeNull();
    const item = screen.getByRole("listitem", { name: "Directors and officers" });
    expect(within(item).getByText("standing")).toBeInTheDocument();
    expect(within(item).getByText(/A standing question: Has an office changed\?/)).toBeInTheDocument();
    expect(within(item).queryByText(/Nothing to do/)).toBeNull();
  });

  it("names the gate in each empty state on a first run", async () => {
    stub({ name: "Sam Secretary" }, null, { ...session, progress: { present: 0, partial: 0, missing: 3 },
      gates: [{ ...gate("start", false, [{ key: "vault", status: "missing" }]), opensWhen: "open once the vault is present" }, gate("ingest", false), gate("establish", false), gate("operate", false), gate("adopt", false)],
      items: session.items.map((i) => ({ ...i, status: "missing" })), next: [], nextTotal: 0, answered: [] });
    render(<SetupTab />);
    expect(await screen.findByText("First run: nothing on the checklist is present yet. Begin with the start gate, open once the vault is present.")).toBeInTheDocument();
    expect(screen.getByText(/No open questions for the start gate/)).toBeInTheDocument();
    expect(screen.getByText(/No answer waits to be applied. An answer to a question for the start gate waits here/)).toBeInTheDocument();
  });
  it("answers through Confirm as the signed-in person, and shows it waiting to be applied with the command", async () => {
    const posts = stub({ name: "Sam Secretary" }, () => new Response(JSON.stringify({ id: "q-mb", status: "answered", answeredBy: "Sam Secretary", answeredAt: "2026-10-04T12:01:00+00:00", highStakes: false, needsConfirmation: false, applied: false, apply: "jason onboard --apply", next: "Answered, waiting to be applied: a person runs jason onboard --apply in a terminal." }), { status: 200 }));
    const user = userEvent.setup();
    render(<SetupTab />);
    const card = (await screen.findByRole("heading", { name: "Who keeps the minute book?", level: 3 })).closest("article")!;
    expect(await within(card).findByDisplayValue("Sam Secretary")).toHaveAttribute("readonly");
    await user.click(within(card).getByRole("radio", { name: "Another answer" }));
    await user.type(within(card).getByRole("textbox", { name: "Another answer" }), "the secretary keeps it");
    await user.click(within(card).getByRole("button", { name: "Save the answer" }));
    await user.click(within(card).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toEqual(["/api/write/intake/q-mb", { answer: "the secretary keeps it", by: "Sam Secretary" }]);
    const waiting = await screen.findByRole("heading", { name: "Answered, waiting to be applied (1)" });
    const box = waiting.closest("section")!;
    expect(within(box).getByText(/Answered by Sam Secretary, 2026-10-04: waiting to be applied/)).toBeInTheDocument();
    expect(within(box).getByText("jason onboard --apply")).toBeInTheDocument();
    expect(within(box).queryByText(/the secretary keeps it/)).toBeNull();
  });

  it("says a refused secret's reason and clears the field", async () => {
    stub({ name: "Sam Secretary" }, () => new Response(JSON.stringify({ error: "Not stored: it gives a password. jason keeps no secrets." }), { status: 400 }));
    const user = userEvent.setup();
    render(<SetupTab />);
    const card = (await screen.findByRole("heading", { name: "Who keeps the minute book?", level: 3 })).closest("article")!;
    await within(card).findByDisplayValue("Sam Secretary");
    await user.click(within(card).getByRole("radio", { name: "Another answer" }));
    await user.type(within(card).getByRole("textbox", { name: "Another answer" }), "password: hunter22");
    await user.click(within(card).getByRole("button", { name: "Save the answer" }));
    await user.click(within(card).getByRole("button", { name: "Yes, do it" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("it gives a password");
    expect(screen.queryByDisplayValue("password: hunter22")).toBeNull();
  });

  it("shows a connection's terminal command, never a field for a secret", async () => {
    stub({ name: "Sam Secretary" });
    render(<SetupTab />);
    const portal = (await screen.findByRole("heading", { name: /prior portal's sign-in/ })).closest("article")!;
    expect(within(portal).getByText('jason onboard --answer q-portal "KEEPER RECORD NAME" --by "YOUR NAME"')).toBeInTheDocument();
    expect(within(portal).queryByRole("textbox")).toBeNull();
    expect(within(portal).queryByRole("radio")).toBeNull();
    const vault = screen.getByRole("listitem", { name: "The password vault" });
    expect(within(vault).getByText("jason login")).toBeInTheDocument();
    expect(within(vault).getByText(/the console never takes a secret/)).toBeInTheDocument();
    expect(within(vault).queryByRole("textbox")).toBeNull();
    expect(within(vault).queryByRole("radio")).toBeNull();
  });

  it("offers no answer form until a person signs in", async () => {
    stub(null);
    render(<SetupTab />);
    expect(await screen.findByRole("link", { name: "Sign in with Google" })).toBeInTheDocument();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save the answer" })).toBeNull();
  });
});
