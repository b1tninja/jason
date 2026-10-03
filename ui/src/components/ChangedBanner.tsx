import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { cleanName, commands, isJason, short, staleness, when, type Approval, type Recheck } from "../lib/approvals";

/** The plan in hand is stale: superseded, changed since review (a re-plan differs: `recheck`, or the apply marked items
 * changed), or read longer ago than the kind allows. A change blocks approval: decisions on the old plan are not
 * applied, and the banner offers a re-plan (`onReplan`, behind `Confirm`, as `me`) beside the terminal command. A plan
 * that is only old keeps its decisions; apply re-plans first. Renders nothing for a fresh plan. */
export function ChangedBanner({ approval, recheck, now, maxAgeHours = 24, me = "", onReplan, onOpen, busy }: {
  approval: Approval; recheck?: Recheck | null; now?: string; maxAgeHours?: number; me?: string;
  onReplan?: (body: { by: string }) => void; onOpen?: (id: string) => void; busy?: boolean;
}) {
  const s = staleness(approval, { recheck, now, maxAgeHours });
  if (!s.blocked && !s.tooOld) return null;
  const by = cleanName(me);
  const replan = (
    <div className="stack-sm">
      {onReplan && (
        by && !isJason(by) ? (
          <Confirm busy={busy} onConfirm={() => onReplan({ by })} summary={<>Re-plan as {by}: jason reads the live state again and makes a new plan to review. This one is superseded; its decisions show on the new plan as hints, not counted.</>}>
            Re-plan and review again
          </Confirm>
        ) : <p className="muted">Pick whose name goes on the record to re-plan.</p>
      )}
      <Command cmd={commands.plan(approval.kind, by)} note="Or plan again from a terminal. The page never runs a command." />
    </div>
  );
  if (s.superseded)
    return (
      <section className="changed-banner" aria-labelledby={`changed-${approval.id}`}>
        <h3 id={`changed-${approval.id}`}>This plan was superseded</h3>
        <p>
          {approval.supersededBy ? <>A newer plan, <code className="chip">{approval.supersededBy}</code>, replaced it</> : "A newer plan replaced it"}
          {s.changed.length ? ": the live state changed since review. Nothing was written." : "."} It is read-only.
        </p>
        <Changes items={s.changed} />
        {approval.supersededBy && onOpen && <button onClick={() => onOpen(approval.supersededBy!)}>Open the new plan</button>}
      </section>
    );
  if (s.blocked)
    return (
      <section className="changed-banner" aria-labelledby={`changed-${approval.id}`}>
        <h3 id={`changed-${approval.id}`}>The plan changed since it was reviewed</h3>
        <p>Decisions given on the reviewed plan are not applied, and nothing more can be decided or signed on it. Re-plan, then review the changed writes again.</p>
        <dl className="changed-prints">
          <dt>Reviewed</dt><dd><code>{short(recheck?.then || approval.fingerprint)}</code> read {when(approval.readAt)}</dd>
          {recheck?.now && <><dt>Now</dt><dd><code>{short(recheck.now)}</code> read live just now</dd></>}
        </dl>
        <Changes items={s.changed} />
        {replan}
      </section>
    );
  return (
    <section className="changed-banner changed-old" aria-labelledby={`changed-${approval.id}`}>
      <h3 id={`changed-${approval.id}`}>This plan was read {Math.round(s.ageHours ?? 0)} hours ago</h3>
      <p>That is longer than the {maxAgeHours} hours this kind allows before apply. Decisions stand; apply reads live again first, or re-plan now.</p>
      {replan}
    </section>
  );
}

function Changes({ items }: { items: { id: string; op: string; label: string; why: string }[] }) {
  if (!items.length) return null;
  return (
    <ul className="changed-list">
      {items.map((c) => <li key={c.id}><strong>{c.label}</strong>, {c.op}: {c.why}</li>)}
    </ul>
  );
}
