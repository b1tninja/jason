import type { CSSProperties } from "react";
import { SEAL_STATE_WORDS, SEAL_WORDS, isSealWord, norm, type SealState, type SealWord } from "../lib/marks";

export interface SealProps {
  /** What jason did (`SEAL_WORDS`). A word outside the set, a stamp's word, or `recorded` renders nothing. */
  word: SealWord;
  /** Whom or what: "the manager" (waiting on), "for the treasurer" (proposes), "ask counsel" (not jason's). */
  detail?: string;
  /** A county filing's instrument number, on the `read` seal: jason read the recorder's index; it recorded nothing. */
  instrument?: string;
  /** When, as said: "2026-10-03", "since 2026-09-28". */
  date?: string;
  /** The seal's diameter, a CSS length; its words scale with it. */
  size?: string;
  /** Ink instead of the state's colour (a printed page). */
  tone?: "ink";
  /** The box and the label on one line, for a table cell or a sentence. */
  inline?: boolean;
  className?: string;
}

const BOX: Record<SealState, string> = {
  open: '<rect x="4" y="4" width="16" height="16" rx="2.5"/>',
  done: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="m8 12.3 2.6 2.6L16 9.5"/>',
  question: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M9.6 10a2.4 2.4 0 1 1 3.4 2.2c-.7.3-1 .8-1 1.5"/><path d="M12 16.6h.01"/>',
  not: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="m8.5 15.5 7-7"/>',
};
// jason's eave: the roof line over the J, drawn on a 48 grid.
const EAVE = '<path d="M5.5 20 24 5l18.5 15" stroke-width="3.4"/><path d="M10 18v24M38 18v24M10 42h28" stroke-width="3"/><path d="M27.5 18.5v15.5a5.5 5.5 0 0 1-11 0" stroke-width="4"/>';

function Box({ state }: { state: SealState }) {
  return <svg className="seal-box" viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" strokeWidth={1.9}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" dangerouslySetInnerHTML={{ __html: BOX[state] }} />;
}

const warned = new Set<string>();

/** What jason did, and whether a person still has to act: a round seal with jason's eave on top and a box that is
 * empty (open), checked (jason's part is done), questioned (unresolved), or struck (not jason's to do). Never a
 * person's or the board's word; those are `Stamp`s. */
export function Seal({ word, detail, instrument, date, size = "5em", tone, inline = false, className }: SealProps) {
  const w = norm(word);
  if (!isSealWord(w)) {
    if (w && !warned.has(w)) { warned.add(w); console.warn(`Seal: ${JSON.stringify(word)} is not a seal word (what jason did); a decision is a Stamp`); }
    return null;
  }
  const def = SEAL_WORDS[w as SealWord];
  const sub = [detail, instrument ? `instrument ${instrument}` : "", date].filter(Boolean).join(" · ");
  const aria = [def.label, sub, SEAL_STATE_WORDS[def.state]].filter(Boolean).join(", ");
  const cls = `seal seal-${def.state}${tone === "ink" ? " seal-ink" : ""}${inline ? " seal-inline" : ""}${className ? ` ${className}` : ""}`;
  if (inline) {
    return (
      <span className={cls} role="img" aria-label={aria} data-word={w}>
        <Box state={def.state} /><span className="seal-label" aria-hidden="true">{def.label}</span>
        {sub && <span className="seal-sub" aria-hidden="true">{sub}</span>}
      </span>
    );
  }
  return (
    <span className={cls} role="img" aria-label={aria} data-word={w} style={{ "--seal-size": size } as CSSProperties}>
      <span className="seal-disc" aria-hidden="true">
        <svg className="seal-eave" viewBox="0 0 48 48" width="1em" height="1em" fill="none" stroke="currentColor" strokeLinecap="round"
          strokeLinejoin="round" focusable="false" dangerouslySetInnerHTML={{ __html: EAVE }} />
        <Box state={def.state} />
        <span className="seal-label">{def.label}</span>
      </span>
      {sub && <span className="seal-sub" aria-hidden="true">{sub}</span>}
    </span>
  );
}
