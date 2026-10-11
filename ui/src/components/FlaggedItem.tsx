import { useId, useState, type ReactNode } from "react";
import { Confirm } from "./Confirm";
import { Evidence } from "./Evidence";
import { Pill } from "./Pill";
import {
  cleanName, exceptionProblem, personName, short, signerProblem, when,
  type Approval, type DecideBody, type DecisionWord, type ExceptionRow, type PlanItem, type ReferBody,
} from "../lib/approvals";
import "../styles/flagged.css";

type Act<B> = (body: B) => void | Promise<void>;

const NONE = <span className="write-none">none</span>;

/** The nudge: a finding decided by exception often enough that the board may want to write a rule. The number is the
 * server's (`flagged.nudge`, the exceptions log's `EXCEPTION_NUDGE`); the text names the board item the finding waits on. */
export function ExceptionNudge({ count, boardItem, boardHref }: { count: number; boardItem?: string; boardHref?: (id: string) => string }) {
  return (
    <p className="notice notice-warn flagged-nudge" role="note">
      This finding has been decided by exception {count} {count === 1 ? "time" : "times"}. The board may want to write a rule
      {boardItem ? <> (board item {boardHref ? <a href={boardHref(boardItem)}>{boardItem}</a> : <code className="chip">{boardItem}</code>})</> : null}.
    </p>
  );
}

/** Who decided what under the finding, oldest first: the person, when, the decision, the reason, who signed second, and
 * whether the write was made. A decision the log holds for another plan says which. */
function History({ rows, approval }: { rows: readonly ExceptionRow[]; approval: string }) {
  if (!rows.length) return <p className="muted">No exception has been decided under this finding yet.</p>;
  const how = (r: ExceptionRow) => (r.decision === "approved" ? "approved" : r.decision === "rejected" ? "rejected" : "kept flagged");
  return (
    <ul className="flagged-history">
      {rows.map((r) => (
        <li key={`${r.approval}-${r.item}-${r.at}`}>
          <strong>{personName(r.by)}</strong> {how(r)} · {when(r.at)}
          {r.reason ? <>: <q>{r.reason}</q></> : null}
          {r.decision === "approved" && (
            <span className="muted">
              {" "}· {r.secondBy ? `second: ${personName(r.secondBy)}` : "no second signature yet"} · {r.applied ? "applied" : "not applied"}
            </span>
          )}
          {r.approval !== approval && <span className="muted"> · plan <code className="chip">{r.approval}</code></span>}
        </li>
      ))}
    </ul>
  );
}

/** One flagged item (held for the board by jason's policy finding), expandable to what a reviewer needs to decide it: the
 * change (target, from, to), why it is flagged (the finding and the rule row), the evidence, the board item, and the
 * exceptions already made under this finding. A director, an officer, or the manager may then, each in a `Confirm`:
 * - mark it approved as a one-off exception (a reason in words; "One-off decision, not a rule. A second person must sign."),
 * - mark it rejected (a reason),
 * - keep it flagged (a note, for the next reviewer), or
 * - refer it to the board (the board item is made or refreshed; nothing is decided).
 * The actions show only while the plan is open to decisions (`editable`); an item decided shows what was decided. A
 * decision posts the engine's `decide` with `exception: true`; a referral posts `refer`. jason never decides. */
export function FlaggedItem({
  item, approval, me = "", editable = false, busy, onDecide, onRefer, boardHref, nudge = 2, showNudge = true, rule,
}: {
  item: PlanItem; approval: Pick<Approval, "id" | "fingerprint">; me?: string; editable?: boolean; busy?: boolean;
  onDecide?: Act<DecideBody>; onRefer?: Act<ReferBody>; boardHref?: (id: string) => string; nudge?: number;
  /** Show the nudge line here; the plan shows it once for a finding that has several flagged items. */
  showNudge?: boolean;
  /** The rule recited (a `Recitation` in a disclosure, say), instead of the plain rule line. */
  rule?: ReactNode;
}) {
  const uid = useId();
  const [reason, setReason] = useState("");
  const [shown, setShown] = useState<DecisionWord | "refer" | "">("");
  const by = cleanName(me);
  const nameProblem = signerProblem(by);
  const c = item.change;
  const history = item.exceptions ?? [];
  const count = item.exceptionCount ?? 0;
  const decided = !!item.exception && item.decision !== "undecided";
  const states: Record<DecisionWord, string> = {
    approved: "approved as a one-off exception", rejected: "rejected", held: "kept flagged",
  };
  const body = (decision: DecisionWord): DecideBody => ({
    items: [item.id], decision, reason: reason.trim(), by, fingerprint: approval.fingerprint, via: "console", exception: true,
  });
  const done = () => { setReason(""); setShown(""); };

  const problem = (decision: DecisionWord) => nameProblem || exceptionProblem(decision, reason);
  const action = (decision: DecisionWord, label: string, summary: ReactNode) => {
    const why = problem(decision);
    return !why && editable ? (
      <Confirm busy={busy} label="Exception" onConfirm={() => { void onDecide?.(body(decision)); done(); }} summary={summary}>{label}</Confirm>
    ) : (
      <button type="button" className="primary" aria-disabled="true" disabled={!editable || busy} onClick={() => setShown(decision)}>{label}</button>
    );
  };
  const shownError = shown && shown !== "refer" ? problem(shown) : shown === "refer" ? nameProblem : "";

  return (
    <div className="flagged-item" data-flagged-item={item.id}>
      {showNudge && count >= nudge && <ExceptionNudge count={count} boardItem={item.boardItem} boardHref={boardHref} />}
      <details className="flagged-review">
        <summary>
          Review this flagged change
          {decided && <> · <Pill word={item.decision === "held" ? "flagged" : item.decision} /> <span className="muted">{states[item.decision as DecisionWord]} by {personName(item.decidedBy)}</span></>}
          {count > 0 && <span className="muted"> · {count} {count === 1 ? "exception" : "exceptions"} made under this finding</span>}
        </summary>

        <dl className="flagged-change" aria-label="The change">
          <dt>Target</dt><dd><code>{item.target}</code> {item.label}</dd>
          <dt>From</dt><dd>{c?.before ? <del>{c.before}</del> : NONE}</dd>
          <dt>To</dt><dd>{c?.after ? <ins>{c.after}</ins> : NONE}</dd>
        </dl>

        <div className="flagged-why">
          <h4>Why it is flagged</h4>
          <p>{item.why}</p>
          {rule ?? (item.rule ? <p className="muted">Finding and rule: <code>{item.rule}</code></p> : null)}
          <p className="muted">No rule the board has adopted answers this. The finding is jason's; a person decides, in their own name, as a one-off decision (not a rule).</p>
        </div>

        {(item.evidence ?? []).length > 0 && (
          <div className="flagged-evidence">
            <h4>Evidence</h4>
            <Evidence items={item.evidence} approval={approval.id} level={5} />
          </div>
        )}

        <p className="flagged-board">
          Board item:{" "}
          {item.boardItem
            ? (boardHref ? <a href={boardHref(item.boardItem)}>{item.boardItem}</a> : <code className="chip">{item.boardItem}</code>)
            : <span className="muted">none yet (refer it to the board to make one)</span>}
        </p>

        <div className="flagged-exceptions">
          <h4>Exceptions made under this finding</h4>
          <History rows={history} approval={approval.id} />
        </div>

        {decided && item.decision !== "undecided" && (
          <p className="flagged-decided">
            {personName(item.decidedBy)} {states[item.decision]}{item.decidedAt ? ` · ${when(item.decidedAt)}` : ""}{item.reason ? <>: <q>{item.reason}</q></> : null}.
            {item.decision === "approved" && " A second, distinct person signs before it applies."}
          </p>
        )}

        {editable ? (
          <fieldset className="flagged-actions" disabled={busy}>
            <legend>Decide this flagged change</legend>
            <label className="approve-field">
              Reason, in words (for the log)
              <input value={reason} onChange={(e) => { setReason(e.target.value); setShown(""); }} aria-invalid={shownError ? true : undefined}
                aria-describedby={`${uid}-error`} placeholder="Why, in a few words" />
            </label>
            <div className="row wrap">
              {action("approved", "Mark approved as a one-off exception", (
                <>
                  <p><strong>One-off decision, not a rule. A second person must sign.</strong></p>
                  <p>Mark this flagged change approved as {by}, because: "{reason.trim()}". It goes in the exceptions log with your name and the time; nothing is written outside jason until the plan is signed, a second, distinct person confirms, and it is applied.</p>
                </>
              ))}
              {action("rejected", "Mark as rejected", <p>Mark this flagged change rejected as {by}, because: "{reason.trim()}". Nothing is written. Logged with your name and the time.</p>)}
              {action("held", "Keep flagged", <p>Keep this change flagged as {by}, with the note: "{reason.trim()}". It stays flagged for the next reviewer; nothing is decided.</p>)}
              {onRefer && !nameProblem ? (
                <Confirm busy={busy} label="Refer" onConfirm={() => { void onRefer({ item: item.id, by, fingerprint: approval.fingerprint, via: "console" }); done(); }}
                  summary={<p>Refer this finding to the board as {by}: the board item is made or refreshed, proposed for the next agenda, with this plan's evidence. Nothing is decided and nothing is written.</p>}>Refer to the board</Confirm>
              ) : (
                <button type="button" className="primary" aria-disabled="true" disabled={!onRefer || busy} onClick={() => setShown("refer")}>Refer to the board</button>
              )}
            </div>
            <p id={`${uid}-error`} className="approve-error" role="alert">{shownError}</p>
          </fieldset>
        ) : (
          <p className="muted">Decisions on flagged changes open while the plan is planned or in review.</p>
        )}
        <p className="muted">Recorded with plan fingerprint <code>{short(approval.fingerprint)}</code>.</p>
      </details>
    </div>
  );
}
