/** A refused or failed request: the server's own message, with the status and the body it answered (an apply refused as
 * stale answers 409 with `supersededBy` and `changed`). */
export class ApiError extends Error {
  status?: number;
  body?: unknown;
  constructor(message: string, status?: number, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  const error = (body as { error?: string } | null)?.error;
  if (!res.ok || error) throw new ApiError(error ?? `${res.status} ${res.statusText}`, res.status, body);
  return body as T;
}

/** Who signed in with Google: the officer the account matched (`jason.web.signin`); `role` joins two offices. */
export interface SignedIn { name: string; role?: string; email?: string; provider?: string; at?: string; maintainer?: boolean }

/** Whether Google sign-in is set up on this server, whether writes need it, its routes, and `--dev`. */
export interface SignInSetup { provider?: string; configured?: boolean; required?: boolean; start?: string; signOut?: string; dev?: boolean; actAs?: string }

/** Who a maintainer views the console as under `--dev`: a person (`name`) or an office alone (`role`, no name). */
export interface Acting { name: string; role: string }

/** What `GET /api/session` says about this server process: the write token and its header, which approval steps it
 * allows (`applyEnabled` only when started with `--allow-apply`; `liveChecks` when a re-plan may read live), and who is
 * signed in (`signedIn`, null when no one is; `signInError` is the last sign-in's refusal, said once). */
export interface ServerSession {
  token?: string; header?: string; applyEnabled?: boolean; liveChecks?: boolean; approvalsWrites?: boolean;
  signedIn?: SignedIn | null; signIn?: SignInSetup; signInError?: string;
  canActAs?: boolean; acting?: Acting | null; actAsPeople?: { name: string; role: string }[]; actAsRoles?: string[];
}

let session: Promise<ServerSession> | null = null;

/** The server's session, asked once; a failed answer is not kept, so the next write asks again. */
export function serverSession(): Promise<ServerSession> {
  if (!session) {
    const asked = getJson<ServerSession>("/api/session").then(
      (s) => (s && typeof s === "object" ? s : {}),
      () => ({}) as ServerSession,
    );
    session = asked;
    asked.then((s) => { if (!s.token && session === asked) session = null; });
  }
  return session;
}

/** Forget the cached session (a test, or a server restarted with a new token). */
export function resetServerSession(): void {
  session = null;
}

/** Where "Sign in with Google" goes: the server's start route, returning to `hash` (a console route) after. */
export function signInHref(setup: SignInSetup | undefined, hash: string): string {
  const start = setup?.start || "/auth/google";
  return hash.startsWith("#/") ? `${start}?next=${encodeURIComponent(hash)}` : start;
}

/** Sign out (a guarded POST); the cached session is dropped so the next read says who is signed in. */
export async function signOut(setup?: SignInSetup): Promise<void> {
  await postJson(setup?.signOut || "/auth/signout", {});
  resetServerSession();
}

/** Under `--dev`, view the console as a person (`{name}`) or an office (`{role}`); `{}` goes back to oneself. */
export async function actAs(setup: SignInSetup | undefined, target: { name?: string; role?: string }): Promise<Acting | null> {
  const out = await postJson<{ acting?: Acting | null }>(setup?.actAs || "/auth/act-as", target);
  resetServerSession();
  return out.acting ?? null;
}

/** The per-process write token: the page's `<meta name="jason-token">`, else `GET /api/session`. Empty when neither has
 * one (the HttpOnly cookie still covers the store writes). */
async function writeToken(): Promise<[string, string]> {
  const meta = typeof document !== "undefined" ? document.querySelector('meta[name="jason-token"]')?.getAttribute("content") ?? "" : "";
  if (meta) return ["X-Jason-Token", meta];
  const s = await serverSession();
  return [s.header || "X-Jason-Token", s.token ?? ""];
}

/** A write. Every POST carries the server's write token header when the page has one. */
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const [header, token] = await writeToken();
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  if (token) headers[header] = token;
  const res = await fetch(path, { method: "POST", headers, body: JSON.stringify(body) });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  const error = (data as { error?: string } | null)?.error;
  if (!res.ok || error) throw new ApiError(error ?? `${res.status} ${res.statusText}`, res.status, data);
  return data as T;
}
