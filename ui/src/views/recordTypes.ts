import type { Tone } from "../components";
import type { GlyphName } from "../components/Glyph";

/** The shapes of the record checklist's loaders and acts (`jason.web.extra.record_slots`, `jason.web.extra.drive_choose`).
 * Nothing is worked out in the page: every state, count, verdict, and refusal arrives from the server in words. */

export type Cardinality = "one" | "several" | "series";

/** One row of `GET /api/record-slots`. */
export interface SlotRow {
  key: string; title: string; group: string; requires: string[]; cardinality: Cardinality;
  state: string; stateWord: string; held: number; cells: number; periods: { period: string; state: string }[];
  confidential: boolean; hidden: string; source: string; gate: string; kinds: string[]; pins: number; candidates: number;
  collision: boolean; problem: string; waitsOn: string[]; closed: boolean; bindings: number;
}
export interface SlotGroup {
  key: string; title: string; law: string; opensGate: string;
  counts: { total: number; held: number; answered: number }; slots: SlotRow[];
}
export interface SlotsPage {
  found?: boolean; note?: string; asOf: string; profile: string; driveConnected: boolean | null;
  driveCatalog?: { syncedAt?: string | null; files: number };
  counts: { total: number; byState: Record<string, number>; held: number; hidden: number };
  states: { value: string; word: string; meaning: string }[];
  groups: SlotGroup[];
  biggestUnknowns: { key: string; title: string; why: string; blocks: string[] }[];
  notes?: string[]; caveats: string[];
}

export interface Fit { key: string; title: string; held?: boolean; current?: boolean }
export interface Segment {
  segment: string; pages: [number, number]; title?: string; kind: string | null; tier: string; readers: string[]; date?: string;
  slots: Fit[]; confirmed: boolean; confirmedBy?: string;
}
export interface Preflight {
  pages: number; blank?: number; marked?: number; content?: number; withText?: number; suspectShare?: number | null; locked?: boolean;
  note?: string; recommend: { action: string; pages: string; reason: string }[];
}
export interface Readback {
  readAt: string; readBy: string; sha256: string; size: number | null; type: string; readers: Record<string, string | null>;
  method: string; tier: string; readsAs: string | null; text: { source?: string; chars?: number };
  alreadyFiled: boolean; preflight: Preflight | null;
  segments: { documents: number; pageCount?: number; proposes: boolean; proposal: Segment[]; note?: string } | null;
  findings: { code: string; text: string }[];
  changed: { at?: string; from?: string; to?: string; diff?: { fact: string; before: unknown; after: unknown }[] } | null;
  acknowledged?: { by?: string; at?: string } | string | null;
  split: { parts: number; confirmed: { segment: string; slot: string; by: string; at: string }[]; declined: { by: string; at: string } | null | false; open: boolean } | null;
  history: { at: string; sha256: string }[]; held: boolean;
}
export interface WrongSlot { readsAs: string; expects: string[]; fits: Fit[]; acts: string[] }
export interface Holder {
  pin: string; origin: string; source: string; kind: string; name: string; ref: string; period: string; by: string; at: string; note: string;
  state: string; stateWord: string; held: boolean; opens: string;
  reading: { found: boolean; readsAs: string | null; readers: string[]; tier: string | null; read: boolean; confirmedBy: string; confirmedAt: string };
  problem: string; wrongSlot: WrongSlot | null; readback?: Readback; changed?: Readback["changed"];
  kept?: { by: string; at: string; reason: string; readsAs: string };
}
export interface Standing {
  pinned: number; read: number;
  duties: { anchor: string; keeps: string; cadence: string; when: string; sections: string; produce: string; because: string; command: string }[];
  conflicts: { count: number; open: number; held: boolean; items: { key: string; provision: string; authority: string; status: string; clarity: string; open: boolean; boardItem: string; because: string }[] };
  programs: { available: boolean; items: unknown[]; why: string };
  caveats: string[];
}
export interface SlotAnswer { id: string; answer: string; word: string; by: string; at: string; reason: string; who: string; source: string; held: boolean }
export interface SlotPageData extends Omit<SlotRow, "candidates" | "bindings"> {
  found?: boolean; note?: string; reason?: string; why: string; existence: { possible: boolean; answer: SlotAnswer | null };
  shelf: string[]; record: string; delivery: string; holders: Holder[];
  bindings: { id: string; name: string; by: string; at: string }[];
  more: { id: string; answer: string; by: string; at: string; complete: boolean } | null;
  specificationFolders: { pin: string; folder: string; source: string }[]; holding: string | null;
  collisions: { slot: string; period?: string; note: string; holders: { pin: string; origin: string; source: string; kind?: string; by: string; at: string }[] }[];
  candidates: { ref: string; name: string; kind: string; why: string }[];
  standing: Standing;
  acts: { pickFile: boolean; answer: boolean; unpin: boolean; pickFolder: boolean; read: boolean; keep: boolean; repin: boolean; more: boolean; reopen: boolean; upload: boolean; replace: boolean; split: boolean; ack: boolean; why: string };
  log: { at?: string; by?: string; act?: string; pin?: string; slot?: string; [k: string]: unknown }[];
  commands: Record<string, string>; caveats: string[];
}

/** What a Drive loader or POST answers (`jason.tasks.drive_choose`). */
export interface DriveItem {
  id: string; name: string; type: string; mime?: string; size: number | null; modified: string; parents?: string[]; owner: string;
  sharedDrive: boolean; readable: boolean; why: string; held: boolean; opens: string; doc: string;
  jason: { inLibrary?: string; kind?: string; ruleCovers?: boolean; pinnedFor?: string[] };
}
export interface DriveListing {
  found: boolean; driveConnected?: boolean; why?: string; command?: string; account?: string;
  parent?: { name: string; path: { name: string }[] }; items?: DriveItem[]; drives?: { name: string; id: string; type: string }[];
  empty?: string; next?: string | null; caveats?: string[];
}
export interface DriveResolved extends Partial<DriveItem> {
  found: boolean; driveConnected?: boolean; why?: string; command?: string; kind?: "file" | "folder"; ownerDomain?: string; offer?: string; account?: string;
}

/** What a dry run or a confirmed act answers. Fields are read as the server sends them; any may be missing. */
export interface PartPlan { segment: string; pages: [number, number]; slot: string; period?: string; entry?: string; kind?: string | null; fits?: boolean; action: string; why?: string; kept?: string }
export interface ReadPlan { pin: string; slot: string; ok?: boolean; problem?: string; plan?: { name: string; type?: string; size: number | null; export?: string; willFetch: boolean }; reads?: string; note?: string; unchanged?: boolean }
export interface Plan {
  ok?: boolean; dryRun?: boolean; act?: string; key?: string; note?: string; would?: Record<string, unknown>;
  already?: boolean; twin?: string; alsoIn?: string[]; parts?: PartPlan[]; reads?: ReadPlan[];
  first?: { would?: Record<string, unknown>; note?: string }; then?: { would?: Record<string, unknown>; note?: string };
  proposal?: { kind?: string; record?: string; text?: string; note?: string } | Segment[] | null;
  job?: number; queued?: boolean; command?: string; pin?: string; replaced?: string; partial?: boolean; why?: string;
  filled?: unknown[]; notQueued?: unknown[]; declined?: boolean; caveats?: string[]; written?: string;
}

export interface JobState { found?: boolean; job?: { id: number; status: string; summary?: string | null; note?: string | null }; log?: string[] }

/** The look of each state word: a tone, a glyph, and the server's own word. The glyph and tone only repeat the word. */
export const STATE_LOOK: Record<string, { tone: Tone; glyph: GlyphName }> = {
  empty: { tone: "neutral", glyph: "circle-dashed" },
  picked: { tone: "neutral", glyph: "link" },
  uploaded: { tone: "neutral", glyph: "upload" },
  classified: { tone: "neutral", glyph: "file-search" },
  read: { tone: "good", glyph: "file-check" },
  confirmed: { tone: "good", glyph: "shield-check" },
  notApplicable: { tone: "neutral", glyph: "ban" },
  doesNotExist: { tone: "warn", glyph: "circle-x" },
  held: { tone: "neutral", glyph: "lock" },
  waiting: { tone: "warn", glyph: "hourglass" },
  problem: { tone: "bad", glyph: "triangle-alert" },
};

export const LIST_ROUTE = "#/setup/records";
export const slotRoute = (key: string) => `${LIST_ROUTE}/${encodeURIComponent(key)}`;

/** What the hash names: the checklist (`key` empty) or one slot. The slot key is URL-encoded, and a key with unencoded
 * slashes is accepted too. A file's name or id is never in a route. */
export function parseRoute(hash: string): { key: string; query: URLSearchParams } {
  const [path, q = ""] = hash.replace(/^#?\/?/, "").split("?");
  const parts = path.split("/");
  const rest = parts[0] === "setup" && parts[1] === "records" ? parts.slice(2).join("/") : "";
  let key = rest;
  try { key = decodeURIComponent(rest); } catch { /* a stray percent sign: the key as written */ }
  return { key, query: new URLSearchParams(q) };
}

export function sizeWords(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "size unknown";
  if (n < 1024) return `${n} bytes`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(n < 10 * 1024 ** 2 ? 1 : 0)} MB`;
  return `${(n / 1024 ** 3).toFixed(1)} GB`;
}

export function words(s: string): string {
  return s.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").toLowerCase();
}

export const CARDINALITY: Record<Cardinality, string> = { one: "one", several: "several (a set that grows)", series: "a series (one for each period)" };

/** The states in the order the checklist counts them. */
export const STATE_ORDER = ["empty", "picked", "uploaded", "classified", "read", "confirmed", "notApplicable", "doesNotExist", "waiting", "problem"] as const;
