import { forwardRef, useState, type ReactNode } from "react";
import { BasisPill } from "./BasisPill";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { ControlStepNotice } from "./ControlNotice";
import { ItemTable, RemedyNote, SupplyItems } from "./RunItems";
import { Doc } from "./Doc";
import { Glyph } from "./Glyph";
import { Pill } from "./Pill";
import { ActStatus, TextConfirm, type Acts } from "./RunActs";
import { StepStateWord } from "./StepStateWord";
import { addressScheme, driveDocRef, fileDocRef, type DocRef } from "../lib/docref";
import {
  KIND_WORDS, WORDS, dayOf, refusalsFor, safeAddress, shortHash, waitingWords,
  type Run, type RunClock, type RunLink, type RunStep, type StepEvidence, type WorkViewer,
} from "../lib/work";

/** A DocRef for an evidence address the server named, so a document opens in the viewer (one logged view) rather than by a
 * link of the page's own. An address of no known scheme (a citation) is text. */
export function evidenceRef(address: string): DocRef | null {
  const scheme = addressScheme(address);
  if (!scheme) return null;
  const rest = address.slice(scheme.length + 1);
  if (scheme === "file") return fileDocRef(rest, rest.split("/").pop() || rest, { source: "File on disk" });
  if (scheme === "drive") return driveDocRef(rest, "File in Drive");
  return { address, name: scheme === "payhoa" ? "PayHOA record" : "Library document", kind: "file", source: scheme === "payhoa" ? "PayHOA" : "Library copy" };
}

function EvidenceRow({ e }: { e: StepEvidence }) {
  const address = safeAddress(e.address);
  const ref = address === e.address ? evidenceRef(e.address) : null;
  return (
    <li className="work-evidence">
      {ref ? <Doc doc={ref} variant="chip" /> : <code className="chip">{address}</code>}
      {ref && <code className="chip work-evidence-address">{address}</code>}
      {!e.present && <span className="muted"> not on disk</span>}
      {e.changed && (
        <span className="work-changed-word">
          {" "}<Glyph name="triangle-alert" size="1em" /> {WORDS.changedSince}: was <code>{shortHash(e.kept)}</code>, now <code>{shortHash(e.now)}</code>
        </span>
      )}
    </li>
  );
}

function LinkRow({ l, href }: { l: RunLink; href: string | null }) {
  const target = l.kind === "run" ? href : l.screen ? `#/${l.screen}` : null;
  const name = l.label || `${l.kind} ${l.id}`;
  return (
    <li className="work-link-row">
      <span className="muted">{l.kind}</span> {target ? <a href={target}>{name}</a> : <span>{name}</span>}{" "}
      {l.read ? <Pill word={l.state} /> : <span className="muted">state not read here</span>}
      {l.problem && <span className="muted"> {l.problem}</span>}
    </li>
  );
}

// -- the panel, by kind -----------------------------------------------------------------------------------------------------

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="work-step-part"><h3>{title}</h3>{children}</section>;
}

/** Mark a step done: only a person's step (or a branch a person answers), only by the role it names, and only with the record
 * it asks for. The first click states what will be recorded and under what name; the second records it. */
function MarkDone({ step, run, viewer, acts }: { step: RunStep; run: Run; viewer: WorkViewer; acts: Acts }) {
  const [choice, setChoice] = useState(step.choices[0] ?? "");
  const branch = step.kind === "branch" && step.choices.length > 0;
  const by = viewer.name || "the signed-in person";
  const what = (record: string) => (
    <>
      Record step {step.n}, {step.title}, as {branch ? `answered: ${choice}` : "done"}, under the name {by}
      {record ? <>, with the record: <q>{record}</q></> : null}. It goes on the run's history; a correction is a later entry, never an edit.
    </>
  );
  const body = (record: string) => ({
    act: "attest" as const, step: step.id, ...(step.needsRecord ? { record } : {}), ...(branch ? { choice } : {}),
  });
  return (
    <div className="work-do stack-sm">
      {branch && (
        <fieldset className="work-choices">
          <legend>Your answer</legend>
          {step.choices.map((c) => (
            <label key={c}><input type="radio" name={`choice-${step.id}`} value={c} checked={choice === c} onChange={() => setChoice(c)} /> {c}</label>
          ))}
        </fieldset>
      )}
      {step.needsRecord ? (
        <TextConfirm single trigger={branch ? "Answer" : "Mark done"} field={`The record: ${step.needsRecord}`} required busy={acts.busy}
          summary={what} label={branch ? "Answer" : "Mark done"} onConfirm={(record) => void acts.send(body(record))} />
      ) : (
        <Confirm busy={acts.busy} label={branch ? "Answer" : "Mark done"} summary={what("")} onConfirm={() => void acts.send(body(""))}>
          {branch ? "Answer" : "Mark done"}
        </Confirm>
      )}
    </div>
  );
}

function KindBlock({ step, run, viewer, acts, onReread }: { step: RunStep; run: Run; viewer: WorkViewer; acts: Acts; onReread?: () => void }) {
  switch (step.kind) {
    case "check": {
      const result = step.state === "done" ? "Passed" : step.state === "failed" ? "Did not pass" : "Not read yet";
      return (
        <Section title="The check">
          <p><strong>{step.title}</strong></p>
          <p>Result: <strong>{result}</strong>{step.at ? <>, read {dayOf(step.at)}</> : null}{step.reason ? <>. <span className="muted">{step.reason}</span></> : null}</p>
          {onReread && <button type="button" onClick={onReread}>Run again</button>}
          <p className="muted">"Run again" reads the stores again; it changes nothing.</p>
        </Section>
      );
    }
    case "job":
      return (
        <Section title="The job">
          <p>
            {step.job?.name && <code className="chip">{step.job.name}</code>}{" "}
            {step.job?.job ? <>Job {step.job.job}: <Pill word={step.job.state} /></> : <span className="muted">No job has been queued yet.</span>}
            {step.at ? <span className="muted"> Ran {dayOf(step.at)}.</span> : null}
          </p>
          <p className="muted">A person runs the command at a terminal; the job's result arrives here.</p>
        </Section>
      );
    case "plan":
      return (
        <Section title="The plan">
          {step.plan?.approval
            ? <p>Approval <code className="chip">{step.plan.approval}</code>: <Pill word={step.plan.status} /></p>
            : <p className="muted">No approval has been made for this step yet; the plan is made when the run reaches it.</p>}
          <p><a href="#/approvals">{WORDS.reviewInApprovals}</a></p>
          <p className="muted">The decision is made and applied in Approvals; the run reads the result.</p>
        </Section>
      );
    case "decision": {
      const d = step.decision;
      return (
        <Section title="The decision">
          <dl className="work-facts">
            <dt>Motion</dt><dd>{d?.motion || step.title}</dd>
            {d?.recorded ? (
              <>
                <dt>Outcome</dt><dd>{d.outcome}</dd>
                {d.record && <><dt>Record</dt><dd>{d.record}</dd></>}
                {d.by && <><dt>Recorded by</dt><dd>{d.by}{d.at ? <>, {dayOf(d.at)}</> : null}</dd></>}
              </>
            ) : (
              <><dt>Outcome</dt><dd className="muted">Not recorded yet</dd></>
            )}
          </dl>
          <p className="muted">The mover, the second, and each director's vote are read on the decision record in Decisions.</p>
          <p><a href="#/decisions">{d?.recorded ? "Read in Decisions" : WORDS.recordInDecisions}</a></p>
        </Section>
      );
    }
    case "wait":
      return (
        <Section title="What it waits for">
          <p>
            {step.waitingOn ? waitingWords(step.waitingOn) : step.reason || "Waiting."}
            {step.clock && <> <BasisPill basis={step.clock.basis} label={step.clock.basisLabel} /></>}
          </p>
          {step.acts.includes("arrived") && (
            <Confirm busy={acts.busy} label="Note an arrival" onConfirm={() => void acts.send({ act: "arrived", step: step.id })}
              summary={<>Note that what step {step.n}, {step.title}, waits for has come, under the name {viewer.name || "the signed-in person"}.</>}>
              Note an arrival
            </Confirm>
          )}
        </Section>
      );
    case "branch":
      return (
        <Section title="The fact it reads">
          <p>{step.title}</p>
          <p>{step.choice ? <>Path chosen: <strong>{step.choice}</strong></> : <span className="muted">No path chosen yet. {step.choices.length ? `The paths are ${step.choices.join(" or ")}.` : ""}</span>}</p>
        </Section>
      );
    default:
      return null;
  }
}

/** The step: its title, its state and whose move it is; why; what to look at; the command; and, by kind, what the page shows
 * and which one control it offers. The act is only what the server says `acts` allows. A step that is not the viewer's says
 * "Waiting on the treasurer" and has no act. An act the step does not offer shows the server's sentence in its place. The
 * page embeds reads and links writes: a plan is decided in Approvals, a decision recorded in Decisions, a job run at a
 * terminal. Only a person's attestation is written here. */
export const RunStepPanel = forwardRef<HTMLHeadingElement, {
  step: RunStep; run: Run; viewer: WorkViewer; acts: Acts; childHref: (l: RunLink) => string | null; onReread?: () => void;
  /** The run's clocks (a per-item clock is read from them), its steps and a way to go to one (a remedy names its check). */
  clocks?: readonly RunClock[]; steps?: readonly RunStep[]; onGo?: (id: string) => void;
}>(function RunStepPanel({ step, run, viewer, acts, childHref, onReread, clocks = [], steps = [], onGo }, ref) {
  const yours = step.yours;
  const refusals = refusalsFor(step);
  const mine = step.acts.includes("attest") && (step.kind === "person" || step.kind === "branch");
  const waiting = !yours && step.waitingOn && !["done", "skipped", "superseded"].includes(step.state);
  const supply = run.acts.supplyItems;
  const setName = step.itemSet ?? "";
  const mayFill = !!(supply?.offered && step.perItem && supply.sets?.some((s) => s.name === setName));
  const notFilled = step.itemAware && step.items.length === 0 && !mayFill && supply && !supply.offered ? supply.why : "";
  return (
    <section className="work-step" aria-labelledby="work-step-h">
      <h2 id="work-step-h" ref={ref} tabIndex={-1}>{step.n}. {step.title}</h2>
      <p className="work-step-meta">
        <StepStateWord state={step.state} changed={step.changed.length > 0} />{" "}
        <span className="muted">{KIND_WORDS[step.kind] ?? step.kind} for the {step.role}</span>
        {yours && <strong className="work-yours"> Your move</strong>}
        {waiting && <strong className="work-waiting"> {waitingWords(step.waitingOn)}</strong>}
      </p>
      {step.state === "failed" && (
        <p className="notice notice-error" role="note">
          This step failed{step.reason ? `: ${step.reason}` : ""}. The {step.role} may resolve it. Nothing is retried by a click.
        </p>
      )}
      {step.state === "blocked" && (
        <p className="notice notice-warn" role="note">Blocked: it waits on {step.blockedBy.length ? step.blockedBy.join(", ") : "another step or a fact"}.</p>
      )}
      <RemedyNote step={step} steps={steps} onGo={onGo} />
      {step.reason && step.state !== "failed" && <p className="muted">{step.reason}</p>}
      {step.changed.length > 0 && (
        <p className="notice notice-warn" role="note">
          <Glyph name="triangle-alert" size="1em" /> {WORDS.changedSince}: {step.changed.map((c) => `${safeAddress(c.address)} (was ${shortHash(c.was)}, now ${shortHash(c.now)})`).join("; ")}.
        </p>
      )}
      <ControlStepNotice controls={step.controls} />
      {step.why && (
        <Section title="Why"><p>{step.why}</p>{step.sop && <p className="muted">Procedure: {step.sop}</p>}</Section>
      )}
      {step.evidence.length > 0 && (
        <Section title="Look at"><ul className="work-evidence-list">{step.evidence.map((e) => <EvidenceRow key={e.address} e={e} />)}</ul></Section>
      )}
      {step.links.length > 0 && (
        <Section title="What this step made"><ul className="work-links">{step.links.map((l) => <LinkRow key={`${l.kind}-${l.id}`} l={l} href={childHref(l)} />)}</ul></Section>
      )}
      {step.command && <Section title="Command"><Command cmd={step.command} /></Section>}
      <KindBlock step={step} run={run} viewer={viewer} acts={acts} onReread={onReread} />
      <ItemTable step={step} clocks={clocks} empty={notFilled ? `No items have been supplied yet. ${notFilled}` : undefined} />
      {mayFill && <SupplyItems step={step} run={run} viewer={viewer} acts={acts} setName={setName} />}
      {step.clock && (
        <p className="work-step-clock">
          Clock: <strong>{step.clock.label || step.clock.slot}</strong> <BasisPill basis={step.clock.basis} label={step.clock.basisLabel} />
          {step.clock.cite && <> <span className="muted">Law: {step.clock.cite}, recited under Clocks.</span></>}
        </p>
      )}
      {(mine || step.acts.length > 0 || refusals.length > 0) && (
        <Section title="What you can do">
          {mine && <MarkDone step={step} run={run} viewer={viewer} acts={acts} />}
          {step.acts.includes("skip") && (
            <TextConfirm trigger="Skip this step" field="Why it is skipped" required={step.skip?.reasonRequired ?? true} busy={acts.busy} label="Skip"
              summary={(reason) => <>Skip step {step.n}, {step.title}, under the name {viewer.name || "the signed-in person"}{reason ? <>, because: <q>{reason}</q></> : null}. A skip is a decision with a reason; it is on the history.</>}
              onConfirm={(reason) => void acts.send({ act: "skip", step: step.id, reason })} />
          )}
          {step.acts.includes("reopen") && (
            <TextConfirm trigger="Reopen this step" field="Why it is reopened" busy={acts.busy} label="Reopen"
              summary={(reason) => <>Open step {step.n}, {step.title}, again under the name {viewer.name || "the signed-in person"}, because: <q>{reason}</q>. What was done stays on the history.</>}
              onConfirm={(reason) => void acts.send({ act: "reopen", step: step.id, reason })} />
          )}
          {refusals.map((r) => <p key={r.act} className="muted work-not-offered" data-act={r.act}>{r.why}</p>)}
        </Section>
      )}
      {run.acts.note.offered && (
        <details className="work-step-note">
          <summary>Add a note to this step</summary>
          <TextConfirm trigger="Add the note" field="The note" busy={acts.busy} label="Note" rows={2}
            summary={(text) => <>Add a note to step {step.n} under the name {viewer.name || "the signed-in person"}: <q>{text}</q></>}
            onConfirm={(text) => void acts.send({ act: "note", step: step.id, text })} />
        </details>
      )}
      <ActStatus said={acts.said} onReload={onReread} />
    </section>
  );
});
