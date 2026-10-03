import { useState } from "react";
import { ReadinessRow, type AgendaCandidate } from "jason-ui";

const base = { ask: "", motion: "", allot: 10, order: 0, packet: [] as AgendaCandidate["packet"], include: true };

const landscape: AgendaCandidate = {
  ...base, id: "landscape-2027", title: "Renew the landscape contract", ask: "Approve a contract", session: "open session", authority: "CC&R 7.1; CIV 5350", kind: "action", allot: 15,
  motion: "Move to approve the contract with Greenway Landscape for 2027 at $1,850.00 a month.",
  readiness: { ready: true, checks: [{ label: "Motion drafted", ok: true }, { label: "Supporting documents", ok: true }, { label: "Options brief written", ok: true }, { label: "Notice can still be given by 2026-10-17 (CIV 4920)", ok: true }] },
  suggestion: "",
};

const loan: AgendaCandidate = {
  ...base, id: "reserve-loan", title: "Reserve loan not restored", ask: "Decide whether to restore the loan", session: "open session", authority: "CIV 5515(d)", kind: "action", include: false,
  readiness: { ready: false, checks: [{ label: "Motion drafted", ok: false, why: "no motion drafted yet" }, { label: "Supporting documents", ok: false, why: "the transfer ledger is not in the packet" }, { label: "Notice can still be given by 2026-10-17 (CIV 4920)", ok: true }] },
  suggestion: "no motion drafted yet; the treasurer's transfer ledger would go in the packet",
};

const hearing: AgendaCandidate = {
  ...base, id: "payment-plan-7", title: "Payment plan, unit 7", ask: "Decide the plan", session: "executive session", kind: "executive", order: 1,
  readiness: { ready: true, checks: [{ label: "Executive session marked (CIV 4935)", ok: true }, { label: "Owner notified of the hearing (CIV 5855)", ok: true }] },
  suggestion: "noted generally in the next open minutes (CIV 4935(e))",
};

function Row({ candidate }: { candidate: AgendaCandidate }) {
  const [include, setInclude] = useState(candidate.include);
  return <ReadinessRow candidate={{ ...candidate, include }} onToggle={setInclude} />;
}

/** Ready: every check passes, the pill reads ready, no line from jason. */
export const Ready = () => <Row candidate={landscape} />;

/** Needs work: the failing checks in warn, the item left off the agenda, and jason's one line saying what is missing. */
export const NeedsWork = () => <Row candidate={loan} />;

/** An executive-session matter: the warn badge beside the pill. */
export const Executive = () => <Row candidate={hearing} />;

/** The three together as the Ready to act step stacks them. */
export const Stacked = () => (
  <div className="stack" style={{ display: "grid", gap: 10 }}>
    <Row candidate={landscape} />
    <Row candidate={loan} />
    <Row candidate={hearing} />
  </div>
);
