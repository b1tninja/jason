import type { ReactNode } from "react";

/** A defined term the words use, recited too (`cite_document`'s `terms`). */
export interface RecitedTerm { term: string; definedAt?: string; address?: string; citation?: string; definition?: string; found?: boolean }

/** `cite_document` / `jason cite --json`: the citation, the stored words whole, the version in force, and the caveat. */
export interface Citation {
  kind?: string; found: boolean; citation: string; text?: string; inForce?: string; caveat?: string; address?: string;
  title?: string; reason?: string; detail?: string; version?: { inForce?: boolean; note?: string } & Record<string, unknown>;
  terms?: RecitedTerm[];
}

function marked(text: string, mark?: string): ReactNode {
  if (!mark) return text;
  const at = text.indexOf(mark);
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{mark}</mark>{text.slice(at + mark.length)}</>;
}

/** The provision's operative words, quoted whole from the stored copy, with its citation, the version in force, and the
 * caveat. Never a paraphrase: a miss says why and recites nothing. `mark` highlights the words that answer the question.
 * A reading of these words goes after it, in a `ReadingLabel`, never inside. */
export function Recitation({ citation, mark }: { citation: Citation; mark?: string }) {
  const c = citation;
  if (!c.found || !c.text)
    return (
      <figure className="recitation recitation-miss">
        <div className="recitation-label">Recited words</div>
        <p className="muted">
          {c.found ? `${c.citation}: an outline, not words to recite.` : `Not found: ${c.citation}${c.reason ? ` (${c.reason.replace(/_/g, " ")})` : ""}${c.detail ? `. ${c.detail}` : ""}.`} Nothing is quoted.
        </p>
      </figure>
    );
  const notInForce = c.version?.inForce === false;
  return (
    <figure className={`recitation${notInForce ? " recitation-not-in-force" : ""}`}>
      <div className="recitation-label">Recited words{notInForce ? " · not in force" : ""}</div>
      <blockquote className="recitation-words">
        {c.text.split(/\n\s*\n/).map((p, n) => <p key={n}>{marked(p.trim(), mark)}</p>)}
      </blockquote>
      <figcaption className="recitation-source">
        <cite>{c.citation}</cite>
        {c.inForce && <span className="muted"> · {c.inForce}</span>}
        {c.address && <code className="chip">{c.address}</code>}
      </figcaption>
      {notInForce && c.version?.note && <p className="notice notice-warn">{c.version.note}</p>}
      {(c.terms ?? []).filter((t) => t.found && t.definition).map((t) => (
        <div key={t.term} className="recitation-term">
          <strong>{t.term}</strong>: <q>{t.definition}</q> <span className="muted">({t.citation || t.definedAt})</span>
        </div>
      ))}
      {c.caveat && <p className="recitation-caveat">{c.caveat}</p>}
    </figure>
  );
}
