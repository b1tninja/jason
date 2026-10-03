import { useState } from "react";
import { Badge, Card, Evidence, RemoteView } from "../components";
import { useApi } from "../lib/useApi";
import type { Duties, Duty, DutyBrief } from "./types";

const CADENCES = ["monthly", "annual", "every three years", "continuous", "on the event"];

/** The tools a duty names, as chips a person can look up; the words after a comma or space are tool or command names. */
function produces(d: Duty): string[] {
  return d.produce.split(/,\s*/).map((s) => s.trim()).filter(Boolean);
}

function Brief({ anchor, onClose }: { anchor: string; onClose: () => void }) {
  const r = useApi<DutyBrief>(`/api/duties?anchor=${encodeURIComponent(anchor)}`);
  return (
    <Card title={anchor} actions={<button onClick={onClose}>Close</button>}>
      <RemoteView r={r}>
        {(d) => (
          <div className="stack">
            <dl className="kv">
              <dt>Keeps straight</dt><dd>{d.keepsStraight}</dd>
              <dt>Sections</dt><dd>{d.sections}</dd>
              <dt>Artifact</dt><dd>{d.artifact}</dd>
              <dt>When</dt><dd>{d.cadence}: {d.when}</dd>
              <dt>Records</dt><dd>{d.records.map((x) => <Badge key={x}>{x.replace(/_/g, " ")}</Badge>)}</dd>
              <dt>Jason produces</dt><dd><Evidence items={produces(d)} label="" /></dd>
              {d.limit && <><dt>Limit</dt><dd className="notice notice-warn">{d.limit}</dd></>}
            </dl>
            <h3>What the documents say</h3>
            {Object.entries(d.passages).map(([q, hits]) => (
              <details key={q} open={hits.length > 0}>
                <summary>{q} <span className="muted">({hits.length})</span></summary>
                {hits.length === 0 && <p className="muted">nothing found in the extracts</p>}
                {hits.map((h, i) => (
                  <blockquote key={i} className="passage">
                    <p>{h.text}</p>
                    <footer className="muted"><Badge>{h.shelf}</Badge> {h.file} · passage {h.passage}</footer>
                  </blockquote>
                ))}
              </details>
            ))}
            {d.note && <p className="caveats">{d.note}</p>}
          </div>
        )}
      </RemoteView>
    </Card>
  );
}

/** The manager's duties, by cadence. A card is the frame for a duty; its brief is the statute and the documents' own words. */
export function DutiesView() {
  const r = useApi<Duties>("/api/duties");
  const [open, setOpen] = useState<string | null>(null);
  if (open) return <Brief anchor={open} onClose={() => setOpen(null)} />;
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <p className="muted">
            A manager collects, reports, and archives the association's finances and assets; carries out the board's resolutions;
            carries out the governing documents; and administers its contracts, insurance, and vendors (BPC 11500(d)), at the board's direction. Each
            card is one duty; the brief decides nothing.
          </p>
          {CADENCES.map((c) => {
            const rows = d.duties.filter((x) => x.cadence === c);
            if (!rows.length) return null;
            return (
              <section key={c} aria-label={c}>
                <h3 className="cadence">{c}</h3>
                <div className="grid-3">
                  {rows.map((x) => (
                    <article key={x.anchor} className="duty">
                      <h4>
                        <button className="link" onClick={() => setOpen(x.anchor)}>{x.anchor}</button>
                      </h4>
                      <p>{x.keepsStraight}</p>
                      <p className="muted">{x.sections}</p>
                      <p className="muted">{x.when}</p>
                      <Evidence items={produces(x)} label="Tools" />
                      {x.limit && <p className="limit">{x.limit}</p>}
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </RemoteView>
  );
}
