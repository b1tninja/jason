import { useMemo, type ReactNode } from "react";
import { ViewBoundary } from "./Boundary";
import { EmptyState, ErrorNotice, Loading } from "./States";
import type { Remote } from "../lib/useApi";

let nextKey = 0;
const keys = new WeakMap<object, number>();
/** A stable key per data object, so the boundary resets when a reload brings new data. */
function keyFor(data: unknown): number {
  if (!data || typeof data !== "object") return -1;
  let k = keys.get(data);
  if (k === undefined) keys.set(data, (k = ++nextKey));
  return k;
}

/** Calls the view's render function during its own render, so a throw while computing the JSX (the shape-mismatch
 * case) happens inside the boundary, not in RemoteView's render above it. */
function Render<T>({ fn, data }: { fn: (data: T) => ReactNode; data: T }) {
  return <>{fn(data)}</>;
}

/** Loading, error (with Retry), the tool's own `found: false` note, or the data. Every view goes through this. */
export function RemoteView<T extends { found?: boolean; note?: string; hint?: string }>({ r, children }: {
  r: Remote<T> & { reload: () => void };
  children: (data: T) => ReactNode;
}) {
  const data = r.status === "ready" ? r.data : undefined;
  const key = useMemo(() => keyFor(data), [data]);
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  if (r.data.found === false) return <EmptyState>{r.data.note ?? r.data.hint ?? "Nothing on disk yet."}</EmptyState>;
  return (
    <ViewBoundary key={key} data={r.data}>
      <Render fn={children} data={r.data} />
    </ViewBoundary>
  );
}
