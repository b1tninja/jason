import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Confirm } from "./Confirm";
import {
  cleanName, decidable, decisionProblem, isApprovable, plural, short, signerProblem, tally,
  type Approval, type DecideBody, type DecisionWord, type SignBody,
} from "../lib/approvals";

const VERBS: Record<DecisionWord, [string, string]> = {
  approved: ["Approve", "approve"],
  rejected: ["Reject", "reject"],
  held: ["Hold for the board", "hold for the board"],
};

/** Decide the selected changes, then sign. Two parts:
 * 1. Approve, reject, or hold the selected approvable items. Reject and Hold need a reason; held, for-a-person, and
 *    informational items are never in `selected` (they have no checkbox, and any passed are refused).
 * 2. Sign: the tally, the cost (`cost`), the person's full name (pre-filled with `me`; never "jason"), and the button that
 *    says what is signed: "Approve 5 of 8 changes as Jane Example". With changes undecided it stays unavailable and says
 *    how many are left.
 * Each write goes through `Confirm` and posts the plan's fingerprint. `blocked` (changed since review) disables both. */
export function ApproveBar({ approval, selected, me = "", onDecide, onSubmit, blocked = false, busy, cost }: {
  approval: Approval; selected: readonly string[]; me?: string;
  onDecide?: (body: DecideBody) => void; onSubmit?: (body: SignBody) => void;
  blocked?: boolean; busy?: boolean; cost?: ReactNode;
}) {
  const uid = useId();
  const [decision, setDecision] = useState<DecisionWord>("approved");
  const [reason, setReason] = useState("");
  const [name, setName] = useState(me);
  const [decideError, setDecideError] = useState("");
  const [signError, setSignError] = useState("");
  const reasonRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => setName(me), [me]);
  useEffect(() => { setDecideError(""); }, [decision, reason, selected.length]);

  const byId = new Map(approval.items.map((i) => [i.id, i]));
  const ids = selected.filter((id) => { const i = byId.get(id); return !!i && isApprovable(i); });
  const t = tally(approval);
  const by = cleanName(name);
  const open = decidable(approval) && !blocked;
  const nameProblem = signerProblem(by);
  const fingerprint = approval.fingerprint;
  const held = approval.items.filter((i) => i.class === "held_for_board").length;
  const person = approval.items.filter((i) => i.class === "for_a_person" || i.class === "confirm_with_owner").length;

  const problem = nameProblem || decisionProblem(approval, ids, decision, reason);
  const [Verb, verb] = VERBS[decision];
  const decideLabel = `${Verb} ${ids.length || ""} selected`.replace("  ", " ");
  const refuse = () => {
    setDecideError(problem);
    if (problem && nameProblem) nameRef.current?.focus();
    else if (problem && decision !== "approved" && !reason.trim()) reasonRef.current?.focus();
  };

  const signLabel = (t.approved === t.approvable && t.approvable > 0 ? `Approve all ${plural(t.approvable, "change", "changes")}` : `Approve ${t.approved} of ${plural(t.approvable, "change", "changes")}`) + (by ? ` as ${by}` : "");
  const signWhy = !open ? "" : t.undecided > 0 ? `Decide ${t.undecided} more ${t.undecided === 1 ? "change" : "changes"} to submit.` : nameProblem;
  const decideReasonError = decideError && decision !== "approved" && !reason.trim();

  return (
    <form className={`approve-bar${blocked || !decidable(approval) ? " approve-blocked" : ""}`} aria-label="Decide and sign" onSubmit={(e) => e.preventDefault()}>
      {blocked && <p className="notice notice-warn">The plan changed since review: nothing can be decided or signed on it. Re-plan first.</p>}
      <fieldset className="approve-decide" disabled={!open}>
        <legend>Decide the selected changes</legend>
        <output className="approve-count" aria-live="polite">
          {ids.length ? `${ids.length} of ${plural(t.approvable, "change", "changes")} selected` : "Select changes in the list"}
        </output>
        <div className="row wrap approve-choices" role="radiogroup" aria-label="Decision">
          {(Object.keys(VERBS) as DecisionWord[]).map((d) => (
            <label key={d}><input type="radio" name={`${uid}-decision`} value={d} checked={decision === d} onChange={() => setDecision(d)} /> {VERBS[d][0]}</label>
          ))}
        </div>
        <label className="approve-field">
          Reason, to reject or hold
          <input ref={reasonRef} value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={decideReasonError || undefined}
            aria-describedby={`${uid}-decide-error`} placeholder="A few words, for the log" />
        </label>
        <div className="row wrap">
          {open && !problem ? (
            <Confirm busy={busy} onConfirm={() => onDecide?.({ items: ids, decision, reason: reason.trim(), by, fingerprint, via: "console" })} summary={
              <p>{Verb} {plural(ids.length, "change", "changes")} as {by}{decision !== "approved" ? `, because: "${reason.trim()}"` : ""}. Recorded with your name, the time, and fingerprint <code>{short(fingerprint)}</code>; nothing is written outside jason.</p>
            }>{decideLabel}</Confirm>
          ) : (
            <button type="button" className="primary" aria-disabled="true" disabled={!open || busy} aria-describedby={`${uid}-decide-error`} onClick={refuse}>{decideLabel}</button>
          )}
        </div>
        <p id={`${uid}-decide-error`} className="approve-error" role="alert">{decideError ? `Cannot ${verb}: ${decideError}` : ""}</p>
      </fieldset>

      <div className="approve-sign">
        <p className="approve-tally">
          <strong>{t.approved} of {t.approvable}</strong> approved · {t.rejected} rejected{t.held ? ` · ${t.held} held by a person` : ""} · {t.undecided} undecided
        </p>
        {cost}
        <label className="approve-field">
          Your full name
          <input ref={nameRef} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required disabled={!open}
            aria-invalid={(signError || decideError) && nameProblem ? true : undefined} aria-describedby={`${uid}-sign-why`} />
        </label>
        <div className="row wrap">
          {open && !signWhy ? (
            <Confirm busy={busy} onConfirm={() => onSubmit?.({ by, fingerprint, via: "console" })} summary={
              <p>
                Sign as {by}: {t.approved} approved, {t.rejected} rejected{t.held ? `, ${t.held} held for the board` : ""}, on fingerprint <code>{short(fingerprint)}</code>.
                {t.approved === 0 ? " Nothing is approved, so the plan is withdrawn." : " jason re-plans before anything is applied; if the plan changed, nothing is applied."}
              </p>
            }>{signLabel}</Confirm>
          ) : (
            <button type="button" className="primary" aria-disabled="true" disabled={!open || busy} aria-describedby={`${uid}-sign-why`} onClick={() => setSignError(signWhy)}>{signLabel}</button>
          )}
          <span id={`${uid}-sign-why`} className="muted" role="status">{signWhy || signError}</span>
        </div>
      </div>
      <p className="muted approve-note">
        {held + person > 0 && <>{held ? `${held} held for the board` : ""}{held && person ? " and " : ""}{person ? `${person} for a person` : ""} {held + person === 1 ? "is" : "are"} not part of this approval. </>}
        Your name, the time, and the plan's fingerprint <code>{short(fingerprint)}</code> are recorded. jason plans; only a named person decides and signs.
      </p>
    </form>
  );
}
