import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type Column } from "./DataTable";

interface Row { id: string; unit: string; due: string }
const rows: Row[] = [
  { id: "a", unit: "Unit 7", due: "2026-10-16" },
  { id: "b", unit: "Unit 12", due: "2026-11-02" },
];
const cols: Column<Row>[] = [
  { key: "unit", header: "Unit" },
  { key: "due", header: "Due", kind: "date" },
];

describe("DataTable selection", () => {
  it("selects a whole row by click and by Enter, and marks it", async () => {
    const onSelect = vi.fn();
    const { rerender } = render(<DataTable rows={rows} columns={cols} rowKey={(r) => r.id} onSelect={onSelect} />);
    const body = screen.getAllByRole("row").slice(1);
    expect(body.every((tr) => tr.getAttribute("aria-selected") === "false")).toBe(true);
    await userEvent.click(within(body[1]).getByText("Unit 12"));
    expect(onSelect).toHaveBeenCalledWith(rows[1]);
    body[0].focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith(rows[0]);
    rerender(<DataTable rows={rows} columns={cols} rowKey={(r) => r.id} onSelect={onSelect} selectedKey="b" />);
    const after = screen.getAllByRole("row").slice(1);
    expect(after[1]).toHaveAttribute("aria-selected", "true");
    expect(after[1]).toHaveClass("selected");
    expect(after[0]).toHaveAttribute("aria-selected", "false");
  });

  it("gives a date column the date class and no selection attributes without onSelect", () => {
    render(<DataTable rows={rows} columns={cols} />);
    const cell = screen.getByText("2026-10-16");
    expect(cell).toHaveClass("date");
    expect(screen.getAllByRole("row")[1]).not.toHaveAttribute("aria-selected");
    expect(screen.getAllByRole("row")[1]).not.toHaveAttribute("tabindex");
  });
});
