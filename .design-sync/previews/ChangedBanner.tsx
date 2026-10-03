import { ChangedBanner, type Approval } from "jason-ui";

const FP = "f12f68bc95107ae48a4247a73ab578d6bd8a324fdb64e6aead6cc6ea4e418b59";
const approval: Approval = {
  id: "apr-20261003T183801-4f5b", kind: "owner-info-tags", title: "Owner information: PayHOA tags and request completions", status: "in_review",
  fingerprint: FP, readAt: "2026-10-03T18:38:01+00:00", requestedBy: "A Manager", requestedAt: "2026-10-03T18:38:01+00:00", items: [], decisions: [],
};
const changed = [
  { id: "dceffc0b8fac3f1d", op: "member tag +", label: "102 EXAMPLE WAY: Ben Sample", then: "5312b5da", now: "9a0c11e2", why: "what it relies on changed since review" },
  { id: "6f35931565f4e006", op: "member tag +", label: "104 EXAMPLE WAY: Dee Fictional", then: "bd148e0e", now: "", why: "no longer in the plan" },
];

/** A re-plan differs: both fingerprints, what changed, and the re-plan behind a confirm beside the terminal command. */
export const Changed = () => <ChangedBanner approval={approval} now="2026-10-03T19:00:00+00:00" me="Jane Example" onReplan={() => {}} recheck={{ then: FP, now: "4c71a0e93b58".padEnd(64, "0"), changed }} />;

/** Superseded by a newer plan after an apply was refused: read-only, with a way to the new plan. */
export const Superseded = () => (
  <ChangedBanner now="2026-10-03T19:00:00+00:00" onOpen={() => {}}
    approval={{ ...approval, status: "superseded", supersededBy: "apr-20261003T191500-9c1d", items: [{ id: "dceffc0b8fac3f1d", op: "member tag +", target: "member:11", label: "102 EXAMPLE WAY: Ben Sample", value: "Notices by Email", why: "", basis: "5312b5da", class: "approvable", decision: "approved", decidedBy: "Jane Example", result: "changed", resultDetail: "what it relies on changed since review" }] }} />
);

/** Only old: read 26 hours ago, past the 24 this kind allows; decisions stand and apply re-plans first. */
export const TooOld = () => <ChangedBanner approval={approval} now="2026-10-04T20:40:00+00:00" me="Jane Example" />;
