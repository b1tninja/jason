import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, resetServerSession } from "../lib/api";
import { EvidenceEntries } from "./EvidenceEntries";
import { DecisionBrief } from "./DecisionBrief";
import { DOC_WORDS, type DocumentView, type EvidenceEntry } from "./index";

// Made-up entries, as `refs_from_strings` answers them; nothing here names a real document.
const entries: EvidenceEntry[] = [
  { address: "library:abc1234", document: "library:abc1234", name: "Open minutes", kind: "pdf", level: "P0", source: "Library copy" },
  { command: "jason board --sheet" },
  { text: "PayHOA: request 12" },
  { address: "CIV 4920(a)", document: "section", name: "CIV 4920(a)", kind: "text", level: "P0", source: "Statutes on disk" },
];
const textView: DocumentView = { kind: "text", name: "Open minutes", readAt: "", url: "", expires: "", text: "The board met.", caveats: [] };

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

function noRawLinks(container: HTMLElement) {
  expect(container.innerHTML).not.toContain("/api/file");
  expect(container.innerHTML).not.toMatch(/[A-Za-z]:[\\/]|file:\/\//);
  for (const f of Array.from(container.querySelectorAll("iframe"))) expect(f.getAttribute("src") ?? "").toMatch(/^\/api\//);
}

describe("EvidenceEntries", () => {
  it("renders each entry by its kind: a Doc chip, a command to copy, and text as written", () => {
    const { container } = render(<EvidenceEntries entries={entries} signedIn by="A Manager" onView={vi.fn()} />);
    expect(screen.getByText("Evidence:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Open minutes" })).toHaveAccessibleDescription("PDF");
    expect(screen.getByRole("button", { name: "Open CIV 4920(a)" })).toBeInTheDocument();
    expect(screen.getByText("jason board --sheet").tagName).toBe("CODE");
    expect(screen.getByRole("button", { name: "Copy the command jason board --sheet" })).toBeInTheDocument();
    expect(screen.getByText("PayHOA: request 12")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /PayHOA/ })).not.toBeInTheDocument();     // text never opens
    noRawLinks(container);
  });

  it("opening a chip is one logged view, never on load", async () => {
    const onView = vi.fn(async () => textView);
    render(<EvidenceEntries entries={entries} signedIn by="A Manager" onView={onView} />);
    expect(onView).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(onView).toHaveBeenCalledWith({ address: "library:abc1234", document: "library:abc1234", by: "A Manager" });
    expect(await screen.findByRole("dialog")).toHaveTextContent("The board met.");
  });

  it("signed out and not allowed say their words", async () => {
    const onView = vi.fn(async () => { throw new ApiError("The treasurer's office doesn't open this (P3).", 403); });
    const { unmount } = render(<EvidenceEntries entries={entries} signedIn={false} onView={onView} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(screen.getByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(onView).not.toHaveBeenCalled();
    unmount();
    render(<EvidenceEntries entries={entries} signedIn by="A Manager" onView={onView} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Open minutes" }));
    expect(await screen.findByText(/The treasurer's office doesn't open this/)).toBeInTheDocument();
  });

  it("renders nothing for no entries", () => {
    const { container } = render(<EvidenceEntries entries={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("DecisionBrief sources", () => {
  it("shows the matter's sources as chips beside the facts a person wrote, which stay text", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ token: "t", signedIn: { name: "A Manager" } }), { status: 200 })));
    const { container } = render(<DecisionBrief decision={{ question: "Which contract?", criteria: [], options: [{ label: "Renew", values: [] }, { label: "Rebid", values: [] }], facts: ["Both bids are in the packet"] }}
      sources={entries} />);
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });   // the session answers
    expect(screen.getByText("Both bids are in the packet").tagName).toBe("LI");
    expect(screen.getByText("Sources:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Open minutes" })).toBeInTheDocument();
    noRawLinks(container);
  });

  it("without sources it is as it was", () => {
    render(<DecisionBrief decision={{ question: "Which contract?", criteria: [], options: [], facts: [] }} />);
    expect(screen.queryByText("Sources:")).not.toBeInTheDocument();
  });
});
