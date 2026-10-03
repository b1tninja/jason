import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommunitiesView, OnboardingView } from "./OnboardingView";

afterEach(() => vi.unstubAllGlobals());

const summary = { factsSupplied: 40, factsTotal: 66, accountsSet: 3, accountsTotal: 7, recordsHeld: 9, recordsTotal: 15, deliveriesFound: 6, deliveriesTotal: 18, requests: { asked: 2, received: 1, gap: 1 }, gaps: 6 };
const item = (key: string, title: string, status = "not asked", extra: Record<string, unknown> = {}) => ({ key, group: "financial", title, authority: "CIV 5300", holders: ["the treasurer or CPA"], record: "financial_disclosure", delivery: "", kinds: ["budget"], why: "", status, askedOf: "", askedOn: "", chasedOn: "", receivedOn: "", filed: "", reason: "", note: "", history: [], storeSays: "", ...extra });

describe("OnboardingView", () => {
  it("shows progress, the request list with the stores' reading, marks an item, and builds the letter", async () => {
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify({ key: "budget", status: "asked", asked_of: "the prior manager", asked_on: "2026-10-03", chased_on: "", received_on: "", filed: "", reason: "", note: "", history: ["2026-10-03: not asked -> asked"] }), { status: 200 }); }
      if (url.startsWith("/api/library")) return new Response(JSON.stringify({ found: true, count: 1, heldBackConfidential: 0, rows: [{ id: "lib-77", path: "Financials/Budget 2027.pdf", kind: "budget", records: ["financial_disclosure"], period: "2027", method: "NAME_RULE", evidence: "", confidential: false }] }), { status: 200 });
      if (url.startsWith("/api/request-letter")) return new Response(JSON.stringify({ found: true, count: 1, markdown: "# Records and information requested for The Association\n\n## Financial\n\n- **The current and prior year's budgets** (CIV 5300)." }), { status: 200 });
      return new Response(JSON.stringify({ found: true, summary, accounts: [{ service: "PayHOA", set: true, how: "jason login" }, { service: "Google", set: false, how: "docs/setup.md" }],
        facts: [{ duty: "money", facts: [{ name: "bank_accounts", supplied: true }, { name: "obligations", supplied: false }] }],
        items: [item("budget", "The current and prior year's budgets"), item("reserve-study", "The reserve study", "gap", { askedOn: "2026-09-01", storeSays: "the inventory shows a gap for this record" })],
        gaps: ["tax_return: nothing pinned"], statuses: ["not asked", "asked", "received", "pinned", "gap", "not applicable"], holders: ["the board", "the prior manager"], groups: ["financial"], caveats: ["The request list is sent by a person."] }), { status: 200 });
    }));
    render(<OnboardingView />);
    expect(await screen.findByText("3 of 7")).toBeInTheDocument();
    expect(screen.getByText("the inventory shows a gap for this record")).toBeInTheDocument();
    const user = userEvent.setup();
    const row = screen.getByText("The current and prior year's budgets").closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "mark" }));
    await user.selectOptions(within(row).getByLabelText("Status"), "asked");
    await user.type(within(row).getByLabelText("Asked of"), "the prior manager");
    await user.click(await within(row).findByRole("button", { name: "Financials/Budget 2027.pdf" }));
    expect(within(row).getByLabelText("Filed where")).toHaveValue("Financials/Budget 2027.pdf (library lib-77)");
    expect(within(row).getByLabelText("Status")).toHaveValue("received");
    await user.selectOptions(within(row).getByLabelText("Status"), "asked");
    await user.click(within(row).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/onboarding/budget");
    expect(((posts[0] as unknown[])[1] as { status: string }).status).toBe("asked");
    expect(await within(row).findByText("asked")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "The letter" }));
    expect(await screen.findByRole("heading", { level: 1, name: /Records and information requested/ })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Gaps/ }));
    expect(screen.getByText(/The reserve study: asked 2026-09-01, not received/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Facts" }));
    expect(screen.getByText("obligations")).toBeInTheDocument();
  });
});

describe("CommunitiesView", () => {
  it("lists profiles with the active one's progress", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ found: true, count: 2, communities: [{ name: "mystique", where: "/x/mystique", active: true, progress: summary }, { name: "sample", where: "/x/profiles/sample", active: false }] }), { status: 200 })));
    render(<CommunitiesView />);
    expect(await screen.findByText("mystique")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("9 of 15")).toBeInTheDocument();
    expect(screen.getByText("JASON_PROFILE=sample")).toBeInTheDocument();
  });
});
