import { Pill } from "./Pill";
import { changeText, personName, plural, results, when, type Approval, type PlanItem } from "../lib/approvals";

function List({ title, items, open = false, why }: { title: string; items: PlanItem[]; open?: boolean; why?: (i: PlanItem) => string }) {
  if (!items.length) return null;
  return (
    <details className="apply-section" open={open}>
      <summary>{title} ({items.length})</summary>
      <ul>
        {items.map((i) => (
          <li key={i.id}>
            {i.label}: <strong>{changeText(i)}</strong>
            {(why ? why(i) : i.resultDetail) && <span className="muted"> · {why ? why(i) : i.resultDetail}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

const UNCERTAIN = "The request went out and no answer came back. The next plan's live read shows whether it was written; do not apply again until then.";

/** What an apply did, from the approval's own items and `result`: applied, failed, uncertain, changed since review,
 * blocked, and not applied (rejected, held, never approvable), each a disclosure, failures open. A refused apply (a
 * re-plan found a change) says nothing was written and names the new plan. `role="status"`; while applying, the count
 * updates live. Renders nothing before an apply. */
export function ApplyResult({ approval, onOpen }: { approval: Approval; onOpen?: (id: string) => void }) {
  const r = results(approval);
  const res = approval.result ?? {};
  const refused = typeof res.refused === "string" ? res.refused : "";
  const by = typeof res.by === "string" ? res.by : "";
  const at = typeof res.at === "string" ? res.at : "";
  if (approval.status === "superseded" && refused)
    return (
      <section className="apply-result apply-refused" role="status" aria-label="Apply result">
        <div className="row wrap"><h3>Nothing written: {refused}</h3><Pill word="superseded" /></div>
        <List title="Changed since review" items={r.changed} open />
        {approval.supersededBy && (onOpen
          ? <button onClick={() => onOpen(approval.supersededBy!)}>Open the new plan, {approval.supersededBy}</button>
          : <p>Review the new plan: <code className="chip">{approval.supersededBy}</code>.</p>)}
      </section>
    );
  if (!["applying", "applied", "failed"].includes(approval.status)) return null;
  const done = r.applied.length;
  const total = r.approved.length;
  const failed = r.failed.length + r.uncertain.length;
  return (
    <section className={`apply-result${failed ? " apply-failures" : ""}`} role="status" aria-live="polite" aria-label="Apply result">
      <div className="row wrap">
        <h3>{approval.status === "applying" ? `Applying: ${done} of ${plural(total, "approved change", "approved changes")} written` : `Applied ${done} of ${plural(total, "approved change", "approved changes")}`}</h3>
        <Pill word={approval.status} />
        {(by || at) && <span className="muted">{by ? `by ${personName(by)}` : ""}{by && at ? ", " : ""}{when(at)}</span>}
      </div>
      <dl className="apply-tally">
        {([["Applied", done], ["Failed", r.failed.length], ["Uncertain", r.uncertain.length], ["Changed", r.changed.length], ["Blocked", r.blocked.length], ["Not applied", r.notApplied.length]] as const)
          .map(([k, v]) => <div key={k} className={v && (k === "Failed" || k === "Uncertain") ? "apply-bad" : undefined}><dt>{k}</dt><dd className="num">{v}</dd></div>)}
      </dl>
      <List title="Failed" items={r.failed} open />
      <List title="Uncertain" items={r.uncertain} open why={(i) => `${i.resultDetail ? `${i.resultDetail}. ` : ""}${UNCERTAIN}`} />
      <List title="Blocked" items={r.blocked} open />
      <List title="Not applied" items={r.notApplied} />
      <List title="Applied" items={r.applied} />
    </section>
  );
}
