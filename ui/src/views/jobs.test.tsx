import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { JobsView } from "./JobsView";

const read = {
  id: 1, command: "gmail --sync", resource: "google", status: "queued", writes: false, confirmedBy: null, added: "2026-10-02T02:00:00",
  attempts: 0, maxAttempts: 3, started: null, finished: null, exitCode: null, note: null, summary: null,
};
const write = {
  id: 2, command: "board --sheet --yes", resource: "google", status: "failed", writes: true, confirmedBy: "T. Board", added: "2026-10-02T03:00:00",
  attempts: 1, maxAttempts: 1, started: "2026-10-02T03:01:00", finished: "2026-10-02T03:02:00", exitCode: 1, note: "waits for a person", summary: "sheet locked",
};

function mockFetch(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return new Response(JSON.stringify({ error: `no route ${url}` }), { status: 404 });
    return new Response(JSON.stringify(routes[key](init)), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
afterEach(() => vi.unstubAllGlobals());

describe("JobsView", () => {
  it("lanes jobs by status and marks a confirmed write", async () => {
    mockFetch({ "/api/jobs": () => ({ found: true, jobs: [read, write], byStatus: { queued: 1, failed: 1 } }) });
    render(<JobsView />);
    const queued = await screen.findByRole("region", { name: "queued" });
    expect(within(queued).getByText("jason gmail --sync")).toBeInTheDocument();
    const failed = screen.getByRole("region", { name: "failed" });
    expect(within(failed).getByText("jason board --sheet --yes")).toBeInTheDocument();
    expect(within(failed).getByText("writes · confirmed by T. Board")).toBeInTheDocument();
    expect(within(queued).queryByText(/confirmed by/)).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "done" })).toHaveTextContent("0");
    expect(screen.getByRole("region", { name: "cancelled" })).toHaveTextContent("0");
    expect(within(failed).getByText("exit 1")).toBeInTheDocument();
  });

  it("fetches one job's log when its card is clicked", async () => {
    const f = mockFetch({
      "/api/jobs?job=2": () => ({ found: true, job: write, log: ["syncing", "PermissionError: sheet locked"] }),
      "/api/jobs": () => ({ found: true, jobs: [read, write], byStatus: {} }),
    });
    const user = userEvent.setup();
    render(<JobsView />);
    await user.click(await screen.findByRole("button", { name: "job 2" }));
    expect(await screen.findByText(/PermissionError: sheet locked/)).toBeInTheDocument();
    await waitFor(() => expect(f.mock.calls.some(([url]) => String(url).startsWith("/api/jobs?job=2"))).toBe(true));
  });

  it("asks for every job when show all is checked", async () => {
    const f = mockFetch({ "/api/jobs": () => ({ found: true, jobs: [], byStatus: {} }) });
    render(<JobsView />);
    await screen.findByRole("region", { name: "queued" });
    await userEvent.click(screen.getByLabelText("show all"));
    await waitFor(() => expect(f.mock.calls.some(([url]) => String(url).startsWith("/api/jobs?all=1"))).toBe(true));
  });

  it("shows the tool's not-found note", async () => {
    mockFetch({ "/api/jobs": () => ({ found: false, note: "no job queue yet" }) });
    render(<JobsView />);
    expect(await screen.findByText("no job queue yet")).toBeInTheDocument();
  });
});
