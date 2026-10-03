import type { ReactNode } from "react";
import { AskPanel } from "jason-ui";

/* Harness glue: the panel loads `/api/dock?part=ask`; there is no server in the capture. The fixture is the shape
 * `jason.web.extra.dock._ask()` returns. The Translate tab and a shown answer are internal state, so the cells show the
 * Ask tab as it first renders. */
const common = [
  { question: "When is the next board meeting?", screen: "meetings", routed: false,
    answer: "The next board meeting is 2026-10-21. The agenda notice is due by 2026-10-17 (CIV 4920); an executive-only meeting's by 2026-10-19. 4 open-session and 1 executive items are proposed or on the agenda.",
    sources: ["meeting()", "CIV 4920"] },
  { question: "What is due this month?", screen: "calendar", routed: false,
    answer: "Due in 2026-10: Budget report to members by 2026-10-10 (CIV 5300); Agenda notice for the October 21 meeting by 2026-10-17 (CIV 4920).",
    sources: ["association_calendar()", "CIV 4920", "CIV 5300"] },
  { question: "What is overdue?", screen: "calendar", routed: false, answer: "Overdue: Annual policy statement to members (2026-09-28, 5d); D&O renewal certificate (2026-09-30, 3d).", sources: ["association_calendar()"] },
  { question: "What did the board decide last meeting?", screen: "decisions", routed: true, answer: "", sources: [] },
  { question: "Where are the minutes?", screen: "records", routed: false,
    answer: "The minutes are kept at Governance/Minutes (41 files; newest 2026-09-16). Newest in the library: Governance/Minutes/2026-09-16 open session.pdf (2026-09).",
    sources: ["records_inventory()", "CIV 5200(a)(8)", "library_search(kind=minutes)"] },
];
const asks = [
  { id: "q2", question: "Can the board fine an owner without a hearing?", answer: "", sources: [], screen: "", routed: true, at: "2026-10-02T20:15:00+00:00", by: "P. Quinn", task: "t5" },
  { id: "q1", question: "How much notice does a special assessment need?", answer: "The phrase appears in 2 library file(s): Governing/CC&Rs 2004.pdf (ccrs); Finance/Budget letter 2025.pdf (letter, 2025). Read the file; this is where the words were found, not a finding.",
    sources: ["library_search(words='special assessment notice')", "Governing/CC&Rs 2004.pdf", "Finance/Budget letter 2025.pdf"], screen: "records", routed: false, at: "2026-09-29T17:40:00+00:00", by: "M. Chen" },
];
const translations = [
  { id: "x1", englishKey: "notice-2026-10-21", english: "The board meets Wednesday, October 21, at 6:30 p.m. in the clubhouse. Owners may speak during open forum.",
    language: "Spanish", draft: "La junta se reúne el miércoles 21 de octubre a las 6:30 p.m. en la casa club. Los propietarios pueden hablar durante el foro abierto.",
    state: "needs review", by: "D. Okafor", at: "2026-10-02T22:00:00+00:00" },
];
const ASK = {
  found: true, common, asks, translations, translationStates: ["needs review", "sent for review", "approved"], translateCommand: "",
  routedAnswer: "jason has no sourced answer for this. It went to the action register for the manager to answer.",
  caveats: [
    "Answers come from the association's records and jason's stores, and cite where each was read. They are not legal advice.",
    "A question with no sourced answer goes to the action register for the manager. jason never guesses.",
    "A translation is a person's draft marked needs review; the English notice controls.",
  ],
};

const FIXTURES: Record<string, unknown> = { "/api/dock?part=ask": ASK };
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const key = Object.keys(FIXTURES).find((k) => url.startsWith(k));
  if (!key) return realFetch(input, init);
  return new Response(JSON.stringify(FIXTURES[key]), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

/** The drawer's width, with the panel's input rules (`.dock-panel`) so the "Your name" field above the tabs is styled as the tabs' own inputs are. */
const Frame = ({ children }: { children: ReactNode }) => <div className="dock-panel" style={{ maxWidth: 440 }}>{children}</div>;

/** A board member on the Ask tab: the question box with Ask held back until typed, the five common questions, two asked before (one routed), the caveats. */
export const Board = () => (
  <Frame>
    <AskPanel go={() => {}} me="D. Okafor" />
  </Frame>
);

/** An owner with no name yet: the "Your name" field above the tabs and the note that a name is needed to record who asked. */
export const NoName = () => (
  <Frame>
    <AskPanel go={() => {}} />
  </Frame>
);
