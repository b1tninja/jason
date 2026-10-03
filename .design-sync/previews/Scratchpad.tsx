import type { ReactNode } from "react";
import { Scratchpad } from "jason-ui";

/* Harness glue: the scratchpad loads `/api/dock?part=notes`; there is no server in the capture. The fixture is the shape
 * `jason.web.extra.dock._notes()` returns. Opening a note is internal state, so the cells show the list. */
const note = (id: string, title: string, status: string, body: string, sources: string[], by: string, created: string, updated: string) =>
  ({ id, title, status, body, sources, created, updated, by });

const notes = [
  note("n1", "Reserve study vendors", "question", "Ask three firms for a level-one study. Two answered the 2023 bid; the third is new to the county.",
    ["CIV 5550", "Finance/Reserve study 2023.pdf"], "D. Okafor", "2026-10-01T16:00:00+00:00", "2026-10-02T21:10:00+00:00"),
  note("n2", "Pool deck resurfacing", "researching", "Two bids in. Clearwater wants the deck closed for nine days; the other quote says five.",
    ["Vendors/Clearwater Pools/quote 2026-09.pdf"], "M. Chen", "2026-09-26T18:00:00+00:00", "2026-09-30T15:20:00+00:00"),
  note("n3", "Tree trimming schedule", "parked", "Wait for the arborist's report before setting dates.", [], "P. Quinn", "2026-09-12T17:00:00+00:00", "2026-09-12T17:00:00+00:00"),
];
const statuses = ["researching", "question", "draft", "parked", "done"];
const caveat = "Working notes, not association records.";

const NOTES: Record<string, unknown> = {
  default: { found: true, count: 3, notes, statuses, caveat },
  empty: { found: true, count: 0, notes: [], statuses, caveat },
};

let variant = "default";
const FIXTURES: Record<string, Record<string, unknown>> = { "/api/dock?part=notes": NOTES };
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

/** A board member's three working notes, each a card with its status pill, a one-line preview, and when it was last touched; New note is live. */
export const Board = () => (
  <WithFixture name="default">
    <Scratchpad me="D. Okafor" />
  </WithFixture>
);

/** No name yet: the "Your name" field on top and New note held back until someone says who is writing. */
export const NoName = () => (
  <WithFixture name="default">
    <Scratchpad />
  </WithFixture>
);

/** No notes yet: the count reads 0 notes, New note ready, the caveat under it. */
export const Empty = () => (
  <WithFixture name="empty">
    <Scratchpad me="P. Quinn" />
  </WithFixture>
);
