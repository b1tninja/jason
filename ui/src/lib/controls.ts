import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getJson, serverSession, signInRefusal } from "./api";
import type { GlyphName } from "../components/Glyph";
import { formatCents, isCentsKey, titleCase } from "./format";

// The Controls screen's data (docs/console/screens/controls.md). The shapes are the loaders': `jason.controls.view`
// (`row`, `compose`, `one`, `notices`) behind `GET /api/controls`, `GET /api/control?key=`, `GET /api/control-notices?subject=`,
// and `POST /api/write/controls/<key>` (`jason.web.extra.controls`). Every state is a word the loader makes; the page
// invents none, and a suggestion never says it is in force.

/** A control's recorded state (`ControlState`). */
export type ControlState = "suggested" | "proposed" | "adopted" | "declined" | "deferred" | "retired";
/** The loader's `standing` key: the state, with an adopted control split three ways by its date and the roster. */
export type Standing = ControlState | "in-force" | "in-force-roster-lacks" | "adopted-not-in-force";
export type ControlFamily = "money" | "contracts" | "reviews" | "notices" | "meetings" | "onboarding" | "applying";

export const FAMILIES: readonly ControlFamily[] = ["money", "contracts", "reviews", "notices", "meetings", "onboarding", "applying"];
/** In the order the list sorts them: adopted first, then proposed, suggested, deferred, declined, retired. */
export const STATES: readonly ControlState[] = ["adopted", "proposed", "suggested", "deferred", "declined", "retired"];
export const FAMILY_TITLES: Readonly<Record<ControlFamily, string>> = {
  money: "Money", contracts: "Contracts", reviews: "Reviews", notices: "Notices", meetings: "Meetings", onboarding: "Onboarding", applying: "Applying plans",
};

/** Fixed words of the screen (the brief, section D). */
export const WORDS = {
  tagline: "jason suggests; the board adopts",
  reading: "jason's reading, not the provision",
  onlyAdds: "A control only adds",
  propose: "Propose to the board",
  openInDecisions: "Open in Decisions",
  recordedBy: "recorded by the secretary",
  empty: "jason has not read your governing documents. Ingest them from Onboarding.",
} as const;

export interface ControlScope { kind: string; value: string }
/** `jason.controls.effective.InForce` as the row carries it: `ok` is true only for an adopted control whose date has
 * come; `lacks` is the roster's shortfall in words ("" when it can satisfy the control). */
export interface ControlInForce { ok: boolean; reason: string; lacks: string }
export interface ControlBasis { citation: string; words: string; floor: Record<string, unknown> | null }
export interface ControlFloor { provision: Record<string, unknown> | null; catalog: Record<string, unknown> | null; read: boolean; note: string }
/** The decision the secretary recorded; `meeting`, `outcome`, and `tally` (vote counts) only in an open session. */
export interface ControlDecision { id: string; meeting?: string; outcome?: string; tally?: Record<string, number> }
/** Where the control bites: an approval kind (`key`, with the kind's own rule beside what the control asks), or a workflow
 * step, send, or spend (`what`). */
export interface ControlTouch {
  kind: string; what?: string; key?: string | null; title?: string; builtin?: string; with?: string; changes?: boolean; note?: string;
}
export interface ControlHistoryEntry { act: string; by?: string; at?: string; why?: string; decision?: string; againOn?: string }
/** Offices and counts, never a person. */
export interface RosterOffice { office: string; count: number }
export interface RosterCheckData {
  read: boolean; needs: RosterOffice[]; seated: RosterOffice[]; missing: { office: string }[]; lacks: string;
}
/** A provision changed since the control was recorded. `one()` makes `was`/`now`/`changedOn`; the list carries the
 * reading's `wasWords`/`words`. */
export interface ControlChanged {
  was?: string; now?: string; changedOn?: string; basis?: string; citation?: string; wasWords?: string; words?: string; key?: string;
}

/** One control: a row of the list and the card's data (`view.row`). */
export interface ControlRowData {
  key: string; type: string; title: string; family: ControlFamily; familyTitle: string; scope: ControlScope;
  parameters: Record<string, unknown>; summary: string; boardSets: string[];
  state: ControlState; standing: Standing | string; stateWord: string;
  inForce: ControlInForce; basis: ControlBasis; floor: ControlFloor;
  reading: string; readingLabel: string; touches: ControlTouch[];
  proposedAs: string | null; proposedStatus: string | null;
  decision: ControlDecision | null; effective: string; history: ControlHistoryEntry[];
  roster: RosterCheckData; missing: string[]; changed: ControlChanged | null;
}

/** A provision jason cannot read cleanly: a question for the board or counsel, never a suggestion. */
export interface ControlQuestion {
  key: string; type: string; title: string; family: ControlFamily; familyTitle: string; kind: "question";
  document: string; number: string; citation: string; words: string; question: boolean; whyQuestion: string;
  floorNote?: string; reading?: string; readingLabel?: string;
}

/** A control that would go below a floor, listed with the floor. The loader has no source for these yet (`refused` is
 * empty); the shape is the spec's. */
export interface RefusedControl { title: string; why: string; floor: { citation: string; words: string } }

export interface ControlGroup { family: ControlFamily; title: string; controls: ControlRowData[]; questions: ControlQuestion[] }
export interface ControlCounts {
  total: number; adopted: number; inForce: number; adoptedNotInForce: number; proposed: number; suggested: number;
  declined: number; deferred: number; retired: number; questions: number; refused: number;
}
/** `GET /api/controls`. */
export interface ControlsPage {
  found: boolean; note?: string; asOf: string; label: string; readingLabel: string;
  counts: ControlCounts; heading: string; families: ControlGroup[]; controls: ControlRowData[]; questions: ControlQuestion[];
  refused: RefusedControl[]; read: string; empty: string; rosterRead: boolean; caveats: string[];
  types: { key: string; title: string; family: ControlFamily }[];
}

/** The provision as the documents hold it now (`view._current_words`). */
export interface ControlProvision {
  found: boolean; note?: string; citation?: string; words?: string; address?: string; changedOn?: string; setBy?: string;
  outline?: unknown[];
}
/** `GET /api/control?key=`: `found: false` with `note` for a key with no control. */
export interface OneControl {
  found: boolean; key?: string; note?: string; control: ControlRowData; provision: ControlProvision;
  label: string; readingLabel: string; caveats: string[];
}

/** One control a notice names (`view._notice`); `reason` on a control adopted but not yet in force. */
export interface NoticeControl {
  key: string; title: string; adoptedOn: string; effective: string; effect: string; link: string; reason?: string;
}
/** `GET /api/control-notices?subject=`. An approval kind carries the effective rule; a step or send carries the lists. */
export interface ControlNotices {
  found: boolean; note?: string; subject: string; subjectKind: string; title: string; asOf: string;
  builtin?: string; why?: string; stricter?: boolean;
  second?: { always: boolean; aboveCents: number | null }; roles?: string[]; mustInclude?: string[]; clash?: string;
  controls: NoticeControl[]; waiting: NoticeControl[]; refusals: string[]; caveats: string[];
}

/** One gate a control adds to a workflow step (`jason.controls.view.step_controls`), on `RunStep.controls`: the control, the
 * gate (`resolution`: a board resolution on record first; `second`: a second, different person confirms; `roles`: only these
 * offices record it), and `why`, the sentence the engine refuses with. `state`: in force, waiting (adopted, the date not
 * reached: binds nothing yet), or refused (in force, and the roster cannot satisfy it). `firstBy` on a `second` gate: who
 * made the first of two. */
export interface StepControl {
  key: string; title: string; why: string; gate: "resolution" | "second" | "roles" | string;
  state: "in force" | "waiting" | "refused" | string; effective: string; roles?: string[]; firstBy?: string;
}

/** `POST /api/write/controls/<key>` with `{act: "propose"}`: the board item made or refreshed, and the control as it now stands. */
export interface ProposeAnswer {
  key: string; item: string; state: ControlState; refreshed: boolean; board: unknown; by: string; control: ControlRowData;
}

// -- standing: the word and the glyph, never colour alone -----------------------------------------------------------------

export type StandingTone = "neutral" | "good" | "warn" | "bad";
export interface StandingLook { tone: StandingTone; glyph: GlyphName; word: string }

/** The short word and mark for each standing the loader names. An adopted control has three: in force, adopted with the
 * date ahead (`calendar-clock`), and in force while the roster cannot satisfy it (`user-x`). The loader's own sentence
 * (`stateWord`) is shown beside it. A suggestion has no "in force" in any of them. */
export function lookOf(standing: string, effective = ""): StandingLook | null {
  switch (standing) {
    case "suggested": return { tone: "neutral", glyph: "proposal", word: "suggested" };
    case "proposed": return { tone: "neutral", glyph: "paperclip", word: "proposed to the board" };
    case "in-force": return { tone: "good", glyph: "shield-check", word: "adopted, in force" };
    case "in-force-roster-lacks": return { tone: "bad", glyph: "user-x", word: "in force, the roster cannot satisfy it" };
    case "adopted-not-in-force":
      return { tone: "warn", glyph: "calendar-clock", word: effective ? `adopted, takes effect ${effective}` : "adopted, not in force" };
    case "declined": return { tone: "neutral", glyph: "circle-x", word: "declined" };
    case "deferred": return { tone: "neutral", glyph: "circle-pause", word: "deferred" };
    case "retired": return { tone: "neutral", glyph: "archive", word: "retired" };
    default: return null;
  }
}

/** Whether the standing is a suggestion's: it never says it is in force. */
export const isSuggestion = (r: { state: string }) => r.state === "suggested";

// -- words for the card ---------------------------------------------------------------------------------------------------

const ACT_WORDS: Record<string, string> = {
  suggest: "suggested", propose: "proposed", adopt: "adopted", decline: "declined", defer: "deferred", retire: "retired",
};
export const actWord = (act: string) => ACT_WORDS[act] ?? act;

/** The day of an ISO date or datetime ("2099-10-03T12:00:00+00:00" is "2099-10-03"), as the record has it. */
export const dayOf = (iso: string | undefined | null) => (iso ? iso.slice(0, 10) : "");

/** A vote as counts, never names: "5 to 0", with abstentions and any other word said after. */
export function voteCounts(tally: Record<string, number> | undefined): string {
  if (!tally) return "";
  const yes = tally.yes ?? 0;
  const no = tally.no ?? 0;
  const rest = Object.entries(tally).filter(([k, n]) => k !== "yes" && k !== "no" && n > 0).map(([k, n]) => `${n} ${k}`);
  return `${yes} to ${no}${rest.length ? `, ${rest.join(", ")}` : ""}`;
}

/** The last history entry of an act (the declined or deferred reason and the date it may be asked again). */
export function lastAct(history: readonly ControlHistoryEntry[], act: string): ControlHistoryEntry | undefined {
  return [...history].reverse().find((h) => h.act === act);
}

// -- routes ---------------------------------------------------------------------------------------------------------------

/** The card's address: `#/controls?key=KEY`. */
export const controlHref = (key: string) => `#/controls?key=${encodeURIComponent(key)}`;
export const CONTROLS_HREF = "#/controls";
/** A board item on the Board action items screen (the item a proposal makes: `control-<key>`). */
export const boardHref = (id: string) => `#/actions?item=${encodeURIComponent(id)}`;
/** The decision on the Decisions screen, for the secretary who records the board's vote. */
export const decisionHref = (id?: string) => `#/decisions${id ? `?decision=${encodeURIComponent(id)}` : ""}`;

/** The control the address asks for (`?key=` in the hash), or "". */
export function focusedControl(hash: string = typeof window === "undefined" ? "" : window.location.hash): string {
  const at = hash.indexOf("?");
  return at < 0 ? "" : new URLSearchParams(hash.slice(at + 1)).get("key") ?? "";
}

export const controlsUrl = (f: { family?: string; state?: string } = {}) => {
  const q = new URLSearchParams();
  if (f.family) q.set("family", f.family);
  if (f.state) q.set("state", f.state);
  const s = q.toString();
  return `/api/controls${s ? `?${s}` : ""}`;
};
export const controlUrl = (key: string) => `/api/control?key=${encodeURIComponent(key)}`;
export const noticesUrl = (subject: string, amountCents?: number) =>
  `/api/control-notices?subject=${encodeURIComponent(subject)}${amountCents !== undefined ? `&amount=${Math.max(0, Math.floor(amountCents))}` : ""}`;
export const proposeUrl = (key: string) => `/api/write/controls/${encodeURIComponent(key)}`;

// -- reading --------------------------------------------------------------------------------------------------------------

export type ControlsRemote<T> =
  | { status: "loading" }
  | { status: "error"; error: string; code?: number; signIn?: string }
  | { status: "ready"; data: T; refreshing: boolean };

/** A read that keeps what it last showed while it reads again (a filter changed, a proposal made), so the page does not
 * blank and a status line is not lost. An error drops the data: nothing is shown as adopted that is not. A 401 or 403 keeps
 * `code`, and a 401 the sign-in link, so the page says it with the server's own sentence. */
export function useControlsApi<T>(path: string): ControlsRemote<T> & { reload: () => void } {
  const [state, setState] = useState<ControlsRemote<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    const ctl = new AbortController();
    setState((s) => (s.status === "ready" && !first.current ? { ...s, refreshing: true } : { status: "loading" }));
    first.current = false;
    getJson<T>(path, ctl.signal).then(
      (data) => setState({ status: "ready", data, refreshing: false }),
      (e: Error) => {
        if (e.name === "AbortError") return;
        const code = e instanceof ApiError ? e.status : undefined;
        setState({ status: "error", error: e.message, code, signIn: signInRefusal(e)?.href });
      },
    );
    return () => ctl.abort();
  }, [path, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}

/** The notice for one approval kind, for a screen that shares it among several parts (a plan's line and its second-signer
 * control). Silent by design: while it loads, when `kind` is empty, and on any failure (a viewer the loader refuses with
 * 401 or 403, a 404, a network error) it is `null`, so the line is an aid and never the gate. `stamp` reads it again when
 * the plan changed (a signature, a re-plan). */
export function useControlNotice(kind: string, amountCents?: number, stamp = ""): ControlNotices | null {
  const [data, setData] = useState<ControlNotices | null>(null);
  const url = kind ? noticesUrl(kind, amountCents) : "";
  useEffect(() => {
    if (!url) { setData(null); return; }
    const ctl = new AbortController();
    getJson<ControlNotices>(url, ctl.signal).then(
      (d) => setData(d && typeof d === "object" && Array.isArray(d.controls) ? d : null),
      () => setData(null),
    );
    return () => ctl.abort();
  }, [url, stamp]);
  return data;
}

/** The offices a control in force lets sign, and the offices that must be among the signers, as a sentence of offices only
 * ("Only the treasurer or the director may sign. The treasurer must be among the signers."), "" when no control narrows
 * it. The loader's `roles` and `mustInclude` are office words; a person's name is never in them. */
export function signerWords(n: ControlNotices | null | undefined): string {
  if (!n || n.found === false || !n.controls?.length) return "";
  const offices = (rs: readonly string[]) => rs.map((r) => `the ${r}`);
  const join = (xs: string[], word: string) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} ${word} ${xs[xs.length - 1]}` : xs[0] ?? "");
  const parts: string[] = [];
  if (n.roles?.length) parts.push(`Only ${join(offices(n.roles), "or")} may sign.`);
  if (n.mustInclude?.length) {
    const who = join(offices(n.mustInclude), "and");
    parts.push(`${who[0].toUpperCase()}${who.slice(1)} must be among the signers.`);
  }
  return parts.join(" ");
}

/** Who is reading, from the server's session (asked once): the name a write goes under, the viewer's office words, and, for
 * an administrator viewing as someone else, whom (the write is refused then: the page says so in place of the control). */
export interface ControlsViewer { known: boolean; name: string; role: string; actingAs: string }
export function useControlsViewer(): ControlsViewer {
  const [v, setV] = useState<ControlsViewer>({ known: false, name: "", role: "", actingAs: "" });
  useEffect(() => {
    let on = true;
    serverSession().then((s) => {
      if (on) setV({ known: true, name: s.signedIn?.name ?? "", role: s.signedIn?.role ?? "", actingAs: s.acting?.name || s.acting?.role || "" });
    });
    return () => { on = false; };
  }, []);
  return v;
}

/** Whether the viewer is the secretary (who records the board's decision in Decisions): their office words say so. */
export const isSecretary = (v: ControlsViewer) => /\bsecretary\b/i.test(v.role);

// -- parameters as words ----------------------------------------------------------------------------------------------------

/** A parameter map (a floor's, as the loader gives it) as a line: "Signers: 2; Roles: director, officer". Amounts are
 * integer cents; the keys and values are the loader's. */
export function paramWords(params: Record<string, unknown> | null | undefined): string {
  if (!params) return "";
  return Object.entries(params).map(([k, v]) => {
    const key = titleCase(k.replace(/Cents$/, ""));
    const val = Array.isArray(v) ? v.join(", ") : isCentsKey(k) && typeof v === "number" ? formatCents(v) : typeof v === "boolean" ? (v ? "yes" : "no") : String(v);
    return `${key}: ${val}`;
  }).join("; ");
}
