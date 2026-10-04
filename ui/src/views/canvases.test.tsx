import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CanvasList, CanvasWorkspace } from "./CanvasesView";
import { resetServerSession } from "../lib/api";
import { DOC_WORDS } from "../components";

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
afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

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

describe("CanvasWorkspace: attachments and clip sources are Docs", () => {
  const photo = { address: "file:photos/east-bed.jpg", document: "image", name: "East bed", kind: "image", level: "P1", source: "File on disk" };
  const rules = { address: "drive:1ExampleDriveFile01", name: "Example rules", kind: "pdf", level: "P0", source: "Drive copy",
    original: { url: "https://docs.google.com/document/d/1ExampleDriveFile01/edit", label: "Open in Google" } };
  const recorded = { address: "file:governing/Example Declaration.pdf", document: "pdf", name: "Example Declaration.pdf", kind: "pdf", level: "P0", source: "Recorded copy" };
  const withDocs = {
    ...canvas,
    clips: [{ at: "2026-10-03T10:00:00+00:00", source: "file:governing/Example Declaration.pdf", text: "the recital", label: "", args: {}, doc: recorded },
      { at: "2026-10-03T10:00:00+00:00", source: "budget_status", text: "a row", label: "", args: {} }],
    attachments: [
      { kind: "doc", ref: "1ExampleDriveFile01", title: "Example rules", doc: rules },
      { kind: "image", ref: "photos/east-bed.jpg", title: "East bed", doc: photo },
      { kind: "calendar", ref: "abc@group.calendar.google.com", title: "Association calendar" },
    ],
  };
  function serve(session: object, view: { status: number; body: object }) {
    const posts: [string, unknown][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
      if (init?.method === "POST") {
        posts.push([url, JSON.parse(String(init.body))]);
        return url === "/api/evidence/view" ? json(view.body, view.status) : json(withDocs);
      }
      if (url.startsWith("/api/session")) return json(session);
      if (url.startsWith("/api/evidence?")) return json({ found: true, address: rules.address, label: rules.name, kind: "drive", sources: [], changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "", refreshable: null, documents: [] });
      if (url.includes("key=")) return json({ found: true, canvas: withDocs });
      return json({ found: false, note: "none" });
    }));
    return posts;
  }
  const IN = { signedIn: { name: "A Manager" }, signIn: { configured: true, start: "/auth/google" } };
  const imageView = { kind: "image", name: "East bed", readAt: "", url: "/api/evidence/document/p", expires: "", caveats: [] };

  it("renders each variant from the loader's references: a Drive card, a P1 photo inline (one view on mount), a clip chip", async () => {
    const posts = serve(IN, { status: 200, body: imageView });
    const { container } = render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    expect(await screen.findByRole("region", { name: "East bed" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview Example rules" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", rules.original.url);
    expect(screen.getByRole("button", { name: "Open Example Declaration.pdf" })).toBeInTheDocument();
    expect(screen.getByText("budget_status")).toBeInTheDocument();                       // a tool's name stays text
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: photo.address, document: "image", by: "A Manager" }]]));
    expect(container.querySelector("iframe")).toBeNull();                                 // the calendar waits for a click
    expect(screen.getByRole("button", { name: "Load Association calendar from calendar.google.com" })).toBeInTheDocument();
    expect(container.querySelector('a[href*="/api/file"], img[src*="/api/file"]')).toBeNull();
    expect(container.innerHTML).not.toMatch(/[A-Za-z]:\|"\/(?:Users|home)\//);
  });

  it("opening a clip's chip posts a view; signed out and not allowed say their words", async () => {
    let posts = serve(IN, { status: 403, body: { error: "The treasurer's office doesn't open this file." } });
    const { unmount } = render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Open Example Declaration.pdf" }));
    await waitFor(() => expect(posts.some(([u, b]) => u === "/api/evidence/view" && (b as { address: string }).address === recorded.address)).toBe(true));
    expect((await screen.findAllByText(/The treasurer's office doesn't open this file/)).length).toBeGreaterThan(0);
    unmount();
    posts = serve({ signedIn: null, signIn: { configured: true, start: "/auth/google" } }, { status: 200, body: imageView });
    render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Open Example Declaration.pdf" }));
    expect((await screen.findAllByText(new RegExp(DOC_WORDS.signedOut))).length).toBeGreaterThan(0);
    expect(posts).toEqual([]);
  });

  it("a recording under data/ is a Doc inline (a P2 one waits for Show the document), never a /api/file player", async () => {
    const recording = { address: "file:zoom/meetings/2099-01-01-abc/audio.m4a", document: "audio", name: "Board meeting (audio)", kind: "audio", level: "P2", source: "File on disk" };
    const audioView = { kind: "audio", name: "audio.m4a", readAt: "", url: "/api/evidence/document/r", expires: "", caveats: [] };
    const posts: [string, unknown][] = [];
    const canvas = { ...withDocs, attachments: [{ kind: "audio", ref: "zoom/meetings/2099-01-01-abc/audio.m4a", title: "Board meeting (audio)", doc: recording }] };
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return json(audioView); }
      if (url.startsWith("/api/session")) return json(IN);
      if (url.includes("key=")) return json({ found: true, canvas });
      return json({ found: false, note: "none" });
    }));
    const { container } = render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    const region = await screen.findByRole("region", { name: recording.name });
    expect(container.querySelector("audio")).toBeNull();
    await userEvent.click(await within(region).findByRole("button", { name: DOC_WORDS.show }));
    await waitFor(() => expect(region.querySelector("audio")).toHaveAttribute("src", "/api/evidence/document/r"));
    expect(posts).toEqual([["/api/evidence/view", { address: recording.address, document: "audio", by: "A Manager" }]]);
    expect(container.querySelector('audio[src*="/api/file"]')).toBeNull();
  });

  it("removing an attachment sends the others back without their references", async () => {
    const posts = serve(IN, { status: 200, body: imageView });
    render(<CanvasWorkspace keyName="pool-deck-bids" back={() => {}} />);
    await screen.findByRole("region", { name: "East bed" });
    await userEvent.click(screen.getAllByRole("button", { name: "remove from the canvas" })[2]);
    await waitFor(() => expect(posts.find(([u]) => u === "/api/canvases/pool-deck-bids")?.[1]).toEqual({ attachments: [
      { kind: "doc", ref: "1ExampleDriveFile01", title: "Example rules" }, { kind: "image", ref: "photos/east-bed.jpg", title: "East bed" }] }));
  });
});
