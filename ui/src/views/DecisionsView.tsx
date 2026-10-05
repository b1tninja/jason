import { useState } from "react";
import { Badge, Caveats, Confirm, DecisionBrief, DecisionCard, RemoteView, Stamp, type AgendaCandidate, type AgendaPlan, type Brief, type DecisionDraft, type EvidenceEntry } from "../components";
import { HELD_LINE } from "../components/AgendaWizard";
import { EvidenceEntries } from "../components/EvidenceEntries";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";

interface Decision extends DecisionDraft { id: string; meeting: string; item: string; session: string; recorded: string; updated: string; history: string[]; tally: Record<string, number>; suggested: string }
/** A candidate with its evidence as the loader mapped it (`evidenceRefs`: a document reference, a command, or text). */
type Candidate = AgendaCandidate & { evidenceRefs?: EvidenceEntry[] };
type Plan = Omit<AgendaPlan, "decisions" | "candidates"> & { decisions: Decision[]; candidates: Candidate[] };

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

/** A person writes the brief: the question, the criteria (one per line), each option's label and its value for each
 * criterion, and the facts on file. There is no field for a recommendation, and the store refuses one. */
function BriefForm({ item, by, busy, onSave }: { item: Candidate; by: string; busy: boolean; onSave: (brief: Brief) => void }) {
  const [question, setQuestion] = useState(item.ask ? `${item.ask}?`.replace(/\?\?$/, "?") : "");
  const [criteria, setCriteria] = useState("");
  const [options, setOptions] = useState<{ label: string; values: string }[]>([{ label: "", values: "" }, { label: "", values: "" }]);
  const [facts, setFacts] = useState(item.evidence?.length ? item.evidence.join("\n") : "");
  const crit = lines(criteria);
  const brief: Brief = { question: question.trim(), criteria: crit, options: options.filter((o) => o.label.trim()).map((o) => ({ label: o.label.trim(), values: crit.map((_, j) => lines(o.values)[j] ?? "") })), facts: lines(facts) };
  const ready = brief.question.length > 0 && brief.options.length >= 2;
  return (
    <div className="brief-form">
      <p className="muted">No brief yet. Lay out the options side by side: the same criteria for each, and the facts on file. jason never recommends one; the board chooses.</p>
      <div className="fields">
        <label className="wide">The question before the board<input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Which contract, if any, starting 2027-01-01?" /></label>
        <label className="wide">Criteria, one per line<textarea rows={3} value={criteria} onChange={(e) => setCriteria(e.target.value)} placeholder={"Monthly cost\nTerm\nOpen questions"} /></label>
        {options.map((o, i) => (
          <label key={i}>Option {String.fromCharCode(65 + i)}
            <input value={o.label} onChange={(e) => setOptions(options.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} placeholder="label" />
            <textarea rows={Math.max(2, crit.length)} value={o.values} onChange={(e) => setOptions(options.map((x, j) => (j === i ? { ...x, values: e.target.value } : x)))} placeholder="one value per criterion, in order" />
          </label>
        ))}
        <label className="wide"><span /><button onClick={() => setOptions([...options, { label: "", values: "" }])}>Add an option</button></label>
        <label className="wide">Facts on file, one per line<textarea rows={3} value={facts} onChange={(e) => setFacts(e.target.value)} /></label>
      </div>
      <EvidenceEntries entries={item.evidenceRefs} label="Sources" />
      {ready && by.trim() ? (
        <Confirm busy={busy} onConfirm={() => onSave(brief)} summary={<div><p>Save the brief for "{item.title}" to the plan, written by {by}: the question, {brief.criteria.length} criteria, {brief.options.length} options ({brief.options.map((o) => o.label).join(", ")}), {brief.facts?.length ?? 0} facts. No recommendation is saved; the board chooses.</p></div>}>
          Save the brief
        </Confirm>
      ) : <span className="muted">{by.trim() ? "A brief needs the question and at least two options." : "Enter your name above to save."}</span>}
    </div>
  );
}

/** Decisions: one section per open matter for the next meeting, the brief (written by a person) above the
 * `DecisionCard` that records what the board did. */
export function DecisionsView() {
  const r = useApi<Plan>("/api/agenda-plan");
  const [by, setBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Record<string, Decision>>({});
  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const saveBrief = (date: string, item: Candidate, brief: Brief) => run(async () => {
    await postJson(`/api/write/agenda-plan/${date}`, { by, items: { [item.id]: { brief } } });
    r.reload();
  });
  const saveDecision = (date: string, item: AgendaCandidate, d: DecisionDraft) => run(async () => {
    const out = await postJson<Decision>("/api/decisions", { meeting: date, title: d.title, motion: d.motion, item: item.id, session: item.session, mover: d.mover, second: d.second, votes: d.votes, recused: d.recused, outcome: d.outcome, by: d.by, notes: d.notes });
    setSaved((s) => ({ ...s, [out.id]: out }));
  });
  return (
    <div className="stack">
      <header className="screen-head">
        <h1>Decisions</h1>
        <p className="muted">Matters with more than one way forward. Each brief lays out the options side by side; the decision card records the motion, the roll call, and the board's own word for the outcome.</p>
      </header>
      <RemoteView r={r}>
        {(d) => (
          <div className="stack">
            <div className="row wrap"><label>Your name <input value={by} onChange={(e) => setBy(e.target.value)} placeholder="who writes the brief" /></label><span className="muted">a brief is written by a person and saved to the {d.date} plan</span></div>
            {error && <p className="notice notice-error">{error}</p>}
            {d.candidates.length === 0 && <p className="muted">No board item is proposed or on the agenda for {d.date}.</p>}
            {d.candidates.map((c) => {
              const existing = saved[`${d.date}--${c.id}`] ?? d.decisions.find((x) => x.item === c.id);
              return (
                <section key={c.id} className="decision-section">
                  <div className="row wrap">
                    <h2>{c.title}</h2>
                    <Badge>{`Board meeting ${d.date}`}</Badge>
                    {c.session === "executive session" && <Badge tone="warn">executive session</Badge>}
                    {existing?.outcome && <Stamp word={existing.outcome} by={existing.by || undefined} date={existing.recorded?.slice(0, 10) || undefined} tilt={0} size="1.9em" />}
                  </div>
                  {c.held ? <p className="muted">{HELD_LINE} Its brief and its decision are written there.</p> : (
                    <>
                      {c.brief ? <DecisionBrief decision={c.brief} sources={c.evidenceRefs} /> :<BriefForm item={c} by={by} busy={busy} onSave={(b) => saveBrief(d.date, c, b)} />}
                      <DecisionCard key={c.id + (existing?.updated ?? "")} title={c.title} directors={d.directors} initial={existing ? { ...existing } : { session: c.session, motion: c.motion }} busy={busy} onSave={(dd) => saveDecision(d.date, c, dd)} />
                    </>
                  )}
                </section>
              );
            })}
            <Caveats items={["A recorded decision is the record of what the board decided; jason changes nothing it decided.", "A director who discloses an interest is recorded as recused, as the secretary records the disclosure: not absent, not a no, and never inferred by jason. CIV 5350(b) lists matters an interested director shall not vote on; a contract is 5350(a), through Corporations Code 7233 and 7234. Whether a recused director counts toward the quorum is the bylaws' or counsel's to say; not on file, ask counsel.", "jason lays out the options and the facts on file. It does not recommend one; the board chooses."]} />
          </div>
        )}
      </RemoteView>
    </div>
  );
}
