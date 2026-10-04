import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentViewer, humanSize, looksLikeMarkdown, type DocumentView, type EvidenceDocument } from "./index";

afterEach(() => vi.restoreAllMocks());

const UNMASKED = "Unmasked: shown because Jane Example asked; this view is logged.";
const today = new Date("2026-10-03T12:00:00");

const view = (over: Partial<DocumentView> = {}): DocumentView => ({
  kind: "submission", name: "Owner information, Unit 12", readAt: "2026-09-30T18:38:00+00:00", url: "", expires: "",
  submission: {
    form: "Owner information", unit: "12", submitted: "2026-09-28T16:02:00+00:00", status: "Pending",
    questions: [
      { question: "Owner's full name", answer: "Jane Doe", kind: "text" },
      { question: "Mailing address", answer: "123 Main St", kind: "text" },
      { question: "Do you rent the unit?", answer: "No", kind: "choice" },
      { question: "Second phone", answer: "", kind: "text" },
    ],
  },
  caveats: [UNMASKED, "A stored copy is what jason read then, not the record now."],
  ...over,
});

const listed: EvidenceDocument = { id: "d1", name: "Owner information, Unit 12", kind: "submission", size: 0, readAt: "2026-09-30T18:38:00+00:00", note: "" };

describe("DocumentViewer", () => {
  it("opens as a modal dialog named by the document, with when it was read and the unmasked caveat in a notice", () => {
    render(<DocumentViewer data={view()} onClose={() => {}} today={today} />);
    const dialog = screen.getByRole("dialog", { name: "Owner information, Unit 12" });
    expect(dialog).toHaveAttribute("open");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(within(dialog).getByText(/\(3 days ago\)/)).toHaveTextContent("Read 2026-09-30 18:38 UTC (3 days ago)");
    expect(within(dialog).getByText(UNMASKED)).toHaveClass("notice");
    expect(within(dialog).getByText("A stored copy is what jason read then, not the record now.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Owner information, Unit 12", level: 2 })).toHaveFocus();
  });

  it("shows a submission as the form was filled in, its questions in order, a blank as (no answer)", () => {
    render(<DocumentViewer data={view()} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Owner information", level: 3 })).toBeInTheDocument();
    expect(within(dialog).getByText("Unit 12")).toBeInTheDocument();
    expect(within(dialog).getByText(/Submitted/)).toHaveTextContent("Submitted 2026-09-28");
    expect(within(dialog).getByText("Pending")).toBeInTheDocument();
    const terms = within(dialog).getAllByRole("term").map((t) => t.textContent);
    expect(terms).toEqual(["Owner's full name", "Mailing address", "Do you rent the unit?", "Second phone"]);
    expect(within(dialog).queryByRole("heading", { level: 4 })).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/Completed/)).not.toBeInTheDocument();
    const answers = within(dialog).getAllByRole("definition").map((d) => d.textContent);
    expect(answers).toEqual(["Jane Doe", "123 Main St", "No", "(no answer)"]);
    expect(within(dialog).getByText("(no answer)")).toHaveClass("muted");
    expect(within(dialog).queryByRole("link", { name: /Open in a new tab/ })).not.toBeInTheDocument();
  });

  const owner = (): DocumentView => view({
    submission: {
      form: "Owner information", unit: "102 EXAMPLE WAY", submitted: "2026-10-05T17:00:00.000Z", completed: "2026-10-07", status: "pending",
      intro: "Please answer by October 23.\n\nThank you.",
      questions: [
        { question: "Owner", answer: "", kind: "section" },
        { question: "1. Your name", answer: "Ana Example", kind: "text", help: "As on the deed.", required: true },
        { question: "Answer for the unit named above.", answer: "", kind: "note" },
        { question: "Notice delivery", answer: "", kind: "section" },
        { question: "2. How should the Association deliver notices", answer: "By mail; By email", kind: "choice", help: "Choose any." },
        { question: "3. Mailing address for notices", answer: "Same as my unit address; PO Box 12, Example City, CA 90000", kind: "choice", flag: "both given" },
        { question: "5. Pets in the unit", answer: "None chosen", kind: "choice" },
        { question: "6. Lease (optional)", answer: "lease.pdf; addendum.pdf", kind: "file", files: ["77_lease.pdf"] },
        { question: "7. Second phone", answer: "", kind: "text" },
      ],
    },
  });
  const ownerDocs: EvidenceDocument[] = [
    { id: "submission", name: "Owner information as submitted", kind: "submission", size: 0, readAt: "", note: "" },
    { id: "77_lease.pdf", name: "77_lease.pdf", kind: "pdf", size: 812, readAt: "", note: "" },
  ];

  it("lays a submission out as the form: its introduction, its sections as headings, its notes, and Completed", () => {
    render(<DocumentViewer data={owner()} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Please answer by October 23/)).toHaveClass("doc-submission-intro", "muted");
    expect(within(dialog).getByText(/Please answer by October 23/).textContent).toBe("Please answer by October 23.\n\nThank you.");
    expect(within(dialog).getByText(/Completed/)).toHaveTextContent("Completed 2026-10-07");
    const sections = within(dialog).getAllByRole("heading", { level: 4 });
    expect(sections.map((h) => h.textContent)).toEqual(["Owner", "Notice delivery"]);
    expect(sections[0]).toHaveClass("doc-submission-section");
    expect(within(dialog).getByText("Answer for the unit named above.")).toHaveClass("doc-submission-note", "muted");
    expect(within(dialog).queryByText("Answer for the unit named above.")?.closest("dl")).toBeNull();
    const terms = within(dialog).getAllByRole("term").map((t) => t.querySelector(".doc-answer-question")?.textContent);
    expect(terms).toEqual(["1. Your name", "2. How should the Association deliver notices", "3. Mailing address for notices",
      "5. Pets in the unit", "6. Lease (optional)", "7. Second phone"]);
  });

  it("shows a question's help under it, required in words, a flag as a warn chip, and None chosen as given", () => {
    render(<DocumentViewer data={owner()} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    const name = within(dialog).getAllByRole("term")[0];
    expect(within(name).getByText("required")).toHaveClass("doc-answer-required");
    expect(within(name).getByText("As on the deed.")).toHaveClass("doc-answer-help");
    expect(within(dialog).getAllByText("required")).toHaveLength(1);
    expect(within(dialog).getByText("By mail; By email")).toBeInTheDocument();
    const flag = within(dialog).getByText("both given");
    expect(flag).toHaveClass("chip", "doc-answer-flag");
    expect(flag.closest("dd")).toHaveTextContent("Same as my unit address; PO Box 12, Example City, CA 90000 both given");
    expect(within(dialog).getByText("None chosen")).not.toHaveClass("muted");
    expect(within(dialog).getByText("(no answer)")).toHaveClass("muted");
  });

  it("opens a file answer's saved file through onGo, a new view; an unsaved file stays text", async () => {
    const onGo = vi.fn();
    const { rerender } = render(<DocumentViewer data={owner()} documents={ownerDocs} position={{ index: 0, count: 2 }} onGo={onGo} onClose={() => {}} />);
    const lease = screen.getByRole("button", { name: "lease.pdf" });
    expect(screen.queryByRole("button", { name: "addendum.pdf" })).not.toBeInTheDocument();
    expect(lease.closest("dd")).toHaveTextContent("lease.pdf; addendum.pdf");
    await userEvent.click(lease);
    expect(onGo).toHaveBeenCalledWith(1);
    rerender(<DocumentViewer data={owner()} position={{ index: 0, count: 2 }} onGo={onGo} onClose={() => {}} />);
    expect(screen.queryByRole("button", { name: "lease.pdf" })).not.toBeInTheDocument();       // no list: names only
    expect(screen.getByText("lease.pdf; addendum.pdf")).toBeInTheDocument();
  });

  it("prints from the Print button", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<DocumentViewer data={view()} onClose={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Print" }));
    expect(print).toHaveBeenCalledTimes(1);
  });

  it("frames a pdf from its url, with a new-tab link and the fallback link", () => {
    const url = "/api/evidence/document/tok-abc";
    render(<DocumentViewer data={view({ kind: "pdf", name: "Inspection report.pdf", url, expires: "2026-10-03T19:12:00+00:00", submission: null })} onClose={() => {}} />);
    const frame = screen.getByTitle("Inspection report.pdf");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame).toHaveAttribute("src", url);
    const tab = screen.getByRole("link", { name: /Open in a new tab/ });
    expect(tab).toHaveAttribute("href", url);
    expect(tab).toHaveAttribute("target", "_blank");
    expect(tab).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByRole("link", { name: "open it in a new tab" })).toHaveAttribute("href", url);
    expect(screen.getByText(/Your browser can't show the PDF here/)).toBeInTheDocument();
    expect(screen.getByText(/The link works until/)).toHaveTextContent("2026-10-03 19:12 UTC");
  });

  it("shows an image fitted, and at its actual size from the toggle", async () => {
    const url = "/api/evidence/document/tok-img";
    render(<DocumentViewer data={view({ kind: "image", name: "Fence photo.jpg", url, submission: null })} onClose={() => {}} />);
    const img = screen.getByRole("img", { name: "Fence photo.jpg" });
    expect(img).toHaveAttribute("src", url);
    const fit = screen.getByRole("button", { name: "Fit" });
    const actual = screen.getByRole("button", { name: "Actual size" });
    expect(fit).toHaveAttribute("aria-pressed", "true");
    expect(img.closest(".doc-image")).toHaveClass("doc-image-fit");
    await userEvent.click(actual);
    expect(actual).toHaveAttribute("aria-pressed", "true");
    expect(fit).toHaveAttribute("aria-pressed", "false");
    expect(img.closest(".doc-image")).toHaveClass("doc-image-actual");
    await userEvent.click(fit);
    expect(img.closest(".doc-image")).toHaveClass("doc-image-fit");
    expect(screen.getByRole("link", { name: /Open in a new tab/ })).toHaveAttribute("href", url);
  });

  it("shows plain text as stored, and Markdown through the sanitizing renderer", () => {
    const plain = "Example Village board\n\nThe fence on 123 Main St is to be repaired.";
    const { rerender } = render(<DocumentViewer data={view({ kind: "text", name: "Letter.txt", text: plain, submission: null })} onClose={() => {}} />);
    const block = screen.getByText(/The fence on 123 Main St/);
    expect(block).toHaveClass("doc-text-plain");
    expect(block.textContent).toBe(plain);
    rerender(<DocumentViewer data={view({ kind: "text", name: "Notes.md", text: "# Example Village\n\n## Minutes\n\nRead <script>alert(1)</script>the **notes**.", submission: null })} onClose={() => {}} />);
    expect(screen.getByRole("heading", { name: "Example Village", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("notes").tagName).toBe("STRONG");
    expect(document.querySelector(".doc-viewer script")).toBeNull();
    expect(looksLikeMarkdown("Dear owner,\n## not at the start")).toBe(true);
    expect(looksLikeMarkdown("Dear owner,\n#5 on the list")).toBe(false);
  });

  it("offers a file only to download", () => {
    const url = "/api/evidence/document/tok-file";
    render(<DocumentViewer data={view({ kind: "file", name: "Ledger.xlsx", url, submission: null })} onClose={() => {}} />);
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", url);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(document.querySelector(".doc-viewer iframe")).toBeNull();
  });

  it("says Opening with aria-busy while the view runs, then shows an error in the dialog", () => {
    const { rerender } = render(<DocumentViewer data={null} document={listed} busy onClose={() => {}} />);
    const dialog = screen.getByRole("dialog", { name: "Owner information, Unit 12" });
    expect(within(dialog).getByText("Opening…")).toBeInTheDocument();
    expect(dialog.querySelector(".doc-viewer-body")).toHaveAttribute("aria-busy", "true");
    rerender(<DocumentViewer data={null} document={listed} error="This document is no longer on disk." onClose={() => {}} />);
    expect(within(dialog).getByText("This document is no longer on disk.")).toHaveClass("notice-error");
    expect(dialog).toHaveAttribute("open");
    expect(dialog.querySelector(".doc-viewer-body")).not.toHaveAttribute("aria-busy");
  });

  it("closes on Escape and on Close", async () => {
    const onClose = vi.fn();
    render(<DocumentViewer data={view()} onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");
    await userEvent.click(screen.getByRole("button", { name: "Close", hidden: true }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("offers Previous and Next only with several documents, disabled at the ends", async () => {
    const onGo = vi.fn();
    const { rerender } = render(<DocumentViewer data={view()} position={{ index: 0, count: 1 }} onGo={onGo} onClose={() => {}} />);
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
    rerender(<DocumentViewer data={view()} position={{ index: 0, count: 3 }} onGo={onGo} onClose={() => {}} />);
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
    const prev = screen.getByRole("button", { name: "Previous" });
    expect(prev).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(prev);
    expect(onGo).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onGo).toHaveBeenCalledWith(1);
  });

  it("renders in place, not modal, for a preview", () => {
    render(<DocumentViewer data={view()} inline />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("open");
    expect(dialog).not.toHaveAttribute("aria-modal");
    expect(dialog).toHaveClass("doc-viewer-inline");
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
  });
});

describe("humanSize", () => {
  it("says a size people read", () => {
    expect(humanSize(812)).toBe("812 bytes");
    expect(humanSize(1)).toBe("1 byte");
    expect(humanSize(48 * 1024)).toBe("48 KB");
    expect(humanSize(2_200_000)).toBe("2.1 MB");
    expect(humanSize(1024 * 1024)).toBe("1 MB");
    expect(humanSize(undefined)).toBe("");
  });
});
