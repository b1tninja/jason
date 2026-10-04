/** Finding the association and its recorded documents, for onboarding: the county's association directory
 * (`GET /api/associations`, built from the county recorder's public index by asspy's survey) and the documents the
 * locator ties to one association (`GET /api/documents-located`, `jason.tasks.document_locator`). Both are leads, not
 * pins. The console never calls the county: a locate is a read job a person queues
 * (`POST /api/write/documents-located/locate`), run by `jason worker`. */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getJson, postJson } from "./api";

/** What an association-named party is, read from its name (asspy's `Kind`). */
export type AssociationKind = "homeowners" | "commercial" | "maintenance" | "timeshare" | "bank" | "other" | (string & {});
/** How sure the directory is that a name is an association (asspy's `Standing`). */
export type DirectoryStanding = "confirmed" | "likely" | "named" | (string & {});

/** What each standing means, in asspy's words; shown on hover and to a screen reader beside the word. */
export const STANDING_MEANING: Record<string, string> = {
  confirmed: "records assessment liens or a declaration",
  likely: "records other association business",
  named: "the name alone",
};

/** One association in the county's directory. Owners never appear: a row is an association-named party. */
export interface DirectoryRow {
  key: string; name: string; kind: AssociationKind; standing: DirectoryStanding;
  first: string; last: string; spellings: string[];
  /** Recordings under the name by what they show (asspy's `Evidence`): "assessment lien", "declaration", ... */
  evidence: Record<string, number>;
  governing: number; links: number; score: number;
}

export interface Directory {
  county: string; surveyed: boolean;
  summary?: { byKind?: Record<string, number>; byStanding?: Record<string, number>; coverage?: unknown; links?: number };
  results: DirectoryRow[]; caveats?: string[]; command?: string;
  found?: boolean; note?: string;
}

/** The choice a person makes in the picker. Choosing writes nothing. */
export interface AssociationChoice { key: string; name: string; county: string; row: DirectoryRow }

/** A queued or running read job (`jason jobs`). */
export interface JobRef { id: string | number; status: string }

/** One recorded instrument the locator ties to the association. `parties` are business and association parties only. */
export interface LocatedDoc {
  number: string; recorded: string | null; filing: string;
  /** The `Tie` name and its words: "names the association", "recorded with the association's documents", "the builder's filing". */
  tie: string; tie_label: string; strong: boolean; via: string; parties: string[];
}
/** One onboarding checklist item and what was located for it. `stakes`: a second person confirms the answer. */
export interface LocatedItem { item: string; title: string; question: string; stakes: boolean; located: LocatedDoc[] }
export interface NotLocated { item: string; title: string; ask: string }

export interface Location {
  association: string; county: string; located_at: string; searches: number; liens: number; spellings: string[];
  items: LocatedItem[]; not_located: NotLocated[]; notes: string[]; caveats: string[]; job?: JobRef | null;
  missing?: false;
}
/** Nothing located yet: the tool's note and the command that fills it, and the job when one is queued. */
export interface LocationMissing { missing: true; command: string; note: string; job?: JobRef | null }
export type LocationResult = Location | LocationMissing;

export const LEAD_NOT_PIN = "A directory row is a lead, not a pin.";
export const LOCATED_NOT_PIN = "A located document is a lead, not a pin: the recorded copy is read before it is pinned.";

export function isMissing(r: LocationResult): r is LocationMissing {
  return (r as LocationMissing).missing === true;
}

/** A job that has not finished: the page keeps reading the result while one is queued or running. */
export function isPending(job: JobRef | null | undefined): boolean {
  return !!job && (job.status === "queued" || job.status === "running");
}

const NOUNS: Record<string, [string, string]> = {
  "assessment lien": ["assessment lien", "assessment liens"],
  "sale notice": ["sale notice", "sale notices"],
};

/** A count of one kind of evidence in words: "386 assessment liens", "15 declaration filings", "1 property filing". */
export function evidenceWord(kind: string, n: number): string {
  const [one, many] = NOUNS[kind] ?? [`${kind} filing`, `${kind} filings`];
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}

/** The evidence summary, largest first: "386 assessment liens · 15 declaration filings". */
export function evidenceText(evidence: Record<string, number> | null | undefined): string {
  return Object.entries(evidence ?? {})
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => evidenceWord(k, n))
    .join(" · ");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** An ISO day in the console's form: "Oct 3, 2026". Anything else is shown as given. */
export function dayText(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ""));
  if (!m) return String(iso ?? "");
  return `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${Number(m[3])}, ${m[1]}`;
}

/** Years active: "recorded from 2004 through 2025", or "recorded in 2004". */
export function yearsText(first: string | null | undefined, last: string | null | undefined): string {
  const a = String(first ?? "").slice(0, 4), b = String(last ?? "").slice(0, 4);
  if (!a && !b) return "";
  if (!a || !b || a === b) return `recorded in ${a || b}`;
  return `recorded from ${a} through ${b}`;
}

/** A county key as words: "placer" is "Placer", "san-luis-obispo" is "San Luis Obispo". */
export function countyName(county: string): string {
  return county.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** The onboarding question a located item becomes (`onboarding_session.lead_asks`: `fact:lookup:located-ITEM`). */
export function questionSubject(item: string): string {
  return `fact:lookup:located-${item}`;
}

export function associationsPath(county: string, q: string, limit = 25): string {
  const p = new URLSearchParams({ county, limit: String(limit) });
  if (q.trim()) p.set("q", q.trim());
  return `/api/associations?${p}`;
}

/** The active profile's result with no arguments; another association's by county and name. */
export function locatedPath(county?: string, name?: string): string {
  if (!county || !name) return "/api/documents-located";
  return `/api/documents-located?${new URLSearchParams({ county, name })}`;
}

export type LocateOutcome =
  | { queued: true; job: JobRef; command: string }
  | { queued: false; writesOff: true; command: string; error: string }
  | { queued: false; writesOff: false; error: string };

/** Queue the locator as a read job. Writes off (405) is not an error: the person runs `command` in a terminal. */
export async function locateDocuments(body: { county: string; name: string; by: string }, command = ""): Promise<LocateOutcome> {
  try {
    const out = await postJson<{ job: JobRef; command: string }>("/api/write/documents-located/locate", body);
    return { queued: true, job: out.job, command: out.command ?? command };
  } catch (e) {
    const err = e as ApiError;
    if (err.status === 405) {
      const cmd = ((err.body as { command?: string } | null)?.command) || command;
      return { queued: false, writesOff: true, command: cmd, error: err.message };
    }
    return { queued: false, writesOff: false, error: err.message || "The request failed." };
  }
}

/** A GET that keeps the last answer while it reads again (no flash of "Loading" on a refresh or a poll), and reads
 * again every `pollMs` while `poll(data)` holds. */
export function useKeptJson<T>(path: string, opts: { poll?: (data: T) => boolean; pollMs?: number } = {}) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const pollRef = useRef(opts.poll);
  pollRef.current = opts.poll;
  const pollMs = opts.pollMs ?? 4000;
  const lastPath = useRef(path);
  useEffect(() => {
    const ctl = new AbortController();
    if (lastPath.current !== path) { setData(undefined); lastPath.current = path; }
    setLoading(true);
    getJson<T>(path, ctl.signal).then(
      (d) => { setData(d); setError(""); setLoading(false); },
      (e: Error) => { if (e.name !== "AbortError") { setError(e.message); setLoading(false); } },
    );
    return () => ctl.abort();
  }, [path, tick]);
  useEffect(() => {
    if (loading || data === undefined || !pollRef.current?.(data)) return;
    const h = setTimeout(() => setTick((t) => t + 1), pollMs);
    return () => clearTimeout(h);
  }, [data, loading, pollMs]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

/** A value that settles `ms` after the last change (a search box's words). */
export function useDebounced<T>(value: T, ms: number): T {
  const [out, setOut] = useState(value);
  useEffect(() => {
    if (ms <= 0) { setOut(value); return; }
    const h = setTimeout(() => setOut(value), ms);
    return () => clearTimeout(h);
  }, [value, ms]);
  return out;
}
