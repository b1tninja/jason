import { AuditLog, type AuditEntry } from "jason-ui";

// Lines 3–8 of the approvals engine's Example Village audit log (tests/fixtures/approvals/example-village-audit.jsonl).
const FP = "f12f68bc95107ae48a4247a73ab578d6bd8a324fdb64e6aead6cc6ea4e418b59";
const ID = "apr-20261003T183801-51fb";
const at = "2026-10-03T18:38:01+00:00";
const approved = ["0567aea365e18877", "6ae6c864f8a1250c", "6f35931565f4e006", "79b0872b69c00a3f", "9611d0b11945aa9a", "a0f145a0cdf5357c", "dceffc0b8fac3f1d"];
const line = (seq: number, prev: string, hash: string, rest: Partial<AuditEntry>): AuditEntry =>
  ({ seq, at, os_user: "manager", approval: ID, kind: "owner-info-tags", actor: "A Manager", via: "cli", fingerprint: FP, prev, hash, event: "plan.created", ...rest });
const entries: AuditEntry[] = [
  line(3, "dc9da7799f9d53ed14f0e6eb418f78b26f66493eaa2f50f23cac555130045d85", "21ee49033ba120203d8133f1aea3c1b3069d7026328cc41ff31a1afe7b708f92", { event: "plan.created", result: { approvable: 12, for_a_person: 1, held_for_board: 2, informational: 2 } }),
  line(4, "21ee49033ba120203d8133f1aea3c1b3069d7026328cc41ff31a1afe7b708f92", "95c7ffa4e226a47a16fa022639e1d3adeba17dd220819939976d1fa614056b85", { event: "item.decided", items: approved, result: "approved" }),
  line(5, "95c7ffa4e226a47a16fa022639e1d3adeba17dd220819939976d1fa614056b85", "6c43019727936c20427e123b963e280db4501225ec2d6c82c53db8cd7910e2d0", { event: "item.decided", items: ["7344a0e1a0d1efa6", "9f524866de8c5727", "a6011a0ad7cbb357", "ce429297c68875e6", "e956ce6be8a40eaf"], result: "rejected", detail: "next week" }),
  line(6, "6c43019727936c20427e123b963e280db4501225ec2d6c82c53db8cd7910e2d0", "7bf3b10c426fa89b7c0c436efffb8ff70fb1a271c249f3674342e554245c53ac", { event: "approval.submitted", items: approved, result: "partially_approved", role: "manager" }),
  line(7, "7bf3b10c426fa89b7c0c436efffb8ff70fb1a271c249f3674342e554245c53ac", "2adbbc368b70640c84197155043de168409710e338eaf0811f537dd26feb2e1e", { event: "apply.started", items: approved }),
  line(8, "2adbbc368b70640c84197155043de168409710e338eaf0811f537dd26feb2e1e", "8c02edec58451d1d8dfe755ddb46fad0706a9a27b00bf1226520251a89102b79", { event: "item.applying", item: "dceffc0b8fac3f1d", label: "102 EXAMPLE WAY: Ben Sample", op: "member tag +", value: "Notices by Email" }),
];
const done: AuditEntry[] = [
  line(21, "6e385defd2bb442a6cec2e57874217a8d8e62d1dc15307610d8ae6e65c44888c", "a5c29ea85d2499b4e7aef14f641878caee11cf5bc6171c5bd5f43b5642627365", { event: "item.applied", item: "0567aea365e18877", label: "104 EXAMPLE WAY: Dee Fictional", op: "complete request", value: "complete", result: "applied", detail: "marked complete; the owner is thanked" }),
  line(22, "a5c29ea85d2499b4e7aef14f641878caee11cf5bc6171c5bd5f43b5642627365", "37cf1f56ffa1e23bf6bc2a4212fa7047a80dfacfcbfa1a10acd83e9923de8777", { event: "approval.applied", result: { applied: 7, not_applied: 10 } }),
];

/** Planned by jason (asked by a named person), decided, signed, and the apply started: each line names the one before. */
export const History = () => <AuditLog entries={entries} />;

/** Inside a plan: one approval, the intent lines left out, and the server's chain check. */
export const Compact = () => <AuditLog entries={[...entries, ...done]} approval={ID} compact chain={{ ok: true, why: "22 lines, whole" }} />;

/** A broken chain, as the server's verify reports it. */
export const Broken = () => <AuditLog entries={done} chain={{ ok: false, line: 21, why: "the hash does not match the line" }} />;

/** Provenance glyphs in one log: planned, signed, declined, refused, failed, blocked. */
export const EveryGlyph = () => (
  <AuditLog entries={[
    line(30, "a", "b", { event: "plan.created", result: { approvable: 3 } }),
    line(31, "b", "c", { event: "approval.submitted", result: "approved", items: ["x1", "x2"] }),
    line(32, "c", "d", { event: "approval.declined", detail: "second person declined" }),
    line(33, "d", "e", { event: "apply.refused", detail: "plan changed since it was approved" }),
    line(34, "e", "f", { event: "item.failed", item: "x1", label: "105 EXAMPLE WAY: Lee Placeholder", op: "member tag +", value: "Paperless", detail: "PayHOA refused" }),
    line(35, "f", "g", { event: "item.blocked", item: "x2", label: "106 EXAMPLE WAY: Kim Invented", op: "member tag +", value: "Notices by Email" }),
  ]} />
);
