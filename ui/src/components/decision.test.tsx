import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecisionCard } from "./DecisionCard";
import { tally } from "./RollCall";

describe("DecisionCard", () => {
  it("takes a motion and a roll call, shows the tally, and records through a confirm", async () => {
    const onSave = vi.fn();
    render(<DecisionCard title="Reserve loan not restored" directors={["A. Director", "B. Director", "C. Director"]} onSave={onSave} />);
    expect(screen.queryByRole("button", { name: "Record the decision" })).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Motion, as made"), "Move to restore $6,000 by March 1");
    await user.click(screen.getByLabelText("A. Director: aye"));
    await user.click(screen.getByLabelText("B. Director: aye"));
    await user.click(screen.getByLabelText("C. Director: no"));
    expect(screen.getByText(/2 aye · 1 no · 0 abstain · 0 absent · on their face the votes carry the motion/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Outcome, the board's word"), "approved");
    await user.click(screen.getByRole("button", { name: "Record the decision" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("2–1, approved");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const d = onSave.mock.calls[0][0];
    expect(d.motion).toBe("Move to restore $6,000 by March 1");
    expect(d.votes).toEqual({ "A. Director": "aye", "B. Director": "aye", "C. Director": "no" });
    expect(d.outcome).toBe("approved");
  });
  it("records a recusal as one: the row reads recused, no vote or absence is saved for it, and the save passes it", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<DecisionCard title="Painting contract" directors={["A. Director", "B. Director", "C. Director"]} initial={{ votes: { "C. Director": "absent" } }} onSave={onSave} />);
    await user.type(screen.getByLabelText("Motion, as made"), "Move to approve the painting contract");
    await user.click(screen.getByRole("checkbox", { name: "C. Director" }));
    expect(screen.getByText("recused")).toBeInTheDocument();
    expect(screen.getByLabelText("C. Director: aye")).toBeDisabled();
    await user.click(screen.getByLabelText("A. Director: aye"));
    await user.click(screen.getByLabelText("B. Director: aye"));
    expect(screen.getByText(/2 aye · 0 no · 0 abstain · 0 absent · 1 recused/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Record the decision" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("2–0, C. Director recused");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const d = onSave.mock.calls[0][0];
    expect(d.recused).toEqual(["C. Director"]);
    expect(d.votes).toEqual({ "A. Director": "aye", "B. Director": "aye" });
  });
  it("tallies", () => {
    expect(tally({ a: "aye", b: "abstain", c: "zzz" })).toEqual({ aye: 1, no: 0, abstain: 1, absent: 0 });
  });
});
