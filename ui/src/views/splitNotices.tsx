import { useEffect, useId, useRef, useState } from "react";
import { Glyph } from "../components/Glyph";
import { PrivateAsk } from "../components/PrivateSwitch";
import { serverSession, type PrivateView } from "../lib/api";
import { privateActs } from "../lib/session";
import type { Busy } from "./splitApi";

/** The splitter's calm notices for the three things the server can say that are not a failure (docs/pdf-splitter.md, sections 6.7 and 8.1):
 * a confidential file whose page text is withheld, a library that could not be read just now, and a plan that changed after it was reviewed.
 * Each is words first, with a glyph and a left rule as the second cue (never colour alone), in the page's ink so it reads at the same
 * contrast in light, dark, and forced colours. A notice never shows what the server withheld: it only says that it did. */

export const BUSY_SENTENCE = "The library could not be read just now. Nothing was changed.";
export const HELD_SENTENCE = "This file is confidential: page text, titles and reasons are hidden until the private view is open.";
export const CHANGED_SENTENCE = "The draft changed since you reviewed it: the plan is now different. Review it again.";
export const DUPLICATES_SKIPPED_SENTENCE = "The duplicate check was skipped because the library was busy; apply will refuse until it can run.";

/** Whole seconds left, counting down once a second from `from`, starting over whenever `run` changes. Reaches 0 and stays there. */
export function useCountdown(from: number, run: unknown): number {
  const [left, setLeft] = useState(from);
  useEffect(() => {
    setLeft(from);
    if (from <= 0) return;
    const t = setInterval(() => setLeft((n) => (n <= 1 ? (clearInterval(t), 0) : n - 1)), 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, run]);
  return left;
}

export const secondsWords = (n: number): string => `${n} ${n === 1 ? "second" : "seconds"}`;

/** "The library could not be read just now. Nothing was changed." with a Try again button that waits out the server's Retry-After and says so in
 * words (the button's own label counts down; it is not a live region, so the count is not read out a second at a time). One polite line says,
 * once, when the wait is over. `again` changes whenever the same failure comes back, so the wait starts again. */
export function BusyNotice({ busy, onRetry, working = false, again = 0 }: { busy: Busy; onRetry(): void; working?: boolean; again?: number }) {
  const left = useCountdown(busy.retryAfter, again);
  const [ready, setReady] = useState("");
  const waited = useRef(busy.retryAfter > 0);
  useEffect(() => {
    waited.current = busy.retryAfter > 0;
    setReady("");
  }, [busy.retryAfter, again]);
  useEffect(() => { if (left === 0 && waited.current) setReady("You can try again now."); }, [left]);
  const detail = busy.message && busy.message !== BUSY_SENTENCE ? busy.message : "";
  return (
    <div className="split-note split-busy" data-note="busy" aria-label="The library is busy" role="group">
      <p role="status"><Glyph name="hourglass" size={14} /> <strong>{BUSY_SENTENCE}</strong></p>
      {detail && <p className="muted" data-detail>{detail}</p>}
      <p className="row wrap">
        <button type="button" onClick={onRetry} disabled={left > 0 || working}>
          {working ? "Trying again…" : left > 0 ? `Try again in ${secondsWords(left)}` : "Try again"}
        </button>
        {left > 0 && <span className="muted" aria-hidden="true">The server asked for {secondsWords(busy.retryAfter)} between tries.</span>}
      </p>
      <p className="sr-only" role="status" data-ready>{ready}</p>
    </div>
  );
}

/** A way into the private view from a confidential file's notice: the same ask the console's header makes (why, and for how long), for a person
 * whose office opens it; the server's reason, in words, for one whose office does not. The page reloads when it opens, so every screen asks again. */
export function PrivateViewLink({ by = "" }: { by?: string }) {
  const [view, setView] = useState<PrivateView | null | undefined>(undefined);
  const [asking, setAsking] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const whyId = useId();
  useEffect(() => {
    let live = true;
    serverSession().then((s) => { if (live) setView(s.private ?? null); }, () => { if (live) setView(null); });
    return () => { live = false; };
  }, []);
  if (view === undefined) return null;
  if (view === null) return <p className="muted" data-private="none">The private view opens from the switch in the console's header, for a person whose office may open it.</p>;
  if (view.open) return <p className="muted" data-private="open">The private view is open.</p>;
  if (!view.mayOpen) {
    return (
      <p className="muted" data-private="refused" id={whyId}>
        <Glyph name="lock" size={12} /> The private view is not open to your office{view.why ? `: ${view.why}` : "."}
      </p>
    );
  }
  const close = () => { setAsking(false); button.current?.focus(); };
  return (
    <div data-private="may">
      <button type="button" ref={button} aria-expanded={asking} onClick={() => setAsking((a) => !a)}>Open the private view…</button>
      {asking && <PrivateAsk name={by} onOpen={privateActs.open} onCancel={close} minutes={view.minutes} initial={view.default} />}
    </div>
  );
}

/** A confidential file whose page text the server withheld (`masked`, `confidentialWhy`). Numbers, states and the pictures' places stay on screen;
 * the page text, titles and the reasons behind a suggestion do not. When the library could not be asked, the server treats the file as confidential
 * until it can be, says so (`why`), and `onCheckAgain` asks again. */
export function ConfidentialNotice({ why = "", known = true, onCheckAgain, compact = false, by = "" }: {
  why?: string; known?: boolean; onCheckAgain?(): void; compact?: boolean; by?: string;
}) {
  return (
    <section className="split-note split-held" data-note="held" role="note" aria-label="This file is confidential">
      <p><Glyph name="file-lock" size={14} /> <strong>{HELD_SENTENCE}</strong>{!compact && <> Page numbers, counts and states are still shown.</>}</p>
      {!known && why && <p data-detail>{why}</p>}
      {!known && onCheckAgain && <p><button type="button" onClick={onCheckAgain}>Check again</button></p>}
      {!compact && <PrivateViewLink by={by} />}
    </section>
  );
}

/** The plan changed after the person reviewed it: said in words, with the server's own sentence below (verbatim). The review above it is the new one. */
export const ChangedNotice = ({ detail, headingRef }: { detail: string; headingRef?: React.RefObject<HTMLHeadingElement> }) => (
  <section className="split-note split-changed" data-note="changed" role="group" aria-labelledby="split-changed-h">
    <h3 id="split-changed-h" tabIndex={-1} ref={headingRef}><Glyph name="refresh-cw" size={14} /> {CHANGED_SENTENCE}</h3>
    {detail && <p className="muted" data-detail>{detail}</p>}
    <p>Nothing was written. The review below is the new one; confirm it again to write.</p>
  </section>
);
