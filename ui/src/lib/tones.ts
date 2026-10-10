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
  // conversations and policies: a statutory miss or a missing required policy is not an accusation, so never "bad"
  stalled: "warn", replied: "good", assigned: "neutral", routed: "neutral", shared: "neutral", reassigned: "neutral",
  "waiting on us": "warn", "held for the board": "warn", adopted: "good", declined: "neutral",
  required: "neutral", "required and missing": "warn",
  // connections, schedules, and the service heartbeat
  connected: "good", failing: "bad", paused: "warn", "needs sign in": "warn", "needs sign-in": "warn", "not set up": "neutral",
  stale: "warn", stopped: "neutral", draining: "warn", none: "neutral",
  // follow-ups and arrivals
  due: "warn", dropped: "neutral", new: "warn", seen: "neutral", read: "neutral", keyed: "warn", dismissed: "neutral",
};

export function toneOf(word: string | null | undefined): Tone {
  return TONES[String(word ?? "").toLowerCase().replace(/_/g, " ")] ?? "neutral";
}
