import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Confirm } from "./Confirm";
import {
  cleanName, decidable, decisionProblem, isApprovable, plural, short, signerProblem, tally,
  type Approval, type DecideBody, type DecisionWord, type SignBody,
} from "../lib/approvals";

/** The three marks, each as the word on its radio, the verb in an error, and the word in the button ("Mark 3 as approved"):
 * a mark is a decision on an item, recorded in jason's own plan record. It writes nothing outside jason. */
const VERBS: Record<DecisionWord, [string, string, string]> = {
  approved: ["Approved", "mark as approved", "approved"],
  rejected: ["Rejected", "mark as rejected", "rejected"],
  held: ["Held for the board", "mark as held", "held"],
};

/** Mark the selected changes, then sign. Two parts:
 * 1. Mark the selected approvable items approved, rejected, or held ("Mark 5 as approved"). Rejected and held need a reason; held, for-a-person, and
 *    informational items are never in `selected` (they have no checkbox, and any passed are refused). A flagged item
 *    (held for the board by jason's policy finding) is never approved here: it is decided on its own (`FlaggedItem`),
 *    and this bar only counts it.
 * 2. Sign: the tally, the cost (`cost`), the person's full name (pre-filled with `me`; never "jason"), and the button that
 *    says what it does: "Sign this plan as Jane Example", with the line that signing makes no change. With changes
 *    undecided it stays unavailable and says how many are left.
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
  const flagged = approval.items.filter((i) => i.class === "held_for_board").length;
  const person = approval.items.filter((i) => i.class === "for_a_person" || i.class === "confirm_with_owner").length;

  const problem = nameProblem || decisionProblem(approval, ids, decision, reason);
  const [, verb, word] = VERBS[decision];
  const decideLabel = `Mark ${ids.length ? `${ids.length} ` : ""}as ${word}`;
  const refuse = () => {
    setDecideError(problem);
    if (problem && nameProblem) nameRef.current?.focus();
    else if (problem && decision !== "approved" && !reason.trim()) reasonRef.current?.focus();
  };

  const signLabel = `Sign this plan${by ? ` as ${by}` : ""}`;
  const signWhy = !open ? "" : t.undecided > 0 ? `Decide ${t.undecided} more ${t.undecided === 1 ? "change" : "changes"} to submit.` : nameProblem;
  const decideReasonError = decideError && decision !== "approved" && !reason.trim();

  return (
    <form className={`approve-bar${blocked || !decidable(approval) ? " approve-blocked" : ""}`} aria-label="Decide and sign" onSubmit={(e) => e.preventDefault()}>
      {blocked && <p className="notice notice-warn">The plan changed since review: nothing can be decided or signed on it. Re-plan first.</p>}
      <fieldset className="approve-decide" disabled={!open}>
        <legend>Mark the selected changes</legend>
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
              <>
                <p>Mark {plural(ids.length, "change", "changes")} as {word}, as {by}{decision !== "approved" ? `, because: "${reason.trim()}"` : ""}. Recorded with your name, the time, and fingerprint <code>{short(fingerprint)}</code>.</p>
                <p><strong>Nothing is written.</strong> You still need to sign the plan.</p>
              </>
            }>{decideLabel}</Confirm>
          ) : (
            <button type="button" className="primary" aria-disabled="true" disabled={!open || busy} aria-describedby={`${uid}-decide-error`} onClick={refuse}>{decideLabel}</button>
          )}
        </div>
        <p id={`${uid}-decide-error`} className="approve-error" role="alert">{decideError ? `Cannot ${verb}: ${decideError}` : ""}</p>
      </fieldset>

      <div className="approve-sign">
        <p className="approve-tally">
          <strong>{t.approved} of {t.approvable}</strong> marked approved · {t.rejected} rejected{t.held ? ` · ${t.held} held by a person` : ""} · {t.undecided} undecided{t.exceptions ? ` · ${plural(t.exceptions, "flagged change", "flagged changes")} approved as ${t.exceptions === 1 ? "an exception" : "exceptions"}` : ""}
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
                Sign this plan as {by}: {t.approved} marked approved{t.exceptions ? ` and ${plural(t.exceptions, "exception", "exceptions")}` : ""}, {t.rejected} rejected{t.held ? `, ${t.held} held for the board` : ""}, on fingerprint <code>{short(fingerprint)}</code>.
                {t.approved + t.exceptions === 0 ? " Nothing is approved, so the plan is withdrawn." : " Signing writes nothing outside jason. jason re-plans before anything is applied; if the plan changed, nothing is applied."}
              </p>
            }>{signLabel}</Confirm>
          ) : (
            <button type="button" className="primary" aria-disabled="true" disabled={!open || busy} aria-describedby={`${uid}-sign-why`} onClick={() => setSignError(signWhy)}>{signLabel}</button>
          )}
          <span id={`${uid}-sign-why`} className="muted" role="status">{signWhy || signError}</span>
        </div>
        <p className="muted approve-sign-note">Signing does not make the changes. It says these decisions are yours. A second person may still need to sign, and someone must apply.</p>
      </div>
      <p className="muted approve-note">
        {flagged + person > 0 && <>{flagged ? `${flagged} flagged for review` : ""}{flagged && person ? " and " : ""}{person ? `${person} for a person` : ""} {flagged + person === 1 ? "is" : "are"} not part of this approval{flagged ? "; a flagged change is decided on its own, in its section" : ""}. </>}
        Your name, the time, and the plan's fingerprint <code>{short(fingerprint)}</code> are recorded. jason plans; only a named person decides and signs.
      </p>
    </form>
  );
}
