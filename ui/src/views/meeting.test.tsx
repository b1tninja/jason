import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingView, weekOf } from "./MeetingView";

afterEach(() => vi.unstubAllGlobals());

const item = { id: "reserve-loan", title: "Reserve loan not restored", summary: "", ask: "Decide whether to restore", category: "reserves", priority: "high", status: "on agenda", authority: "CIV 5515(d)", evidence: [], session: null, special_notice: "", due: null, opened: null, owner: "", meeting: "2026-10-20", notes: "", source: "jason", history: [], agendaSession: "open session" };

/** Answers /api/meeting with one noticed item and /api/embeds with the calendar and a recording dated the meeting day. */
function mockFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.startsWith("/api/embeds") ? new Response(JSON.stringify({
      found: true, calendarId: "abc@group.calendar.google.com", timeZone: "America/Los_Angeles", recordings: [
        { date: "2026-10-20", topic: "Board meeting", uuid: "u1", shareUrl: "https://zoom.us/rec/share/abc", playUrl: "https://zoom.us/rec/play/abc", files: [{ type: "audio", name: "audio_only.m4a", path: "zoom/2026-10-20/audio_only.m4a" }] },
        { date: "2026-09-15", topic: "Earlier meeting", uuid: "u0", shareUrl: "https://zoom.us/rec/share/old", playUrl: "", files: [] },
      ],
    }), { status: 200 }) : new Response(JSON.stringify({
      found: true, date: url.includes("date=") ? url.split("date=")[1] : "2026-10-20", today: "2026-10-03", noticeBy: "2026-10-16", executiveNoticeBy: "2026-10-18",
      items: [item], openCount: 1, executiveCount: 0, directors: ["A. Director", "B. Director"], decisions: [], agendaMarkdown: "# Agenda\n\n1. **Reserve loan not restored**", packetMarkdown: "# Board packet\n\n## 1. Reserve loan not restored\n\n**The question for the board.** Decide whether to restore", minutesTemplate: "# Minutes", notes: [],
      commands: { agendaDoc: "jason board --agenda <id> --date 2026-10-20 --doc --yes", packetDoc: "jason board --packet --date 2026-10-20 --doc --yes", minutesDraft: "jason board --minutes 2026-10-20", notice: "jason board --set <item id> --status \"on agenda\" --meeting 2026-10-20" },
      caveats: ["No action may be taken on an item not on the noticed agenda (CIV 4930)."],
    }), { status: 200 })));
}

describe("MeetingView", () => {
  it("shows notice deadlines, items by session, the agenda, and the packet with their commands", async () => {
    mockFetch();
    render(<MeetingView />);
    expect(await screen.findByText("in 13d")).toBeInTheDocument();
    expect(screen.getByText("open session")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Agenda" })).toBeInTheDocument();
    expect(screen.getByText("jason board --agenda <id> --date 2026-10-20 --doc --yes")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Board packet" }));
    expect(screen.getByText(/The question for the board/)).toBeInTheDocument();
    expect(screen.getByText("No action may be taken on an item not on the noticed agenda (CIV 4930).")).toBeInTheDocument();
  });

  it("shows the meeting's week on the calendar and its recording on the Decisions tab", async () => {
    mockFetch();
    render(<MeetingView />);
    expect(await screen.findByText("That week on the calendar")).toBeInTheDocument();
    const week = await screen.findByTitle("Association calendar, week of 2026-10-20") as HTMLIFrameElement;
    expect(week.src).toContain("src=abc%40group.calendar.google.com");
    expect(week.src).toContain("mode=WEEK");
    expect(week.src).toContain("dates=20261018%2F20261024");
    expect(weekOf("2026-10-20")).toBe("20261018/20261024");
    expect(weekOf("2026-10-18")).toBe("20261018/20261024");
    expect(weekOf("2026-10-24")).toBe("20261018/20261024");
    await userEvent.click(screen.getByRole("tab", { name: /Decisions/ }));
    const zoom = screen.getByTitle("Board meeting") as HTMLIFrameElement;
    expect(zoom.src).toBe("https://zoom.us/rec/share/abc");
    const audio = document.querySelector("audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/file?path=zoom%2F2026-10-20%2Faudio_only.m4a");
    expect(screen.getByText(/under a litigation hold/)).toBeInTheDocument();
    expect(screen.queryByTitle("Earlier meeting")).not.toBeInTheDocument();
  });
});
