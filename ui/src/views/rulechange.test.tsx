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
});
