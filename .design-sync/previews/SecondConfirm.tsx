import { SecondConfirm, type Approval } from "jason-ui";

const FP = "5d0e19a7c2b3".padEnd(64, "0");
const signed: Approval = {
  id: "apr-20261002T141000-7a1c", kind: "owner-info-tags", title: "Owner information: PayHOA tags and request completions", status: "approved",
  fingerprint: FP, readAt: "2026-10-02T14:10:00+00:00", requestedBy: "Jane Example", requestedAt: "2026-10-02T14:10:00+00:00",
  items: [{ id: "6f35931565f4e006", op: "member tag +", target: "member:13", label: "104 EXAMPLE WAY: Dee Fictional", value: "Notices by Email", why: "this cycle's answer (payhoa:504)", basis: "bd148e0e".padEnd(64, "0"), class: "approvable", decision: "approved", decidedBy: "Jane Example", highStakes: true, result: "pending" }],
  decisions: [], first: { name: "Jane Example", at: "2026-10-02T15:02:00+00:00", fingerprint: FP, role: "manager", via: "console" }, second: null,
};

/** Waiting on a second person: the rule in words, who asked and who signed first, and an empty name field. */
export const Waiting = () => <SecondConfirm approval={signed} me="Casey Sample" onConfirm={() => {}} onDecline={() => {}} />;

/** Seen by the person who signed first: told they cannot be the second. */
export const SignedFirstViewing = () => <SecondConfirm approval={signed} me="Jane Example" onConfirm={() => {}} onDecline={() => {}} />;

/** A two-person kind with no high-stakes item, still waiting. */
export const TwoPersonKind = () => <SecondConfirm approval={{ ...signed, items: signed.items.map((i) => ({ ...i, highStakes: false })) }} twoPerson me="Casey Sample" />;

/** Confirmed: both people and both times. */
export const Confirmed = () => <SecondConfirm approval={{ ...signed, second: { name: "Casey Sample", at: "2026-10-03T09:05:00+00:00", fingerprint: FP, role: "director", via: "console" } }} />;
