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

function stub(signedIn: { name: string } | null, post?: (url: string, body: Record<string, unknown>) => Response) {
  const posts: [string, Record<string, unknown>][] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      posts.push([url, body]);
      return post ? post(url, body) : new Response("{}", { status: 200 });
    }
    if (url.startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn, signIn: { configured: true, start: "/auth/google" } }), { status: 200 });
    if (url.startsWith("/api/onboarding-session")) return new Response(JSON.stringify(session), { status: 200 });
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
    expect(screen.getByRole("img", { name: /jason read/ })).toBeInTheDocument();
    const row = screen.getByText("The units").closest("tr")!;
    expect(within(row).getByText("present")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /done|mark|complete/i })).toBeNull();
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
    const vault = screen.getByText("The password vault").closest("tr")!;
    expect(within(vault).getByText("jason login")).toBeInTheDocument();
    expect(within(vault).queryByRole("textbox")).toBeNull();
  });

  it("offers no answer form until a person signs in", async () => {
    stub(null);
    render(<SetupTab />);
    expect(await screen.findByRole("link", { name: "Sign in with Google" })).toBeInTheDocument();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save the answer" })).toBeNull();
  });
});
