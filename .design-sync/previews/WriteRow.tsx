import { useState } from "react";
import { WriteRow, type PlanItem } from "jason-ui";

// Rows from the approvals engine's Example Village fixture, as the engine writes them.
const base = { group: "101 EXAMPLE WAY: Ana Example", label: "101 EXAMPLE WAY: Ana Example", rule: "the response policy's delivery row (owner_responses.RULES: delivery)", basis: "4cd8072d3d4c7b2b49bc8218e77e4462c9236566a3b7826acecb5ffeaa791549", boardItem: "", dependsOn: [], highStakes: false, costCents: 0, decision: "undecided", decidedBy: "", decidedAt: "", reason: "", result: "pending", resultDetail: "", evidence: [{ label: "PayHOA request 501", address: "payhoa:submission:501" }] } satisfies Partial<PlanItem>;
const add: PlanItem = { ...base, id: "ce429297c68875e6", op: "member tag +", target: "member:10", value: "Notices by Mail", why: "this cycle's answer (payhoa:501)", class: "approvable", change: { op: "add", field: "member tags", value: "Notices by Mail", before: "Notices by Email", after: "Notices by Email, Notices by Mail", text: "+ Notices by Mail (member tags)" } };
const remove: PlanItem = { ...base, id: "7344a0e1a0d1efa6", op: "member tag -", target: "member:10", value: "Notices by Email", why: "this cycle's answer (payhoa:501)", class: "approvable", change: { op: "remove", field: "member tags", value: "Notices by Email", before: "Notices by Email", after: "", text: "- Notices by Email (member tags)" } };
const held: PlanItem = { ...base, id: "acad6529c029339a", op: "unit tag -", target: "unit:1", value: "Rental", why: "says owner-occupied; the unit is tagged Rented out: held for the board by the response policy (occupancy-vs-tag)", rule: "owner_responses.RULES: occupancy-vs-tag", class: "held_for_board", boardItem: "rental-approvals-4-15", change: { op: "remove", field: "unit tags", value: "Rental", before: "Rental", after: "", text: "- Rental (unit tags)" } };
const person: PlanItem = { ...base, id: "3bb2cb92e752903d", op: "for a person", target: "submission:503", label: "103 EXAMPLE WAY: Cy Placeholder", group: "103 EXAMPLE WAY: Cy Placeholder", value: "a person enters the secondary delivery", why: "an answer asks what jason does not write: a person enters it in PayHOA", rule: "owner_info.FOR_A_PERSON", class: "for_a_person", change: null };
const complete: PlanItem = { ...base, id: "9611d0b11945aa9a", op: "complete request", target: "submission:502", label: "102 EXAMPLE WAY: Ben Sample", value: "complete", why: "nothing is left but its writes: once they are made, the request is marked complete and the board's comment is emailed to the owner", rule: "the board's owner-information completion rule", class: "approvable", dependsOn: ["dceffc0b8fac3f1d", "79b0872b69c00a3f"], change: { op: "set", field: "request status", value: "complete", before: "pending", after: "complete", text: "request status: pending -> complete" } };
const waits: PlanItem[] = [
  { ...add, id: "dceffc0b8fac3f1d", change: { op: "add", field: "member tags", value: "Notices by Email", before: "", after: "Notices by Email", text: "+ Notices by Email (member tags)" } },
  { ...add, id: "79b0872b69c00a3f", change: { op: "add", field: "member tags", value: "Owner Info 2027", before: "", after: "Owner Info 2027", text: "+ Owner Info 2027 (member tags)" } },
];

function Selectable({ items }: { items: PlanItem[] }) {
  const [on, setOn] = useState<string[]>([items[0].id]);
  return <div className="plan-group">{items.map((i) => <WriteRow key={i.id} item={i} selectable checked={on.includes(i.id)} onToggle={(id, c) => setOn((s) => (c ? [...s, id] : s.filter((x) => x !== id)))} />)}</div>;
}

/** Two approvable writes for one owner, the first selected: a tag removed and a tag added, before → after. */
export const Approvable = () => <Selectable items={[remove, add]} />;

/** Decided rows: approved by a named person, rejected with a reason, and held for the board by a person. */
export const Decided = () => (
  <div className="plan-group">
    <WriteRow item={{ ...remove, decision: "approved", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:52:00+00:00" }} />
    <WriteRow item={{ ...add, decision: "rejected", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:53:00+00:00", reason: "Ana asked to confirm by phone first" }} />
    <WriteRow item={{ ...add, id: "a6011a0ad7cbb357", value: "Owner Info 2027", decision: "held", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:55:00+00:00", reason: "the board should say how this tag is chosen" }} />
  </div>
);

/** Never approvable: jason's policy hold names its board item; a person's task has no checkbox either. */
export const NeverApprovable = () => <div className="plan-group"><WriteRow item={held} selectable /><WriteRow item={person} selectable /></div>;

/** A completion that waits on the owner's two writes. */
export const Completion = () => <div className="plan-group"><WriteRow item={complete} selectable waits={waits} /></div>;

/** After apply: one applied, one refused because its basis moved since review. */
export const Results = () => (
  <div className="plan-group">
    <WriteRow item={{ ...remove, decision: "approved", decidedBy: "Jane Example", result: "applied", resultDetail: "written" }} />
    <WriteRow item={{ ...add, decision: "approved", decidedBy: "Jane Example", result: "changed", resultDetail: "what it relies on changed since review" }} />
  </div>
);
