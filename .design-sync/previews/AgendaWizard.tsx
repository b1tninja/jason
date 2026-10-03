import { useEffect, useRef } from "react";
import { AgendaWizard, type AgendaCandidate, type AgendaPlan } from "jason-ui";

// The wizard keeps its step in state and takes no initial-step prop, so a cell past step 1 clicks the step button once
// after mount, as a person would. Nothing is saved: onSave only records.

const landscape: AgendaCandidate = {
  id: "landscape-2027", title: "Renew the landscape contract", ask: "Approve a contract", session: "open session", authority: "CC&R 7.1; CIV 5350", kind: "action", include: true, order: 0, allot: 15,
  motion: "Move to approve the contract with Greenway Landscape for 2027 at $1,850.00 a month, and authorize the president to sign.",
  packet: [{ id: "f-bid-a", name: "Greenway Landscape bid 2027.pdf", kind: "pdf", url: "https://drive.google.com/file/d/f-bid-a/view" }, { id: "f-bid-b", name: "Sierra Turf Care proposal.pdf", kind: "pdf", url: "" }],
  brief: { question: "Which landscape contract?", criteria: ["Monthly cost", "Term"], options: [{ label: "Renew with Greenway", values: ["$1,850.00", "two years"] }, { label: "Switch to Sierra Turf", values: ["$1,640.00", "one year"] }] },
  readiness: { ready: true, checks: [{ label: "Motion drafted", ok: true }, { label: "Supporting documents", ok: true }, { label: "Options brief written", ok: true }, { label: "Notice can still be given by 2026-10-17 (CIV 4920)", ok: true }] },
  suggestion: "",
};
const loan: AgendaCandidate = {
  id: "reserve-loan", title: "Reserve loan not restored", ask: "Decide whether to restore the loan", session: "open session", authority: "CIV 5515(d)", evidence: ["jason reserves --transfers"], kind: "action", include: true, order: 1, allot: 10, motion: "", packet: [], brief: null,
  readiness: { ready: false, checks: [{ label: "Motion drafted", ok: false, why: "no motion drafted yet" }, { label: "Supporting documents", ok: false, why: "the transfer ledger is not in the packet" }, { label: "Notice can still be given by 2026-10-17 (CIV 4920)", ok: true }] },
  suggestion: "no motion drafted yet; the treasurer's transfer ledger would go in the packet",
};
const minutes: AgendaCandidate = {
  id: "minutes-2026-09", title: "Approve the September minutes", ask: "Approve the minutes", session: "open session", kind: "consent", include: true, order: 2, allot: 3, motion: "Move to approve the minutes of the 2026-09-16 open meeting as presented.", packet: [{ id: "f-min", name: "Minutes 2026-09-16 (draft)", kind: "doc", url: "https://docs.google.com/document/d/f-min" }], brief: null,
  readiness: { ready: true, checks: [{ label: "Motion drafted", ok: true }, { label: "Supporting documents", ok: true }] }, suggestion: "",
};
const hearing: AgendaCandidate = {
  id: "payment-plan-7", title: "Payment plan, unit 7", ask: "Decide the plan", session: "executive session", kind: "executive", include: true, order: 3, allot: 10, motion: "", packet: [], brief: null,
  readiness: { ready: true, checks: [{ label: "Executive session marked (CIV 4935)", ok: true }, { label: "Owner notified of the hearing (CIV 5855)", ok: true }] }, suggestion: "noted generally in the next open minutes (CIV 4935(e))",
};

const plan: AgendaPlan = {
  found: true, date: "2026-10-21", today: "2026-10-03", noticeBy: "2026-10-17", executiveNoticeBy: "2026-10-19", directors: ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"], decisions: [],
  basics: { date: "2026-10-21", start: "18:30", format: "hybrid", location: "Clubhouse, 123 Main St", join: "https://zoom.example/j/000000000", dialIn: "+1 555 010 0100, meeting 000 000 000", help: "the manager, 555-010-0199, manager@example.org" },
  zoom: { topic: "Board of directors, open meeting 2026-10-21", joinUrl: "https://zoom.example/j/000000000", dialIn: "+1 555 010 0100", command: "jason zoom --create --date 2026-10-21 --start 18:30 --yes", note: "The notice needs the join link and the telephone option." },
  candidates: [landscape, loan, minutes, hearing], kinds: ["consent", "discussion", "action", "executive"], formats: ["in person", "hybrid", "teleconference"],
  rules: ["A physical location plus teleconference (CIV 4090(b)).", "Notice and the agenda to members four days ahead (CIV 4920).", "Clear instructions for joining and a telephone option (CIV 4926(a)).", "Every director vote is a roll call by name (CIV 4926(a)(3))."],
  notice: { by: "2026-10-17", executiveBy: "2026-10-19", required: [{ label: "Time and place of the meeting (CIV 4920)", ready: true }, { label: "Clear instructions for joining (CIV 4926(a)(1))", ready: true }, { label: "A telephone option (CIV 4926(a)(4))", ready: true }, { label: "The agenda, with each executive matter by title only (CIV 4930, 4935)", ready: false, detail: "the reserve loan item has no motion" }] },
  steps: ["Meeting", "Ready to act", "Order and motions", "Notice"],
  commands: {
    agendaDoc: "jason board --agenda 1AbC_dEfGhIjK --date 2026-10-21 --doc --yes", packetDoc: "jason board --packet --date 2026-10-21 --doc --yes", minutesDraft: "jason board --minutes 2026-10-21",
    notice: 'jason board --set <item id> --status "on agenda" --meeting 2026-10-21',
    onAgenda: ['jason board --set landscape-2027 --status "on agenda" --meeting 2026-10-21', 'jason board --set reserve-loan --status "on agenda" --meeting 2026-10-21', 'jason board --set minutes-2026-09 --status "on agenda" --meeting 2026-10-21'],
  },
  updated: "2026-10-02T17:10:00+00:00", history: [], caveats: ["The board sets the agenda; jason proposes items and checks readiness."],
};

function AtStep({ step, plan: p = plan }: { step: number; plan?: AgendaPlan }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const buttons = ref.current?.querySelectorAll<HTMLButtonElement>(".wizard-steps button");
    buttons?.[step - 1]?.click();
  }, [step]);
  return (
    <div ref={ref}>
      <AgendaWizard plan={p} onSave={() => {}} />
    </div>
  );
}

/** Step 1, Meeting: date, start, the format radios, and the fields a hybrid meeting needs beside what the format requires. */
export const Meeting = () => <AtStep step={1} />;

/** Step 2, Ready to act: the counts, then one readiness row per candidate. */
export const ReadyToAct = () => <AtStep step={2} />;

/** Step 3, Order and motions: the run of the meeting with start times, the fixed rows, kind and minutes per item, the motion, and the packet (two items, so the step fits a capture). */
export const OrderAndMotions = () => <AtStep step={3} plan={{ ...plan, candidates: [landscape, hearing] }} />;

/** Step 4, Notice: the Zoom fields, the notice checklist, and the terminal commands that put items on the noticed agenda; nothing here sends. */
export const Notice = () => <AtStep step={4} plan={{ ...plan, commands: { ...plan.commands, onAgenda: plan.commands.onAgenda.slice(0, 1) } }} />;

/** Step 2 with nothing proposed: the empty line and the zero counts. */
export const NothingProposed = () => <AtStep step={2} plan={{ ...plan, candidates: [], commands: { ...plan.commands, onAgenda: [] } }} />;
