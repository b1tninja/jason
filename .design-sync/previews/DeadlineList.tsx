import type { ReactNode } from "react";
import { DeadlineList } from "jason-ui";

/* Harness glue: the drawer loads `/api/dock?part=deadlines`; there is no server in the capture. The fixture is the
 * shape `jason.web.extra.dock.deadlines()` returns, read as of 2026-10-03. */
const row = (id: string, title: string, date: string, days: number, authority: string, screen: string) =>
  ({ id, title, date, days, authority, standing: days < 0 ? "overdue" : days <= 14 ? "due soon" : "scheduled", note: "", screen });

const overdue = [
  row("d1", "Annual policy statement to members", "2026-09-28", -5, "CIV 5310", "disclosures"),
  row("d2", "D&O renewal certificate", "2026-09-30", -3, "the policy term", "insurance"),
];
const soon = [
  row("d3", "Budget report to members", "2026-10-10", 7, "CIV 5300", "reserves"),
  row("d4", "Agenda notice for the October 21 meeting", "2026-10-17", 14, "CIV 4920", "meetings"),
];
const later = [
  row("d5", "Reserve study update", "2026-11-15", 43, "CIV 5550", "reserves"),
  row("d6", "Election notice", "2026-12-01", 59, "CIV 5115", "disclosures"),
];
const clock = (rows: ReturnType<typeof row>[]) => rows.filter((r) => Math.abs(r.days) <= 45).map((r) => ({ key: r.id, label: r.title, date: r.date, authority: r.authority }));
const groups = (o: typeof overdue, s: typeof soon, l: typeof later) => [
  { key: "overdue", label: "Overdue", rows: o },
  { key: "soon", label: "Next 14 days", rows: s },
  { key: "later", label: "Later", rows: l },
];
const caveats = ["The dates are what jason computed from the calendar; a payment is evidence a thing was done, not proof."];

const DEADLINES: Record<string, unknown> = {
  default: { found: true, asOf: "2026-10-03", today: "2026-10-03", groups: groups(overdue, soon, later), clock: clock([...overdue, ...soon, ...later]),
    counts: { overdue: 2, soon: 2, later: 2 }, caveats },
  quiet: { found: true, asOf: "2026-10-03", today: "2026-10-03", groups: groups([], [soon[0]], later), clock: clock([soon[0], ...later]),
    counts: { overdue: 0, soon: 1, later: 2 }, caveats },
  empty: { found: false, note: "calendar not read: the profile's calendar is not on disk", asOf: "2026-10-03", groups: groups([], [], []), clock: [],
    counts: { overdue: 0, soon: 0, later: 0 } },
};

let variant = "default";
const FIXTURES: Record<string, Record<string, unknown>> = { "/api/dock?part=deadlines": DEADLINES };
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

/** A board's week: two overdue rows in red, two due within 14 days, two later, each linking to the screen that works it, the 45-day clock collapsed. */
export const Board = () => (
  <WithFixture name="default">
    <DeadlineList go={() => {}} />
  </WithFixture>
);

/** Nothing overdue: the Overdue group says so, one row due soon, the later ones scheduled. */
export const Quiet = () => (
  <WithFixture name="quiet">
    <DeadlineList go={() => {}} />
  </WithFixture>
);

/** The calendar not read (`found: false`): the remote view shows the loader's note in place of the groups, a miss said plainly. */
export const NoCalendar = () => (
  <WithFixture name="empty">
    <DeadlineList go={() => {}} />
  </WithFixture>
);
