import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RequestForm } from "./RequestForm";

const kinds = [
  { record: "minutes", label: "Minutes of member, board, and committee meetings", citation: "CIV 5200(a)(8)" },
  { record: "membership_list", label: "Membership list", citation: "CIV 5200(a)(9)" },
];

afterEach(() => vi.unstubAllGlobals());

describe("RequestForm", () => {
  it("keeps Send disabled until a record is picked, then records the request and repeats the 5210 deadline", async () => {
    const posted: { url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      posted.push({ url, body: JSON.parse(String(init?.body)) });
      return new Response(JSON.stringify({
        id: "2026-10-03--unit-12", receivedOn: "2026-10-03", unit: "Unit 12", records: ["minutes"], dueBy: "2026-10-16",
        stages: [{ key: "received", label: "Request received", date: "2026-10-03", done: true }, { key: "current", label: "Current fiscal year records produced", date: "2026-10-16" }],
      }), { status: 200 });
    }));
    const user = userEvent.setup();
    render(<RequestForm kinds={kinds} today="2026-10-03" />);
    const send = screen.getByRole("button", { name: "Send request" });
    expect(send).toBeDisabled();
    expect(screen.getByText("Pick at least one record.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your unit"), "Unit 12");
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled(); // a unit alone is not a request
    await user.click(screen.getByLabelText(/Minutes of member/));
    expect(screen.getByRole("button", { name: "Send request" })).toBeEnabled();
    await user.click(screen.getByLabelText("Inspect in person"));
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("from Unit 12 for 1 record (Minutes of member, board, and committee meetings), inspect in person");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].url).toBe("/api/write/records-requests/new");
    expect(posted[0].body).toMatchObject({ receivedOn: "2026-10-03", unit: "Unit 12", via: "form", records: ["minutes"], delivery: "Inspect in person", years: [] });
    const notice = await screen.findByRole("status");
    expect(notice).toHaveClass("notice-good");
    expect(notice).toHaveTextContent("The association has until 2026-10-16 to produce the records (CIV 5210)");
    expect(notice).toHaveTextContent("Current fiscal year records produced by 2026-10-16");
  });

  it("asks for a stated purpose when the membership list is picked", async () => {
    const user = userEvent.setup();
    render(<RequestForm kinds={kinds} today="2026-10-03" />);
    await user.type(screen.getByLabelText("Your unit"), "Unit 12");
    await user.click(screen.getByLabelText(/Membership list/));
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
    expect(screen.getByText("The membership list asks for a stated purpose.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Purpose, in your words/), "to reach other members about the election");
    expect(screen.getByRole("button", { name: "Send request" })).toBeEnabled();
  });
});
