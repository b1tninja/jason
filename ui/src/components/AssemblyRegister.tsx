import { Discrepancy } from "./Discrepancy";
import { type DocStatic } from "./Doc";
import { EvidenceEntries } from "./EvidenceEntries";
import { NoticeClock } from "./NoticeClock";
import { Pill } from "./Pill";
import { ASSEMBLY_TYPE_WORDS, NOT_READ, TEST_RESULT_MEANINGS, sizeText, type Assembly, type Discrepancy as DiscrepancyData, type NoticeClockData } from "../lib/inspections";

/** The last failed test is newer than the last pass: the device is failed until a pass or a repair says otherwise. */
export const isFailed = (a: Assembly) => !!a.lastFailed && (!a.lastPassed || a.lastFailed > a.lastPassed);

function Device({ a, sources, clock, docProps }: { a: Assembly; sources: string[]; clock?: NoticeClockData; docProps?: DocStatic }) {
  const failed = isFailed(a);
  return (
    <article className="insp-assembly" data-failed={failed ? "true" : undefined} aria-label={`${a.service} ${a.type} ${a.serial}`}>
      <header className="row wrap">
        <strong>{a.service}: {a.type}, {sizeText(a.sizeIn)}</strong>
        <span className="muted" title={ASSEMBLY_TYPE_WORDS[a.type]}>serial {a.serial}</span>
        {failed && <Pill word="failed" meaning="The latest test on record failed and no later pass is on record." glyph="triangle-alert" />}
        {a.ids.length === 0 && <Pill word="no source lists it" meaning="None of the sources checked gives this device an id. A lead, not a finding." glyph="circle-dashed" />}
      </header>
      <p className="muted">{a.location}{a.tag ? ` · ${a.tag}` : ""}{a.account ? ` · ${a.account}` : ""}{a.meter ? ` · ${a.meter}` : ""}</p>
      <div className="table-wrap insp-region" role="region" aria-label={`${a.serial}: the id each source gives it`} tabIndex={0}>
        <table className="insp-stack">
          <thead><tr>{sources.map((s) => <th key={s} scope="col">{s}</th>)}</tr></thead>
          <tbody>
            <tr>
              {sources.map((s) => {
                const id = a.ids.find((i) => i.source === s)?.id;
                return <td key={s} data-label={s}>{id ?? <span className="muted">not listed</span>}</td>;
              })}
            </tr>
          </tbody>
        </table>
      </div>
      <dl className="insp-facts">
        <div><dt>Last passed</dt><dd>{a.lastPassed ? <time dateTime={a.lastPassed}>{a.lastPassed}</time> : <span className="muted">none on record</span>}</dd></div>
        <div><dt>Last failed</dt><dd>{a.lastFailed ? <time dateTime={a.lastFailed}>{a.lastFailed}</time> : <span className="muted">none on record</span>}</dd></div>
        <div><dt>Test due</dt><dd><time dateTime={a.testDue}>{a.testDue}</time></dd></div>
      </dl>
      {failed && clock && <NoticeClock clock={clock} />}
      {a.history.length > 0 && (
        <details>
          <summary>History ({a.history.length})</summary>
          <ul className="insp-history">
            {a.history.map((h) => (
              <li key={`${h.date}-${"address" in h.document ? h.document.address : h.result}`}>
                <time dateTime={h.date}>{h.date}</time>{" "}
                <Pill word={h.result} meaning={TEST_RESULT_MEANINGS[h.result]} glyph={h.result === "not read" ? "circle-question-mark" : undefined} />
                {h.result === "not read" && <span className="muted"> {NOT_READ}: no result is guessed</span>}{" "}
                <EvidenceEntries entries={[h.document]} label="" {...docProps} />
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

/** One row per device: its service, type and size, serial, the id each source gives it (a column per source, never a
 * merged value), last passed and last failed, test due, and its history behind a disclosure. A figure the scan could not
 * be read for shows "not read", never a guess. A device no source has says so. A source count that differs is a
 * `Discrepancy`, shown, not settled. A failed device carries its repair clock when the loader gives one
 * (`repairClocks`, by serial). At 320 px the source columns stack under the device. */
export function AssemblyRegister({ assemblies, discrepancies = [], repairClocks = {}, docProps }: {
  assemblies: readonly Assembly[];
  discrepancies?: readonly DiscrepancyData[];
  repairClocks?: Readonly<Record<string, NoticeClockData>>;
  docProps?: DocStatic;
}) {
  const sources = [...new Set(assemblies.flatMap((a) => a.ids.map((i) => i.source)))];
  return (
    <section className="insp-register" aria-label="Backflow assemblies">
      <h3>Assemblies ({assemblies.length})</h3>
      {discrepancies.map((d) => <Discrepancy key={d.subject} discrepancy={d} docProps={docProps} />)}
      {assemblies.length === 0
        ? <p className="muted">No assembly is on record.</p>
        : <div className="stack insp-devices">{assemblies.map((a) => <Device key={a.serial} a={a} sources={sources} clock={repairClocks[a.serial]} docProps={docProps} />)}</div>}
    </section>
  );
}
