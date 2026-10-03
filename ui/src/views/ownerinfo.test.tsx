import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmList } from "../components";
import { OwnerInfoView } from "./OwnerInfoView";

afterEach(() => vi.unstubAllGlobals());

describe("ConfirmList", () => {
  it("gates its children on every row confirmed and needs a name", async () => {
    const onToggle = vi.fn();
    const { rerender } = render(<ConfirmList who="" rows={[{ key: "a", label: "A" }]} onToggle={onToggle}><p>NEXT</p></ConfirmList>);
    expect(screen.getByLabelText("confirm: A")).toBeDisabled();
    rerender(<ConfirmList who="S" rows={[{ key: "a", label: "A" }]} onToggle={onToggle}><p>NEXT</p></ConfirmList>);
    await userEvent.click(screen.getByLabelText("confirm: A"));
    expect(onToggle).toHaveBeenCalledWith(expect.objectContaining({ key: "a" }), true);
    expect(screen.queryByText("NEXT")).not.toBeInTheDocument();
    rerender(<ConfirmList who="S" rows={[{ key: "a", label: "A", by: "S", on: "2026-10-03T10:00:00" }]} onToggle={onToggle}><p>NEXT</p></ConfirmList>);
    expect(screen.getByText("NEXT")).toBeInTheDocument();
    expect(screen.getByText(/confirmed by S on 2026-10-03/)).toBeInTheDocument();
  });
});

describe("OwnerInfoView", () => {
  it("confirms a write with a name and then shows the apply command", async () => {
    const base = { found: true, savedAt: "2026-10-03T09:00:00+00:00", written: false, summary: { currentOwners: 2, deadlines: [{ what: "answers due", date: "2026-11-01", daysLeft: 29 }] },
      writes: [{ key: "member tag +|11|notice: email", kind: "member tag +", target: 11, label: "unit 12 owner", value: "notice: email", why: "answered this cycle", confirmedBy: "", confirmedOn: "" }],
      pending: 1, allConfirmed: false, toComplete: [{ submissionId: 901, unit: "12", name: "Owner Twelve", left: [] }], owners: [{ unit: "12", name: "Owner Twelve", status: "answered this cycle", delivery: "email", actions: [] }], command: "jason owner-info --apply --payhoa --yes", caveats: ["jason writes nothing from this page."] };
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify({ ...base, pending: 0, allConfirmed: true, writes: [{ ...base.writes[0], confirmedBy: "Secretary", confirmedOn: "2026-10-03T10:00:00+00:00" }] }), { status: 200 }); }
      return new Response(JSON.stringify(base), { status: 200 });
    }));
    render(<OwnerInfoView />);
    expect(await screen.findByText("unit 12 owner", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText("jason owner-info --apply --payhoa --yes")).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("your name"), "Secretary");
    await user.click(screen.getByLabelText(/confirm: member tag \+/));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/owner-info/member%20tag%20%2B%7C11%7Cnotice%3A%20email");
    expect((posts[0] as unknown[])[1]).toEqual({ by: "Secretary", confirmed: true });
    expect(await screen.findByText("jason owner-info --apply --payhoa --yes")).toBeInTheDocument();
    expect(screen.getByText("fully recorded")).toBeInTheDocument();
  });
});
