/** Documents that point elsewhere, report portals, program notices, and the life-safety watchlist
 * (docs/console/handoff-inspections-and-portals.md). The data shapes the loaders return, the fixed word tables (each
 * word with its meaning, shown on focus and hover), and small pure helpers. Nothing here fetches, and nothing here
 * decides: a clock never picks a date, a source never wins, "unknown" is never "not done". */
import type { GlyphName } from "../components/Glyph";
import type { DocRef, EvidenceEntry } from "./docref";

export type DocRefData = DocRef;

// --- a document's codes ---------------------------------------------------------------------------------------------

export interface DocumentCode {
  /** The payload; a secret value is already "***" when the server masked it. */
  text: string;
  format: "QR Code" | "MicroQRCode";
  page: number;
  link: boolean;
  /** "reports.example.com", or "". */
  host: string;
  /** True when the server hid a secret in `text`. */
  masked: boolean;
  portal?: { platform: "firenspec"; host: string; key: string };
  meeting?: { platform: "zoom"; host: string; id: string; recorded: boolean };
}

export type CodeKind = "meeting" | "portal" | "link" | "text";

/** What a code is, from the server's own fields. A meeting or a portal is still a link; a payload that is not a link is text. */
export function codeKind(c: DocumentCode): CodeKind {
  if (c.meeting) return "meeting";
  if (c.portal) return "portal";
  return c.link ? "link" : "text";
}

/** The host a link points at: the server's `host`, else the one the code's portal or meeting names, else "". */
export function codeHost(c: DocumentCode): string {
  return c.host || c.portal?.host || c.meeting?.host || "";
}

export const DECODER_MISSING = "Codes are not read: the decoder is not installed. This is not a finding that the document has no code.";
export const NOT_OPENED = "jason has not opened this link.";
export const PASSCODE_IN_LINK = "A passcode is in the link; it is shown masked.";
export const NO_ZOOM_RECORD = "no record in the Zoom index";

// --- a report portal ------------------------------------------------------------------------------------------------

export interface Holding { place: "library" | "drive" | "payhoa" | "email" | "portal"; where: string; identical: boolean }

export type HeldWord = "library and drive" | "library only" | "drive only" | "not filed";

export interface PortalReport {
  urlUuid: string;
  /** ISO date. */
  day: string;
  site: string;
  /** The portal's own name for the report. */
  template: string;
  inspector: string;
  kind: "inspection" | "record of completion";
  holdings: Holding[];
  held: HeldWord;
  /** Why a check held it back. */
  refused?: string;
}

export interface ReportPortal {
  /** The portal's id on its platform (a UUID). */
  key: string;
  vendor: string;
  customer: string;
  protected: boolean;
  /** Another portal key. */
  sameCustomerAs?: string;
  /** The documents whose codes named it. */
  readFrom: string[];
  /** ISO time of the last sync. */
  fetched: string;
  reports: PortalReport[];
  counts: { listed: number; onDisk: number; inLibrary: number; notFiled: number };
  /** An error, or why it was skipped. */
  note?: string;
}

export const HELD_MEANINGS: Record<HeldWord, string> = {
  "library and drive": "The same content is in jason's library and in Drive.",
  "library only": "A copy is in jason's library; none was found in Drive.",
  "drive only": "A copy is in Drive; none was found in jason's library.",
  "not filed": "The portal lists it; no copy was found in the library or in Drive. A lead, not a finding that the association lacks it.",
};

export const KIND_MEANINGS: Record<PortalReport["kind"], string> = {
  inspection: "An inspection report.",
  "record of completion": "A record of completion of an installation. It is not an inspection.",
};

export const PLACE_WORDS: Record<Holding["place"], string> = {
  library: "Library", drive: "Drive", payhoa: "PayHOA library", email: "Email attachment", portal: "Vendor's portal",
};

export const DIFFERENT_COPY = "a different copy";

// --- the filing plan ------------------------------------------------------------------------------------------------

export type FilingAction = "file" | "move" | "copy" | "in drive" | "filed before" | "held";

export interface FilingPlan {
  vendor: string;
  counts: Record<FilingAction, number>;
  rows: {
    name: string;
    action: FilingAction;
    /** "My Drive/Reports/Fire Protection/Fire Alarm". */
    destination: string;
    /** The rule's condition and the facts that decided it. */
    why: string;
    /** For a copy: where the original stays. */
    original?: string;
    kind: string;
  }[];
  /** The CLI that does it with --yes. */
  command: string;
}

/** The action words are the code's. Each says what happens to the file; none deletes. */
export const FILING_ACTION_ORDER: readonly FilingAction[] = ["file", "copy", "move", "in drive", "filed before", "held"];

export const FILING_MEANINGS: Record<FilingAction, string> = {
  file: "Put a new copy in the destination folder. Nothing in Drive is changed.",
  copy: "Put a copy in the destination folder. The original stays where it is.",
  move: "Move the file to the destination folder. It keeps its id, its link, and its sharing.",
  "in drive": "Already in Drive at the destination. Nothing to do.",
  "filed before": "Filed in an earlier run. Nothing to do.",
  held: "Held for a person to verify first. jason does not write it.",
};

/** The actions that write to Drive. The rest are read-only rows. */
export const WRITING_ACTIONS: readonly FilingAction[] = ["file", "copy", "move"];

export const NOTHING_DELETES = "Nothing is deleted.";
export const COPY_ORIGINAL_STAYS = "The original stays.";
export const MOVE_KEEPS_LINK = "The file keeps its id, its link, and its sharing.";

export function writeCount(plan: Pick<FilingPlan, "counts">): number {
  return WRITING_ACTIONS.reduce((n, a) => n + (plan.counts[a] ?? 0), 0);
}

/** The button's words: the numbers of what it will do, "File 8, copy 5, move 2". A zero is left out; none is "". */
export function filingButtonLabel(plan: Pick<FilingPlan, "counts">): string {
  const parts = WRITING_ACTIONS.filter((a) => (plan.counts[a] ?? 0) > 0).map((a) => `${a} ${plan.counts[a]}`);
  if (!parts.length) return "";
  const s = parts.join(", ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** The plan's rows grouped by action in the order of `FILING_ACTION_ORDER`, for a long plan; an empty group is left out. */
export function groupByAction<T extends { action: FilingAction }>(rows: readonly T[]): { action: FilingAction; rows: T[] }[] {
  return FILING_ACTION_ORDER.map((action) => ({ action, rows: rows.filter((r) => r.action === action) })).filter((g) => g.rows.length);
}

// --- a notice's clock -----------------------------------------------------------------------------------------------

export type RunsFromLabel = "dated" | "postmarked" | "scanned" | "failed test";
export type ClockStanding = "met" | "running" | "passed" | "unknown";

export interface NoticeClockData {
  /** "City cross-connection program". */
  program: string;
  /** A notice's own words, or a statute's citation. */
  basis: string;
  days: number;
  runsFrom: { label: RunsFromLabel; date: string; elapsed: number; met: boolean | null }[];
  standing: ClockStanding;
  /** "Which date counts is the program's to say." */
  caveat: string;
  /** A statute's own clock (cited), not a program's notice. Set by a loader that knows; absent means a program's notice. */
  statute?: boolean;
}

export const STANDING_MEANINGS: Record<ClockStanding, string> = {
  met: "The answer is in on or before the day the clock allows, on the reading shown.",
  running: "The clock has not run out on the readings shown.",
  passed: "The days have run out on the readings shown without an answer.",
  unknown: "The readings disagree or one is missing. Which date counts is not jason's to say.",
};

export const RUNS_FROM_MEANINGS: Record<RunsFromLabel, string> = {
  dated: "The date printed on the notice.",
  postmarked: "The date on the envelope's postmark.",
  scanned: "The day the notice was scanned into the records.",
  "failed test": "The day of the failed test the notice follows.",
};

/** A reading in words: "met", "not met", or "unknown". Never a boolean's color alone. */
export function metWord(met: boolean | null): "met" | "not met" | "unknown" {
  return met === null ? "unknown" : met ? "met" : "not met";
}

// --- the assemblies -------------------------------------------------------------------------------------------------

export type TestResult = "passed" | "failed" | "repaired" | "not read";

export interface Assembly {
  service: "irrigation" | "domestic" | "fire";
  type: "RP" | "DC" | "PVB" | "AG";
  sizeIn: number;
  serial: string;
  /** County assembly id, City backflow id. */
  ids: { source: string; id: string }[];
  location: string;
  account?: string;
  meter?: string;
  lastPassed?: string;
  lastFailed?: string;
  testDue: string;
  tag?: string;
  /** A document reference, or, when the loader could not make one, a command or the name as text (`EvidenceEntry`). */
  history: { date: string; result: TestResult; document: EvidenceEntry }[];
}

export interface Discrepancy {
  subject: string;
  sources: { source: string; says: string; doc?: EvidenceEntry }[];
  /** The next step as a command or a question. A line that starts with "jason " is shown as a command. */
  next?: string;
}

export const ASSEMBLY_TYPE_WORDS: Record<Assembly["type"], string> = {
  RP: "reduced pressure principle assembly",
  DC: "double check assembly",
  PVB: "pressure vacuum breaker",
  AG: "air gap",
};

export const TEST_RESULT_MEANINGS: Record<TestResult, string> = {
  passed: "The tester's report says the device passed.",
  failed: "The tester's report says the device failed.",
  repaired: "The report records a repair.",
  "not read": "The scan could not be read. No result is guessed.",
};

export const NOT_READ = "not read";

/** The unit "in" with a size: `1 1/2` is not computed; the number is shown as given. */
export const sizeText = (inches: number) => `${inches}-inch`;

/** Whether a next step is a command to run (shown with `Command`) or a question or sentence. */
export const isCommand = (next: string) => /^jason\s/.test(next.trim());

// --- the tester check -----------------------------------------------------------------------------------------------

export type ListFound = "listed" | "listed under another business" | "not listed" | "not fetched";

export interface TesterCheck {
  /** As printed on the report. */
  tester: string;
  /** As printed, not verified. */
  certificate?: string;
  lists: { name: string; dated?: string; found: ListFound; id?: string }[];
  contactsMasked: boolean;
}

export const LIST_MEANINGS: Record<ListFound, string> = {
  listed: "The tester's name is on that list as of its date.",
  "listed under another business": "Matched on the tester's name; the business on the list is a different one.",
  "not listed": "The name is not on that list as of its date. The list may be out of date.",
  "not fetched": "The list has not been fetched, so nothing is said about it.",
};

/** A list dated more than a year before `today`. A list with no date is treated as old. */
export function listIsOld(dated: string | undefined, today: Date = new Date()): boolean {
  if (!dated) return true;
  const d = new Date(dated + (dated.length === 10 ? "T00:00:00" : ""));
  if (Number.isNaN(d.getTime())) return true;
  const limit = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
  return d.getTime() < limit.getTime();
}

// --- grades of text -------------------------------------------------------------------------------------------------

export type TextGradeWord = "legislature" | "official" | "digest" | "quoted by a notice" | "not found";

export interface GradeInfo { label: string; meaning: string; glyph: GlyphName; confirm: boolean }

/** The grade is attached to the words it describes. A digest says confirm at the source, in text beside the words. */
export const GRADES: Record<TextGradeWord, GradeInfo> = {
  legislature: { label: "the Legislature's text", meaning: "The words come from the Legislature's own published text. A grade says where the words came from, not that they are the answer.", glyph: "scroll-text", confirm: false },
  official: { label: "official text, read in full", meaning: "A regulation or handbook read in full from its own publication.", glyph: "book-open", confirm: false },
  digest: { label: "a summary of a code reader", meaning: "A summary from a code reader, not the official words.", glyph: "triangle-alert", confirm: true },
  "quoted by a notice": { label: "quoted by a notice", meaning: "A notice quotes the provision; the notice's quotation is not the provision's own text.", glyph: "file-text", confirm: true },
  "not found": { label: "not found", meaning: "No text was found. Nothing is quoted.", glyph: "circle-dashed", confirm: false },
};

export const GRADE_ORDER: readonly TextGradeWord[] = ["legislature", "official", "digest", "quoted by a notice", "not found"];

export const CONFIRM_AT_SOURCE = "confirm at the source";

// --- the watchlist --------------------------------------------------------------------------------------------------

export type WatchStanding = "overdue" | "unknown" | "partly answered" | "current" | "not applicable";

export interface WatchItem {
  item: string;
  standing: WatchStanding;
  evidence: EvidenceEntry[];
  /** What would change the standing. */
  changes: string;
  /** "by email subject and Drive file name". */
  searched: string;
}

export const WATCH_MEANINGS: Record<WatchStanding, string> = {
  overdue: "A record shows it was due and no answer was found.",
  unknown: "Nothing was found either way. This is not a finding that it was not done.",
  "partly answered": "Some of what it asks is answered by a record; some is not.",
  current: "A record answers it for the period it asks about.",
  "not applicable": "A person has recorded that it does not apply.",
};

export const WATCH_GLYPH: Record<WatchStanding, GlyphName> = {
  overdue: "triangle-alert", unknown: "circle-question-mark", "partly answered": "clock", current: "circle-check", "not applicable": "minus",
};

/** Scan order for a table of twelve: overdue first, then unknown (it needs a person's look more than a current one),
 * then partly answered, current, and not applicable. A choice for the design to confirm (decision 1). */
export const WATCH_ORDER: readonly WatchStanding[] = ["overdue", "unknown", "partly answered", "current", "not applicable"];

export const NOT_SEEN = "A record under another name is not seen.";

export function sortWatch<T extends { standing: WatchStanding }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => WATCH_ORDER.indexOf(a.standing) - WATCH_ORDER.indexOf(b.standing));
}

// --- mail that is not ours ------------------------------------------------------------------------------------------

/** Mail addressed to another party at a shared address. Only what is visible on the envelope, never the other party's details. */
export interface NotOurs {
  /** Where it sits: "mail", "thread", "notice". */
  subject: string;
  /** The addressee as a role or a generic name ("another party at the shared address"), already masked by the server. */
  addressee: string;
  /** What the envelope shows, masked. */
  visible: string[];
  /** A person has marked it not ours: who and when. */
  marked?: { by: string; on: string };
}

// --- the tester's summary -------------------------------------------------------------------------------------------

/** One line for a tester across the lists checked, in words: never "certified". A list not fetched says nothing. */
export function testerSummary(lists: readonly TesterCheck["lists"][number][]): string {
  const checked = lists.filter((l) => l.found !== "not fetched");
  if (!checked.length) return "lists not fetched";
  const listed = checked.filter((l) => l.found === "listed").length;
  if (listed === checked.length) return checked.length === 1 ? "listed on the list checked" : "listed on every list checked";
  if (listed === 1 && checked.length > 1) return "listed on one only";
  if (listed > 0) return `listed on ${listed} of ${checked.length} lists checked`;
  if (checked.some((l) => l.found === "listed under another business")) return "listed under a different business";
  return "not listed";
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
