import { useEffect, useId, useState, type ReactNode } from "react";
import { Badge } from "./Badge";
import { Caveats } from "./Caveats";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { DataTable, type Column } from "./DataTable";
import { ErrorNotice, Loading } from "./States";
import { Tabs } from "./Tabs";
import { cleanName, signerProblem } from "../lib/approvals";
import {
  LOCATED_NOT_PIN, countyName, dayText, isMissing, isPending, locateDocuments, locatedPath, questionSubject, useKeptJson,
  type JobRef, type LocatedDoc, type LocatedItem, type Location, type LocationResult,
} from "../lib/discovery";

/** The tie as a word badge: a strong tie (it names the association, or was recorded with its documents) and the
 * builder's filing, which may be another community's. The word carries the meaning; the tone only repeats it. */
export function TieBadge({ doc }: { doc: LocatedDoc }) {
  return (
    <span className="row wrap tie">
      <Badge tone={doc.strong ? "neutral" : "warn"}>{doc.tie_label || doc.tie}</Badge>
      {!doc.strong && <span className="muted">may be another community's</span>}
    </span>
  );
}

function When({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="muted">undated</span>;
  return <time dateTime={iso.slice(0, 10)}>{dayText(iso)}</time>;
}

const docColumns: Column<LocatedDoc>[] = [
  { key: "number", header: "Document", render: (x) => <code className="chip">{x.number}</code> },
  { key: "recorded", header: "Recorded", kind: "date", value: (x) => x.recorded ?? "", render: (x) => <When iso={x.recorded} /> },
  { key: "filing", header: "Filing" },
  { key: "tie", header: "Why it is thought the association's", value: (x) => `${x.strong ? 0 : 1} ${x.tie_label}`, render: (x) => <TieBadge doc={x} /> },
  { key: "via", header: "Found by", render: (x) => x.via ? <span>{x.via}</span> : <span className="muted">its name</span> },
  { key: "parties", header: "Parties", value: (x) => x.parties.join("; "), render: (x) => x.parties.length ? x.parties.join("; ") : <span className="muted">none kept</span> },
];

function tieCounts(docs: readonly LocatedDoc[]): string {
  const strong = docs.filter((x) => x.strong).length, weak = docs.length - strong;
  return [strong && `${strong} strong ${strong === 1 ? "tie" : "ties"}`, weak && `${weak} the builder's ${weak === 1 ? "filing" : "filings"}`].filter(Boolean).join(" · ");
}

/** One checklist item: the question for the board, the stakes, and the documents located for it. */
function ItemGroup({ it, questionHref }: { it: LocatedItem; questionHref?: (item: string) => string | undefined }) {
  const uid = useId();
  const href = questionHref?.(it.item);
  return (
    <section className="locator-item stack-sm" aria-labelledby={`${uid}-h`}>
      <div className="row wrap">
        <h4 id={`${uid}-h`}>{it.title}</h4>
        <span className="muted">{it.located.length} located{it.located.length ? `: ${tieCounts(it.located)}` : ""}</span>
        {it.stakes && <Badge tone="warn">a second person confirms</Badge>}
      </div>
      <p className="locator-question">{it.question}{/copy/i.test(it.question) ? "" : " Do you hold a copy of each?"}</p>
      <DataTable rows={it.located} columns={docColumns} searchable={false} rowKey={(x) => x.number} caption={`${it.title}: documents located, oldest first`} />
      <p className="muted">
        Answered in the onboarding questions as <code className="chip">{questionSubject(it.item)}</code>
        {href && <> · <a href={href}>Answer it</a></>}
        {it.stakes ? ". The answer decides which words are in force, so a second person confirms it." : "."}
      </p>
    </section>
  );
}

/** The located documents, grouped by checklist item: the header (association, county, when, searches, liens counted),
 * each item's question and documents, what was not located with its ask, the notes, and the caveats. */
export function LocatedDocuments({ location, questionHref, actions }: {
  location: Location; questionHref?: (item: string) => string | undefined; actions?: ReactNode;
}) {
  const d = location;
  const count = d.items.reduce((n, it) => n + it.located.length, 0);
  return (
    <div className="stack locator">
      <header className="stack-sm">
        <h3 className="locator-title">Recorded documents located for {d.association}</h3>
        <p className="muted">
          Read from the {countyName(d.county)} recorder's public index{d.located_at ? <>, <When iso={d.located_at} /></> : null}
          {" · "}{d.searches.toLocaleString("en-US")} {d.searches === 1 ? "search" : "searches"}
          {" · "}{count} {count === 1 ? "document" : "documents"} in {d.items.length} checklist {d.items.length === 1 ? "item" : "items"}
          {d.liens > 0 && <> · {d.liens.toLocaleString("en-US")} of the association's own assessment liens and releases, counted, not listed</>}
        </p>
        {d.spellings.length > 0 && (
          <details>
            <summary>Searched under {d.spellings.length} {d.spellings.length === 1 ? "spelling" : "spellings"}</summary>
            <ul className="assoc-spellings">{d.spellings.map((s) => <li key={s}><code className="chip">{s}</code></li>)}</ul>
          </details>
        )}
        <p className="muted">
          <strong>Ties.</strong> "Names the association" and "recorded with the association's documents" are strong ties.
          "The builder's filing" may be another community's: it is asked about, never suggested. Owners' names are never kept.
        </p>
        {actions}
      </header>
      {d.items.length === 0 && <p className="muted">None located under the association's names or beside its documents.</p>}
      {d.items.map((it) => <ItemGroup key={it.item} it={it} questionHref={questionHref} />)}
      {d.not_located.length > 0 && (
        <section className="stack-sm" aria-label="Not located">
          <h4>Not located</h4>
          <ul className="locator-asks">
            {d.not_located.map((n) => <li key={n.item}><strong>{n.title}.</strong> {n.ask}</li>)}
          </ul>
        </section>
      )}
      {d.notes.length > 0 && (
        <section className="stack-sm" aria-label="Notes">
          <h4>Notes</h4>
          <ul className="muted">{d.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </section>
      )}
      <Caveats items={[LOCATED_NOT_PIN, ...d.caveats.filter((c) => c !== LOCATED_NOT_PIN)]} />
    </div>
  );
}

/** The board's list: the same documents as a checklist the board marks on paper (we hold a copy, order a copy).
 * Print-friendly; the page records no mark. */
export function BoardList({ location }: { location: Location }) {
  const d = location;
  return (
    <div className="board-list stack">
      <div className="row wrap no-print">
        <button type="button" onClick={() => window.print()}>Print the board's list</button>
        <span className="muted">Marks on the printed list are the board's. The page records none; the answers go in the onboarding questions.</span>
      </div>
      <h3>Recorded documents located for {d.association}</h3>
      <p>
        From the {countyName(d.county)} recorder's public index{d.located_at ? `, ${dayText(d.located_at)}` : ""}. For each document,
        mark whether the association holds a copy or should order one.
      </p>
      {d.items.map((it) => (
        <section key={it.item} className="board-list-item">
          <h4>{it.title}{it.stakes ? " (a second person confirms)" : ""}</h4>
          <p><strong>Ask:</strong> {it.question}{/copy/i.test(it.question) ? "" : " Do you hold a copy of each?"}</p>
          <table>
            <caption className="visually-hidden">{it.title}: mark each document</caption>
            <thead>
              <tr><th scope="col">Document</th><th scope="col">Recorded</th><th scope="col">Filing</th><th scope="col">Why</th><th scope="col">We hold a copy</th><th scope="col">Order a copy</th></tr>
            </thead>
            <tbody>
              {it.located.map((x) => (
                <tr key={x.number}>
                  <td>{x.number}</td>
                  <td className="date">{x.recorded ? dayText(x.recorded) : "undated"}</td>
                  <td>{x.filing}</td>
                  <td>{x.tie_label}{x.via ? ` (${x.via})` : ""}</td>
                  <td className="board-box"><span aria-hidden="true">☐</span><span className="visually-hidden">to mark on paper</span></td>
                  <td className="board-box"><span aria-hidden="true">☐</span><span className="visually-hidden">to mark on paper</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {d.not_located.length > 0 && (
        <section className="board-list-item">
          <h4>Not located</h4>
          <ul>{d.not_located.map((n) => <li key={n.item}><strong>{n.title}.</strong> {n.ask}</li>)}</ul>
        </section>
      )}
      <p className="muted">{LOCATED_NOT_PIN}</p>
    </div>
  );
}

/** The queued job in words, announced without moving focus. */
function JobLine({ job, pollMs }: { job: JobRef; pollMs: number }) {
  const secs = Math.max(1, Math.round(pollMs / 1000));
  if (isPending(job))
    return (
      <p className="notice" role="status">
        {job.status === "running" ? "Running" : "Queued"}: job <code className="chip">{String(job.id)}</code>. jason reads the
        county's public index in the background; this page checks again every {secs} {secs === 1 ? "second" : "seconds"}.
        {" "}<a href="#/jobs">Open the job queue</a>
      </p>
    );
  if (job.status === "failed" || job.status === "cancelled")
    return (
      <p className="notice notice-error" role="alert">
        Job <code className="chip">{String(job.id)}</code> {job.status === "failed" ? "failed" : "was cancelled"}. Nothing was
        located. <a href="#/jobs">Read its log in the job queue</a>, or run the command below in a terminal.
      </p>
    );
  return null;
}

/** The "Locate documents" action: a named person queues the read job, behind `Confirm`. With writes off, the command. */
function LocateAction({ county, name, me, command, label, onQueued }: {
  county: string; name: string; me: string; command: string; label: string; onQueued: (job: JobRef) => void;
}) {
  const uid = useId();
  const [by, setBy] = useState(me);
  useEffect(() => setBy(me), [me]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [writesOff, setWritesOff] = useState("");
  const who = cleanName(by);
  const problem = signerProblem(who);
  const where = `the ${countyName(county || "county")} recorder's public index`;
  const go = async () => {
    setBusy(true);
    setError("");
    const out = await locateDocuments({ county, name, by: who }, command);
    setBusy(false);
    if (out.queued) onQueued(out.job);
    else if (out.writesOff) setWritesOff(out.command || command);
    else setError(out.error);
  };
  if (writesOff)
    return (
      <div className="stack-sm">
        <p className="notice" role="status">Writes are off in this console, so it cannot queue the job. Nothing was queued. A person runs it in a terminal:</p>
        <Command cmd={writesOff} note="Read-only against the county. It keeps each item located as an onboarding question." />
      </div>
    );
  return (
    <div className="stack-sm locator-action">
      <div className="row wrap">
        <label className="approve-field">Queued by<input value={by} onChange={(e) => setBy(e.target.value)} autoComplete="name" required aria-describedby={`${uid}-why`} /></label>
        {problem ? (
          <button type="button" className="primary" aria-disabled="true" aria-describedby={`${uid}-why`}>{label}</button>
        ) : (
          <Confirm busy={busy} label="Queue" onConfirm={go} summary={
            <p>Queue a read of {where} for {name || "the active community"}, as {who}. jason searches by its names, beside its
              documents, and by its builder; nothing is written to the county, PayHOA, or the profile. Each item located
              becomes an onboarding question.</p>
          }>{label}</Confirm>
        )}
        <span id={`${uid}-why`} className="muted" role="status">{problem && by ? problem : ""}</span>
      </div>
      {error && <p className="notice notice-error" role="alert">jason could not queue the job: {error}. Nothing was queued.</p>}
    </div>
  );
}

/** Locate an association's recorded documents and show them: the active community's with no `county` and `name`,
 * another's with both. Missing shows the tool's note, its command, and "Locate documents", which queues a read job
 * (`POST /api/write/documents-located/locate`, as a named person, behind `Confirm`); with writes off it shows the
 * command instead. While a job is queued or running the page reads the result again every `pollMs`. A located
 * document is a lead, not a pin; the answers go through the onboarding questions (`questionHref` links to one). */
export function DocumentLocator({ county, name, me = "", pollMs = 4000, questionHref }: {
  county?: string; name?: string; me?: string; pollMs?: number; questionHref?: (item: string) => string | undefined;
}) {
  // The job this page queued, and the result's date when it was queued: a newer result without a job field ends it.
  const [queued, setQueued] = useState<{ job: JobRef; base: string } | null>(null);
  const path = locatedPath(county, name);
  useEffect(() => setQueued(null), [path]);
  const r = useKeptJson<LocationResult>(path, { pollMs, poll: (d) => isPending(d.job ?? queued?.job) });
  const [view, setView] = useState("items");
  const data = r.data;
  useEffect(() => {
    if (queued && data && !isMissing(data) && !data.job && data.located_at !== queued.base) setQueued(null);
  }, [data, queued]);

  if (r.data === undefined) {
    if (r.error) return <ErrorNotice error={`jason could not read the documents located: ${r.error}`} onRetry={r.reload} />;
    return <Loading label="Reading the documents located…" />;
  }
  const d = r.data;
  const job = d.job ?? queued?.job ?? null;
  const onQueued = (j: JobRef) => { setQueued({ job: j, base: isMissing(d) ? "" : d.located_at }); r.reload(); };
  const errorLine = r.error ? <ErrorNotice error={`jason could not read the documents located again: ${r.error}`} onRetry={r.reload} /> : null;

  if (isMissing(d)) {
    return (
      <div className="stack-sm locator">
        <p>{d.note || "No documents located yet."}</p>
        {job && <JobLine job={job} pollMs={pollMs} />}
        {!isPending(job) && (
          <>
            <LocateAction county={county ?? ""} name={name ?? ""} me={me} command={d.command} label="Locate documents" onQueued={onQueued} />
            {d.command && <Command cmd={d.command} note="The same read from a terminal. The page never runs a command." />}
          </>
        )}
        {errorLine}
        <Caveats items={[LOCATED_NOT_PIN]} />
      </div>
    );
  }
  return (
    <div className="stack-sm">
      {job && <JobLine job={job} pollMs={pollMs} />}
      {errorLine}
      <Tabs active={view} onChange={setView} tabs={[
        { id: "items", label: "By checklist item", content: (
          <LocatedDocuments location={d} questionHref={questionHref} actions={!isPending(job) && (
            <details className="no-print">
              <summary>Read the index again</summary>
              <LocateAction county={county ?? d.county} name={name ?? d.association} me={me} command="" label="Locate documents again" onQueued={onQueued} />
            </details>
          )} />
        ) },
        { id: "board", label: "The board's list", content: <BoardList location={d} /> },
      ]} />
    </div>
  );
}
