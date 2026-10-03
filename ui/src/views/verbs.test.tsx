import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BorrowingCard } from "./ReservesView";
import { HearingsView } from "./HearingsView";
import { InboxView } from "./InboxView";
import { TitleWatchView } from "./TitleWatchView";

function mockFetch(routes: Record<string, unknown>) {
  const f = vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    return new Response(JSON.stringify(key ? routes[key] : { error: `no route ${url}` }), { status: key ? 200 : 404 });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
afterEach(() => vi.unstubAllGlobals());

describe("BorrowingCard", () => {
  it("ticks the 5515 record and lists gaps", () => {
    render(<BorrowingCard b={{
      day: "2025-03-01", cents: 1000000, account: "Reserve", kind: "withdrawal", purpose: "borrowing", number: "77", memo: "roof", description: "",
      deadline: "2026-03-01", repaidCents: 400000, outstandingCents: 600000, repaidOn: null, exactRepayment: false, repayments: [],
      documents: { notice: { path: "a.pdf" }, minutes: { path: "m.pdf", draft: true }, resolution: null },
      gaps: ["the library holds only DRAFT minutes of that meeting", "no resolution in the library authorizes it"],
    }} />);
    expect(screen.getByText("$10,000.00")).toBeInTheDocument();
    expect(screen.getByText("outstanding")).toBeInTheDocument();
    expect(screen.getByText(/DRAFT only/)).toBeInTheDocument();
    expect(screen.getAllByText("✗")).toHaveLength(3);
    expect(screen.getAllByText("✓")).toHaveLength(1);
    expect(screen.getByText(/no resolution/)).toBeInTheDocument();
  });
});

describe("TitleWatchView", () => {
  it("asks for attention rows by default and shows the namesake flag", async () => {
    const f = mockFetch({ "/api/title-watch": { found: true, counts: { STANDS: 1 }, note: "what the index shows, not a title report", rows: [
      { apn: "1", address: "123 Main St #1", building: 1, owner: "J Doe", currentOwners: [], process: "assessment lien", number: "2024-1", recorded: "2024-01-01", claimant: ["the association"], status: "recorded", standing: "STANDS", meaning: "stands against the current owner", presumedPaidAt: "", namesakeRisk: true, enforceableUntil: "", sharedWith: [], latestStep: "2024-01-01" },
    ] } });
    render(<TitleWatchView />);
    expect(await screen.findByText("namesake?")).toBeInTheDocument();
    expect(String(f.mock.calls[0][0])).toContain("attention=true");
    expect(screen.getByText("what the index shows, not a title report")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("attention only"));
    expect(String(f.mock.calls.at(-1)![0])).toContain("attention=false");
  });
});

describe("HearingsView", () => {
  it("shows delivered notice and the decision clock", async () => {
    mockFetch({ "/api/hearings": { found: true, hearings: [
      { address: "123 Main St #2", start: "2026-10-20T18:00:00", noticeBy: "2026-10-10", noticeOn: "2026-10-05", decisionByIfHeld: "2026-11-03", standing: "notice by 2026-10-10 (delivered 2026-10-05)", scheduled: true, problems: [] },
    ] } });
    render(<HearingsView />);
    expect(await screen.findByText("delivered 2026-10-05")).toBeInTheDocument();
    expect(screen.getByText("zoom")).toBeInTheDocument();
    expect(screen.getByText(/never decides discipline/)).toBeInTheDocument();
  });
});

describe("InboxView", () => {
  it("tabs through the sections with counts", async () => {
    mockFetch({ "/api/open-items": { found: true, counts: { threads: 1, letters: 1 }, caveats: ["jason answers nothing."],
      threadsAwaitingUs: [{ last: "2026-10-01", ageDays: 2, who: "vendor", subject: "Invoice 42", topics: ["invoice"], likelyNeedsResponse: true, replyRate: 0.8 }],
      requestsPending: [], deadlines: [], insurance: [], mailNotScanned: [],
      lettersToAct: [{ received: "2026-09-30", from: "county", kind: "tax", deadlines: ["2026-12-10"] }], lienNotices: [] } });
    render(<InboxView />);
    expect(await screen.findByText("Invoice 42")).toBeInTheDocument();
    expect(screen.getByText("80% replied before")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Letters to act on (1)" }));
    expect(screen.getByText("2026-12-10")).toBeInTheDocument();
    expect(screen.getByText("jason answers nothing.")).toBeInTheDocument();
  });
});
