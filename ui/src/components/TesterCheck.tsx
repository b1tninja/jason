import { Pill } from "./Pill";
import { LIST_MEANINGS, listIsOld, testerSummary, type TesterCheck as TesterCheckData } from "../lib/inspections";

const GLYPH = { listed: "circle-check", "listed under another business": "info", "not listed": "circle-dashed", "not fetched": "circle-question-mark" } as const;

/** Whether a tester printed on a report is on the lists jason holds, each as "listed on the list dated D". It never says
 * a tester is approved or credentialed: a list is a dated snapshot and a name on it is a match. A list more than a year
 * old says so, and a list not fetched says nothing about the tester. Contact details are not rendered here at all: the
 * payload says only whether the server masked them (`contactsMasked`). */
export function TesterCheck({ check, today }: { check: TesterCheckData; today?: Date }) {
  const c = check;
  return (
    <section className="insp-tester" aria-label={`Tester check: ${c.tester}`}>
      <header className="row wrap">
        <h3>{c.tester}</h3>
        <Pill word={testerSummary(c.lists)} glyph="info" />
      </header>
      <p className="muted">Name as printed on the report.{c.certificate ? <> Number as printed, not checked: <code className="chip">{c.certificate}</code></> : null}</p>
      <ul className="insp-lists">
        {c.lists.map((l) => {
          const old = l.found !== "not fetched" && listIsOld(l.dated, today);
          return (
            <li key={l.name} data-found={l.found}>
              <strong>{l.name}</strong>{" "}
              <Pill word={l.found} meaning={LIST_MEANINGS[l.found]} glyph={GLYPH[l.found]} />
              <div>
                {l.found === "listed" && <>listed on the list dated {l.dated ?? "(no date)"}{l.id && <> · id {l.id}</>}</>}
                {l.found === "listed under another business" && <>matched on the tester's name, on the list dated {l.dated ?? "(no date)"}{l.id && <> · id {l.id}</>}</>}
                {l.found === "not listed" && <>not on the list dated {l.dated ?? "(no date)"}</>}
                {l.found === "not fetched" && <>not fetched: nothing is said about this list</>}
              </div>
              {old && <p className="notice notice-warn" role="note">This list is dated {l.dated ?? "(no date)"}, more than a year ago. A newer list may differ.</p>}
            </li>
          );
        })}
      </ul>
      <p className="muted">{c.contactsMasked ? "Contact details are masked." : "Contact details are held by the server and are not shown here."} jason does not call the tester.</p>
    </section>
  );
}
