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
});
