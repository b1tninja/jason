import { ControlRow } from "jason-ui";

// Made-up Oakview controls in the shape `jason.controls.view` returns. Dates are fixed fake ones in 2099; a roster names offices only.
const READING = "jason's reading, not the provision";
const WORDS = "Sample bylaw text, not a statute: payments are signed by two officers unless the board names another manner.";
const roster = { read: true, needs: [{ office: "treasurer", count: 1 }], seated: [{ office: "treasurer", count: 1 }, { office: "president", count: 1 }], missing: [], lacks: "" };
const mk = (over: Record<string, unknown>): any => ({
  type: over.key, family: "money", familyTitle: "Money", scope: { kind: "all", value: "" }, parameters: {}, boardSets: [], summary: "",
  inForce: { ok: false, reason: "", lacks: "" },
  basis: { citation: "Example Bylaws, 99.9", words: WORDS, floor: null }, floor: { provision: null, catalog: null, read: false, note: "" },
  reading: "", readingLabel: READING, touches: [], proposedAs: null, proposedStatus: null, decision: null, effective: "", history: [], roster, missing: [], changed: null,
  ...over,
});

const SUGGESTED = mk({
  key: "reserve-withdrawals", title: "Reserve withdrawals", state: "suggested", standing: "suggested", stateWord: "suggested",
  summary: "the board sets: signers", basis: { citation: "Example Bylaws, 99.9(b)", words: WORDS, floor: { signers: 2 } },
  history: [{ act: "suggest", by: "jason", at: "2099-10-01T09:00:00+00:00" }],
});
const IN_FORCE = mk({
  key: "payment-signers", title: "Payment signers", state: "adopted", standing: "in-force", stateWord: "adopted, in force since 2099-09-20", effective: "2099-09-20",
  summary: "signers: 2; offices that may sign: treasurer, director; second signer above: $2,500.00", inForce: { ok: true, reason: "", lacks: "" },
  decision: { id: "2099-09-05-4" },
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-09-05T20:00:00+00:00", decision: "2099-09-05-4" }],
});
const AHEAD = mk({
  key: "delivery-class", title: "Delivery class", family: "notices", familyTitle: "Notices", state: "adopted", standing: "adopted-not-in-force",
  stateWord: "adopted, not in force: takes effect 2099-11-14", effective: "2099-11-14", summary: "first class for notice letters",
  inForce: { ok: false, reason: "adopted, not in force until 2099-11-14", lacks: "" },
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", decision: "2099-10-03-3" }],
});
const LACKS = mk({
  key: "monthly-review", title: "Monthly review", family: "reviews", familyTitle: "Reviews", state: "adopted", standing: "in-force-roster-lacks",
  stateWord: "adopted, in force; the roster cannot satisfy it, so the acts it governs are refused", effective: "2099-10-10",
  summary: "required offices: treasurer, vice president", inForce: { ok: true, reason: "", lacks: "the roster has no vice president" },
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", decision: "2099-10-03-2" }],
});
const PROPOSED = mk({
  key: "contract-term", title: "Contract term check", family: "contracts", familyTitle: "Contracts", state: "proposed", standing: "proposed", stateWord: "proposed to the board",
  summary: "longest term without a board vote: 12 months", proposedAs: "item-1", proposedStatus: "open",
  history: [{ act: "suggest", by: "jason", at: "2099-10-01T09:00:00+00:00" }, { act: "propose", by: "A. Secretary", at: "2099-10-09T09:00:00+00:00" }],
});
const DECLINED = mk({
  key: "manager-limit", title: "Manager spending limit", state: "declined", standing: "declined", stateWord: "declined",
  history: [{ act: "decline", by: "A. Secretary", at: "2099-08-01T20:00:00+00:00", why: "the manager's limit lives in the management contract", againOn: "2100-02-01" }],
});
const DEFERRED = mk({
  key: "recorder", title: "Recorder", family: "notices", familyTitle: "Notices", state: "deferred", standing: "deferred", stateWord: "deferred",
  history: [{ act: "defer", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", why: "after the annual meeting", againOn: "2100-01-15" }],
});
const RETIRED = mk({
  key: "payment-countersign", title: "Payment countersign", state: "retired", standing: "retired", stateWord: "retired",
  history: [{ act: "retire", by: "A. Secretary", at: "2099-09-05T20:00:00+00:00", why: "replaced by Payment signers" }],
});

const List = ({ children }: { children: React.ReactNode }) => <ul className="control-list" style={{ maxWidth: 760 }}>{children}</ul>;

/** A suggestion: the title links to the card, the word says "suggested", and "Propose" is its own control. It never says it is in force. */
export const Suggestion = () => <List><ControlRow row={SUGGESTED} as={{ by: "A. Secretary" }} /></List>;

/** The three ways an adopted control stands: in force, adopted with the date still ahead, and in force but the roster cannot satisfy it. */
export const AdoptedStandings = () => (
  <List><ControlRow row={IN_FORCE} /><ControlRow row={AHEAD} /><ControlRow row={LACKS} /></List>
);

/** A control before the board: it names the board item that carries it. */
export const BeforeTheBoard = () => <List><ControlRow row={PROPOSED} /></List>;

/** The board's other outcomes, each with its reason and the date it may be asked again. */
export const ClosedOutcomes = () => (
  <List><ControlRow row={DECLINED} /><ControlRow row={DEFERRED} /><ControlRow row={RETIRED} /></List>
);

/** The onboarding step's row: the provision's words under a disclosure, and no per-row Propose. */
export const InTheOnboardingStep = () => <List><ControlRow row={SUGGESTED} inStep /></List>;
