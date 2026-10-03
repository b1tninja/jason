import { ApplyResult, type Approval, type PlanItem } from "jason-ui";

const FP = "f12f68bc95107ae48a4247a73ab578d6bd8a324fdb64e6aead6cc6ea4e418b59";
const row = (id: string, label: string, text: string, extra: Partial<PlanItem>): PlanItem => ({
  id, op: "member tag +", target: "member:11", label, value: text, why: "this cycle's answer", basis: "5312b5da".padEnd(64, "0"), class: "approvable",
  decision: "approved", decidedBy: "A Manager", result: "applied", resultDetail: "written",
  change: { op: "add", field: "member tags", value: text, text: `+ ${text} (member tags)` }, ...extra,
});
const BEN = "102 EXAMPLE WAY: Ben Sample", DEE = "104 EXAMPLE WAY: Dee Fictional", ANA = "101 EXAMPLE WAY: Ana Example";
const items: PlanItem[] = [
  row("dceffc0b8fac3f1d", BEN, "Notices by Email", {}),
  row("79b0872b69c00a3f", BEN, "Owner Info 2027", {}),
  row("6f35931565f4e006", DEE, "Notices by Email", {}),
  row("9611d0b11945aa9a", BEN, "complete", { op: "complete request", resultDetail: "marked complete; the owner is thanked", change: { op: "set", field: "request status", before: "pending", after: "complete", text: "request status: pending -> complete" } }),
  row("7344a0e1a0d1efa6", ANA, "Notices by Mail", { decision: "rejected", reason: "next week", result: "not_applied", resultDetail: "rejected by A Manager: next week" }),
  row("acad6529c029339a", ANA, "Rental", { class: "held_for_board", decision: "undecided", decidedBy: "", result: "not_applied", resultDetail: "held for board" }),
];
const applied: Approval = {
  id: "apr-20261003T183801-51fb", kind: "owner-info-tags", title: "Owner information: PayHOA tags and request completions", status: "applied",
  fingerprint: FP, readAt: "2026-10-03T18:38:01+00:00", requestedBy: "A Manager", requestedAt: "2026-10-03T18:38:01+00:00", items, decisions: [],
  result: { applied: 4, not_applied: 2, at: "2026-10-03T18:38:01+00:00", by: "A Manager" },
};

/** Every approved change applied; what was not applied (rejected, held) folded below. */
export const Applied = () => <ApplyResult approval={applied} />;

/** One write failed and one is uncertain: both open, with what to do next. */
export const Failures = () => (
  <ApplyResult approval={{ ...applied, status: "failed", items: items.map((i, n) => (n === 1 ? { ...i, result: "failed", resultDetail: "PayHOA answered 500" } : n === 2 ? { ...i, result: "uncertain", resultDetail: "TimeoutError: no answer" } : i)) }} />
);

/** Refused: the re-plan found a change, nothing was written, and the plan was superseded. */
export const Refused = () => (
  <ApplyResult onOpen={() => {}} approval={{ ...applied, status: "superseded", supersededBy: "apr-20261003T191500-9c1d", result: { refused: "changed since review", changed: ["dceffc0b8fac3f1d"] }, items: items.map((i, n) => (n === 0 ? { ...i, result: "changed", resultDetail: "what it relies on changed since review" } : { ...i, result: "pending", resultDetail: "" })) }} />
);
