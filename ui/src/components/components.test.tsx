import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, Money, Tabs, ErrorNotice } from "./index";
import { DigestView } from "../DigestView";
import { formatCents } from "../lib/format";

describe("formatCents", () => {
  it("formats integer cents", () => {
    expect(formatCents(6120)).toBe("$61.20");
    expect(formatCents(-5)).toBe("-$0.05");
    expect(formatCents(123456789)).toBe("$1,234,567.89");
  });
});

describe("DataTable", () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ name: `unit ${7 - i}`, owedCents: i * 100 }));
  const cols = [
    { key: "name", header: "Name" },
    { key: "owedCents", header: "Owed", align: "right" as const, render: (r: (typeof rows)[0]) => <Money cents={r.owedCents} /> },
  ];
  it("sorts and filters", async () => {
    const user = userEvent.setup();
    render(<DataTable rows={rows} columns={cols} />);
    await user.click(screen.getByRole("button", { name: "Name" }));
    expect(within(screen.getAllByRole("row")[1]).getByText("unit 1")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Filter"), "unit 3");
    expect(screen.getAllByRole("row")).toHaveLength(2);
    await user.clear(screen.getByLabelText("Filter"));
    await user.type(screen.getByLabelText("Filter"), "zzz");
    expect(screen.getByText("No rows match.")).toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("switches panels", async () => {
    const onChange = vi.fn();
    render(<Tabs active="a" onChange={onChange} tabs={[{ id: "a", label: "A", content: "pa" }, { id: "b", label: "B", content: "pb" }]} />);
    expect(screen.getByRole("tabpanel")).toHaveTextContent("pa");
    await userEvent.click(screen.getByRole("tab", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});

describe("DigestView", () => {
  it("renders scalars as stats and rows as tables, cents as dollars", () => {
    render(<DigestView digest={{ openLiens: 3, owners: [{ unit: "A", pastDueCents: 250000 }] }} />);
    expect(screen.getByText("Open Liens")).toBeInTheDocument();
    expect(screen.getByText("$2,500.00")).toBeInTheDocument();
  });
});

describe("ErrorNotice", () => {
  it("retries", async () => {
    const retry = vi.fn();
    render(<ErrorNotice error="boom" onRetry={retry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });
});
