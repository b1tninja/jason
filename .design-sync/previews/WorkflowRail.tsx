import { useEffect, useRef, useState } from "react";
import { WorkflowRail } from "jason-ui";

// Made-up run of the "Owner information cycle" for "Oakview", with 2099 dates. The rail is controlled: a small wrapper keeps the
// selected step, as the run page does with the URL. Types are not exported from jason-ui, so the rows are inline objects.
const step = (over: any): any => ({
  of: 12, role: "manager", state: "not started", reason: "", phase: "collect", phaseTitle: "Collect", group: "", why: "", command: "",
  sop: "", legal: false, needsRecord: "", record: "", by: "", at: "", current: false, blockedBy: [], items: [], choice: "", choices: [],
  spawns: null, skip: null, clock: null, evidence: [], links: [], changed: [], waitingOn: null, yours: false, acts: [], notOffered: {}, ...over,
});
const link = (id: string, label: string, state: string, stepId: string) => ({ kind: "run", id, step: stepId, label, state, read: true, screen: "work" });

const STEPS = [
  step({ id: "oi.check-data", n: 1, title: "Check the data", kind: "check", state: "done", phase: "prepare" }),
  step({ id: "oi.board-decides", n: 2, title: "The board adopts the cycle", kind: "decision", state: "done", phase: "prepare" }),
  step({ id: "oi.send-plan", n: 3, title: "Plan the owner-information send", kind: "plan", state: "done", phase: "send",
    changed: [{ address: "file:forms/campaigns.json", was: "1a2b3c4d", now: "9f8e7d6c" }] }),
  step({ id: "oi.delivery", n: 4, title: "Notice delivery", kind: "wait", state: "done", phase: "send", spawns: "notice-delivery" }),
  step({ id: "oi.mailroom", n: 5, title: "Mailroom batch 1", kind: "wait", state: "waiting", phase: "send", spawns: "mailroom-batch" }),
  step({ id: "oi.read-forms", n: 6, title: "Read the returned forms", kind: "person", state: "needs a person", current: true, yours: true,
    itemCounts: { done: 3, "not started": 9 } }),
  step({ id: "oi.apply-tags", n: 7, title: "Apply the tags", kind: "job", state: "ready", group: "response" }),
  step({ id: "oi.record-answers", n: 8, title: "Record what the answers say", kind: "person", state: "not started", group: "response" }),
  step({ id: "oi.answers-by", n: 9, title: "Answers by", kind: "wait", state: "waiting" }),
  step({ id: "oi.choose", n: 10, title: "Is the cycle complete?", kind: "branch", state: "not started", phase: "close", phaseTitle: "Close" }),
  step({ id: "oi.close", n: 11, title: "Close the cycle", kind: "person", state: "not started", role: "secretary", phase: "close", phaseTitle: "Close" }),
];
const PHASES = [
  { key: "prepare", title: "Prepare", steps: ["oi.check-data", "oi.board-decides"] },
  { key: "send", title: "Send", steps: ["oi.send-plan", "oi.delivery", "oi.mailroom"] },
  { key: "collect", title: "Collect", steps: ["oi.read-forms", "oi.apply-tags", "oi.record-answers", "oi.answers-by"] },
  { key: "close", title: "Close", steps: ["oi.choose", "oi.close"] },
];
const LINKS = [link("run-7b8c9d0e1f", "Notice delivery", "done", "oi.delivery"), link("run-8c9d0e1f2a", "Mailroom batch 1", "waiting", "oi.mailroom")];
const PAGE = { phases: PHASES, steps: STEPS, links: LINKS };
const href = (l: { id: string }) => `#/work/notice-delivery/${l.id}`;

const Rail = ({ page = PAGE, start = "oi.read-forms", compact = false }: { page?: any; start?: string; compact?: boolean }) => {
  const [selected, setSelected] = useState(start);
  return <div style={{ maxWidth: 360 }}><WorkflowRail page={page} selected={selected} onSelect={setSelected} href={href} compact={compact} /></div>;
};

/** The run's steps by phase: finished phases fold to a count, the phase with work stays open, and the current step is marked. */
export const Standard = () => <Rail />;

/** A child run is one row under the step that spawned it, linking to its page; a step counted by item shows "3 of 12 items done". */
export const ChildRunsAndItems = () => (
  <Rail start="oi.mailroom" page={{
    ...PAGE,
    steps: STEPS.map((s) => s.id === "oi.mailroom" ? { ...s, current: true, state: "waiting" } : s.id === "oi.read-forms" ? { ...s, current: false, itemCounts: { done: 3, "not started": 9 } } : s),
  }} />
);

/** A step group the definition titles is a collapsible section with its own state and count, open where the current step is. */
export const TitledGroups = () => (
  <Rail page={{
    ...PAGE,
    groups: [{ key: "response", title: "Responses", steps: ["oi.apply-tags", "oi.record-answers"], state: "ready", done: 0, total: 2, expanded: true, current: "" }],
  }} />
);

/** A failed step and a blocked one: the state is a word and a glyph, never colour alone. */
export const FailedAndBlocked = () => (
  <Rail start="oi.apply-tags" page={{
    ...PAGE,
    steps: STEPS.map((s) =>
      s.id === "oi.read-forms" ? { ...s, state: "failed", current: false } : s.id === "oi.apply-tags" ? { ...s, state: "blocked" } : s.id === "oi.record-answers" ? { ...s, state: "skipped" } : s),
  }} />
);

/** On a narrow screen the rail is one line, "Step 6 of 11: Read the returned forms". */
export const CompactClosed = () => <Rail compact />;

/** The compact header opened: the same phases and steps below it. */
export const CompactOpen = () => {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const t = setTimeout(() => box.current?.querySelector<HTMLButtonElement>("button.work-rail-summary")?.click(), 30);
    return () => clearTimeout(t);
  }, []);
  return <div ref={box}><Rail compact /></div>;
};
