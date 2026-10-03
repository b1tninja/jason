import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RegisterGrid, cellText, type RegisterColumn } from "../components/RegisterGrid";
import { RegisterList, RegisterPage, RegistersView } from "./RegistersView";

afterEach(() => vi.unstubAllGlobals());

const columns: RegisterColumn[] = [
  { name: "id", owner: "jason", kind: "text", choices: [] },
  { name: "title", owner: "jason", kind: "text", choices: [] },
  { name: "amount", owner: "jason", kind: "money", choices: [] },
  { name: "status", owner: "board", kind: "choice", choices: ["open", "done"] },
  { name: "done", owner: "board", kind: "checkbox", choices: [] },
  { name: "due", owner: "board", kind: "date", choices: [] },
  { name: "notes", owner: "board", kind: "text", choices: [] },
];
const rows = [
  { id: "w-1", title: "First", amount: 12.5, status: "open", done: "", due: "", notes: "" },
  { id: "w-2", title: "Second", amount: 0, status: "", done: true, due: "2026-10-20", notes: "n", pendingSync: true, pendingColumns: ["done"] },
];
const log = [{ seen: "2026-10-03T10:00:00+00:00", key: "w-2", column: "done", before: "", after: true, by: "Secretary" }];
const one = { found: true, key: "widgets", title: "Widgets", confidential: false, about: "made up", savedAt: "2026-10-03T09:00:00+00:00", columns, keyColumn: "id", rows, log, pending: 1, inSpecification: true, syncCommand: "jason registers --sync widgets", caveats: ["Until then the Sheet is behind."] };
const listing = { found: true, count: 2, registers: [
  { key: "widgets", title: "Widgets", tab: "Widgets", confidential: false, about: "", columns, boardColumns: ["status", "done", "due", "notes"], snapshot: true, savedAt: "2026-10-03T09:00:00+00:00", rows: 2, pending: 1 },
  { key: "holds", title: "Legal hold", tab: "Holds", confidential: true, about: "", columns: [], boardColumns: ["sent"], snapshot: false, savedAt: null, rows: 0, pending: 0 },
], caveats: ["The Sheet catches up at the next sync."] };

function mockFetch(onPost: (url: string, body: unknown) => unknown) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const out = onPost(url, JSON.parse(String(init.body)));
      const err = (out as { error?: string }).error;
      return new Response(JSON.stringify(out), { status: err ? 400 : 200 });
    }
    if (url.includes("key=")) return new Response(JSON.stringify(one), { status: 200 });
    return new Response(JSON.stringify(listing), { status: 200 });
  });
  vi.stubGlobal("fetch", f);
  return f;
}

describe("cellText", () => {
  it("shows each kind as the Sheet does", () => {
    expect(cellText("checkbox", true)).toBe("yes");
    expect(cellText("checkbox", "")).toBe("");
    expect(cellText("money", 1250.5)).toBe("$1,250.50");
    expect(cellText("date", "2026-10-20")).toBe("2026-10-20");
  });
});

describe("RegisterGrid", () => {
  it("renders jason columns plain and the board's with an edit control, and the log", () => {
    render(<RegisterGrid registerKey="widgets" columns={columns} rows={rows} log={log} />);
    const first = screen.getByText("w-1").closest("tr")!;
    expect(within(first).getByText("First")).toBeInTheDocument();
    expect(within(first).getByText("$12.50")).toBeInTheDocument();
    expect(within(first).queryByRole("button", { name: "Edit title for w-1" })).toBeNull();
    expect(within(first).queryByRole("button", { name: "Edit amount for w-1" })).toBeNull();
    expect(within(first).getByRole("button", { name: "Edit status for w-1" })).toBeInTheDocument();
    expect(within(first).getByRole("button", { name: "Edit notes for w-1" })).toBeInTheDocument();
    expect(screen.getByText("pending sync")).toBeInTheDocument();
    expect(screen.getByText("Log (1)")).toBeInTheDocument();
    expect(screen.getByText("Secretary")).toBeInTheDocument();
  });

  it("edits a choice column through the confirm and posts the right body", async () => {
    const posts: [string, unknown][] = [];
    mockFetch((url, body) => { posts.push([url, body]); return { key: "widgets", rowKey: "w-1", column: "status", row: { ...rows[0], status: "done", pendingSync: true, pendingColumns: ["status"] } }; });
    const onSaved = vi.fn();
    render(<RegisterGrid registerKey="widgets" columns={columns} rows={rows} log={[]} by="Secretary" onSaved={onSaved} />);
    const user = userEvent.setup();
    const first = screen.getByText("w-1").closest("tr")!;
    await user.click(within(first).getByRole("button", { name: "Edit status for w-1" }));
    await user.selectOptions(within(first).getByLabelText("status"), "done");
    await user.click(within(first).getByRole("button", { name: "Save" }));
    expect(within(first).getByRole("group", { name: "Confirm" })).toHaveTextContent("open → done");
    await user.click(within(first).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0][0]).toBe("/api/write/registers/widgets|w-1");
    expect(posts[0][1]).toEqual({ column: "status", value: "done", by: "Secretary" });
    expect(onSaved).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(within(first).getByText("done")).toBeInTheDocument());
    expect(within(first).getByText("pending sync")).toBeInTheDocument();
  });

  it("shows the server's refusal and keeps the editor open", async () => {
    mockFetch(() => ({ error: "status is one of open, done" }));
    render(<RegisterGrid registerKey="widgets" columns={columns} rows={rows} log={[]} />);
    const user = userEvent.setup();
    const first = screen.getByText("w-1").closest("tr")!;
    await user.click(within(first).getByRole("button", { name: "Edit notes for w-1" }));
    await user.type(within(first).getByLabelText("notes"), "call");
    await user.click(within(first).getByRole("button", { name: "Save" }));
    await user.click(within(first).getByRole("button", { name: "Yes, do it" }));
    expect(await within(first).findByText("status is one of open, done")).toBeInTheDocument();
    expect(within(first).getByLabelText("notes")).toHaveValue("call");
  });
});

describe("RegistersView", () => {
  it("lists the registers with their snapshots and opens one", async () => {
    mockFetch(() => ({}));
    const go = vi.fn();
    render(<RegisterList go={go} />);
    expect(await screen.findByText("Registers (2)")).toBeInTheDocument();
    const widgets = screen.getByText("Widgets").closest("tr")!;
    expect(within(widgets).getByText("2026-10-03 09:00")).toBeInTheDocument();
    expect(within(widgets).getByText("1")).toBeInTheDocument();
    const holds = screen.getByText("Legal hold").closest("tr")!;
    expect(within(holds).getByText("none yet")).toBeInTheDocument();
    expect(within(holds).getByText("confidential")).toBeInTheDocument();
    expect(screen.getByText("The Sheet catches up at the next sync.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Widgets" }));
    expect(go).toHaveBeenCalledWith("widgets");
  });

  it("shows one register's grid, the sync command, and the caveats", async () => {
    const f = mockFetch(() => ({}));
    render(<RegisterPage keyName="widgets" back={() => undefined} />);
    expect(await screen.findByText("Widgets")).toBeInTheDocument();
    expect(f).toHaveBeenCalledWith("/api/registers?key=widgets", expect.anything());
    expect(screen.getByText("jason registers --sync widgets")).toBeInTheDocument();
    expect(screen.getByText("1 pending sync")).toBeInTheDocument();
    expect(screen.getByText("Until then the Sheet is behind.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit status for w-1" })).toBeInTheDocument();
  });

  it("routes by hash", async () => {
    mockFetch(() => ({}));
    window.location.hash = "/registers";
    render(<RegistersView />);
    expect(await screen.findByText("Registers (2)")).toBeInTheDocument();
    window.location.hash = "";
  });
});
