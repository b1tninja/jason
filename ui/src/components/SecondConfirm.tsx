import { useId, useRef, useState } from "react";
import { Confirm } from "./Confirm";
import { cleanName, needsSecond, personName, sameName, short, signerProblem, when, type Approval, type SignBody } from "../lib/approvals";

/** The second, distinct person signs the same fingerprint, or declines and sends it back to review with a reason. The
 * first signer and the person who asked for the plan are refused, compared case-blind with spacing ignored (the server
 * refuses them too). The name field starts empty. Shown for a signed plan that needs a second person (`twoPerson`, the
 * kind's rule, or a high-stakes approved item); once confirmed it shows both people. */
export function SecondConfirm({ approval, twoPerson = false, me = "", onConfirm, onDecline, busy }: {
  approval: Approval; twoPerson?: boolean; me?: string;
  onConfirm?: (body: SignBody) => void; onDecline?: (body: SignBody & { reason: string }) => void; busy?: boolean;
}) {
  const uid = useId();
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [reasonError, setReasonError] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);
  const reasonRef = useRef<HTMLInputElement>(null);
  const signed = approval.status === "approved" || approval.status === "partially_approved";
  if (!needsSecond(approval, twoPerson) || (!signed && !approval.second)) return null;

  const first = approval.first;
  const refused = [first?.name, approval.requestedBy];
  const by = cleanName(name);
  const problem = signerProblem(by, refused);
  // The engine's decline refuses only the first signer: the person who asked may send it back.
  const declineProblem = signerProblem(by, [first?.name]);
  const fingerprint = approval.fingerprint;
  const iSigned = refused.some((r) => sameName(r, me));

  const Facts = (
    <dl className="kv second-facts">
      <dt>Plan</dt><dd>{approval.title} · fingerprint <code>{short(fingerprint)}</code></dd>
      <dt>Asked for by</dt><dd>{personName(approval.requestedBy)}</dd>
      <dt>Signed first by</dt><dd>{first ? <>{personName(first.name)}, {when(first.at)}</> : "not yet signed"}</dd>
      {approval.second && <><dt>Confirmed by</dt><dd>{personName(approval.second.name)}, {when(approval.second.at)}</dd></>}
    </dl>
  );

  if (approval.second)
    return (
      <section className="second-confirm second-done" aria-labelledby={`${uid}-title`}>
        <h3 id={`${uid}-title`}>Signed by two people</h3>
        {Facts}
      </section>
    );

  return (
    <section className="second-confirm" aria-labelledby={`${uid}-title`}>
      <h3 id={`${uid}-title`}>A second person confirms</h3>
      <p><strong>The rule:</strong> this plan is applied only after two different people sign the same fingerprint. The person who signed first, and the person who asked for it, cannot be the second.</p>
      {Facts}
      {iSigned && <p className="notice">Waiting on a second person. You signed or asked for this plan, so you cannot confirm it.</p>}
      <div className="fields">
        <label>
          Your full name
          <input ref={nameRef} value={name} autoComplete="name" required aria-invalid={error ? true : undefined}
            aria-describedby={`${uid}-hint ${uid}-error`} onChange={(e) => { setName(e.target.value); setError(""); }} />
          <span id={`${uid}-hint`} className="muted">Someone other than {[first?.name, approval.requestedBy].filter(Boolean).filter((n, i, a) => a.findIndex((m) => sameName(m, n)) === i).join(" or ")}.</span>
        </label>
        <label>
          Reason, to decline
          <input ref={reasonRef} value={reason} aria-invalid={reasonError ? true : undefined} aria-describedby={`${uid}-reason-error`}
            onChange={(e) => { setReason(e.target.value); setReasonError(""); }} />
        </label>
      </div>
      <p id={`${uid}-error`} className="approve-error" role="alert">{error}</p>
      <p id={`${uid}-reason-error`} className="approve-error" role="alert">{reasonError}</p>
      <div className="row wrap">
        {problem ? (
          <button type="button" className="primary" disabled={busy} onClick={() => { setError(problem); nameRef.current?.focus(); }}>Confirm with your name</button>
        ) : (
          <Confirm busy={busy} onConfirm={() => onConfirm?.({ by, fingerprint, via: "console" })}
            summary={<p>Sign as {by}, the second person, on fingerprint <code>{short(fingerprint)}</code>. Apply may then proceed; jason re-plans first.</p>}>
            Confirm as {by}
          </Confirm>
        )}
        {declineProblem || !reason.trim() ? (
          <button type="button" disabled={busy} onClick={() => {
            if (declineProblem) { setError(declineProblem); nameRef.current?.focus(); return; }
            setReasonError("Give a reason of a few words for declining."); reasonRef.current?.focus();
          }}>Decline and send back</button>
        ) : (
          <Confirm busy={busy} onConfirm={() => onDecline?.({ by, fingerprint, via: "console", reason: reason.trim() })}
            summary={<p>Decline as {by}: "{reason.trim()}". The plan goes back to review with its decisions kept; the first signature is cleared.</p>}>
            Decline and send back
          </Confirm>
        )}
      </div>
    </section>
  );
}
