import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftsView } from "./DraftsView";
import { resetServerSession } from "../lib/api";
import { DOC_WORDS } from "../components";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

describe("DraftsView", () => {
  it("shows a draft with its command, copies it, and never posts", async () => {
    const fetchSpy = vi.fn(async () => new Response(JSON.stringify({
      found: true, requests: 2, withNotice: 1, withOwnerThread: 1, emailedWithoutRequest: 1, caveats: ["No request is approved, denied, or assigned."],
      rows: [{ id: 7, form: "Maintenance", unit: "12", status: "open", created: "2026-09-01", title: "Leak under sink", topics: ["plumbing"], notices: [{ threadId: "t1", at: "2026-09-01T10:00:00", subject: "New request", how: "PayHOA submission notice" }], ownerThreads: [] }],
      drafts: [{ threadId: "18f2a", unit: "7", first: "2026-09-20", last: "2026-09-28", status: "awaiting us", topics: ["parking"], form: "General request", title: "Visitor parking tag", link: "https://mail.example/t/18f2a", message: "Raised by email by the owner of 7." }],
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);
    const writeText = vi.fn(async () => {});
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(<DraftsView />);
    expect(await screen.findByText("Visitor parking tag")).toBeInTheDocument();
    expect(screen.getByText("jason request-links --create 18f2a --yes")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copy command" }));
    expect(writeText).toHaveBeenCalledWith("jason request-links --create 18f2a --yes");
    expect(screen.getByText("Leak under sink")).toBeInTheDocument();
    expect(screen.getByText("No request is approved, denied, or assigned.")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.every((c) => !(c as unknown[])[1] || ((c as unknown[])[1] as RequestInit).method !== "POST")).toBe(true);
  });
});

describe("DraftsView: a request is its submission's Doc chip", () => {
  const doc = { address: "payhoa:submission:7", document: "submission", name: "Leak under sink", kind: "submission", level: "P2", source: "PayHOA" };
  const listing = { found: true, requests: 1, withNotice: 1, withOwnerThread: 0, emailedWithoutRequest: 0, caveats: [], drafts: [],
    rows: [{ id: 7, form: "Maintenance", unit: "12", status: "open", created: "2026-09-01", title: "Leak under sink", topics: [], notices: [], ownerThreads: [], doc }] };
  function serve(session: object, view: { status: number; body: object }) {
    const posts: [string, unknown][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posts.push([url, JSON.parse(String(init.body))]);
        return new Response(JSON.stringify(view.body), { status: view.status, headers: { "Content-Type": "application/json" } });
      }
      const body = url.startsWith("/api/session") ? session : listing;
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    return posts;
  }
  const IN = { signedIn: { name: "A Manager" }, signIn: { configured: true, start: "/auth/google" } };
  const submissionView = { kind: "submission", name: "Leak under sink", readAt: "", url: "", expires: "", caveats: [],
    submission: { form: "Maintenance", sections: [] } };

  it("renders the chip from the loader's reference; opening it posts one view", async () => {
    const posts = serve(IN, { status: 200, body: submissionView });
    render(<DraftsView />);
    const chip = await screen.findByRole("button", { name: "Open Leak under sink" });
    expect(chip).toHaveAccessibleDescription("Form submission");
    expect(posts).toEqual([]);
    await userEvent.click(chip);
    await screen.findByRole("dialog");
    expect(posts).toEqual([["/api/evidence/view", { address: "payhoa:submission:7", document: "submission", by: "A Manager" }]]);
  });

  it("signed out: says to sign in, and posts nothing", async () => {
    const posts = serve({ signedIn: null, signIn: { configured: true, start: "/auth/google" } }, { status: 200, body: submissionView });
    render(<DraftsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open Leak under sink" }));
    expect(await screen.findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(posts).toEqual([]);
  });

  it("not allowed: the server's reason", async () => {
    serve(IN, { status: 403, body: { error: "The treasurer's office doesn't open this request." } });
    render(<DraftsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open Leak under sink" }));
    expect(await screen.findByText(/The treasurer's office doesn't open this request/)).toBeInTheDocument();
  });

  it("renders no /api/file href, no outside frame, and no absolute path", async () => {
    serve(IN, { status: 200, body: submissionView });
    const { container } = render(<DraftsView />);
    await screen.findByRole("button", { name: "Open Leak under sink" });
    expect(container.querySelector('a[href*="/api/file"], img[src*="/api/file"], iframe')).toBeNull();
    expect(container.innerHTML).not.toMatch(/[A-Za-z]:\\|"\/(?:Users|home)\//);
  });
});
