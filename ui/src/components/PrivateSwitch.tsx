import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import type { PrivateOpenBody, PrivateView } from "../lib/api";

/** The lengths a private view is opened for, in minutes; 30 unless the person picks another. */
export const PRIVATE_MINUTES = [15, 30, 60] as const;
export const PRIVATE_DEFAULT = 30;
export const PRIVATE_HINT = "A short phrase, e.g. executive session prep. It's logged.";
const SOON = 5;                       // minutes left when the band says, once, that the view is about to close
const TICK_MS = 10_000;

/** "21:15": an ISO time as the 24-hour clock on this machine. Empty for a time that cannot be read. */
export function clockTime(iso: string | undefined): string {
  const at = iso ? new Date(iso) : null;
  if (!at || Number.isNaN(at.getTime())) return "";
  return `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
}

/** Whole minutes left until `until`, rounded up; 0 once it has passed (or cannot be read). */
export function minutesLeft(until: string | undefined, now: Date): number {
  const at = until ? new Date(until).getTime() : NaN;
  if (Number.isNaN(at)) return 0;
  return Math.max(0, Math.ceil((at - now.getTime()) / 60_000));
}

export interface PrivateSwitchProps {
  /** The private view as `GET /api/session` says it (`private`). */
  view: PrivateView;
  /** Who opens it, for the confirm: "Open the private view as NAME for 30 minutes". */
  name: string;
  /** Open it: `POST /api/private` with `{reason, minutes}`. A refusal is thrown with the server's sentence, and said. */
  onOpen: (body: PrivateOpenBody) => Promise<void> | void;
}

/** The private view's switch, in the console's header beside the account: a quiet "Private view: off" button that
 * asks why and for how long, then opens it as the named person; disabled, with the server's reason beside it, for a
 * person whose office does not open restricted material; "Private view: on" while it is open (the band below the
 * header closes it). Rendered for a signed-in person only, never in the owner view (the shell decides). */
export function PrivateSwitch({ view, name, onOpen }: PrivateSwitchProps) {
  const [asking, setAsking] = useState(false);
  const button = useRef<HTMLButtonElement | null>(null);
  const whyId = useId();
  if (view.open) return <span className="private-switch private-switch-on">Private view: on</span>;
  if (!view.mayOpen) {
    const why = view.why || "Your office doesn't open restricted material.";
    return (
      <span className="private-switch private-switch-disabled">
        <button type="button" disabled aria-describedby={whyId}>Private view: off</button>
        <span id={whyId} className="private-why" title={why}>{why}</span>
      </span>
    );
  }
  const close = () => { setAsking(false); button.current?.focus(); };
  return (
    <span className="private-switch">
      <button type="button" ref={button} aria-expanded={asking} onClick={() => setAsking((a) => !a)}>Private view: off</button>
      {asking && <PrivateAsk name={name} onOpen={onOpen} onCancel={close} minutes={view.minutes} initial={view.default} />}
    </span>
  );
}

/** The ask, as the `Confirm` stamp: why (required, logged), how long, and the act in words. Static props only, so a
 * preview can show it. */
export function PrivateAsk({ name, onOpen, onCancel, minutes, initial, autoFocus = true }: {
  name: string; onOpen: (body: PrivateOpenBody) => Promise<void> | void; onCancel: () => void;
  minutes?: readonly number[]; initial?: number; autoFocus?: boolean;
}) {
  const lengths = minutes?.length ? minutes : PRIVATE_MINUTES;
  const [reason, setReason] = useState("");
  const [length, setLength] = useState<number>(initial && lengths.includes(initial) ? initial : PRIVATE_DEFAULT);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const field = useRef<HTMLInputElement | null>(null);
  const hintId = useId();
  const errorId = useId();
  const fieldId = useId();
  useEffect(() => { if (autoFocus) field.current?.focus(); }, [autoFocus]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const said = reason.split(/\s+/).filter(Boolean).join(" ");
    if (!said) {
      setError("Say why you open it: a short phrase. It's logged.");
      field.current?.focus();
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onOpen({ reason: said, minutes: length });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  const onKeyDown = (e: KeyboardEvent<HTMLFormElement>) => {
    if (e.key === "Escape") { e.preventDefault(); onCancel(); }
  };
  return (
    <form className="confirm private-ask" role="group" aria-label="Open the private view" onSubmit={submit} onKeyDown={onKeyDown} noValidate>
      <span className="confirm-label" aria-hidden="true">Private view</span>
      <p className="private-ask-lead">Restricted material is shown until it closes. Opening it is logged with your name and reason.</p>
      <label htmlFor={fieldId} className="private-ask-label">Why</label>
      <input id={fieldId} ref={field} type="text" value={reason} maxLength={120} required aria-required="true"
        aria-invalid={error ? true : undefined} aria-describedby={`${hintId}${error ? ` ${errorId}` : ""}`}
        onChange={(e) => setReason(e.target.value)} disabled={busy} autoComplete="off" />
      <span id={hintId} className="muted private-ask-hint">{PRIVATE_HINT}</span>
      <fieldset className="private-ask-minutes" disabled={busy}>
        <legend>For</legend>
        {lengths.map((m) => (
          <label key={m}>
            <input type="radio" name="private-minutes" value={m} checked={length === m} onChange={() => setLength(m)} /> {m} minutes
          </label>
        ))}
      </fieldset>
      {error && <p id={errorId} className="private-ask-error" role="alert">{error}</p>}
      <div className="row wrap">
        <button type="submit" className="primary" disabled={busy}>Open the private view as {name || "yourself"} for {length} minutes</button>
        <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </form>
  );
}

export interface PrivateBandProps {
  /** The open private view (`until`, `reason`). */
  view: PrivateView;
  /** Close it: `DELETE /api/private`. */
  onClose: () => Promise<void> | void;
  /** Its time is up: the page reloads, so the server says it expired and the screens fetch without it. */
  onExpired?: () => void;
  /** Move focus to the band's heading (right after it was opened). */
  focus?: boolean;
  /** The clock (tests and previews). */
  now?: () => Date;
}

/** The band across the console, under the header, while the private view is open: hatched in the warning tone and
 * in words, never colour alone. "Private view — restricted material is shown — for REASON — until 21:15 (12 min left)"
 * and "Close private view". The countdown is not announced; a polite line says once when five minutes are left, and
 * again when it closes. */
export function PrivateBand({ view, onClose, onExpired, focus = false, now = () => new Date() }: PrivateBandProps) {
  const [at, setAt] = useState<Date>(now);
  const [said, setSaid] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement | null>(null);
  const warned = useRef(false);
  const clock = useRef(now);
  clock.current = now;
  const expired = useRef(onExpired);
  expired.current = onExpired;
  const left = minutesLeft(view.until, at);

  useEffect(() => { if (focus) heading.current?.focus(); }, [focus]);
  useEffect(() => {
    const id = setInterval(() => setAt(clock.current()), TICK_MS);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    if (left <= 0) {
      setSaid("The private view has closed.");
      const id = setTimeout(() => expired.current?.(), 1500);    // time for the line to be read
      return () => clearTimeout(id);
    }
    if (left <= SOON && !warned.current) {
      warned.current = true;
      setSaid(`The private view closes in ${left} minute${left === 1 ? "" : "s"}.`);
    }
    return undefined;
  }, [left]);

  const close = async () => {
    setBusy(true);
    setError("");
    setSaid("Closing the private view.");
    try {
      await onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSaid("");
    } finally {
      setBusy(false);
    }
  };
  const until = clockTime(view.until);
  return (
    <section className="private-band" role="region" aria-label="Private view">
      <div className="private-band-inner">
        <h2 ref={heading} tabIndex={-1} className="private-band-heading">
          <span className="private-band-word">Private view</span>
          <span> — restricted material is shown</span>
          {view.reason && <span> — for {view.reason}</span>}
          {left > 0
            ? <span> — until <time dateTime={view.until}>{until}</time> ({left} min left)</span>
            : <span> — closed</span>}
        </h2>
        <button type="button" className="private-band-close" onClick={() => void close()} disabled={busy}>Close private view</button>
      </div>
      {error && <p className="private-band-error" role="alert">{error}</p>}
      <p className="visually-hidden" aria-live="polite">{said}</p>
    </section>
  );
}
