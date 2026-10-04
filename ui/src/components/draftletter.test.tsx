import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DraftLetter, REPLIES, REPLIES_MISSING, approvalLine, letterText, type Letter } from "./DraftLetter";
import type { Person } from "../lib/session";

const people: Person[] = [
  { name: "R. Lind", role: "secretary", approves: ["the secretary"], canApproveBoard: true },
  { name: "M. Chen", role: "treasurer", approves: ["the treasurer"], canApproveBoard: false },
  { name: "P. Varga", role: "manager", approves: ["the manager"], canApproveBoard: false },
];
const saved = { id: "1", date: "2026-10-02", title: "Draft saved to Drive/Example/letter.docx by P. Varga", by: "P. Varga" };
const requested = { id: "2", date: "2026-10-02", title: "Approval requested from the board by P. Varga", by: "P. Varga" };
const board: Letter = {
  key: "Drive/Example/letter.docx", kind: "Notice", title: "Notice of a hearing", date: "2026-10-03", to: "The owner of Unit 1, 123 Main St",
  via: "First-class mail", body: ["The board will meet."], signoff: "The Board of Directors", approver: "the board", stage: "requested", log: [saved, requested],
};
const OFFICERS = "jason is automated; the officers sign, jason never does.";

describe("the approval line", () => {
  it("says jason drafts and nothing is saved yet, and who approves, before the first save", () => {
    expect(approvalLine({ ...board, stage: "draft", log: [], approver: "the treasurer" })).toEqual([
      "jason drafts; not yet saved", "Not yet approved (approver: the treasurer)", OFFICERS, REPLIES,
    ]);
  });

  it("names who saved the draft and still waits on the approver", () => {
    expect(approvalLine(board).slice(0, 2)).toEqual(["Drafted by jason for P. Varga, 2026-10-02", "Not yet approved (approver: the board)"]);
  });

  it("names the board's vote, its meeting, and the officer who recorded it", () => {
    const vote = { id: "3", date: "2026-10-04", title: "The board approved it by vote at its meeting of 2026-10-03 (CIV 4910); recorded by R. Lind, secretary", tone: "good" as const, by: "R. Lind" };
    expect(approvalLine({ ...board, stage: "approved", meeting: "2026-10-03", log: [saved, requested, vote] })[1])
      .toBe("Approved by the board at its meeting of 2026-10-03, recorded by R. Lind");
    expect(approvalLine({ ...board, stage: "sent", log: [saved, requested, vote] })[1])
      .toBe("Approved by the board at its meeting of 2026-10-03, recorded by R. Lind");
  });

  it("names the officer who approved for their role, and when", () => {
    const ok = { id: "3", date: "2026-10-03", title: "Approved by M. Chen (treasurer) as the treasurer", tone: "good" as const, by: "M. Chen" };
    expect(approvalLine({ ...board, approver: "the treasurer", stage: "approved", log: [saved, ok] })[1]).toBe("Approved by M. Chen as the treasurer, 2026-10-03");
  });

  it("carries where replies go when the letter has it", () => {
    expect(approvalLine({ ...board, replyTo: "Secretary, 123 Main St" })[3]).toBe(`${REPLIES}: Secretary, 123 Main St`);
  });

  it("is not part of the letter's copied text", () => {
    expect(letterText(board)).not.toContain("jason is automated");
  });
});

describe("DraftLetter's foot", () => {
  it("ends every stage with the approval line, and says when the reply address is not on file", () => {
    const { container, rerender } = render(<DraftLetter letter={board} me="P. Varga" people={people} />);
    const last = () => container.querySelector("article > footer:last-child > :last-child");
    expect(last()).toHaveClass("draft-letter-approval");
    expect(last()).toHaveTextContent(`Drafted by jason for P. Varga, 2026-10-02 · Not yet approved (approver: the board) · ${OFFICERS} · ${REPLIES} ${REPLIES_MISSING}`);
    expect(screen.getByText(REPLIES_MISSING)).toBeInTheDocument();
    for (const stage of ["draft", "saved", "approved", "sent"] as const) {
      rerender(<DraftLetter letter={{ ...board, stage }} me="P. Varga" people={people} />);
      expect(last()).toHaveClass("draft-letter-approval");
    }
  });

  it("shows the approval line in the owner's view too, with the reply address when known", () => {
    const { container } = render(<DraftLetter letter={{ ...board, replyTo: "Secretary, 123 Main St" }} readonly />);
    const line = container.querySelector("article > footer:last-child > .draft-letter-approval");
    expect(line).toHaveTextContent(`${REPLIES}: Secretary, 123 Main St`);
    expect(screen.queryByText(REPLIES_MISSING)).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
