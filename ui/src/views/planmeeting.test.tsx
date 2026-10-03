import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionsView } from "./DecisionsView";
import { PlanMeetingView } from "./PlanMeetingView";

afterEach(() => vi.unstubAllGlobals());

const loan = {
  id: "reserve-loan", title: "Reserve loan not restored", ask: "Decide whether to restore the loan", session: "open session", authority: "CIV 5515(d)", evidence: ["jason reserves --transfers"],
  kind: "action", include: false, motion: "", allot: 10, order: 0, packet: [], brief: null,
  readiness: { ready: false, checks: [{ label: "Motion drafted", ok: false, why: "no motion drafted yet" }] }, suggestion: "no motion drafted yet",
};
const written = { ...loan, id: "paint", title: "Painting contract", ask: "Approve a contract", brief: { question: "Which painter?", criteria: ["Cost"], options: [{ label: "Alpha", values: ["$1,000.00"] }, { label: "Beta", values: ["$1,200.00"] }], facts: [] } };
const plan = (candidates: unknown[]) => ({
  found: true, date: "2026-10-21", today: "2026-10-03", noticeBy: "2026-10-17", executiveNoticeBy: "2026-10-19", directors: ["A. Director", "B. Director"], decisions: [],
  basics: { date: "2026-10-21", start: "", format: "", location: "", join: "", dialIn: "", help: "" }, zoom: { topic: "", joinUrl: "", dialIn: "", command: null, note: "no command" },
  candidates, kinds: ["consent", "discussion", "action", "executive"], formats: ["in person", "hybrid", "teleconference"], rules: [],
  notice: { by: "2026-10-17", executiveBy: "2026-10-19", required: [] }, steps: ["Meeting", "Ready to act", "Order and motions", "Notice"],
  commands: { agendaDoc: "jason board --agenda <id> --date 2026-10-21 --doc --yes", packetDoc: "jason board --packet --date 2026-10-21 --doc --yes", minutesDraft: "jason board --minutes 2026-10-21", notice: "jason board --set <item id> --status \"on agenda\" --meeting 2026-10-21", onAgenda: [] },
  updated: "", history: [], caveats: ["The board sets the agenda."],
});

function mockFetch(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return new Response(JSON.stringify({ error: `no route ${url}` }), { status: 404 });
    return new Response(JSON.stringify(routes[key](init)), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", f);
  return f;
}

describe("PlanMeetingView", () => {
  it("loads the plan, saves the basics behind a confirm to the plan store, and reloads", async () => {
    const posted: { url: string; body: unknown }[] = [];
    let saved = plan([loan]);
    mockFetch({
      "/api/write/agenda-plan/2026-10-21": (init) => { posted.push({ url: "/api/write/agenda-plan/2026-10-21", body: JSON.parse(String(init?.body)) }); saved = { ...saved, updated: "2026-10-03T10:00:00+00:00", basics: { ...saved.basics, start: "18:30", format: "teleconference" } }; return saved; },
      "/api/agenda-plan": () => saved,
    });
    const user = userEvent.setup();
    render(<PlanMeetingView />);
    expect(await screen.findByRole("heading", { level: 1, name: "Plan a meeting" })).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Entirely by teleconference/ }));
    await user.type(screen.getByLabelText("Start"), "18:30");
    expect(screen.queryByText("Yes, do it")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Saved by"), "D. Okafor");
    await user.click(screen.getByRole("button", { name: "Save the plan" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    expect(confirm).toHaveTextContent("Format: — → teleconference");
    expect(confirm).toHaveTextContent("Start: — → 18:30");
    expect(confirm).toHaveTextContent("Nothing goes on the noticed agenda and nothing is sent");
    await user.click(within(confirm).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ url: "/api/write/agenda-plan/2026-10-21", body: { by: "D. Okafor", basics: { start: "18:30", format: "teleconference" } } }]));
    expect(await screen.findByText(/plan saved 2026-10-03 10:00 UTC/)).toBeInTheDocument();
  });

  it("shows the tool's not-found note", async () => {
    mockFetch({ "/api/agenda-plan": () => ({ found: false, note: "date is YYYY-MM-DD" }) });
    render(<PlanMeetingView />);
    expect(await screen.findByText("date is YYYY-MM-DD")).toBeInTheDocument();
  });
});

describe("DecisionsView", () => {
  it("shows a written brief, lets a person write a missing one behind a confirm, and records decisions through /api/decisions", async () => {
    const posted: { url: string; body: Record<string, unknown> }[] = [];
    mockFetch({
      "/api/write/agenda-plan/2026-10-21": (init) => { posted.push({ url: "plan", body: JSON.parse(String(init?.body)) }); return plan([loan, written]); },
      "/api/decisions": (init) => { const b = JSON.parse(String(init?.body)); posted.push({ url: "decisions", body: b }); return { ...b, id: `${b.meeting}--${b.item}`, recorded: "x", updated: "x", history: [], tally: {}, suggested: "" }; },
      "/api/agenda-plan": () => plan([loan, written]),
    });
    const user = userEvent.setup();
    render(<DecisionsView />);
    expect(await screen.findByText("Which painter?")).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Option B" })).toHaveTextContent("Beta");
    expect(screen.getAllByText("jason lays out the options and the facts on file. It does not recommend one; the board chooses.").length).toBeGreaterThan(0);
    expect(screen.getByText(/No brief yet/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/recommend/i)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Your name"), "D. Okafor");
    await user.clear(screen.getByLabelText("The question before the board"));
    await user.type(screen.getByLabelText("The question before the board"), "How is the loan restored?");
    await user.type(screen.getByLabelText("Criteria, one per line"), "How{enter}When");
    const [labelA, valuesA] = within(screen.getByText("Option A").closest("label") as HTMLElement).getAllByRole("textbox");
    await user.type(labelA, "Transfer");
    await user.type(valuesA, "from operating{enter}by 2026-10-31");
    const [labelB] = within(screen.getByText("Option B", { selector: "label" }).closest("label") as HTMLElement).getAllByRole("textbox");
    await user.type(labelB, "Delay");
    await user.click(screen.getByRole("button", { name: "Save the brief" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    expect(confirm).toHaveTextContent("2 options (Transfer, Delay)");
    expect(confirm).toHaveTextContent("No recommendation is saved; the board chooses.");
    await user.click(within(confirm).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted[0]).toEqual({ url: "plan", body: { by: "D. Okafor", items: { "reserve-loan": { brief: { question: "How is the loan restored?", criteria: ["How", "When"], options: [{ label: "Transfer", values: ["from operating", "by 2026-10-31"] }, { label: "Delay", values: ["", ""] }], facts: ["jason reserves --transfers"] } } } } }));
    const cards = screen.getAllByText("Motion, as made").map((l) => l.closest("article") as HTMLElement);
    await user.type(within(cards[1]).getByLabelText("Motion, as made"), "Move to hire Alpha.");
    await user.click(within(cards[1]).getByRole("button", { name: "Record the decision" }));
    await user.click(within(cards[1]).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted[1].url).toBe("decisions"));
    expect(posted[1].body).toMatchObject({ meeting: "2026-10-21", item: "paint", title: "Painting contract", motion: "Move to hire Alpha.", session: "open session" });
  });
});
