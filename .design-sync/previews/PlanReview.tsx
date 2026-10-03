import { PlanReview, type Approval, type PlanItem } from "jason-ui";

// The approvals engine's Example Village fixture (tests/fixtures/approvals/example-village-planned.json), cut to two
// owners, the board's hold, a person's task, and what follows. Props are the engine's JSON as it is.
const FP = "f12f68bc95107ae48a4247a73ab578d6bd8a324fdb64e6aead6cc6ea4e418b59";
const ev = (n: number) => [{ label: `PayHOA request ${n}`, address: `payhoa:submission:${n}` }];
const base = { why: "", group: "", rule: "the response policy's delivery row (owner_responses.RULES: delivery)", basis: "4cd8072d3d4c7b2b49bc8218e77e4462c9236566a3b7826acecb5ffeaa791549", boardItem: "", dependsOn: [], highStakes: false, costCents: 0, decision: "undecided", decidedBy: "", decidedAt: "", reason: "", result: "pending", resultDetail: "" } satisfies Partial<PlanItem>;
const ANA = "101 EXAMPLE WAY: Ana Example", BEN = "102 EXAMPLE WAY: Ben Sample";
const items: PlanItem[] = [
  { ...base, id: "7344a0e1a0d1efa6", op: "member tag -", target: "member:10", label: ANA, group: ANA, value: "Notices by Email", why: "this cycle's answer (payhoa:501)", class: "approvable", evidence: ev(501), change: { op: "remove", field: "member tags", value: "Notices by Email", before: "Notices by Email", after: "", text: "- Notices by Email (member tags)" } },
  { ...base, id: "ce429297c68875e6", op: "member tag +", target: "member:10", label: ANA, group: ANA, value: "Notices by Mail", why: "this cycle's answer (payhoa:501)", class: "approvable", evidence: ev(501), change: { op: "add", field: "member tags", value: "Notices by Mail", before: "Notices by Email", after: "Notices by Email, Notices by Mail", text: "+ Notices by Mail (member tags)" } },
  { ...base, id: "dceffc0b8fac3f1d", op: "member tag +", target: "member:11", label: BEN, group: BEN, value: "Notices by Email", why: "this cycle's answer (payhoa:502)", class: "approvable", evidence: ev(502), change: { op: "add", field: "member tags", value: "Notices by Email", before: "", after: "Notices by Email", text: "+ Notices by Email (member tags)" } },
  { ...base, id: "79b0872b69c00a3f", op: "member tag +", target: "member:11", label: BEN, group: BEN, value: "Owner Info 2027", why: "this cycle's answer (payhoa:502)", class: "approvable", evidence: ev(502), change: { op: "add", field: "member tags", value: "Owner Info 2027", before: "", after: "Owner Info 2027", text: "+ Owner Info 2027 (member tags)" } },
  { ...base, id: "9611d0b11945aa9a", op: "complete request", target: "submission:502", label: BEN, group: BEN, value: "complete", why: "nothing is left but its writes: once they are made, the request is marked complete and the board's comment is emailed to the owner", rule: "the board's owner-information completion rule", class: "approvable", evidence: ev(502), dependsOn: ["dceffc0b8fac3f1d", "79b0872b69c00a3f"], change: { op: "set", field: "request status", value: "complete", before: "pending", after: "complete", text: "request status: pending -> complete" } },
  { ...base, id: "acad6529c029339a", op: "unit tag -", target: "unit:1", label: ANA, group: ANA, value: "Rental", why: "says owner-occupied; the unit is tagged Rented out: held for the board by the response policy (occupancy-vs-tag)", rule: "owner_responses.RULES: occupancy-vs-tag", class: "held_for_board", boardItem: "rental-approvals-4-15", evidence: [{ label: "Board item rental-approvals-4-15", address: "board-item:rental-approvals-4-15" }, ...ev(501)], change: { op: "remove", field: "unit tags", value: "Rental", before: "Rental", after: "", text: "- Rental (unit tags)" } },
  { ...base, id: "3bb2cb92e752903d", op: "for a person", target: "submission:503", label: "103 EXAMPLE WAY: Cy Placeholder", group: "103 EXAMPLE WAY: Cy Placeholder", value: "a person enters the secondary delivery", why: "an answer asks what jason does not write: a person enters it in PayHOA", rule: "owner_info.FOR_A_PERSON", class: "for_a_person", evidence: ev(503), change: null },
  { ...base, id: "62e81e24baaf4a8e", op: "request stays open", target: "submission:501", label: ANA, group: ANA, value: "board: occupancy-vs-tag", why: "only a request with nothing left is completed (the board's rule); what is left: board: occupancy-vs-tag", rule: "the board's owner-information completion rule", class: "informational", evidence: ev(501), dependsOn: ["7344a0e1a0d1efa6", "ce429297c68875e6"], change: null },
];
const approval: Approval = {
  id: "apr-20261003T183801-4f5b", kind: "owner-info-tags", title: "Owner information: PayHOA tags and request completions", status: "planned",
  scope: { payhoa: true, cycle: 2027 }, profile: "example-village", fingerprint: FP, readAt: "2026-10-03T18:38:01+00:00", requestedBy: "A Manager",
  requestedAt: "2026-10-03T18:38:01+00:00", requestedVia: "cli", evidence: [{ label: "Civil Code 4040, 4041", address: "CIV 4041" }],
  items, decisions: [], first: null, second: null, costCents: null, clock: { what: "owners asked to answer by", due: "2026-10-23", daysLeft: 20 },
  summary: { cost: "No charge: PayHOA tag changes and request status" }, result: {}, supersedes: "", supersededBy: "", notes: [],
};
const NOW = "2026-10-03T19:00:00+00:00";
const decided = (over: Partial<PlanItem>[]): Approval => ({ ...approval, status: "in_review", items: items.map((i, n) => (over[n] ? { ...i, ...over[n] } : i)) });

/** Planned, nothing decided: four approvable writes and a completion, the board's hold, a person's task, and what follows. */
export const Planned = () => <PlanReview approval={approval} me="Jane Example" now={NOW} onDecide={() => {}} onSubmit={() => {}} />;

/** In review: two approved, one rejected with its reason, one held for the board by a person beside jason's policy hold. */
export const InReview = () => (
  <PlanReview me="Jane Example" now={NOW} onDecide={() => {}} onSubmit={() => {}} approval={decided([
    { decision: "approved", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:52:00+00:00" },
    { decision: "approved", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:52:00+00:00" },
    { decision: "rejected", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:53:00+00:00", reason: "Ben asked to confirm by phone first" },
    { decision: "held", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:55:00+00:00", reason: "the board should say how this tag is chosen" },
  ])} />
);

/** Changed since review: a re-plan found a write's basis moved, so approval is blocked and a re-plan is offered. */
export const ChangedSinceReview = () => (
  <PlanReview approval={approval} me="Jane Example" now={NOW} onDecide={() => {}} onReplan={() => {}}
    recheck={{ then: FP, now: "4c71a0e93b58".padEnd(64, "0"), changed: [{ id: "dceffc0b8fac3f1d", op: "member tag +", label: BEN, then: "5312b5da", now: "9a0c11e2", why: "what it relies on changed since review" }] }} />
);

/** Signed, every approvable change approved, with the apply step behind a confirm. */
export const ReadyToApply = () => (
  <PlanReview me="Jane Example" now={NOW} onApply={() => {}}
    approval={{ ...approval, status: "approved", first: { name: "Jane Example", at: NOW, fingerprint: FP, role: "manager", via: "console" }, items: items.map((i) => (i.class === "approvable" ? { ...i, decision: "approved", decidedBy: "Jane Example", decidedAt: NOW } : i)) }} />
);
