import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingView, weekOf } from "./MeetingView";

afterEach(() => vi.unstubAllGlobals());

const item = { id: "reserve-loan", title: "Reserve loan not restored", summary: "", ask: "Decide whether to restore", category: "reserves", priority: "high", status: "on agenda", authority: "CIV 5515(d)", evidence: [], session: null, special_notice: "", due: null, opened: null, owner: "", meeting: "2026-10-20", notes: "", source: "jason", history: [], agendaSession: "open session" };

/** The recording's reference as the embeds loader gives it (`jason.approvals.docref.file_ref`): the server's level. */
const audioDoc = { address: "file:zoom/meetings/2026-10-20-abc/audio.m4a", document: "audio", name: "Board meeting (audio)", kind: "audio", level: "P1", source: "File on disk", size: 9 };
const audioView = { kind: "audio", name: "audio.m4a", readAt: "", url: "/api/evidence/document/rec", expires: "", caveats: ["Unmasked: shown because A. Director asked; this view is logged."] };

/** Answers /api/meeting with one noticed item and /api/embeds with the calendar and a recording dated the meeting day;
 * a view of the recording answers its short-lived link. Records each POST. */
function mockFetch(posts: [string, unknown][] = [], meeting: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push([url, JSON.parse(String(init.body))]);
    return url === "/api/evidence/view" ? new Response(JSON.stringify(audioView), { status: 200 })
    : url === "/api/session" ? new Response(JSON.stringify({
      token: "t", signedIn: { name: "A. Director" }, signIn: { configured: true },          // a recording's file opens signed in
    }), { status: 200 }) : url.startsWith("/api/embeds") ? new Response(JSON.stringify({
      found: true, calendarId: "abc@group.calendar.google.com", timeZone: "America/Los_Angeles", recordings: [
        { date: "2026-10-20", topic: "Board meeting", uuid: "u1", shareUrl: "https://zoom.us/rec/share/abc", playUrl: "https://zoom.us/rec/play/abc", files: [{ type: "audio", name: "audio.m4a", path: "zoom/meetings/2026-10-20-abc/audio.m4a", doc: audioDoc }] },
        { date: "2026-09-15", topic: "Earlier meeting", uuid: "u0", shareUrl: "https://zoom.us/rec/share/old", playUrl: "", files: [] },
      ],
    }), { status: 200 }) : new Response(JSON.stringify({
      found: true, date: url.includes("date=") ? url.split("date=")[1] : "2026-10-20", today: "2026-10-03", noticeBy: "2026-10-16", executiveNoticeBy: "2026-10-18",
      items: [item], openCount: 1, executiveCount: 0, directors: ["A. Director", "B. Director"], decisions: [], agendaMarkdown: "# Agenda\n\n1. **Reserve loan not restored**", packetMarkdown: "# Board packet\n\n## 1. Reserve loan not restored\n\n**The question for the board.** Decide whether to restore", minutesTemplate: "# Minutes", notes: [],
      commands: { agendaDoc: "jason board --agenda <id> --date 2026-10-20 --doc --yes", packetDoc: "jason board --packet --date 2026-10-20 --doc --yes", minutesDraft: "jason board --minutes 2026-10-20", notice: "jason board --set <item id> --status \"on agenda\" --meeting 2026-10-20" },
      caveats: ["No action may be taken on an item not on the noticed agenda (CIV 4930)."], ...meeting,
    }), { status: 200 });
  }));
  return posts;
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
    const posts = mockFetch();
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
    // Zoom's share page is the original, a link in a new tab, never a frame
    const zoom = screen.getByRole("link", { name: /^Open in Zoom/ });
    expect(zoom).toHaveAttribute("href", "https://zoom.us/rec/share/abc");
    expect(zoom).toHaveAttribute("target", "_blank");
    expect(zoom).toHaveAttribute("rel", "noreferrer");
    expect(document.querySelector('iframe[src*="zoom.us"]')).toBeNull();
    // the kept audio is a Doc inline on file:<path> (P1: the screen's subject, one logged view on mount), played from
    // the view's short-lived link, never /api/file
    const region = await screen.findByRole("region", { name: audioDoc.name });
    await waitFor(() => expect(region.querySelector("audio")).not.toBeNull());
    const audio = region.querySelector("audio") as HTMLAudioElement;
    expect(audio.getAttribute("src")).toBe("/api/evidence/document/rec");
    expect(audio).toHaveAttribute("controls");
    expect(posts).toEqual([["/api/evidence/view", { address: audioDoc.address, document: "audio", by: "A. Director" }]]);
    expect(document.querySelector('audio[src*="/api/file"], a[href*="/api/file"]')).toBeNull();
    expect(screen.getByText(/under a litigation hold/)).toBeInTheDocument();
    expect(screen.queryByTitle("Earlier meeting")).not.toBeInTheDocument();
  });

  it("shows a held executive item by its 4935 subject, with no decision card, outside the private view", async () => {
    const held = { ...item, id: "executive-1", title: "An executive-session matter: a member's payment of assessments", ask: "", authority: "", category: "",
      agendaSession: "executive session", held: true, subject: "assessment_payment", general: "a member's payment of assessments" };
    mockFetch([], { items: [item, held], executiveCount: 1, executiveHeld: 1,
      executiveHeldNote: "1 executive-session item(s) listed by their Civil Code 4935 subject only (4935(e)); open the private view to see their titles." });
    render(<MeetingView />);
    expect(await screen.findByText(/listed by their Civil Code 4935 subject only/)).toBeInTheDocument();
    expect(screen.getByText(held.title)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Decisions/ }));
    expect(screen.getByText(/recorded in the private view/)).toBeInTheDocument();
    // one card for the open item and one for "another motion"; none for the held matter
    expect(screen.getAllByText(item.title, { selector: "strong" })).toHaveLength(1);
    expect(screen.queryByText(held.title, { selector: "strong" })).not.toBeInTheDocument();
  });
});
