import type { ReactNode } from "react";
import { ActionRegister } from "jason-ui";

/* Harness glue: the register loads `/api/dock?part=tasks`; there is no server in the capture. The fixture is the shape
 * `jason.web.extra.dock._tasks()` returns, read as of 2026-10-03. Writes stay behind Confirm and are never faked. */
const task = (id: string, text: string, owner: string, due: string, source: string, screen: string, by: string, created: string) =>
  ({ id, text, source, screen, owner, due, done: false, doneBy: "", doneAt: "", created, by });

const tasks = [
  task("t1", "Collect two landscape bids", "D. Okafor", "2026-09-20", "manual", "", "D. Okafor", "2026-09-01T16:00:00+00:00"),
  task("t2", "Review the draft minutes", "P. Quinn", "2026-10-16", "meetings", "meetings", "P. Quinn", "2026-09-24T18:30:00+00:00"),
  task("t3", "Follow up: Reserve study vendors", "", "", "scratchpad", "", "D. Okafor", "2026-10-02T21:10:00+00:00"),
  { ...task("t4", "Ask the broker for the fidelity bond certificate", "M. Chen", "2026-09-26", "ask", "insurance", "M. Chen", "2026-09-12T15:00:00+00:00"),
    done: true, doneBy: "M. Chen", doneAt: "2026-09-29T17:45:00+00:00" },
];
const caveats = ["The register is what people said needs doing; jason assigns nothing and marks nothing done."];

const TASKS: Record<string, unknown> = {
  default: { found: true, today: "2026-10-03", count: 4, overdue: 1, open: 3, tasks, editable: ["text", "owner", "due", "screen"], caveats },
  empty: { found: true, today: "2026-10-03", count: 0, overdue: 0, open: 0, tasks: [], editable: ["text", "owner", "due", "screen"], caveats },
};

let variant = "default";
const FIXTURES: Record<string, Record<string, unknown>> = { "/api/dock?part=tasks": TASKS };
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const key = Object.keys(FIXTURES).find((k) => url.startsWith(k));
  if (!key) return realFetch(input, init);
  const body = FIXTURES[key][variant] ?? FIXTURES[key].default;
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

/** Picks the fixture the cell loads: set during render, read when the child's effect calls fetch. */
function WithFixture({ name, children }: { name: string; children: ReactNode }) {
  variant = name;
  return <>{children}</>;
}

/** A board member signed in: the Open filter selected with its counts, one row overdue in red, one unassigned from the Scratchpad, the done checkboxes live. */
export const Board = () => (
  <WithFixture name="default">
    <ActionRegister go={() => {}} me="D. Okafor" />
  </WithFixture>
);

/** No name yet: the "Your name" field on top, the checkboxes disabled until someone says who they are, and Add task held back. */
export const NoName = () => (
  <WithFixture name="default">
    <ActionRegister go={() => {}} />
  </WithFixture>
);

/** An empty register: every filter at zero, "Nothing here.", and the quick-add form waiting for a task. */
export const Empty = () => (
  <WithFixture name="empty">
    <ActionRegister go={() => {}} me="P. Quinn" />
  </WithFixture>
);
