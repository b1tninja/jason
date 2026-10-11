import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import {
  BasisPill, Caveats, Card, ChangedSince, ClockStrip, Confirm, DueDate, EmptyState, Glyph, Loading, Pill, RunHistory, RunStepPanel, ScreenHeader,
  WorkflowRail,
} from "../components";
import { ActDialog, ActStatus, TextConfirm, useActs } from "../components/RunActs";
import { LinkButton, WorkCrumbs, WorkNav, WorkNotes, WorkProblem } from "../components/WorkParts";
import { PHONE_QUERY, useMediaQuery } from "../lib/useMediaQuery";
import {
  HELD_WORDS, WORK_HREF, asOfDate, dayOf, maskContact, openingStep, pastLegal, runHref, useRunDefinitions, useWorkApi, useWorkViewer, workRunUrl,
  type RunLink, type RunPage, type WorkViewer,
} from "../lib/work";
import "../styles/work.css";

type Dialog = "" | "pause" | "note" | "cancel";

/** Pause, resume, open, note, print the history, cancel. Each is a `Confirm` that says what is recorded and under whose
 * name; pause, cancel, and a step's skip or reopen ask for a reason. A control the run does not offer is not drawn, except
 * cancel, whose reason is given. For an administrator viewing as someone else there is one sentence in its place. */
function RunControls({ page, viewer, acts, printing, onPrint }: {
  page: RunPage; viewer: WorkViewer; acts: ReturnType<typeof useActs>; printing: boolean; onPrint: () => void;
}) {
  const { run } = page;
  const [dialog, setDialog] = useState<Dialog>("");
  const close = useCallback(() => setDialog(""), []);
  const by = viewer.name || "the signed-in person";
  const opener = useRef<HTMLButtonElement | null>(null);
  const acting = ["pause", "resume", "note", "cancel"].every((k) => !run.acts[k as "pause"].offered) && /^Viewing as /.test(run.acts.note.why);
  const open = (d: Dialog) => (e: MouseEvent<HTMLButtonElement>) => { opener.current = e.currentTarget; acts.clear(); setDialog(d); };
  const done = async (body: Parameters<typeof acts.send>[0]) => { if (await acts.send(body)) { setDialog(""); opener.current?.focus(); } };
  const stepTitle = (id: string) => page.steps.find((s) => s.id === id)?.title ?? id;
  const childName = (id: string) => page.links.find((l) => l.kind === "run" && l.id === id)?.label || id;
  const will = run.cancelWill;

  if (acting) {
    return (
      <div className="work-controls stack-sm">
        <p className="notice notice-warn" role="alert">{run.acts.note.why}</p>
        <div className="row wrap"><button type="button" aria-pressed={printing} onClick={onPrint}>Print the history</button></div>
      </div>
    );
  }
  return (
    <div className="work-controls stack-sm">
      <div className="row wrap">
        {run.acts.open.offered && (
          <Confirm busy={acts.busy} label="Open" onConfirm={() => void acts.send({ act: "open", ...(run.acts.open.needsYes ? { yes: true } : {}) })}
            summary={<>Open the run under the name {by}: its clocks start now{run.acts.open.needsYes ? ", and it has a legal clock; this is the yes it needs" : ""}. The stores are read, and what changed is recorded.</>}>
            Open the run
          </Confirm>
        )}
        {run.acts.pause.offered && <button type="button" onClick={open("pause")}>Pause</button>}
        {run.acts.resume.offered && (
          <Confirm busy={acts.busy} label="Resume" onConfirm={() => void acts.send({ act: "resume" })}
            summary={<>Lift the pause under the name {by}. The clocks that kept running show as they are.</>}>
            Resume
          </Confirm>
        )}
        {run.acts.note.offered && <button type="button" onClick={open("note")}>Note</button>}
        <button type="button" aria-pressed={printing} onClick={onPrint}>Print the history</button>
        {run.acts.cancel.offered && <button type="button" onClick={open("cancel")}>Cancel</button>}
      </div>
      {!run.acts.cancel.offered && run.acts.cancel.why && <p className="muted work-not-offered">{run.acts.cancel.why}</p>}
      {!dialog && <ActStatus said={acts.said} />}

      <ActDialog title="Pause this run" open={dialog === "pause"} onClose={close}>
        <TextConfirm trigger="Pause" field="Why it is paused" busy={acts.busy} label="Pause"
          summary={(reason) => <>Pause the run under the name {by}, because: <q>{reason}</q>. No clock is hidden while it is paused.</>}
          onConfirm={(reason) => void done({ act: "pause", reason })} />
        <ActStatus said={acts.said} onReload={() => window.location.reload()} />
      </ActDialog>
      <ActDialog title="Add a note to the run" open={dialog === "note"} onClose={close}>
        <TextConfirm trigger="Add the note" field="The note" busy={acts.busy} label="Note"
          summary={(text) => <>Add a note to the run under the name {by}: <q>{text}</q></>}
          onConfirm={(text) => void done({ act: "note", text })} />
        <ActStatus said={acts.said} />
      </ActDialog>
      <ActDialog title="Cancel this run" open={dialog === "cancel"} onClose={close}>
        <div className="work-cancel-will">
          <p>Cancelling leaves {will.openSteps.length} open {will.openSteps.length === 1 ? "step" : "steps"} and {will.childRuns.length} child {will.childRuns.length === 1 ? "run" : "runs"} as they are. The run stays listed as cancelled.</p>
          {will.openSteps.length > 0 && <><h3>Open steps it leaves</h3><ul>{will.openSteps.map((s) => <li key={s}>{stepTitle(s)}</li>)}</ul></>}
          {will.childRuns.length > 0 && <><h3>Child runs it leaves</h3><ul>{will.childRuns.map((c) => <li key={c}>{childName(c)}</li>)}</ul></>}
          {run.acts.cancel.legal && <p className="notice notice-warn">This run has a legal clock. A cancellation needs a plain yes from the secretary or the manager.</p>}
        </div>
        <TextConfirm trigger="Cancel the run" field="Why it is cancelled" busy={acts.busy} label="Cancel"
          summary={(reason) => <>Cancel the run under the name {by}, because: <q>{reason}</q>. It leaves {will.openSteps.length} open {will.openSteps.length === 1 ? "step" : "steps"} and {will.childRuns.length} child {will.childRuns.length === 1 ? "run" : "runs"}.{run.acts.cancel.needsYes ? " This is the yes a legal clock needs." : ""}</>}
          onConfirm={(reason) => void done({ act: "cancel", reason, ...(run.acts.cancel.needsYes ? { yes: true } : {}) })} />
        <ActStatus said={acts.said} onReload={() => window.location.reload()} />
      </ActDialog>
    </div>
  );
}

/** The state of the run in a sentence, where it is not simply running. */
function StateBanner({ page }: { page: RunPage }) {
  const { run } = page;
  const paused = page.history.find((e) => e.kind === "paused");
  if (run.state === "paused") {
    return (
      <p className="notice notice-warn work-banner" role="note">
        <Glyph name="circle-pause" size="1em" /> Paused{run.pausedReason ? `: ${run.pausedReason}` : ""}
        {paused ? <>. {paused.by ? `By ${maskContact(paused.by)}` : ""}{paused.at ? `, ${dayOf(paused.at)}` : ""}</> : null}. No clock is hidden: the dates below keep running.
      </p>
    );
  }
  if (run.state === "draft") return <p className="notice work-banner" role="note"><Glyph name="info" size="1em" /> A draft: being set up. No clock runs until the run is opened.</p>;
  if (run.state === "cancelled") return <p className="notice work-banner" role="note"><Glyph name="circle-x" size="1em" /> Cancelled{run.cancelledReason ? `: ${run.cancelledReason}` : ""}. The run stays listed.</p>;
  if (run.state === "failed") return <p className="notice notice-error work-banner" role="note"><Glyph name="triangle-alert" size="1em" /> This run failed. See the failing step; nothing is retried by a click.</p>;
  return null;
}

/** One run (`#/work/<definition>/<id>`): the title row and its acts; the "changed since" banner first when a store moved under a
 * done step; the rail beside the step; the clocks; the links; the history. It reads the run as opening it now would find it
 * (written nowhere); a person's act is the only write, in their name, behind a `Confirm`. */
export function WorkRunView({ definition, id }: { definition: string; id: string }) {
  const r = useWorkApi<RunPage>(workRunUrl(definition, id));
  const viewer = useWorkViewer();
  const compact = useMediaQuery(PHONE_QUERY);
  const [picked, setPicked] = useState("");
  const [printing, setPrinting] = useState(false);
  const head = useRef<HTMLSpanElement>(null);
  const panel = useRef<HTMLHeadingElement>(null);
  const d = r.status === "ready" ? r.data : null;
  const reload = r.reload;
  // one hook each, so the status of a step's act stands in the step and the run's in its own dialog
  const stepActs = useActs(d?.run ?? { definition, id, n: 0 }, reload);
  const runActs = useActs(d?.run ?? { definition, id, n: 0 }, reload);

  const ids = useMemo(() => (d ? [...new Set([...(d.run.parent ? [d.run.parent] : []), ...d.run.children, ...d.links.filter((l) => l.kind === "run").map((l) => l.id)])] : []), [d]);
  const defs = useRunDefinitions(ids);
  const childHref = useCallback((l: RunLink): string | null => (l.kind === "run" && defs[l.id] ? runHref(defs[l.id], l.id) : null), [defs]);

  const ready = r.status === "ready";
  useEffect(() => { if (ready) head.current?.focus(); }, [ready, definition, id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    document.body.classList.toggle("work-printing", printing);
    return () => document.body.classList.remove("work-printing");
  }, [printing]);

  const selected = d && picked && d.steps.some((s) => s.id === picked) ? picked : d ? openingStep(d) : "";
  const step = d?.steps.find((s) => s.id === selected);
  const select = (sid: string) => { setPicked(sid); stepActs.clear(); setTimeout(() => panel.current?.focus(), 0); };
  const today = asOfDate(d?.asOf);
  const run = d?.run;

  return (
    <div className="stack work-view work-run" aria-busy={r.status === "ready" && r.refreshing ? "true" : undefined}>
      <WorkCrumbs here={run ? run.label || run.id : id} />
      <ScreenHeader glyph="list-checks"
        title={<span ref={head} tabIndex={-1} className="work-focus">{run ? run.label || run.id : id}</span>}
        summary={run ? (d?.held ? <>{HELD_WORDS}</> : <>{run.definitionTitle} · Opened {dayOf(run.opened)} by {run.openedBy}{run.subject ? <> · about <code>{run.subject}</code></> : null}</>) : undefined}
        actions={run ? <Pill word={run.state} /> : undefined} />
      <WorkNav current="runs" />
      {r.status === "loading" && <Loading label="Reading the run on disk…" />}
      {r.status === "error" && (
        r.code === 404
          ? <EmptyState glyph="list-checks">{r.error} <a href={WORK_HREF}>Back to the open runs</a></EmptyState>
          : <WorkProblem r={r} what="This run" onRetry={r.reload} />
      )}
      {d && run && d.held && (
        <>
          <p className="notice notice-warn work-banner" role="note" data-held="true"><Glyph name="lock" size="1em" /> {d.heldWhy || HELD_WORDS}</p>
          <Card title={d.heldTitle || run.label}>
            <ul className="work-links">
              <li className="work-link-row"><span className="muted">state</span> <Pill word={run.state} /></li>
              <li className="work-link-row"><span className="muted">step</span> {run.current?.title || "No open step"}</li>
              <li className="work-link-row">
                <span className="muted">next date</span>{" "}
                {run.due ? <><DueDate iso={run.due.date} today={today} /> <BasisPill basis={run.due.basis} label={run.due.basisLabel} /></> : <span className="muted">No date</span>}
              </li>
            </ul>
          </Card>
          <Caveats items={d.caveats} />
          <p><LinkButton href={WORK_HREF}>Back to the open runs</LinkButton></p>
        </>
      )}
      {d && run && !d.held && (
        <>
          <RunControls page={d} viewer={viewer} acts={runActs} printing={printing} onPrint={() => { setPrinting((p) => !p); }} />
          <StateBanner page={d} />
          {d.pending.length > 0 && (
            <div className="notice work-pending" role="note">
              <p>
                <Glyph name="info" size="1em" /> Opening the run now would record {d.pending.length} {d.pending.length === 1 ? "event" : "events"}:
                {" "}{d.pending.map((p) => `${p.kind}${p.stepTitle ? ` (${p.stepTitle})` : ""}`).join(", ")}. This page shows the run as that read finds it; nothing is written until a person records it.
              </p>
              {!run.acts.open.offered && run.acts.note.offered && (
                <Confirm busy={runActs.busy} label="Record" onConfirm={() => void runActs.send({ act: "open" })}
                  summary={<>Record what the read found ({d.pending.length} {d.pending.length === 1 ? "event" : "events"}) under the name {viewer.name || "the signed-in person"}.</>}>
                  Record what the read found
                </Confirm>
              )}
            </div>
          )}
          {pastLegal(d) && (
            <p className="notice notice-warn work-banner work-past" role="note">
              <Glyph name="triangle-alert" size="1em" /> This run is past a legal date. The law's words are recited under Clocks; jason's reading follows them, labeled.
            </p>
          )}
          <ChangedSince changed={d.changed} onGo={select} />
          <div className="work-run-grid">
            <WorkflowRail page={d} selected={selected} onSelect={select} href={childHref} compact={compact} />
            {step ? (
              <RunStepPanel ref={panel} step={step} run={run} viewer={viewer} acts={stepActs} childHref={childHref} onReread={reload} />
            ) : <EmptyState>This run has no steps.</EmptyState>}
          </div>
          <Card title="Clocks"><ClockStrip clocks={d.clocks} today={today} /></Card>
          <Card title="Links">
            {d.links.length === 0 && !run.parent ? <p className="muted">This run has made nothing yet.</p> : (
              <ul className="work-links">
                {run.parent && <li className="work-link-row"><span className="muted">parent run</span> {defs[run.parent] ? <a href={runHref(defs[run.parent], run.parent)}>{run.parent}</a> : <span>{run.parent}</span>}</li>}
                {d.links.map((l) => {
                  const href = l.kind === "run" ? childHref(l) : l.screen ? `#/${l.screen}` : null;
                  const name = l.label || `${l.kind} ${l.id}`;
                  return (
                    <li key={`${l.kind}-${l.id}`} className="work-link-row">
                      <span className="muted">{l.kind === "run" ? "child run" : l.kind}</span> {href ? <a href={href}>{name}</a> : <span>{name}</span>}{" "}
                      {l.read ? <Pill word={l.state} /> : <span className="muted">state not read here</span>}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
          <Card title="History"><RunHistory events={d.history} /></Card>
          {printing && (
            <section className="work-print-sheet" aria-label="The history, for printing">
              <h2>{run.label || run.id}</h2>
              <p className="muted">{run.definitionTitle} · run {run.id} · opened {dayOf(run.opened)} · the events, oldest first</p>
              <RunHistory events={d.history} print />
              <div className="row work-print-bar">
                <button type="button" className="primary" onClick={() => window.print()}>Print</button>
                <button type="button" onClick={() => setPrinting(false)}>Close the print view</button>
              </div>
            </section>
          )}
          {(run.torn || run.corrupt) && (
            <p className="notice notice-warn" role="note">
              {run.torn ? "The run's last line is torn (a partial write was dropped); the next write cuts it off and keeps its text." : `Line ${run.corrupt} of the run is not an event; nothing more is appended until a person looks at it.`}
            </p>
          )}
          <WorkNotes problems={d.problems} notComposed={d.notComposed} />
          <Caveats items={d.caveats} />
          <p><LinkButton href={WORK_HREF}>Back to the open runs</LinkButton></p>
        </>
      )}
    </div>
  );
}
