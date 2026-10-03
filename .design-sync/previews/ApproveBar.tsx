import { ApproveBar, CostLine, type Approval, type PlanItem } from "jason-ui";

const FP = "f12f68bc95107ae48a4247a73ab578d6bd8a324fdb64e6aead6cc6ea4e418b59";
const row = (id: string, label: string, value: string, extra: Partial<PlanItem> = {}): PlanItem => ({
  id, op: "member tag +", target: "member:10", label, group: label, value, why: "this cycle's answer", basis: "4cd8072d".padEnd(64, "0"),
  class: "approvable", decision: "undecided", result: "pending", ...extra,
});
const items: PlanItem[] = [
  row("7344a0e1a0d1efa6", "101 EXAMPLE WAY: Ana Example", "Notices by Mail"),
  row("ce429297c68875e6", "101 EXAMPLE WAY: Ana Example", "Owner Info 2027"),
  row("dceffc0b8fac3f1d", "102 EXAMPLE WAY: Ben Sample", "Notices by Email"),
  row("79b0872b69c00a3f", "102 EXAMPLE WAY: Ben Sample", "Owner Info 2027"),
  row("acad6529c029339a", "101 EXAMPLE WAY: Ana Example", "Rental", { class: "held_for_board", boardItem: "rental-approvals-4-15" }),
  row("3bb2cb92e752903d", "103 EXAMPLE WAY: Cy Placeholder", "a person enters the secondary delivery", { class: "for_a_person" }),
];
const approval: Approval = {
  id: "apr-20261003T183801-4f5b", kind: "owner-info-tags", title: "Owner information: PayHOA tags and request completions", status: "planned",
  fingerprint: FP, readAt: "2026-10-03T18:38:01+00:00", requestedBy: "A Manager", requestedAt: "2026-10-03T18:38:01+00:00", items, decisions: [],
  costCents: null, summary: { cost: "No charge: PayHOA tag changes and request status" },
};
const decided = (d: PlanItem["decision"][]): Approval => ({
  ...approval, status: "in_review",
  items: items.map((i, n) => (d[n] && d[n] !== "undecided" ? { ...i, decision: d[n], decidedBy: "Jane Example", reason: d[n] === "approved" ? "" : "Ben asked to confirm by phone first" } : i)),
});
const cost = <CostLine {...approval} />;

/** Nothing decided, two changes selected: the decide row, and the sign button waiting on the rest. */
export const Selecting = () => <ApproveBar approval={approval} selected={["7344a0e1a0d1efa6", "ce429297c68875e6"]} me="Jane Example" cost={cost} onDecide={() => {}} onSubmit={() => {}} />;

/** Partly decided: the tally says what is left to decide before signing. */
export const PartlyDecided = () => <ApproveBar approval={decided(["approved", "approved", "rejected"])} selected={[]} me="Jane Example" cost={cost} onDecide={() => {}} onSubmit={() => {}} />;

/** Every change decided: the button says exactly what is signed, and by whom. */
export const ReadyToSign = () => <ApproveBar approval={decided(["approved", "approved", "rejected", "approved"])} selected={[]} me="Jane Example" cost={cost} onDecide={() => {}} onSubmit={() => {}} />;

/** The plan changed since review: nothing can be decided or signed. */
export const Blocked = () => <ApproveBar approval={approval} selected={["7344a0e1a0d1efa6"]} me="Jane Example" blocked cost={cost} />;
