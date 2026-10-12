import { getJson, postJson } from "../lib/api";
import type { ClientPictures } from "./splitClient";
import type { ActAnswer, ApplyAnswer, ListedSession, Review, SessionAnswer, SessionView, Size } from "./splitModel";

/** What the splitter's screens ask of a server. `RealBackend` is the console's routes (docs/pdf-splitter.md, section 9.4); the demo
 * (`splitDemo.ts`) answers the same questions from memory, so a person can try the interactions with no server. */
export interface OpenAnswer {
  ok?: boolean; resumed?: boolean; session?: SessionView; dryRun?: boolean;
  /** `pages` is null for a Drive file (its pages are counted when it is read, after the checks); `fetches` says so in words. */
  would?: { act: string; pages: number | null; size: number | null; by: string; keeps: string; source?: string; fetches?: string; pagesCounted?: string };
  note?: string; factsPending?: boolean; caveats?: string[];
  /** Drive is not connected on this server: `found` is false, with the sentence and the command that fixes it. */
  found?: boolean; driveConnected?: boolean; why?: string; command?: string;
}
/** The limits a draft's screens read (`jason.limits`); the two `clientRender` ones say whether and for how long a file the browser draws. */
export interface SplitLimits { maxPages: number; suggestEnabled: boolean; draftDays: number; maxParts: number; clientRender?: boolean; clientRenderMaxPages?: number }
export interface ListAnswer { found?: boolean; note?: string; sessions: ListedSession[]; limits?: SplitLimits; caveats?: string[] }
/** `held` is a copy jason keeps of a file the person picked in their own Google Drive (docs/google-picker.md); `id` is the copy's address from the server. */
export type OpenRef = { kind: "library"; id: string } | { kind: "upload"; name: string; base64: string } | { kind: "drive"; id: string } | { kind: "held"; id: string };
export type ActBody = { act: string; by?: string; version?: number; dryRun?: boolean; [k: string]: unknown };
export type AnyAnswer = ActAnswer & ApplyAnswer & { review?: Review };

/** A draft being saved in the background (a file chosen on this computer is read and sent while the person already works on it). */
export type Phase = "uploading" | "saved" | "refused";
export interface Background { phase: Phase; id: string; words: string }

export interface SplitBackend {
  readonly demo: boolean;
  /** The browser's own picture source, for a backend that has one before the draft exists (a file chosen on this computer). */
  readonly pictures?: ClientPictures;
  /** The background save of a local file: `get()` is its state, and `subscribe` hears each change. */
  readonly background?: { subscribe(fn: () => void): () => void; get(): Background };
  /** Hear the draft arrive on the server (a local file's), once. */
  onServer?(fn: () => void): () => void;
  thumbUrl(id: string, page: number, size: Size): string;
  list(): Promise<ListAnswer>;
  session(id: string, q?: { facts?: [number, number]; review?: boolean; flags?: boolean }): Promise<SessionAnswer>;
  act(id: string, body: ActBody): Promise<AnyAnswer>;
  open(ref: OpenRef, dryRun: boolean, by?: string): Promise<OpenAnswer>;
}

export const realBackend: SplitBackend = {
  demo: false,
  thumbUrl: (id, page, size) => `/api/split/thumb?id=${encodeURIComponent(id)}&page=${page}&size=${size}`,
  list: () => getJson<ListAnswer>("/api/split-sessions"),
  session: (id, q = {}) => {
    const p = new URLSearchParams({ id });
    if (q.facts) p.set("facts", `${q.facts[0]}-${q.facts[1]}`);
    if (q.review) p.set("review", "1");
    if (q.flags) p.set("flags", "1");
    return getJson<SessionAnswer>(`/api/split-session?${p}`);
  },
  act: (id, body) => postJson<AnyAnswer>(`/api/write/split/${encodeURIComponent(id)}`, body),
  open: (ref, dryRun, by) => postJson<OpenAnswer>("/api/write/split/new", { act: "open", ref, dryRun, by: by || undefined }),
};

/** A save that was refused because the draft moved on (409): the server's words and its copy. */
export interface Conflict { message: string; current: SessionView }

export function conflictOf(e: unknown): Conflict | null {
  const err = e as { status?: number; message?: string; body?: { conflict?: boolean; current?: SessionView } };
  if (err?.status === 409 && err.body?.current) return { message: err.message ?? "", current: err.body.current };
  return null;
}

/** The library could not be read just now (a 503 with `Retry-After`, or `busy: true`): nothing was changed, and trying again is safe. */
export interface Busy { retryAfter: number; message: string }

export const DEFAULT_RETRY_SECONDS = 5;

export function busyOf(e: unknown): Busy | null {
  const err = e as { status?: number; message?: string; retryAfter?: number; body?: { busy?: boolean; retryAfter?: number } | null };
  if (err?.status !== 503) return null;
  const after = err.retryAfter ?? err.body?.retryAfter;
  if (!err.body?.busy && after === undefined) return null;
  return { retryAfter: Math.max(0, Math.min(120, Math.floor(after ?? DEFAULT_RETRY_SECONDS))), message: err.message ?? "" };
}

/** An apply refused because the plan is not the plan that was reviewed (409 `planChanged`): the server's words and the new (masked) review. */
export interface PlanChange { message: string; review: Review }

export function planChangedOf(e: unknown): PlanChange | null {
  const err = e as { status?: number; message?: string; body?: { planChanged?: boolean; review?: Review } | null };
  if (err?.status === 409 && err.body?.planChanged && err.body.review) return { message: err.message ?? "", review: err.body.review };
  return null;
}

/** Whether a failure is the network's (the request never got an answer) rather than the server's refusal. */
export function isOffline(e: unknown): boolean {
  const err = e as { status?: number; name?: string };
  return err?.status === undefined && !(err?.name === "AbortError");
}
