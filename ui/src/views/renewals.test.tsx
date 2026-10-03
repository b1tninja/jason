import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InsuranceRenewalsView } from "./InsuranceRenewalsView";

afterEach(() => vi.unstubAllGlobals());

const base = { priorNumbers: [], program: "", agent: "Agent", terms: [], nextTermPayments: [], letters: [], notices: [], findings: [] };
const policies = [
  { ...base, kind: "property", building: null, number: "P-1", carrier: "Acme", standing: "in term", termEnd: "2026-12-01", key: "P-1", renewal: null, daysToTermEnd: 59, renewalWindow: true, memberNoticeNeeded: false },
  { ...base, kind: "flood", building: 5, number: "F-5", carrier: "NFIP", standing: "in term", termEnd: "2027-06-01", key: "F-5", daysToTermEnd: 241, renewalWindow: false, memberNoticeNeeded: true,
    renewal: { number: "F-5", decision: "renew with changes", decidedOn: "2026-09-15", by: "Treasurer", premiumCents: 123456, limitsChanged: true, memberNoticeNeeded: true, noticeAuthority: "CIV 5810", note: "", recorded: "2026-09-16T00:00:00+00:00", history: ["2026-09-16: recorded renew with changes by Treasurer"] } },
];
const page = { found: true, asOf: "2026-10-03", today: "2026-10-03", windowDays: 90, decisions: ["renew as quoted", "renew with changes", "re-bid", "change carrier", "let lapse"], policies,
  caveats: ["The renewal is the board's decision with its agent: jason buys, renews, cancels, and claims nothing."] };

describe("InsuranceRenewalsView", () => {
  it("shows each policy with its decision or the window flag, and records a decision through a confirm", async () => {
    const posts: [string, unknown][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posts.push([url, JSON.parse(String(init.body))]);
        return new Response(JSON.stringify({ number: "P-1", decision: "re-bid", decidedOn: "2026-10-20", by: "Secretary", premiumCents: 612000, limitsChanged: false, memberNoticeNeeded: false, noticeAuthority: "", note: "two more quotes", recorded: "2026-10-20T20:00:00+00:00", history: ["2026-10-20: recorded re-bid by Secretary"] }), { status: 200 });
      }
      return new Response(JSON.stringify(page), { status: 200 });
    }));
    render(<InsuranceRenewalsView />);
    expect(await screen.findByText("renewal window")).toBeInTheDocument();
    expect(screen.getByText("decision needed")).toBeInTheDocument();
    expect(screen.getByText("renew with changes")).toBeInTheDocument();
    expect(screen.getByText("notice needed (5810)")).toBeInTheDocument();
    expect(screen.getByText("$1,234.56")).toBeInTheDocument();
    expect(screen.getByText(/1 in the 90-day window without a decision/)).toBeInTheDocument();
    expect(screen.getByText(/claims nothing/)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getAllByRole("button", { name: "Open" })[0]);
    expect(screen.getByRole("list", { name: "timeline" })).toHaveTextContent("Term in force ends");
    expect(screen.getByText("No decision recorded for this policy.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record the decision" })).toBeNull();
    await user.selectOptions(screen.getByLabelText("Decision"), "re-bid");
    await user.clear(screen.getByLabelText("Decided on"));
    await user.type(screen.getByLabelText("Decided on"), "2026-10-20");
    await user.type(screen.getByLabelText(/Premium quoted/), "6120.00");
    await user.type(screen.getByLabelText("Recorded by"), "Secretary");
    await user.type(screen.getByLabelText("Note"), "two more quotes");
    await user.click(screen.getByRole("button", { name: "Record the decision" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Nothing is bought or sent");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0][0]).toBe("/api/write/insurance-renewals/P-1");
    expect(posts[0][1]).toEqual({ decision: "re-bid", decidedOn: "2026-10-20", by: "Secretary", premiumCents: 612000, limitsChanged: false, note: "two more quotes" });
    expect(await screen.findByText(/Recorded 2026-10-20 by Secretary/)).toBeInTheDocument();
    expect(screen.getAllByText("re-bid").length).toBeGreaterThan(0);
    expect(screen.queryByText("decision needed")).toBeNull();
  });

  it("shows a recorded decision's 5810 flag when opened and leaves the policy's number in the URL", async () => {
    const posts: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push(url); return new Response(JSON.stringify({ ...policies[1].renewal, decision: "let lapse", decidedOn: "2026-10-01", history: [] }), { status: 200 }); }
      return new Response(JSON.stringify(page), { status: 200 });
    }));
    render(<InsuranceRenewalsView />);
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[1]);
    expect(screen.getByText(/Individual notice to the members is needed/)).toBeInTheDocument();
    expect(screen.getByText(/Recorded 2026-09-16 by Treasurer/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record the decision" })).toBeNull();
    await user.selectOptions(screen.getByLabelText("Decision"), "let lapse");
    await user.click(screen.getByRole("button", { name: "Record the decision" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toEqual(["/api/write/insurance-renewals/F-5"]));
  });
});
