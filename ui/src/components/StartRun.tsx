import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Confirm } from "./Confirm";
import { postStart, refusalOf, type DefinitionRow, type StartAnswer, type StartDry } from "../lib/work";

/** Start a run: a definition (by family), what it is about and its name, and the dates the definition asks for. Each date is
 * checked on the server against the definition's own rule (a dry run that writes nothing); the sentence it gives shows beside
 * the date it is about, the rest below. A definition with a legal clock needs a plain yes. Starting makes a draft: no clock
 * runs until the run is opened. The run is recorded under the signed-in person's name, who is its manager. */
export function StartRun({ definitions, initial = "", by, actingAs = "", onStarted, debounceMs = 300 }: {
  definitions: readonly DefinitionRow[]; initial?: string; by: string; actingAs?: string;
  onStarted: (definition: string, id: string) => void; debounceMs?: number;
}) {
  const uid = useId();
  const [key, setKey] = useState(definitions.some((d) => d.key === initial) ? initial : "");
  const [subject, setSubject] = useState("");
  const [label, setLabel] = useState("");
  const [dates, setDates] = useState<Record<string, string>>({});
  const [yes, setYes] = useState(false);
  const [checked, setChecked] = useState<StartDry | null>(null);
  const [refused, setRefused] = useState<{ text: string; signIn?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const def = definitions.find((d) => d.key === key);
  const families = useMemo(() => [...new Set(definitions.map((d) => d.family))].sort(), [definitions]);
  const touched = !!subject.trim() || Object.values(dates).some(Boolean);
  const latest = useRef(0);

  useEffect(() => {
    if (!def || !touched) { setChecked(null); return; }
    const n = ++latest.current;
    const t = setTimeout(() => {
      postStart<StartDry>({ definition: def.key, subject: subject.trim(), label: label.trim(), dates, yes, dryRun: true }).then(
        (r) => { if (n === latest.current) { setChecked(r); setRefused(null); } },
        (e) => { if (n === latest.current) { setChecked(null); setRefused(refusalOf(e)); } },
      );
    }, debounceMs);
    return () => clearTimeout(t);
  }, [def, subject, label, dates, yes, touched, debounceMs]);

  const problems = checked?.problems ?? [];
  // A sentence belongs to the date it names first ("answer_by may not come before send": the answer-by date); one that names
  // none of them is for the form as a whole.
  const owner = (p: string) => {
    const low = p.toLowerCase();
    let best = { at: Infinity, name: "" };
    for (const d of def?.dates ?? []) {
      for (const w of [d.name, d.label]) {
        const at = w ? low.indexOf(w.toLowerCase()) : -1;
        if (at >= 0 && at < best.at) best = { at, name: d.name };
      }
    }
    return best.name;
  };
  const about = (d: { name: string }) => problems.filter((p) => owner(p) === d.name);
  const used = new Set(problems.filter((p) => owner(p)));
  const rest = problems.filter((p) => !used.has(p) && !(def?.legalClock && /needs yes/.test(p)));
  const missing = (def?.dates ?? []).filter((d) => d.required && !dates[d.name]);
  const ready = !!def && !!subject.trim() && !missing.length && checked?.ok === true && (!def.legalClock || yes);
  const name = by || "the signed-in person";

  const start = async () => {
    if (!def) return;
    setBusy(true);
    setRefused(null);
    try {
      const out = await postStart<StartAnswer>({ definition: def.key, subject: subject.trim(), label: label.trim(), dates, ...(def.legalClock ? { yes: true } : {}) });
      onStarted(out.definition, out.id);
    } catch (e) {
      setRefused(refusalOf(e));
    } finally {
      setBusy(false);
    }
  };

  if (actingAs) {
    return <p className="notice notice-warn" role="alert">Viewing as {actingAs} (admin view): go back to yourself first. A run is started in a person's own name.</p>;
  }
  return (
    <form className="work-start stack" onSubmit={(e) => e.preventDefault()} aria-label="Start a run">
      <div className="work-field">
        <label htmlFor={`${uid}-def`}>What to run</label>
        <select id={`${uid}-def`} value={key} onChange={(e) => { setKey(e.target.value); setDates({}); setChecked(null); setYes(false); }}>
          <option value="">Choose a workflow</option>
          {families.map((f) => (
            <optgroup key={f} label={f}>
              {definitions.filter((d) => d.family === f).map((d) => <option key={d.key} value={d.key}>{d.title}</option>)}
            </optgroup>
          ))}
        </select>
        {def && <p className="muted">{def.steps} steps{def.procedure ? `, built from the procedure ${def.procedure}` : ""}.</p>}
      </div>
      {def && (
        <>
          <div className="work-field">
            <label htmlFor={`${uid}-subject`}>What it is about</label>
            <input id={`${uid}-subject`} type="text" value={subject} onChange={(e) => setSubject(e.target.value)} aria-required="true"
              placeholder={`for example ${def.subjectKind || "campaign"}:KEY`} />
            <p className="muted">A kind and a key, such as <code>{def.subjectKind || "campaign"}:KEY</code>. The run is listed by its name below, never by this.</p>
          </div>
          <div className="work-field">
            <label htmlFor={`${uid}-label`}>Its name (optional)</label>
            <input id={`${uid}-label`} type="text" value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>
          {def.dates.length > 0 && (
            <fieldset className="work-dates">
              <legend>Dates</legend>
              {def.dates.map((d) => {
                const own = about(d);
                return (
                  <div key={d.name} className="work-field">
                    <label htmlFor={`${uid}-${d.name}`}>{d.label || d.name}{d.required ? "" : " (optional)"}</label>
                    <input id={`${uid}-${d.name}`} type="date" value={dates[d.name] ?? ""} aria-required={d.required || undefined}
                      aria-invalid={own.length ? true : undefined} aria-describedby={`${uid}-${d.name}-r`}
                      onChange={(e) => setDates({ ...dates, [d.name]: e.target.value })} />
                    <p id={`${uid}-${d.name}-r`} className={own.length ? "work-date-bad" : "muted"} role={own.length ? "alert" : undefined}>
                      {own.length ? own.join(" ") : d.rule || (dates[d.name] && checked?.ok ? "This date passes its check." : "")}
                    </p>
                  </div>
                );
              })}
            </fieldset>
          )}
          {rest.length > 0 && (
            <ul className="work-problems" role="status" aria-label="What the check found">
              {rest.map((p) => <li key={p}>{p}</li>)}
            </ul>
          )}
          {def.legalClock && (
            <label className="work-yes">
              <input type="checkbox" checked={yes} onChange={(e) => setYes(e.target.checked)} /> Yes: this workflow has a legal clock. I start it knowing the
              law's dates are kept on the run once it is opened.
            </label>
          )}
          {refused && (
            <div role="alert" className="notice notice-error"><span>{refused.text}{refused.signIn && <> <a href={refused.signIn}>Sign in with Google</a></>}</span></div>
          )}
          <p className="muted">The run is recorded under the name {name}, who is its manager. It starts as a draft: no clock runs until it is opened.</p>
          <Confirm busy={busy || !ready} label="Start" onConfirm={() => void start()}
            summary={<>Start a draft run of {def.title} about <code>{subject.trim()}</code> under the name {name}. No clock runs until the run is opened.{def.legalClock ? " The legal-clock yes is recorded with it." : ""}</>}>
            Start the run
          </Confirm>
          {!ready && <p className="muted">{missing.length ? `Still needed: ${missing.map((d) => d.label || d.name).join(", ")}.` : !subject.trim() ? "Say what it is about." : def.legalClock && !yes ? "The legal-clock yes is needed." : checked?.ok === false ? "The check above says what to change." : "Checking the dates."}</p>}
        </>
      )}
    </form>
  );
}
