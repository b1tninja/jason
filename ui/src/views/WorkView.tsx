import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Caveats, Card, EmptyState, Loading, RunRow, ScreenHeader } from "../components";
import { LinkButton, WorkCrumbs, WorkNav, WorkNotes, WorkProblem } from "../components/WorkParts";
import { StartRun } from "../components/StartRun";
import { useHash } from "../lib/useHash";
import {
  DUE_FILTERS, GROUP_FOLD, GROUP_KEYS, GROUP_TITLES, NO_FILTERS, START_HREF, WORDS, asOfDate, headingLine, parseRoute, runHref, workDefinitionsUrl, workUrl,
  useWorkApi, useWorkViewer,
  type DefinitionsPage, type GroupKey, type WorkFilters, type WorkPage, type WorkRow,
} from "../lib/work";
import { WorkDefinitionsView } from "./WorkDefinitionsView";
import { WorkRunView } from "./WorkRunView";
import "../styles/work.css";

const WHOSE_WORDS: Record<string, string> = { jason: "jason", scheduler: "the scheduler", anyone: "anyone signed in" };

/** One group of the list, folded after five rows with its count. */
function Group({ k, rows, today }: { k: GroupKey; rows: WorkRow[]; today?: Date }) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, GROUP_FOLD);
  const id = useId();
  return (
    <section className="card work-group" aria-labelledby={`${id}-h`} data-group={k}>
      <header className="card-head">
        <h2 id={`${id}-h`}>{GROUP_TITLES[k]} <span className="work-group-count muted">{rows.length} {rows.length === 1 ? "run" : "runs"}</span></h2>
      </header>
      <ul className="work-rows" aria-label={GROUP_TITLES[k]}>
        {shown.map((r) => <RunRow key={`${r.definition}-${r.id}`} row={r} today={today} />)}
      </ul>
      {rows.length > GROUP_FOLD && (
        <button type="button" className="work-fold" aria-expanded={all} onClick={() => setAll((v) => !v)}>
          {all ? `Show the first ${GROUP_FOLD}` : `Show all ${rows.length} runs`}
        </button>
      )}
    </section>
  );
}

function Filters({ f, page, onChange }: { f: WorkFilters; page: WorkPage | null; onChange: (next: WorkFilters) => void }) {
  const uid = useId();
  const [q, setQ] = useState(f.q);
  useEffect(() => setQ(f.q), [f.q]);
  useEffect(() => {
    if (q === f.q) return;
    const t = setTimeout(() => onChange({ ...f, q }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  const whose = f.mine ? "mine" : f.role;
  return (
    <form className="work-filters row wrap" role="search" aria-label="Filter the runs" onSubmit={(e) => e.preventDefault()}>
      <label htmlFor={`${uid}-def`}>Workflow</label>
      <select id={`${uid}-def`} value={f.definition} onChange={(e) => onChange({ ...f, definition: e.target.value })}>
        <option value="">All workflows</option>
        {(page?.definitions ?? []).map((d) => <option key={d.key} value={d.key}>{d.title}</option>)}
      </select>
      <label htmlFor={`${uid}-who`}>Whose move</label>
      <select id={`${uid}-who`} value={whose} onChange={(e) => {
        const v = e.target.value;
        onChange({ ...f, mine: v === "mine", role: v === "mine" ? "" : v });
      }}>
        <option value="">Anyone's</option>
        <option value="mine">Mine</option>
        {(page?.roles ?? []).map((r) => <option key={r} value={r}>{WHOSE_WORDS[r] ?? `the ${r}`}</option>)}
      </select>
      <label htmlFor={`${uid}-due`}>Due</label>
      <select id={`${uid}-due`} value={f.due} onChange={(e) => onChange({ ...f, due: e.target.value })}>
        <option value="">Any date</option>
        {DUE_FILTERS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
      </select>
      <label htmlFor={`${uid}-q`}>Search</label>
      <input id={`${uid}-q`} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
    </form>
  );
}

/** The open runs, in four groups: Yours, Waiting on others, Waiting on a clock, The board. A run shows once, in the group of its
 * most pressing open step; the loader orders each group (a legal date first). The heading counts are the loader's. */
function WorkList({ initial }: { initial: WorkFilters }) {
  const [f, setF] = useState<WorkFilters>(initial);
  const key = JSON.stringify(initial);
  useEffect(() => setF(initial), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const r = useWorkApi<WorkPage>(workUrl(f));
  const head = useRef<HTMLSpanElement>(null);
  const ready = r.status === "ready";
  const d = ready ? r.data : null;
  const [lastPage, setLastPage] = useState<WorkPage | null>(null);
  useEffect(() => { if (d) setLastPage(d); }, [d]);
  const filtered = f.definition || f.role || f.due || f.mine || f.q.trim();
  const groups = useMemo(() => GROUP_KEYS.map((k) => ({ k, rows: (d?.runs ?? []).filter((x) => x.group === k) })).filter((g) => g.rows.length), [d]);
  const today = asOfDate(d?.asOf);

  return (
    <div className="stack work-view" aria-busy={r.status === "ready" && r.refreshing ? "true" : undefined}>
      <ScreenHeader glyph="list-checks"
        title={<span ref={head} tabIndex={-1} className="work-focus">Work</span>}
        summary={d ? headingLine(d.counts) : "whose move it is, and what is due"}
        actions={<LinkButton href={START_HREF} primary>Start a run</LinkButton>} />
      <WorkNav current="runs" />
      <Filters f={f} page={d ?? lastPage} onChange={setF} />
      {r.status === "loading" && <Loading label={`${WORDS.loading}…`} />}
      {r.status === "error" && <WorkProblem r={r} what="The runs" onRetry={r.reload} />}
      {d && d.counts.open === 0 && !filtered && (
        <EmptyState glyph="list-checks">{d.empty || WORDS.empty} <a href={START_HREF}>Start a run</a></EmptyState>
      )}
      {d && (d.counts.open > 0 || filtered) && groups.length === 0 && (
        <p className="muted">
          No run matches these filters.{" "}
          <button type="button" onClick={() => setF(NO_FILTERS)}>Show every open run</button>
        </p>
      )}
      {d && groups.map((g) => <Group key={g.k} k={g.k} rows={g.rows} today={today} />)}
      {d && <WorkNotes problems={d.problems} notComposed={d.notComposed} />}
      {d && <Caveats items={d.caveats} />}
    </div>
  );
}

/** Start a run, as a page: `#/work/start` or `#/work/start?definition=KEY`. */
function StartPage({ definition }: { definition: string }) {
  const r = useWorkApi<DefinitionsPage>(workDefinitionsUrl());
  const viewer = useWorkViewer();
  const head = useRef<HTMLSpanElement>(null);
  const ready = r.status === "ready";
  useEffect(() => { if (ready) head.current?.focus(); }, [ready]);
  return (
    <div className="stack work-view">
      <WorkCrumbs here="Start a run" />
      <ScreenHeader glyph="plus" title={<span ref={head} tabIndex={-1} className="work-focus">Start a run</span>}
        summary="A run starts as a draft. No clock runs until it is opened, and the dates are checked against the workflow's own rule." />
      {r.status === "loading" && <Loading />}
      {r.status === "error" && <WorkProblem r={r} what="The workflows" onRetry={r.reload} />}
      {ready && r.data.definitions.length === 0 && <EmptyState>{r.data.empty || "No workflows are registered."}</EmptyState>}
      {ready && r.data.definitions.length > 0 && viewer.known && (
        <Card>
          <StartRun definitions={r.data.definitions} initial={definition} by={viewer.name} actingAs={viewer.actingAs}
            onStarted={(def, id) => { window.location.hash = runHref(def, id).slice(1); }} />
        </Card>
      )}
      {ready && <Caveats items={r.data.caveats} />}
    </div>
  );
}

/** Work (docs/console/screens/work.md): the runs that are open, one run, what can be run, and starting a run. The hash is
 * `#/work` (with its filters in the query), `#/work/<definition>/<id>`, `#/work/definitions[?key=]`, and
 * `#/work/start[?definition=]`. The screens read; the small acts they offer are the signed-in person's own. */
export function WorkView() {
  const [hash] = useHash("work");
  const route = parseRoute(hash);
  switch (route.page) {
    case "run": return <WorkRunView key={`${route.definition}/${route.id}`} definition={route.definition} id={route.id} />;
    case "definitions": return <WorkDefinitionsView key={route.key || "catalog"} dkey={route.key} />;
    case "start": return <StartPage key={route.definition} definition={route.definition} />;
    default: return <WorkList initial={route.filters} />;
  }
}
