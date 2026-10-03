import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OwnerPageView } from "./OwnerPageView";
import { RecordsRequestsView } from "./RecordsRequestsView";

const profile = {
  found: true, slug: "sample-commons", name: "Sample Commons Owners Association", corporateName: "SAMPLE COMMONS OWNERS ASSOCIATION", wordmark: "Sample Commons",
  site: "https://sample.example", pages: [{ page: "home", label: "Home", path: "/", url: "https://sample.example/" }, { page: "records", label: "Records", path: "/records", url: "https://sample.example/records" }],
  mailing: [{ kind: "current mailing address", label: "PO Box 1, Anytown", zip: "90000" }],
  contacts: [{ label: "HOA", purpose: "the association's general inbox", kind: "general", email: "hoa@sample.example" }],
  calendarId: "cal-1@group.calendar.google.com", timeZone: "America/Los_Angeles",
  records: { kinds: [{ record: "minutes", citation: "CIV 5200(a)(8)", meaning: "Minutes", onFile: true }, { record: "tax_return", citation: "CIV 5200(a)(6)", meaning: "Tax returns", onFile: false }], onFile: 1, total: 2, note: "" },
  asOf: "2026-10-03", caveats: ["A record on file is pinned, not reviewed."],
};

function stub(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })));
}
afterEach(() => vi.unstubAllGlobals());

describe("OwnerPageView", () => {
  it("shows what the loader gives, under data-reach=full, with the calendar embedded", async () => {
    stub(profile);
    render(<OwnerPageView />);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Sample Commons");
    const root = screen.getByRole("heading", { level: 1 }).closest("[data-reach]");
    expect(root).toHaveAttribute("data-reach", "full");
    expect(screen.getByRole("navigation", { name: "Site" })).toHaveTextContent("Records");
    expect(screen.getByText("PO Box 1, Anytown 90000")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "hoa@sample.example" })).toHaveAttribute("href", "mailto:hoa@sample.example");
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    expect(screen.getByText("on file")).toBeInTheDocument();
    expect(screen.getByText("not on file")).toBeInTheDocument();
    expect(screen.getByTitle("Sample Commons Owners Association calendar")).toHaveAttribute("src", expect.stringContaining("cal-1%40group.calendar.google.com"));
    expect(screen.getByRole("complementary", { name: "Caveats" })).toHaveTextContent("pinned, not reviewed");
  });

  it("shows nothing for what the profile leaves empty", async () => {
    stub({ ...profile, pages: [], mailing: [], contacts: [], calendarId: "", site: "", records: { kinds: [], onFile: 0, total: 0, note: "records inventory unavailable" } });
    render(<OwnerPageView />);
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("navigation", { name: "Site" })).toBeNull();
    expect(screen.queryByText("Reach the association")).toBeNull();
    expect(screen.queryByText("Write to the association")).toBeNull();
    expect(screen.queryByText("Calendar")).toBeNull();
    expect(screen.getByText("records inventory unavailable")).toBeInTheDocument();
  });
});

describe("RecordsRequestsView for owners", () => {
  it("shows the request form and the record kinds, never other members' requests", async () => {
    stub({ found: true, count: 1, counts: { open: 1 }, kinds: [{ record: "minutes", label: "Minutes", citation: "CIV 5200(a)(8)", meaning: "", retention: "", files: 3, gap: "" }], vias: ["email"], note: "", caveats: ["board caveat"],
      requests: [{ id: "r1", receivedOn: "2026-09-24", unit: "Unit 31", via: "email", records: ["minutes"], purpose: "", membershipList: false, years: [], decisions: { purposeAdequate: null, withheld: [], producedOn: "", inspectedOrCopies: "", feeCents: 0, note: "" }, by: "", recorded: "", updated: "", history: [], stages: [], dueBy: "2026-10-08", standing: "open", citations: {} }] });
    render(<RecordsRequestsView audience="owner" />);
    expect(await screen.findByText("Request a record")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
    expect(screen.getByText("3 on file")).toBeInTheDocument();
    expect(screen.queryByText("Unit 31")).toBeNull();
    expect(screen.queryByText(/Records requests \(/)).toBeNull();
    expect(screen.queryByText("Receive a request")).toBeNull();
  });
});
