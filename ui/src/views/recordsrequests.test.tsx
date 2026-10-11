import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RecordsRequestsView } from "./RecordsRequestsView";

afterEach(() => vi.unstubAllGlobals());

const kinds = [
  { record: "membership_list", label: "Membership list", citation: "CIV 5200(a)(9)", meaning: "", retention: "", files: null, gap: "" },
  { record: "minutes", label: "Minutes of member, board, and committee meetings", citation: "CIV 5200(a)(8)", meaning: "what the board did", retention: "", files: 3, gap: "" },
];
const caveats = ["The manager decides, with counsel where needed. jason records those decisions; it makes none.", "jason prepares the membership list. It does not hand the list to anyone."];
const existing = {
  id: "2026-09-01--unit-7", receivedOn: "2026-09-01", unit: "Unit 7", via: "mail", records: ["minutes"], purpose: "to see what the board did about the roof", membershipList: false, years: [],
  decisions: { purposeAdequate: null, withheld: [], producedOn: "", inspectedOrCopies: "", feeCents: 0, note: "" }, by: "", recorded: "2026-09-01T10:00:00+00:00", updated: "2026-09-01T10:00:00+00:00",
  history: ["2026-09-01: received via mail"], dueBy: "2026-09-15", standing: "overdue", citations: { minutes: "CIV 5200(a)(8)" },
  stages: [{ key: "received", label: "Request received", date: "2026-09-01", done: true }, { key: "currentYear", label: "Current fiscal year records produced by", date: "2026-09-15", authority: "CIV 5210(b)(1)" }],
};
const opened = {
  ...existing, id: "2026-10-02--unit-12", receivedOn: "2026-10-02", unit: "Unit 12", via: "email", records: ["membership_list", "minutes"], purpose: "to contact owners about the roof vote", membershipList: true,
  history: ["2026-10-02: received via email"], dueBy: "2026-10-09", standing: "open", citations: { membership_list: "CIV 5200(a)(9)", minutes: "CIV 5200(a)(8)" },
  stages: [{ key: "received", label: "Request received", date: "2026-10-02", done: true }, { key: "membershipList", label: "Membership list: jason's computed date, for a person to check", date: "2026-10-09", authority: "CIV 5210(b)(6), CORP 8330", who: "counsel reads the statute" }, { key: "currentYear", label: "Current fiscal year records produced by", date: "2026-10-16", authority: "CIV 5210(b)(1)" }],
};

const G = "(g) In addition to the direct and actual costs of copying and mailing, the association may bill the requesting member an amount not in excess of ten dollars ($10) per hour, and not to exceed two hundred dollars ($200) total per written request, for the time actually and reasonably involved in redacting an enhanced association record.";
const F = "(f) The association may bill the requesting member for the direct and actual cost of copying and mailing requested documents.";
const L = "(6) Membership list, within the timeframe specified in Section 8330 of the Corporations Code.";
const words = (citation: string, text: string) => ({ citation, text, found: true, inForce: "the 2025 publication of the code" });
const rule = {
  fee: { words: [words("CIV 5205(f)", F), words("CIV 5205(g)", G), words("CIV 5200(b)", "(b) Enhanced association records means invoices.")], capCents: 20000, hourlyCents: 1000, reading: "jason's reading, not the statute's: 5205(g) bounds only the redaction charge." },
  membershipList: { words: [words("CIV 5210(b)(6)", L), words("CORP 8330", "8330. A member may inspect and copy the record of all the members.")], reading: "jason's reading, not the statute's: the date on the clock is jason's count, computed for a person to check." },
};
const withFee = { ...existing, decisions: { ...existing.decisions, feeCents: 5000, redactionCents: 5000, redactionMinutes: 0 },
  feeCheck: { status: "warning", needsCounsel: true, findings: [{ code: "no-time", sentence: "A redaction charge is recorded with no time, so the hourly rate in CIV 5205(g) cannot be checked." }], capCents: 20000, hourlyCents: 1000, words: [], reading: "jason's reading, not the statute's: counsel reads the statute." } };

function stub(posts: unknown[], requests: unknown[] = [existing], fail = "") {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      posts.push([url, body]);
      if (fail && !url.endsWith("/new")) return new Response(JSON.stringify({ error: fail }), { status: 400 });
      if (url.endsWith("/new")) return new Response(JSON.stringify(opened), { status: 200 });
      return new Response(JSON.stringify({ ...opened, by: body.by, updated: "2026-10-05T10:00:00+00:00", standing: body.producedOn ? "produced" : "open", history: [...opened.history, "2026-10-05: purpose (undecided) -> adequate (CIV 5225)"],
        decisions: { ...opened.decisions, ...body } }), { status: 200 });
    }
    return new Response(JSON.stringify({ found: true, count: 1, counts: { overdue: 1 }, requests, kinds, vias: ["email", "mail", "form"], note: "", caveats, rule }), { status: 200 });
  }));
}

describe("RecordsRequestsView", () => {
  it("lists the requests with their standing, caveats, and the member's purpose as given", async () => {
    stub([]);
    render(<RecordsRequestsView />);
    expect(await screen.findByText("Records requests (1)")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Caveats" })).toHaveTextContent("does not hand the list");
    expect(screen.getByText("overdue")).toBeInTheDocument();
    expect(screen.getByText("Unit 7")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByRole("list", { name: "timeline" })).toHaveTextContent("Current fiscal year records produced by");
    expect(screen.getByText("to see what the board did about the roof")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Purpose adequate/)).toBeNull(); // no list asked: no 5225 question
  });

  it("opens a request through a confirm, posting to the new key", async () => {
    const posts: unknown[] = [];
    stub(posts);
    render(<RecordsRequestsView />);
    await screen.findByText("Records requests (1)");
    const user = userEvent.setup();
    const form = screen.getByText("Receive a request").closest("section") as HTMLElement;
    await user.clear(within(form).getByLabelText("Received on"));
    await user.type(within(form).getByLabelText("Received on"), "2026-10-02");
    await user.type(within(form).getByLabelText("Unit"), "Unit 12");
    await user.click(within(form).getByLabelText(/^Membership list/));
    await user.click(within(form).getByLabelText(/^Minutes of member/));
    await user.type(within(form).getByLabelText("Purpose, as the member stated it"), "to contact owners about the roof vote");
    await user.type(within(form).getByLabelText("Received by"), "Manager");
    await user.click(screen.getByRole("button", { name: "Open the request" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("including the membership list");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/write/records-requests/new");
    expect((posts[0] as unknown[])[1]).toEqual({ receivedOn: "2026-10-02", unit: "Unit 12", via: "email", records: ["membership_list", "minutes"], purpose: "to contact owners about the roof vote", years: [], by: "Manager" });
    expect(await screen.findByText("Records requests (2)")).toBeInTheDocument();
    expect(screen.getByText("The request from Unit 12")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "timeline" })).toHaveTextContent("Membership list: jason's computed date, for a person to check");
  });

  it("records the decisions through a confirm: adequacy under 5225, a withheld record with its basis, production", async () => {
    const posts: unknown[] = [];
    stub(posts);
    render(<RecordsRequestsView />);
    await screen.findByText("Records requests (1)");
    const user = userEvent.setup();
    // Open the list request first, so the 5225 question is on the panel.
    const form = screen.getByText("Receive a request").closest("section") as HTMLElement;
    await user.type(within(form).getByLabelText("Unit"), "Unit 12");
    await user.click(within(form).getByLabelText(/^Membership list/));
    await user.click(within(form).getByLabelText(/^Minutes of member/));
    await user.click(screen.getByRole("button", { name: "Open the request" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await screen.findByText("The request from Unit 12");
    await user.selectOptions(screen.getByLabelText(/Purpose adequate for the membership list/), "yes");
    await user.click(screen.getByRole("button", { name: "Withhold a record" }));
    expect(screen.queryByRole("button", { name: "Record the decisions" })).toBeNull(); // the basis is still blank
    expect(screen.getByText(/Each withheld record needs the basis stated/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Withheld record 1"), "minutes");
    await user.type(screen.getByLabelText("Withheld reason 1"), "executive session minutes, CIV 4935");
    await user.type(screen.getByLabelText("Produced on"), "2026-10-08");
    await user.selectOptions(screen.getByLabelText(/Inspection or copies/), "copies");
    await user.clear(screen.getByLabelText(/Fee the member agreed to/));
    await user.type(screen.getByLabelText(/Fee the member agreed to/), "12.50");
    await user.type(screen.getByLabelText("Decided by"), "Manager");
    await user.click(screen.getByRole("button", { name: "Record the decisions" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("purpose adequate under 5225; 1 record kind(s) withheld under 5215; produced 2026-10-08; by copies; fee $12.50");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(2));
    expect((posts[1] as unknown[])[0]).toBe("/api/write/records-requests/2026-10-02--unit-12");
    expect((posts[1] as unknown[])[1]).toEqual({ by: "Manager", purposeAdequate: true, withheld: [{ record: "minutes", reason: "executive session minutes, CIV 4935" }], producedOn: "2026-10-08", inspectedOrCopies: "copies", feeCents: 1250 });
    expect(await screen.findByText(/Produced 2026-10-08 by copies, fee \$12\.50/)).toBeInTheDocument();
    expect(screen.getAllByText("produced").length).toBeGreaterThan(0);
  });

  it("recites 5205(f) and (g) beside the fee fields, with jason's reading labeled, and lowers nothing", async () => {
    stub([]);
    render(<RecordsRequestsView />);
    await screen.findByText("Records requests (1)");
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const panel = screen.getByText("What Civil Code 5205 says about the cost").closest("details") as HTMLElement;
    expect(panel).toHaveTextContent(G);
    expect(panel).toHaveTextContent(F);
    expect(panel).not.toHaveTextContent("Enhanced association records means");      // 5200(b) is the statute's definition, not recited here
    expect(within(panel).getByLabelText("jason's reading")).toHaveTextContent("jason's reading, not the statute's");
    expect(screen.queryByRole("button", { name: /lower|reduce|cap/i })).toBeNull();
  });

  it("warns before saving when the redaction figure is above the stated total, and shows the server's refusal with the statute's words", async () => {
    const posts: unknown[] = [];
    stub(posts, [existing], `The redaction charge, $250.00, is more than the $200.00 total the stored CIV 5205(g) states per written request. CIV 5205(g) reads: "${G}"`);
    render(<RecordsRequestsView />);
    await screen.findByText("Records requests (1)");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.clear(screen.getByLabelText(/Fee the member agreed to/));
    await user.type(screen.getByLabelText(/Fee the member agreed to/), "250");
    await user.clear(screen.getByLabelText(/Of it, redacting an enhanced record/));
    await user.type(screen.getByLabelText(/Of it, redacting an enhanced record/), "250");
    await user.clear(screen.getByLabelText(/Time spent redacting/));
    await user.type(screen.getByLabelText(/Time spent redacting/), "25");
    expect(screen.getByRole("alert")).toHaveTextContent("The redaction figure, $250.00, is above the $200.00 total");
    await user.type(screen.getByLabelText("Decided by"), "Manager");
    await user.click(screen.getByRole("button", { name: "Record the decisions" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[1]).toEqual({ by: "Manager", feeCents: 25000, redactionCents: 25000, redactionMinutes: 1500 });
    expect(await screen.findByText(/CIV 5205\(g\) reads:/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Fee the member agreed to/)).toHaveValue("250");        // the figure is the person's still
  });

  it("shows a saved fee's warning for counsel, labeled as jason's reading", async () => {
    stub([], [withFee]);
    render(<RecordsRequestsView />);
    await screen.findByText("Records requests (1)");
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("Counsel reads this fee");
    expect(note).toHaveTextContent("so the hourly rate in CIV 5205(g) cannot be checked");
    expect(note).toHaveTextContent("jason's reading");
  });

  it("recites 5210(b)(6) and the law it points to beside the membership list's date, labeled as jason's count", async () => {
    stub([], [{ ...opened, decisions: opened.decisions }]);
    render(<RecordsRequestsView />);
    await screen.findByText("Records requests (1)");
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const card = screen.getByText("The membership list's timeframe").closest("section") as HTMLElement;
    expect(card).toHaveTextContent(L);
    expect(card).toHaveTextContent("8330. A member may inspect and copy");
    expect(card).toHaveTextContent("computed for a person to check");
    expect(screen.getByRole("list", { name: "timeline" })).toHaveTextContent("counsel reads the statute");
    expect(screen.queryByText("Membership list produced by")).toBeNull();
  });
});
