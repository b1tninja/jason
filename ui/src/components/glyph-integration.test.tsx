import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Badge } from "./Badge";
import { Pill } from "./Pill";
import { DueDate } from "./DueDate";
import { Timeline } from "./Timeline";
import { AuditLog } from "./AuditLog";
import { Findings } from "./Findings";
import { Caveats } from "./Caveats";
import { EmptyState } from "./States";
import { DataTable } from "./DataTable";
import { glyphForStatus } from "../lib/statusGlyph";
import type { AuditEntry } from "../lib/approvals";

const glyphs = (root: HTMLElement) => Array.from(root.querySelectorAll("svg[data-glyph]")).map((g) => g.getAttribute("data-glyph"));

describe("glyphForStatus", () => {
  it("takes the word before the tone, and gives a neutral word none", () => {
    expect(glyphForStatus("missing", "bad")).toBe("circle-dashed");
    expect(glyphForStatus("blocked", "warn")).toBe("octagon-alert");
    expect(glyphForStatus("approved", "good")).toBe("circle-check");
    expect(glyphForStatus("in review", "warn")).toBe("clock");
    expect(glyphForStatus("overdue", "bad")).toBe("triangle-alert");
    expect(glyphForStatus("closed", "neutral")).toBeUndefined();
  });
});

describe("Badge and Pill", () => {
  it("a Badge has no glyph unless it is given one, and the word stays its text", () => {
    const { container, rerender } = render(<Badge tone="good">3</Badge>);
    expect(glyphs(container)).toEqual([]);
    rerender(<Badge tone="good" glyph="circle-check">ready</Badge>);
    expect(glyphs(container)).toEqual(["circle-check"]);
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("a Pill carries the attention glyph for its word or tone, and can leave it off", () => {
    const { container, rerender } = render(<Pill word="approved" />);
    expect(glyphs(container)).toEqual(["circle-check"]);
    rerender(<Pill word="missing" />);
    expect(glyphs(container)).toEqual(["circle-dashed"]);
    rerender(<Pill word="closed" />);
    expect(glyphs(container)).toEqual([]);
    rerender(<Pill word="approved" glyph={false} />);
    expect(glyphs(container)).toEqual([]);
    rerender(<Pill word="closed" glyph="lock" />);
    expect(glyphs(container)).toEqual(["lock"]);
  });
});

describe("DueDate", () => {
  const today = new Date("2026-10-04T12:00:00");
  it("marks overdue and soon, and says nothing extra for a far date", () => {
    const { container, rerender } = render(<DueDate iso="2026-10-01" today={today} />);
    expect(glyphs(container)).toEqual(["triangle-alert"]);
    rerender(<DueDate iso="2026-10-10" today={today} />);
    expect(glyphs(container)).toEqual(["clock"]);
    rerender(<DueDate iso="2027-03-01" today={today} />);
    expect(glyphs(container)).toEqual([]);
  });
});

describe("Timeline and AuditLog", () => {
  it("takes an event's own glyph, else the attention glyph for its tone, else none", () => {
    const { container } = render(
      <Timeline events={[
        { id: "a", date: "2026-01-01", title: "Proposed", glyph: "proposal" },
        { id: "b", date: "2026-01-02", title: "Done", tone: "good" },
        { id: "c", date: "2026-01-03", title: "Noted" },
      ]} />,
    );
    const rows = within(container).getAllByRole("listitem");
    expect(glyphs(rows[0])).toEqual(["proposal"]);
    expect(glyphs(rows[1])).toEqual(["circle-check"]);
    expect(glyphs(rows[2])).toEqual([]);
  });

  it("an audit event shows what it was: planned, signed, applied, taken back", () => {
    const base = { actor: "person:Ana", at: "2026-10-01T10:00:00Z", hash: "h", prev: "", approval: "ap1" } as const;
    const entries = [
      { ...base, seq: 1, event: "plan.created", result: { added: 2 } },
      { ...base, seq: 2, event: "approval.submitted", result: "approved" },
      { ...base, seq: 3, event: "approval.applied", result: { applied: 2 } },
      { ...base, seq: 4, event: "approval.withdrawn" },
    ] as unknown as AuditEntry[];
    const { container } = render(<AuditLog entries={entries} approval="ap1" />);
    expect(glyphs(container)).toEqual(["proposal", "signature", "send", "undo-2"]);
  });
});

describe("Findings, Caveats, EmptyState", () => {
  it("each finding carries the question mark; a caveat the note mark", () => {
    const { container, rerender } = render(<Findings items={["a", "b"]} />);
    expect(glyphs(container)).toEqual(["circle-question-mark", "circle-question-mark"]);
    rerender(<Findings items={["a"]} glyph={false} />);
    expect(glyphs(container)).toEqual([]);
    rerender(<Caveats items={["one", "two"]} />);
    expect(glyphs(container)).toEqual(["info", "info"]);
    expect(screen.getByText("two")).toBeInTheDocument();
  });

  it("an empty state shows its screen's glyph at 32px only when given one", () => {
    const { container, rerender } = render(<EmptyState>No payments are waiting.</EmptyState>);
    expect(glyphs(container)).toEqual([]);
    rerender(<EmptyState glyph="receipt">No payments are waiting.</EmptyState>);
    const svg = container.querySelector("svg[data-glyph='receipt']");
    expect(svg).toHaveAttribute("width", "32px");
    expect(screen.getByText("No payments are waiting.")).toBeInTheDocument();
  });

  it("a glyph name that does not exist renders nothing and logs once", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<Badge glyph={"not-a-glyph" as never}>x</Badge>);
    expect(glyphs(container)).toEqual([]);
    expect(screen.getByText("x")).toBeInTheDocument();
    warn.mockRestore();
  });
});

describe("DataTable kinds", () => {
  interface Row { id: string; kind: string; amount: number; when: string }
  const rows: Row[] = [{ id: "1", kind: "Roofing", amount: 258400, when: "2026-06-01" }, { id: "2", kind: "Landscape", amount: -5000, when: "2026-06-02" }];

  it("a money column shows dollars from cents, right-aligned; a glyph column puts the mark beside the word", () => {
    const { container } = render(
      <DataTable<Row> rows={rows} rowKey={(r) => r.id} columns={[
        { key: "kind", header: "Kind", glyph: (r) => (r.kind === "Roofing" ? "hammer" : "sprout") },
        { key: "amount", header: "Amount", kind: "money" },
        { key: "when", header: "When", kind: "date" },
      ]} />,
    );
    const cells = container.querySelectorAll("tbody tr:first-child td");
    expect(cells[0].textContent).toBe("Roofing");
    expect(glyphs(cells[0] as HTMLElement)).toEqual(["hammer"]);
    expect(cells[1]).toHaveClass("num", "money-cell");
    expect(cells[1].textContent).toContain("2,584.00");
    expect(container.querySelector("tbody tr:nth-child(2) td:nth-child(2)")?.textContent).toMatch(/-.*50\.00|50\.00.*-|\(/);
    expect(cells[2]).toHaveClass("date");
  });
});
