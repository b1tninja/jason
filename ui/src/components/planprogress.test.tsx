/// <reference types="vite/client" />
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import appliedJson from "../../../tests/fixtures/approvals/example-village-applied.json";
import { ApproveBar } from "./ApproveBar";
import { PlanProgress, currentStep, terminalCommand } from "./PlanProgress";
import { PlanReview } from "./PlanReview";
import { applyCounts, applyCountsWords, planState, systemWord, writtenTo, type Approval, type KindFacts } from "../lib/approvals";

const planned = () => structuredClone(plannedJson) as unknown as Approval;
const applied = () => structuredClone(appliedJson) as unknown as Approval;
const NOW = "2026-10-03T19:00:00+00:00";
const A = { name: "A Manager", at: NOW, fingerprint: "f", role: "manager", via: "console" as const };
const B = { name: "B Director", at: "2026-10-03T19:30:00+00:00", fingerprint: "f" };

const KIND: KindFacts = {
  key: "owner-info-tags", title: "Owner information tags", system: "payhoa", risk: "R2", riskWords: "member-facing record",
  approver: "one person", twoPerson: false, reversible: "a tag removed again", maxAgeHours: 24,
};
const MAIL: KindFacts = {
  ...KIND, key: "payhoa-mailroom-send", title: "Mailroom", twoPerson: true, terminalOnly: true,
  cli: "jason mailroom --send --yes --expect FINGERPRINT --approval ID",
};

/** Every approvable change marked approved by A Manager. */
function marked(): Approval {
  const a = planned();
  for (const i of a.items) if (i.class === "approvable") Object.assign(i, { decision: "approved", decidedBy: "A Manager", decidedAt: NOW });
  return { ...a, status: "in_review" };
}
/** Marked and signed by A Manager: waiting to be applied (or for a second signature). */
const signed = (): Approval => ({ ...marked(), status: "approved", first: A });
const bothSigned = (): Approval => ({ ...signed(), second: B });
const current = (container: HTMLElement) => container.querySelector("[aria-current=step] .plan-step-name")?.textContent ?? null;
const stepNames = (container: HTMLElement) => [...container.querySelectorAll(".plan-step-name")].map((e) => e.textContent);

describe("the stage words", () => {
  it("never uses Approve for the signing button: it says Sign this plan, and that signing makes no change", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    const a = marked();
    render(<ApproveBar approval={a} selected={[]} me="A Manager" onSubmit={onSubmit} />);
    const sign = screen.getByRole("button", { name: "Sign this plan as A Manager" });
    expect(sign).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByRole("button", { name: /^approve/i })).toBeNull();
    expect(screen.getAllByRole("button").filter((b) => /sign/i.test(b.textContent ?? "")).map((b) => b.textContent)).toEqual(["Sign this plan as A Manager"]);
    expect(screen.getByText("Signing does not make the changes. It says these decisions are yours. A second person may still need to sign, and someone must apply.")).toBeInTheDocument();
    await user.click(sign);
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent(/Signing writes nothing outside jason/);
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onSubmit).toHaveBeenCalledWith({ by: "A Manager", fingerprint: a.fingerprint, via: "console" });
  });

  it("marks items with Mark N as approved, and says nothing is written and the plan still needs a signature", async () => {
    const user = userEvent.setup();
    const a = planned();
    render(<ApproveBar approval={a} selected={[a.items[0].id, a.items[1].id]} me="A Manager" onDecide={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Mark 2 as approved" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Nothing is written. You still need to sign the plan.");
    expect(screen.queryByRole("button", { name: /^approve/i })).toBeNull();
  });

  it("keeps 'approved' as an item's mark and for a fully signed plan: Signed by A and B, ready to apply", () => {
    const { container } = render(<PlanReview approval={{ ...bothSigned(), items: bothSigned().items.map((i) => ({ ...i, highStakes: false })) }} me="C Officer" now={NOW} kind={{ ...KIND, twoPerson: true }} twoPerson />);
    expect(screen.getByText("Signed by A Manager and B Director, ready to apply.")).toBeInTheDocument();
    expect(screen.getAllByText("approved").length).toBeGreaterThan(0);
    expect(container.querySelectorAll("button")).not.toHaveLength(0);
  });
});

describe("PlanProgress: the strip", () => {
  it("is at Review for a plan nobody has marked, and says who does it", () => {
    const { container } = render(<PlanProgress approval={planned()} needsSecond={false} />);
    expect(stepNames(container)).toEqual(["Review", "Sign", "Apply", "Done"]);
    expect(current(container)).toBe("Review");
    expect(container.querySelectorAll("[aria-current=step]")).toHaveLength(1);
    expect(screen.getByText("Any board member or the manager marks each change approved, rejected, or held.")).toBeInTheDocument();
  });

  it("moves to Sign once every approvable change is marked, naming who marked and when", () => {
    const { container } = render(<PlanProgress approval={marked()} needsSecond={false} />);
    expect(current(container)).toBe("Sign");
    expect(screen.getByText("Marked by A Manager, 2026-10-03 19:00 UTC")).toBeInTheDocument();
    expect(screen.getByText("The person who reviewed signs the plan.")).toBeInTheDocument();
  });

  it("leaves out the second signature unless the plan needs one, and is there when it does", () => {
    const one = render(<PlanProgress approval={signed()} needsSecond={false} />);
    expect(stepNames(one.container)).not.toContain("Second signature");
    one.unmount();
    const two = render(<PlanProgress approval={signed()} needsSecond />);
    expect(stepNames(two.container)).toEqual(["Review", "Sign", "Second signature", "Apply", "Done"]);
    expect(current(two.container)).toBe("Second signature");
    expect(screen.getByText("Signed by A Manager, 2026-10-03 19:00 UTC")).toBeInTheDocument();
    expect(screen.getByText("A second person, not A Manager, signs the same plan.")).toBeInTheDocument();
  });

  it("is at Apply once signed (and by both where two must), naming both signers", () => {
    const { container } = render(<PlanProgress approval={bothSigned()} needsSecond ready me="A Manager" />);
    expect(current(container)).toBe("Apply");
    expect(screen.getByText("Signed by B Director, 2026-10-03 19:30 UTC")).toBeInTheDocument();
    expect(screen.getByText("Signed by A Manager and B Director, ready to apply.")).toBeInTheDocument();
  });

  it("is at Apply while applying and when an apply failed, at Done once applied, and at no step when withdrawn or replaced", () => {
    const cases: [Approval, string | null][] = [
      [{ ...signed(), status: "applying" }, "Apply"],
      [{ ...applied(), status: "failed" }, "Apply"],
      [applied(), "Done"],
      [{ ...planned(), status: "withdrawn" }, null],
      [{ ...planned(), status: "superseded" }, null],
    ];
    for (const [a, step] of cases) {
      const { container, unmount } = render(<PlanProgress approval={a} needsSecond={false} />);
      expect(current(container)).toBe(step);
      unmount();
    }
  });

  it("marks every earlier step complete, and Done complete after an apply, with who applied and when", () => {
    const { container } = render(<PlanProgress approval={applied()} needsSecond={false} />);
    expect([...container.querySelectorAll(".plan-step-state")].map((e) => e.textContent)).toEqual(["complete", "complete", "complete", "complete"]);
    expect(screen.getByText("Applied by A Manager, 2026-10-03 18:38 UTC")).toBeInTheDocument();
  });

  it("says where apply happens: a terminal with the command and Copy, or here where the server allows it", () => {
    const term = render(<PlanProgress approval={signed()} needsSecond={false} ready me="A Manager" />);
    expect(screen.getByText("A person applies this at a terminal:")).toBeInTheDocument();
    expect(screen.getByText(/jason approvals apply apr-20261003T183801-4f5b --yes --by "A Manager"/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy command" })).toBeInTheDocument();
    term.unmount();
    render(<PlanProgress approval={signed()} needsSecond={false} ready canApplyHere me="A Manager" />);
    expect(screen.getByText("Apply from here.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy command" })).toBeNull();
  });

  it("shows the command only once apply is reachable, and says an old or changed plan is planned again first", () => {
    const before = render(<PlanProgress approval={planned()} needsSecond={false} me="A Manager" />);
    expect(screen.queryByText(/jason approvals apply/)).toBeNull();
    expect(screen.getByText("Once signed, a person applies this at a terminal.")).toBeInTheDocument();
    before.unmount();
    const old = render(<PlanProgress approval={signed()} needsSecond={false} tooOld />);
    expect(screen.getByText("Read too long ago: apply plans it again before it writes anything.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy command" })).toBeNull();
    old.unmount();
    render(<PlanProgress approval={signed()} needsSecond={false} blocked />);
    expect(screen.getByText("The plan changed since review: plan it again first.")).toBeInTheDocument();
  });

  it("says a terminal-only kind is applied only at the terminal, with its own command", () => {
    render(<PlanProgress approval={bothSigned()} needsSecond ready kind={MAIL} me="A Manager" canApplyHere={false} />);
    expect(screen.getByText("Applied only at a terminal, by a person:")).toBeInTheDocument();
    const a = bothSigned();
    expect(screen.getByText(`jason mailroom --send --yes --expect ${a.fingerprint} --approval ${a.id}`)).toBeInTheDocument();
    expect(terminalCommand(a, "A Manager", MAIL)).toContain(a.fingerprint);
  });

  it("works out the step from the status alone", () => {
    expect(currentStep(planned(), false)).toBe("review");
    expect(currentStep({ ...marked() }, false)).toBe("sign");
    expect(currentStep(signed(), true)).toBe("second");
    expect(currentStep(bothSigned(), true)).toBe("apply");
    expect(currentStep({ ...signed(), status: "partially_approved" }, false)).toBe("apply");
  });
});

describe("PlanProgress: nothing has been written yet", () => {
  it("stands on every open plan until it is applied, naming the system and counting what applying will do", () => {
    for (const status of ["planned", "in_review", "approved", "partially_approved"] as const) {
      const a = { ...signed(), status };
      const { unmount } = render(<PlanProgress approval={a} needsSecond={false} kind={KIND} />);
      expect(screen.getByText("Nothing has been written to PayHOA yet.")).toBeInTheDocument();
      unmount();
    }
  });

  it("counts the approved changes, by field and by record, and says none are marked when none are", () => {
    expect(applyCounts(marked())).toMatchObject({ changes: 12, records: 4 });
    expect(applyCountsWords(marked())).toBe("Applying will make 12 changes on 4 records: member tags (10), request status (2).");
    expect(applyCountsWords(planned())).toBe("No change is marked approved yet.");
    render(<PlanProgress approval={marked()} needsSecond={false} kind={KIND} />);
    expect(screen.getByText(/Applying will make 12 changes on 4 records/)).toBeInTheDocument();
  });

  it("says outside jason when the kind names no system", () => {
    render(<PlanProgress approval={planned()} needsSecond={false} />);
    expect(screen.getByText("Nothing has been written outside jason yet.")).toBeInTheDocument();
    expect(writtenTo({ system: "local" })).toBe("outside jason");
    expect(systemWord({ system: "google" })).toBe("Google");
  });

  it("is gone once the plan is applied (the result takes its place), and says nothing was written when withdrawn", () => {
    const done = render(<PlanProgress approval={applied()} needsSecond={false} kind={KIND} />);
    expect(screen.queryByText(/Nothing has been written/)).toBeNull();
    done.unmount();
    render(<PlanProgress approval={{ ...planned(), status: "withdrawn" }} needsSecond={false} kind={KIND} />);
    expect(screen.getByText("Nothing was written to PayHOA.")).toBeInTheDocument();
  });

  it("stands in the plan itself until the apply result shows", () => {
    const open = render(<PlanReview approval={signed()} me="A Manager" now={NOW} kind={KIND} />);
    expect(screen.getByText("Nothing has been written to PayHOA yet.")).toBeInTheDocument();
    expect(open.container.querySelector(".plan-progress")).not.toBeNull();
    open.unmount();
    render(<PlanReview approval={applied()} me="A Manager" now={NOW} kind={KIND} />);
    expect(screen.queryByText(/Nothing has been written/)).toBeNull();
    expect(screen.getByRole("heading", { name: "Applied 7 of 7 approved changes" })).toBeInTheDocument();
  });
});

describe("apply, named for what it does", () => {
  const readyPlan = () => ({ ...signed(), items: signed().items.map((i) => ({ ...i, highStakes: false })) });

  it("labels the button with the system and opens a dialog with the counts and the live read", async () => {
    const onApply = vi.fn(async () => {});
    const user = userEvent.setup();
    const a = readyPlan();
    render(<PlanReview approval={a} me="A Manager" now={NOW} kind={KIND} onApply={onApply} />);
    expect(screen.getByText("Apply from here.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Apply 12 changes to PayHOA now" }));
    const dialog = screen.getByRole("group", { name: "Confirm" });
    expect(dialog).toHaveTextContent(/Applying will make 12 changes on 4 records/);
    expect(dialog).toHaveTextContent(/reads the live PayHOA state first: if anything an approved change relies on moved, nothing is written/);
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onApply).toHaveBeenCalledWith({ by: "A Manager", confirm: a.fingerprint });
  });

  it("shows the terminal command and no Apply button for a terminal-only kind, even when the server would apply", () => {
    const a = bothSigned();
    render(<PlanReview approval={a} me="C Officer" now={NOW} kind={MAIL} twoPerson onApply={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /^Apply/ })).toBeNull();
    expect(screen.getByText("Applied only at a terminal, by a person:")).toBeInTheDocument();
    expect(screen.getByText(`jason mailroom --send --yes --expect ${a.fingerprint} --approval ${a.id}`)).toBeInTheDocument();
  });

  it("shows the command, not a button, when the server does not allow apply", () => {
    render(<PlanReview approval={readyPlan()} me="A Manager" now={NOW} kind={KIND} onApply={vi.fn()} applyBlocked="the server was started without --allow-apply." />);
    expect(screen.queryByRole("button", { name: /^Apply/ })).toBeNull();
    expect(screen.getByText(/Apply is not available here: the server was started without --allow-apply/)).toBeInTheDocument();
    expect(screen.getByText(/jason approvals apply apr-20261003T183801-4f5b --yes --by "A Manager"/)).toBeInTheDocument();
  });

  it("tells a header state sentence beside the status word", () => {
    const { container } = render(<PlanReview approval={planned()} me="A Manager" now={NOW} />);
    expect(within(container.querySelector(".plan-head") as HTMLElement).getByText("Needs review: 0 of 12 marked.")).toBeInTheDocument();
  });
});

describe("planState: the six sentences", () => {
  it("says what is left to review, then that the marks need a signature", () => {
    const a = planned();
    expect(planState(a, "A Manager")).toBe("Needs review: 0 of 12 marked.");
    const some = planned();
    some.items.filter((i) => i.class === "approvable").slice(0, 3).forEach((i) => Object.assign(i, { decision: "approved" }));
    expect(planState({ ...some, status: "in_review" }, "A Manager")).toBe("Needs review: 3 of 12 marked.");
    expect(planState(marked(), "A Manager")).toBe("Marked, needs your signature.");
    expect(planState(marked(), "")).toBe("Marked, needs a signature.");
    expect(planState(marked(), "jason")).toBe("Marked, needs a signature.");
  });

  it("waits for a second signature, then says signed and not applied", () => {
    expect(planState(signed(), "B Director", { needsSecond: true })).toBe("Waiting for a second signature (someone other than A Manager).");
    expect(planState(signed(), "B Director", { twoPerson: true })).toBe("Waiting for a second signature (someone other than A Manager).");
    expect(planState(bothSigned(), "B Director", { needsSecond: true })).toBe("Signed, not applied yet. Nothing has been written.");
    expect(planState(signed(), "A Manager")).toBe("Signed, not applied yet. Nothing has been written.");
    expect(planState({ ...signed(), status: "partially_approved" }, "A Manager")).toBe("Signed, not applied yet. Nothing has been written.");
  });

  it("gives the result, and the three ways a plan ends otherwise", () => {
    expect(planState(applied())).toBe("Applied: 7 changes made, 0 failed.");
    const failed = applied();
    Object.assign(failed.items.find((i) => i.result === "applied")!, { result: "failed" });
    expect(planState({ ...failed, status: "failed" })).toBe("Failed: 1 change was not made");
    Object.assign(failed.items.filter((i) => i.result === "applied")[0], { result: "uncertain" });
    expect(planState({ ...failed, status: "failed" })).toBe("Failed: 2 changes were not made");
    expect(planState({ ...planned(), status: "withdrawn" })).toBe("Withdrawn");
    expect(planState({ ...planned(), status: "superseded" })).toBe("Replaced by a newer plan");
    expect(planState({ ...signed(), status: "applying" })).toMatch(/^Applying: 0 of 12 changes written\.$/);
  });

  it("reads a list row too, where items is a count and the counts come by class, decision, and result", () => {
    const row = { status: "in_review" as const, items: 17, byClass: { approvable: 12, held_for_board: 2 }, byDecision: { approved: 3, rejected: 1, undecided: 8 } };
    expect(planState(row, "A Manager")).toBe("Needs review: 4 of 12 marked.");
    expect(planState({ ...row, byDecision: { approved: 12 } }, "A Manager")).toBe("Marked, needs your signature.");
    expect(planState({ status: "approved", items: 17, byClass: { approvable: 12 }, first: "A Manager", second: "", needsSecond: true })).toBe("Waiting for a second signature (someone other than A Manager).");
    expect(planState({ status: "approved", items: 17, byClass: { approvable: 12 }, first: "A Manager", second: "B Director", needsSecond: true })).toBe("Signed, not applied yet. Nothing has been written.");
    expect(planState({ status: "applied", items: 17, byResult: { applied: 12, not_applied: 5 } })).toBe("Applied: 12 changes made, 0 failed.");
    expect(planState({ status: "failed", items: 17, approved: 12, byResult: { applied: 10, failed: 2 } })).toBe("Failed: 2 changes were not made");
  });
});
