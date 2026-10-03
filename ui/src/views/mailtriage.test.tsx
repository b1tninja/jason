import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MailTriageView } from "./MailTriageView";

afterEach(() => vi.unstubAllGlobals());

const data = {
  found: true, since: "2026-09-03", items: 3, byKind: { legal: 1, bank: 1, ad: 1 }, choices: ["scan", "forward", "shred", "discard", "keep"], chosen: 1,
  act: [{ mailId: "9001", received: "2026-10-01", sender: "Superior Court", kind: "legal", urgency: "act", evidence: ["summons"], deadlines: [{ date: "2099-10-31", label: "respond by" }], scanned: true, summary: ["A summons in a civil case."], choice: null }],
  review: [{ mailId: "9002", received: "2026-09-28", sender: "A Bank", kind: "bank", urgency: "review", evidence: [], deadlines: [], scanned: true, summary: [], choice: null }],
  unscanned: [{ mailId: "9003", received: "2026-09-30", sender: "Ad Co", kind: "ad", urgency: "file", evidence: [], deadlines: [], scanned: false, summary: [], choice: { mailId: "9003", choice: "discard", by: "Secretary", on: "2026-10-02T10:00:00+00:00", note: "", history: [] } }],
  caveats: ["jason scans, forwards, shreds, and discards nothing."],
};

describe("MailTriageView", () => {
  it("renders the lanes with each letter's facts and the recorded choice", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return new Response(JSON.stringify(data), { status: 200 }); }));
    render(<MailTriageView />);
    expect(await screen.findByText("Superior Court")).toBeInTheDocument();
    expect(urls[0]).toBe("/api/mail-triage?days=30");
    expect(screen.getByText(/jason scans, forwards, shreds, and discards nothing\. The choice/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Act (1)" })).toBeInTheDocument();
    const first = screen.getByRole("article", { name: "letter 9001" });
    expect(within(first).getByText("legal")).toBeInTheDocument();
    expect(within(first).getByText("act")).toBeInTheDocument();
    expect(within(first).getByText("2099-10-31")).toBeInTheDocument();
    expect(within(first).getByText("summons")).toBeInTheDocument();
    expect(within(first).getByText("Enter your name above to record a choice.")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: "Not scanned (1)" }));
    const letter = screen.getByRole("article", { name: "letter 9003" });
    expect(within(letter).getByText("discard")).toBeInTheDocument();
    expect(within(letter).getByText(/by Secretary on 2026-10-02/)).toBeInTheDocument();
    expect(within(letter).getByText("not scanned")).toBeInTheDocument();
  });

  it("records a choice through a confirm, posting to the mail id", async () => {
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify({ mailId: "9001", choice: "forward", by: "Treasurer", on: "2026-10-03T10:00:00+00:00", note: "", history: [] }), { status: 200 }); }
      return new Response(JSON.stringify(data), { status: 200 });
    }));
    render(<MailTriageView />);
    await screen.findByText("Superior Court");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("your name"), "Treasurer");
    const letter = screen.getByRole("article", { name: "letter 9001" });
    expect(within(letter).getAllByRole("button")).toHaveLength(5);
    await user.click(within(letter).getByRole("button", { name: "Forward" }));
    expect(within(letter).getByRole("group", { name: "Confirm" })).toHaveTextContent('Record "forward" for the letter from Superior Court');
    await user.click(within(letter).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/write/mail-triage/9001");
    expect((posts[0] as unknown[])[1]).toEqual({ choice: "forward", by: "Treasurer", note: "" });
    expect(await within(letter).findByText("forward")).toBeInTheDocument();
    expect(within(letter).getByText(/by Treasurer on 2026-10-03/)).toBeInTheDocument();
  });

  it("cancels a choice without posting", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MailTriageView />);
    await screen.findByText("Superior Court");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("your name"), "T");
    const letter = screen.getByRole("article", { name: "letter 9001" });
    await user.click(within(letter).getByRole("button", { name: "Shred" }));
    await user.click(within(letter).getByRole("button", { name: "Cancel" }));
    expect(within(letter).queryByRole("group", { name: "Confirm" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.every((c) => (c as unknown[])[1] === undefined || ((c as unknown[])[1] as RequestInit).method !== "POST")).toBe(true);
  });
});
