import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActionRegister, AskPanel, DeadlineList, DOCK_DRAWERS, DockToolbar, Drawer, Scratchpad } from "./index";

function mockFetch(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return new Response(JSON.stringify({ error: `no route ${url}` }), { status: 404 });
    return new Response(JSON.stringify(routes[key](init)), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
afterEach(() => vi.unstubAllGlobals());

const counts = { deadlines: 2, tasks: 1 };

describe("DockToolbar", () => {
  it("shows four pills with red counts for the board, and only Ask for owners", () => {
    const { unmount } = render(<DockToolbar open="tasks" onToggle={() => {}} counts={counts} audience="board" />);
    const bar = screen.getByRole("toolbar", { name: "Dock" });
    expect(within(bar).getAllByRole("button").map((b) => b.textContent)).toEqual(["Deadlines2", "Tasks1", "Scratchpad", "Ask"]);
    expect(within(bar).getByRole("button", { name: /Tasks/ })).toHaveAttribute("aria-expanded", "true");
    expect(within(bar).getByRole("button", { name: /Deadlines/ })).toHaveAttribute("aria-expanded", "false");
    unmount();
    render(<DockToolbar open={null} onToggle={() => {}} counts={counts} audience="owner" />);
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual(["Ask"]);
  });

  it("toggles by id and lists the drawers owners may open", async () => {
    const user = userEvent.setup();
    const toggled: string[] = [];
    render(<DockToolbar open={null} onToggle={(id) => toggled.push(id)} counts={{ deadlines: 0, tasks: 0 }} audience="board" />);
    await user.click(screen.getByRole("button", { name: "Scratchpad" }));
    expect(toggled).toEqual(["notes"]);
    expect(screen.queryByLabelText(/overdue/)).not.toBeInTheDocument();
    expect(DOCK_DRAWERS.filter((d) => d.owner).map((d) => d.id)).toEqual(["ask"]);
  });
});

describe("Drawer", () => {
  const props = { id: "ask", title: "Ask jason", onPin: vi.fn(), onUnpin: vi.fn(), onClose: vi.fn() };
  it("floats as a dialog with Dock it only when it can dock", () => {
    const { unmount } = render(<Drawer {...props} pinned={false} canDock><p>body</p></Drawer>);
    const dialog = screen.getByRole("dialog", { name: "Ask jason" });
    expect(dialog).toHaveClass("drawer-float");
    expect(within(dialog).getByRole("button", { name: "Dock it" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Float" })).not.toBeInTheDocument();
    unmount();
    render(<Drawer {...props} pinned={false} canDock={false}><p>body</p></Drawer>);
    expect(screen.queryByRole("button", { name: "Dock it" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("pins as a column card with Float, not a dialog", async () => {
    const user = userEvent.setup();
    render(<Drawer {...props} pinned canDock><p>body</p></Drawer>);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const aside = screen.getByRole("complementary", { name: "Ask jason" });
    expect(aside).toHaveClass("drawer-pinned");
    await user.click(within(aside).getByRole("button", { name: "Float" }));
    expect(props.onUnpin).toHaveBeenCalled();
    await user.click(within(aside).getByRole("button", { name: "Close" }));
    expect(props.onClose).toHaveBeenCalled();
  });
});

describe("DeadlineList", () => {
  it("groups Overdue, Next 14 days, Later and links each row to its screen", async () => {
    mockFetch({
      "/api/dock?part=deadlines": () => ({
        found: true, asOf: "2026-10-03", today: "2026-10-03", counts: { overdue: 1, soon: 1, later: 0 }, caveats: ["A payment is evidence, not proof."],
        groups: [
          { key: "overdue", label: "Overdue", rows: [{ id: "d1", title: "D&O renewal certificate", date: "2026-09-30", days: -3, authority: "the policy term", standing: "overdue", note: "", screen: "insurance" }] },
          { key: "soon", label: "Next 14 days", rows: [{ id: "d2", title: "Budget report to members", date: "2026-10-10", days: 7, authority: "CIV 5300", standing: "due soon", note: "", screen: "reserves" }] },
          { key: "later", label: "Later", rows: [] },
        ],
        clock: [{ key: "d1", label: "D&O renewal certificate", date: "2026-09-30", authority: "the policy term" }],
      }),
    });
    const user = userEvent.setup();
    const went: string[] = [];
    render(<DeadlineList go={(s) => went.push(s)} />);
    const over = await screen.findByRole("region", { name: "Overdue" });
    expect(within(over).getByText("3d overdue")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Later" })).getByText("Nothing here.")).toBeInTheDocument();
    expect(screen.getByText("the policy term · Insurance")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Budget report to members" }));
    expect(went).toEqual(["reserves"]);
    expect(screen.getByText("A payment is evidence, not proof.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "timeline" })).toBeInTheDocument();
  });
});

const task = { id: "t1", text: "Collect two landscape bids", source: "manual", screen: "", owner: "D. Okafor", due: "2026-09-20", done: false, doneBy: "", doneAt: "", created: "2026-09-01T00:00:00+00:00", by: "D. Okafor" };

describe("ActionRegister", () => {
  it("filters, and the done checkbox stamps who after a confirm", async () => {
    const posted: { url: string; body: unknown }[] = [];
    mockFetch({
      "/api/write/dock/t1": (init) => { posted.push({ url: "/api/write/dock/t1", body: JSON.parse(String(init?.body)) }); return { ...task, done: true, doneBy: "D. Okafor", doneAt: "2026-10-03T10:00:00+00:00" }; },
      "/api/dock?part=tasks": () => ({ found: true, today: "2026-10-03", count: 2, overdue: 1, open: 2, caveats: [], tasks: [task, { ...task, id: "t2", text: "Review the draft minutes", owner: "P. Quinn", due: "2026-10-16", source: "meetings", screen: "meetings" }] }),
    });
    const user = userEvent.setup();
    render(<ActionRegister go={() => {}} me="D. Okafor" />);
    expect(await screen.findByRole("tab", { name: "Open 2" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Mine 1" }));
    expect(screen.getByText("Collect two landscape bids")).toBeInTheDocument();
    expect(screen.queryByText("Review the draft minutes")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Overdue 1" }));
    expect(screen.getByText("13d overdue")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Done: Collect two landscape bids" }));
    expect(posted).toEqual([]);
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("stamped D. Okafor");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ url: "/api/write/dock/t1", body: { action: "task_done", by: "D. Okafor", done: true } }]));
  });

  it("quick add posts a task with owner and due behind Confirm", async () => {
    const posted: unknown[] = [];
    mockFetch({
      "/api/write/dock/new": (init) => { posted.push(JSON.parse(String(init?.body))); return { ...task, id: "t3" }; },
      "/api/dock?part=tasks": () => ({ found: true, today: "2026-10-03", count: 0, overdue: 0, open: 0, tasks: [] }),
    });
    const user = userEvent.setup();
    render(<ActionRegister go={() => {}} />);
    expect(await screen.findByText("Nothing here.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add task" })).toBeDisabled();
    await user.type(screen.getByLabelText("Your name"), "P. Quinn");
    await user.type(screen.getByLabelText("Task"), "Bring three reserve study bids");
    await user.type(screen.getByLabelText("Owner"), "the manager");
    await user.click(screen.getByRole("button", { name: "Add task" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("for the manager");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ action: "task_add", by: "P. Quinn", text: "Bring three reserve study bids", owner: "the manager", due: "", source: "manual" }]));
  });
});

describe("Scratchpad", () => {
  it("lists notes as working notes and hands a follow-up to the register", async () => {
    const posted: unknown[] = [];
    mockFetch({
      "/api/write/dock/new": (init) => { posted.push(JSON.parse(String(init?.body))); return { id: "t9" }; },
      "/api/dock?part=notes": () => ({ found: true, count: 1, statuses: ["researching", "question", "draft", "parked", "done"], caveat: "Working notes, not association records.",
        notes: [{ id: "n1", title: "Reserve study vendors", status: "question", body: "Ask **three** firms.", sources: ["CIV 5550"], created: "2026-10-01T00:00:00+00:00", updated: "2026-10-02T00:00:00+00:00", by: "D" }] }),
    });
    const user = userEvent.setup();
    render(<Scratchpad me="D. Okafor" />);
    expect(await screen.findByText(/Working notes, not association records/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Reserve study vendors/ }));
    expect(screen.getByLabelText("Title")).toHaveValue("Reserve study vendors");
    expect(screen.getByText("CIV 5550")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add a follow-up to the register" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ action: "task_add", by: "D. Okafor", text: "Follow up: Reserve study vendors", source: "scratchpad" }]));
    expect(await screen.findByText("On the action register.")).toBeInTheDocument();
  });
});

describe("AskPanel", () => {
  const ask = {
    found: true, routedAnswer: "jason has no sourced answer; routed to the manager", translateCommand: "", translationStates: ["needs review", "sent for review", "approved"],
    caveats: ["A question with no sourced answer goes to the action register for the manager. jason never guesses."],
    common: [
      { question: "When is the next board meeting?", screen: "meetings", answer: "The next board meeting is 2026-10-21.", sources: ["meeting()", "CIV 4920"], routed: false },
      { question: "What did the board decide last meeting?", screen: "decisions", answer: "", sources: [], routed: true },
    ],
    asks: [],
    translations: [{ id: "x1", englishKey: "notice-2026-10-21", english: "The board meets October 21.", language: "Spanish", draft: "La junta se reúne el 21 de octubre.", state: "needs review", by: "D", at: "2026-10-02T00:00:00+00:00" }],
  };

  it("answers a common question with sources and a link, and shows the routed state when there are none", async () => {
    mockFetch({ "/api/dock?part=ask": () => ask });
    const user = userEvent.setup();
    const went: string[] = [];
    render(<AskPanel go={(s) => went.push(s)} me="D. Okafor" />);
    await user.click(await screen.findByRole("button", { name: /When is the next board meeting/ }));
    const answer = screen.getByRole("article", { name: "Answer" });
    expect(answer).toHaveTextContent("The next board meeting is 2026-10-21.");
    expect(within(answer).getByText("CIV 4920")).toBeInTheDocument();
    await user.click(within(answer).getByRole("button", { name: "Open Meetings" }));
    expect(went).toEqual(["meetings"]);
    await user.click(screen.getByRole("button", { name: /What did the board decide/ }));
    expect(screen.getByRole("article", { name: "No sourced answer" })).toHaveTextContent("went to the action register for the manager");
    expect(screen.queryByText("Sources:")).not.toBeInTheDocument();
  });

  it("a free question is a write behind Confirm, and a routed answer reads as routed", async () => {
    const posted: unknown[] = [];
    mockFetch({
      "/api/write/dock/new": (init) => { posted.push(JSON.parse(String(init?.body))); return { id: "q1", question: "Can we fine without a hearing?", answer: "jason has no sourced answer; routed to the manager", sources: [], screen: "", routed: true, at: "", by: "D" }; },
      "/api/dock?part=ask": () => ask,
    });
    const user = userEvent.setup();
    render(<AskPanel go={() => {}} me="D. Okafor" />);
    await user.type(await screen.findByLabelText("Question"), "Can we fine without a hearing?");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(posted).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ action: "ask", by: "D. Okafor", question: "Can we fine without a hearing?" }]));
    expect(await screen.findByRole("article", { name: "No sourced answer" })).toHaveTextContent("Can we fine without a hearing?");
  });

  it("the Translate tab shows the English record beside a draft marked needs review and sends for review behind Confirm", async () => {
    const posted: { url: string; body: unknown }[] = [];
    mockFetch({
      "/api/write/dock/x1": (init) => { posted.push({ url: "x1", body: JSON.parse(String(init?.body)) }); return { ...ask.translations[0], state: "sent for review" }; },
      "/api/dock?part=ask": () => ask,
    });
    const user = userEvent.setup();
    render(<AskPanel go={() => {}} me="D. Okafor" />);
    await user.click(await screen.findByRole("tab", { name: "Translate" }));
    const record = screen.getByLabelText("Translation record");
    expect(within(record).getByText("The board meets October 21.")).toHaveAttribute("lang", "en");
    expect(within(record).getByText("needs review")).toBeInTheDocument();
    expect(within(record).getByText("La junta se reúne el 21 de octubre.")).toBeInTheDocument();
    expect(screen.getByText(/the English notice controls/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send for review" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("fluent reviewer");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ url: "x1", body: { action: "translation_state", by: "D. Okafor", state: "sent for review" } }]));
  });
});
