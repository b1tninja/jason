import { useState, type ReactNode } from "react";

/** A two-step button: the first click shows what will happen, the second does it. For anything that writes. Armed, it
 * is a stamp: the `label` ("Confirm", "Record", "Send") hangs on its top edge, the summary comes first, the buttons last. */
export function Confirm({ children, summary, onConfirm, busy, label = "Confirm" }: { children: ReactNode; summary: ReactNode; onConfirm: () => void; busy?: boolean; label?: string }) {
  const [armed, setArmed] = useState(false);
  if (!armed)
    return (
      <button className="primary" onClick={() => setArmed(true)} disabled={busy}>
        {children}
      </button>
    );
  return (
    <div className="confirm" role="group" aria-label={label}>
      <span className="confirm-label" aria-hidden="true">{label}</span>
      <div>{summary}</div>
      <div className="row">
        <button className="primary" onClick={() => { setArmed(false); onConfirm(); }} disabled={busy}>
          Yes, do it
        </button>
        <button onClick={() => setArmed(false)} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
}
