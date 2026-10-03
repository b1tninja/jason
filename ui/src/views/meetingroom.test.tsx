import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { roomData } from "./meetingroom.fixture";
import { MeetingRoomView, hashQuery, script, stageContent } from "./MeetingRoomView";

function mockFetch(routes: Record<string, (init?: RequestInit, url?: string) => unknown>) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return new Response(JSON.stringify({ error: `no route ${url}` }), { status: 404 });
    const out = routes[key](init, url);
    if (out instanceof Response) return out;
    return new Response(JSON.stringify(out), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
afterEach(() => { vi.unstubAllGlobals(); window.location.hash = ""; });

describe("MeetingRoomView", () => {
  it("shows the stage with the host panel, and moves to the next item through a confirm that logs the transition", async () => {
    const posted: unknown[] = [];
    let data = roomData({}, { current: 0, calledToOrder: "", log: [] });
    mockFetch({
      "/api/write/meeting-room/2026-10-21": (init) => { const b = JSON.parse(String(init?.body)); posted.push(b); if (b.action === "go_to") data = roomData({}, { ...data.room, current: b.item }); return data.room; },
      "/api/meeting-room": () => data,
    });
    const user = userEvent.setup();
    render(<MeetingRoomView />);
    expect(await screen.findByRole("heading", { name: "Call to order and roll call" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Meeting stage" })).toHaveTextContent("4 of 5 directors present. A quorum is 3.");
    expect(screen.getByLabelText("Host panel")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "jason presents" })).toHaveAttribute("aria-checked", "true");
    await user.type(screen.getByLabelText("Recording as"), "S. Clerk");
    await user.click(screen.getByRole("button", { name: "Next item →" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent('log the call to order with 4 of 5 directors present (quorum 3), then open "Open forum"');
    expect(posted).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted.map((p) => (p as { action: string }).action)).toEqual(["call_to_order", "go_to"]));
    expect(posted[1]).toMatchObject({ by: "S. Clerk", item: 1, directors: data.directors });
    expect(await screen.findByRole("heading", { name: "Open forum" })).toBeInTheDocument();
    expect(screen.getByText("The chair runs the meeting.")).toBeInTheDocument();
  });

  it("gives members the stage alone with a live badge when the hash says audience=owner", async () => {
    window.location.hash = "/meeting-room?audience=owner&date=2026-10-21";
    expect(hashQuery().get("audience")).toBe("owner");
    const f = mockFetch({ "/api/meeting-room": () => roomData() });
    render(<MeetingRoomView />);
    expect(await screen.findByRole("heading", { name: "Renew the landscape contract" })).toBeInTheDocument();
    expect(String(f.mock.calls[0][0])).toBe("/api/meeting-room?date=2026-10-21");
    expect(screen.getByText("live", { selector: ".badge" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Host panel")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next item →" })).not.toBeInTheDocument();
    expect(screen.getByText(/You are watching the open session/)).toBeInTheDocument();
  });

  it("shows a write's refusal and the tool's not-found note", async () => {
    mockFetch({
      "/api/write/meeting-room/2026-10-21": () => new Response(JSON.stringify({ error: "no quorum: 2 directors present, 3 needed" }), { status: 400 }),
      "/api/meeting-room": () => roomData(),
    });
    const user = userEvent.setup();
    render(<MeetingRoomView />);
    await screen.findByRole("heading", { name: "Renew the landscape contract" });
    await user.type(screen.getByLabelText("Recording as"), "S. Clerk");
    await user.click(screen.getByRole("button", { name: "Next item →" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no quorum: 2 directors present, 3 needed");
    vi.unstubAllGlobals();
    mockFetch({ "/api/meeting-room": () => ({ found: false, note: "date is YYYY-MM-DD" }) });
    render(<MeetingRoomView />);
    expect(await screen.findByText("date is YYYY-MM-DD")).toBeInTheDocument();
  });

  it("picks the stage content and the script for each kind of item", () => {
    const d = roomData();
    expect(stageContent(d, d.items[0], {}, 0, 0)).toMatchObject({ kind: "attendance", quorum: "4 of 5 directors present. A quorum is 3." });
    expect(stageContent(d, d.items[1], {}, 61, 2)).toMatchObject({ kind: "countdown", seconds: 61 });
    expect(stageContent(d, d.items[2], {}, 0, 0)).toMatchObject({ kind: "motion", text: "Move to approve the contract with Vendor A.", mover: "" });
    expect(stageContent(d, d.items[2], { options: true }, 0, 0)).toMatchObject({ kind: "options" });
    expect(stageContent(d, d.items[2], { packet: d.items[2].packet[0] }, 0, 0)).toMatchObject({ kind: "packet" });
    expect(stageContent(d, d.items[3], {}, 0, 0)).toMatchObject({ kind: "adjourned" });
    expect(script(d, d.items[2])).toBe("Item 1, Renew the landscape contract. Two bids in the packet. H. Quinn has disclosed an interest and will not vote. The proposed motion is on the screen.");
    expect(script(d, d.items[0])).toMatch(/so the board has a quorum\.$/);
  });
});
