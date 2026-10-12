import { useEffect, useState } from "react";
import { ApiError, postJson, serverSession, signInRefusal } from "./api";

/** Choosing files from a person's own Google Drive with Google's Picker (docs/google-picker.md, "The UI contract").
 *
 * The button leaves the console for the server's start route, Google shows its Picker, and the server sends the page back as
 * `/?pick=<token>#/route`. The token is read once: `pickReturn()` takes it out of the address at the first call and asks the server for
 * the result once; every later call (a remount, React's second effect) gets the same answer, and `clearPickReturn()` is the person
 * closing the list. Nothing but the route and the slot key goes out; no file id, name or token. */

export type PickPurpose = "split" | "slot";

/** One picked file's result, as `jason.tasks.drive_pick.Row` says it. `name` is shown here once and is not kept by the server. */
export interface PickRow { outcome: "held" | "already held" | "would hold" | "refused"; reason: string; words: string; heldId: string; size: number; pages: number; name: string }
export interface PickReport { dryRun: boolean; counts: Record<string, number>; rows: PickRow[] }
export interface PickResult { purpose: PickPurpose; slot: string; error: string; report: PickReport | null }

/** What coming back from Google came to. */
export type PickReturn =
  | { kind: "result"; result: PickResult }
  | { kind: "gone" }
  | { kind: "signin"; message: string; href: string }
  | { kind: "error"; message: string };

/** The server's start route for a pick, with where to come back to (`next`, a console route) and, for a record slot, which slot. */
export function pickStartUrl(start: string, purpose: PickPurpose, slot: string, hash: string): string {
  const q = new URLSearchParams();
  if (hash.startsWith("#/")) q.set("next", hash);
  if (slot) q.set("slot", slot);
  q.set("purpose", purpose);
  return `${start || "/auth/google/pick"}?${q}`;
}

/** The page leaves for Google. A navigation, not a fetch. Replaceable in a test (`vi.mock`). */
export function navigateTo(url: string): void {
  window.location.assign(url);
}

export interface PickSetup { enabled: boolean; start: string; result: string; known: boolean }

/** Whether this community has choosing from the person's own Drive on, from `GET /api/session` (`known` false until it answered). */
export function usePickSetup(): PickSetup {
  const [s, setS] = useState<PickSetup>({ enabled: false, start: "/auth/google/pick", result: "/api/drive/pick/result", known: false });
  useEffect(() => {
    let on = true;
    serverSession().then((x) => {
      if (on) setS({ enabled: !!x.pick?.enabled, start: x.pick?.start || "/auth/google/pick", result: x.pick?.result || "/api/drive/pick/result", known: true });
    });
    return () => { on = false; };
  }, []);
  return s;
}

let pending: Promise<PickReturn> | null = null;
let taken = false;

/** Take `?pick=` out of the address at once (so it is never reloaded, bookmarked, or sent in a Referer) and keep it as the token. */
function takeToken(): string {
  if (typeof window === "undefined") return "";
  const url = new URL(window.location.href);
  const token = url.searchParams.get("pick") ?? "";
  if (url.searchParams.has("pick")) {
    url.searchParams.delete("pick");
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }
  return token;
}

async function read(token: string, path: string): Promise<PickReturn> {
  try {
    const result = await postJson<PickResult>(path, { token });
    return { kind: "result", result };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return { kind: "gone" };
    // A pick that ended in an error (Google refused, nothing picked) is a result whose `error` is set: the shared write helper throws on any
    // body that has an `error`, so the result is taken from the error's body (a 200 answer that carries `purpose`).
    const body = e instanceof ApiError ? (e.body as Partial<PickResult> | null) : null;
    if (e instanceof ApiError && e.status === 200 && body && typeof body.purpose === "string") {
      return { kind: "result", result: { purpose: body.purpose, slot: body.slot ?? "", error: body.error ?? "", report: body.report ?? null } };
    }
    const sign = signInRefusal(e);
    if (sign) return { kind: "signin", ...sign };
    return { kind: "error", message: (e as Error).message };
  }
}

/** The result of the pick this page load came back from, read from the server once; null when the page did not come from Google. */
export function pickReturn(path = "/api/drive/pick/result"): Promise<PickReturn> | null {
  if (!taken) {
    taken = true;
    const token = takeToken();
    if (token) pending = read(token, path);
  }
  return pending;
}

/** The person has closed the list; a later visit to the screen does not show it again. */
export function clearPickReturn(): void {
  pending = null;
}

/** For a test: forget what was taken. */
export function resetPickReturn(): void {
  pending = null;
  taken = false;
}

/** The return from Google for a screen that takes `purpose`: null while there is none, until read, or for another purpose's. */
export function usePickReturn(purpose: PickPurpose): { value: PickReturn | null; close: () => void } {
  const [value, setValue] = useState<PickReturn | null>(null);
  useEffect(() => {
    let on = true;
    const p = pickReturn();
    p?.then((r) => { if (on && (r.kind !== "result" || r.result.purpose === purpose)) setValue(r); });
    return () => { on = false; };
  }, [purpose]);
  return { value, close: () => { clearPickReturn(); setValue(null); } };
}
