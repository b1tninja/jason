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

/** Whether the console is in the owner view: `?view=owner` in the hash (`#/<screen>?view=owner`). */
export function ownerView(): boolean {
  if (typeof window === "undefined") return false;
  const h = window.location.hash;
  return h.includes("?") && new URLSearchParams(h.slice(h.indexOf("?") + 1)).get("view") === "owner";
}

/** A read as the owner view makes it: every `/api/<source>` read carries `view=owner`, so the server answers it from
 * the owner loaders alone (`jason.web.extra.owner_view`) and refuses a source that has none. The session is not a
 * source. Outside the owner view, and for a path that already says its view, the path is unchanged. */
export function forView(path: string, owner: boolean = ownerView()): string {
  if (!owner || !path.startsWith("/api/") || path.startsWith("/api/session") || /[?&]view=/.test(path)) return path;
  return `${path}${path.includes("?") ? "&" : "?"}view=owner`;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(forView(path), { signal, headers: { Accept: "application/json" } });
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
export interface SignedIn { name: string; role?: string; email?: string; provider?: string; at?: string; admin?: boolean }

/** Whether Google sign-in is set up on this server, whether writes need it, its routes, and `--dev`. */
export interface SignInProviderInfo { key: string; label?: string; source?: string }

/** Whether Google sign-in is set up on this server (one or more providers: the community's own Workspace, the
 * installation's), whether writes need it, its routes, and `--dev`. */
export interface SignInSetup { provider?: string; configured?: boolean; required?: boolean; start?: string; signOut?: string; dev?: boolean; actAs?: string; providers?: SignInProviderInfo[] }

/** Who an admin views the console as under `--dev`: a person (`name`) or an office alone (`role`, no name). */
export interface Acting { name: string; role: string }

/** What `GET /api/session` says about this server process: the write token and its header, which approval steps it
 * allows (`applyEnabled` only when started with `--allow-apply`; `liveChecks` when a re-plan may read live), and who is
 * signed in (`signedIn`, null when no one is; `signInError` is the last sign-in's refusal, said once). */
export interface ServerSession {
  token?: string; header?: string; applyEnabled?: boolean; liveChecks?: boolean; approvalsWrites?: boolean;
  signedIn?: SignedIn | null; signIn?: SignInSetup; signInError?: string;
  /** What the signed-in person (or whom an admin views as) is to the console: "officer", "manager", "administrator", or
   * "" (derived on the server from their offices, `jason.web.signin.role_class`). */
  roleClass?: string;
  canActAs?: boolean; acting?: Acting | null; actAsPeople?: { name: string; role: string }[]; actAsRoles?: string[];
  private?: PrivateView;
}

/** The private view (`jason.web.access`): a time-limited, logged window in which restricted (P3) material is shown to
 * a person whose office opens it. `until` is when it closes (ISO 8601); `mayOpen` and `why` say whether this person
 * may open it and why not. `minutes` are the lengths offered, `default` the one chosen unless the person picks. */
export interface PrivateView {
  open: boolean; until?: string; reason?: string; id?: string; mayOpen: boolean; why?: string;
  minutes?: number[]; default?: number;
}

/** What opening the private view sends: a short reason (logged) and how long, in minutes (15, 30, or 60). */
export interface PrivateOpenBody { reason: string; minutes: number }

/** Open the private view (`POST /api/private`, with the write token); the server's refusal comes back as `ApiError`. */
export async function openPrivate(body: PrivateOpenBody): Promise<PrivateView> {
  const out = await postJson<{ private: PrivateView }>("/api/private", body);
  resetServerSession();
  return out.private;
}

/** Close the private view (`DELETE /api/private`, with the write token). */
export async function closePrivate(): Promise<PrivateView> {
  const out = await sendJson<{ private: PrivateView }>("DELETE", "/api/private");
  resetServerSession();
  return out.private;
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
export function signInHref(setup: SignInSetup | undefined, hash: string, provider = ""): string {
  const start = setup?.start || "/auth/google";
  const q = [hash.startsWith("#/") ? `next=${encodeURIComponent(hash)}` : "", provider ? `provider=${encodeURIComponent(provider)}` : ""].filter(Boolean);
  return q.length ? `${start}?${q.join("&")}` : start;
}

/** One "Sign in with Google" link a provider; with more than one, each named by its label (or key). */
export function signInLinks(setup: SignInSetup | undefined, hash: string): { label: string; href: string }[] {
  if (!setup?.configured) return [];
  const providers = setup.providers?.length ? setup.providers : [{ key: "" }];
  return providers.map((p) => ({
    label: providers.length > 1 ? `Sign in with Google (${p.label || p.key})` : "Sign in with Google",
    href: signInHref(setup, hash, providers.length > 1 ? p.key : ""),
  }));
}

/** A refusal that asks for a sign-in (401 from `jason.web.access`): the server's sentence and where "Sign in with Google"
 * goes, back to `hash` (the console route) after. `null` for any other error. */
export function signInRefusal(e: unknown, hash = typeof window !== "undefined" ? window.location.hash : ""): { message: string; href: string } | null {
  if (!(e instanceof ApiError) || e.status !== 401) return null;
  const start = (e.body as { signIn?: unknown } | null)?.signIn;
  return { message: e.message, href: signInHref({ start: typeof start === "string" && start.startsWith("/") ? start : undefined }, hash) };
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
  return sendJson<T>("POST", path, body);
}

/** A write by `method` (POST, DELETE), with the server's write token header when the page has one; `body` is sent as
 * JSON when given. */
export async function sendJson<T>(method: "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  const [header, token] = await writeToken();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers[header] = token;
  const res = await fetch(path, { method, headers, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
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
