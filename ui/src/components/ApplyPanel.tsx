import { useEffect, useId, useState, type ReactNode } from "react";
import { Confirm } from "./Confirm";
import { holdClock, typedCountProblem, when, type ApplyHold, type ApplyPrefs, type TypedCount } from "../lib/approvals";
import "../styles/plan-progress.css";

/** The five apply settings that hold for this plan's kind, in plain words, each with where it comes from: the default, or the
 * board's adoption (`jason.controls.apply_prefs`). A preference never lowers a signature count, removes a control, or lets the
 * console apply a kind that is terminal-only, costs money, or sends mail or email; one adopted but not yet in force is listed. */
export function ApplyPrefsNote({ prefs }: { prefs?: ApplyPrefs | null }) {
  if (!prefs) return null;
  return (
    <details className="plan-prefs">
      <summary>How this plan is applied</summary>
      <ul className="plan-prefs-list">
        {prefs.rows.map((r) => (
          <li key={r.setting} data-setting={r.setting}>
            <strong>{r.title}:</strong> {r.words} <span className="muted">({r.source})</span>
          </li>
        ))}
        {prefs.waiting.map((w) => (
          <li key={w.control} className="muted">A preference the board adopted is not in force yet: {w.why}.</li>
        ))}
      </ul>
      <p className="muted">These are the board's opt-in preferences. None lowers a signature count or removes a control, and the console never applies a kind that is applied only at a terminal, costs money, or sends mail or email.</p>
    </details>
  );
}

/** The pause the board adopted between the last signature and apply, while it lasts: a countdown (from the seconds the server
 * said were left, on this page's clock), why, and `withdraw` beside it. Apply is not offered until it ends; `onElapsed` runs when
 * the countdown reaches zero, so the page can read the plan again. */
export function PauseHold({ hold, withdraw, onElapsed }: { hold: ApplyHold; withdraw?: ReactNode; onElapsed?: () => void }) {
  const [left, setLeft] = useState(hold.secondsLeft);
  useEffect(() => {
    const end = Date.now() + hold.secondsLeft * 1000;
    setLeft(hold.secondsLeft);
    const tick = setInterval(() => {
      const s = Math.max(0, Math.ceil((end - Date.now()) / 1000));
      setLeft(s);
      if (s <= 0) { clearInterval(tick); onElapsed?.(); }
    }, 1000);
    return () => clearInterval(tick);
  }, [hold.endsAt, hold.secondsLeft]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="plan-hold" role="group" aria-label="Pause before apply">
      <p>
        <strong>Held for <span className="plan-hold-clock" role="timer" aria-live="off">{holdClock(left)}</span> more.</strong>{" "}
        {hold.words} Ends {when(hold.endsAt)}.
      </p>
      {withdraw}
    </div>
  );
}

/** The apply button: two steps through `Confirm`, and, where the board asked for it above some number of changes, the person
 * first types the number of changes the plan makes. Until the typed number is right the button stays unavailable and says why.
 * `onConfirm` gets the typed number (undefined when none is asked). */
export function ApplyButton({ typedCount, busy, summary, onConfirm, children }: {
  typedCount?: TypedCount | null; busy?: boolean; summary: ReactNode; onConfirm: (count?: number) => void; children: ReactNode;
}) {
  const uid = useId();
  const [typed, setTyped] = useState("");
  const [shown, setShown] = useState(false);
  const ask = !!typedCount?.needed;
  const problem = typedCountProblem(typedCount, typed);
  useEffect(() => { setShown(false); }, [typed]);
  return (
    <div className="stack-sm">
      {ask && (
        <label className="approve-field">
          Type the number of changes this plan makes, to apply it
          <input inputMode="numeric" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off"
            aria-invalid={shown && problem ? true : undefined} aria-describedby={`${uid}-typed`} />
        </label>
      )}
      {problem ? (
        <div className="row wrap">
          <button type="button" className="primary" aria-disabled="true" disabled={busy} aria-describedby={`${uid}-typed`} onClick={() => setShown(true)}>{children}</button>
          <span id={`${uid}-typed`} className="approve-error" role="alert">{shown ? problem : ""}</span>
        </div>
      ) : (
        <Confirm busy={busy} summary={summary} onConfirm={() => onConfirm(ask ? Number(typed.trim()) : undefined)}>{children}</Confirm>
      )}
    </div>
  );
}
