import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CanvasList, CanvasWorkspace } from "./CanvasesView";

const canvas = {
  key: "pool-deck-bids", title: "Pool deck bids", question: "Which bidder?", status: "research", matter: "", duty: "Money", notes: "three quotes",
  clips: [{ at: "2026-10-03T10:00:00+00:00", source: "budget_status", text: "Pool: $3,000 over budget", label: "the gap", args: { year: 2026 } }],
  links: [], attachments: [], checklist: [{ text: "find the resolution", done: false }], created: "2026-10-01T00:00:00+00:00", updated: "2026-10-03T00:00:00+00:00", history: ["2026-10-01: opened"],
};

function mockFetch(onPost: (url: string, body: unknown) => unknown) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") return new Response(JSON.stringify(onPost(url, JSON.parse(String(init.body)))), { status: 200 });
    if (url.includes("key=")) return new Response(JSON.stringify({ found: true, canvas }), { status: 200 });
    if (url.startsWith("/api/drive-files")) return new Response(JSON.stringify({ found: true, files: [{ id: "1A", name: "Minutes 2026-09", path: "Board", kind: "doc", link: "" }] }), { status: 200 });
    if (url.startsWith("/api/photos")) return new Response(JSON.stringify({ found: false, note: "no albums" }), { status: 200 });
    if (url.startsWith("/api/embeds")) return new Response(JSON.stringify({ found: true, calendarId: "abc@group.calendar.google.com", timeZone: "America/Los_Angeles", recordings: [
      { date: "2026-10-20", topic: "Board meeting", uuid: "u1", shareUrl: "https://zoom.us/rec/share/abc", playUrl: "https://zoom.us/rec/play/abc", files: [{ type: "audio", name: "audio_only.m4a", path: "zoom/2026-10-20/audio_only.m4a" }, { type: "video", name: "shared_screen.mp4", path: "zoom/2026-10-20/shared_screen.mp4" }] },
    ] }), { status: 200 });
    return new Response(JSON.stringify({ found: true, count: 1, statuses: ["research", "preparing", "on agenda", "done"], canvases: [{ ...canvas, clips: 1, notes: "" }] }), { status: 200 });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
afterEach(() => vi.unstubAllGlobals());

describe("CanvasList", () => {
  it("lanes canvases by status and opens one", async () => {
    mockFetch(() => ({}));
    const go = vi.fn();
    render(<CanvasList go={go} />);
    expect(await screen.findByRole("region", { name: "research" })).toHaveTextContent("Pool deck bids");
    expect(screen.getByRole("region", { name: "done" })).toHaveTextContent("0");
    await userEvent.click(screen.getByRole("button", { name: "Pool deck bids" }));
    expect(go).toHaveBeenCalledWith("pool-deck-bids");
  });
});

describe("CanvasWorkspace", () => {
  it("saves only the changed fields, keeps a clip, and ticks a task", async () => {
    const posts: unknown[] = [];
    mockFetch((url, body) => { posts.push([url, body]); return { ...canvas, ...(body as object), clips: (body as { clip?: unknown }).clip ? [...canvas.clips, { at: "2026-10-03T11:00:00+00:00", ...(body as { clip: object }).clip, args: {} }] : canvas.clips }; });
    render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    expect(await screen.findByText("Pool: $3,000 over budget")).toBeInTheDocument();
    expect(screen.getByText(/No board item yet/)).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Notes \(Markdown/), " plus a fourth");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(posts[0]).toEqual(["/api/canvases/pool-deck-bids", { notes: "three quotes plus a fourth" }]));
    await user.type(screen.getByLabelText("Text"), "Reserve balance $482,100.33");
    await user.type(screen.getByLabelText("Source"), "budget_status");
    await user.click(screen.getByRole("button", { name: "Keep clip" }));
    await waitFor(() => expect((posts[1] as unknown[])[1]).toEqual({ clip: { source: "budget_status", label: "", text: "Reserve balance $482,100.33" } }));
    expect(await screen.findByText("Reserve balance $482,100.33")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox"));
    await waitFor(() => expect((posts[2] as unknown[])[1]).toEqual({ checklist: [{ text: "find the resolution", done: true }] }));
  });

  it("offers the new kinds and picks the calendar, a Zoom recording, and its audio", async () => {
    mockFetch(() => canvas);
    render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    await screen.findByText("Pool: $3,000 over budget");
    const kind = screen.getByLabelText("Kind") as HTMLSelectElement;
    const values = Array.from(kind.options).map((o) => o.value);
    expect(values).toEqual(expect.arrayContaining(["calendar", "zoom", "audio", "map", "chart", "thread"]));
    expect(screen.getByRole("option", { name: "Sheets chart (published chart link, or Sheet id)" })).toBeInTheDocument();
    const user = userEvent.setup();
    const ref = () => (screen.getByLabelText(/Link, Google file id, or path under data\//) as HTMLInputElement).value;
    await user.click(await screen.findByRole("button", { name: "The association's calendar" }));
    expect(kind.value).toBe("calendar");
    expect(ref()).toBe("abc@group.calendar.google.com");
    await user.click(screen.getByRole("button", { name: "Board meeting" }));
    expect(kind.value).toBe("zoom");
    expect(ref()).toBe("https://zoom.us/rec/share/abc");
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("Board meeting (2026-10-20)");
    await user.click(screen.getByRole("button", { name: "audio_only.m4a" }));
    expect(kind.value).toBe("audio");
    expect(ref()).toBe("zoom/2026-10-20/audio_only.m4a");
    expect(screen.queryByRole("button", { name: "shared_screen.mp4" })).not.toBeInTheDocument();
  });
});
