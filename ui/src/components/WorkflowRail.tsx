import { useState, type ReactNode } from "react";
import { StepStateWord } from "./StepStateWord";
import { SETTLED_STEP_STATES, railPhases, type RailPhase, type RunGroup, type RunLink, type RunPage, type RunStep } from "../lib/work";

/** A child run as one row of the rail: its label and state, a link when its address is known. */
function ChildRun({ link, href }: { link: RunLink; href: string | null }) {
  const label = link.label || link.id;
  const state = link.state || "state not read here";
  return (
    <li className="work-rail-child">
      {href ? <a href={href}>Child run: {label}</a> : <span>Child run: {label}</span>} <span className="muted">({state})</span>
    </li>
  );
}

/** "3 of 12 items" for a step that counts its items by state (round three), or nothing. */
function itemWords(step: RunStep): string {
  const counts = Object.values(step.itemCounts ?? {});
  const total = counts.reduce((a, n) => a + n, 0);
  return total > 0 ? `${step.itemCounts?.done ?? 0} of ${total} ${total === 1 ? "item" : "items"} done` : "";
}

function StepItem({ step, selected, onSelect, children, href }: {
  step: RunStep; selected: boolean; onSelect: (id: string) => void; children: RunLink[]; href: (l: RunLink) => string | null;
}) {
  const items = itemWords(step);
  return (
    <>
      <li className={`work-rail-step${step.current ? " work-rail-current" : ""}${selected ? " work-rail-selected" : ""}`}>
        <button type="button" aria-current={step.current ? "step" : undefined} aria-pressed={selected} onClick={() => onSelect(step.id)}>
          <StepStateWord state={step.state} changed={step.changed.length > 0} />
          <span className="work-rail-n">{step.n}</span>
          <span className="work-rail-title">{step.title}</span>
          {step.current && <span className="work-rail-here">current step</span>}
          {items && <span className="work-rail-items muted">{items}</span>}
        </button>
      </li>
      {children.map((l) => <ChildRun key={`${l.kind}-${l.id}`} link={l} href={href(l)} />)}
    </>
  );
}

/** A step group the definition titles (`Workflow.groups`): a collapsible section with its title, its roll-up state, and how many of
 * its steps are done. It is open where the fold says so (it holds the run's current step or a failed one) or where the step the
 * person picked stands; a person's own click on it wins until the page is left. */
function GroupBlock({ group, steps, selected, id, children }: {
  group: RunGroup; steps: RunStep[]; selected: string; id: string; children: ReactNode;
}) {
  const [picked, setPicked] = useState<boolean | null>(null);
  const open = picked ?? (group.expanded || steps.some((s) => s.id === selected || s.current));
  return (
    <li className="work-rail-group work-rail-section" data-group={group.key} data-expanded={open ? "true" : "false"}>
      <h4 className="work-rail-section-h">
        <button type="button" className="work-rail-phase-toggle" aria-expanded={open} aria-controls={`${id}-list`} onClick={() => setPicked(!open)}>
          <span aria-hidden="true">{open ? "▾" : "▸"}</span> {group.title}{" "}
          <StepStateWord state={group.state} />
          <span className="muted work-rail-count"> {group.done} of {group.total} done</span>
        </button>
      </h4>
      <ol id={`${id}-list`} aria-label={`${group.title} steps`} hidden={!open}>{children}</ol>
    </li>
  );
}

function Phase({ phase, selected, onSelect, open: initial, childOf, href, groups }: {
  phase: RailPhase; selected: string; onSelect: (id: string) => void; open: boolean; childOf: (s: RunStep) => RunLink[]; href: (l: RunLink) => string | null;
  groups: readonly RunGroup[];
}) {
  const [open, setOpen] = useState(initial);
  const done = phase.steps.filter((s) => SETTLED_STEP_STATES.includes(s.state)).length;
  const id = `rail-${phase.key}`;
  return (
    <section className="work-rail-phase" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`}>
        <button type="button" className="work-rail-phase-toggle" aria-expanded={open} aria-controls={`${id}-list`} onClick={() => setOpen((o) => !o)}>
          <span aria-hidden="true">{open ? "▾" : "▸"}</span> {phase.title}
          <span className="muted work-rail-count"> {done} of {phase.steps.length} done</span>
        </button>
      </h3>
      <ol id={`${id}-list`} className="work-rail-list" hidden={!open}>
        {phase.blocks.map((b, i) => {
          const items = b.steps.map((s) => (
            <StepItem key={s.id} step={s} selected={s.id === selected} onSelect={onSelect} children={childOf(s)} href={href} />
          ));
          const titled = groups.find((g) => g.key === b.group);
          if (titled) return <GroupBlock key={`g${i}`} group={titled} steps={b.steps} selected={selected} id={`${id}-g${i}`}>{items}</GroupBlock>;
          return b.group && b.steps.length > 1 ? (
            <li key={`g${i}`} className="work-rail-group">
              <span className="work-rail-group-name" id={`${id}-g${i}`}>{b.group}</span>
              <ol aria-labelledby={`${id}-g${i}`}>{items}</ol>
            </li>
          ) : items;
        })}
      </ol>
    </section>
  );
}

/** The rail: every step of the run, its state as a word and a glyph, grouped by the definition's phases, the current step
 * marked. A phase with every step settled folds to one line (its count of steps done) and the phase with work stays open; a step
 * group shows under its own prefix; a child run is one row that links to it. On a narrow screen (`compact`) it is a
 * collapsed "Step 9 of 25: Read the returned forms" header that opens the list. */
export function WorkflowRail({ page, selected, onSelect, href, compact = false }: {
  page: Pick<RunPage, "phases" | "steps" | "links"> & { groups?: RunGroup[] }; selected: string; onSelect: (id: string) => void;
  /** The address of a child run's page, or null when it is not known. */
  href: (link: RunLink) => string | null; compact?: boolean;
}) {
  const [shown, setShown] = useState(false);
  const phases = railPhases(page);
  const here = page.steps.find((s) => s.id === selected) ?? page.steps.find((s) => s.current) ?? page.steps[0];
  const childOf = (s: RunStep): RunLink[] => page.links.filter((l) => l.kind === "run" && l.step === s.id);
  const list = (
    <>
      {phases.map((p) => (
        <Phase key={p.key} phase={p} selected={selected} onSelect={onSelect} childOf={childOf} href={href} groups={page.groups ?? []}
          open={p.steps.some((s) => s.current || s.id === selected || !SETTLED_STEP_STATES.includes(s.state))} />
      ))}
    </>
  );
  if (!compact) {
    return (
      <nav className="work-rail" aria-label="Steps of this run">
        <h2>Steps</h2>
        {list}
      </nav>
    );
  }
  return (
    <nav className="work-rail work-rail-compact" aria-label="Steps of this run">
      <h2 className="visually-hidden">Steps</h2>
      <button type="button" className="work-rail-summary" aria-expanded={shown} aria-controls="work-rail-all" onClick={() => setShown((v) => !v)}>
        Step {here?.n ?? 0} of {page.steps.length}: {here?.title ?? ""}
      </button>
      <div id="work-rail-all" hidden={!shown}>{list}</div>
    </nav>
  );
}
