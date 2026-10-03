import { useState, type ReactNode } from "react";

/** A two-step button: the first click shows what will happen, the second does it. For anything that writes. */
export function Confirm({ children, summary, onConfirm, busy }: { children: ReactNode; summary: ReactNode; onConfirm: () => void; busy?: boolean }) {
  const [armed, setArmed] = useState(false);
  if (!armed)
    return (
      <button className="primary" onClick={() => setArmed(true)} disabled={busy}>
        {children}
      </button>
    );
  return (
    <div className="confirm" role="group" aria-label="Confirm">
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
