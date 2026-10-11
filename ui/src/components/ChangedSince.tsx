import { dayOf, safeAddress, shortHash, type ChangedRow } from "../lib/work";

/** "Changed since": a store moved under a step that was done. It stands above the rail, before anything else on the page, and
 * says which step, what moved, what it was and what it is now; the step reads "changed since" too. Nothing done is silently
 * repeated: a person looks, then reopens the step if it should be done again. Renders nothing when nothing changed. */
export function ChangedSince({ changed, onGo }: { changed: readonly ChangedRow[]; onGo?: (step: string) => void }) {
  if (!changed.length) return null;
  const steps = [...new Set(changed.map((c) => c.step))];
  return (
    <section className="changed-banner work-changed" aria-labelledby="work-changed-h" role="region">
      <h2 id="work-changed-h">Changed since</h2>
      {steps.map((step) => {
        const rows = changed.filter((c) => c.step === step);
        const first = rows[0];
        return (
          <div key={step} className="work-changed-step">
            <p>
              <strong>Step {first.n}, {first.stepTitle || first.step}</strong> was done, and what it was done on has changed
              {first.at ? <> (found {dayOf(first.at)})</> : null}.
              {first.pending && <> This read found it; no event holds it until the run is opened.</>}
              {onGo && <> <button type="button" className="link" onClick={() => onGo(step)}>Go to the step</button></>}
            </p>
            <ul className="changed-list">
              {rows.map((c) => (
                <li key={c.address}>
                  <code className="chip">{safeAddress(c.address)}</code> was <code>{shortHash(c.was)}</code>, now <code>{shortHash(c.now)}</code>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}
