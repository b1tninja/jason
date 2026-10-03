import type { ReactNode } from "react";
import { Evidence } from "./Evidence";
import { Pill } from "./Pill";
import { HeldNote } from "./HeldNote";
import { changeText, evidenceText, isApprovable, personName, RESULT_WORDS, when, type PlanItem } from "../lib/approvals";

const OP_WORDS = { add: ["+", "Add"], remove: ["−", "Remove"], set: ["~", "Change"] } as const;

function Op({ item }: { item: PlanItem }) {
  if (!item.change) {
    const [mark, words] = item.class === "for_a_person" ? ["✎", "A person does"] : ["→", "Then"];
    return <span className="write-op"><span aria-hidden="true">{mark}</span><span className="visually-hidden">{words}</span></span>;
  }
  const [mark, words] = OP_WORDS[item.change.op] ?? ["~", "Change"];
  return <span className={`write-op write-op-${item.change.op}`}><span aria-hidden="true">{mark}</span><span className="visually-hidden">{words}</span></span>;
}

function Diff({ item }: { item: PlanItem }) {
  const c = item.change;
  if (!c) return <span className="muted">{item.class === "for_a_person" ? "a person enters it" : "no field changes"}</span>;
  const none = <span className="write-none">none</span>;
  return (
    <span className="write-diff">
      {c.before ? <del>{c.before}</del> : none}
      <span aria-hidden="true"> → </span><span className="visually-hidden"> becomes </span>
      {c.after ? <ins>{c.after}</ins> : none}
    </span>
  );
}

/** The item's state in words: undecided, or decided by a named person (with the reason), and its result once applied. */
function State({ item }: { item: PlanItem }) {
  if (!isApprovable(item))
    return <Pill word={item.result !== "pending" ? RESULT_WORDS[item.result] : item.class === "held_for_board" ? "held" : item.class === "informational" ? "follows" : "never approvable"} />;
  return (
    <span className="write-state">
      <Pill word={item.decision} />
      {item.decision !== "undecided" && (
        <span className="muted">{item.decision === "held" ? "for the board " : ""}by {personName(item.decidedBy)}{item.decidedAt ? `, ${when(item.decidedAt)}` : ""}{item.reason ? `: ${item.reason}` : ""}</span>
      )}
      {item.result !== "pending" && <Pill word={RESULT_WORDS[item.result]} meaning={item.resultDetail} />}
    </span>
  );
}

/** One planned change, as the engine's plan item gives it: the change, before → after, why, the rule, the evidence, and its
 * state. Only an approvable item, while `selectable`, has a checkbox; held, for-a-person, confirm-with-owner, and
 * informational items never do, whatever is passed. `waits` names the changes a completion waits on. `rule` replaces the
 * plain rule line (a `Recitation` in a disclosure, say). */
export function WriteRow({ item, selectable = false, checked = false, onToggle, waits, rule, labelledBy }: {
  item: PlanItem; selectable?: boolean; checked?: boolean; onToggle?: (id: string, checked: boolean) => void;
  waits?: readonly PlanItem[]; rule?: ReactNode; labelledBy?: string;
}) {
  const canSelect = selectable && isApprovable(item);
  const changeId = `write-${item.id}`;
  const cls = ["write-row", `write-${item.class.replace(/_/g, "-")}`, isApprovable(item) ? `write-${item.decision}` : "", item.result === "changed" ? "write-changed" : ""].filter(Boolean).join(" ");
  return (
    <div className={cls} data-item-id={item.id} data-class={item.class} data-board-item={item.boardItem || undefined}>
      <div className="write-select">
        {canSelect && (
          <input type="checkbox" data-plan-check checked={checked} onChange={(e) => onToggle?.(item.id, e.target.checked)}
            aria-labelledby={[labelledBy, changeId].filter(Boolean).join(" ")} />
        )}
      </div>
      <div className="write-change" id={changeId}>
        <Op item={item} /> <span className="write-field">{item.change?.field ?? item.op}</span>{" "}
        <strong className="write-value">{item.change?.value || item.value}</strong>
        <span className="visually-hidden"> ({changeText(item)})</span>
        {item.highStakes && <span className="badge badge-warn write-stakes" title="A second, distinct person signs before it applies">second person</span>}
      </div>
      <div className="write-before-after"><Diff item={item} /></div>
      <div className="write-why">
        <p>{item.why}</p>
        {waits && waits.length > 0 && (
          <p className="muted write-waits"><span aria-hidden="true">↳ </span>Waits on {waits.length} {waits.length === 1 ? "change" : "changes"}: {waits.map((w) => w.change?.text || `${w.op} ${w.value}`).join("; ")}</p>
        )}
        {rule ?? (item.rule ? <p className="muted write-rule">Rule: {item.rule}</p> : null)}
        {item.class === "held_for_board" && <HeldNote items={[item]} inline />}
        <Evidence items={(item.evidence ?? []).map(evidenceText)} />
      </div>
      <div className="write-status"><State item={item} /></div>
    </div>
  );
}
