import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CalendarView } from "./CalendarView";
import { DutiesView } from "./DutiesView";
import { MeetingsView } from "./MeetingsView";
import { MoneyView } from "./MoneyView";

function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    return new Response(JSON.stringify(key ? routes[key] : { error: `no route ${url}` }), { status: key ? 200 : 404 });
  }));
}
afterEach(() => vi.unstubAllGlobals());

describe("DutiesView", () => {
  it("groups duties by cadence and opens a brief", async () => {
    mockFetch({
      "/api/duties?anchor=Money": { found: true, anchor: "Money", keepsStraight: "k", sections: "CIV 5500", artifact: "a", cadence: "monthly", when: "w", records: ["check_register"], produce: "budget_status, books_report", limit: "", passages: { "reserve use": [{ shelf: "law", file: "CIV 5500", passage: 1, score: 1, text: "The board shall review..." }] }, note: "n" },
      "/api/duties": { found: true, count: 2, duties: [
        { anchor: "Money", keepsStraight: "k", sections: "CIV 5500", artifact: "a", cadence: "monthly", when: "w", records: [], produce: "budget_status, books_report", limit: "" },
        { anchor: "Discipline", keepsStraight: "k2", sections: "CIV 5855", artifact: "a", cadence: "on the event", when: "w", records: [], produce: "hearings", limit: "Do not impose the penalty" },
      ] },
    });
    render(<DutiesView />);
    expect(await screen.findByRole("region", { name: "monthly" })).toHaveTextContent("Money");
    expect(screen.getByRole("region", { name: "on the event" })).toHaveTextContent("Do not impose the penalty");
    expect(screen.getAllByText("budget_status")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Money" }));
    expect(await screen.findByText("The board shall review...")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(await screen.findByRole("region", { name: "monthly" })).toBeInTheDocument();
  });
});

describe("CalendarView", () => {
  it("sorts overdue first and counts standings", async () => {
    mockFetch({ "/api/calendar": { asOf: "2026-10-03", caveats: ["A payment is evidence, not proof."], obligations: [
      { name: "Budget report", authority: "CIV 5300", rule: "yearly", note: "", standing: "upcoming", next: "2026-11-01", daysLeft: 29, lastDone: "2025-11-01", history: [] },
      { name: "Backflow test", authority: "city", rule: "yearly", note: "", standing: "overdue", next: "2026-09-01", daysLeft: -32, lastDone: null, history: [{ deadline: "2025-09-01", standing: "done late", daysLate: 10 }] },
    ] } });
    render(<CalendarView />);
    const rows = await screen.findAllByRole("row");
    expect(rows[1]).toHaveTextContent("Backflow test");
    expect(rows[1]).toHaveTextContent("2025-09-01: done late (10d late)");
    expect(screen.getByText("A payment is evidence, not proof.")).toBeInTheDocument();
  });
});

describe("MeetingsView", () => {
  it("marks missing minutes and filters to checks", async () => {
    mockFetch({ "/api/meetings": { found: true, meetings: [
      { date: "2026-09-10", titles: ["Board"], has: { agenda: { drive: 1 }, minutes: { payhoa: 1 } }, checks: [] },
      { date: "2026-08-10", titles: ["Board"], has: { agenda: { drive: 1 } }, checks: ["no minutes 30 days on (CIV 4950)"] },
    ], scheduleGaps: ["2026-07-10"], caveats: [] } });
    render(<MeetingsView />);
    expect(await screen.findAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("no minutes")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("only with checks"));
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("2026-07-10")).toBeInTheDocument();
  });
});

describe("MoneyView", () => {
  it("shows budget stats, then collections with its warning", async () => {
    mockFetch({
      "/api/budget": { found: true, year: 2026, yearToDate: { revenue: { budget: 100000, actual: 90000 }, expense: { budget: 80000, actual: 85000 }, net: { actual: 5000 } }, months: [], expenseGaps: [{ name: "Water", budgeted: 1000, actual: 3000, gap: 2000 }], revenueGaps: [], accounts: [{ label: "Operating", purpose: "operating", balance_cents: 123456 }], reserveTotalCents: 5000000, note: "PayHOA's figures as of the sync." },
      "/api/collections": { found: true, counts: { RELEASE_DUE: 1 }, pastDueCents: 0, rows: [{ apn: "1", address: "123 Main St #1", owners: [], standing: "RELEASE_DUE", meaning: "paid; release owed within 21 days", balanceCents: 0, pastDueCents: 0, lien: "2024-000001", lienStatus: "recorded", lienDays: 400, nextStep: "record the release (CIV 5685)" }] },
    });
    render(<MoneyView />);
    expect(await screen.findByText("$900.00")).toBeInTheDocument();
    expect(screen.getByText("Water")).toBeInTheDocument();
    expect(screen.getByText("$50,000.00")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Collections" }));
    expect(await screen.findByText("release due")).toBeInTheDocument();
    expect(screen.getByText(/never submits an account/)).toBeInTheDocument();
  });
});
