import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LegalView } from "./LegalView";

function mockFetch(routes: Record<string, unknown>) {
  const f = vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    return new Response(JSON.stringify(key ? routes[key] : { error: `no route ${url}` }), { status: key ? 200 : 404 });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
afterEach(() => vi.unstubAllGlobals());

const routes = {
  "/api/legal-cases": {
    found: true,
    caveats: ["Confidential: for directors and counsel.", "A duty 'not shown' may be met in records jason does not hold."],
    openDuties: [
      { case: "defect", statute: "CIV 6100(a)", requirement: "disclose the settlement to members", met: null },
      { case: "defect", statute: "CIV 6150", requirement: "notice before filing suit", met: false },
    ],
    cases: [{
      key: "defect", title: "Construction defect claim", forum: "SB 800 prelitigation (Civil Code 895-945.5)", role: "claimant", status: "settled",
      court: "Superior Court of Example County", case_number: "24CV000123", opposing: ["Example Builders LLC"], counsel: ["Example Law LLP"],
      insurer_claims: [], buildings: [1, 2],
      events: [{ day: "2024-01-15", step: "notice of claim served", source: "Drive: Legal/notice.pdf" }, { day: "2025-06-01", step: "settlement signed", source: "" }],
      gross_cents: 50000000, fees_cents: 15000000, net_cents: 35000000, proceeds_account: "Reserve",
      duties: [
        { statute: "CIV 6100(a)", requirement: "disclose the settlement to members", met: null, due: "2025-08-01", applies: true },
        { statute: "CIV 6150", requirement: "notice before filing suit", met: false, applies: true },
        { statute: "CIV 5986", requirement: "member vote before suit", met: null, applies: false },
      ],
      board_item: "bi-7", confidential: true, settled_items: [],
    }],
  },
  "/api/audit-chains": {
    checked: 2, clean: 1, restorationYears: [2013],
    parcels: [
      { apn: "123-0010-001", phase: 1, steps: 3, reassessing: { "2016": "2016-0001" }, findings: [] },
      { apn: "123-0010-002", phase: 2, steps: 4, reassessing: {}, findings: [
        { check: "price near base", detail: "the declared price is far from the base the next bill enrolled", number: "2019-0456", year: 2019 },
      ] },
    ],
  },
};

describe("LegalView", () => {
  it("shows the confidential notice, open duties with a not-shown pill, and hides a duty that does not apply", async () => {
    mockFetch(routes);
    render(<LegalView />);
    expect(await screen.findByText("Construction defect claim")).toBeInTheDocument();
    expect(screen.getByText(/CONFIDENTIAL/)).toBeInTheDocument();
    expect(screen.getByText(/4935\(a\)/)).toBeInTheDocument();
    // open duties table: met=null → "not shown", met=false → "not met"; the case card repeats both
    expect(screen.getAllByText("not shown")).toHaveLength(2);
    expect(screen.getAllByText("not met")).toHaveLength(2);
    expect(screen.queryByText("met")).not.toBeInTheDocument();
    // applies=false stays out of the card's duties table
    expect(screen.queryByText("CIV 5986")).not.toBeInTheDocument();
    expect(screen.queryByText("member vote before suit")).not.toBeInTheDocument();
    expect(screen.getByText("settled")).toBeInTheDocument();
    expect(screen.getByText("24CV000123")).toBeInTheDocument();
    expect(screen.getByText("$500,000.00")).toBeInTheDocument();
    expect(screen.getByText("$350,000.00")).toBeInTheDocument();
    expect(screen.getByText("notice of claim served")).toBeInTheDocument();
    expect(screen.getByText("Drive: Legal/notice.pdf")).toBeInTheDocument();
    expect(screen.getByText("Confidential: for directors and counsel.")).toBeInTheDocument();
  });

  it("tabs to deed chains with stats and expandable findings", async () => {
    mockFetch(routes);
    render(<LegalView />);
    await screen.findByText("Construction defect claim");
    await userEvent.click(screen.getByRole("tab", { name: "Deed chains" }));
    expect(await screen.findByText("123-0010-002")).toBeInTheDocument();
    expect(screen.getByText("Chains checked")).toBeInTheDocument();
    expect(screen.getByText("1 with findings")).toBeInTheDocument();
    expect(screen.getByText("2013")).toBeInTheDocument();
    expect(screen.getByText("clean")).toBeInTheDocument();
    expect(screen.getByText(/a lead, not a determination/)).toBeInTheDocument();
    const details = screen.getByText("1 finding").closest("details")!;
    expect(details.open).toBe(false);
    await userEvent.click(screen.getByText("1 finding"));
    expect(details.open).toBe(true);
    expect(within(details).getByText("price near base")).toBeInTheDocument();
    expect(within(details).getByText(/far from the base/)).toBeInTheDocument();
    expect(within(details).getByText("2019-0456")).toBeInTheDocument();
    expect(within(details).getByText("2019")).toBeInTheDocument();
  });
});
