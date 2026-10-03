import type { ReactNode } from "react";
import { EmptyState, ErrorNotice, Loading } from "./States";
import type { Remote } from "../lib/useApi";

/** Loading, error (with Retry), the tool's own `found: false` note, or the data. Every view goes through this. */
export function RemoteView<T extends { found?: boolean; note?: string; hint?: string }>({ r, children }: {
  r: Remote<T> & { reload: () => void };
  children: (data: T) => ReactNode;
}) {
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  if (r.data.found === false) return <EmptyState>{r.data.note ?? r.data.hint ?? "Nothing on disk yet."}</EmptyState>;
  return <>{children(r.data)}</>;
}
