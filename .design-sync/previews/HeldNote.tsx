import { HeldNote, type PlanItem } from "jason-ui";

const base = { op: "unit tag -", target: "unit:1", label: "101 EXAMPLE WAY: Ana Example", group: "101 EXAMPLE WAY: Ana Example", value: "Rental", why: "says owner-occupied; the unit is tagged Rented out", rule: "owner_responses.RULES: occupancy-vs-tag", basis: "2e2705aa73b5f3a08ff43cef633826223c021e3b27d5a0c37a329ee6df719d5e", dependsOn: [], highStakes: false, costCents: 0, decidedBy: "", decidedAt: "", reason: "", result: "pending", resultDetail: "", evidence: [], change: null } satisfies Partial<PlanItem>;
const policy: PlanItem[] = [
  { ...base, id: "acad6529c029339a", class: "held_for_board", boardItem: "rental-approvals-4-15", decision: "undecided" },
  { ...base, id: "f8c33b440bec33f9", op: "unit tag +", value: "Owner Occupied", class: "held_for_board", boardItem: "rental-approvals-4-15", decision: "undecided" },
];
const byPerson: PlanItem = { ...base, id: "dceffc0b8fac3f1d", op: "member tag +", label: "102 EXAMPLE WAY: Ben Sample", value: "Notices by Email", class: "approvable", boardItem: "", decision: "held", decidedBy: "Jane Example", decidedAt: "2026-10-03T18:55:00+00:00", reason: "the board should say how a delivery tag is chosen" };

/** Both kinds side by side, as the plan shows them: jason's policy finding (solid) and a person's decision (dashed). */
export const BothKinds = () => <div className="held-notes"><HeldNote items={[...policy, byPerson]} /></div>;

/** jason's policy finding alone, with the board item it waits on. */
export const PolicyFinding = () => <div className="held-notes"><HeldNote items={policy} /></div>;

/** A person's hold alone: who, when, and the reason. */
export const ByPerson = () => <div className="held-notes"><HeldNote items={[byPerson]} /></div>;

/** The one-line form inside a write row. */
export const Inline = () => <HeldNote items={[policy[0]]} inline />;
