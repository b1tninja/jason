import type {
  ControlRowData, ControlsPage, ControlGroup, ControlCounts, ControlNotices, OneControl, ProposeAnswer, RosterCheckData,
} from "./controls";

// Made-up controls for "Oakview" (no real association), in the shapes `jason.controls.view` returns. Today is 2099-10-12.
// Offices only in a roster; a name appears only as an actor in a history line. Sample words are invented.

export const TODAY = "2099-10-12";
const READING = "jason's reading, not the provision";

const roster = (over: Partial<RosterCheckData> = {}): RosterCheckData => ({
  read: true, needs: [{ office: "treasurer", count: 1 }, { office: "director", count: 1 }],
  seated: [{ office: "director", count: 1 }, { office: "president", count: 1 }, { office: "secretary", count: 1 }, { office: "treasurer", count: 1 }],
  missing: [], lacks: "", ...over,
});

export const row = (over: Partial<ControlRowData> & Pick<ControlRowData, "key" | "title" | "family" | "state" | "standing" | "stateWord">): ControlRowData => ({
  type: over.key, familyTitle: over.family.charAt(0).toUpperCase() + over.family.slice(1), scope: { kind: "all", value: "" },
  parameters: {}, summary: "", boardSets: [],
  inForce: { ok: false, reason: `${over.state}, not adopted`, lacks: "" },
  basis: { citation: "Example Bylaws, 99.9", words: "All checks, drafts, and orders for the payment of money shall be signed by any two directors, or by an officer and a director, unless the Board specifies another manner.", floor: null },
  floor: { provision: null, catalog: null, read: false, note: "floor: read by a person (jason reads a floor only where one count is certain)" },
  reading: "", readingLabel: "", touches: [], proposedAs: null, proposedStatus: null, decision: null, effective: "", history: [],
  roster: roster(), missing: [], changed: null, ...over,
} as ControlRowData);

export const PAYMENT_SIGNERS = row({
  key: "payment-signers", title: "Payment signers", family: "money", state: "adopted", standing: "in-force",
  stateWord: "adopted, in force since 2099-09-20", effective: "2099-09-20",
  summary: "signers: 2; offices that may sign: treasurer, director; second signer above: $2,500.00",
  inForce: { ok: true, reason: "", lacks: "" },
  basis: { citation: "Example Bylaws, 99.9", words: "All checks, drafts, and orders for the payment of money shall be signed by any two directors, or by an officer and a director, unless the Board specifies another manner.", floor: { signers: 2 } },
  floor: { provision: { signers: 2 }, catalog: { signers: 2 }, read: true, note: "" },
  reading: "Name the manner the Bylaws allow: the treasurer and one other director above an amount the board sets.", readingLabel: READING,
  touches: [{ kind: "approval kind", key: "payhoa-attach-bills", title: "Payment plans", builtin: "one person", with: "two signers above $2,500.00", changes: true }],
  decision: { id: "2099-09-05-4", meeting: "2099-09-05 regular meeting", outcome: "approved", tally: { yes: 5, no: 0, abstain: 0 } },
  history: [
    { act: "suggest", by: "jason", at: "2099-09-01T09:00:00+00:00" },
    { act: "propose", by: "A. Secretary", at: "2099-09-02T09:00:00+00:00", why: "put before the board as board item control-payment-signers" },
    { act: "adopt", by: "A. Secretary", at: "2099-09-05T20:00:00+00:00", decision: "2099-09-05-4" },
  ],
});

export const RESERVE = row({
  key: "reserve-withdrawals", title: "Reserve withdrawals", family: "money", state: "suggested", standing: "suggested", stateWord: "suggested",
  summary: "the board sets: signers",
  basis: { citation: "Example Bylaws, 99.9(b)", words: "Withdrawals from the reserve account require the signatures of two board members.", floor: { signers: 2 } },
  floor: { provision: { signers: 2 }, catalog: { signers: 2 }, read: true, note: "" },
  reading: "The floor is two board members. jason suggests keeping it and naming which two.", readingLabel: READING,
  touches: [{ kind: "approval kind", key: "reserve-transfer", title: "Reserve transfers", builtin: "one person", with: "two signers", changes: true }],
  history: [{ act: "suggest", by: "jason", at: "2099-10-01T09:00:00+00:00" }],
});

export const MANAGER_LIMIT = row({
  key: "manager-limit", title: "Manager spending limit", family: "money", state: "declined", standing: "declined", stateWord: "declined",
  history: [
    { act: "suggest", by: "jason", at: "2099-07-01T09:00:00+00:00" },
    { act: "decline", by: "A. Secretary", at: "2099-08-01T20:00:00+00:00", why: "the manager's limit lives in the management contract", againOn: "2100-02-01" },
  ],
});

export const COUNTERSIGN = row({
  key: "payment-countersign", title: "Payment countersign", family: "money", state: "retired", standing: "retired", stateWord: "retired",
  history: [{ act: "retire", by: "A. Secretary", at: "2099-09-05T20:00:00+00:00", why: "replaced by Payment signers" }],
});

export const CONTRACT_AUTH = row({
  key: "contract-authorization", title: "Contract authorization", family: "contracts", state: "adopted", standing: "in-force",
  stateWord: "adopted, in force since 2099-09-20", effective: "2099-09-20", summary: "resolution on record first: yes", inForce: { ok: true, reason: "", lacks: "" },
  decision: { id: "2099-09-05-5" }, history: [{ act: "adopt", by: "A. Secretary", at: "2099-09-05T20:00:00+00:00", decision: "2099-09-05-5" }],
});

export const CONTRACT_TERM = row({
  key: "contract-term", title: "Contract term check", family: "contracts", state: "proposed", standing: "proposed", stateWord: "proposed to the board",
  summary: "longest term without a board vote: 12 months", proposedAs: "control-contract-term", proposedStatus: "open",
  history: [{ act: "suggest", by: "jason", at: "2099-10-01T09:00:00+00:00" }, { act: "propose", by: "A. Secretary", at: "2099-10-09T09:00:00+00:00" }],
});

/** The date has come and the roster cannot satisfy it: the vice president's office is vacant. */
export const MONTHLY_REVIEW = row({
  key: "monthly-review", title: "Monthly review", family: "reviews", state: "adopted", standing: "in-force-roster-lacks",
  stateWord: "adopted, in force; the roster cannot satisfy it, so the acts it governs are refused", effective: "2099-10-10",
  summary: "required offices: treasurer, vice president", inForce: { ok: true, reason: "", lacks: "the roster has no vice president" },
  roster: roster({ needs: [{ office: "treasurer", count: 1 }, { office: "vice president", count: 1 }], missing: [{ office: "vice president" }], lacks: "the roster has no vice president" }),
  missing: ["vice president"],
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", decision: "2099-10-03-2" }],
  decision: { id: "2099-10-03-2" },
});

/** Adopted, and the date has not come. */
export const DELIVERY_CLASS = row({
  key: "delivery-class", title: "Delivery class", family: "notices", state: "adopted", standing: "adopted-not-in-force",
  stateWord: "adopted, not in force: takes effect 2099-11-14", effective: "2099-11-14", summary: "first class for notice letters",
  inForce: { ok: false, reason: "adopted, not in force until 2099-11-14", lacks: "" },
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", decision: "2099-10-03-3" }], decision: { id: "2099-10-03-3" },
});

export const RECORDER = row({
  key: "recorder", title: "Recorder", family: "notices", state: "deferred", standing: "deferred", stateWord: "deferred",
  history: [{ act: "defer", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", why: "after the annual meeting", againOn: "2100-01-15" }],
});

export const SECOND_PERSON = row({
  key: "second-person", title: "Second person, other kinds", family: "onboarding", state: "suggested", standing: "suggested", stateWord: "suggested",
  summary: "a second person confirms: yes", history: [{ act: "suggest", by: "jason", at: "2099-10-01T09:00:00+00:00" }],
});

export const QUESTION = {
  key: "reserve-signers", type: "payment-signers", title: "Payment signers", family: "money" as const, familyTitle: "Money", kind: "question" as const,
  document: "Example Bylaws", number: "99.9(c)", citation: "Example Bylaws, 99.9(c)",
  words: "The reserve may be drawn on the signature of the officer named by the Board or, if none, the president.",
  question: true, whyQuestion: "it reads two ways about who may sign for the reserve. A question for the board or counsel.",
};

const ALL = [PAYMENT_SIGNERS, RESERVE, MANAGER_LIMIT, COUNTERSIGN, CONTRACT_AUTH, CONTRACT_TERM, MONTHLY_REVIEW, DELIVERY_CLASS, RECORDER, SECOND_PERSON];

export const COUNTS: ControlCounts = {
  total: 10, adopted: 4, inForce: 3, adoptedNotInForce: 1, proposed: 1, suggested: 2, declined: 1, deferred: 1, retired: 1, questions: 1, refused: 0,
};

export const CAVEATS = [
  "jason suggests; the board adopts. A control only adds to what the law, the governing documents, or a built-in rule already set, and is in force only from its effective date.",
  "The provision's words are the stored text, whole. jason's reading is jason's, not the provision.",
  "The roster check names offices and counts, never a person.",
];

const group = (family: ControlGroup["family"], title: string, controls: ControlRowData[], questions: ControlGroup["questions"] = []): ControlGroup =>
  ({ family, title, controls, questions });

export const PAGE: ControlsPage = {
  found: true, asOf: TODAY, label: "jason suggests; the board adopts", readingLabel: READING, counts: COUNTS,
  heading: "4 adopted (3 in force, 1 not in force); 1 proposed to the board; 2 suggested; 1 deferred; 1 declined; 1 retired; 1 question(s) for the board or counsel",
  families: [
    group("money", "Money", [PAYMENT_SIGNERS, RESERVE, MANAGER_LIMIT, COUNTERSIGN], [QUESTION]),
    group("contracts", "Contracts", [CONTRACT_AUTH, CONTRACT_TERM]),
    group("reviews", "Reviews", [MONTHLY_REVIEW]),
    group("notices", "Notices", [DELIVERY_CLASS, RECORDER]),
    group("onboarding", "Onboarding", [SECOND_PERSON]),
  ],
  controls: ALL, questions: [QUESTION], refused: [], read: "2099-10-01T09:00:00+00:00", empty: "", rosterRead: true, caveats: CAVEATS,
  types: [{ key: "payment-signers", title: "Payment signers", family: "money" }],
};

/** Nothing read yet: the governing documents are not ingested. */
export const EMPTY_PAGE: ControlsPage = {
  ...PAGE, counts: { ...COUNTS, total: 0, adopted: 0, inForce: 0, adoptedNotInForce: 0, proposed: 0, suggested: 0, declined: 0, deferred: 0, retired: 0, questions: 0 },
  heading: "no controls yet", families: [], controls: [], questions: [], read: "",
  empty: "jason has not read your governing documents. Ingest them from Onboarding.",
};

export const one = (control: ControlRowData, over: Partial<OneControl> = {}): OneControl => ({
  found: true, control,
  provision: { found: true, citation: control.basis.citation, words: control.basis.words, address: "", changedOn: "", setBy: "", outline: [] },
  label: "jason suggests; the board adopts", readingLabel: READING, caveats: CAVEATS, ...over,
});

export const PROPOSED_ANSWER: ProposeAnswer = {
  key: "reserve-withdrawals", item: "control-reserve-withdrawals", state: "proposed", refreshed: false, board: { added: 1 }, by: "A. Secretary",
  control: { ...RESERVE, state: "proposed", standing: "proposed", stateWord: "proposed to the board", proposedAs: "control-reserve-withdrawals", proposedStatus: "open" },
};

/** An approval kind with one control in force (the effective rule), one adopted but not yet in force, and a refusal. */
export const KIND_NOTICES: ControlNotices = {
  found: true, subject: "payhoa-attach-bills", subjectKind: "approval kind", title: "Payment plans", builtin: "one person", why: "Two signers are required above $2,500.00.",
  stricter: true, second: { always: false, aboveCents: 250000 }, roles: ["treasurer", "director"], mustInclude: [], clash: "", asOf: TODAY,
  controls: [{ key: "payment-signers", title: "Payment signers", adoptedOn: "2099-09-05T20:00:00+00:00", effective: "2099-09-20", effect: "signers: 2", link: "#/controls?key=payment-signers" }],
  waiting: [{ key: "delivery-class", title: "Delivery class", adoptedOn: "2099-10-03T20:00:00+00:00", effective: "2099-11-14", effect: "first class", link: "#/controls?key=delivery-class", reason: "adopted, not in force until 2099-11-14" }],
  refusals: ["Monthly review requires a treasurer and a vice president; the roster has no vice president"],
  caveats: ["The server refuses the same act whatever the page shows."],
};
