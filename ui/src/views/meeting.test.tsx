import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingView } from "./MeetingView";

afterEach(() => vi.unstubAllGlobals());

describe("MeetingView", () => {
  it("shows notice deadlines, items by session, the agenda, and the packet with their commands", async () => {
    const item = { id: "reserve-loan", title: "Reserve loan not restored", summary: "", ask: "Decide whether to restore", category: "reserves", priority: "high", status: "on agenda", authority: "CIV 5515(d)", evidence: [], session: null, special_notice: "", due: null, opened: null, owner: "", meeting: "2026-10-20", notes: "", source: "jason", history: [], agendaSession: "open session" };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({
      found: true, date: url.includes("date=") ? url.split("date=")[1] : "2026-10-20", today: "2026-10-03", noticeBy: "2026-10-16", executiveNoticeBy: "2026-10-18",
      items: [item], openCount: 1, executiveCount: 0, agendaMarkdown: "# Agenda\n\n1. **Reserve loan not restored**", packetMarkdown: "# Board packet\n\n## 1. Reserve loan not restored\n\n**The question for the board.** Decide whether to restore", minutesTemplate: "# Minutes", notes: [],
      commands: { agendaDoc: "jason board --agenda <id> --date 2026-10-20 --doc --yes", packetDoc: "jason board --packet --date 2026-10-20 --doc --yes", minutesDraft: "jason board --minutes 2026-10-20", notice: "jason board --set <item id> --status \"on agenda\" --meeting 2026-10-20" },
      caveats: ["No action may be taken on an item not on the noticed agenda (CIV 4930)."],
    }), { status: 200 })));
    render(<MeetingView />);
    expect(await screen.findByText("in 13d")).toBeInTheDocument();
    expect(screen.getByText("open session")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Agenda" })).toBeInTheDocument();
    expect(screen.getByText("jason board --agenda <id> --date 2026-10-20 --doc --yes")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Board packet" }));
    expect(screen.getByText(/The question for the board/)).toBeInTheDocument();
    expect(screen.getByText("No action may be taken on an item not on the noticed agenda (CIV 4930).")).toBeInTheDocument();
  });
});
