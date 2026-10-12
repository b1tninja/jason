import { PlanProgress, type Approval, type PlanItem } from "jason-ui";

// A made-up Oakview plan: four tag changes, ids 'item-1'..'item-4'. Dates are fixed fake ones in 2099.
const T0 = "2099-03-02T09:00:00+00:00", T1 = "2099-03-02T09:20:00+00:00", T2 = "2099-03-02T10:05:00+00:00", T3 = "2099-03-02T11:30:00+00:00";
const FP = "0f3a9c51d27be4608a1c5d93e7b2f4406c8d1a5e9b3f7024d6c8e1a3b5f79d20";
const mk = (n: number, label: string, tag: string, over: Partial<PlanItem> = {}): PlanItem => ({
  id: `item-${n}`, op: "member tag +", target: `member:${n}`, label, group: label, value: tag, why: "this cycle's answer", basis: "5312b5da".padEnd(64, "0"),
  class: "approvable", decision: "undecided", decidedBy: "", result: "pending", resultDetail: "",
  change: { op: "add", field: "member tags", value: tag, before: "", after: tag, text: `+ ${tag} (member tags)` }, ...over,
});
const OWNER1 = "101 Example Way: A. Owner", OWNER2 = "102 Example Way: B. Owner";
const items = (over: Partial<PlanItem> = {}): PlanItem[] => [
  mk(1, OWNER1, "Notices by Email", over), mk(2, OWNER1, "Owner Info 2100", over), mk(3, OWNER2, "Notices by Mail", over), mk(4, OWNER2, "Owner Info 2100", over),
];
const marked = (): PlanItem[] => items({ decision: "approved", decidedBy: "Person 1 office", decidedAt: T1 });
const plan: Approval = {
  id: "apr-20990302T090000-0001", kind: "owner-info-tags", title: "Owner information: PayHOA tags", status: "planned", fingerprint: FP,
  readAt: T0, requestedBy: "Person 1 office", requestedAt: T0, items: items(), decisions: [], first: null, second: null, result: {},
};
const first = { name: "Person 1 office", at: T2, fingerprint: FP, role: "manager", via: "console" as const };
const second = { name: "Person 2 office", at: T3, fingerprint: FP, role: "director", via: "console" as const };
const kind = { key: "owner-info-tags", title: "Owner information tags", system: "payhoa", risk: "R2", riskWords: "member-facing record", approver: "one person", twoPerson: false, reversible: "a tag removed again", maxAgeHours: 24 };

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 640 }}>{children}</div>;

/** Planned and nothing marked: the strip is at Review, and the standing line says nothing has been written and that no change is marked yet. */
export const AtReview = () => <Frame><PlanProgress approval={plan} kind={kind} needsSecond={false} me="Person 1 office" /></Frame>;

/** Every change marked: Review is complete (who marked and when) and the plan waits for a signature. */
export const AtSign = () => (
  <Frame><PlanProgress approval={{ ...plan, status: "in_review", items: marked() }} kind={kind} needsSecond={false} me="Person 1 office" /></Frame>
);

/** A plan that needs two people: the Second signature step appears, naming the first signer and who may not sign again. */
export const AtSecondSignature = () => (
  <Frame><PlanProgress approval={{ ...plan, status: "approved", items: marked(), first }} kind={{ ...kind, twoPerson: true }} needsSecond me="Person 2 office" /></Frame>
);

/** Signed by both and ready: the Apply step is current and a person at a terminal is given the command with Copy. */
export const ReadyAtTerminal = () => (
  <Frame><PlanProgress approval={{ ...plan, status: "approved", items: marked(), first, second }} kind={{ ...kind, twoPerson: true }} needsSecond ready me="Person 1 office" /></Frame>
);

/** The board's pause has not ended: Apply says so and shows no command until it does. */
export const HeldByPause = () => (
  <Frame>
    <PlanProgress approval={{ ...plan, status: "approved", items: marked(), first }} kind={kind} needsSecond={false} ready me="Person 1 office"
      hold={{ endsAt: "2099-03-03T11:30:00+00:00", secondsLeft: 86400, words: "The board's pause after the last signature" }} />
  </Frame>
);

/** Applied: every step complete, who ran it and when, and the result line instead of a promise. */
export const Applied = () => (
  <Frame>
    <PlanProgress kind={kind} needsSecond={false} me="Person 1 office"
      approval={{ ...plan, status: "applied", items: marked().map((i) => ({ ...i, result: "applied", resultDetail: "written" })), first, result: { applied: 4, by: "Person 1 office", at: "2099-03-02T12:10:00+00:00" } }} />
  </Frame>
);
