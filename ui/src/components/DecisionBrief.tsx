import type { EvidenceEntry } from "../lib/docref";
import { EvidenceEntries } from "./EvidenceEntries";

export interface BriefOption { label: string; values: string[] }
export interface Brief { question: string; criteria: string[]; options: BriefOption[]; facts?: string[] }

export const BRIEF_FOOTER = "jason lays out the options and the facts on file. It does not recommend one; the board chooses.";

/** The options before the motion: one question, one lettered card per option (A, B, C) with the same criteria in the
 * same order, and the facts on file. It never recommends. `columns` is the three-column stage variant. `sources` are the
 * matter's evidence as the loader mapped it (`evidenceRefs`): each document a `Doc` chip, each command to copy; the
 * facts a person wrote stay text. */
export function DecisionBrief({ decision, columns, sources }: { decision: Brief; columns?: boolean; sources?: readonly EvidenceEntry[] | null }) {
  const d = decision ?? { question: "", criteria: [], options: [], facts: [] };
  const facts = d.facts ?? [];
  return (
    <div className={`brief${columns ? " brief-columns" : ""}`}>
      <p className="brief-q">{d.question}</p>
      <div className="brief-options">
        {d.options.map((o, i) => (
          <article key={i} className="brief-option" aria-label={`Option ${String.fromCharCode(65 + i)}`}>
            <div className="brief-option-head"><span className="brief-letter">{String.fromCharCode(65 + i)}</span><strong>{o.label}</strong></div>
            <dl>
              {d.criteria.map((c, j) => (
                <div key={j}><dt>{c}</dt><dd>{o.values[j] ?? ""}</dd></div>
              ))}
            </dl>
          </article>
        ))}
      </div>
      {facts.length > 0 && <ul className="brief-facts">{facts.map((f, i) => <li key={i}>{f}</li>)}</ul>}
      <EvidenceEntries entries={sources} label="Sources" />
      <p className="brief-foot">{BRIEF_FOOTER}</p>
    </div>
  );
}
