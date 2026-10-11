import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RuleChangeView } from "./RuleChangeView";

afterEach(() => vi.unstubAllGlobals());

describe("RuleChangeView", () => {
  it("lists changes, opens one with its clock and brackets, fills a bracket, and shows the command", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("key=")) {
        const p = new URLSearchParams(url.split("?")[1]);
        const days = p.get("V_number of days");
        return new Response(JSON.stringify({ found: true, key: "parking-tags", title: "Visitor parking tags", documentTitle: "Parking Rules", purpose: "fewer tows", effect: "owners register visitors", authorities: ["CIV 4360"],
          decisions: ["the number of days"], placeholders: ["[number of days]"], open: days ? [] : ["[number of days]"], sectionsMarkdown: `### Section 4: Visitor parking\n\nA visitor may park for ${days ?? "[number of days]"} days.`, currentNote: "",
          stages: [{ key: "notice", label: "Member notice goes out", date: "2026-10-03" }, { key: "decision", label: "Board decides", date: "2026-11-17", authority: "CIV 4360(a)" }], timelineNote: "", today: "2026-10-03",
          command: "jason rule-change parking-tags --draft-email --yes", caveats: ["A bracketed choice is the board's; jason never fills it."] }), { status: 200 });
      }
      return new Response(JSON.stringify({ found: true, changes: [{ key: "parking-tags", slug: "parking-tags", title: "Visitor parking tags", document: "parking-rules", documentTitle: "Parking Rules", purpose: "", effect: "", sections: 2, placeholders: ["[number of days]"], decisions: ["the number of days"], authorities: ["CIV 4360"] }] }), { status: 200 });
    }));
    render(<RuleChangeView />);
    expect(await screen.findByText("Visitor parking tags")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(await screen.findByText("Board decides")).toBeInTheDocument();
    expect(screen.getByText("Still open: [number of days]")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("number of days"), "3");
    await waitFor(() => expect(screen.getByText("A visitor may park for 3 days.")).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.queryByText(/Still open/)).not.toBeInTheDocument();
    expect(screen.getByText("jason rule-change parking-tags --draft-email --yes")).toBeInTheDocument();
    expect(screen.getByText("A bracketed choice is the board's; jason never fills it.")).toBeInTheDocument();
  });

  const change = (law?: unknown) => vi.fn(async (url: string) => {
    if (url.includes("key=")) {
      return new Response(JSON.stringify({ found: true, key: "tags", title: "Visitor tags", documentTitle: "Parking Rules", purpose: "fewer tows 2099", effect: "owners register visitors", authorities: ["CIV 4360"],
        decisions: [], placeholders: [], open: [], sectionsMarkdown: "### Section 4 (proposed number): Visitor tags\n\nA visitor registers.", currentNote: "", stages: [], timelineNote: "", today: "2099-01-01",
        command: "jason rule-change tags --draft-email --yes", caveats: [], law, lawCaveat: "jason's consolidated text of the statute is not an official restatement." }), { status: 200 });
    }
    return new Response(JSON.stringify({ found: true, changes: [{ key: "tags", slug: "tags", title: "Visitor tags", document: "rules", documentTitle: "Parking Rules", purpose: "", effect: "", sections: 1, placeholders: [], decisions: [], authorities: [] }] }), { status: 200 });
  });

  async function open() {
    render(<RuleChangeView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    await screen.findByText("The text of the proposed change");
  }

  it("prints the text of the change before the description of its purpose and effect, the description labeled as the board's", async () => {
    vi.stubGlobal("fetch", change([]));
    await open();
    const text = screen.getByText("The text of the proposed change");
    const purpose = screen.getByText("The board's description of its purpose and effect");
    expect(text.compareDocumentPosition(purpose) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("A visitor registers.").compareDocumentPosition(screen.getByText("fewer tows 2099")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/The board's own description of the change, not the rule itself/)).toBeInTheDocument();
    expect(screen.getByText(/proposed number/)).toBeInTheDocument();
  });

  it("recites 4360(a) and 4355(a) from the shelf, with the caveat and the reading labeled", async () => {
    vi.stubGlobal("fetch", change([
      { citation: "CIV 4360(a)", why: "What the notice must carry", found: true, words: "(a) The notice shall include the text of the proposed rule change.", note: "" },
      { citation: "CIV 4355(a)", why: "The subjects", found: true, words: "(a) Sections 4360 and 4365 only apply to an operating rule that relates to the following subjects:", note: "" },
    ]));
    await open();
    expect(screen.getByLabelText("The words of CIV 4360(a)")).toHaveTextContent("(a) The notice shall include the text of the proposed rule change.");
    expect(screen.getByLabelText("The words of CIV 4355(a)")).toBeInTheDocument();
    expect(screen.getByText(/not an official restatement/)).toBeInTheDocument();
    expect(screen.getByText("Reading, not the statute:")).toBeInTheDocument();
    expect(screen.queryByText(/Text not on the shelf/)).not.toBeInTheDocument();
  });

  it("says the text is not on the shelf and cites by number only when the shelf lacks a section", async () => {
    vi.stubGlobal("fetch", change([
      { citation: "CIV 4360(a)", why: "What the notice must carry", found: false, words: "", note: "text not on the shelf; cited by number only" },
    ]));
    await open();
    expect(screen.getByText(/Text not on the shelf\. See CIV 4360\(a\) by number/)).toBeInTheDocument();
    expect(screen.queryByLabelText("The words of CIV 4360(a)")).not.toBeInTheDocument();
  });
});
