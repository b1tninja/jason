import { DockDrawerBody } from "jason-ui";

/* Harness glue: each drawer body loads its own part of `/api/dock`; there is no server in the capture. The fixtures are
 * the shapes `jason.web.extra.dock` returns, read as of 2026-10-03. */
const caveat = "Working notes, not association records.";
const FIXTURES: Record<string, unknown> = {
  "/api/dock?part=deadlines": {
    found: true, asOf: "2026-10-03", today: "2026-10-03", counts: { overdue: 1, soon: 2, later: 1 },
    caveats: ["The dates are what jason computed from the calendar; a payment is evidence a thing was done, not proof."],
    groups: [
      { key: "overdue", label: "Overdue", rows: [{ id: "d1", title: "D&O renewal certificate", date: "2026-09-30", days: -3, authority: "the policy term", standing: "overdue", note: "", screen: "insurance" }] },
      { key: "soon", label: "Next 14 days", rows: [
        { id: "d2", title: "Budget report to members", date: "2026-10-10", days: 7, authority: "CIV 5300", standing: "due soon", note: "", screen: "reserves" },
        { id: "d3", title: "Agenda notice for the October 21 meeting", date: "2026-10-17", days: 14, authority: "CIV 4920", standing: "due soon", note: "", screen: "meetings" },
      ] },
      { key: "later", label: "Later", rows: [{ id: "d4", title: "Reserve study update", date: "2026-11-15", days: 43, authority: "CIV 5550", standing: "scheduled", note: "", screen: "reserves" }] },
    ],
    clock: [
      { key: "d1", label: "D&O renewal certificate", date: "2026-09-30", authority: "the policy term" },
      { key: "d2", label: "Budget report to members", date: "2026-10-10", authority: "CIV 5300" },
      { key: "d3", label: "Agenda notice for the October 21 meeting", date: "2026-10-17", authority: "CIV 4920" },
      { key: "d4", label: "Reserve study update", date: "2026-11-15", authority: "CIV 5550" },
    ],
  },
  "/api/dock?part=tasks": {
    found: true, today: "2026-10-03", count: 3, overdue: 1, open: 2, editable: ["text", "owner", "due", "screen"],
    caveats: ["The register is what people said needs doing; jason assigns nothing and marks nothing done."],
    tasks: [
      { id: "t1", text: "Collect two landscape bids", source: "manual", screen: "", owner: "D. Okafor", due: "2026-09-20", done: false, doneBy: "", doneAt: "", created: "2026-09-01T16:00:00+00:00", by: "D. Okafor" },
      { id: "t2", text: "Review the draft minutes", source: "meetings", screen: "meetings", owner: "P. Quinn", due: "2026-10-16", done: false, doneBy: "", doneAt: "", created: "2026-09-24T18:30:00+00:00", by: "P. Quinn" },
      { id: "t4", text: "Ask the broker for the fidelity bond certificate", source: "ask", screen: "insurance", owner: "M. Chen", due: "2026-09-26", done: true, doneBy: "M. Chen", doneAt: "2026-09-29T17:45:00+00:00", created: "2026-09-12T15:00:00+00:00", by: "M. Chen" },
    ],
  },
  "/api/dock?part=notes": {
    found: true, count: 2, statuses: ["researching", "question", "draft", "parked", "done"], caveat,
    notes: [
      { id: "n1", title: "Reserve study vendors", status: "question", body: "Ask three firms for a level-one study.", sources: ["CIV 5550"], created: "2026-10-01T16:00:00+00:00", updated: "2026-10-02T21:10:00+00:00", by: "D. Okafor" },
      { id: "n2", title: "Pool deck resurfacing", status: "researching", body: "Two bids in. Clearwater wants the deck closed for nine days.", sources: [], created: "2026-09-26T18:00:00+00:00", updated: "2026-09-30T15:20:00+00:00", by: "M. Chen" },
    ],
  },
  "/api/dock?part=ask": {
    found: true, translationStates: ["needs review", "sent for review", "approved"], translateCommand: "",
    routedAnswer: "jason has no sourced answer for this. It went to the action register for the manager to answer.",
    caveats: ["A question with no sourced answer goes to the action register for the manager. jason never guesses."],
    common: [
      { question: "When is the next board meeting?", screen: "meetings", answer: "The next board meeting is 2026-10-21.", sources: ["meeting()", "CIV 4920"], routed: false },
      { question: "What is due this month?", screen: "calendar", answer: "Due in 2026-10: Budget report to members by 2026-10-10 (CIV 5300).", sources: ["association_calendar()", "CIV 5300"], routed: false },
      { question: "What is overdue?", screen: "calendar", answer: "Overdue: D&O renewal certificate (2026-09-30, 3d).", sources: ["association_calendar()"], routed: false },
      { question: "What did the board decide last meeting?", screen: "decisions", answer: "", sources: [], routed: true },
      { question: "Where are the minutes?", screen: "records", answer: "The minutes are kept at Governance/Minutes (41 files; newest 2026-09-16).", sources: ["records_inventory()", "CIV 5200(a)(8)"], routed: false },
    ],
    asks: [],
    translations: [{ id: "x1", englishKey: "notice-2026-10-21", english: "The board meets October 21.", language: "Spanish", draft: "La junta se reúne el 21 de octubre.", state: "needs review", by: "D. Okafor", at: "2026-10-02T22:00:00+00:00" }],
  },
};
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const key = Object.keys(FIXTURES).find((k) => url.startsWith(k));
  if (!key) return realFetch(input, init);
  return new Response(JSON.stringify(FIXTURES[key]), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

const noop = () => {};

/** The deadlines drawer by id: the calendar's rows grouped Overdue, Next 14 days, Later. */
export const Deadlines = () => <DockDrawerBody id="deadlines" go={noop} />;

/** The tasks drawer with a name given: the action register's Open filter, checkboxes live. */
export const Tasks = () => <DockDrawerBody id="tasks" go={noop} me="D. Okafor" />;

/** The notes drawer with no name yet: the scratchpad asks who is writing before New note. */
export const Notes = () => <DockDrawerBody id="notes" go={noop} />;

/** The ask drawer: Ask jason's common questions. */
export const Ask = () => <DockDrawerBody id="ask" go={noop} me="D. Okafor" />;

/** An id no drawer answers to: a muted line, not a crash. */
export const Unknown = () => <DockDrawerBody id="minutes" go={noop} />;
