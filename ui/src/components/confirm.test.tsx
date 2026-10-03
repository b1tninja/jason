import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Confirm } from "./Confirm";

describe("Confirm", () => {
  it("arms into a stamp with its label on top, the summary first, and acts only on the second click", async () => {
    const onConfirm = vi.fn();
    render(<Confirm summary="Record the release with the County Recorder." onConfirm={onConfirm} label="Record">Record and mail</Confirm>);
    await userEvent.click(screen.getByRole("button", { name: "Record and mail" }));
    const stamp = screen.getByRole("group", { name: "Record" });
    expect(stamp.firstElementChild).toHaveClass("confirm-label");
    expect(stamp.firstElementChild).toHaveTextContent("Record");
    expect(stamp.querySelector(":scope > div")).toHaveTextContent("Record the release with the County Recorder.");
    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("is labelled Confirm by default", async () => {
    render(<Confirm summary="Save the board fields." onConfirm={() => {}}>Save</Confirm>);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Confirm");
  });
});
