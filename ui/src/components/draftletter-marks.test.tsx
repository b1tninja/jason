import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DraftLetter, kindGlyph, type Letter } from "./DraftLetter";

const base: Letter = {
  key: "Drive/Example/letter.docx", kind: "Notice", title: "Notice of a hearing", date: "2026-10-03", to: "The owner of Unit 1, 123 Main St",
  via: "First-class mail", body: ["The board will meet."], signoff: "The Board of Directors", approver: "the treasurer", stage: "draft", log: [],
};
const approvedEntry = { id: "3", date: "2026-10-05", title: "Approved by M. Chen as the treasurer", by: "M. Chen" };

const marks = (c: HTMLElement) => ({
  seal: c.querySelector(".draft-letter-foot .seal")?.getAttribute("data-word") ?? null,
  stamps: [...c.querySelectorAll(".draft-letter-foot .stamp")].map((s) => s.getAttribute("data-word")),
});

describe("DraftLetter marks", () => {
  it("picks the kind's glyph by its words", () => {
    expect(kindGlyph("Notice of hearing")).toBe("notice");
    expect(kindGlyph("Vendor inquiry")).toBe("mail");
    expect(kindGlyph("Lien release")).toBe("file-text");
  });

  it("shows the approver's routing tag in the head", () => {
    const { container } = render(<DraftLetter letter={base} />);
    expect(container.querySelector(".draft-letter-head .routing-tag")?.getAttribute("data-role")).toBe("treasurer");
    const board = render(<DraftLetter letter={{ ...base, approver: "the board" }} />);
    expect(board.container.querySelector(".draft-letter-head .routing-tag")?.getAttribute("data-role")).toBe("board");
  });

  it("seals drafted before the save and filed after it, with no stamp", () => {
    expect(marks(render(<DraftLetter letter={base} />).container)).toEqual({ seal: "drafted", stamps: [] });
    expect(marks(render(<DraftLetter letter={{ ...base, stage: "saved" }} />).container)).toEqual({ seal: "filed", stamps: [] });
    expect(marks(render(<DraftLetter letter={{ ...base, stage: "requested" }} />).container)).toEqual({ seal: "filed", stamps: [] });
  });

  it("stamps approved only once approved, and sent only with the record of the sending", () => {
    const approved = { ...base, stage: "approved" as const, log: [approvedEntry] };
    expect(marks(render(<DraftLetter letter={approved} />).container).stamps).toEqual(["approved"]);
    expect(marks(render(<DraftLetter letter={{ ...approved, stage: "sent" }} />).container).stamps).toEqual(["approved"]);
    expect(marks(render(<DraftLetter letter={{ ...approved, stage: "sent", sentRef: "comm-1", sentOn: "2026-10-06" }} />).container).stamps).toEqual(["approved", "sent"]);
  });

  it("leaves the owner's view without seals and stamps", () => {
    const { container } = render(<DraftLetter letter={{ ...base, stage: "sent" }} readonly />);
    expect(container.querySelector(".seal, .stamp, .routing-tag")).toBeNull();
  });
});
