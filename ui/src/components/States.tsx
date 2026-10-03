import type { ReactNode } from "react";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="muted">
      {label}
    </p>
  );
}

export function ErrorNotice({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="notice notice-error">
      <span>{error}</span>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function EmptyState({ children = "Nothing to show." }: { children?: ReactNode }) {
  return <p className="muted">{children}</p>;
}
