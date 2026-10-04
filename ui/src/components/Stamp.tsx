import type { CSSProperties } from "react";
import { NOT_A_MARK, STAMP_WORDS, isSealWord, isStampWord, norm, type StampWord } from "../lib/marks";

export interface StampProps {
  /** The decision in its own word (`STAMP_WORDS`). A word outside the set (a motion's own word the set lacks) renders
   * in the neutral tone so the record is never lost. A seal word, `draft`, `confidential`, or `recorded` renders nothing. */
  word: StampWord | (string & {});
  /** Who decided or recorded it: "the board, 4 yes, 0 no", "R. Lind, secretary". */
  by?: string;
  /** When, as the record has it (ISO date). */
  date?: string;
  /** The record of the sending (a Mailroom communication id, a sent-log line). `sent` without it renders nothing:
   * a stamp follows the record, never a click. */
  sentRef?: string;
  /** The stamp's height, a CSS length; the words scale with it. */
  size?: string;
  /** Degrees; 0 for a table cell. */
  tilt?: number;
  className?: string;
}

const warned = new Set<string>();
function refuse(word: string, why: string) {
  if (warned.has(word)) return;
  warned.add(word);
  console.warn(`Stamp: ${JSON.stringify(word)} ${why}`);
}

/** What a person or the board decided, in its own word, with who and when: a rectangular mark, tilted on a document and
 * flat in a table. jason never stamps; its own acts are `Seal`s, and the two never share a word. */
export function Stamp({ word, by, date, sentRef, size = "2.2em", tilt = -6, className }: StampProps) {
  const w = norm(word);
  if (!w) return null;
  if (isSealWord(w)) { refuse(w, "is a seal word (what jason did), never a stamp"); return null; }
  if ((NOT_A_MARK as readonly string[]).includes(w)) { refuse(w, "is not a stamp: a draft is the drafted seal, confidential the P3 chip, a county recording the read seal"); return null; }
  if (w === "sent" && !sentRef?.trim()) { refuse(w, "needs sentRef: a stamp follows the record of the sending"); return null; }
  const def = isStampWord(w) ? STAMP_WORDS[w as StampWord] : { tone: "neutral" as const, label: String(word).trim() };
  const sub = [by, date].filter(Boolean).join(" · ");
  const aria = [def.label, sub, sentRef ? `record ${sentRef}` : ""].filter(Boolean).join(", ");
  const style = { "--stamp-size": size, "--stamp-tilt": `${tilt}deg` } as CSSProperties;
  return (
    <span className={`stamp stamp-${def.tone}${sub ? " stamp-has-sub" : ""}${className ? ` ${className}` : ""}`} role="img" aria-label={aria}
      data-word={w} data-sent-ref={sentRef || undefined} style={style}>
      <span className="stamp-word" aria-hidden="true">{def.label}</span>
      {sub && <span className="stamp-sub" aria-hidden="true">{sub}</span>}
    </span>
  );
}
