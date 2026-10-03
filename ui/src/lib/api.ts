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

/** What `GET /api/session` says about this server process: the write token and its header, and which approval steps it
 * allows (`applyEnabled` only when started with `--allow-apply`; `liveChecks` when a re-plan may read live). */
export interface ServerSession { token?: string; header?: string; applyEnabled?: boolean; liveChecks?: boolean; approvalsWrites?: boolean }

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
