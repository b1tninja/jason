import type { ReactNode } from "react";
import { RunStepPanel } from "jason-ui";

// Made-up run of the "Owner information cycle" for "Oakview", with 2099 dates; the people are A. Manager and A. Owner. Types are not
// exported from jason-ui, so rows are inline objects. Nothing here posts: the acts are no-ops, and SupplyItems posts only when a
// person presses "Check the list". Statute text is plainly fake.
const BASIS = {
  law: { basis: "law", basisLabel: "LEGAL", legal: true, proposed: false },
  documents: { basis: "documents", basisLabel: "DOCUMENTS", legal: false, proposed: false },
};
const step = (over: any): any => ({
  id: "ex.1", n: 1, of: 12, title: "A step", kind: "person", role: "manager", state: "not started", reason: "", phase: "collect", phaseTitle: "Collect",
  group: "", why: "", command: "", sop: "", legal: false, needsRecord: "", record: "", by: "", at: "", current: false, blockedBy: [], items: [],
  choice: "", choices: [], spawns: null, skip: null, clock: null, evidence: [], links: [], changed: [], waitingOn: null, yours: false,
  acts: [], notOffered: {}, ...over,
});

const RUN: any = {
  id: "run-0a1b2c3d4e", definition: "owner-info-cycle", definitionTitle: "Owner information cycle", family: "members", label: "Owner information 2099",
  subject: "campaign:OI-2099", subjectKind: "campaign", state: "active", n: 9, updated: "2099-10-08T08:12:00Z", opened: "2099-10-01T09:00:00Z",
  openedBy: "A. Manager", dates: { answer_by: "2099-10-23" }, itemCount: 0, parent: null, children: [], pausedReason: "", cancelledReason: "",
  torn: false, corrupt: null, orphans: [], pastLaw: [], age: { days: 8, opened: "2099-10-01", idleDays: 1, updated: "2099-10-08T08:12:00Z" },
  current: { id: "oi.read-forms", title: "Read the returned forms", n: 6, of: 12 },
  acts: {
    open: { offered: false, why: "The run is active, not a draft.", needsYes: true }, pause: { offered: true, why: "" },
    resume: { offered: false, why: "The run is active, not paused." }, note: { offered: true, why: "" },
    cancel: { offered: true, why: "", needsYes: true, legal: true },
  },
  cancelWill: { openSteps: [], childRuns: [] },
};
const VIEWER = { known: true, name: "A. Manager", actingAs: "" };
const acts: any = { busy: false, said: null, send: async () => true, clear: () => {} };
const noLink = () => null;

const NUDGE = {
  band: "soon", word: "due soon", due: "2099-10-23", days: 14, basis: "documents", basisLabel: "DOCUMENTS", legal: false, proposed: true, label: "Answers by",
  cite: "", openDays: null, escalatedTo: null, escalatedWhy: "", snoozable: true, items: null,
  numbers: { leadDays: 14, afterHours: 168, escalateAfterHours: 72, adopted: false, note: "proposed, not the law's" }, claim: null,
};
const ENABLE = {
  state: "ready", word: "Yours: you hold the manager office. Nothing is missing.", holders: [{ office: "manager", names: ["A. Manager"], vacant: false }],
  missing: [], secondPerson: false, terminalOnly: false, youHold: ["manager"], owner: "A. Manager", inHand: [], accessNote: "",
};
const GUIDE = {
  authored: ["instruction", "rule", "checklist", "look-at"],
  instruction: "Read each form that has arrived and confirm the reading when it is right.",
  why: "An answer counts only once a person confirms the reading.",
  lookAt: [
    { label: "Forms that arrived", kind: "read", read: "responses-new", count: 4, rows: ["form:1042", "form:1043"], refs: [], asOf: "2099-10-20", unavailable: "",
      screen: { key: "responses", name: "Responses", href: "#/responses" } },
    { label: "Forms read and not confirmed", kind: "read", read: "responses-unconfirmed", count: null, rows: [], refs: [], asOf: "2099-10-20", unavailable: "the inbox is not readable" },
  ],
  rule: [{
    key: "EX 123.4(a)", kind: "statute", words: "The association shall send a second notice to each member not later than 30 days before the answer-by date. (Sample text, not a statute.)",
    version: "the words in force on 2099-10-20", source: "Example Legislature", reading: "Resend the notice at least 30 days before answers are due.",
    readingLabel: "jason's reading", missing: "", caveats: [], restatement: "jason's consolidated text is not an official restatement.", command: "", versions: [],
  }],
  checklist: [
    { text: "Each reading matches the form", required: true }, { text: "A form for the wrong unit is set aside", required: false },
    { text: "Nothing is marked an answer until you confirm", required: true },
  ],
  requiredChecks: 2,
  commands: [
    { text: "jason responses --list --new", raw: "jason responses --list --new", note: "", terminalOnly: false, fillIn: [] },
    { text: 'jason responses --read ID --by "A. Manager"', raw: "jason responses --read ID --by NAME", note: "", terminalOnly: false, fillIn: ["ID"] },
  ],
  doneWhen: "The count of forms read and not confirmed is 0.", record: "the arrivals read (a count)",
  blocked: "Add a note naming the form id and what is wrong with it.", notApplicable: "This step is required: it has no not-applicable outcome.",
  naOffered: false, skippable: false, ask: [{ office: "manager", names: ["A. Manager"], vacant: false }, { office: "president", names: [], vacant: true }],
  lessons: [{ key: "sample-lesson", status: "fixed" }],
  sop: { address: "owner-info-cycle#14", key: "owner-info-cycle", index: 14, command: "jason sop owner-info-cycle" },
  inHand: ["the response inbox open"], accessNote: "", integrations: [], secondPerson: false, terminalOnly: false,
};
const EVIDENCE = [
  { address: "file:forms/campaigns.json", kept: null, now: "9f8e7d6c5b4a3c2d", changed: false, present: true },
  { address: "drive:1AbCdEfGhIjKlMnOpQrStUv", kept: null, now: "77aa88bb99cc00dd", changed: false, present: true },
];

// The cell frame is the card's viewport (1000x1400) and the guided panel with every section is taller, so the canonical story keeps
// the do-this, look-at, checklist, done-when and ask sections and the reference cell carries the rule and the commands.
const GUIDE_SHORT = { ...GUIDE, rule: [], commands: [], inHand: [], lookAt: [GUIDE.lookAt[0]] };
const GUIDED = step({
  id: "oi.read-forms", n: 6, title: "Read the returned forms", kind: "person", state: "needs a person", current: true, yours: true, acts: ["attest"],
  needsRecord: "the arrivals read", evidence: [EVIDENCE[0]], enable: ENABLE, nudge: NUDGE, guide: GUIDE_SHORT, clock: { slot: "answer_by", days: 14, label: "Answers by", cite: "", ...BASIS.documents },
  skip: null, legal: true, notOffered: { skip: "Skip is not offered: this step is required by the law." },
});

const Column = ({ children }: { children: ReactNode }) => <div style={{ maxWidth: 820 }}>{children}</div>;

/** The canonical story: a guided person step that is the viewer's move. Enable strip and nudge line over the guide (do this, look at, the rule, a checklist, the command, done when), then Mark done and the notes. */
export const GuidedYourMove = () => (
  <Column><RunStepPanel step={GUIDED} run={RUN} viewer={VIEWER} acts={acts} childHref={noLink} /></Column>
);

/** The reference half of a guide on a step that is not the viewer's: the rule recited with its reading labeled, and the commands to run at a terminal. No act is offered. */
export const GuidedRuleAndCommands = () => (
  <Column>
    <RunStepPanel run={RUN} viewer={VIEWER} acts={acts} childHref={noLink} step={step({
      id: "oi.read-forms", n: 6, title: "Read the returned forms", kind: "person", state: "needs a person", current: true, yours: false,
      enable: { ...ENABLE, state: "not yours", word: "Waiting on the secretary: you do not hold the secretary office.", youHold: [], holders: [{ office: "secretary", names: ["A. Secretary"], vacant: false }] },
      nudge: NUDGE, guide: { ...GUIDE, lookAt: [GUIDE.lookAt[1]], checklist: [], inHand: [], lessons: [], doneWhen: "", commands: [GUIDE.commands[0]] },
      waitingOn: { kind: "office", word: "the secretary", role: "secretary", detail: "" },
      notOffered: { attest: "Waiting on the secretary.", skip: "Only the secretary may skip this step." },
    })} />
  </Column>
);

/** A step that is not the viewer's: it says whose move it is, offers no act, and gives the server's sentence for what it does not offer. */
export const WaitingOnAnother = () => (
  <Column>
    <RunStepPanel run={RUN} viewer={VIEWER} acts={acts} childHref={noLink} step={step({
      id: "oi.close", n: 11, title: "Close the cycle", kind: "person", role: "secretary", state: "needs a person",
      why: "The cycle closes once every returned form is read and the secretary records it.", sop: "owner-info-cycle step 20",
      waitingOn: { kind: "office", word: "the secretary", role: "secretary", detail: "" }, skip: { roles: ["secretary"], reasonRequired: true },
      notOffered: { attest: "Waiting on the secretary.", skip: "Only the secretary may skip this step." },
    })} />
  </Column>
);

/** A failed check with its remedy: the failed result stays recorded, and the remedy step is one click away. */
export const FailedWithRemedy = () => (
  <Column>
    <RunStepPanel run={RUN} viewer={VIEWER} acts={acts} childHref={noLink} onGo={() => {}}
      steps={[{ id: "oi.fix-data", n: 2, title: "Correct the owner list" }, { id: "oi.check-data", n: 1, title: "Check the data" }]}
      step={step({
        id: "oi.check-data", n: 1, title: "Check the data", kind: "check", role: "jason", state: "failed", reason: "2 owner records have no mailing address",
        why: "The owner list is read before anything is sent.", by: "jason", at: "2099-10-01T09:00:00Z", remedy: "oi.fix-data",
        evidence: [EVIDENCE[0]],
      })} />
  </Column>
);

/** A step that repeats over items: a roll-up, one row for each item with its state, its own clock and its lateness (a late item is a word and a glyph), and the supply form under it. */
export const ItemsWithClocks = () => (
  <Column>
    <RunStepPanel
      run={{ ...RUN, acts: { ...RUN.acts, supplyItems: { offered: true, why: "", sets: [{ name: "requests" }] } } }}
      viewer={VIEWER} acts={acts} childHref={noLink}
      clocks={[
        { key: "a", step: "oi.each", item: "req-1001", label: "Reply by", due: "2099-10-14", status: "upcoming", days: 5, cite: "", past: false, stepTitle: "Answer each request", scope: "step", ...BASIS.documents },
        { key: "b", step: "oi.each", item: "req-1002", label: "Reply by", due: "2099-10-05", status: "overdue", days: -4, cite: "EX 123.4", past: true, stepTitle: "Answer each request", scope: "step", ...BASIS.law },
      ]}
      step={step({
        id: "oi.each", n: 3, title: "Answer each request", kind: "person", state: "needs a person", current: true, yours: false, perItem: true, itemAware: true,
        itemSet: "requests", why: "Each request in the set is answered on its own clock.", waitingOn: { kind: "office", word: "the manager", role: "manager", detail: "" },
        items: [{ item: "req-1001", state: "needs a person" }, { item: "req-1002", state: "failed" }, { item: "req-1003", state: "done" }],
      })} />
  </Column>
);

/** A done step in the unguided layout: why and the procedure, what it looked at (a changed address is flagged), the command, and what the step made. */
export const DoneWithChange = () => (
  <Column>
    <RunStepPanel run={RUN} viewer={VIEWER} acts={acts} childHref={(l: any) => `#/work/notice-delivery/${l.id}`} step={step({
      id: "oi.send-plan", n: 3, title: "Plan the owner-information send", kind: "plan", role: "manager", state: "done", by: "jason", at: "2099-10-03T11:00:00Z",
      why: "The send is planned and approved before any notice goes out.", sop: "owner-info-cycle step 7", command: "jason owner-info --plan",
      plan: { approval: "ap-2099-0031", status: "applied", kind: "owner-info-send", screen: "approvals" },
      evidence: [{ address: "file:forms/campaigns.json", kept: "1a2b3c4d5e6f7a8b", now: "9f8e7d6c5b4a3c2d", changed: true, present: true }],
      changed: [{ address: "file:forms/campaigns.json", was: "1a2b3c4d5e6f7a8b", now: "9f8e7d6c5b4a3c2d" }],
      links: [
        { kind: "approval", id: "ap-2099-0031", step: "oi.send-plan", label: "Approval 31", state: "applied", read: true, screen: "approvals" },
        { kind: "run", id: "run-7b8c9d0e1f", step: "oi.send-plan", label: "Notice delivery", state: "done", read: true, screen: "work" },
      ],
    })} />
  </Column>
);

/** A step an adopted control gates: the engine's sentence for each gate, linking to the control, above the usual panel. */
export const RequiredByAControl = () => (
  <Column>
    <RunStepPanel run={RUN} viewer={VIEWER} acts={acts} childHref={noLink} step={step({
      id: "oi.pay", n: 7, title: "Approve the vendor payment", kind: "person", role: "treasurer", state: "needs a person", current: true, yours: true, acts: ["attest"],
      why: "A payment is approved by the treasurer before it is sent.",
      controls: [
        { key: "contracts", title: "Payment authorization", gate: "resolution", state: "in force", effective: "2099-01-01",
          why: "a control the board adopted on 2099-01-01 requires a board resolution on record before this step: cite the id of the decision recorded in Decisions in the record" },
        { key: "confirm", title: "Second-person confirmation", gate: "second", state: "in force", effective: "2099-01-01", firstBy: "A. Manager",
          why: "a control the board adopted on 2099-01-01 requires a second, different person to confirm this step" },
      ],
    })} />
  </Column>
);
