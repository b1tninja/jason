/// <reference types="vite/client" />
/** The words a plan is told in (docs/console/approval-clarity.md): a plan that is over is not "changed since review" or "to decide",
 * a pause is not "ready to apply", the header and the list say one sentence, and a failure is not lumped with a change or a doubt. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import appliedJson from "../../../tests/fixtures/approvals/example-village-applied.json";
import { ChangedBanner } from "./ChangedBanner";
import { PlanProgress } from "./PlanProgress";
import { PlanReview } from "./PlanReview";
import { counts } from "../views/PlanApprovals";
import {
  applyOutcomeWords, isClosed, listState, planState, staleness, stateSentence, waitingWords, type ApplyHold, type Approval, type KindFacts,
} from "../lib/approvals";

const planned = () => structuredClone(plannedJson) as unknown as Approval;
const applied = () => structuredClone(appliedJson) as unknown as Approval;
const NOW = "2026-10-03T19:00:00+00:00";
const A = { name: "A Manager", at: NOW, fingerprint: "f", role: "manager", via: "console" as const };
const KIND: KindFacts = {
  key: "owner-info-tags", title: "Owner information tags", system: "payhoa", risk: "R2", riskWords: "member-facing record",
  approver: "one person", twoPerson: false, reversible: "a tag removed again", maxAgeHours: 24,
};
/** Every approvable change marked approved, then signed by A Manager: waiting to be applied. */
function signed(): Approval {
  const a = planned();
  for (const i of a.items) if (i.class === "approvable") Object.assign(i, { decision: "approved", decidedBy: "A Manager", decidedAt: NOW });
  return { ...a, status: "approved", first: A };
}
/** An applied plan whose apply found three items changed, one failed, one uncertain. */
function appliedWithTroubles(): Approval {
  const a = applied();
  const done = a.items.filter((i) => i.result === "applied");
  Object.assign(done[0], { result: "changed", resultDetail: "changed since review" });
  Object.assign(done[1], { result: "failed" });
  Object.assign(done[2], { result: "uncertain" });
  return a;
}

describe("a plan that is over is not 'changed since review'", () => {
  it("is never stale once applied, failed, or withdrawn, though an item was found changed; a superseded plan keeps its own banner", () => {
    for (const status of ["applied", "failed", "withdrawn"] as const)
      expect(staleness({ ...appliedWithTroubles(), status }, { now: NOW })).toMatchObject({ blocked: false, changed: [], tooOld: false });
    expect(staleness({ ...appliedWithTroubles(), status: "superseded" }, { now: NOW })).toMatchObject({ blocked: true, superseded: true });
    // an open plan with the same item is still blocked: that is the case the banner is for
    expect(staleness({ ...appliedWithTroubles(), status: "approved" }, { now: NOW }).blocked).toBe(true);
    expect(["applied", "failed", "withdrawn", "superseded"].every((s) => isClosed(s as Approval["status"]))).toBe(true);
    expect(isClosed("approved")).toBe(false);
  });

  it("draws no banner and no 'Signing is blocked' line on an applied plan with a changed item", () => {
    const a = appliedWithTroubles();
    const { container } = render(<ChangedBanner approval={a} now={NOW} />);
    expect(container).toBeEmptyDOMElement();
    render(<PlanReview approval={a} me="A Manager" now={NOW} kind={KIND} />);
    expect(screen.queryByText(/Signing is blocked/)).toBeNull();
    expect(screen.queryByText(/The plan changed since it was reviewed/)).toBeNull();
    expect(screen.queryByText(/nothing more can be decided or signed/)).toBeNull();
  });

  it("still says it of an open plan whose item changed", () => {
    render(<PlanReview approval={{ ...appliedWithTroubles(), status: "approved" }} me="A Manager" now={NOW} kind={KIND} />);
    expect(screen.getByText(/Signing is blocked: the plan changed since review/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "The plan changed since it was reviewed" })).toBeInTheDocument();
  });

  it("says 'to decide' of an open plan and something else of a closed one", () => {
    const open = { ...planned(), status: "in_review" } as never;
    expect(counts(open)).toMatch(/\d+ to decide/);
    for (const status of ["applied", "withdrawn", "superseded", "failed"] as const) expect(counts({ ...applied(), status } as never)).not.toMatch(/to decide/);
    expect(counts(applied() as never)).toBe("7 applied");
    expect(counts({ ...appliedWithTroubles(), status: "applied" } as never)).toBe("4 applied, 1 failed, 1 changed since review, 1 uncertain");
    expect(counts({ ...planned(), status: "withdrawn" } as never)).toBe("nothing left to decide");
    // the server's summary row: items is a count, the results come by word
    const summary = { id: "apr-x", kind: "k", title: "t", status: "applied", items: 17, byClass: { approvable: 6 }, byResult: { applied: 6, changed: 1 } } as never;
    expect(counts(summary)).toBe("6 applied, 1 changed since review");
  });
});

describe("failed, changed since review, and uncertain are said apart", () => {
  it("lists each kind with its own count, and leaves a kind of none out", () => {
    expect(applyOutcomeWords({ failed: 1, changed: 1, uncertain: 1 })).toBe("1 failed, 1 changed since review, 1 uncertain");
    expect(applyOutcomeWords({ failed: 0, changed: 2, uncertain: 0 })).toBe("2 changed since review");
    expect(applyOutcomeWords({ failed: 0, changed: 0, uncertain: 0 })).toBe("");
    expect(applyOutcomeWords({ failed: 0, changed: 0, uncertain: 0 }, true)).toBe("0 failed");
  });

  it("tells an applied plan's trouble in three counts, not 'N failed'", () => {
    expect(planState(appliedWithTroubles())).toBe("Applied: 4 changes made, 1 failed, 1 changed since review, 1 uncertain.");
    expect(planState(applied())).toBe("Applied: 7 changes made, 0 failed.");
    expect(planState({ status: "applied", items: 17, byResult: { applied: 12, failed: 1, changed: 2, uncertain: 1 } }))
      .toBe("Applied: 12 changes made, 1 failed, 2 changed since review, 1 uncertain.");
  });

  it("names the kinds of a failed apply when there is more than one", () => {
    expect(planState({ ...appliedWithTroubles(), status: "failed" })).toBe("Failed: 3 changes were not made (1 failed, 1 changed since review, 1 uncertain)");
  });
});

describe("a plan in its pause is held, not ready to apply", () => {
  const hold: ApplyHold = { endsAt: "2026-10-03T19:42:39+00:00", secondsLeft: 2559, words: "The board holds a signed plan for 45 minutes." };

  it("says 'ready to apply' once the pause is over and not while it runs", () => {
    const a = signed();
    const ready = render(<PlanProgress approval={a} needsSecond={false} ready kind={KIND} />);
    expect(screen.getByText("Signed by A Manager, ready to apply.")).toBeInTheDocument();
    ready.unmount();
    render(<PlanProgress approval={a} needsSecond={false} ready kind={KIND} hold={hold} />);
    expect(screen.queryByText(/ready to apply/)).toBeNull();
    expect(screen.getByText(/Held by the board's pause until/)).toBeInTheDocument();
  });

  it("says the same sentence in the plan's header and in the list, pause included", () => {
    const server = { waitingToApply: true, waitingHours: 0, waitingStale: false, pausing: true };
    const a = { ...signed(), ...server };
    const row = listState(a, "A Manager");
    expect(row).toBe("Signed, waiting to be applied · less than an hour · held by the board's pause");
    render(<PlanReview approval={a} me="A Manager" now={NOW} kind={KIND} hold={hold} />);
    expect(document.querySelector(".plan-state")!.textContent).toBe(row);
    expect(screen.queryByText(/Signed, not applied yet/)).toBeNull();
    expect(screen.queryByText(/ready to apply/)).toBeNull();
  });

  it("marks the header as held when the page knows the pause but the record does not carry it", () => {
    render(<PlanReview approval={{ ...signed(), waitingToApply: true, waitingHours: 3 }} me="A Manager" now={NOW} kind={KIND} hold={hold} />);
    expect(document.querySelector(".plan-state")!.textContent).toBe("Signed, waiting to be applied · 3 hours · held by the board's pause");
  });

  it("is one function for both, and the state words stay the old ones for a plan the server does not call waiting", () => {
    expect(stateSentence(signed(), "A Manager")).toBe("Signed, not applied yet. Nothing has been written.");
    expect(stateSentence({ ...signed(), waitingToApply: true, waitingHours: 5 }, "A Manager")).toBe(waitingWords({ waitingToApply: true, waitingHours: 5 }));
  });
});
