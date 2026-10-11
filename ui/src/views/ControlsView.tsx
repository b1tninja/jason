import { useEffect, useRef, useState } from "react";
import {
  Caveats, Card, ControlCard, ControlQuestionRow, ControlRow, ControlStateWord, EmptyState, ErrorNotice, Glyph, Loading, RefusedRow, ScreenHeader,
  controlDates, type ProposeAs,
} from "../components";
import {
  CONTROLS_HREF, FAMILIES, FAMILY_TITLES, STATES, WORDS, boardHref, controlUrl, controlsUrl, focusedControl, isSecretary,
  useControlsApi, useControlsViewer,
  type ControlsPage, type ControlsRemote, type ControlsViewer, type OneControl, type ProposeAnswer,
} from "../lib/controls";
import { useHash } from "../lib/useHash";
import "../styles/controls.css";

/** A read the server refused (401 signed out, 403 for an office that does not open it) or that failed. The server's own
 * sentence is shown, with the sign-in link for a 401. A failed read says so with its reason and shows no control, so nothing
 * appears as adopted that is not. */
export function ControlsProblem({ r, what, onRetry }: { r: Extract<ControlsRemote<unknown>, { status: "error" }>; what: string; onRetry: () => void }) {
  if (r.code === 401 || r.code === 403)
    return (
      <div className="notice control-held" role="alert">
        <Glyph name="lock" size="1em" /> <span>{r.error}</span>
        {r.code === 401 && r.signIn && <> <a href={r.signIn}>Sign in with Google</a></>}
      </div>
    );
  return <ErrorNotice error={`${what} could not be read: ${r.error}. Nothing is shown as adopted.`} onRetry={onRetry} />;
}

function ProposedNotice({ done }: { done: ProposeAnswer | null }) {
  if (!done) return null;
  return (
    <p role="status" className="notice notice-good control-done">
      <Glyph name="paperclip" size="1em" />{" "}
      {done.refreshed ? "The board item was refreshed" : "Put before the board"}: <a href={boardHref(done.item)}>{done.item}</a>
      {done.by ? `, as ${done.by}` : ""}. It adopts nothing and changes no rule; the board decides and the secretary records it.
    </p>
  );
}

function useProposals(reload: () => void, viewer: ControlsViewer) {
  const [done, setDone] = useState<ProposeAnswer | null>(null);
  const as: ProposeAs = { by: viewer.name, actingAs: viewer.actingAs, onProposed: (a) => { setDone(a); reload(); } };
  return { done, as };
}

function Filters({ family, state, onFamily, onState }: { family: string; state: string; onFamily: (v: string) => void; onState: (v: string) => void }) {
  return (
    <form className="control-filters row wrap" role="search" aria-label="Filter the controls" onSubmit={(e) => e.preventDefault()}>
      <label>Family{" "}
        <select value={family} onChange={(e) => onFamily(e.target.value)}>
          <option value="">All families</option>
          {FAMILIES.map((f) => <option key={f} value={f}>{FAMILY_TITLES[f]}</option>)}
        </select>
      </label>
      <label>State{" "}
        <select value={state} onChange={(e) => onState(e.target.value)}>
          <option value="">All states</option>
          {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
    </form>
  );
}

/** The list, grouped by family: adopted first, then proposed, suggested, deferred, declined, retired; a family with nothing
 * is not drawn. The heading counts are the loader's. */
function ControlsList({ returnTo }: { returnTo: string }) {
  const [family, setFamily] = useState("");
  const [state, setState] = useState("");
  const r = useControlsApi<ControlsPage>(controlsUrl({ family, state }));
  const viewer = useControlsViewer();
  const { done, as } = useProposals(r.reload, viewer);
  const head = useRef<HTMLSpanElement>(null);
  const ready = r.status === "ready";
  // Coming back from a card, focus lands on the control just left; with none (or a first visit), nothing is moved.
  const focused = useRef(false);
  useEffect(() => {
    if (!ready || focused.current || !returnTo) return;
    focused.current = true;
    const row = Array.from(document.querySelectorAll<HTMLElement>("[data-key]")).find((el) => el.getAttribute("data-key") === returnTo);
    (row?.querySelector<HTMLElement>("a.control-row-link") ?? head.current)?.focus();
  }, [ready, returnTo]);

  const d = r.status === "ready" ? r.data : null;
  return (
    <div className="stack controls-view" aria-busy={r.status === "ready" && r.refreshing ? "true" : undefined}>
      <ScreenHeader
        glyph="shield-check"
        title={<span ref={head} tabIndex={-1} className="control-focus">Controls</span>}
        summary={<>{WORDS.tagline}.{d?.heading ? <><br /><span className="control-heading">{d.heading}.</span></> : null}</>}
      />
      <Filters family={family} state={state} onFamily={setFamily} onState={setState} />
      <ProposedNotice done={done} />
      {r.status === "loading" && <Loading />}
      {r.status === "error" && <ControlsProblem r={r} what="The controls" onRetry={r.reload} />}
      {d && d.found === false && <EmptyState glyph="shield-check">{d.note ?? WORDS.empty}</EmptyState>}
      {d && d.found !== false && d.empty && (
        <EmptyState glyph="shield-check">{WORDS.empty} <a href="#/onboarding">Open Onboarding</a></EmptyState>
      )}
      {d && d.found !== false && !d.empty && (
        <>
          {!d.families.length && (
            <p className="muted">
              No control matches these filters.{" "}
              <button type="button" onClick={() => { setFamily(""); setState(""); }}>Show every control</button>
            </p>
          )}
          {d.families.map((g) => (
            <Card key={g.family} title={g.title}>
              <ul className="control-list" aria-label={`${g.title} controls`}>
                {g.controls.map((c) => <ControlRow key={c.key} row={c} as={as} />)}
                {g.questions.map((q) => <ControlQuestionRow key={`${q.key}-${q.number}`} q={q} />)}
              </ul>
            </Card>
          ))}
          {d.refused.length > 0 && (
            <Card title="Refused">
              <p className="muted">A control only adds. These would go below a floor, so they are not offered.</p>
              <ul className="control-list" aria-label="Refused controls">{d.refused.map((x) => <RefusedRow key={x.title} r={x} />)}</ul>
            </Card>
          )}
          <Caveats items={d.caveats} />
        </>
      )}
    </div>
  );
}

/** One control at `#/controls?key=KEY`: a page of six bands in order. Focus moves to the title when it opens. */
function ControlPage({ ckey }: { ckey: string }) {
  const r = useControlsApi<OneControl>(controlUrl(ckey));
  const viewer = useControlsViewer();
  const { done, as } = useProposals(r.reload, viewer);
  const head = useRef<HTMLSpanElement>(null);
  const ready = r.status === "ready";
  useEffect(() => { if (ready) head.current?.focus(); }, [ready, ckey]);
  const d = r.status === "ready" ? r.data : null;
  const row = d && d.found !== false ? d.control : null;
  const title = row?.title ?? "Control";
  return (
    <div className="stack controls-view control-page" aria-busy={r.status === "ready" && r.refreshing ? "true" : undefined}>
      <nav aria-label="Breadcrumb" className="control-crumbs">
        <ol>
          <li><a href={CONTROLS_HREF}>Controls</a></li>
          <li aria-current="page">{row ? row.title : ckey}</li>
        </ol>
      </nav>
      <ScreenHeader
        glyph="shield-check"
        title={<span ref={head} tabIndex={-1} className="control-focus">{title}</span>}
        summary={row ? controlDates(row) : WORDS.tagline}
        actions={row ? <ControlStateWord standing={row.standing} word={row.stateWord} effective={row.effective} detail /> : undefined}
      />
      <ProposedNotice done={done} />
      {r.status === "loading" && <Loading />}
      {r.status === "error" && <ControlsProblem r={r} what="This control" onRetry={r.reload} />}
      {d && d.found === false && <EmptyState glyph="shield-check">{d.note ?? `No control ${ckey}.`}</EmptyState>}
      {d && row && (
        <>
          <ControlCard data={d} as={as} secretary={isSecretary(viewer)} />
          <Caveats items={d.caveats} />
        </>
      )}
    </div>
  );
}

/** Controls (docs/console/screens/controls.md): the safeguards jason suggests and the board adopts. `#/controls` is the list;
 * `#/controls?key=KEY` is one control. The screen reads; its one write puts a suggestion before the board as a board item. */
export function ControlsView() {
  const [hash] = useHash("controls");
  const key = focusedControl(hash);
  const last = useRef("");
  const back = !key ? last.current : "";
  useEffect(() => { if (key) last.current = key; }, [key]);
  return key ? <ControlPage key={key} ckey={key} /> : <ControlsList key="list" returnTo={back} />;
}
