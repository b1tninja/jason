/// <reference types="vite/client" />
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import appliedJson from "../../../tests/fixtures/approvals/example-village-applied.json";
import auditRaw from "../../../tests/fixtures/approvals/example-village-audit.jsonl?raw";
import { ApplyResult } from "./ApplyResult";
import { ApproveBar } from "./ApproveBar";
import { AuditLog, auditWords } from "./AuditLog";
import { ChangedBanner } from "./ChangedBanner";
import { CostLine } from "./CostLine";
import { FlaggedItem } from "./FlaggedItem";
import { HeldNote } from "./HeldNote";
import { PlanReview } from "./PlanReview";
import { QuestionCard, type Question } from "./QuestionCard";
import { ReadingLabel } from "./ReadingLabel";
import { Recitation } from "./Recitation";
import { SecondConfirm } from "./SecondConfirm";
import { StageSteps } from "./StageSteps";
import { WriteRow } from "./WriteRow";
import { KIND_NOTICES } from "../lib/controls.fixtures";
import { signerWords } from "../lib/controls";
import {
  decisionProblem, flaggedCounts, isJason, needsSecond, nudged, results, sameName, signerProblem, staleness, tally, type Approval,
  type AuditEntry, type PlanItem, type Recheck,
} from "../lib/approvals";

// The engine's own Example Village fixtures (tests/fixtures/approvals): the components take them as they are.
const planned = () => structuredClone(plannedJson) as unknown as Approval;
const applied = () => structuredClone(appliedJson) as unknown as Approval;
const audit = (): AuditEntry[] => auditRaw.trim().split("\n").map((l) => JSON.parse(l));
const NOW = "2026-10-03T19:00:00+00:00";
const item = (a: Approval, id: string) => a.items.find((i) => i.id === id)!;
const HELD = "acad6529c029339a";          // unit tag -, held for the board (rental-approvals-4-15)
const PERSON = "3bb2cb92e752903d";        // for a person
const COMPLETE_502 = "9611d0b11945aa9a";  // complete request, waits on dceffc0b8fac3f1d and 79b0872b69c00a3f
const WRITE_502 = ["dceffc0b8fac3f1d", "79b0872b69c00a3f"];

/** An approval signed by A Manager, with one high-stakes approved item: a second person must confirm. */
function signed(): Approval {
  const a = planned();
  for (const i of a.items) if (i.class === "approvable") Object.assign(i, { decision: "approved", decidedBy: "A Manager", decidedAt: NOW });
  item(a, WRITE_502[0]).highStakes = true;
  return { ...a, status: "approved", first: { name: "A Manager", at: NOW, fingerprint: a.fingerprint, role: "manager", via: "console" } };
}

describe("the rules (lib/approvals)", () => {
  it("compares names case-blind with spacing ignored, and never lets jason sign", () => {
    expect(sameName("  a   MANAGER ", "A Manager")).toBe(true);
    expect(sameName("", "")).toBe(false);
    expect(isJason(" JASON ")).toBe(true);
    expect(signerProblem("Jason")).toMatch(/jason never signs/);
    expect(signerProblem("a manager", ["A Manager"])).toMatch(/second, distinct person/);
    expect(signerProblem("B Director", ["A Manager"])).toBe("");
  });

  it("refuses what the engine's decide refuses", () => {
    const a = planned();
    expect(decisionProblem(a, [WRITE_502[0]], "rejected", " ")).toMatch(/reason of a few words for rejecting/);
    expect(decisionProblem(a, [WRITE_502[0]], "held", "")).toMatch(/holding these changes for the board/);
    expect(decisionProblem(a, [HELD], "approved", "")).toMatch(/never approvable/);
    expect(decisionProblem(a, [COMPLETE_502], "approved", "")).toMatch(/waits on 2 changes not approved/);
    expect(decisionProblem(a, [COMPLETE_502, ...WRITE_502], "approved", "")).toBe("");
    expect(decisionProblem(applied(), [WRITE_502[0]], "approved", "")).toMatch(/applied: items are decided before/);
  });

  it("finds a stale plan: changed since review blocks; only old does not", () => {
    const a = planned();
    expect(staleness(a, { now: NOW })).toMatchObject({ blocked: false, tooOld: false });
    const recheck: Recheck = { changed: [{ id: WRITE_502[0], op: "member tag +", label: "102 EXAMPLE WAY: Ben Sample", then: "a", now: "b", why: "what it relies on changed since review" }] };
    expect(staleness(a, { now: NOW, recheck }).blocked).toBe(true);
    expect(staleness(a, { now: "2026-10-05T00:00:00+00:00" })).toMatchObject({ blocked: false, tooOld: true });
    expect(staleness({ ...a, status: "superseded" }, { now: NOW })).toMatchObject({ blocked: true, superseded: true });
  });
});

describe("WriteRow", () => {
  it("gives an approvable item a checkbox named by its owner and change", async () => {
    const a = planned();
    const onToggle = vi.fn();
    render(<><h4 id="g">101 EXAMPLE WAY: Ana Example</h4><WriteRow item={a.items[0]} selectable onToggle={onToggle} labelledBy="g" /></>);
    const box = screen.getByRole("checkbox");
    expect(box).toHaveAccessibleName(/101 EXAMPLE WAY: Ana Example .*Notices by Email/);
    await userEvent.setup().click(box);
    expect(onToggle).toHaveBeenCalledWith("7344a0e1a0d1efa6", true);
  });

  it("never gives a held, for-a-person, or informational item a checkbox, whatever is passed", () => {
    const a = planned();
    const { container } = render(<>{a.items.filter((i) => i.class !== "approvable").map((i) => <WriteRow key={i.id} item={i} selectable checked />)}</>);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(container.querySelectorAll("[data-class=held_for_board]")).toHaveLength(2);
    expect(screen.getAllByText(/jason's policy finding/).length).toBeGreaterThan(0);
  });

  it("shows a person's decision with the person and the reason, and what a completion waits on", () => {
    const a = planned();
    const w = item(a, WRITE_502[0]);
    Object.assign(w, { decision: "held", decidedBy: "Jane Example", reason: "the board should say how a tag is chosen" });
    render(<WriteRow item={item(a, COMPLETE_502)} waits={WRITE_502.map((id) => item(a, id))} />);
    expect(screen.getByText(/Waits on 2 changes/)).toBeInTheDocument();
    render(<WriteRow item={w} />);
    expect(screen.getByText(/for the board by Jane Example: the board should say how a tag is chosen/)).toBeInTheDocument();
  });
});

describe("HeldNote", () => {
  it("keeps jason's policy finding (flagged for review) apart from a person's hold", () => {
    const a = planned();
    Object.assign(item(a, WRITE_502[0]), { decision: "held", decidedBy: "Jane Example", decidedAt: NOW, reason: "ask the board first" });
    render(<HeldNote items={a.items} />);
    const policy = screen.getByRole("note", { name: "Flagged for review: jason's policy finding" });
    expect(within(policy).getByText(/2 changes flagged for review/)).toBeInTheDocument();
    expect(within(policy).getByText("rental-approvals-4-15")).toBeInTheDocument();
    const person = screen.getByRole("note", { name: "Held for the board by Jane Example" });
    expect(within(person).getByText("ask the board first")).toBeInTheDocument();
  });

  it("renders nothing when nothing is held", () => {
    const { container } = render(<HeldNote items={planned().items.filter((i) => i.class === "approvable")} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ChangedBanner", () => {
  const recheck: Recheck = { then: "f".repeat(64), now: "e".repeat(64), changed: [{ id: WRITE_502[0], op: "member tag +", label: "102 EXAMPLE WAY: Ben Sample", then: "a", now: "b", why: "what it relies on changed since review" }] };

  it("is absent for a fresh plan", () => {
    const { container } = render(<ChangedBanner approval={planned()} now={NOW} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names what changed and offers a re-plan behind Confirm, as a named person", async () => {
    const onReplan = vi.fn();
    const user = userEvent.setup();
    render(<ChangedBanner approval={planned()} recheck={recheck} now={NOW} me="Jane Example" onReplan={onReplan} />);
    expect(screen.getByRole("heading", { name: "The plan changed since it was reviewed" })).toBeInTheDocument();
    expect(screen.getByText(/what it relies on changed since review/)).toBeInTheDocument();
    expect(screen.getByText(/jason approvals plan owner-info-tags --by "Jane Example"/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Re-plan and review again" }));
    expect(onReplan).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onReplan).toHaveBeenCalledWith({ by: "Jane Example" });
  });

  it("asks for a name before a re-plan, and opens the plan that superseded this one", async () => {
    const onOpen = vi.fn();
    render(<ChangedBanner approval={planned()} recheck={recheck} now={NOW} onReplan={() => {}} />);
    expect(screen.getByText(/Pick whose name goes on the record/)).toBeInTheDocument();
    render(<ChangedBanner approval={{ ...planned(), status: "superseded", supersededBy: "apr-20261004T090000-9c1d" }} now={NOW} onOpen={onOpen} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Open the new plan" }));
    expect(onOpen).toHaveBeenCalledWith("apr-20261004T090000-9c1d");
  });
});

describe("ApproveBar", () => {
  it("refuses a rejection without a reason, says why, and focuses the reason", async () => {
    const onDecide = vi.fn();
    const user = userEvent.setup();
    render(<ApproveBar approval={planned()} selected={[WRITE_502[0]]} me="A Manager" onDecide={onDecide} />);
    await user.click(screen.getByRole("radio", { name: "Rejected" }));
    await user.click(screen.getByRole("button", { name: "Mark 1 as rejected" }));
    expect(onDecide).not.toHaveBeenCalled();
    expect(screen.getByText(/Give a reason of a few words for rejecting/)).toBeInTheDocument();
    const reason = screen.getByLabelText("Reason, to reject or hold");
    expect(reason).toHaveFocus();
    expect(reason).toHaveAttribute("aria-invalid", "true");
  });

  it("holds with a reason, through Confirm, and drops a held item someone passed in", async () => {
    const onDecide = vi.fn();
    const user = userEvent.setup();
    const a = planned();
    render(<ApproveBar approval={a} selected={[WRITE_502[0], HELD, PERSON]} me="A Manager" onDecide={onDecide} />);
    expect(screen.getByText("1 of 12 changes selected")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Held for the board" }));
    await user.type(screen.getByLabelText("Reason, to reject or hold"), "the board decides tags");
    await user.click(screen.getByRole("button", { name: "Mark 1 as held" }));
    expect(onDecide).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onDecide).toHaveBeenCalledWith({ items: [WRITE_502[0]], decision: "held", reason: "the board decides tags", by: "A Manager", fingerprint: a.fingerprint, via: "console" });
  });

  it("says what is signed, and waits until every approvable change is decided", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    const a = planned();
    const { rerender } = render(<ApproveBar approval={a} selected={[]} me="A Manager" onSubmit={onSubmit} />);
    const sign = screen.getByRole("button", { name: "Sign this plan as A Manager" });
    expect(sign).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Decide 12 more changes to submit.")).toBeInTheDocument();
    a.items.forEach((i, n) => { if (i.class === "approvable") Object.assign(i, { decision: n % 4 ? "approved" : "rejected", decidedBy: "A Manager", reason: n % 4 ? "" : "later" }); });
    rerender(<ApproveBar approval={{ ...a, status: "in_review" }} selected={[]} me="A Manager" onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Sign this plan as A Manager" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onSubmit).toHaveBeenCalledWith({ by: "A Manager", fingerprint: a.fingerprint, via: "console" });
  });

  it("never signs as jason, and blocks everything on a changed plan", async () => {
    const onDecide = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<ApproveBar approval={planned()} selected={[WRITE_502[0]]} me="jason" onDecide={onDecide} />);
    await user.click(screen.getByRole("button", { name: "Mark 1 as approved" }));
    expect(screen.getByText(/jason never signs/)).toBeInTheDocument();
    expect(onDecide).not.toHaveBeenCalled();
    rerender(<ApproveBar approval={planned()} selected={[WRITE_502[0]]} me="A Manager" onDecide={onDecide} blocked />);
    expect(screen.getByText(/The plan changed since review/)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Mark the selected changes" })).toBeDisabled();
  });
});

describe("SecondConfirm", () => {
  it("refuses the first signer by any case or spacing, then confirms a second person", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    const a = signed();
    render(<SecondConfirm approval={a} onConfirm={onConfirm} />);
    const name = screen.getByLabelText(/Your full name/);
    expect(name).toHaveValue("");
    await user.type(name, "  a   MANAGER ");
    await user.click(screen.getByRole("button", { name: "Confirm with your name" }));
    expect(screen.getByText(/A Manager already signed or asked for this plan/)).toBeInTheDocument();
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(onConfirm).not.toHaveBeenCalled();
    await user.clear(name);
    await user.type(name, "B Director");
    await user.click(screen.getByRole("button", { name: "Confirm as B Director" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onConfirm).toHaveBeenCalledWith({ by: "B Director", fingerprint: a.fingerprint, via: "console" });
  });

  it("needs a reason to decline, and is absent when no second person is needed", async () => {
    const onDecline = vi.fn();
    const user = userEvent.setup();
    render(<SecondConfirm approval={signed()} onDecline={onDecline} />);
    await user.type(screen.getByLabelText(/Your full name/), "B Director");
    await user.click(screen.getByRole("button", { name: "Decline and send back" }));
    expect(screen.getByText("Give a reason of a few words for declining.")).toBeInTheDocument();
    expect(onDecline).not.toHaveBeenCalled();
    const plain = signed();
    plain.items.forEach((i) => (i.highStakes = false));
    const { container } = render(<SecondConfirm approval={plain} />);
    expect(container).toBeEmptyDOMElement();
    render(<SecondConfirm approval={plain} twoPerson />);
    expect(screen.getAllByRole("heading", { name: "A second person confirms" })).toHaveLength(2);
  });
});

describe("CostLine and ApplyResult", () => {
  it("states the cost in words or integer cents", () => {
    render(<CostLine {...planned()} />);
    expect(screen.getByText(/No charge: PayHOA tag changes and request status/)).toBeInTheDocument();
    render(<CostLine costCents={816} summary={{ cost: "4 letters" }} />);
    expect(screen.getByText("$8.16")).toBeInTheDocument();
  });

  it("counts what the apply did from the items, and nothing before an apply", () => {
    const { container } = render(<ApplyResult approval={planned()} />);
    expect(container).toBeEmptyDOMElement();
    render(<ApplyResult approval={applied()} />);
    const r = screen.getByRole("status", { name: "Apply result" });
    expect(within(r).getByRole("heading", { name: "Applied 7 of 7 approved changes" })).toBeInTheDocument();
    expect(within(r).getByText("Not applied (10)")).toBeInTheDocument();
    expect(within(r).getByText(/^by A Manager, 2026-10-03 18:38 UTC/)).toBeInTheDocument();
  });

  it("says an uncertain write must not be applied again until the next live read", () => {
    const a = applied();
    Object.assign(item(a, WRITE_502[0]), { result: "uncertain", resultDetail: "timeout" });
    render(<ApplyResult approval={{ ...a, status: "failed" }} />);
    expect(screen.getByText(/do not apply again until then/)).toBeInTheDocument();
  });
});

describe("Recitation and ReadingLabel", () => {
  it("recites the stored words whole with the citation, version, and caveat; a miss quotes nothing", () => {
    render(<Recitation mark="in writing" citation={{ found: true, citation: "Declaration § 7.3", text: "An Owner may lease the whole Unit, in writing.", inForce: "as amended 2024", caveat: "jason's consolidated text, not an official restatement." }} />);
    expect(screen.getByText("Recited words")).toBeInTheDocument();
    expect(screen.getByText("in writing").tagName).toBe("MARK");
    expect(screen.getByText("Declaration § 7.3")).toBeInTheDocument();
    render(<Recitation citation={{ found: false, citation: "Rules R-9", reason: "no_such_section" }} />);
    expect(screen.getByText(/Not found: Rules R-9 \(no such section\)/)).toBeInTheDocument();
  });

  it("labels whose reading it is", () => {
    render(<><ReadingLabel whose="jason">A month-to-month written lease meets it.</ReadingLabel><ReadingLabel whose="board" adopted="2025-06-10">Calendar days.</ReadingLabel><ReadingLabel whose="open" options={["From signing", "From possession"]} /></>);
    expect(screen.getByRole("complementary", { name: "jason's reading" })).toHaveTextContent(/not legal advice/);
    expect(screen.getByRole("complementary", { name: "The board's reading" })).toHaveTextContent(/adopted 2025-06-10/);
    expect(screen.getByRole("complementary", { name: "Two readings remain" })).toHaveTextContent(/asks counsel/);
  });
});

describe("AuditLog", () => {
  it("shows jason only as the planner and every act under its person", () => {
    const rows = audit();
    expect(auditWords(rows[0])).toBe("Planned by jason: 17 items (asked by A Manager)");
    render(<AuditLog entries={rows} />);
    expect(screen.getByText(/Each of these 22 lines names the line before it/)).toBeInTheDocument();
    const words = rows.map(auditWords);
    expect(words.filter((w) => /jason/i.test(w)).every((w) => w.startsWith("Planned by jason"))).toBe(true);
    expect(words).toContain("A Manager rejected 5 changes");
  });

  it("flags a broken link, a server-reported break, and narrows to one approval", () => {
    const rows = audit();
    rows[5] = { ...rows[5], prev: "0".repeat(64) };
    render(<AuditLog entries={rows} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Line 6 does not name the line before it");
    render(<AuditLog entries={audit()} approval="apr-20261003T183801-4f5b" chain={{ ok: false, line: 9, why: "hash mismatch" }} />);
    expect(screen.getAllByRole("alert")[1]).toHaveTextContent("Chain broken at line 9: hash mismatch");
  });
});

describe("QuestionCard and StageSteps", () => {
  const q: Question = {
    id: "q-decl", question: "Which declaration is in force?", choices: ["The 2019 restatement, as amended", "The 2019 restatement alone"],
    suggestion: "The 2019 restatement, as amended", evidence: ["Restated declaration, 2019"], highStakes: true,
    unblocks: { clocks: ["notice:board-meeting", "notice:annual"], gates: ["establish"] },
  };

  it("marks jason's suggestion without choosing it, and saves a named answer through Confirm", async () => {
    const onAnswer = vi.fn();
    const user = userEvent.setup();
    render(<QuestionCard question={q} rank={1} me="Jane Example" onAnswer={onAnswer} />);
    expect(screen.getByText("Rank")).toBeInTheDocument();
    expect(screen.getByText(/2 legal clocks, the establish gate/)).toBeInTheDocument();
    expect(screen.getByText("jason's suggestion")).toBeInTheDocument();
    screen.getAllByRole("radio").forEach((r) => expect(r).not.toBeChecked());
    expect(screen.getByRole("button", { name: "Save the answer" })).toHaveAttribute("aria-disabled", "true");
    await user.click(screen.getByRole("radio", { name: /The 2019 restatement alone/ }));
    await user.click(screen.getByRole("button", { name: "Save the answer" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAnswer).toHaveBeenCalledWith({ id: "q-decl", answer: "The 2019 restatement alone", by: "Jane Example" });
  });

  it("puts the stage being worked in the reading order with what it waits on", () => {
    render(<StageSteps current="establish" gates={[
      { stage: "start", title: "Accounts set", open: true },
      { stage: "establish", title: "Governing documents settled", open: false, waiting: [{ key: "declaration", status: "partial" }] },
    ]} />);
    const steps = screen.getAllByRole("listitem");
    expect(steps[0]).toHaveTextContent("Gate open");
    expect(steps[1]).toHaveAttribute("aria-current", "step");
    expect(steps[1]).toHaveTextContent("Waiting on: declaration (partial)");
  });
});

describe("PlanReview", () => {
  it("puts each item in exactly one section, and only approvable items get checkboxes", () => {
    render(<PlanReview approval={planned()} me="A Manager" now={NOW} />);
    for (const h of ["To decide (12)", "Flagged for review: 2 flagged, 0 decided by exception", "For a person (1)", "What follows (2)"])
      expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
    const decide = screen.getByRole("region", { name: "To decide (12)" });
    const items = decide.querySelectorAll<HTMLInputElement>("input[data-plan-check]");
    expect(items).toHaveLength(12);
    expect(items[0]).toHaveAccessibleName(/101 EXAMPLE WAY: Ana Example/);
    for (const h of ["Flagged for review: 2 flagged, 0 decided by exception", "For a person (1)", "What follows (2)"])
      expect(within(screen.getByRole("region", { name: h })).queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.getByText(/Planned by jason, asked by A Manager/)).toBeInTheDocument();
  });

  it("moves between item checkboxes with the arrow keys and toggles with Space", async () => {
    const user = userEvent.setup();
    render(<PlanReview approval={planned()} me="A Manager" now={NOW} />);
    const boxes = [...screen.getByRole("region", { name: "To decide (12)" }).querySelectorAll<HTMLInputElement>("input[data-plan-check]")];
    boxes[0].focus();
    await user.keyboard("{ArrowDown}");
    expect(boxes[1]).toHaveFocus();
    await user.keyboard(" ");
    expect(boxes[1]).toBeChecked();
    await user.keyboard("{End}");
    expect(boxes[11]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(boxes[0]).toHaveFocus();
    expect(screen.getByText("1 of 12 changes selected")).toBeInTheDocument();
  });

  it("approves everything selected as a named person and says so in a status message", async () => {
    const onDecide = vi.fn(async () => {});
    const user = userEvent.setup();
    const a = planned();
    render(<PlanReview approval={a} me="A Manager" now={NOW} onDecide={onDecide} />);
    await user.click(screen.getByRole("checkbox", { name: "Select all 12 approvable" }));
    await user.click(screen.getByRole("button", { name: "Mark 12 as approved" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onDecide).toHaveBeenCalledTimes(1);
    const body = (onDecide.mock.calls[0] as unknown as [{ items: string[]; by: string; decision: string }])[0];
    expect(body.items).toHaveLength(12);
    expect(body.items).not.toContain(HELD);
    expect(body).toMatchObject({ by: "A Manager", decision: "approved" });
    expect(await screen.findByText(/Marked approved\. Nothing is written\. You still need to sign the plan\./)).toBeInTheDocument();
  });

  it("blocks approval on a stale plan and offers a re-plan", () => {
    const recheck: Recheck = { changed: [{ id: WRITE_502[0], op: "member tag +", label: "102 EXAMPLE WAY: Ben Sample", then: "a", now: "b", why: "no longer in the plan" }] };
    render(<PlanReview approval={planned()} me="A Manager" now={NOW} recheck={recheck} onReplan={() => {}} />);
    expect(within(screen.getByRole("region", { name: "To decide (12)" })).queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.getByRole("group", { name: "Mark the selected changes" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Re-plan and review again" })).toBeInTheDocument();
  });

  it("asks a second person before the apply command, and shows the result after", () => {
    const { unmount } = render(<PlanReview approval={signed()} me="A Manager" now={NOW} />);
    expect(screen.getByRole("heading", { name: "A second person confirms" })).toBeInTheDocument();
    expect(screen.getByText(/You signed or asked for this plan/)).toBeInTheDocument();
    expect(screen.queryByText(/jason approvals apply/)).toBeNull();
    unmount();
    const both = { ...signed(), second: { name: "B Director", at: NOW, fingerprint: planned().fingerprint } };
    const { unmount: u2 } = render(<PlanReview approval={both} me="A Manager" now={NOW} />);
    expect(screen.getByText(/jason approvals apply apr-20261003T183801-4f5b --yes --by "A Manager"/)).toBeInTheDocument();
    u2();
    render(<PlanReview approval={applied()} me="A Manager" now={NOW} audit={audit()} />);
    expect(screen.queryByRole("form", { name: "Decide and sign" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Applied 7 of 7 approved changes" })).toBeInTheDocument();
  });

  it("applies through Confirm with the full fingerprint, or says why the server will not", async () => {
    const onApply = vi.fn(async () => {});
    const user = userEvent.setup();
    const plain = signed();
    plain.items.forEach((i) => (i.highStakes = false));
    const { unmount } = render(<PlanReview approval={plain} me="A Manager" now={NOW} onApply={onApply} />);
    await user.click(screen.getByRole("button", { name: "Apply 12 changes now" }));
    expect(onApply).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onApply).toHaveBeenCalledWith({ by: "A Manager", confirm: plain.fingerprint });
    unmount();
    render(<PlanReview approval={plain} me="A Manager" now={NOW} onApply={onApply} applyBlocked="the server was started without --allow-apply." />);
    expect(screen.queryByRole("button", { name: /Apply 12 changes now/ })).toBeNull();
    expect(screen.getByText(/Apply is not available here: the server was started without --allow-apply/)).toBeInTheDocument();
  });

  it("withdraws only with a reason", async () => {
    const onWithdraw = vi.fn(async () => {});
    const user = userEvent.setup();
    render(<PlanReview approval={planned()} me="A Manager" now={NOW} onWithdraw={onWithdraw} />);
    await user.click(screen.getByText("Withdraw this plan"));
    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(screen.getByText("Give a reason of a few words for withdrawing it.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Reason, to withdraw"), "planned twice");
    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onWithdraw).toHaveBeenCalledWith({ by: "A Manager", reason: "planned twice" });
  });

  it("never lets an approvable row read as decided by jason", () => {
    const a = planned();
    Object.assign(a.items[0], { decision: "approved", decidedBy: "jason" } satisfies Partial<PlanItem>);
    render(<PlanReview approval={{ ...a, status: "in_review" }} me="A Manager" now={NOW} />);
    expect(screen.getByText(/by \(no person named\)/)).toBeInTheDocument();
  });
});

describe("a control's notice on a plan and at the second signature", () => {
  it("shows the effective rule at the top of the plan, the waiting control muted, and the refusal beside the signature controls", () => {
    const { container } = render(<PlanReview approval={planned()} me="A Manager" now={NOW} notice={KIND_NOTICES} />);
    const head = container.querySelector(".plan-head")!;
    const line = within(head as HTMLElement).getByText(/Required by a control the board adopted on 2099-09-05:/).closest("p")!;
    expect(line).toHaveTextContent("Two signers are required above $2,500.00.");
    expect(within(line).getByRole("link", { name: "Payment signers" })).toHaveAttribute("href", "#/controls?key=payment-signers");
    const waiting = head.querySelector(".control-notice-waiting")!;
    expect(waiting.className).toContain("muted");
    expect(waiting).toHaveTextContent("Takes effect 2099-11-14; not yet required");
    // The refusal is said again where the person signs, so no one is blocked without a reason; the rule itself is not repeated.
    const refused = container.querySelectorAll(".control-notice-refused");
    expect(refused).toHaveLength(2);
    expect(refused[1]).toHaveTextContent("Monthly review requires a treasurer and a vice president; the roster has no vice president");
    expect(refused[1].closest(".plan-head")).toBeNull();
  });

  it("draws no line when the notice could not be read or no control touches the kind, and never blocks the plan", () => {
    const none = { ...KIND_NOTICES, controls: [], waiting: [], refusals: [] };
    for (const notice of [undefined, null, none, { ...KIND_NOTICES, found: false }]) {
      const { container, unmount } = render(<PlanReview approval={planned()} me="A Manager" now={NOW} notice={notice} />);
      expect(container.querySelector(".control-notice")).toBeNull();
      expect(screen.getByRole("heading", { name: /To decide/ })).toBeInTheDocument();
      unmount();
    }
  });

  it("shows the server's refusal, naming the control, in the plan's own error line", () => {
    const why = "a control the board adopted on 2099-09-05 allows only the treasurer or the director to sign; B Director does not hold one of those offices";
    render(<PlanReview approval={signed()} me="A Manager" now={NOW} notice={KIND_NOTICES} error={why} />);
    expect(screen.getAllByRole("alert").some((e) => e.textContent === why)).toBe(true);
  });

  it("says at the second signature who may sign, in offices only", () => {
    const narrowed = { ...KIND_NOTICES, roles: ["treasurer", "director"], mustInclude: ["treasurer"] };
    expect(signerWords(narrowed)).toBe("Only the treasurer or the director may sign. The treasurer must be among the signers.");
    render(<SecondConfirm approval={signed()} twoPerson notice={narrowed} />);
    const line = screen.getByLabelText("Who may sign, by a control");
    expect(line).toHaveTextContent("Required by a control the board adopted on 2099-09-05: Payment signers. Only the treasurer or the director may sign. The treasurer must be among the signers.");
    expect(within(line).getByRole("link", { name: "Payment signers" })).toHaveAttribute("href", "#/controls?key=payment-signers");
  });

  it("says nothing of signers when no control narrows them, or the notice is missing", () => {
    const open = { ...KIND_NOTICES, roles: [], mustInclude: [] };
    expect(signerWords(open)).toBe("");
    expect(signerWords({ ...KIND_NOTICES, controls: [] })).toBe("");
    expect(signerWords(null)).toBe("");
    for (const notice of [open, null, undefined]) {
      const { unmount } = render(<SecondConfirm approval={signed()} twoPerson notice={notice} />);
      expect(screen.queryByLabelText("Who may sign, by a control")).toBeNull();
      expect(screen.getByRole("heading", { name: "A second person confirms" })).toBeInTheDocument();
      unmount();
    }
  });
});

// --- flagged for review (docs/held-items.md) -----------------------------------------------------------------------------

const HELD2 = "f8c33b440bec33f9";           // unit tag +, the other flagged item (same finding)
const FINDING = "owner_responses.RULES: occupancy-vs-tag";
const BOARD = "rental-approvals-4-15";
const WHY = "the owner confirmed in writing that the unit is owner-occupied";
/** What the server sends beside a flagged item (GET /api/approvals/<id>): the log's rows for its finding and their count. */
const row = (n: number, by = "Dana Director", decision = "approved") => ({
  at: `2026-10-0${n}T17:0${n}:00+00:00`, approval: `apr-2026100${n}T120000-aaaa`, item: HELD, finding: FINDING, boardItem: BOARD, by, secondBy: n === 1 ? "Lee President" : "",
  decision, reason: `case ${n}: the owner's written answer`, applied: n === 1, kind: "owner-info-tags",
});
function withExceptions(count = 0): Approval {
  const a = planned();
  const rows = Array.from({ length: count }, (_, n) => row(n + 1));
  for (const id of [HELD, HELD2]) Object.assign(item(a, id), { exceptions: rows, exceptionCount: count });
  return a;
}

describe("flagged for review", () => {
  it("says flagged in the row's pill, and the policy finding stays jason's", () => {
    const a = planned();
    render(<WriteRow item={item(a, HELD)} />);
    expect(screen.getByText("flagged")).toBeInTheDocument();
    expect(screen.getByText(/Flagged for review/)).toBeInTheDocument();
    expect(screen.getByText(/jason's policy finding/)).toBeInTheDocument();
    expect(screen.queryByText(/never approvable/)).toBeNull();
  });

  it("heads the section with how many are flagged and how many were decided by exception", () => {
    const a = withExceptions();
    Object.assign(item(a, HELD2), { decision: "approved", decidedBy: "Dana Director", exception: true, reason: WHY, highStakes: true });
    render(<PlanReview approval={a} me="A Manager" now={NOW} />);
    expect(screen.getByRole("heading", { name: "Flagged for review: 2 flagged, 1 decided by exception" })).toBeInTheDocument();
    const section = screen.getByRole("region", { name: "Flagged for review: 2 flagged, 1 decided by exception" });
    expect(within(section).getAllByText("approved").length).toBeGreaterThan(0);
    expect(within(section).getByText(/^as a one-off exception by Dana Director: the owner confirmed in writing/)).toBeInTheDocument();   // the badge says "approved"; the line does not say it twice
    expect(within(section).getAllByText("second person").length).toBeGreaterThan(0);
  });

  it("expands to the change, the finding and rule, the evidence, the board item, and the exceptions already made", () => {
    const a = withExceptions(2);
    render(<FlaggedItem item={item(a, HELD)} approval={a} me="A Manager" editable boardHref={(id) => `#/actions?item=${id}`} />);
    const panel = document.querySelector("[data-flagged-item]") as HTMLElement;
    const change = within(panel).getByLabelText("The change");
    expect(change).toHaveTextContent("Targetunit:1");
    expect(change).toHaveTextContent("FromRental");
    expect(change).toHaveTextContent("Tonone");
    expect(panel).toHaveTextContent("says owner-occupied; the unit is tagged Rented out");
    expect(panel).toHaveTextContent(`Finding and rule: ${FINDING}`);
    expect(panel).toHaveTextContent("PayHOA request 501");
    expect(within(panel).getAllByRole("link", { name: BOARD })[0]).toHaveAttribute("href", `#/actions?item=${BOARD}`);
    const history = panel.querySelector(".flagged-history") as HTMLElement;
    expect(within(history).getAllByRole("listitem")).toHaveLength(2);
    expect(history).toHaveTextContent("Dana Director approved · 2026-10-01 17:01 UTC: case 1: the owner's written answer · second: Lee President · applied");
    expect(history).toHaveTextContent("no second signature yet · not applied");
    expect(panel).toHaveTextContent("2 exceptions made under this finding");
  });

  it("offers the four actions, each in a Confirm, and says the exception is not a rule", async () => {
    const onDecide = vi.fn();
    const onRefer = vi.fn();
    const user = userEvent.setup();
    const a = withExceptions();
    render(<FlaggedItem item={item(a, HELD)} approval={a} me="A Manager" editable onDecide={onDecide} onRefer={onRefer} />);
    for (const name of ["Mark approved as a one-off exception", "Mark as rejected", "Keep flagged", "Refer to the board"])
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    // no reason, or a token for one: refused before it is sent
    await user.click(screen.getByRole("button", { name: "Mark approved as a one-off exception" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give a reason in words");
    await user.type(screen.getByLabelText("Reason, in words (for the log)"), "ok");
    await user.click(screen.getByRole("button", { name: "Mark approved as a one-off exception" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give a reason in words");
    expect(onDecide).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText("Reason, in words (for the log)"));
    await user.type(screen.getByLabelText("Reason, in words (for the log)"), WHY);
    await user.click(screen.getByRole("button", { name: "Mark approved as a one-off exception" }));
    const dialog = screen.getByRole("group", { name: "Exception" });
    expect(dialog).toHaveTextContent("One-off decision, not a rule. A second person must sign.");
    expect(dialog).toHaveTextContent(`because: "${WHY}"`);
    expect(onDecide).not.toHaveBeenCalled();                                    // two steps: nothing is sent yet
    await user.click(within(dialog).getByRole("button", { name: "Yes, do it" }));
    expect(onDecide).toHaveBeenCalledWith({ items: [HELD], decision: "approved", reason: WHY, by: "A Manager", fingerprint: a.fingerprint, via: "console", exception: true });
  });

  it("rejects and keeps flagged with a reason or a note, and refers without one, as the named person", async () => {
    const onDecide = vi.fn();
    const onRefer = vi.fn();
    const user = userEvent.setup();
    const a = withExceptions();
    render(<FlaggedItem item={item(a, HELD)} approval={a} me="A Manager" editable onDecide={onDecide} onRefer={onRefer} />);
    await user.click(screen.getByRole("button", { name: "Mark as rejected" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give a reason of a few words for rejecting");
    await user.click(screen.getByRole("button", { name: "Keep flagged" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Add a note");
    await user.type(screen.getByLabelText("Reason, in words (for the log)"), "the owner moved out");
    await user.click(screen.getByRole("button", { name: "Mark as rejected" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onDecide).toHaveBeenLastCalledWith(expect.objectContaining({ items: [HELD], decision: "rejected", reason: "the owner moved out", exception: true }));
    await user.type(screen.getByLabelText("Reason, in words (for the log)"), "wait for the rule");
    await user.click(screen.getByRole("button", { name: "Keep flagged" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onDecide).toHaveBeenLastCalledWith(expect.objectContaining({ decision: "held", reason: "wait for the rule", exception: true }));
    await user.click(screen.getByRole("button", { name: "Refer to the board" }));
    expect(screen.getByRole("group", { name: "Refer" })).toHaveTextContent("Nothing is decided and nothing is written");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onRefer).toHaveBeenCalledWith({ item: HELD, by: "A Manager", fingerprint: a.fingerprint, via: "console" });
  });

  it("never signs as jason: without a person's name the actions stay unavailable", async () => {
    const user = userEvent.setup();
    const a = withExceptions();
    render(<FlaggedItem item={item(a, HELD)} approval={a} me="Jason" editable onDecide={vi.fn()} onRefer={vi.fn()} />);
    await user.type(screen.getByLabelText("Reason, in words (for the log)"), WHY);
    await user.click(screen.getByRole("button", { name: "Mark approved as a one-off exception" }));
    expect(screen.getByRole("alert")).toHaveTextContent("jason never signs");
    expect(screen.getByRole("button", { name: "Refer to the board" })).toHaveAttribute("aria-disabled", "true");
  });

  it("shows the history but no actions when the plan is no longer open to decisions", () => {
    const a = withExceptions(1);
    render(<FlaggedItem item={item(a, HELD)} approval={a} me="A Manager" editable={false} />);
    expect(screen.queryByRole("button", { name: "Mark approved as a one-off exception" })).toBeNull();
    expect(screen.getByText(/open while the plan is planned or in review/)).toBeInTheDocument();
    expect(screen.getByText(/case 1: the owner's written answer/)).toBeInTheDocument();
  });

  it("nudges toward a rule at two exceptions, with the board item's link, and not before", () => {
    const board = (id: string) => `#/actions?item=${id}`;
    const { unmount } = render(<PlanReview approval={withExceptions(1)} me="A Manager" now={NOW} boardHref={board} />);
    expect(screen.queryByText(/has been decided by exception/)).toBeNull();
    unmount();
    render(<PlanReview approval={withExceptions(2)} me="A Manager" now={NOW} boardHref={board} />);
    const nudge = screen.getAllByText(/This finding has been decided by exception 2 times\. The board may want to write a rule/);
    expect(nudge).toHaveLength(1);                                              // once for the finding, not once per item
    expect(within(nudge[0].closest("p") as HTMLElement).getByRole("link", { name: BOARD })).toHaveAttribute("href", `#/actions?item=${BOARD}`);
  });

  it("uses the server's threshold for the nudge", () => {
    const a = { ...withExceptions(2), flagged: { flagged: 2, decidedByException: 0, nudge: 3 } };
    render(<PlanReview approval={a} me="A Manager" now={NOW} />);
    expect(screen.queryByText(/has been decided by exception/)).toBeNull();
  });

  it("is decided through PlanReview as an exception, and referred, in the named person's name", async () => {
    const onDecide = vi.fn(async () => {});
    const onRefer = vi.fn(async () => {});
    const user = userEvent.setup();
    const a = withExceptions();
    render(<PlanReview approval={a} me="A Manager" now={NOW} onDecide={onDecide} onRefer={onRefer} />);
    const panel = document.querySelector(`[data-flagged-item="${HELD2}"]`) as HTMLElement;
    await user.type(within(panel).getByLabelText("Reason, in words (for the log)"), WHY);
    await user.click(within(panel).getByRole("button", { name: "Mark approved as a one-off exception" }));
    await user.click(within(panel).getByRole("button", { name: "Yes, do it" }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ items: [HELD2], decision: "approved", exception: true, by: "A Manager" }));
    expect(await screen.findByText(/Recorded: approved \(one-off exception\) as A Manager/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Refer to the board" }));
    await user.click(within(panel).getByRole("button", { name: "Yes, do it" }));
    expect(onRefer).toHaveBeenCalledWith({ item: HELD2, by: "A Manager", fingerprint: a.fingerprint, via: "console" });
    expect(await screen.findByText(/Referred to the board as A Manager/)).toBeInTheDocument();
  });

  it("is never approved by the approve bar, which counts it and signs for exceptions apart from changes", async () => {
    const onDecide = vi.fn();
    const user = userEvent.setup();
    const a = planned();
    const { unmount } = render(<ApproveBar approval={a} selected={[HELD, HELD2]} me="A Manager" onDecide={onDecide} />);
    expect(screen.getByText("Select changes in the list")).toBeInTheDocument();       // a flagged item is dropped from the selection
    expect(screen.getByText(/2 flagged for review and 1 for a person are not part of this approval/)).toBeInTheDocument();
    expect(decisionProblem(a, [HELD], "approved", "")).toMatch(/flagged for review, never approvable here/);
    expect(screen.getByRole("button", { name: "Mark as approved" })).toHaveAttribute("aria-disabled", "true");
    expect(onDecide).not.toHaveBeenCalled();
    unmount();
    // an exception approved: written like an approved change, and the second person is needed
    const decided = planned();
    for (const i of decided.items) if (i.class === "approvable") Object.assign(i, { decision: "rejected", decidedBy: "A Manager", reason: "later" });
    Object.assign(item(decided, HELD), { decision: "approved", decidedBy: "A Manager", exception: true, reason: WHY, highStakes: true });
    expect(tally(decided)).toMatchObject({ approved: 0, rejected: 12, undecided: 0, exceptions: 1 });
    expect(needsSecond(decided)).toBe(true);
    expect(needsSecond(planned())).toBe(false);
    render(<ApproveBar approval={{ ...decided, status: "in_review" }} selected={[]} me="A Manager" onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Sign this plan as A Manager" }));
    const sign = screen.getAllByRole("group", { name: "Confirm" }).pop() as HTMLElement;
    expect(sign).toHaveTextContent("0 marked approved and 1 exception, 12 rejected");
    expect(sign).not.toHaveTextContent("the plan is withdrawn");                      // an exception is approved: not withdrawn
  });

  it("words a referral in the history, naming the person and the board item", () => {
    const e = { seq: 9, at: "2026-10-11T12:00:00+00:00", event: "item.referred", os_user: "x", actor: "A Manager", detail: `board item ${BOARD}`, prev: "", hash: "" } as AuditEntry;
    expect(auditWords(e)).toBe(`A Manager referred a flagged finding to the board (board item ${BOARD})`);
  });

  it("counts an approved exception among the approved changes at apply", () => {
    const a = signed();
    Object.assign(item(a, HELD), { decision: "approved", decidedBy: "A Manager", exception: true, reason: WHY, highStakes: true });
    expect(results(a).approved).toHaveLength(13);
    expect(results({ items: planned().items }).approved).toHaveLength(0);
    expect(flaggedCounts(a)).toEqual({ flagged: 2, decidedByException: 1 });
    expect(nudged(withExceptions(2).items.find((i) => i.id === HELD) as PlanItem)).toBe(true);
    expect(nudged(item(planned(), HELD))).toBe(false);
  });
});
