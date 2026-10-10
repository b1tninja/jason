import { Command } from "./Command";
import { type DocStatic } from "./Doc";
import { EvidenceEntries } from "./EvidenceEntries";
import { isCommand, type Discrepancy as DiscrepancyData } from "../lib/inspections";

/** Two or more sources and what each says, each in its own column. jason never picks a side and never merges them. The
 * next step is a command (shown to copy, never run) or a question a person answers. `docProps` passes `Doc`'s static
 * props through (previews and tests). */
export function Discrepancy({ discrepancy: d, docProps }: { discrepancy: DiscrepancyData; docProps?: DocStatic }) {
  return (
    <section className="insp-discrepancy" aria-label={`Sources differ: ${d.subject}`}>
      <h4>{d.subject}</h4>
      <div className="table-wrap insp-region" role="region" aria-label={`${d.subject}: what each source says`} tabIndex={0}>
        <table className="insp-stack">
          <thead><tr>{d.sources.map((s) => <th key={s.source} scope="col">{s.source}</th>)}</tr></thead>
          <tbody>
            <tr>
              {d.sources.map((s) => (
                <td key={s.source} data-label={s.source}>
                  <span>{s.says}</span>
                  {s.doc && <div><EvidenceEntries entries={[s.doc]} label="" {...docProps} /></div>}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="muted">The sources differ. jason does not say which is right.</p>
      {d.next && (isCommand(d.next) ? <><p className="muted">Next step:</p><Command cmd={d.next} /></> : <p>Next step: {d.next}</p>)}
    </section>
  );
}
