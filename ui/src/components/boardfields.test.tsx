import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BoardFields } from "./BoardFields";

const item = { id: "reserve-loan", status: "open", owner: "", meeting: "", notes: "", history: ["2026-09-01: opened by jason"] };

afterEach(() => vi.unstubAllGlobals());

describe("BoardFields", () => {
  it("says No changes until a field differs, then lists Label: old → new and ends with the scope line", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      posted.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify({ ...item, status: "on agenda", owner: "D. Okafor", history: [...item.history, "2026-10-03: status open -> on agenda"] }), { status: 200 });
    }));
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(<BoardFields item={item} onSaved={onSaved} />);
    expect(screen.getByText("No changes.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save board fields" })).toBeNull();
    await user.selectOptions(screen.getByLabelText("Status"), "on agenda");
    await user.type(screen.getByLabelText("Owner"), "D. Okafor");
    expect(screen.queryByText("No changes.")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Save board fields" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    expect(confirm).toHaveTextContent("Status: open → on agenda");
    expect(confirm).toHaveTextContent("Owner: (blank) → D. Okafor");
    expect(confirm.querySelector(":scope > div")?.textContent?.trim().endsWith("Saved to the board fields only.")).toBe(true); // the summary, before the buttons
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toEqual([{ status: "on agenda", owner: "D. Okafor" }]));
    const saved = onSaved.mock.calls[0][0];
    expect(saved.status).toBe("on agenda");
    expect(saved.history).toHaveLength(2); // the save is one more line on the trail
  });

  it("discards a draft back to the item", async () => {
    const user = userEvent.setup();
    render(<BoardFields item={item} onSaved={vi.fn()} />);
    await user.type(screen.getByLabelText("Meeting"), "2026-10-21");
    await user.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByLabelText("Meeting")).toHaveValue("");
    expect(screen.getByText("No changes.")).toBeInTheDocument();
  });
});
