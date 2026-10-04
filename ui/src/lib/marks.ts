// The two vocabularies of marks on a record. A stamp says what a PERSON decided, in the motion's or the decision's own
// word; a seal says what JASON did and whether a person still has to act. They never share a word, so a reader can tell
// a proposal from a decision at arm's length (marks.test.tsx checks it, word by word). Neither is a status: pending,
// due, and missing are badges and attention glyphs.

export type StampTone = "good" | "bad" | "warn" | "neutral";

/** A person's or the board's decision. `table`, `continue`, and `refer` are motions the board votes on by roll call;
 * only `withdrawn` (by the mover, before the vote) is a logged act without a vote. `sent` follows a record of the
 * sending (`sentRef`), never a click. */
export type StampWord = "carried" | "failed" | "approved" | "denied" | "adopted" | "tabled" | "continued" | "referred" | "withdrawn" | "sent";

export const STAMP_WORDS: Readonly<Record<StampWord, { tone: StampTone; label: string; meaning: string }>> = {
  carried: { tone: "good", label: "Carried", meaning: "A motion passed on a roll call" },
  failed: { tone: "bad", label: "Failed", meaning: "A motion did not pass" },
  approved: { tone: "good", label: "Approved", meaning: "A person or the board approved a document or a request" },
  denied: { tone: "bad", label: "Denied", meaning: "A request or an appeal refused" },
  adopted: { tone: "good", label: "Adopted", meaning: "A resolution, budget, rule, or policy the board adopted" },
  tabled: { tone: "warn", label: "Tabled", meaning: "Set aside by the board's vote" },
  continued: { tone: "warn", label: "Continued", meaning: "Carried over to a later meeting by the board's vote" },
  referred: { tone: "warn", label: "Referred", meaning: "Sent by the board's vote to a committee, counsel, or the manager to report back" },
  withdrawn: { tone: "neutral", label: "Withdrawn", meaning: "The mover withdrew it before the vote; no vote" },
  sent: { tone: "good", label: "Sent", meaning: "Mailed or delivered, on the record of the sending; cannot be recalled" },
};

/** Whether jason's part is open (a person still has to act), done, unresolved, or not jason's to do. */
export type SealState = "open" | "done" | "question" | "not";

/** What jason did. A county filing is `read` with its instrument number: jason read the recorder's index; it records
 * nothing. `filed` is jason saving a file where it belongs, a seal and never a stamp. */
export type SealWord =
  | "proposes" | "suggests" | "needs-approval" | "waiting-on"
  | "read" | "drafted" | "reminded" | "filed"
  | "could-not-confirm" | "not-sure"
  | "not-jason" | "wont-send";

export const SEAL_WORDS: Readonly<Record<SealWord, { state: SealState; label: string; meaning: string }>> = {
  proposes: { state: "open", label: "jason proposes", meaning: "A draft; a person approves or sends it back" },
  suggests: { state: "open", label: "jason suggests", meaning: "A reading of the clocks or options; the board decides" },
  "needs-approval": { state: "open", label: "needs approval", meaning: "Nothing goes out without it" },
  "waiting-on": { state: "open", label: "waiting on", meaning: "jason asked a person and is waiting" },
  read: { state: "done", label: "jason read", meaning: "From the records, as of a date; a county filing with its instrument number" },
  drafted: { state: "done", label: "jason drafted", meaning: "Wording is ready for a person to edit" },
  reminded: { state: "done", label: "jason reminded", meaning: "The deadline notice went out" },
  filed: { state: "done", label: "jason filed", meaning: "Saved where it belongs" },
  "could-not-confirm": { state: "question", label: "not confirmed", meaning: "No record found; a gap is a place to look, and a person checks" },
  "not-sure": { state: "question", label: "not sure", meaning: "Two records disagree; a person decides" },
  "not-jason": { state: "not", label: "ask a person", meaning: "A legal, tax, or board question" },
  "wont-send": { state: "not", label: "will not send", meaning: "Without approval it stays a draft" },
};

export const SEAL_STATE_WORDS: Readonly<Record<SealState, string>> = {
  open: "a person still has to act",
  done: "done",
  question: "unresolved",
  not: "not jason's to do",
};

/** Words that are neither: a draft is the `drafted` seal; confidential is the P3 level chip, a level and not a decision;
 * a county recording is the `read` seal with its instrument number. */
export const NOT_A_MARK = ["draft", "confidential", "recorded"] as const;

export const norm = (w: string | undefined | null) => String(w ?? "").trim().toLowerCase().replace(/\s+/g, " ");

export function isStampWord(w: string): w is StampWord {
  return Object.prototype.hasOwnProperty.call(STAMP_WORDS, norm(w));
}

export function isSealWord(w: string): w is SealWord {
  return Object.prototype.hasOwnProperty.call(SEAL_WORDS, norm(w));
}

/** The words of a vocabulary, as a reader sees them: each key's parts and each label's words. */
export function markTokens(vocab: Readonly<Record<string, { label: string }>>): Set<string> {
  const out = new Set<string>();
  for (const [key, { label }] of Object.entries(vocab)) for (const t of `${key} ${label}`.toLowerCase().split(/[^a-z']+/)) if (t) out.add(t);
  return out;
}

// -- routing: whose desk a thing is on, from the roster (resolved by the server), never from a thing's words ----------

/** An owner the server resolved from the roster or the profile's assignments: the office's role value (`"treasurer"`,
 * `"vice president"`, `"board"`, `"owners"`), and the person's name when one holds it. A dock deadline's `owners` row
 * and an `Officer` both fit. `adoption` is the assignment's (`"proposed"` until the board adopts it). */
export interface RoutingOwner { role: string; name?: string; adoption?: string }

/** The office's own mark, by its role value. An office without one (a committee, the inspector of elections) is named
 * with no glyph. */
export const ROLE_GLYPH: Readonly<Record<string, "for-board" | "for-president" | "for-vice-president" | "for-secretary" | "for-treasurer" | "for-director" | "for-manager" | "for-counsel" | "for-members">> = {
  board: "for-board",
  president: "for-president",
  "vice president": "for-vice-president",
  secretary: "for-secretary",
  treasurer: "for-treasurer",
  director: "for-director",
  manager: "for-manager",
  counsel: "for-counsel",
  owners: "for-members",
};

export const UNASSIGNED = "unassigned";

const AS_THEMSELVES = new Set(["jason", "owners"]);

/** An office as a sentence names it: "the treasurer", "the board"; jason and owners as themselves (the server's
 * `role_words`). */
export function roleWords(role: string): string {
  const r = norm(role);
  return AS_THEMSELVES.has(r) ? r : `the ${r}`;
}

/** Whether the server resolved an owner: a role, and not an empty one. */
export function isResolved(owner: RoutingOwner | null | undefined): owner is RoutingOwner {
  return !!owner && norm(owner.role) !== "";
}
