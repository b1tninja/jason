export class ApiError extends Error {}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  const error = (body as { error?: string } | null)?.error;
  if (!res.ok || error) throw new ApiError(error ?? `${res.status} ${res.statusText}`);
  return body as T;
}
