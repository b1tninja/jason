import { useId, useState } from "react";
import { BasisPill } from "./BasisPill";
import { Confirm } from "./Confirm";
import { Glyph } from "./Glyph";
import { StepStateWord } from "./StepStateWord";
import type { Acts } from "./RunActs";
import {
  itemRollUp, itemRows, parseItemLines, postSupplyDry, refusalOf, setWords,
  type Run, type RunClock, type RunStep, type SupplyDry, type WorkViewer,
} from "../lib/work";
import "../styles/work-items.css";

/** An item table shows this many rows, then a button for the rest. */
export const ITEM_FOLD = 50;

/** The items of a step that repeats over a set: one row for each item (its opaque id, its state, its own clock, and the date and
 * the lateness in words), with a roll-up line over them ("3 of 12 done, 2 late"). A step over a set with no items yet says so and
 * what it waits for. A late item is a word with a glyph beside it, never a colour alone. */
export function ItemTable({ step, clocks, empty }: { step: RunStep; clocks: readonly RunClock[]; empty?: string }) {
  const rows = itemRows(step, clocks);
  const [all, setAll] = useState(false);
  const id = useId();
  if (rows.length === 0) {
    if (!step.itemAware) return null;
    return (
      <section className="work-step-part work-items" aria-labelledby={`${id}-h`}>
        <h3 id={`${id}-h`}>Items</h3>
        <p className="work-items-empty" data-empty="true">
          {empty || `No items have been supplied to ${setWords(step.itemSet)} yet. This step waits until some are.`}
        </p>
      </section>
    );
  }
  const shown = all ? rows : rows.slice(0, ITEM_FOLD);
  const timed = rows.some((r) => r.clock);
  return (
    <section className="work-step-part work-items" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`}>Items</h3>
      <p className="work-items-rollup"><strong>{itemRollUp(rows)}</strong></p>
      <div className="work-items-scroll" role="region" aria-label={`Items of step ${step.n}, ${step.title}`} tabIndex={0}>
        <table className="work-items-table">
          <caption className="visually-hidden">
            The {rows.length === 1 ? "item" : `${rows.length} items`} of {step.title}, each with its state{timed ? ", its clock, and when it is due" : ""}.
          </caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">State</th>
              {timed && <th scope="col">Clock</th>}
              {timed && <th scope="col">Due</th>}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.item} data-late={r.late ? "true" : undefined}>
                <th scope="row"><code>{r.item}</code></th>
                <td><StepStateWord state={r.state} /></td>
                {timed && (
                  <td>
                    {r.clock ? <>{r.clock.label || "Clock"} <BasisPill basis={r.clock.basis} label={r.clock.basisLabel} /></> : <span className="muted">no clock</span>}
                  </td>
                )}
                {timed && (
                  <td>
                    {r.clock?.due ? <time dateTime={r.clock.due}>{r.clock.due}</time> : !(r.clock && /no date/.test(r.words)) && <span className="muted">no date</span>}
                    {r.clock ? (
                      <span className={r.late ? "work-item-late" : "muted"}>
                        {" "}{r.late && <Glyph name="triangle-alert" size="1em" />}{r.late ? <strong>{r.words}</strong> : r.words}
                      </span>
                    ) : null}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > ITEM_FOLD && (
        <button type="button" className="work-items-more" aria-expanded={all} onClick={() => setAll((v) => !v)}>
          {all ? `Show the first ${ITEM_FOLD}` : `Show all ${rows.length} items`}
        </button>
      )}
    </section>
  );
}

/** The check-then-record form that gives an item set more items: the ids one to a line, an optional record. "Check the list"
 * asks the server to make every check a real supply makes and writes nothing, and shows its sentence when it refuses (an id is an
 * opaque handle, never a name or an address); only then does a `Confirm` record it, under the signed-in name, as a note on the
 * run. Edit the list and the check is asked again. */
export function SupplyItems({ step, run, viewer, acts, setName }: {
  step: Pick<RunStep, "n" | "title">; run: Pick<Run, "definition" | "id">; viewer: WorkViewer; acts: Acts; setName: string;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [record, setRecord] = useState("");
  const [checked, setChecked] = useState<{ text: string; dry: SupplyDry } | null>(null);
  const [refused, setRefused] = useState("");
  const [checking, setChecking] = useState(false);
  const items = parseItemLines(text);
  const ready = checked && checked.text === text && !refused;
  const by = viewer.name || "the signed-in person";

  const check = async () => {
    setChecking(true);
    setRefused("");
    try {
      const dry = await postSupplyDry(run.definition, run.id, { set: setName, items, ...(record.trim() ? { record: record.trim() } : {}) });
      setChecked({ text, dry });
    } catch (e) {
      setChecked(null);
      setRefused(refusalOf(e).text);
    } finally {
      setChecking(false);
    }
  };
  const record_ = async () => {
    if (await acts.send({ act: "supply-items", set: setName, items, ...(record.trim() ? { record: record.trim() } : {}) })) {
      setText("");
      setRecord("");
      setChecked(null);
    }
  };
  const dry = ready ? checked.dry : null;
  const fresh = dry ? dry.wouldAdd.length : 0;

  return (
    <section className="work-step-part work-supply" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`}>Supply items</h3>
      <div className="work-text-confirm stack-sm">
        <label htmlFor={`${id}-ids`}>Item ids for {setWords(setName)}, one to a line</label>
        <textarea id={`${id}-ids`} rows={4} value={text} aria-describedby={`${id}-hint`} spellCheck={false}
          onChange={(e) => { setText(e.target.value); setRefused(""); }} />
        <p id={`${id}-hint`} className="muted">
          An item id is an opaque handle: letters, digits, and : _ . # / - only, up to 64 characters. Never a name or an address.
        </p>
        <label htmlFor={`${id}-record`}>The record that shows them (optional)</label>
        <input id={`${id}-record`} type="text" value={record} onChange={(e) => { setRecord(e.target.value); setChecked(null); }} />
        <div className="row wrap">
          <button type="button" onClick={() => void check()} disabled={items.length === 0 || checking || acts.busy}>Check the list</button>
          <span className="muted">{items.length === 0 ? "Type at least one id." : `${items.length} ${items.length === 1 ? "id" : "ids"} typed.`}</span>
        </div>
        {refused && <p role="alert" className="notice notice-error work-said">{refused}</p>}
        {dry && (
          <>
            <p role="status" className="notice work-said">
              <Glyph name="circle-check" size="1em" /> The list passes the checks. {fresh} new {fresh === 1 ? "item" : "items"} would be added
              {dry.alreadyThere.length > 0 ? `; ${dry.alreadyThere.length} already in the set (${dry.alreadyThere.join(", ")})` : ""}. Nothing is recorded yet.
            </p>
            {fresh > 0 || dry.withDates.length > 0 ? (
              <Confirm busy={acts.busy} label="Supply"
                summary={<>Supply {fresh} new {fresh === 1 ? "item" : "items"} to {setWords(setName)} for step {step.n}, {step.title}, under the name {by}
                  {record.trim() ? <>, with the record: <q>{record.trim()}</q></> : null}. It is one note on the run's history; items are never removed, only skipped.</>}
                onConfirm={() => void record_()}>
                Supply {fresh} {fresh === 1 ? "item" : "items"}
              </Confirm>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

/** The two sentences about a remedy: on the step that remedies a failed check, and on the failed check itself. The check stays
 * recorded as failed either way. */
export function RemedyNote({ step, steps, onGo }: {
  step: Pick<RunStep, "remedy" | "remedyOf">; steps: readonly Pick<RunStep, "id" | "n" | "title">[]; onGo?: (id: string) => void;
}) {
  const named = (sid: string | undefined) => steps.find((s) => s.id === sid);
  const check = named(step.remedyOf);
  const fix = named(step.remedy);
  if (!step.remedyOf && !step.remedy) return null;
  return (
    <>
      {step.remedyOf && (
        <p className="notice work-remedy" role="note" data-remedy="of">
          <Glyph name="info" size="1em" />
          <span className="work-remedy-body">
            This step is the remedy for the failed check above; the check stays recorded as failed.
            {check && onGo ? <> <button type="button" onClick={() => onGo(check.id)}>Go to the check: step {check.n}, {check.title}</button></> : null}
          </span>
        </p>
      )}
      {step.remedy && (
        <p className="notice notice-warn work-remedy" role="note" data-remedy="by">
          <Glyph name="triangle-alert" size="1em" />
          <span className="work-remedy-body">
            This check failed and stays recorded as failed. {fix ? `Step ${fix.n}, ${fix.title}, is its remedy and is open, so the run goes on there.` : "A remedy step is open, so the run goes on there."}
            {fix && onGo ? <> <button type="button" onClick={() => onGo(fix.id)}>Go to the remedy</button></> : null}
          </span>
        </p>
      )}
    </>
  );
}
