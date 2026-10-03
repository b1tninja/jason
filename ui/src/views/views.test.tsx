import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BoardItemsView } from "./BoardItemsView";
import { LeadsView } from "./LeadsView";
import { DueDate, Kanban, Timeline } from "../components";

const item = {
  id: "reserve-loan", title: "Reserve loan not restored", summary: "s", ask: "Decide whether to restore", category: "reserves", priority: "high",
  status: "open", authority: "CIV 5515(d)", evidence: ["jason reserves --transfers"], session: null, special_notice: "", due: null, opened: "2026-09-01",
  owner: "", meeting: "", notes: "", source: "jason", history: [],
};

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

describe("BoardItemsView", () => {
  it("lanes items by status and saves only the board's fields after a confirm", async () => {
    const posted: unknown[] = [];
    mockFetch({
      "/api/board-items/reserve-loan": (init) => { posted.push(JSON.parse(String(init?.body))); return { ...item, status: "on agenda", owner: "T" }; },
      "/api/board-items": () => ({ found: true, items: [item] }),
    });
    const user = userEvent.setup();
    render(<BoardItemsView />);
    const lane = await screen.findByRole("region", { name: "open" });
    expect(within(lane).getByText("Reserve loan not restored")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Details/ }));
    await user.selectOptions(screen.getByLabelText("Status"), "on agenda");
    await user.type(screen.getByLabelText("Owner"), "T");
    expect(screen.queryByText("Yes, do it")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save board fields" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("status");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ status: "on agenda", owner: "T" }]));
    expect(within(await screen.findByRole("region", { name: "on agenda" })).getByText("Reserve loan not restored")).toBeInTheDocument();
  });

  it("shows the tool's not-found note", async () => {
    mockFetch({ "/api/board-items": () => ({ found: false, items: [], note: "run jason board" }) });
    render(<BoardItemsView />);
    expect(await screen.findByText("run jason board")).toBeInTheDocument();
  });
});

describe("LeadsView", () => {
  it("filters by kind and repeats the caveat", async () => {
    mockFetch({
      "/api/leads": () => ({
        count: 2, counts: { "records gap": 1, "unclassified file": 1 }, notes: [], caveats: ["A lead is evidence, not a pin."],
        rows: [
          { source: "records_inventory", kind: "records gap", title: "minutes", detail: "nothing pinned", next: "pin it" },
          { source: "library_status", kind: "unclassified file", title: "x.pdf", detail: "no rule", next: "classify" },
        ],
      }),
    });
    render(<LeadsView />);
    expect(await screen.findByText("A lead is evidence, not a pin.")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: "records gap 1" }));
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("minutes")).toBeInTheDocument();
  });
});

describe("primitives", () => {
  it("DueDate marks overdue and soon", () => {
    const today = new Date("2026-10-03T12:00:00");
    const { rerender } = render(<DueDate iso="2026-10-01" today={today} />);
    expect(screen.getByText("2d overdue")).toBeInTheDocument();
    rerender(<DueDate iso="2026-10-10" today={today} />);
    expect(screen.getByText("in 7d")).toBeInTheDocument();
    rerender(<DueDate iso={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
  it("Timeline sorts oldest first with undated last", () => {
    render(<Timeline events={[{ id: "b", date: "", title: "undated" }, { id: "a", date: "2020-01-01", title: "old" }, { id: "c", date: "2024-01-01", title: "new" }]} />);
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["2020-01-01old", "2024-01-01new", "undatedundated"]);
  });
  it("Kanban keeps empty lanes", () => {
    render(<Kanban lanes={["a", "b"]} items={[{ k: "a" }]} laneOf={(i) => i.k} keyOf={(i) => i.k} render={(i) => i.k} />);
    expect(screen.getByRole("region", { name: "b" })).toHaveTextContent("0");
  });
});
