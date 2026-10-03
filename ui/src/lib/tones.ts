import type { Tone } from "../components/Badge";

/** Status, standing, and priority words to a tone. Unknown words stay neutral; the word itself is always shown. */
const TONES: Record<string, Tone> = {
  // board item status
  open: "warn", proposed: "neutral", "on agenda": "good", "in progress": "good", deferred: "neutral", closed: "neutral",
  // priority
  urgent: "bad", high: "warn", normal: "neutral",
  // standings
  overdue: "bad", "due soon": "warn", upcoming: "neutral", done: "good", "done late": "warn", "no evidence": "bad",
  released: "good", "in default": "bad", stands: "warn", "release due": "bad",
  // jobs and batches
  queued: "neutral", running: "good", failed: "bad", cancelled: "neutral", sent: "good", uncertain: "warn", pending: "neutral",
  // agenda readiness
  ready: "good", "needs work": "warn",
  // documents
  recorded: "good", superseded: "neutral", unrecorded: "warn", missing: "bad", pinned: "good",
  // approvals engine: an approval's status, an item's decision and result
  planned: "neutral", "in review": "warn", approved: "good", "partially approved": "warn", applying: "good", applied: "good",
  withdrawn: "neutral", undecided: "neutral", rejected: "bad", held: "warn", "not applied": "neutral",
  "changed since review": "warn", blocked: "warn",
};

export function toneOf(word: string | null | undefined): Tone {
  return TONES[String(word ?? "").toLowerCase().replace(/_/g, " ")] ?? "neutral";
}
