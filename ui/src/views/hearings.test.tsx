import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HearingsView } from "./HearingsView";

afterEach(() => vi.unstubAllGlobals());

describe("HearingsView", () => {
  it("opens a hearing, records the decision through a confirm, then previews the notice with its command", async () => {
    const posts: unknown[] = [];
    const h = { key: "2026-10-20|123-main-st-12", address: "123 Main St #12", start: "2026-10-20T18:00:00", noticeBy: "2026-10-10", noticeOn: "2026-10-05", decisionByIfHeld: "2026-11-03", standing: "notice by 2026-10-10 (delivered 2026-10-05)", scheduled: true, problems: [], decision: null,
      stages: [{ key: "noticeBy", label: "Notice delivered by", date: "2026-10-10", done: true }, { key: "hearing", label: "Hearing", date: "2026-10-20" }, { key: "decisionBy", label: "Written decision by, if the board acts at the hearing", date: "2026-11-03" }] };
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify({ ...h, decision: { findings: "A $50 fine, waived if removed by December 1.", decidedOn: "2026-10-20", noticeDueBy: "2026-11-03", by: "Secretary", recorded: "2026-10-20T20:00:00+00:00", history: [] } }), { status: 200 }); }
      if (url.startsWith("/api/templates")) return new Response(JSON.stringify({ found: true, markdown: "# Notice of Decision\n\nA $50 fine, waived if removed by December 1.", open: ["OWNER_NAME"], command: "jason letter --template decision-notice --name 'Decision notice, 123 Main St #12' --set 'FINDINGS=A $50 fine, waived if removed by December 1.' --yes" }), { status: 200 });
      return new Response(JSON.stringify({ found: true, hearings: [h] }), { status: 200 });
    }));
    render(<HearingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(screen.getByRole("list", { name: "timeline" })).toHaveTextContent("Hearing");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Findings and the discipline, as decided"), "A $50 fine, waived if removed by December 1.");
    await user.type(screen.getByLabelText("Recorded by"), "Secretary");
    await user.click(screen.getByRole("button", { name: "Record the decision" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/hearings/2026-10-20%7C123-main-st-12");
    expect((posts[0] as unknown[])[1]).toEqual({ findings: "A $50 fine, waived if removed by December 1.", decidedOn: "2026-10-20", by: "Secretary" });
    expect(await screen.findByText(/notice due by/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Notice of Decision" })).toBeInTheDocument();
    expect(screen.getByText("Still open in the notice: owner name")).toBeInTheDocument();
    expect(screen.getByText(/jason letter --template decision-notice/)).toBeInTheDocument();
  });
});
