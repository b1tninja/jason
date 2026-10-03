import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApprovalsInbox, Checklist, DraftLetter, groupLetters, type Letter } from "./index";
import { canApprove, type Person } from "../lib/session";

const people: Person[] = [
  { name: "Quill Ashgrove", role: "president", approves: ["the president"], canApproveBoard: true },
  { name: "Odo Fennimore", role: "secretary", approves: ["the secretary"], canApproveBoard: true },
  { name: "Ilse Varnholt", role: "treasurer", approves: ["the treasurer"], canApproveBoard: false },
  { name: "Pell Marchbanks", role: "manager", approves: ["the manager"], canApproveBoard: false },
];
const base: Letter = {
  key: "Drive/Collections/Unit 7/release.docx", kind: "Lien release", title: "Release of Notice of Delinquent Assessment", date: "2026-10-03",
  to: "County Recorder; copy to the owner of record, Unit 7", via: "Recording; first-class mail to the owner", body: ["The association releases the notice.", "Recorded on request."],
  signoff: "The Board of Directors", approver: "the board", stage: "requested", sentCommand: "jason letter release --unit 7 --yes",
  log: [{ id: "1", date: "2026-10-02", title: "Draft saved", by: "Pell Marchbanks" }, { id: "2", date: "2026-10-02", title: "Approval requested from the board", by: "Pell Marchbanks" }],
};
const vendor: Letter = { ...base, key: "Drive/Finance/vendor.docx", kind: "Vendor inquiry", title: "Request for an itemized invoice", approver: "the treasurer", to: "Billing, Gate Co.", via: "Email", sentCommand: "jason letter vendor-inquiry --yes" };

describe("canApprove", () => {
  it("lets only the president or secretary record a board vote, and a role approve only its own", () => {
    expect(canApprove("Quill Ashgrove", "the board", people)).toBe(true);
    expect(canApprove("Ilse Varnholt", "the board", people)).toBe(false);
    expect(canApprove("Ilse Varnholt", "the treasurer", people)).toBe(true);
    expect(canApprove("Ilse Varnholt", "the secretary", people)).toBe(false);
    expect(canApprove("Nobody", "the treasurer", people)).toBe(false);
  });
});

describe("DraftLetter", () => {
  it("shows the document, the awaiting badge, and the trail", () => {
    render(<DraftLetter letter={base} me="Ilse Varnholt" people={people} />);
    expect(screen.getByText("awaiting approval")).toBeInTheDocument();
    expect(screen.getByText("jason drafts it. Nothing is sent without approval.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: base.title })).toBeInTheDocument();
    expect(screen.getByText("The association releases the notice.")).toBeInTheDocument();
    expect(screen.getByText("Approval requested from the board")).toBeInTheDocument();
  });

  it("offers Approve only to the matching person and says why to anyone else", async () => {
    const onStage = vi.fn();
    const { rerender } = render(<DraftLetter letter={vendor} me="Quill Ashgrove" people={people} onStage={onStage} />);
    expect(screen.queryByRole("button", { name: /Approve as/ })).not.toBeInTheDocument();
    expect(screen.getByText("Signed in as Quill Ashgrove, who is not the treasurer.")).toBeInTheDocument();
    rerender(<DraftLetter letter={vendor} me="Ilse Varnholt" people={people} onStage={onStage} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Approve as Ilse Varnholt" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Approve \"Request for an itemized invoice\" as Ilse Varnholt, treasurer, for the treasurer");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onStage).toHaveBeenCalledWith("approve", { by: "Ilse Varnholt", note: undefined });
  });

  it("records the board's approval only through the president or secretary, with the meeting date and CIV 4910", async () => {
    const onStage = vi.fn();
    const { rerender } = render(<DraftLetter letter={base} me="Ilse Varnholt" people={people} onStage={onStage} />);
    expect(screen.queryByRole("button", { name: /approval/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Needs a board vote at a meeting \(CIV 4910\)/)).toBeInTheDocument();
    rerender(<DraftLetter letter={base} me="Odo Fennimore" people={people} onStage={onStage} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Record the board's approval" }));
    const group = screen.getByRole("group", { name: "Confirm" });
    expect(group).toHaveTextContent("CIV 4910");
    expect(group).toHaveTextContent("vote at an open meeting");
    await user.type(within(group).getByLabelText("Meeting date"), "2026-10-20");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onStage).toHaveBeenCalledWith("approve", { by: "Odo Fennimore", note: undefined, meeting: "2026-10-20" });
  });

  it("shows the terminal command once approved and never a button that sends", async () => {
    const onStage = vi.fn();
    render(<DraftLetter letter={{ ...base, stage: "approved" }} me="Pell Marchbanks" people={people} onStage={onStage} />);
    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getByText("jason letter release --unit 7 --yes")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Send$/ })).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Record as sent" }));
    await user.type(screen.getByLabelText("Where it was logged"), "mailroom 48213");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onStage).toHaveBeenCalledWith("record_sent", { by: "Pell Marchbanks", note: undefined, sentRef: "mailroom 48213" });
  });

  it("walks a draft to saved to requested behind confirms", async () => {
    const onStage = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<DraftLetter letter={{ ...vendor, stage: "draft", log: [] }} me="Pell Marchbanks" people={people} onStage={onStage} />);
    expect(screen.getByText("draft")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Nothing is mailed, posted, or recorded without approval.");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onStage).toHaveBeenLastCalledWith("save", { by: "Pell Marchbanks", note: undefined });
    rerender(<DraftLetter letter={{ ...vendor, stage: "saved", log: [] }} me="Pell Marchbanks" people={people} onStage={onStage} />);
    await user.click(screen.getByRole("button", { name: "Ask the treasurer to approve" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onStage).toHaveBeenLastCalledWith("request", { by: "Pell Marchbanks", note: undefined });
  });

  it("shows the sent line and the readonly owner view", () => {
    const { rerender } = render(<DraftLetter letter={{ ...base, stage: "sent", sentOn: "2026-10-03", sentRef: "mailroom 48213" }} me="Pell Marchbanks" people={people} />);
    expect(screen.getByText("Sent 2026-10-03. Logged: mailroom 48213.")).toBeInTheDocument();
    rerender(<DraftLetter letter={{ ...base, ownerBadge: "mailed" }} readonly />);
    expect(screen.getByText("mailed")).toBeInTheDocument();
    expect(screen.getByText("As delivered to members.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("ApprovalsInbox", () => {
  const letters: Letter[] = [base, vendor, { ...vendor, key: "Drive/Finance/approved.docx", title: "Approved one", stage: "approved" }, { ...vendor, key: "Drive/Finance/sent.docx", title: "Sent one", stage: "sent", sentRef: "mailroom 1", sentOn: "2026-10-01" }];

  it("groups by stage", () => {
    const groups = groupLetters(letters);
    expect(groups.map((g) => [g.id, g.items.length])).toEqual([["requested", 2], ["approved", 1], ["sent", 1]]);
  });

  it("shows each group with the actions the signed-in person may take", async () => {
    const onAction = vi.fn();
    render(<ApprovalsInbox letters={letters} me="Ilse Varnholt" people={people} onAction={onAction} />);
    const waiting = screen.getByRole("region", { name: "Awaiting approval" });
    expect(within(waiting).getAllByRole("article")).toHaveLength(2);
    expect(within(waiting).getByText("Needs a board vote at a meeting (CIV 4910)")).toBeInTheDocument();
    expect(within(waiting).getAllByRole("button", { name: "Approve" })).toHaveLength(1);
    const approved = screen.getByRole("region", { name: "Approved, not sent" });
    expect(within(approved).getByText("jason letter vendor-inquiry --yes")).toBeInTheDocument();
    expect(within(approved).queryByRole("button", { name: /Send/ })).not.toBeInTheDocument();
    const sent = screen.getByRole("region", { name: "Sent" });
    expect(within(sent).getByText("Logged: mailroom 1")).toBeInTheDocument();
    expect(within(sent).queryByRole("button", { name: /Approve|Send/ })).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(waiting).getByRole("button", { name: "Send back" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith(vendor.key, "send_back", { by: "Ilse Varnholt" });
  });

  it("lets the secretary record a board vote with the meeting date", async () => {
    const onAction = vi.fn();
    render(<ApprovalsInbox letters={[base]} me="Odo Fennimore" people={people} onAction={onAction} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Record board approval" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("CIV 4910");
    await user.type(screen.getByLabelText("Meeting date"), "2026-10-20");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith(base.key, "approve", { by: "Odo Fennimore", meeting: "2026-10-20" });
  });
});

describe("Checklist", () => {
  it("marks each line ready or missing and ticks nothing", () => {
    render(<Checklist title="Notice contents" items={[{ label: "Date, time, and place", ready: true }, { label: "Agenda", ready: false, detail: "no items yet" }]} />);
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
    expect(screen.getByText("1 missing")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
