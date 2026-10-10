import { ApplyResult } from "./ApplyResult";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Pill } from "./Pill";
import type { Approval } from "../lib/approvals";
import {
  COPY_ORIGINAL_STAYS, FILING_ACTION_ORDER, FILING_MEANINGS, MOVE_KEEPS_LINK, NOTHING_DELETES, filingButtonLabel, groupByAction, plural, writeCount,
  type FilingAction, type FilingPlan as FilingPlanData,
} from "../lib/inspections";

const GLYPH = { file: "file-plus", copy: "copy", move: "arrow-right", "in drive": "circle-check", "filed before": "history", held: "circle-pause" } as const;

function Row({ row }: { row: FilingPlanData["rows"][number] }) {
  return (
    <li className="insp-plan-row" data-action={row.action}>
      <div className="row wrap">
        <Pill word={row.action} meaning={FILING_MEANINGS[row.action]} glyph={GLYPH[row.action]} />
        <strong>{row.name}</strong>
        <span className="muted">{row.kind}</span>
      </div>
      <div className="muted">To: {row.destination}</div>
      {row.action === "copy" && <div>{COPY_ORIGINAL_STAYS}{row.original && <> It stays at {row.original}.</>}</div>}
      {row.action === "move" && <div>{MOVE_KEEPS_LINK}</div>}
      {row.action === "held" && <div>Held for a person to verify first. jason does not write it.</div>}
      <details><summary>Why</summary><p>{row.why}</p></details>
    </li>
  );
}

/** The plan to file a vendor's reports in Drive. The whole plan is on screen first: the counts by action, and every row
 * with its action word, its destination folder, and a "Why" that recites the rule's condition. Only after the plan is the
 * one button that writes, and it names the numbers ("File 8, copy 5, move 2") behind `Confirm`, which spells the change
 * out. A copy says the original stays; a move says the file keeps its id, link, and sharing; nothing is deleted. A held
 * row has no control. With nothing to write it says everything is filed. Rows are grouped by action, the counts first
 * (a choice for the design to confirm: grouping keeps forty rows scannable).
 * `onConfirmFile` is the person's act; without it the plan shows its `Command`. `running` shows the filing under way;
 * `approval` (an applied approval) shows `ApplyResult`. */
export function FilingPlan({ plan, onConfirmFile, busy, running = false, approval }: {
  plan: FilingPlanData;
  onConfirmFile?: (plan: FilingPlanData) => void;
  busy?: boolean;
  running?: boolean;
  approval?: Approval;
}) {
  const writes = writeCount(plan);
  const label = filingButtonLabel(plan);
  const groups = groupByAction(plan.rows);
  return (
    <section className="insp-plan" aria-label={`Filing plan for ${plan.vendor}`}>
      <h3>Filing plan: {plan.vendor}</h3>
      <dl className="insp-counts" aria-label="Counts by action">
        {FILING_ACTION_ORDER.map((a: FilingAction) => (
          <div key={a} data-action={a}><dt title={FILING_MEANINGS[a]}>{a}</dt><dd className="num">{plan.counts[a] ?? 0}</dd></div>
        ))}
      </dl>
      {plan.rows.length === 0 || (writes === 0 && !plan.counts.held)
        ? <p role="status">Everything is filed. Nothing to do.</p>
        : null}
      {groups.map((g) => (
        <section key={g.action} className="insp-plan-group" aria-label={`${g.action}: ${plural(g.rows.length, "row")}`}>
          <h4>{g.action} ({g.rows.length})</h4>
          <ul>{g.rows.map((r) => <Row key={`${r.action}-${r.name}`} row={r} />)}</ul>
        </section>
      ))}
      <p className="muted">{NOTHING_DELETES}</p>
      {running && <p role="status" aria-live="polite">Filing: {label}. Each file is written once; nothing is deleted.</p>}
      {approval && <ApplyResult approval={approval} />}
      {writes > 0 && !running && (
        <div className="insp-plan-act">
          {onConfirmFile
            ? (
              <Confirm busy={busy} label="File"
                summary={<>
                  <p>{label}.</p>
                  <ul>
                    {plan.counts.file > 0 && <li>File {plural(plan.counts.file, "new report")} in Drive.</li>}
                    {plan.counts.copy > 0 && <li>Copy {plural(plan.counts.copy, "report")}. {COPY_ORIGINAL_STAYS}</li>}
                    {plan.counts.move > 0 && <li>Move {plural(plan.counts.move, "report")}. {MOVE_KEEPS_LINK}</li>}
                  </ul>
                  <p>{NOTHING_DELETES}</p>
                </>}
                onConfirm={() => onConfirmFile(plan)}>{label}</Confirm>
            )
            : <p className="muted">A person files this from a terminal.</p>}
          <Command cmd={plan.command} note="Does the same, with --yes. The page never runs a command." />
        </div>
      )}
    </section>
  );
}
