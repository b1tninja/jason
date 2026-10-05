import { useEffect, useId, useState, type KeyboardEvent } from "react";
import { ApplyResult } from "./ApplyResult";
import { Confirm } from "./Confirm";
import { ApproveBar } from "./ApproveBar";
import { AuditLog } from "./AuditLog";
import { Caveats } from "./Caveats";
import { ChangedBanner } from "./ChangedBanner";
import { Command } from "./Command";
import { CostLine } from "./CostLine";
import { DueDate } from "./DueDate";
import { Evidence, EvidenceVersion, RefreshAllEvidence } from "./Evidence";
import { HeldNote } from "./HeldNote";
import { Pill } from "./Pill";
import { Recitation, type Citation } from "./Recitation";
import { SecondConfirm } from "./SecondConfirm";
import { WriteRow } from "./WriteRow";
import {
  cleanName, commands, decidable, groupItems, isApprovable, needsSecond, personName, plural, SECTIONS, short, signerProblem, staleness,
  STATUS_MEANING, when, type Approval, type AuditEntry, type ChainCheck, type DecideBody, type KindFacts, type PlanItem, type Recheck,
  type SignBody,
} from "../lib/approvals";

type Act<B> = (body: B) => void | Promise<void>;

/** Withdraw an open plan, with a reason, as a named person, behind `Confirm`. */
function Withdraw({ me, busy, onWithdraw }: { me: string; busy?: boolean; onWithdraw: (b: { by: string; reason: string }) => void }) {
  const [reason, setReason] = useState("");
  const [shown, setShown] = useState(false);
  const by = cleanName(me);
  const problem = signerProblem(by) || (!reason.trim() ? "Give a reason of a few words for withdrawing it." : "");
  return (
    <details className="plan-withdraw">
      <summary>Withdraw this plan</summary>
      <div className="stack-sm">
        <label className="approve-field">Reason, to withdraw<input value={reason} onChange={(e) => { setReason(e.target.value); setShown(false); }} aria-invalid={shown && !!problem ? true : undefined} /></label>
        {problem ? (
          <div className="row wrap">
            <button type="button" disabled={busy} onClick={() => setShown(true)}>Withdraw</button>
            <span className="approve-error" role="alert">{shown ? problem : ""}</span>
          </div>
        ) : (
          <Confirm busy={busy} onConfirm={() => onWithdraw({ by, reason: reason.trim() })} summary={<p>Withdraw the plan as {by}: "{reason.trim()}". Nothing in it is applied; a new plan is made when the work is wanted again.</p>}>Withdraw</Confirm>
        )}
      </div>
    </details>
  );
}

export const PLAN_CAVEATS = [
  "jason plans; it never approves its own plan. Every decision and signature names a person.",
  "Held for the board, for a person, confirm with the owner, and what follows are never approvable.",
  "Apply reads the live state again and refuses when anything an approved change relies on moved; then nothing is written.",
];

/** One approval from the approvals engine (`jason approvals show ID --json`, or `/api/approvals/<id>`), as a person reviews
 * it: the header (who asked, when it was read, the fingerprint, the clock), a changed-since-review banner, the two kinds
 * of held note side by side, the items in exactly one section by their class and grouped by owner (only approvable items
 * have checkboxes; arrow keys move between them), the cost, then by status: the approve bar, the second person, the
 * apply command, or the result; and the audit history. Every write goes through `Confirm` as a named person (`me`) and
 * carries the plan's fingerprint. */
export function PlanReview({
  approval, me = "", audit, chain, recheck, now, maxAgeHours = 24, twoPerson = false, recitations, boardHref, kind,
  onDecide, onSubmit, onConfirmSecond, onDecline, onReplan, onOpen, busy, error, caveats = PLAN_CAVEATS,
  onCheck, onApply, applyBlocked, onWithdraw,
}: {
  approval: Approval; me?: string; audit?: readonly AuditEntry[]; chain?: ChainCheck | null; recheck?: Recheck | null;
  now?: string; maxAgeHours?: number; twoPerson?: boolean; recitations?: Readonly<Record<string, Citation>>;
  boardHref?: (id: string) => string;
  /** The kind's declared facts as the server sends them (`kindFacts`): shown in the header, never worked out here. */
  kind?: KindFacts;
  onDecide?: Act<DecideBody>; onSubmit?: Act<SignBody>; onConfirmSecond?: Act<SignBody>; onDecline?: Act<SignBody & { reason: string }>;
  onReplan?: Act<{ by: string }>; onOpen?: (id: string) => void; busy?: boolean; error?: string; caveats?: readonly string[];
  /** Re-plan live and compare, writing nothing (the result comes back as `recheck`). */
  onCheck?: Act<void>;
  /** Apply the approved items, as `me`, confirming the full fingerprint. Without it, or with `applyBlocked` (why the
   * server will not apply), the step is the terminal command. */
  onApply?: Act<{ by: string; confirm: string }>; applyBlocked?: string;
  onWithdraw?: Act<{ by: string; reason: string }>;
}) {
  const uid = useId();
  const a = approval;
  const [selected, setSelected] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [evidenceVersion, setEvidenceVersion] = useState(0);
  useEffect(() => { setSelected([]); setStatus(""); }, [a.id, a.fingerprint]);

  const stale = staleness(a, { recheck, now, maxAgeHours });
  const editable = decidable(a) && !stale.blocked;
  const selectable = a.items.filter((i) => isApprovable(i));
  const toggle = (id: string, on: boolean) => setSelected((s) => (on ? [...new Set([...s, id])] : s.filter((x) => x !== id)));
  const toggleMany = (ids: string[], on: boolean) => setSelected((s) => (on ? [...new Set([...s, ...ids])] : s.filter((x) => !ids.includes(x))));
  const run = async <B,>(fn: Act<B> | undefined, body: B, done: string) => {
    if (!fn) return;
    try { await fn(body); setSelected([]); setStatus(done); } catch { /* the caller shows `error` */ }
  };

  const onKeys = (e: KeyboardEvent<HTMLDivElement>) => {
    const t = e.target as HTMLElement;
    if (!t.matches("input[data-plan-check]") || !["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    const boxes = [...e.currentTarget.querySelectorAll<HTMLInputElement>("input[data-plan-check]:not(:disabled)")];
    const at = boxes.indexOf(t as HTMLInputElement);
    const next = e.key === "Home" ? 0 : e.key === "End" ? boxes.length - 1 : Math.min(boxes.length - 1, Math.max(0, at + (e.key === "ArrowDown" ? 1 : -1)));
    e.preventDefault();
    boxes[next]?.focus();
  };

  const approvedCount = a.items.filter((i) => isApprovable(i) && i.decision === "approved").length;
  const signed = a.status === "approved" || a.status === "partially_approved";
  const second = needsSecond(a, twoPerson);
  // A plan older than its kind allows is refused at apply ("plan again"), so it is never offered as ready: the banner
  // says so and offers the re-plan.
  const ready = signed && (!second || !!a.second) && !stale.blocked && !stale.tooOld;
  const today = now ? new Date(now) : undefined;
  const by = (i: PlanItem) => a.items.filter((x) => (i.dependsOn ?? []).includes(x.id));
  const rule = (i: PlanItem) => {
    const c = i.rule ? recitations?.[i.rule] : undefined;
    return c ? (
      <details className="write-rule">
        <summary>Rule: {i.rule}</summary>
        <Recitation citation={c} />
      </details>
    ) : undefined;
  };

  const refs = [...(a.evidence ?? []), ...a.items.flatMap((i) => i.evidence ?? [])];

  return (
    <EvidenceVersion.Provider value={evidenceVersion}>
    <article className="plan-review" aria-labelledby={`${uid}-title`}>
      <header className="plan-head">
        <div className="row wrap">
          <h2 id={`${uid}-title`}>{a.title}</h2>
          <Pill word={a.status} meaning={STATUS_MEANING[a.status]} />
        </div>
        <p className="muted">
          Planned by jason, asked by {personName(a.requestedBy)}{a.requestedVia ? ` (${a.requestedVia})` : ""} · read live {when(a.readAt)} · fingerprint <code>{short(a.fingerprint)}</code>
          {a.first && <> · signed by {personName(a.first.name)}, {when(a.first.at)}</>}
          {a.second && <> · confirmed by {personName(a.second.name)}</>}
        </p>
        {kind && (
          <p className="plan-kind">
            {kind.title}: risk {kind.riskWords} ({kind.risk}) · {kind.approver} approves · undone: {kind.reversible || "not stated"} ·
            planned again after {plural(kind.maxAgeHours, "hour", "hours")}
            {kind.cost ? <> · cost: {kind.cost}</> : null}
          </p>
        )}
        {a.clock?.due && <p>Clock: {a.clock.what} <DueDate iso={a.clock.due} today={today} /></p>}
        <Evidence items={a.evidence} label="Read from" approval={a.id} level={3} />
        <RefreshAllEvidence approval={a.id} refs={refs} by={me.trim() ? me : undefined} onDone={() => setEvidenceVersion((v) => v + 1)} />
        {a.supersedes && <p className="muted">Supersedes <code className="chip">{a.supersedes}</code>; earlier decisions are hints, not counted.</p>}
      </header>

      <p className="visually-hidden" role="status" aria-live="polite">
        {status}{stale.blocked ? " Approval is blocked: the plan changed since review." : ""}
      </p>
      {error && <p className="notice notice-error" role="alert">{error}</p>}

      <ChangedBanner approval={a} recheck={recheck} now={now} maxAgeHours={maxAgeHours} me={me} onOpen={onOpen} busy={busy}
        onReplan={onReplan ? (b) => run(onReplan, b, `Re-plan asked for as ${b.by}.`) : undefined} />

      <div className="held-notes">
        <HeldNote items={a.items} boardHref={boardHref} />
      </div>

      {SECTIONS.map(({ cls, title, note }) => {
        const rows = a.items.filter((i) => i.class === cls);
        if (!rows.length) return null;
        const sid = `${uid}-${cls}`;
        const live = cls === "approvable" && editable;
        const chosen = rows.filter((i) => selected.includes(i.id)).length;
        return (
          <section key={cls} className={`plan-section plan-${cls.replace(/_/g, "-")}`} aria-labelledby={sid}>
            <div className="plan-section-head">
              <h3 id={sid}>{title} ({rows.length})</h3>
              {note && <span className="muted">{note}</span>}
              {live && (
                <label className="plan-all">
                  <input type="checkbox" checked={chosen === selectable.length && chosen > 0}
                    ref={(el) => { if (el) el.indeterminate = chosen > 0 && chosen < selectable.length; }}
                    onChange={(e) => toggleMany(selectable.map((i) => i.id), e.target.checked)} />
                  Select all {selectable.length} approvable
                </label>
              )}
            </div>
            <div className="plan-groups" onKeyDown={live ? onKeys : undefined}>
              {groupItems(rows).map(({ group, items }, n) => {
                const gid = `${sid}-g${n}`;
                const mine = items.filter(isApprovable).map((i) => i.id);
                const on = mine.filter((id) => selected.includes(id)).length;
                return (
                  <div key={group} className="plan-group" role="group" aria-labelledby={gid}>
                    <div className="plan-group-head">
                      <h4 id={gid}>{group}</h4>
                      <span className="muted">{plural(items.length, "item", "items")}</span>
                      {live && mine.length > 1 && (
                        <label className="plan-all">
                          <input type="checkbox" checked={on === mine.length} ref={(el) => { if (el) el.indeterminate = on > 0 && on < mine.length; }}
                            onChange={(e) => toggleMany(mine, e.target.checked)} aria-label={`Select all ${mine.length} of ${group}`} />
                          all {mine.length}
                        </label>
                      )}
                    </div>
                    {items.map((i) => (
                      <WriteRow key={i.id} item={i} selectable={live} checked={selected.includes(i.id)} onToggle={toggle}
                        waits={by(i)} rule={rule(i)} labelledBy={gid} approval={a.id} />
                    ))}
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      <CostLine costCents={a.costCents} summary={a.summary} items={a.items} />

      {decidable(a) && (
        <ApproveBar approval={a} selected={selected} me={me} blocked={stale.blocked} busy={busy}
          onDecide={onDecide ? (b) => run(onDecide, b, `Recorded: ${b.decision.replace("held", "held for the board")} ${plural(b.items.length, "change", "changes")} as ${b.by}.`) : undefined}
          onSubmit={onSubmit ? (b) => run(onSubmit, b, `Signed as ${b.by}.`) : undefined} />
      )}
      {signed && second && (
        <SecondConfirm approval={a} twoPerson={twoPerson} me={me} busy={busy}
          onConfirm={onConfirmSecond ? (b) => run(onConfirmSecond, b, `Confirmed as ${b.by}.`) : undefined}
          onDecline={onDecline ? (b) => run(onDecline, b, `Declined as ${b.by}; back to review.`) : undefined} />
      )}
      {ready && (
        <div className="stack-sm plan-apply">
          <p>{plural(approvedCount, "approved change is", "approved changes are")} ready to apply.</p>
          {onApply && !applyBlocked ? (
            signerProblem(me) ? <p className="muted">{signerProblem(me)} Pick whose name goes on the record to apply.</p> : (
              <Confirm busy={busy} onConfirm={() => run(onApply, { by: cleanName(me), confirm: a.fingerprint }, `Apply asked for as ${cleanName(me)}.`)} summary={
                <p>Apply {plural(approvedCount, "approved change", "approved changes")} as {cleanName(me)}, on fingerprint <code>{short(a.fingerprint)}</code>. jason reads the live state again first: if anything an approved change relies on moved, nothing is written and a new plan is made to review.</p>
              }>Apply {plural(approvedCount, "change", "changes")} now</Confirm>
            )
          ) : (
            <>
              {applyBlocked && <p className="muted">Apply is not available here: {applyBlocked}</p>}
              <Command cmd={commands.apply(a.id, me)} note="Apply from a terminal. jason reads live again first and writes nothing if anything changed." />
            </>
          )}
        </div>
      )}
      {onCheck && ["planned", "in_review", "approved", "partially_approved"].includes(a.status) && (
        <div className="row wrap">
          <button type="button" onClick={() => run(onCheck, undefined, "Checked against the live state.")} disabled={busy}>Check against the live state</button>
          <span className="muted">Reads live and compares, writing nothing (<code>{commands.check(a.id)}</code>).</span>
        </div>
      )}
      {onWithdraw && ["planned", "in_review", "approved", "partially_approved"].includes(a.status) && <Withdraw me={me} busy={busy} onWithdraw={(b) => run(onWithdraw, b, `Withdrawn by ${b.by}.`)} />}
      <ApplyResult approval={a} onOpen={onOpen} />
      {a.status === "withdrawn" && <p className="notice">Withdrawn. {(a.notes ?? []).join(" ")}</p>}
      {a.status !== "withdrawn" && (a.notes ?? []).length > 0 && <ul className="muted">{(a.notes ?? []).map((n) => <li key={n}>{n}</li>)}</ul>}

      {audit && audit.length > 0 && (
        <details className="plan-history">
          <summary>History</summary>
          <AuditLog entries={audit} approval={a.id} compact chain={chain} />
        </details>
      )}
      <Command cmd={commands.show(a.id)} note="The same plan in a terminal." />
      <Caveats items={caveats} />
    </article>
    </EvidenceVersion.Provider>
  );
}
