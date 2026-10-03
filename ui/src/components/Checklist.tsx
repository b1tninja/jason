import { Badge } from "./Badge";

export interface ChecklistItem { label: string; ready: boolean; detail?: string }

/** A read-only list of required contents, each line marked ready or missing. It records nothing: when a person must
 * tick each line with their name (a confirmation), use `ConfirmList` instead. */
export function Checklist({ items, title }: { items: readonly ChecklistItem[]; title?: string }) {
  const missing = items.filter((i) => !i.ready).length;
  return (
    <div className="checklist">
      {title && (
        <div className="checklist-head">
          <strong>{title}</strong>
          <span className="muted">{missing ? `${missing} missing` : items.length ? "all ready" : ""}</span>
        </div>
      )}
      {items.length === 0 ? (
        <p className="muted">Nothing required.</p>
      ) : (
        <ul>
          {items.map((it, i) => (
            <li key={i} className={it.ready ? "ready" : "missing"}>
              <Badge tone={it.ready ? "good" : "bad"}>{it.ready ? "ready" : "missing"}</Badge>
              <span>
                {it.label}
                {it.detail && <span className="muted"> · {it.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
