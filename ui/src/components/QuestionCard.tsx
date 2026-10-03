import { useEffect, useId, useState } from "react";
import { Confirm } from "./Confirm";
import { Evidence } from "./Evidence";
import { cleanName, signerProblem } from "../lib/approvals";

/** What answering a question unblocks (`intake_rank.Unblocks.as_dict`). */
export interface Unblocks {
  items?: { key: string; status: string }[]; gates?: string[]; records?: string[]; clocks?: string[]; sections?: string[];
  citedWeight?: number; qualityOnly?: boolean;
}

/** One open question as `next_questions` gives it (`onboarding_session.question_dict`). */
export interface Question {
  id: string; kind?: string; subject?: string; question: string; choices?: string[]; suggestion?: string; likely?: boolean;
  evidence?: string[]; priority?: number; unblocks?: Unblocks; serves?: string; highStakes?: boolean; inQueue?: boolean;
}

/** An answer as recorded (`onboarding_confirm`'s shape). */
export interface Answered { answer: string; answeredBy: string; answeredAt?: string; confirmedBy?: string; confirmedAt?: string }

export function unblocksText(u?: Unblocks): string {
  if (!u) return "";
  const out: string[] = [];
  if (u.clocks?.length) out.push(`${u.clocks.length} legal ${u.clocks.length === 1 ? "clock" : "clocks"}`);
  if (u.items?.length) out.push(`${u.items.length} checklist ${u.items.length === 1 ? "item" : "items"}`);
  if (u.gates?.length) out.push(`the ${u.gates.join(", ")} gate`);
  if (u.records?.length) out.push(`fills ${u.records.join(", ")}`);
  if (u.sections?.length) out.push(`${u.sections.length} cited ${u.sections.length === 1 ? "section" : "sections"}`);
  return out.join(", ") || (u.qualityOnly ? "the text's quality only" : "");
}

const OTHER = "\u0000other";

/** One ranked question for a person: the rank (in words too), what answering unblocks (a legal clock first), the
 * question, the choices with jason's suggestion labeled and never pre-selected, the evidence, and the answer, saved
 * behind `Confirm` as a named person (pre-filled with `me`; never jason). An answer never carries a secret; the server
 * refuses one. A high-stakes answer is confirmed by a second person before it is applied. */
export function QuestionCard({ question, rank, me = "", onAnswer, answered, compact = false, busy, error }: {
  question: Question; rank?: number; me?: string; onAnswer?: (body: { id: string; answer: string; by: string }) => void;
  answered?: Answered | null; compact?: boolean; busy?: boolean; error?: string;
}) {
  const uid = useId();
  const q = question;
  const [pick, setPick] = useState("");
  const [other, setOther] = useState("");
  const [by, setBy] = useState(me);
  useEffect(() => setBy(me), [me]);
  const answer = pick === OTHER ? other.trim() : pick;
  const who = cleanName(by);
  const problem = !answer ? "Pick an answer, or write one." : signerProblem(who);
  const unblocks = unblocksText(q.unblocks);
  return (
    <article className={`question-card${q.highStakes ? " question-high" : ""}${compact ? " question-compact" : ""}`} aria-labelledby={`${uid}-q`}>
      {rank !== undefined && <span className="question-rank"><span className="visually-hidden">Rank </span>{rank}</span>}
      <div className="stack-sm">
        <div className="row wrap">
          <h3 id={`${uid}-q`} className="question-text">{q.question}</h3>
          {q.highStakes && <span className="badge badge-warn">high stakes</span>}
          {q.likely && <span className="badge badge-neutral">likely</span>}
        </div>
        {unblocks && <p className="muted"><strong>Unblocks:</strong> {unblocks}</p>}
        {!compact && <Evidence items={q.evidence} />}
        {answered ? (
          <p className="notice">
            Answered by {answered.answeredBy}{answered.answeredAt ? `, ${answered.answeredAt.slice(0, 10)}` : ""}: <q>{answered.answer}</q>
            {q.highStakes && (answered.confirmedBy ? ` · confirmed by ${answered.confirmedBy}` : " · waits on a second person's confirmation")}
          </p>
        ) : !compact && (
          <form className="stack-sm" onSubmit={(e) => e.preventDefault()}>
            <fieldset className="question-choices">
              <legend>Your answer</legend>
              {(q.choices ?? []).map((c) => (
                <label key={c}>
                  <input type="radio" name={`${uid}-a`} value={c} checked={pick === c} onChange={() => setPick(c)} /> {c}
                  {q.suggestion === c && <span className="reading-label reading-jason">jason's suggestion</span>}
                </label>
              ))}
              <label><input type="radio" name={`${uid}-a`} value={OTHER} checked={pick === OTHER} onChange={() => setPick(OTHER)} /> Another answer</label>
              {pick === OTHER && <input aria-label="Another answer" value={other} onChange={(e) => setOther(e.target.value)} aria-describedby={`${uid}-secret`} />}
            </fieldset>
            {q.suggestion && !(q.choices ?? []).includes(q.suggestion) && <p className="muted">jason's suggestion, a lead: {q.suggestion}</p>}
            <p id={`${uid}-secret`} className="muted"><strong>Never a secret:</strong> no password, account number, or key.{q.highStakes ? " A second person confirms this answer before it is applied." : ""}</p>
            <div className="row wrap">
              <label className="approve-field">Answered by<input value={by} onChange={(e) => setBy(e.target.value)} autoComplete="name" required /></label>
              {problem ? (
                <button type="button" className="primary" aria-disabled="true" aria-describedby={`${uid}-why`}>Save the answer</button>
              ) : (
                <Confirm busy={busy} onConfirm={() => onAnswer?.({ id: q.id, answer, by: who })} summary={<p>Save "{answer}" as {who}'s answer to {q.id}. Nothing is applied until a person runs the apply.</p>}>
                  Save the answer
                </Confirm>
              )}
              <span id={`${uid}-why`} className="muted" role="status">{problem && (pick || other) ? problem : ""}</span>
            </div>
            {error && <p className="notice notice-error" role="alert">{error}</p>}
          </form>
        )}
      </div>
    </article>
  );
}
