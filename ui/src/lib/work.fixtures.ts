import type {
  ActAnswer, BasisInfo, DefinitionPageData, DefinitionRow, DefinitionsPage, HistoryEvent, LawWords, Run, RunClock, RunLink, RunPage,
  RunStep, StartAnswer, StartDry, WaitingOn, WorkDue, WorkPage, WorkRow,
} from "./work";

// Made-up data for the Work screens: "Oakview", a community that does not exist, with 2099 dates. The shapes are the
// loaders' (`jason.web.extra.work`); the words are the engine's. No real association, owner, street, or statute.

export const AS_OF = "2099-10-09";
export const MANAGER = "A. Manager";

const BASIS: Record<string, BasisInfo> = {
  law: { basis: "law", basisLabel: "LEGAL", legal: true, proposed: false },
  documents: { basis: "documents", basisLabel: "DOCUMENTS", legal: false, proposed: false },
  counterparty: { basis: "counterparty", basisLabel: "COUNTERPARTY", legal: false, proposed: false },
  "proposed policy": { basis: "proposed policy", basisLabel: "PROPOSED", legal: false, proposed: true },
  person: { basis: "person", basisLabel: "PERSON", legal: false, proposed: false },
};

export function due(date: string, basis: keyof typeof BASIS, days: number, over: Partial<WorkDue> = {}): WorkDue {
  return { date, label: "", cite: "", status: days < 0 ? "overdue" : "upcoming", days, step: "", ...BASIS[basis], ...over };
}

const age = (days: number) => ({ days, opened: "2099-10-01", idleDays: 1, updated: "2099-10-08T08:12:00Z" });

export function row(over: Partial<WorkRow> & Pick<WorkRow, "id" | "definition" | "label" | "group">): WorkRow {
  return {
    definitionTitle: over.definition, family: "members", subjectKind: "campaign", state: "active",
    current: { id: `${over.definition}.1`, title: "A step", n: 1, of: 5, kind: "person", state: "needs a person", role: "manager" },
    owner: "manager", waitingOn: { kind: "office", word: "the manager", role: "manager", detail: "" }, mine: false, due: null,
    pastLaw: false, age: age(8), paused: false, pausedReason: "", ...over,
  };
}

export const OWNER_INFO_ROW = row({
  id: "run-0a1b2c3d4e", definition: "owner-info-cycle", definitionTitle: "Owner information cycle", label: "Owner information 2099",
  group: "yours", mine: true,
  current: { id: "oi.read-forms", title: "Read the returned forms", n: 6, of: 12, kind: "person", state: "needs a person", role: "manager" },
  due: due("2099-10-23", "documents", 14, { label: "Answers by", step: "oi.read-forms" }),
});
export const BILL_ROW = row({
  id: "run-1b2c3d4e5f", definition: "bill-attach", definitionTitle: "Bill attachment", family: "money", label: "Bill attach: Example Electric, Oct",
  group: "yours", mine: true,
  current: { id: "ba.approve", title: "Approve the attachments", n: 4, of: 7, kind: "person", state: "needs a person", role: "treasurer" },
  owner: "treasurer", waitingOn: { kind: "office", word: "the treasurer", role: "treasurer", detail: "" },
  due: due("2099-10-14", "person", 5),
});
export const HEARING_ROW = row({
  id: "run-2c3d4e5f6a", definition: "hearing", definitionTitle: "Hearing", family: "members", label: "Hearing H-7", group: "others",
  current: { id: "hr.reply", title: "The member's reply", n: 6, of: 9, kind: "wait", state: "waiting", role: "secretary" },
  owner: "secretary", waitingOn: { kind: "arrival", word: "an arrival", role: "secretary", detail: "the member's written reply" },
  due: due("2099-11-02", "documents", 24),
});
export const BACKFLOW_ROW = row({
  id: "run-3d4e5f6a7b", definition: "backflow-annual", definitionTitle: "Annual backflow test", family: "life-safety", label: "Annual backflow test",
  group: "clock",
  current: { id: "bf.report", title: "The vendor's report", n: 3, of: 6, kind: "wait", state: "waiting", role: "manager" },
  waitingOn: { kind: "clock", word: "a clock", role: "manager", detail: "report due" },
  due: due("2099-12-01", "counterparty", 53),
});
export const RULE_ROW = row({
  id: "run-4e5f6a7b8c", definition: "rule-change", definitionTitle: "Rule change", family: "governance", label: "Rule change: quiet hours",
  group: "board",
  current: { id: "rc.decide", title: "The board decides", n: 13, of: 18, kind: "decision", state: "needs a person", role: "secretary" },
  owner: "secretary", waitingOn: { kind: "board", word: "the board; the secretary records", role: "secretary", detail: "" },
  due: due("2099-11-14", "law", 36, { cite: "EX 321.1" }),
});
export const ELECTION_ROW = row({
  id: "run-5f6a7b8c9d", definition: "election", definitionTitle: "Election", family: "governance", label: "Election 2099", group: "board",
  current: { id: "el.inspector", title: "Appoint the inspector", n: 4, of: 14, kind: "decision", state: "needs a person", role: "secretary" },
  owner: "secretary", waitingOn: { kind: "board", word: "the board; the secretary records", role: "secretary", detail: "" },
  due: due("2099-10-02", "law", -7, { cite: "EX 321.2" }), pastLaw: true,
});
export const ALARM_ROW = row({
  id: "run-6a7b8c9d0e", definition: "life-safety-period", definitionTitle: "Annual inspection", family: "life-safety",
  label: "Annual inspection: fire alarm", group: "others",
  current: { id: "ls.child", title: "A deficiency run is open", n: 5, of: 8, kind: "wait", state: "waiting", role: "manager" },
  waitingOn: { kind: "run", word: "a child run", role: "manager", detail: "child run open" },
  due: due("2099-11-30", "documents", 52),
});

export const ROWS: WorkRow[] = [OWNER_INFO_ROW, BILL_ROW, HEARING_ROW, BACKFLOW_ROW, RULE_ROW, ELECTION_ROW, ALARM_ROW];

const TITLES = { yours: "Yours", others: "Waiting on others", clock: "Waiting on a clock", board: "The board" } as const;
const ORDER = ["yours", "others", "clock", "board"] as const;

/** The list as the loader answers it: legal dates first within a group, then the nearest date, then a run with none. */
export function workPage(runs: WorkRow[] = ROWS, over: Partial<WorkPage> = {}): WorkPage {
  const rank = (r: WorkRow) => (r.due?.legal ? 0 : r.due ? 1 : 2);
  const sorted = [...runs].sort((a, b) =>
    ORDER.indexOf(a.group as (typeof ORDER)[number]) - ORDER.indexOf(b.group as (typeof ORDER)[number]) || rank(a) - rank(b)
    || (a.due?.date ?? "").localeCompare(b.due?.date ?? "") || a.id.localeCompare(b.id));
  const n = (g: string) => runs.filter((r) => r.group === g).length;
  return {
    found: true, asOf: AS_OF, state: "open",
    counts: {
      open: runs.length, dueThisWeek: runs.filter((r) => r.due && r.due.days !== null && r.due.days >= 0 && r.due.days <= 7).length,
      overdue: runs.filter((r) => r.due && r.due.days !== null && r.due.days < 0).length, pastLegal: runs.filter((r) => r.pastLaw).length,
      yours: n("yours"), others: n("others"), clock: n("clock"), board: n("board"),
    },
    shown: runs.length, runs: sorted,
    groups: ORDER.map((key) => ({ key, title: TITLES[key], count: n(key) })),
    definitions: [
      { key: "owner-info-cycle", title: "Owner information cycle", family: "members" },
      { key: "bill-attach", title: "Bill attachment", family: "money" },
      { key: "hearing", title: "Hearing", family: "members" },
    ],
    roles: ["manager", "president", "vice president", "secretary", "treasurer", "director", "administrator", "jason", "scheduler", "anyone"],
    viewer: { roles: ["manager", "treasurer"] },
    empty: runs.length ? "" : "No runs are open. Start one from Start a run.",
    caveats: [
      "Read from the stores on disk. jason decides nothing: a date is the law's, the documents', a counterparty's, jason's proposal, or a person's, and says which.",
    ],
    problems: [],
    notComposed: [{ what: "Executive-session runs (CIV 4935(e))", why: "No definition marks a step executive, so every run shows in full at this level." }],
    ...over,
  };
}

/** A group of `n` runs for the fold test. */
export const manyYours = (n: number): WorkRow[] =>
  Array.from({ length: n }, (_, i) => row({
    id: `run-many${String(i).padStart(5, "0")}`, definition: "owner-info-cycle", definitionTitle: "Owner information cycle",
    label: `Sample cycle ${i + 1}`, group: "yours", mine: true, due: due(`2099-11-${String(10 + i).padStart(2, "0")}`, "documents", 31 + i),
  }));

export const PAGE = workPage();
export const EMPTY_PAGE = workPage([], { counts: { open: 0, dueThisWeek: 0, overdue: 0, pastLegal: 0, yours: 0, others: 0, clock: 0, board: 0 } });

// -- one run ----------------------------------------------------------------------------------------------------------------

const LAW: LawWords = {
  citation: "EX 123.4", section: "EX 123.4(a)",
  words: "The association shall send a second notice to each member not later than 30 days before the answer-by date. (Sample text, not a statute.)",
  digest: "d0c5a1", source: "authorities shelf: sample", note: "version in force on 2099-10-09", caveats: [],
  versions: [], undecided: false, missing: "", readingLabel: "jason's reading, not the provision",
  restatement: "jason's consolidated text is not an official restatement.", reading: "Resend the notice at least 30 days before answers are due",
};

export function step(over: Partial<RunStep> & Pick<RunStep, "id" | "n" | "title" | "kind">): RunStep {
  return {
    of: 12, role: "manager", state: "not started", reason: "", phase: "collect", phaseTitle: "Collect", group: "", why: "", command: "",
    sop: "", legal: false, needsRecord: "", record: "", by: "", at: "", current: false, blockedBy: [], items: [], choice: "", choices: [],
    spawns: null, skip: null, clock: null, evidence: [], links: [], changed: [], waitingOn: null, yours: false, acts: [], notOffered: {}, ...over,
  };
}

const MANAGER_WAIT: WaitingOn = { kind: "office", word: "the manager", role: "manager", detail: "" };

export const STEPS: RunStep[] = [
  step({ id: "oi.check-data", n: 1, title: "Check the data", kind: "check", state: "done", role: "jason", phase: "prepare", phaseTitle: "Prepare",
    by: "jason", at: "2099-10-01T09:00:00Z", reason: "passed", why: "The owner list is read before anything is sent.",
    evidence: [{ address: "file:owners/roster.json", kept: "aa11bb22cc33dd44", now: "aa11bb22cc33dd44", changed: false, present: true }] }),
  step({ id: "oi.board-decides", n: 2, title: "The board adopts the cycle", kind: "decision", state: "done", role: "secretary", phase: "prepare",
    phaseTitle: "Prepare", by: "B. Secretary", at: "2099-10-02T10:00:00Z",
    decision: { recorded: true, motion: "Adopt the 2099 owner information cycle", outcome: "adopted", record: "decision:d-2099-10-02", by: "B. Secretary",
      at: "2099-10-02T10:00:00Z", final: true, screen: "decisions" },
    notOffered: { attest: "A decision is recorded in Decisions by the secretary; this screen does not record it, and the step reads done once the decision is on record." } }),
  step({ id: "oi.send-plan", n: 3, title: "Plan the owner-information send", kind: "plan", state: "done", role: "manager", phase: "send", phaseTitle: "Send",
    by: "jason", at: "2099-10-03T11:00:00Z", reason: "approval applied",
    plan: { approval: "ap-2099-0031", status: "applied", kind: "owner-info-send", screen: "approvals" },
    links: [{ kind: "approval", id: "ap-2099-0031", step: "oi.send-plan", label: "Approval 31", state: "applied", read: true, screen: "approvals" }],
    evidence: [{ address: "file:forms/campaigns.json", kept: "1a2b3c4d5e6f7a8b", now: "9f8e7d6c5b4a3c2d", changed: true, present: true }],
    changed: [{ address: "file:forms/campaigns.json", was: "1a2b3c4d5e6f7a8b", now: "9f8e7d6c5b4a3c2d" }],
    notOffered: { attest: "A plan is decided and applied in Approvals; the run reads the result." } }),
  step({ id: "oi.delivery", n: 4, title: "Notice delivery", kind: "wait", state: "done", role: "manager", phase: "send", phaseTitle: "Send",
    spawns: "notice-delivery", by: "jason", at: "2099-10-04T09:00:00Z",
    links: [{ kind: "run", id: "run-7b8c9d0e1f", step: "oi.delivery", label: "Notice delivery", state: "done", read: true, screen: "work" }] }),
  step({ id: "oi.mailroom", n: 5, title: "Mailroom batch 1", kind: "wait", state: "waiting", role: "manager", phase: "send", phaseTitle: "Send",
    spawns: "mailroom-batch", reason: "a child run is open", waitingOn: { kind: "run", word: "a child run", role: "manager", detail: "a child run is open" },
    links: [{ kind: "run", id: "run-8c9d0e1f2a", step: "oi.mailroom", label: "Mailroom batch 1", state: "waiting", read: true, screen: "work" }] }),
  step({ id: "oi.read-forms", n: 6, title: "Read the returned forms", kind: "person", state: "needs a person", role: "manager", current: true, yours: true,
    why: "An owner's answer counts only once a person confirms the reading (jason's reading, not the owner's word).",
    command: "jason responses --list --state new", needsRecord: "the count of forms read", legal: true, sop: "owner-info-cycle step 9",
    clock: { slot: "answer_by", days: null, label: "Answers by", cite: "", ...BASIS.documents } as RunStep["clock"],
    evidence: [
      { address: "file:forms/campaigns.json", kept: null, now: "9f8e7d6c5b4a3c2d", changed: false, present: true },
      { address: "drive:1AbCdEfGhIjKlMnOpQrStUv", kept: null, now: "77aa88bb99cc00dd", changed: false, present: true },
    ],
    acts: ["attest"], notOffered: { skip: "Skip is not offered: this step is required by the law." },
    waitingOn: MANAGER_WAIT }),
  step({ id: "oi.apply-tags", n: 7, title: "Apply the tags", kind: "job", state: "ready", role: "manager", phase: "collect", group: "response",
    command: "jason owner-info --apply --payhoa --yes", job: { job: null, state: "", name: "owner-info-apply" } as RunStep["job"],
    waitingOn: { kind: "system", word: "jason", role: "manager", detail: "the next time the run is opened" } }),
  step({ id: "oi.record-answers", n: 8, title: "Record what the answers say", kind: "person", state: "not started", role: "manager", group: "response",
    needsRecord: "the response record", skip: { roles: ["manager"], reasonRequired: true }, notOffered: { attest: "This step is not started, not waiting on a person." } }),
  step({ id: "oi.answers-by", n: 9, title: "Answers by", kind: "wait", state: "waiting", role: "manager", phase: "collect",
    waitingOn: { kind: "clock", word: "a clock", role: "manager", detail: "Answers by" }, yours: false,
    clock: { slot: "answer_by", days: null, label: "Answers by", cite: "", ...BASIS.documents } as RunStep["clock"], acts: ["arrived"] }),
  step({ id: "oi.resend", n: 10, title: "Resend to owners who have not answered", kind: "person", state: "not started", role: "manager", phase: "collect",
    legal: true, clock: { slot: "resend", days: -30, label: "Resend by", cite: "EX 123.4", ...BASIS.law } as RunStep["clock"],
    notOffered: { attest: "This step is not started, not waiting on a person.", skip: "Skip is not offered: this step is required by the law." } }),
  step({ id: "oi.choose", n: 11, title: "Is the cycle complete?", kind: "branch", state: "not started", role: "manager", phase: "close", phaseTitle: "Close",
    choices: ["complete", "extend"] }),
  step({ id: "oi.close", n: 12, title: "Close the cycle", kind: "person", state: "not started", role: "secretary", phase: "close", phaseTitle: "Close",
    skip: { roles: ["secretary"], reasonRequired: true },
    notOffered: { attest: "Waiting on the secretary.", skip: "Only the secretary may skip this step." }, waitingOn: { kind: "office", word: "the secretary", role: "secretary", detail: "" } }),
];

const CLOCKS: RunClock[] = [
  { key: "oi.read-forms", step: "oi.read-forms", label: "Answers by", due: "2099-10-23", status: "upcoming", days: 14, cite: "", past: false,
    stepTitle: "Read the returned forms", scope: "step", ...BASIS.documents },
  { key: "run.0", step: "", label: "In PayHOA by", due: "2099-11-01", status: "upcoming", days: 23, cite: "", past: false, stepTitle: "", scope: "run", ...BASIS.documents },
  { key: "oi.resend", step: "oi.resend", label: "Resend by", due: "2099-10-30", status: "upcoming", days: 21, cite: "EX 123.4", past: false,
    stepTitle: "Resend to owners who have not answered", scope: "step", law: LAW, ...BASIS.law },
];

const EVENTS: HistoryEvent[] = [
  { n: 9, kind: "changed", step: "oi.send-plan", stepTitle: "Plan the owner-information send", by: "jason", at: "2099-10-08T08:12:00Z",
    text: "jason found that what step 3, Plan the owner-information send was done on has changed", detail: {}, pending: false },
  { n: 8, kind: "attested", step: "oi.delivery", stepTitle: "Notice delivery", by: MANAGER, at: "2099-10-04T09:30:00Z",
    text: `${MANAGER} attested step 4, Notice delivery (sent-notice ref 12)`, detail: { record: "sent-notice ref 12" }, pending: false },
  { n: 7, kind: "applied", step: "oi.send-plan", stepTitle: "Plan the owner-information send", by: "jason", at: "2099-10-03T11:00:00Z",
    text: "jason read the approval for step 3, Plan the owner-information send as applied", detail: {}, pending: false },
  { n: 2, kind: "decided", step: "oi.board-decides", stepTitle: "The board adopts the cycle", by: "B. Secretary", at: "2099-10-02T10:00:00Z",
    text: "B. Secretary recorded the decision on step 2, The board adopts the cycle: adopted (decision:d-2099-10-02)", detail: {}, pending: false },
  { n: 1, kind: "opened", step: "", stepTitle: "", by: MANAGER, at: "2099-10-01T09:00:00Z", text: `${MANAGER} opened the run`, detail: {}, pending: false },
];

const LINKS: RunLink[] = STEPS.flatMap((s) => s.links);

export const OWNER_INFO_RUN: Run = {
  id: "run-0a1b2c3d4e", definition: "owner-info-cycle", definitionTitle: "Owner information cycle", family: "members", label: "Owner information 2099",
  subject: "campaign:OI-2099", subjectKind: "campaign", state: "active", n: 9, updated: "2099-10-08T08:12:00Z", opened: "2099-10-01T09:00:00Z",
  openedBy: MANAGER, dates: { answer_by: "2099-10-23" }, itemCount: 0, parent: null, children: ["run-7b8c9d0e1f", "run-8c9d0e1f2a"], pausedReason: "",
  cancelledReason: "", torn: false, corrupt: null, orphans: [], pastLaw: [], age: age(8),
  current: { id: "oi.read-forms", title: "Read the returned forms", n: 6, of: 12 },
  acts: {
    open: { offered: false, why: "The run is active, not a draft.", needsYes: true },
    pause: { offered: true, why: "" },
    resume: { offered: false, why: "The run is active, not paused." },
    note: { offered: true, why: "" },
    cancel: { offered: true, why: "", needsYes: true, legal: true },
  },
  cancelWill: { openSteps: ["oi.read-forms", "oi.mailroom", "oi.answers-by"], childRuns: ["run-7b8c9d0e1f", "run-8c9d0e1f2a"] },
};

export function runPage(over: Partial<RunPage> = {}): RunPage {
  return {
    found: true, asOf: AS_OF,
    caveats: ["The run page shows the run as opening it now would find it (a dry resume, written nowhere); the list shows each run as of its last write."],
    run: OWNER_INFO_RUN,
    phases: [
      { key: "prepare", title: "Prepare", steps: ["oi.check-data", "oi.board-decides"] },
      { key: "send", title: "Send", steps: ["oi.send-plan", "oi.delivery", "oi.mailroom"] },
      { key: "collect", title: "Collect", steps: ["oi.read-forms", "oi.apply-tags", "oi.record-answers", "oi.answers-by", "oi.resend"] },
      { key: "close", title: "Close", steps: ["oi.choose", "oi.close"] },
    ],
    steps: STEPS, clocks: CLOCKS, links: LINKS, history: EVENTS,
    changed: [{ step: "oi.send-plan", stepTitle: "Plan the owner-information send", n: 3, address: "file:forms/campaigns.json",
      was: "1a2b3c4d5e6f7a8b", now: "9f8e7d6c5b4a3c2d", at: "2099-10-08T08:12:00Z", pending: false }],
    pending: [], viewer: { roles: ["manager", "treasurer"] }, problems: [],
    notComposed: [{ what: "The decision's mover, second, and vote", why: "The run keeps the secretary's record reference and outcome; the votes are read on Decisions." }],
    ...over,
  };
}

export const RUN_PAGE = runPage();

/** The same run with no change under a done step. */
export const QUIET_RUN_PAGE = runPage({
  changed: [], steps: STEPS.map((s) => ({ ...s, changed: [] })),
});

/** A run past a legal date (the election). */
export const ELECTION_PAGE: RunPage = runPage({
  run: { ...OWNER_INFO_RUN, id: "run-5f6a7b8c9d", definition: "election", definitionTitle: "Election", label: "Election 2099", pastLaw: ["el.inspector"],
    children: [], current: { id: "el.inspector", title: "Appoint the inspector", n: 4, of: 14 }, cancelWill: { openSteps: ["el.inspector"], childRuns: [] } },
  phases: [{ key: "pre", title: "Before the election", steps: ["el.inspector"] }],
  steps: [step({ id: "el.inspector", n: 1, of: 1, title: "Appoint the inspector", kind: "decision", role: "secretary", state: "needs a person", phase: "pre",
    phaseTitle: "Before the election", current: true, legal: true,
    clock: { slot: "inspector", days: -30, label: "Inspector appointed by", cite: "EX 321.2", ...BASIS.law } as RunStep["clock"],
    decision: { recorded: false, motion: "Appoint the inspector", outcome: "", record: "", by: "", at: "", final: false, screen: "decisions" },
    waitingOn: { kind: "board", word: "the board; the secretary records", role: "secretary", detail: "" },
    notOffered: { attest: "A decision is recorded in Decisions by the secretary; this screen does not record it, and the step reads done once the decision is on record.", skip: "Skip is not offered: this step is required by the law." } })],
  clocks: [{ key: "el.inspector", step: "el.inspector", label: "Inspector appointed by", due: "2099-10-02", status: "overdue", days: -7, cite: "EX 321.2",
    past: true, stepTitle: "Appoint the inspector", scope: "step", ...BASIS.law,
    law: { ...LAW, citation: "EX 321.2", section: "EX 321.2", words: "The board shall appoint an inspector of elections before ballots are sent. (Sample text, not a statute.)", reading: "Appoint the inspector before ballots go out" } }],
  links: [], history: [EVENTS[EVENTS.length - 1]], changed: [], pending: [],
});

/** A bill's plan step that is the treasurer's, read by a viewer who is not the treasurer. */
export const BILL_PAGE: RunPage = runPage({
  run: { ...OWNER_INFO_RUN, id: "run-1b2c3d4e5f", definition: "bill-attach", definitionTitle: "Bill attachment", label: "Bill attach: Example Electric, Oct",
    children: [], cancelWill: { openSteps: ["ba.plan"], childRuns: [] }, current: { id: "ba.plan", title: "Approve the attachments", n: 1, of: 2 },
    acts: { ...OWNER_INFO_RUN.acts, cancel: { offered: true, why: "", needsYes: false, legal: false } } },
  phases: [{ key: "attach", title: "Attach", steps: ["ba.plan", "ba.review"] }],
  steps: [
    step({ id: "ba.plan", n: 1, of: 2, title: "Approve the attachments", kind: "plan", role: "treasurer", state: "waiting", phase: "attach", phaseTitle: "Attach",
      current: true, plan: { approval: "ap-2099-0040", status: "in review", kind: "bill-attach", screen: "approvals" },
      links: [{ kind: "approval", id: "ap-2099-0040", step: "ba.plan", label: "Approval 40", state: "in review", read: true, screen: "approvals" }],
      waitingOn: { kind: "approval", word: "the approvals engine", role: "treasurer", detail: "in review" },
      notOffered: { attest: "A plan is decided and applied in Approvals; the run reads the result." } }),
    step({ id: "ba.review", n: 2, of: 2, title: "The treasurer reviews the bill", kind: "person", role: "treasurer", state: "needs a person", phase: "attach",
      phaseTitle: "Attach", skip: { roles: ["treasurer"], reasonRequired: true },
      waitingOn: { kind: "office", word: "the treasurer", role: "treasurer", detail: "" },
      notOffered: { attest: "Waiting on the treasurer.", skip: "Only the treasurer may skip this step." } }),
  ],
  clocks: [], links: [], history: [EVENTS[EVENTS.length - 1]], changed: [], pending: [],
});

/** The same run read by an administrator viewing as someone else: no act, the server's sentence in its place. */
export const ACTING = "Viewing as A. Secretary (admin view): go back to yourself first. A step is recorded in a person's own name.";
export const ACTING_PAGE: RunPage = runPage({
  run: { ...OWNER_INFO_RUN, acts: {
    open: { offered: false, why: ACTING }, pause: { offered: false, why: ACTING }, resume: { offered: false, why: ACTING },
    note: { offered: false, why: ACTING }, cancel: { offered: false, why: ACTING, needsYes: true, legal: true } } },
  steps: STEPS.map((s) => ({ ...s, acts: [], notOffered: Object.fromEntries(["attest", "arrived", "skip", "reopen"].map((a) => [a, ACTING])) })),
});

/** A paused run, and a run with pending events a read found. */
export const PAUSED_PAGE: RunPage = runPage({
  run: { ...OWNER_INFO_RUN, state: "paused", pausedReason: "waiting for the board's reply on the list",
    acts: { ...OWNER_INFO_RUN.acts, pause: { offered: false, why: "The run is paused; only a running run is paused." }, resume: { offered: true, why: "" } } },
});
export const PENDING_PAGE: RunPage = runPage({
  pending: [{ kind: "check-ran", step: "oi.check-data", stepTitle: "Check the data" }],
  history: [{ n: 10, kind: "check-ran", step: "oi.check-data", stepTitle: "Check the data", by: "jason", at: "2099-10-09T08:00:00Z",
    text: "jason read step 1, Check the data: passed", detail: {}, pending: true }, ...EVENTS],
});

/** A history line the server masked, and one it did not (the page masks a second time). */
export const CONTACT_EVENT: HistoryEvent = {
  n: 11, kind: "note", step: "", stepTitle: "", by: MANAGER, at: "2099-10-09T09:00:00Z",
  text: `${MANAGER} noted on the run: call jane@example.com or 555-123-4567 about the form`, detail: { text: "call jane@example.com" }, pending: false,
};

/** What a write answers. */
export const ACT_ANSWER: ActAnswer = {
  ok: true, act: "attest", by: MANAGER,
  event: { n: 10, kind: "attested", step: "oi.read-forms", stepTitle: "Read the returned forms", by: MANAGER, at: "2099-10-09T10:00:00Z",
    text: `${MANAGER} attested step 6, Read the returned forms (4 forms read)`, detail: { record: "4 forms read" }, pending: false },
  appended: [], run: RUN_PAGE,
};

// -- the definitions --------------------------------------------------------------------------------------------------------

export function definitionRow(over: Partial<DefinitionRow> & Pick<DefinitionRow, "key" | "title" | "family">): DefinitionRow {
  return {
    subjectKind: "campaign", steps: 12, phases: [{ key: "a", title: "Prepare", steps: 4 }], dates: [], legalClock: false, procedure: "",
    procedureSteps: null, drift: { ok: true, why: [] }, cadence: "", startable: true, startedBy: [], needsYes: false,
    roles: ["manager"], mySteps: true, lessons: [], ...over,
  };
}

export const OWNER_INFO_DEF = definitionRow({
  key: "owner-info-cycle", title: "Owner information cycle", family: "members", steps: 25, procedure: "owner-info-cycle", procedureSteps: 25,
  legalClock: true, needsYes: true, cadence: "yearly",
  dates: [
    { name: "answer_by", label: "Answers by", required: true, after: "send", rule: "may not come before send" },
    { name: "send", label: "Send on", required: true, after: "" },
  ],
});
export const RESPOND_DEF = definitionRow({
  key: "respond", title: "Respond to a request", family: "members", steps: 14, procedure: "respond", procedureSteps: 15,
  drift: { ok: false, why: ["respond.11: the procedure no longer has step 11"] },
  lessons: [{ key: "reply-late", status: "fixed" }],
});
export const BILL_DEF = definitionRow({ key: "bill-attach", title: "Bill attachment", family: "money", steps: 7, procedure: "bill-attach", procedureSteps: 7 });
export const HEARING_DEF = definitionRow({
  key: "hearing", title: "Hearing", family: "members", steps: 9, startable: false, startedBy: ["manager", "secretary"], mySteps: false,
});

export function definitionsPage(defs: DefinitionRow[] = [OWNER_INFO_DEF, RESPOND_DEF, HEARING_DEF, BILL_DEF], over: Partial<DefinitionsPage> = {}): DefinitionsPage {
  const families = [...new Set(defs.map((d) => d.family))].sort();
  return {
    found: true, asOf: AS_OF,
    counts: { definitions: defs.length, shown: defs.length, families: families.length, drifted: defs.filter((d) => !d.drift.ok).length },
    families: families.map((family) => ({ family, definitions: defs.filter((d) => d.family === family) })),
    definitions: defs, empty: defs.length ? "" : "No workflows are registered.", viewer: { roles: ["manager"] },
    roles: ["manager", "secretary", "treasurer"], caveats: ["Read from the stores on disk."], problems: [],
    notComposed: [{ what: "How often a workflow runs", why: "A definition holds no cadence, so 'cadence' is empty." }], ...over,
  };
}

export const DEFINITIONS_PAGE = definitionsPage();

export const DEFINITION_PAGE: DefinitionsPage = definitionsPage(undefined, {
  definition: {
    ...OWNER_INFO_DEF,
    clocks: [{ slot: "resend", days: -30, label: "Resend by", cite: "EX 123.4", ...BASIS.law, law: LAW }],
    steps: [
      { id: "oi.read-forms", n: 1, title: "Read the returned forms", kind: "person", role: "manager", needs: ["oi.apply-tags"],
        why: "An owner's answer counts only once a person confirms the reading.", command: "jason responses --list --state new", plan: "", job: "",
        evidence: ["file:forms/campaigns.json"], record: "the count of forms read", legal: true, repeat: "once", spawns: null, sop: "owner-info-cycle step 9",
        skip: null, clock: { slot: "answer_by", days: null, label: "Answers by", cite: "", ...BASIS.documents }, phase: "collect", group: "" },
      { id: "oi.resend", n: 2, title: "Resend to owners who have not answered", kind: "person", role: "manager", needs: [], why: "", command: "", plan: "", job: "",
        evidence: [], record: "", legal: true, repeat: "once", spawns: null, sop: "", skip: null,
        clock: { slot: "resend", days: -30, label: "Resend by", cite: "EX 123.4", ...BASIS.law, law: LAW }, phase: "collect", group: "" },
    ],
  } as DefinitionPageData,
});

// -- starting a run ---------------------------------------------------------------------------------------------------------

export const START_OK: StartDry = { ok: true, dryRun: true, definition: "owner-info-cycle", problems: [] };
export const START_BAD: StartDry = {
  ok: false, dryRun: true, definition: "owner-info-cycle",
  problems: ["answer_by may not come before send: leave room for one correction before the answer-by date"],
};
export const START_DONE: StartAnswer = { ok: true, act: "start", by: MANAGER, id: "run-9d0e1f2a3b", definition: "owner-info-cycle", run: RUN_PAGE };

// -- a held run, outside the private view ------------------------------------------------------------------------------------

/** A run of a held definition seen outside the private view (`_held_row`): the definition's general words, the state, the
 * date and its basis word, and an opaque handle. No label, subject, step title, or citation. */
export const HELD_ROW = row({
  id: "run-9e8d7c6b5a", handle: "run-9e8d7c6b5a", definition: "hearing", definitionTitle: "A member's hearing", label: "A member's hearing",
  family: "board", subjectKind: "", group: "others", held: true, visibility: "held",
  current: { id: "", title: "a step", n: 0, of: 0, kind: "", state: "waiting", role: "secretary" },
  owner: "secretary", waitingOn: { kind: "arrival", word: "an arrival", role: "secretary", detail: "" },
  due: due("2099-11-02", "law", 24), age: { days: 8, opened: null, idleDays: 1, updated: "" },
});

/** The reduced page `held_page` answers: the run's shape with nothing in it. */
export const HELD_PAGE: RunPage = runPage({
  held: true, heldTitle: "A member's hearing", heldWhy: "Open the private view to see this run.",
  run: {
    ...OWNER_INFO_RUN, id: "run-9e8d7c6b5a", handle: "run-9e8d7c6b5a", definition: "hearing", definitionTitle: "A member's hearing",
    family: "board", label: "A member's hearing", subject: "", subjectKind: "", opened: "", openedBy: "", dates: {}, children: [], updated: "",
    current: { id: "", title: "a step", n: 0, of: 0 }, due: due("2099-11-02", "law", 24), age: { days: 8, opened: null, idleDays: 1, updated: "" },
    acts: {
      open: { offered: false, why: "Open the private view to see this run." }, pause: { offered: false, why: "Open the private view to see this run." },
      resume: { offered: false, why: "Open the private view to see this run." }, note: { offered: false, why: "Open the private view to see this run." },
      cancel: { offered: false, why: "Open the private view to see this run.", legal: false },
    },
    cancelWill: { openSteps: [], childRuns: [] },
  },
  phases: [], steps: [], clocks: [], links: [], history: [], changed: [], pending: [], notComposed: [], problems: [],
});

export const HELD_DEF = definitionRow({
  key: "hearing", title: "A hearing", family: "board", steps: 16, held: true, heldTitle: "A member's hearing", visibility: "held", startable: false,
  startableWhy: "A run of this kind concerns a member's discipline, an account, or a restricted record, so it starts only in the private view.",
});
