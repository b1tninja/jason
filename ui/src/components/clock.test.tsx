import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Clock } from "./Clock";

describe("Clock", () => {
  it("orders stages and marks past, next, overdue, and done", () => {
    const today = new Date("2026-10-03T12:00:00");
    render(<Clock today={today} stages={[
      { key: "decision", label: "Board decides", date: "2026-11-17", authority: "CIV 4360" },
      { key: "notice", label: "Notice to members", date: "2026-10-01", done: true },
      { key: "comment", label: "Comments close", date: "2026-11-16" },
      { key: "missed", label: "Something missed", date: "2026-09-20" },
    ]} />);
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("data-state"))).toEqual(["overdue", "done", "next", "ahead"]);
    expect(items[2]).toHaveTextContent("in 44d");
    expect(items[0]).toHaveTextContent("13d ago");
  });
});
