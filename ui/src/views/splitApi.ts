import { getJson, postJson } from "../lib/api";
import type { ActAnswer, ApplyAnswer, ListedSession, Review, SessionAnswer, SessionView, Size } from "./splitModel";

/** What the splitter's screens ask of a server. `RealBackend` is the console's routes (docs/pdf-splitter.md, section 9.4); the demo
 * (`splitDemo.ts`) answers the same questions from memory, so a person can try the interactions with no server. */
export interface OpenAnswer {
  ok?: boolean; resumed?: boolean; session?: SessionView; dryRun?: boolean; would?: { act: string; pages: number; size: number; by: string; keeps: string };
  note?: string; factsPending?: boolean; caveats?: string[];
}
export interface ListAnswer { found?: boolean; note?: string; sessions: ListedSession[]; limits?: { maxPages: number; suggestEnabled: boolean; draftDays: number; maxParts: number }; caveats?: string[] }
export type OpenRef = { kind: "library"; id: string } | { kind: "upload"; name: string; base64: string };
export type ActBody = { act: string; by?: string; version?: number; dryRun?: boolean; [k: string]: unknown };
export type AnyAnswer = ActAnswer & ApplyAnswer & { review?: Review };

export interface SplitBackend {
  readonly demo: boolean;
  thumbUrl(id: string, page: number, size: Size): string;
  list(): Promise<ListAnswer>;
  session(id: string, q?: { facts?: [number, number]; review?: boolean }): Promise<SessionAnswer>;
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

/** Whether a failure is the network's (the request never got an answer) rather than the server's refusal. */
export function isOffline(e: unknown): boolean {
  const err = e as { status?: number; name?: string };
  return err?.status === undefined && !(err?.name === "AbortError");
}
