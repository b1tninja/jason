import { useState } from "react";
import { Badge } from "./Badge";
import { Confirm } from "./Confirm";
import { Pill } from "./Pill";
import { RollCall, tally } from "./RollCall";

export interface DecisionDraft { title: string; motion: string; item?: string; session?: string; mover: string; second: string; votes: Record<string, string>; outcome: string; by: string; notes: string }
export const OUTCOMES = ["approved", "denied", "tabled"];

/** One motion on one item: the text as made, mover and second, the roll call, and the outcome in the board's word.
 * Saving goes through a confirm that spells out the record. */
export function DecisionCard({ title, directors, initial, onSave, busy }: {
  title: string; directors: readonly string[]; initial?: Partial<DecisionDraft>; onSave: (d: DecisionDraft) => void | Promise<void>; busy?: boolean;
}) {
  const [d, setD] = useState<DecisionDraft>({ title, motion: "", mover: "", second: "", votes: {}, outcome: "", by: "", notes: "", ...initial });
  const t = tally(d.votes);
  const suggested = t.aye + t.no === 0 ? "" : t.aye > t.no ? "approved" : "denied";
  const ready = d.motion.trim().length > 0;
  return (
    <article className="item decision">
      <header className="row wrap"><strong>{title}</strong>{d.outcome ? <Pill word={d.outcome} /> : <Badge>vote open</Badge>}{d.session === "executive session" && <Badge tone="warn">executive</Badge>}</header>
      <div className="fields">
        <label className="wide">Motion, as made <textarea rows={2} value={d.motion} onChange={(e) => setD({ ...d, motion: e.target.value })} /></label>
        <label>Moved by <input list={`directors-${title}`} value={d.mover} onChange={(e) => setD({ ...d, mover: e.target.value })} /></label>
        <label>Seconded by <input list={`directors-${title}`} value={d.second} onChange={(e) => setD({ ...d, second: e.target.value })} /></label>
        <datalist id={`directors-${title}`}>{directors.map((n) => <option key={n} value={n} />)}</datalist>
      </div>
      <RollCall directors={directors} votes={d.votes} onChange={(votes) => setD({ ...d, votes })} />
      <p className="muted">{t.aye} aye · {t.no} no · {t.abstain} abstain · {t.absent} absent{suggested && <> · on their face the votes {suggested === "approved" ? "carry" : "fail"} the motion</>}</p>
      <div className="fields">
        <label>Outcome, the board's word <select value={d.outcome} onChange={(e) => setD({ ...d, outcome: e.target.value })}><option value="">(open)</option>{OUTCOMES.map((o) => <option key={o}>{o}</option>)}</select></label>
        <label>Recorded by <input value={d.by} onChange={(e) => setD({ ...d, by: e.target.value })} /></label>
        <label className="wide">Notes <input value={d.notes} onChange={(e) => setD({ ...d, notes: e.target.value })} /></label>
      </div>
      {ready && (
        <Confirm busy={busy} onConfirm={() => onSave(d)} summary={<p>Record: "{d.motion}" moved by {d.mover || "—"}, seconded by {d.second || "—"}; {t.aye}–{t.no}, {d.outcome || "vote open"}. The minutes draft will quote it.</p>}>
          Record the decision
        </Confirm>
      )}
    </article>
  );
}
