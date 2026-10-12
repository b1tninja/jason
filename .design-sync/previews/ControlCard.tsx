import { ControlCard } from "jason-ui";

// Made-up Oakview controls, in the shape `jason.controls.view` returns for one control. Dates are fixed fake ones in 2099; a roster
// names offices only; provision words are plainly fake sample text.
const READING = "jason's reading, not the provision";
const WORDS = "Sample bylaw text, not a statute: payments are signed by two officers unless the board names another manner.";
const roster = (over: Record<string, unknown> = {}) => ({
  read: true, needs: [{ office: "treasurer", count: 1 }, { office: "director", count: 1 }],
  seated: [{ office: "director", count: 1 }, { office: "president", count: 1 }, { office: "secretary", count: 1 }, { office: "treasurer", count: 1 }],
  missing: [], lacks: "", ...over,
});
const mk = (over: Record<string, unknown>): any => ({
  type: over.key, family: "money", familyTitle: "Money", scope: { kind: "all", value: "" }, parameters: {}, boardSets: [], summary: "",
  inForce: { ok: false, reason: "", lacks: "" },
  basis: { citation: "Example Bylaws, 99.9", words: WORDS, floor: { signers: 2 } }, floor: { provision: { signers: 2 }, catalog: { signers: 2 }, read: true, note: "" },
  reading: "Name the manner the bylaws allow: the treasurer and one other director above an amount the board sets.", readingLabel: READING,
  touches: [{ kind: "approval kind", key: "payhoa-attach-bills", title: "Payment plans", builtin: "one person", with: "two signers above $2,500.00", changes: true }],
  proposedAs: null, proposedStatus: null, decision: null, effective: "", history: [], roster: roster(), missing: [], changed: null,
  ...over,
});
const one = (control: any): any => ({
  found: true, control, label: "jason suggests; the board adopts", readingLabel: READING, caveats: [],
  provision: { found: true, citation: control.basis.citation, words: control.basis.words, address: "", changedOn: "", setBy: "", outline: [] },
});

const SUGGESTED = mk({
  key: "reserve-withdrawals", title: "Reserve withdrawals", state: "suggested", standing: "suggested", stateWord: "suggested", summary: "the board sets: signers",
  basis: { citation: "Example Bylaws, 99.9(b)", words: "Sample bylaw text, not a statute: withdrawals from the reserve account require the signatures of two board members.", floor: { signers: 2 } },
  history: [{ act: "suggest", by: "jason", at: "2099-10-01T09:00:00+00:00" }],
});
const IN_FORCE = mk({
  key: "payment-signers", title: "Payment signers", state: "adopted", standing: "in-force", stateWord: "adopted, in force since 2099-09-20", effective: "2099-09-20",
  summary: "signers: 2; offices that may sign: treasurer, director; second signer above: $2,500.00", inForce: { ok: true, reason: "", lacks: "" },
  decision: { id: "2099-09-05-4", meeting: "2099-09-05 regular meeting", outcome: "approved", tally: { yes: 5, no: 0, abstain: 0 } },
  history: [
    { act: "suggest", by: "jason", at: "2099-09-01T09:00:00+00:00" },
    { act: "propose", by: "A. Secretary", at: "2099-09-02T09:00:00+00:00", why: "put before the board as board item item-1" },
    { act: "adopt", by: "A. Secretary", at: "2099-09-05T20:00:00+00:00", decision: "2099-09-05-4" },
  ],
});
const LACKS = mk({
  key: "monthly-review", title: "Monthly review", family: "reviews", familyTitle: "Reviews", state: "adopted", standing: "in-force-roster-lacks",
  stateWord: "adopted, in force; the roster cannot satisfy it, so the acts it governs are refused", effective: "2099-10-10",
  summary: "required offices: treasurer, vice president", inForce: { ok: true, reason: "", lacks: "the roster has no vice president" },
  roster: roster({ needs: [{ office: "treasurer", count: 1 }, { office: "vice president", count: 1 }], missing: [{ office: "vice president" }], lacks: "the roster has no vice president" }),
  missing: ["vice president"], decision: { id: "2099-10-03-2" }, touches: [],
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", decision: "2099-10-03-2" }],
});
const AHEAD = mk({
  key: "delivery-class", title: "Delivery class", family: "notices", familyTitle: "Notices", state: "adopted", standing: "adopted-not-in-force",
  stateWord: "adopted, not in force: takes effect 2099-11-14", effective: "2099-11-14", summary: "first class for notice letters",
  inForce: { ok: false, reason: "adopted, not in force until 2099-11-14", lacks: "" }, decision: { id: "2099-10-03-3" }, touches: [], floor: { provision: null, catalog: null, read: false, note: "floor: read by a person" },
  history: [{ act: "adopt", by: "A. Secretary", at: "2099-10-03T20:00:00+00:00", decision: "2099-10-03-3" }],
});
const CHANGED = {
  was: "Sample text, not a statute: payments are signed by two officers.",
  now: "Sample text, not a statute: payments over a limit the board sets are signed by two officers; others by one.",
  changedOn: "2099-08-15", basis: "an amendment of the sample bylaws", citation: "EX 123.4",
};

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 900 }}>{children}</div>;
const me = { by: "A. Secretary" };

/** A suggestion: bands 1, 2, 4, 5, and 6 (band 3 is the board's), the provision recited before jason's labeled reading, and "Propose to the board" at the foot. */
export const Suggestion = () => <Frame><ControlCard data={one(SUGGESTED)} as={me} /></Frame>;

/** A control in force: the adopted stamp, the decision with its vote as taken, what it changes, the roster check passing, and the history newest first. */
export const InForce = () => <Frame><ControlCard data={one(IN_FORCE)} as={me} /></Frame>;

/** In force, but the roster lacks an office: the warning note above the bands and the shortfall in band 5. */
export const RosterCannotSatisfy = () => <Frame><ControlCard data={one(LACKS)} as={me} /></Frame>;

/** Adopted with the board's date still ahead: the calendar note says it binds nothing until then. */
export const AdoptedNotYetInForce = () => <Frame><ControlCard data={one(AHEAD)} as={me} /></Frame>;

/** A provision amended since adoption: the changed banner sits above band 1 with the old and new words side by side. */
export const ProvisionAmended = () => <Frame><ControlCard data={one({ ...IN_FORCE, changed: CHANGED })} as={me} /></Frame>;
