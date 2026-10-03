import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReserveFindingsView } from "./ReserveFindingsView";

afterEach(() => vi.unstubAllGlobals());

const move = { kind: "withdrawal", purpose: "borrowing", description: "", exactRepayment: false, repayments: [] };
const borrowings = [
  { ...move, day: "2025-03-01", cents: 1000000, account: "Reserve", number: "77", memo: "roof", deadline: "2026-03-01", repaidCents: 400000, outstandingCents: 600000, repaidOn: null,
    documents: { notice: { path: "a.pdf" }, minutes: null, resolution: null },
    gaps: ["no minutes in the library for the meeting that considered it (5515(c) finding)", "not restored within a year (due 2026-03-01); a delay needs a noticed finding (5515(d))"],
    key: "2025-03-01|77", finding: null, findingNeeded: true },
  { ...move, day: "2024-06-01", cents: 250000, account: "Reserve", number: "41", memo: "", deadline: "2025-06-01", repaidCents: 250000, outstandingCents: 0, repaidOn: "2024-09-01",
    documents: { notice: { path: "n.pdf" }, minutes: { path: "m.pdf", draft: false }, resolution: { path: "r.pdf" } }, gaps: [], key: "2024-06-01|41", findingNeeded: false,
    finding: { key: "2024-06-01|41", finding: "Needed for the pool pump; repaid from the July assessments.", kind: "finding at borrowing", authority: "CIV 5515(c)", madeOn: "2024-05-21", by: "Secretary", meeting: "2024-05-21", recorded: "2024-05-22T00:00:00+00:00", history: ["2024-05-22: recorded finding at borrowing by Secretary"] } },
];
const page = { found: true, ledgerThrough: "2026-09-30", kinds: ["finding at borrowing", "finding for a late restoration"], needed: 1, borrowings, budgetYears: [],
  caveats: ["A match by amount is a lead: only the board's resolution says which loan a payment restored."] };

describe("ReserveFindingsView", () => {
  it("flags the borrowing that needs a finding and records one through a confirm", async () => {
    const posts: [string, unknown][] = [];
    const text = "Restoration deferred to September 2026 while the roof is paid off; the delay is in the association's best interest.";
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posts.push([url, JSON.parse(String(init.body))]);
        return new Response(JSON.stringify({ key: "2025-03-01|77", finding: text, kind: "finding for a late restoration", authority: "CIV 5515(d)", madeOn: "2026-10-03", by: "Secretary", meeting: "2026-09-15", recorded: "2026-10-03T20:00:00+00:00", history: ["2026-10-03: recorded finding for a late restoration by Secretary"] }), { status: 200 });
      }
      return new Response(JSON.stringify(page), { status: 200 });
    }));
    render(<ReserveFindingsView />);
    expect(await screen.findByText("finding needed")).toBeInTheDocument();
    expect(screen.getByText("$10,000.00")).toBeInTheDocument();
    expect(screen.getByText("finding at borrowing")).toBeInTheDocument();
    expect(screen.getByText(/1 finding needed/)).toBeInTheDocument();
    expect(screen.getByText(/only the board's resolution/)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getAllByRole("button", { name: "Open" })[0]);  // newest first: the 2025 borrowing
    expect(screen.getByRole("list", { name: "timeline" })).toHaveTextContent("Restore by (one year)");
    expect(screen.getByText("No finding recorded here.")).toBeInTheDocument();
    expect(screen.getAllByText("✗")).toHaveLength(3);
    expect((screen.getByLabelText("Which finding") as HTMLSelectElement).value).toBe("finding for a late restoration");
    expect(screen.queryByRole("button", { name: "Record the finding" })).toBeNull();
    await user.type(screen.getByLabelText("Finding, as the minutes record it"), text);
    await user.type(screen.getByLabelText("Meeting that made it"), "2026-09-15");
    await user.clear(screen.getByLabelText("Made on"));
    await user.type(screen.getByLabelText("Made on"), "2026-10-03");
    await user.type(screen.getByLabelText("Recorded by"), "Secretary");
    await user.click(screen.getByRole("button", { name: "Record the finding" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Nothing in PayHOA changes");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0][0]).toBe("/api/write/reserve-findings/2025-03-01%7C77");
    expect(posts[0][1]).toEqual({ finding: text, kind: "finding for a late restoration", madeOn: "2026-10-03", by: "Secretary", meeting: "2026-09-15" });
    expect(await screen.findByText(/recorded 2026-10-03 by Secretary/)).toBeInTheDocument();
    expect(screen.queryByText("finding needed")).toBeNull();
    expect(screen.getAllByText("finding for a late restoration").length).toBeGreaterThan(0);
  });

  it("shows a recorded finding in the board's words when opened", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(page), { status: 200 })));
    render(<ReserveFindingsView />);
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[1]);
    expect(screen.getByText("Needed for the pool pump; repaid from the July assessments.", { selector: "blockquote" })).toBeInTheDocument();
    expect(screen.getByLabelText("Finding, as the minutes record it")).toHaveValue("Needed for the pool pump; repaid from the July assessments.");
    expect(screen.getByText(/Made 2024-05-21; recorded 2024-05-22 by Secretary/)).toBeInTheDocument();
    expect(screen.getByText("the record is complete")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record the finding" })).toBeNull();
  });
});
