import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { agoWords, listState, waitingWords } from "../lib/approvals";
import { PlanApprovals } from "./PlanApprovals";

/* A plan signed and not yet applied is a named state of its own (docs/console/approval-clarity.md, section 4). The server
   decides which plan waits and for how long (`waitingToApply`, `waitingHours`, `waitingStale`); the list only says it.
   Made-up plans only. */

afterEach(cleanup);

const base = {
  kind: "owner-info-tags", requestedBy: "A Manager", requestedAt: "2099-01-01T00:00:00+00:00", readAt: "2099-01-01T00:00:00+00:00",
  items: 12, byClass: { approvable: 12 }, byDecision: { approved: 12 }, byResult: {}, approved: 12, needsSecond: false,
};
const waiting = { ...base, id: "apr-20990101T000000-0001", title: "A signed plan", status: "approved", waitingToApply: true, waitingHours: 75, waitingStale: false, terminalOnly: false };
const stale = { ...base, id: "apr-20990101T000000-0002", title: "An old signed plan", status: "partially_approved", waitingToApply: true, waitingHours: 120, waitingStale: true, terminalOnly: false };
const open = { ...base, id: "apr-20990101T000000-0003", title: "A plan in review", status: "in_review", byDecision: {}, approved: 0, waitingToApply: false, waitingHours: null };
const applied = { ...base, id: "apr-20990101T000000-0004", title: "An applied plan", status: "applied", waitingToApply: false, waitingHours: null, byResult: { applied: 12 } };

describe("how long, in words", () => {
  it("says less than an hour, hours under two days, then days", () => {
    expect(agoWords(0.2)).toBe("less than an hour");
    expect(agoWords(1)).toBe("1 hour");
    expect(agoWords(47.9)).toBe("47 hours");
    expect(agoWords(48)).toBe("2 days");
    expect(agoWords(75)).toBe("3 days");
    expect(agoWords(null)).toBe("less than an hour");
  });
});

describe("waitingWords and listState", () => {
  it("says Signed, waiting to be applied with how long, from the server's field", () => {
    expect(waitingWords(waiting as never)).toBe("Signed, waiting to be applied · 3 days");
    expect(listState(waiting as never, "A Manager")).toBe("Signed, waiting to be applied · 3 days");
  });

  it("says a plan older than its kind allows will be planned again before it is applied", () => {
    expect(waitingWords(stale as never)).toBe("Signed 5 days ago; it will be planned again before it is applied");
  });

  it("adds that a terminal-only kind is applied at the terminal", () => {
    expect(waitingWords({ ...waiting, terminalOnly: true } as never)).toBe("Signed, waiting to be applied · 3 days · applied at the terminal");
  });

  it("is silent for a plan the server does not say is waiting, and the list falls back to the plan's state", () => {
    expect(waitingWords(open as never)).toBe("");
    expect(listState(open as never, "A Manager")).toBe("Needs review: 0 of 12 marked.");
    expect(listState(applied as never)).toMatch(/^Applied: 12 changes made/);
  });

  it("does not guess from the status alone: a signed plan the server has not marked keeps the plan's own sentence", () => {
    const unmarked = { ...waiting, waitingToApply: undefined };
    expect(listState(unmarked as never, "A Manager")).toBe("Signed, not applied yet. Nothing has been written.");
  });
});

describe("the Approvals list", () => {
  const show = (rows: unknown[]) => render(<PlanApprovals page={{ approvals: rows }} me="A Manager" open="" onOpen={() => undefined} />);

  it("shows Signed, waiting to be applied with how long in Where it stands, and says what it means above the list", () => {
    show([waiting, open, applied]);
    const table = screen.getByRole("table");
    const row = within(table).getByText("A signed plan").closest("tr")!;
    expect(within(row).getByText("Signed, waiting to be applied · 3 days")).toBeInTheDocument();
    expect(within(table).getByText("Needs review: 0 of 12 marked.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 plan is signed and waiting to be applied. Nothing has been written for it yet.");
  });

  it("counts several and reads a stale one as one that will be planned again", () => {
    show([waiting, stale]);
    expect(screen.getByRole("status")).toHaveTextContent("2 plans are signed and waiting to be applied. Nothing has been written for them yet.");
    expect(screen.getByText("Signed 5 days ago; it will be planned again before it is applied")).toBeInTheDocument();
  });

  it("shows no waiting notice when no plan is signed and waiting", () => {
    show([open, applied]);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText(/waiting to be applied/)).toBeNull();
  });
});
