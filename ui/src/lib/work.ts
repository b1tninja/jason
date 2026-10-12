import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getJson, postJson, serverSession, signInRefusal } from "./api";
import type { GlyphName } from "../components/Glyph";
import type { StepControl } from "./controls";

// The Work screens' data (docs/console/screens/work.md, docs/console/design-brief-work.md). The shapes are the loaders':
// `jason.web.extra.work` behind `GET /api/work`, `GET /api/work-run?definition=&id=`, `GET /api/work-definitions`, and
// `POST /api/write/work/<definition>/<run id>` (and `.../start`). Every word is the engine's; the page invents none. A
// date says whose it is (its basis); a legal date's words are recited, and jason's reading follows, labeled.

// -- words ------------------------------------------------------------------------------------------------------------------

/** Fixed words of the screens (the brief, section D). */
export const WORDS = {
  yours: "Yours",
  others: "Waiting on others",
  clock: "Waiting on a clock",
  board: "The board",
  empty: "No runs are open. Start one from Start a run.",
  loading: "reading the runs on disk",
  legalDate: "a legal date",
  proposed: "proposed, not the law's",
  changedSince: "changed since",
  recordInDecisions: "Record in Decisions",
  reviewInApprovals: "Review in Approvals",
  reading: "jason's reading, not the provision",
} as const;

/** The loader's group keys, in the order the list draws them. */
export const GROUP_KEYS = ["yours", "others", "clock", "board"] as const;
export type GroupKey = (typeof GROUP_KEYS)[number];
export const GROUP_TITLES: Readonly<Record<GroupKey, string>> = {
  yours: WORDS.yours, others: WORDS.others, clock: WORDS.clock, board: WORDS.board,
};

/** A group shows this many rows, then its count and a way to show the rest. */
export const GROUP_FOLD = 5;

/** The due filters the loader takes (`DUE_FILTERS`), in words. */
export const DUE_FILTERS: readonly { value: string; label: string }[] = [
  { value: "soon", label: "Due soon (within a week or past)" },
  { value: "week", label: "Due this week" },
  { value: "overdue", label: "Overdue" },
  { value: "legal", label: "A legal date" },
  { value: "past", label: "Past a legal date" },
];

// -- the basis of a date ----------------------------------------------------------------------------------------------------

export type BasisWord = "law" | "documents" | "counterparty" | "provider" | "proposed policy" | "person";

export interface BasisLook { word: string; glyph: GlyphName; meaning: string }

/** The basis words the engine uses, the word the screen shows for each, a glyph named for the idea, and what the date is.
 * A word outside these is shown as it came (no glyph). */
export const BASES: Readonly<Record<BasisWord, BasisLook>> = {
  law: { word: "LEGAL", glyph: "scale", meaning: "The law's own date: the provision is recited on the run." },
  documents: { word: "DOCUMENTS", glyph: "file-text", meaning: "A date the governing documents or a sent notice set." },
  counterparty: { word: "COUNTERPARTY", glyph: "handshake", meaning: "A date a vendor, an authority, or the other side stated." },
  provider: { word: "PROVIDER", glyph: "handshake", meaning: "A date a service provider stated." },
  "proposed policy": { word: "PROPOSED", glyph: "proposal", meaning: "proposed, not the law's: jason's proposal until the board adopts it." },
  person: { word: "PERSON", glyph: "user", meaning: "A date a person set." },
};

export const isBasisWord = (w: string): w is BasisWord => Object.prototype.hasOwnProperty.call(BASES, w);

// -- the states of a step ---------------------------------------------------------------------------------------------------

export type StepState = "not started" | "ready" | "running" | "waiting" | "needs a person" | "done" | "skipped" | "blocked" | "failed" | "superseded";
export type StepKind = "check" | "job" | "plan" | "person" | "decision" | "wait" | "branch";
export type RunState = "draft" | "active" | "paused" | "waiting" | "done" | "cancelled" | "failed";

export interface StateLook { glyph: GlyphName; tone: "neutral" | "good" | "warn" | "bad"; meaning: string }

/** The ten step states: the engine's own word, always shown, with a glyph named for the idea (an empty circle for not
 * started, a spinner for running, a clock, a person, a check, a slashed circle, a lock, an alert triangle, a struck line). */
export const STATES: Readonly<Record<StepState, StateLook>> = {
  "not started": { glyph: "circle-dashed", tone: "neutral", meaning: "Nothing has reached this step yet." },
  ready: { glyph: "arrow-right", tone: "neutral", meaning: "Its turn has come; the next read of the run or a person starts it." },
  running: { glyph: "refresh-cw", tone: "good", meaning: "Under way now." },
  waiting: { glyph: "clock", tone: "neutral", meaning: "Waiting for a clock, an arrival, an approval, or a child run." },
  "needs a person": { glyph: "user", tone: "warn", meaning: "Only a person can do this step." },
  done: { glyph: "circle-check", tone: "good", meaning: "Done, with its evidence." },
  skipped: { glyph: "ban", tone: "neutral", meaning: "Skipped by a person, with a reason." },
  blocked: { glyph: "lock", tone: "warn", meaning: "Cannot start: it waits on another step or a fact." },
  failed: { glyph: "triangle-alert", tone: "bad", meaning: "Failed. Nothing is retried by a click." },
  superseded: { glyph: "minus", tone: "neutral", meaning: "Replaced by a later step." },
};

export const isStepState = (s: string): s is StepState => Object.prototype.hasOwnProperty.call(STATES, s);

/** A step that still has work in it. */
export const OPEN_STEP_STATES: readonly string[] = ["ready", "running", "waiting", "needs a person", "failed"];
/** A step that is behind the run. */
export const SETTLED_STEP_STATES: readonly string[] = ["done", "skipped", "superseded"];

export const KIND_WORDS: Readonly<Record<StepKind, string>> = {
  check: "a check", job: "a job", plan: "a plan", person: "a person's step", decision: "a decision", wait: "a wait", branch: "a branch",
};

// -- what the loaders send --------------------------------------------------------------------------------------------------

export interface BasisInfo { basis: string; basisLabel: string; legal: boolean; proposed: boolean }

/** `_due`: the date to show for a run, whose it is, and how far off. */
export interface WorkDue extends BasisInfo {
  date: string; label: string; cite: string; status: string; days: number | null; step: string;
}

/** `_waiting_on`: whose move it is, in words. `kind` is one of open, paused, nothing, system, office, board, clock, arrival,
 * approval, run. */
export interface WaitingOn { kind: string; word: string; role?: string; detail?: string }

export interface RunAge { days: number | null; opened: string | null; idleDays: number | null; updated: string }

export interface RowCurrent { id: string; title: string; n: number; of: number; kind: string; state: string; role: string }

/** One row of the list (`_row`). No subject, no item, no name. A `held` row is a run of a held definition (a hearing, a
 * delinquent account, a records request) seen outside the private view: its `label` is the definition's general words
 * (`heldTitle`), its `handle` is the run id, and it opens only in the private view (`jason.web.extra.work_scope`). */
export interface WorkRow {
  id: string; definition: string; definitionTitle: string; family: string; subjectKind: string; label: string; state: string;
  group: GroupKey | "closed" | string; current: RowCurrent; owner: string; waitingOn: WaitingOn | null; mine: boolean;
  due: WorkDue | null; pastLaw: boolean; age: RunAge; paused: boolean; pausedReason: string; torn?: boolean; corrupt?: number | null;
  held?: boolean; handle?: string; visibility?: "board" | "admin" | "held" | string;
}

export interface WorkCounts {
  open: number; dueThisWeek: number; overdue: number; pastLegal: number; yours: number; others: number; clock: number; board: number;
}

export interface Problem { what: string; why: string }

/** `GET /api/work`. `counts` are the viewer's whole picture before the filters; `shown` is after them. */
export interface WorkPage {
  found: boolean; asOf: string; state: string; counts: WorkCounts; shown: number; runs: WorkRow[];
  groups: { key: GroupKey; title: string; count: number }[];
  definitions: { key: string; title: string; family: string }[]; roles: string[]; viewer: { roles: string[] };
  empty: string; caveats: string[]; problems: Problem[]; notComposed: Problem[];
}

export interface StepClock extends BasisInfo { slot: string; days: number | null; label: string; cite: string }

export interface StepEvidence { address: string; kept: string | null; now: string | null; changed: boolean; present: boolean }

/** A link the run holds, in the state its own store gives now. `id` is the address (a run id has no definition: see
 * `useRunDefinitions`). */
export interface RunLink {
  kind: string; id: string; step: string; label: string; state: string; read: boolean; screen?: string; problem?: string;
}

export interface StepChange { address: string; was: string | null; now: string | null }

export interface DecisionRead { recorded: boolean; motion: string; outcome: string; record: string; by: string; at: string; final: boolean; screen: string }
export interface PlanRead { approval: string | null; status: string; kind: string; screen: string }
export interface JobRead { job: string | null; state: string; name: string }

/** One step of a run (`compose_run`'s `steps[]`). `acts` is what the viewer may do now; `notOffered` says why not. */
export interface RunStep {
  id: string; n: number; of: number; title: string; kind: StepKind; role: string; state: StepState; reason: string;
  phase: string; phaseTitle: string; group: string; why: string; command: string; sop: string; legal: boolean;
  needsRecord: string; record: string; by: string; at: string; current: boolean; blockedBy: string[];
  items: { item: string; state: string }[]; choice: string; choices: string[]; spawns: string | null;
  skip: { roles: string[]; reasonRequired: boolean } | null; clock: StepClock | null;
  /** Every role that may act on the step (`role` is the primary); the not-applicable outcome the definition declares, and
   * whether the step is recorded as one; the child runs spawned from the step and whether it waits for them. */
  roles?: string[]; na?: boolean; naOutcome?: { roles: string[]; reasonRequired: boolean; recordRequired: boolean } | null;
  children?: string[]; waitsOnChild?: boolean;
  /** Item sets (engine round three), present only where they apply: the step repeats over items (`perItem`), uses the item-set
   * rules and names its set (`itemAware`, `itemSet`; "" is the run's own items), counts of its items by state, the step that
   * remedies this failed check (`remedy`), and the failed check this step is the remedy for (`remedyOf`). */
  perItem?: boolean; itemAware?: boolean; itemSet?: string; itemCounts?: Record<string, number>; remedy?: string; remedyOf?: string;
  evidence: StepEvidence[]; links: RunLink[]; changed: StepChange[]; waitingOn: WaitingOn | null; yours: boolean;
  acts: string[]; notOffered: Record<string, string>;
  decision?: DecisionRead; plan?: PlanRead; job?: JobRead;
  /** The gates adopted controls add to this step: present only where a control bites, and only when controls are configured. */
  controls?: StepControl[];
  /** A person step's enable state, nudge, and guide (a check, a job, and a plan have none; a held run outside the private view has none). */
  enable?: StepEnable; nudge?: StepNudge; guide?: StepGuide;
}

// -- the step guide: enable, nudge, guide (docs/console/screens/work-guide.md; `jason.web.extra.work_guide`) ------------------

/** The first of the ten enable states that applies (docs/workflows/person-steps.md, section 5.2); `closed` is a run that is done or
 * cancelled, kept with the paused and draft ones. */
export type EnableState =
  | "ready" | "not yours" | "not ready" | "needs an integration" | "needs a second person" | "terminal only" | "viewing as"
  | "draft" | "paused" | "closed" | "done" | "skipped" | "not applicable" | "superseded";

export interface HolderBackup { office: string; names: string[]; basis: string }
/** An office that may act on the step, who holds it on the roster, whether it is vacant, and a backup (the profile's, or the
 * proposal labeled so). Names only: never a phone or an email. */
export interface Holder { office: string; names: string[]; vacant: boolean; owner?: boolean; backup?: HolderBackup }
export interface EnableMissing { what: string; why: string; fix: string }

export interface StepEnable {
  state: EnableState; word: string; detail?: string; holders: Holder[]; missing: EnableMissing[]; secondPerson: boolean; terminalOnly: boolean;
  youHold: string[]; owner: string; inHand: string[]; accessNote: string; firstBy?: string; record?: string;
  waitsOn?: { id: string; n: number; title: string };
}

export type NudgeBand = "legal" | "late" | "date" | "soon" | "stale" | "quiet";

export interface StepNudge {
  band: NudgeBand; word: string; due: string | null; days: number | null; basis: string; basisLabel: string; legal: boolean; proposed: boolean;
  label: string; cite: string; openDays: number | null; escalatedTo: string | null; escalatedWhy: string; snoozable: boolean;
  items: { total: number; notDone: number; earliest: string } | null;
  numbers: { leadDays: number; afterHours: number; escalateAfterHours: number; adopted: boolean; note: string };
  claim: { by: string; at: string; stale: boolean; mine: boolean } | null;
}

/** One look-at read: a count (null when it could not read, then `unavailable` says why), at most five handles, and the screen it lives on. */
export interface GuideLook {
  label: string; kind: "read" | "evidence"; read: string; count: number | null; of?: number; rows: string[]; refs: string[]; asOf: string;
  unavailable: string; screen?: { key: string; name: string; href: string };
}

/** A cite recited from what is stored: the words whole, the version, jason's reading (labeled), or why the words are not here. */
export interface GuideRule {
  key: string; kind: "statute" | "document"; words: string; version: string; source: string; reading: string; readingLabel: string;
  missing: string; caveats: string[]; restatement: string; command: string; versions: { digest: string; words: string; label: string }[];
}

export interface GuideCommand { text: string; raw: string; note: string; terminalOnly: boolean; fillIn: string[] }
export interface GuideAsk { office: string; names: string[]; vacant: boolean }

export interface StepGuide {
  authored: string[]; instruction: string; why: string; lookAt: GuideLook[]; rule: GuideRule[];
  checklist: { text: string; required: boolean }[]; requiredChecks: number; commands: GuideCommand[]; doneWhen: string; record: string;
  blocked: string; notApplicable: string; naOffered: boolean; skippable: boolean; ask: GuideAsk[];
  lessons: { key: string; status: string }[]; sop: { address: string; key: string; index: number; command: string } | null;
  inHand: string[]; accessNote: string; integrations: string[]; secondPerson: boolean; terminalOnly: boolean;
}

/** The statute's words as the authorities shelf holds them (`_recite`), and jason's reading of the clock, labeled. */
export interface LawWords {
  citation: string; section: string; words: string; digest: string; source: string; note: string; caveats: string[];
  versions: { digest: string; words: string; label: string }[]; undecided: boolean; missing: string;
  readingLabel: string; restatement: string; reading?: string;
}

/** One deadline on the run (`_clock_row`), with the law's words where its basis is the law. */
export interface RunClock extends BasisInfo {
  key: string; step: string; label: string; due: string | null; status: string; days: number | null; cite: string;
  past: boolean; stepTitle: string; scope: "step" | "run" | string; law?: LawWords;
  /** A per-item clock: the item it is for (an opaque id). A clock on a step or the whole run has none. */
  item?: string;
}

export interface HistoryEvent {
  n: number; kind: string; step: string; stepTitle: string; by: string; at: string; text: string;
  detail: Record<string, unknown>; pending: boolean;
}

export interface ChangedRow { step: string; stepTitle: string; n: number; address: string; was: string | null; now: string | null; at: string | null; pending: boolean }

export interface RunAct { offered: boolean; why: string; needsYes?: boolean; legal?: boolean; slots?: string[] }

/** An item set some step repeats over (`""` is the run's own items): how many it holds and the steps over it. A count and
 * titles; the ids are in the step's own table. */
export interface RunItemSet { name: string; label: string; count: number; steps: string[] }

/** A step group as the fold reads it (`GroupView`): titled, rolled up, and expanded where it holds the current or a failed step. */
export interface RunGroup { key: string; title: string; steps: string[]; state: string; done: number; total: number; expanded: boolean; current: string }

/** One date slot of a run: its day, who set it after the start, and whether a person may set it now (`set-date`). */
export interface RunDateSlot {
  name: string; label: string; value: string | null; required: boolean; late: boolean; settable: boolean; correction: boolean;
  timing: string; sets: number; setBy: string | null; setAt: string | null; record: string | null; after: string; roles: string[];
}

export interface Run {
  id: string; definition: string; definitionTitle: string; family: string; label: string; subject: string; subjectKind: string;
  handle?: string; due?: WorkDue | null;
  state: RunState | string; n: number; updated: string; opened: string; openedBy: string; dates: Record<string, string>;
  itemCount: number; itemTotal?: number; itemSets?: RunItemSet[]; parent: string | null; children: string[]; pausedReason: string; cancelledReason: string;
  torn: boolean; corrupt: number | null; orphans: string[]; pastLaw: string[]; age: RunAge;
  current: { id: string; title: string; n: number; of: number } | null;
  acts: { open: RunAct; pause: RunAct; resume: RunAct; note: RunAct; cancel: RunAct; setDate?: RunAct; supplyItems?: RunAct & { sets?: RunItemSet[] } };
  dateSlots?: RunDateSlot[]; openSlots?: string[];
  cancelWill: { openSteps: string[]; childRuns: string[] };
}

/** `GET /api/work-run`. `held` is a held run outside the private view (`held_page`): the same shape with nothing in it but the
 * state, the general title, and the date and its basis word; `heldWhy` says where it opens. */
export interface RunPage {
  found: boolean; asOf: string; caveats: string[]; run: Run; held?: boolean; heldTitle?: string; heldWhy?: string; phases: { key: string; title: string; steps: string[] }[];
  /** The step groups, only when the definition has some (`RunView.groups`). */
  groups?: RunGroup[];
  steps: RunStep[]; clocks: RunClock[]; links: RunLink[]; history: HistoryEvent[]; changed: ChangedRow[];
  pending: { kind: string; step: string; stepTitle: string }[]; viewer: { roles: string[] }; problems: Problem[]; notComposed: Problem[];
}

export interface DefinitionDate {
  name: string; label: string; required: boolean; after: string; rule?: string; late?: boolean; settable?: boolean; timing?: string;
}

/** A row of the catalog (`_definition_row`). */
export interface DefinitionRow {
  key: string; title: string; family: string; subjectKind: string; steps: number;
  phases: { key: string; title: string; steps: number }[]; dates: DefinitionDate[]; legalClock: boolean; procedure: string;
  procedureSteps: number | null; drift: { ok: boolean; why: string[] }; cadence: string; startable: boolean; startedBy: string[];
  needsYes: boolean; roles: string[]; mySteps: boolean; lessons: { key: string; status: string }[];
  /** `held`: a held definition (it starts only in the private view); `startableWhy` says why `startable` is false. */
  held?: boolean; heldTitle?: string; visibility?: "board" | "admin" | "held" | string; startableWhy?: string;
}

export interface DefinitionClock extends BasisInfo { slot: string; days: number | null; label: string; cite: string; law?: LawWords }
export interface DefinitionStep {
  id: string; n: number; title: string; kind: StepKind; role: string; needs: string[]; why: string; command: string; plan: string;
  job: string; evidence: string[]; record: string; legal: boolean; repeat: string; spawns: string | null; sop: string;
  roles?: string[]; naOutcome?: { roles: string[]; reasonRequired: boolean; recordRequired: boolean } | null; waitsOnChild?: boolean;
  skip: { roles: string[]; reasonRequired: boolean } | null; clock: DefinitionClock | null; phase: string; group: string;
  /** The guidance a person wrote for the step, in words ("instruction, rule, checklist, look-at"), "derived" when none, "" for jason's own steps. */
  guidance?: string;
}
/** `definition` of `?key=`: the row, read whole. The page's `steps` replace the row's count (the loader merges the two). */
export interface DefinitionPageData extends Omit<DefinitionRow, "steps"> { clocks: DefinitionClock[]; steps: DefinitionStep[] }

/** `GET /api/work-definitions`. */
export interface DefinitionsPage {
  found: boolean; asOf: string; counts: { definitions: number; shown: number; families: number; drifted: number };
  families: { family: string; definitions: DefinitionRow[] }[]; definitions: DefinitionRow[]; empty: string;
  viewer: { roles: string[] }; roles: string[]; caveats: string[]; problems: Problem[]; notComposed: Problem[];
  definition?: DefinitionPageData;
}

/** What a write answers: the event, what an `open` appended, and the run page as it now reads. */
export interface ActAnswer { ok: boolean; act: string; by: string; event: HistoryEvent | null; appended: HistoryEvent[]; run: RunPage }
export interface StartDry { ok: boolean; dryRun: true; definition: string; problems: string[] }
export interface StartAnswer { ok: boolean; act: "start"; by: string; id: string; definition: string; run: RunPage }

// -- routes -----------------------------------------------------------------------------------------------------------------

export const WORK_HREF = "#/work";
export const DEFINITIONS_HREF = "#/work/definitions";
export const START_HREF = "#/work/start";

/** A run's address: `#/work/<definition>/<id>`. */
export const runHref = (definition: string, id: string) => `#/work/${encodeURIComponent(definition)}/${encodeURIComponent(id)}`;
export const definitionHref = (key: string) => `${DEFINITIONS_HREF}?key=${encodeURIComponent(key)}`;
export const startHref = (key = "") => `${START_HREF}${key ? `?definition=${encodeURIComponent(key)}` : ""}`;
/** The list of the viewer's own runs (the Today band's "All your runs"). */
export const MINE_HREF = `${WORK_HREF}?mine=1`;

export type WorkRoute =
  | { page: "list"; filters: WorkFilters }
  | { page: "run"; definition: string; id: string }
  | { page: "definitions"; key: string }
  | { page: "start"; definition: string };

export interface WorkFilters { definition: string; role: string; due: string; state: string; mine: boolean; q: string }
export const NO_FILTERS: WorkFilters = { definition: "", role: "", due: "", state: "", mine: false, q: "" };

const safeDecode = (s: string) => { try { return decodeURIComponent(s); } catch { return s; } };

/** The screen a hash names: `work` (the list, with its filters in the query), `work/definitions[?key=]`, `work/start[?definition=]`,
 * `work/<definition>/<id>`. The path carries ids and keys, never a name. */
export function parseRoute(hash: string): WorkRoute {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const q = new URLSearchParams(query);
  const parts = path.split("/").filter(Boolean).map(safeDecode);
  const rest = parts[0] === "work" ? parts.slice(1) : parts;
  if (rest.length >= 2 && rest[0] !== "definitions") return { page: "run", definition: rest[0], id: rest[1] };
  if (rest[0] === "definitions") return { page: "definitions", key: q.get("key") ?? "" };
  if (rest[0] === "start") return { page: "start", definition: q.get("definition") ?? "" };
  return {
    page: "list",
    filters: {
      definition: q.get("definition") ?? "", role: q.get("role") ?? "", due: q.get("due") ?? "", state: q.get("state") ?? "",
      mine: ["1", "true", "yes"].includes((q.get("mine") ?? "").toLowerCase()), q: q.get("q") ?? "",
    },
  };
}

export function workUrl(f: Partial<WorkFilters> = {}): string {
  const q = new URLSearchParams();
  if (f.definition) q.set("definition", f.definition);
  if (f.role) q.set("role", f.role);
  if (f.due) q.set("due", f.due);
  if (f.state) q.set("state", f.state);
  if (f.mine) q.set("mine", "1");
  if (f.q?.trim()) q.set("q", f.q.trim());
  const s = q.toString();
  return `/api/work${s ? `?${s}` : ""}`;
}
export const workRunUrl = (definition: string, id: string) =>
  `/api/work-run?definition=${encodeURIComponent(definition)}&id=${encodeURIComponent(id)}`;
export function workDefinitionsUrl(f: { family?: string; role?: string; mine?: boolean; q?: string; key?: string } = {}): string {
  const q = new URLSearchParams();
  if (f.family) q.set("family", f.family);
  if (f.role) q.set("role", f.role);
  if (f.mine) q.set("mine", "1");
  if (f.q?.trim()) q.set("q", f.q.trim());
  if (f.key) q.set("key", f.key);
  const s = q.toString();
  return `/api/work-definitions${s ? `?${s}` : ""}`;
}
/** The one write route of a run; the signed-in person's name goes on the record, so the body never carries a `by`. */
export const writeUrl = (definition: string, id: string) =>
  `/api/write/work/${encodeURIComponent(definition)}/${encodeURIComponent(id)}`;
export const startUrl = (definition: string) => `/api/write/work/${encodeURIComponent(definition)}/start`;

// -- small rules ------------------------------------------------------------------------------------------------------------

/** What a held run says in place of its details (the server sends its own sentence on a held page; this is for a row). */
export const HELD_WORDS = "Open the private view to see this run.";

/** The first ten characters of a day: `2099-10-23T08:12:00Z` is `2099-10-23`. */
export const dayOf = (iso: string | null | undefined) => (iso ? iso.slice(0, 10) : "");

/** `today` for `DueDate`, from the loader's `asOf`, so a date reads against the day the loader read. */
export function asOfDate(asOf: string | undefined): Date | undefined {
  if (!asOf || !/^\d{4}-\d{2}-\d{2}/.test(asOf)) return undefined;
  const d = new Date(`${asOf.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? undefined : d;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The heading line of the list, from the loader's counts: "14 open runs · 3 are yours · 2 are due this week · 1 is past a
 * legal date". "Past a legal date" is the loader's count of the law's own dates; it is not computed here. */
export function headingLine(c: WorkCounts): string {
  const be = (n: number) => (n === 1 ? "is" : "are");
  const parts = [plural(c.open, "open run"), `${c.yours} ${be(c.yours)} yours`, `${c.dueThisWeek} ${be(c.dueThisWeek)} due this week`];
  parts.push(c.pastLegal === 1 ? "1 is past a legal date" : `${c.pastLegal} ${be(c.pastLegal)} past a legal date`);
  return parts.join(" · ");
}

/** A hash or digest, shortened to twelve characters for reading. */
export const shortHash = (h: unknown): string => {
  const s = String(h ?? "");
  return s ? (s.length > 12 ? `${s.slice(0, 12)}…` : s) : "nothing";
};

/** An address safe to show: the server already refuses a path outside the data folder; a drive-lettered or rooted path
 * that reached the page anyway is not drawn. */
export function safeAddress(address: string): string {
  const body = address.includes(":") && address.indexOf(":") > 1 ? address.slice(address.indexOf(":") + 1) : address;
  return /^(?:[A-Za-z]:)?[\\/]/.test(body) || /(?:^|[\\/])\.\.(?:[\\/]|$)/.test(body) ? "(a path outside the data folder)" : address;
}

/** Contact details never reach the page from the server (it masks them); this is a second guard for a sentence the page
 * draws: an email becomes [email] and a phone number [phone]. */
export function maskContact(text: string): string {
  return text
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "[email]")
    .replace(/(?<![\w-])(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\w)/g, "[phone]");
}

/** Whose move a step is, as one phrase: "Waiting on the treasurer" for a step the viewer does not hold. */
export function waitingWords(w: WaitingOn | null | undefined): string {
  if (!w) return "";
  return `Waiting on ${w.word}${w.detail ? ` (${w.detail})` : ""}`;
}

/** The refusal sentences a step shows in place of a control it does not offer: only the acts that make sense for its kind
 * and state (a wait is "arrived", a settled step may be reopened), each the server's own words. */
export function refusalsFor(step: RunStep): { act: string; why: string }[] {
  const relevant = new Set<string>(["skip"]);
  if (step.kind === "person" || step.kind === "branch" || step.kind === "decision" || step.kind === "plan") relevant.add("attest");
  if (step.kind === "wait") relevant.add("arrived");
  if (["done", "skipped", "failed"].includes(step.state)) relevant.add("reopen");
  return Object.entries(step.notOffered ?? {})
    .filter(([act]) => relevant.has(act) && !step.acts.includes(act))
    .map(([act, why]) => ({ act, why }));
}

/** The phases of a run for the rail: the definition's own order, a step without a phase under "Other steps"; within a phase,
 * consecutive steps of one group are one block under the group's prefix. */
export interface RailPhase { key: string; title: string; steps: RunStep[]; blocks: { group: string; steps: RunStep[] }[] }
export function railPhases(page: Pick<RunPage, "phases" | "steps">): RailPhase[] {
  const out: RailPhase[] = [];
  const at = new Map<string, RailPhase>();
  for (const p of page.phases) {
    const row: RailPhase = { key: p.key, title: p.title, steps: [], blocks: [] };
    at.set(p.key, row);
    out.push(row);
  }
  for (const s of page.steps) {
    let row = at.get(s.phase);
    if (!row) {
      row = { key: s.phase || "other", title: s.phaseTitle || "Other steps", steps: [], blocks: [] };
      at.set(row.key, row);
      out.push(row);
    }
    row.steps.push(s);
    const last = row.blocks[row.blocks.length - 1];
    if (last && last.group === s.group) last.steps.push(s);
    else row.blocks.push({ group: s.group, steps: [s] });
  }
  return out.filter((p) => p.steps.length);
}

/** The step a run page opens on: the loader's current step, else the first step with work in it, else the first. */
export function openingStep(page: Pick<RunPage, "steps" | "run">): string {
  const cur = page.run.current?.id;
  if (cur && page.steps.some((s) => s.id === cur)) return cur;
  return (page.steps.find((s) => OPEN_STEP_STATES.includes(s.state)) ?? page.steps[0])?.id ?? "";
}

/** Whether the run is past a legal date: the loader's list of the clocks it found past, else a legal clock marked past. */
export const pastLegal = (page: Pick<RunPage, "run" | "clocks">): boolean =>
  page.run.pastLaw.length > 0 || page.clocks.some((c) => c.legal && c.past);

// -- items, in words --------------------------------------------------------------------------------------------------------

const days = (n: number) => `${n} ${n === 1 ? "day" : "days"}`;

/** A per-item clock in words, never by colour: "late by 3 days", "due today", "due in 5 days", "no date yet". `late` is true only
 * for a clock the engine reads as overdue. An item that has no clock reads "no clock". */
export function clockWords(c: Pick<RunClock, "status" | "days"> | null | undefined): { text: string; late: boolean } {
  if (!c) return { text: "no clock", late: false };
  const n = c.days === null || c.days === undefined ? null : Math.abs(c.days);
  switch (c.status) {
    case "overdue": return { text: n === null ? "late" : `late by ${days(n)}`, late: true };
    case "due": return { text: "due today", late: false };
    case "upcoming": return { text: n === null ? "upcoming" : `due in ${days(n)}`, late: false };
    case "satisfied": return { text: "met", late: false };
    case "undated": return { text: "no date yet", late: false };
    case "not running": return { text: "not running yet", late: false };
    default: return { text: c.status || "no clock", late: false };
  }
}

/** One row of a step's item table: the item, its state, its own clock (the loader's `step[item]` clock), and the clock in words. */
export interface ItemRow { item: string; state: string; clock: RunClock | null; words: string; late: boolean }

export function itemRows(step: Pick<RunStep, "id" | "items">, clocks: readonly RunClock[]): ItemRow[] {
  const own = new Map(clocks.filter((c) => c.item && c.step === step.id).map((c) => [c.item as string, c]));
  return step.items.map((i) => {
    const clock = own.get(i.item) ?? null;
    const w = clockWords(clock);
    return { item: i.item, state: i.state, clock, words: w.text, late: w.late };
  });
}

/** "3 of 12 done, 2 late": the items finished of all of them, then the ones the engine reads as late, failed, and skipped. */
export function itemRollUp(rows: readonly ItemRow[]): string {
  const n = (f: (r: ItemRow) => boolean) => rows.filter(f).length;
  const parts = [`${n((r) => r.state === "done")} of ${rows.length} done`];
  const late = n((r) => r.late), failed = n((r) => r.state === "failed"), skipped = n((r) => r.state === "skipped");
  if (late) parts.push(`${late} late`);
  if (failed) parts.push(`${failed} failed`);
  if (skipped) parts.push(`${skipped} skipped`);
  return parts.join(", ");
}

/** The ids typed one to a line: blank lines dropped, each id once, in the order typed. An id is not checked here; the server
 * refuses a name or an address in its own words (the check button asks it). */
export function parseItemLines(text: string): string[] {
  return [...new Set(text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean))];
}

/** The words for an item set: "the set requests", or "the run's own items" for the set named "". */
export const setWords = (name: string | undefined) => (name ? `the set ${name}` : "the run's own items");

// -- reading ----------------------------------------------------------------------------------------------------------------

export type WorkRemote<T> =
  | { status: "loading" }
  | { status: "error"; error: string; code?: number; signIn?: string }
  | { status: "ready"; data: T; refreshing: boolean };

/** A read that keeps what it last showed while it reads again (a filter changed, an act recorded), so the page does not blank
 * and a status line is not lost. An error drops the data. A 401 or 403 keeps `code` (and a 401 the sign-in link), so the
 * page says it in the server's own sentence. */
export function useWorkApi<T>(path: string): WorkRemote<T> & { reload: () => void } {
  const [state, setState] = useState<WorkRemote<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  const last = useRef("");
  useEffect(() => {
    const ctl = new AbortController();
    const same = last.current === path;
    last.current = path;
    setState((s) => (s.status === "ready" && same ? { ...s, refreshing: true } : { status: "loading" }));
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

/** Who is reading, from the server's session (asked once): the name a write goes under, and, for an administrator viewing as
 * someone else, whom (every write is refused then; the page says so in place of the control). */
export interface WorkViewer { known: boolean; name: string; actingAs: string }
export function useWorkViewer(): WorkViewer {
  const [v, setV] = useState<WorkViewer>({ known: false, name: "", actingAs: "" });
  useEffect(() => {
    let on = true;
    serverSession().then((s) => {
      if (on) setV({ known: true, name: s.signedIn?.name ?? "", actingAs: s.acting?.name || s.acting?.role || "" });
    });
    return () => { on = false; };
  }, []);
  return v;
}

/** The definition of each run id the page names (a child, a parent). A run link carries the run's id only, and the run's
 * address needs its definition, so one read of every run (`state=all`, which carries both) maps them. Nothing is read
 * while `ids` is empty. */
export function useRunDefinitions(ids: readonly string[]): Record<string, string> {
  const [map, setMap] = useState<Record<string, string>>({});
  const key = [...ids].sort().join("|");
  useEffect(() => {
    if (!key) return;
    const ctl = new AbortController();
    getJson<WorkPage>("/api/work?state=all", ctl.signal).then(
      (p) => setMap(Object.fromEntries((p.runs ?? []).map((r) => [r.id, r.definition]))),
      () => { /* an unreadable list leaves the child as text with its state */ },
    );
    return () => ctl.abort();
  }, [key]);
  return map;
}

// -- writing ----------------------------------------------------------------------------------------------------------------

/** The body of an act on a run. There is no `by`: the server records the signed-in person, and refuses a body that names
 * another. `expect` is the `n` the page last read, so a run that moved on is refused (409) and not overwritten. */
export interface ActBody {
  act: "attest" | "arrived" | "skip" | "reopen" | "pause" | "resume" | "note" | "cancel" | "open" | "supply-items" | "claim";
  step?: string; record?: string; reason?: string; text?: string; choice?: string; what?: string; yes?: boolean; expect?: number;
  /** `claim`: let the step go (only the person who claimed it). */
  release?: boolean;
  /** `supply-items`: the item set ("" is the run's own) and the ids; `dryRun` checks them and writes nothing. */
  set?: string; items?: string[]; dryRun?: boolean;
}

/** What `supply-items` with `dryRun` answers: the ids that would be added and those already in the set. */
export interface SupplyDry { ok: boolean; act: string; dryRun: true; set: string; wouldAdd: string[]; alreadyThere: string[]; withDates: string[]; text: string; record: string; n: number }
export const postSupplyDry = (definition: string, id: string, body: Pick<ActBody, "set" | "items" | "record">) =>
  postJson<SupplyDry>(writeUrl(definition, id), { act: "supply-items", dryRun: true, ...body });

export const postAct = (definition: string, id: string, body: ActBody) => postJson<ActAnswer>(writeUrl(definition, id), body);

export interface StartBody { definition: string; subject: string; label: string; dates: Record<string, string>; yes?: boolean; dryRun?: boolean }
export const postStart = <T extends StartDry | StartAnswer>(body: StartBody) => postJson<T>(startUrl(body.definition), body);

/** A refusal in the server's own words, with the sign-in link for a 401. */
export function refusalOf(e: unknown): { text: string; signIn?: string; status?: number } {
  const status = e instanceof ApiError ? e.status : undefined;
  const asked = signInRefusal(e);
  return { text: e instanceof Error ? e.message : String(e), signIn: asked?.href, status };
}
