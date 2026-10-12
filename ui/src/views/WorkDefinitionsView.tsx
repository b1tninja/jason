import { useEffect, useId, useRef, useState } from "react";
import { BasisPill, Caveats, Card, DataTable, EmptyState, Glyph, Loading, ScreenHeader, type Column } from "../components";
import { LawBlock } from "../components/ClockStrip";
import { LinkButton, WorkCrumbs, WorkNav, WorkNotes, WorkProblem } from "../components/WorkParts";
import { titleCase } from "../lib/format";
import {
  KIND_WORDS, definitionHref, startHref, useWorkApi, workDefinitionsUrl,
  type DefinitionClock, type DefinitionRow, type DefinitionStep, type DefinitionsPage,
} from "../lib/work";
import "../styles/work.css";

/** "Started by the manager or the secretary": the roles that may start a definition the viewer's office cannot. */
export function startedByWords(roles: readonly string[]): string {
  const words = roles.map((r) => `the ${r}`);
  return `Started by ${words.length > 1 ? `${words.slice(0, -1).join(", ")} or ${words[words.length - 1]}` : words[0] ?? "another office"}`;
}

/** How a definition stands against the procedure it was built from, in words: in step, or DRIFTED with the engine's sentence. */
function Standing({ d }: { d: Pick<DefinitionRow, "procedure" | "procedureSteps" | "drift"> }) {
  if (!d.procedure) return <p className="muted">Built from no procedure.</p>;
  const steps = d.procedureSteps !== null ? ` (${d.procedureSteps} steps)` : "";
  if (d.drift.ok) return <p className="muted">Built from the procedure {d.procedure}{steps}. In step with it.</p>;
  return (
    <p className="work-drift">
      <strong className="badge badge-warn"><Glyph name="triangle-alert" size="1em" className="badge-glyph" />DRIFTED</strong>{" "}
      Built from the procedure {d.procedure}{steps}. {d.drift.why.join(" ")}
    </p>
  );
}

function DefinitionItem({ d }: { d: DefinitionRow }) {
  return (
    <li className="work-def" data-key={d.key}>
      <div className="work-def-head">
        <h3><a href={definitionHref(d.key)}>{d.title}</a></h3>
        <span className="work-def-acts">
          {d.startable
            ? <LinkButton href={startHref(d.key)} primary>Start</LinkButton>
            : <span className="muted">{d.startableWhy || startedByWords(d.startedBy)}</span>}
          <LinkButton href={definitionHref(d.key)}>Read</LinkButton>
        </span>
      </div>
      <p className="muted">
        {d.steps} {d.steps === 1 ? "step" : "steps"}{d.cadence ? ` · ${d.cadence}` : ""} · about a {d.subjectKind || "subject"}
        {d.legalClock ? " · has a legal clock" : ""}
      </p>
      <Standing d={d} />
    </li>
  );
}

function Filters({ f, families, onChange }: {
  f: { family: string; q: string; mine: boolean }; families: readonly string[]; onChange: (n: { family: string; q: string; mine: boolean }) => void;
}) {
  const uid = useId();
  const [q, setQ] = useState(f.q);
  useEffect(() => {
    if (q === f.q) return;
    const t = setTimeout(() => onChange({ ...f, q }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  return (
    <form className="work-filters row wrap" role="search" aria-label="Filter the workflows" onSubmit={(e) => e.preventDefault()}>
      <label htmlFor={`${uid}-f`}>Family</label>
      <select id={`${uid}-f`} value={f.family} onChange={(e) => onChange({ ...f, family: e.target.value })}>
        <option value="">All families</option>
        {families.map((x) => <option key={x} value={x}>{titleCase(x)}</option>)}
      </select>
      <label htmlFor={`${uid}-q`}>Search</label>
      <input id={`${uid}-q`} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
      <label><input type="checkbox" checked={f.mine} onChange={(e) => onChange({ ...f, mine: e.target.checked })} /> Needs my office</label>
    </form>
  );
}

/** What can be run (`#/work/definitions`): the workflows jason has, by family, read only. No control edits a definition. */
function Catalog() {
  const [f, setF] = useState({ family: "", q: "", mine: false });
  const r = useWorkApi<DefinitionsPage>(workDefinitionsUrl(f));
  const [known, setKnown] = useState<string[]>([]);
  const head = useRef<HTMLSpanElement>(null);
  const d = r.status === "ready" ? r.data : null;
  useEffect(() => { if (d) setKnown((k) => [...new Set([...k, ...d.families.map((x) => x.family)])].sort()); }, [d]);
  useEffect(() => { if (d) head.current?.focus(); }, [!!d]); // eslint-disable-line react-hooks/exhaustive-deps
  const c = d?.counts;
  return (
    <div className="stack work-view">
      <WorkCrumbs here="What can be run" />
      <ScreenHeader glyph="book-open" title={<span ref={head} tabIndex={-1} className="work-focus">What can be run</span>}
        summary={c ? `${c.definitions} workflows in ${c.families} ${c.families === 1 ? "family" : "families"}${c.drifted ? ` · ${c.drifted} ${c.drifted === 1 ? "has" : "have"} drifted from their procedure` : " · none has drifted from its procedure"}` : "the workflows jason has"}
        actions={<LinkButton href={startHref()} primary>Start a run</LinkButton>} />
      <WorkNav current="definitions" />
      <Filters f={f} families={known} onChange={setF} />
      {r.status === "loading" && <Loading />}
      {r.status === "error" && <WorkProblem r={r} what="The workflows" onRetry={r.reload} />}
      {d && d.counts.definitions === 0 && <EmptyState glyph="book-open">{d.empty || "No workflows are registered."}</EmptyState>}
      {d && d.counts.definitions > 0 && d.families.length === 0 && <p className="muted">No workflow matches these filters. <button type="button" onClick={() => setF({ family: "", q: "", mine: false })}>Show every workflow</button></p>}
      {d && d.families.map((g) => (
        <Card key={g.family} title={titleCase(g.family)}>
          <ul className="work-defs" aria-label={`${titleCase(g.family)} workflows`}>{g.definitions.map((x) => <DefinitionItem key={x.key} d={x} />)}</ul>
        </Card>
      ))}
      {d && <WorkNotes problems={d.problems} notComposed={d.notComposed} />}
      {d && <Caveats items={d.caveats} />}
    </div>
  );
}

const clockWords = (c: DefinitionClock | null) => (c ? (
  <>{c.label || c.slot} <BasisPill basis={c.basis} label={c.basisLabel} />{c.cite ? <span className="muted"> {c.cite}</span> : null}</>
) : <span className="muted">no clock</span>);

const stepColumns = (): Column<DefinitionStep>[] => [
  { key: "n", header: "#", value: (s) => s.n },
  { key: "title", header: "Step", render: (s) => <><strong>{s.title}</strong>{s.why && <div className="muted">{s.why}</div>}{s.command && <div><code className="chip">{s.command}</code></div>}{s.guidance && <div className="muted">Guidance: {s.guidance}</div>}</> , value: (s) => s.title },
  { key: "kind", header: "Kind", render: (s) => <>{KIND_WORDS[s.kind] ?? s.kind}{s.legal ? <span className="muted"> · required by the law</span> : null}</>, value: (s) => s.kind },
  { key: "role", header: "Role", value: (s) => s.role },
  { key: "clock", header: "Clock", render: (s) => clockWords(s.clock), value: (s) => s.clock?.label ?? "" },
  {
    key: "needs", header: "Needs and makes",
    render: (s) => {
      const bits = [
        s.needs.length ? `Needs: ${s.needs.join(", ")}` : "", s.record ? `Record: ${s.record}` : "", s.plan ? `Makes a plan: ${s.plan}` : "",
        s.job ? `Runs the job: ${s.job}` : "", s.spawns ? `Starts a child run: ${s.spawns}` : "", s.skip ? `May be skipped by ${s.skip.roles.join(" or ")}` : "",
      ].filter(Boolean);
      return bits.length ? <ul className="work-needs">{bits.map((b) => <li key={b}>{b}</li>)}</ul> : <span className="muted">nothing</span>;
    },
    value: (s) => s.needs.join(" "),
  },
];

/** One definition read as a page (`#/work/definitions?key=KEY`): every step, its kind, role, clock and basis, what it needs and
 * makes, and the sentence it shows a person; a step that cites a statute recites it. The board can see how a task is done before
 * it is started. There is no control to edit it: a procedure is the lowest authority, corrected in the definition. */
function DefinitionPage({ dkey }: { dkey: string }) {
  const r = useWorkApi<DefinitionsPage>(workDefinitionsUrl({ key: dkey }));
  const head = useRef<HTMLSpanElement>(null);
  const def = r.status === "ready" ? r.data.definition : undefined;
  useEffect(() => { if (def) head.current?.focus(); }, [def]);
  const laws = (def?.steps.map((s) => s.clock).filter((c): c is DefinitionClock => !!c?.law) ?? []);
  const seen = new Set<string>();
  const unique = laws.filter((c) => (seen.has(c.cite) ? false : (seen.add(c.cite), true)));
  return (
    <div className="stack work-view">
      <WorkCrumbs trail={[{ label: "What can be run", href: "#/work/definitions" }]} here={def?.title ?? dkey} />
      <ScreenHeader glyph="book-open" title={<span ref={head} tabIndex={-1} className="work-focus">{def?.title ?? dkey}</span>}
        summary={def ? `${titleCase(def.family)} · ${def.steps.length} steps · about a ${def.subjectKind || "subject"}` : undefined}
        actions={def && (def.startable ? <LinkButton href={startHref(def.key)} primary>Start</LinkButton> : <span className="muted">{def.startableWhy || startedByWords(def.startedBy)}</span>)} />
      <WorkNav current="definitions" />
      {r.status === "loading" && <Loading />}
      {r.status === "error" && (r.code === 404
        ? <EmptyState glyph="book-open">{r.error} <a href="#/work/definitions">Back to what can be run</a></EmptyState>
        : <WorkProblem r={r} what="This workflow" onRetry={r.reload} />)}
      {r.status === "ready" && !def && <EmptyState glyph="book-open">No workflow {dkey}. <a href="#/work/definitions">Back to what can be run</a></EmptyState>}
      {def && (
        <>
          <Card title="How it stands"><Standing d={def} />
            {def.lessons.length > 0 && <p className="muted">Lessons its procedure names: {def.lessons.map((l) => `${l.key} (${l.status})`).join(", ")}.</p>}
            <p className="muted">A workflow is jason's procedure, the lowest authority. A step that conflicts with the law or a rule is corrected in the definition, and the lesson recorded. This page edits nothing.</p>
          </Card>
          {def.dates.length > 0 && (
            <Card title="The dates it asks for">
              <ul className="work-dates-list">
                {def.dates.map((x) => <li key={x.name}><strong>{x.label || x.name}</strong>{x.required ? "" : " (optional)"}{x.after ? <span className="muted"> · may not come before {x.after}</span> : null}</li>)}
              </ul>
            </Card>
          )}
          <Card title="Steps">
            <DataTable rows={def.steps} columns={stepColumns()} searchable={false} caption={`The steps of ${def.title}`} rowKey={(s) => s.id} />
          </Card>
          {unique.length > 0 && (
            <Card title="What the law says">
              {unique.map((c) => c.law && <LawBlock key={c.cite} law={c.law} cite={c.cite} />)}
            </Card>
          )}
          <WorkNotes problems={r.status === "ready" ? r.data.problems : []} />
          {r.status === "ready" && <Caveats items={r.data.caveats} />}
        </>
      )}
    </div>
  );
}

/** The catalog, or one definition read whole when `dkey` is given. */
export function WorkDefinitionsView({ dkey = "" }: { dkey?: string }) {
  return dkey ? <DefinitionPage dkey={dkey} /> : <Catalog />;
}
