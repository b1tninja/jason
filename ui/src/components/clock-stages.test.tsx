import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Clock, orderStages } from "./Clock";

const today = new Date("2026-10-03T12:00:00");

describe("Clock with actors, evidence, and decisions", () => {
  it("keeps an undated stage in its given place between dated ones", () => {
    const ordered = orderStages([
      { key: "received", date: "2026-08-10" },
      { key: "decide" },                         // no date until the step before it happens
      { key: "produce", date: "2026-08-24" },
      { key: "early", date: "2026-08-01" },      // out of order: dated stages still sort among themselves
    ]);
    expect(ordered.map((s) => s.key)).toEqual(["early", "decide", "received", "produce"]);
  });

  it("marks a decision with the warn diamond and shows who, the authority, the note, and the evidence", () => {
    render(<Clock today={today} stages={[
      { key: "received", label: "Written request received", date: "2026-08-10", done: true, who: "manager", authority: "CIV 5205(a)", evidence: ["inbox: records request, unit 31"] },
      { key: "decide", label: "Records identified and located", who: "board", authority: "CIV 5200", decision: true, note: "Neither record is in the library." },
      { key: "produce", label: "Produce within 10 business days", date: "2026-08-24", who: "manager", authority: "CIV 5210(b)(1)" },
      { key: "log", label: "Log the delivery", who: "manager" },
    ]} />);
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.querySelector("strong")?.textContent)).toEqual(["Written request received", "Records identified and located", "Produce within 10 business days", "Log the delivery"]);
    expect(items.map((li) => li.getAttribute("data-state"))).toEqual(["done", "next", "overdue", "ahead"]);
    expect(items[1]).toHaveAttribute("data-decision", "true");
    expect(items[1]).toHaveClass("clock-decision");
    expect(items[1]).toHaveTextContent("the board decides");
    expect(items[1]).toHaveTextContent("board · CIV 5200");
    expect(items[1]).toHaveTextContent("Neither record is in the library.");
    expect(items[1]).toHaveTextContent("no date yet");
    expect(items[0]).toHaveTextContent("manager · CIV 5205(a)");
    expect(items[0].querySelector("code.chip")).toHaveTextContent("inbox: records request, unit 31");
    expect(items[0].textContent).not.toContain("Evidence:");
    expect(items[2]).toHaveTextContent("40d ago");
    items.forEach((li) => expect(li.querySelector(".clock-marker")).not.toBeNull());
  });
});
