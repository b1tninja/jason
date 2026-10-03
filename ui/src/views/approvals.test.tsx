import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApprovalsView } from "./ApprovalsView";

const people = [
  { name: "Quill Ashgrove", role: "president", approves: ["the president"], canApproveBoard: true },
  { name: "Ilse Varnholt", role: "treasurer", approves: ["the treasurer"], canApproveBoard: false },
];
const letter = {
  key: "Drive/Finance/vendor.docx", kind: "Vendor inquiry", title: "Request for an itemized invoice", date: "2026-10-03", to: "Billing, Gate Co.", via: "Email",
  body: ["Please send an itemized invoice."], signoff: "The Treasurer", approver: "the treasurer", stage: "requested", sentCommand: "jason letter vendor-inquiry --yes",
  log: [{ id: "1", date: "2026-10-01", title: "Approval requested from the treasurer", by: "Pell Marchbanks" }],
};

afterEach(() => { vi.unstubAllGlobals(); try { localStorage.clear(); } catch { /* none */ } });

describe("ApprovalsView", () => {
  it("lists the inbox, opens a letter, and posts the signed-in person's step", async () => {
    const posted: { url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posted.push({ url, body: JSON.parse(String(init.body)) }); return new Response(JSON.stringify({ ...letter, stage: "approved" }), { status: 200 }); }
      return new Response(JSON.stringify({ found: true, letters: [letter], groups: { requested: [letter.key], approved: [], sent: [], drafts: [] }, pending: 1, people, stages: [], caveats: ["jason drafts and records; it decides nothing."] }), { status: 200 });
    }));
    const user = userEvent.setup();
    render(<ApprovalsView />);
    expect(await screen.findByText("jason drafts and records; it decides nothing.")).toBeInTheDocument();
    expect(screen.getByText("Only the treasurer can approve")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Signed in as"), "Ilse Varnholt");
    expect(localStorage.getItem("jason-console-user")).toBe("Ilse Varnholt");
    await user.click(screen.getByRole("button", { name: "Open the document" }));
    const open = screen.getByRole("region", { name: "Open letter" });
    expect(within(open).getByText("Please send an itemized invoice.")).toBeInTheDocument();
    await user.click(within(open).getByRole("button", { name: "Approve as Ilse Varnholt" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].url).toBe("/api/write/approvals/Drive%2FFinance%2Fvendor.docx");
    expect(posted[0].body).toEqual({ action: "approve", by: "Ilse Varnholt" });
  });

  it("shows the tool's not-found note", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ found: false, note: "no letter drafted yet" }), { status: 200 })));
    render(<ApprovalsView />);
    expect(await screen.findByText("no letter drafted yet")).toBeInTheDocument();
  });
});
