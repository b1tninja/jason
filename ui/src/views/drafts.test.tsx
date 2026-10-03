import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftsView } from "./DraftsView";

afterEach(() => vi.unstubAllGlobals());

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
