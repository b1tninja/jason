import { ApprovalsInbox, type Letter } from "jason-ui";

const people = [
  { name: "D. Okafor", role: "president", approves: ["the president"], canApproveBoard: true },
  { name: "R. Lind", role: "secretary", approves: ["the secretary"], canApproveBoard: true },
  { name: "M. Chen", role: "treasurer", approves: ["the treasurer"], canApproveBoard: false },
  { name: "P. Varga", role: "manager", approves: ["the manager"], canApproveBoard: false },
];

const release: Letter = {
  key: "Drive/Collections/Unit 7/release.docx", kind: "Lien release", title: "Release of Notice of Delinquent Assessment", date: "2026-10-03",
  to: "County Recorder; copy to the owner, Unit 7", via: "Recording; first-class mail", body: ["The association releases the notice."],
  signoff: "The Board of Directors", approver: "the board", stage: "requested", sentCommand: "jason letter release --unit 7 --yes",
  log: [{ id: "1", date: "2026-10-02", title: "Draft saved", by: "P. Varga" }, { id: "2", date: "2026-10-02", title: "Approval requested from the board", by: "P. Varga" }],
};
const vendor: Letter = {
  ...release, key: "Drive/Finance/Greenway/itemized-invoice.docx", kind: "Vendor inquiry", title: "Request for an itemized invoice",
  approver: "the treasurer", to: "Billing, Greenway Landscape", via: "Email", sentCommand: "jason letter vendor-inquiry --yes",
  log: [{ id: "1", date: "2026-10-03", title: "Approval requested from the treasurer", by: "P. Varga" }],
};
const notice: Letter = {
  ...release, key: "Drive/Meetings/2026-10-21/notice.docx", kind: "Meeting notice", title: "Notice of the October 21 board meeting",
  approver: "the secretary", to: "All members", via: "Email and the clubhouse board", stage: "approved", sentCommand: "jason notice post --meeting 2026-10-21 --yes",
  log: [{ id: "1", date: "2026-10-01", title: "Approved by the secretary", tone: "good", by: "R. Lind" }],
};
const reminder: Letter = {
  ...release, key: "Drive/Collections/Unit 12/reminder.docx", kind: "Payment reminder", title: "Reminder: assessment past due, Unit 12",
  approver: "the treasurer", to: "Owner of record, Unit 12", via: "First-class mail", stage: "sent", sentOn: "2026-10-01", sentRef: "mailroom 48190",
  log: [{ id: "1", date: "2026-10-01", title: "Recorded as sent", tone: "good", by: "P. Varga" }],
};
const minutes: Letter = {
  ...release, key: "Drive/Meetings/2026-09-16/minutes-draft.docx", kind: "Draft minutes", title: "Draft minutes of September 16",
  approver: "the secretary", to: "All members", via: "Email", stage: "sent", sentOn: "2026-09-28", sentRef: "sent-mail 2026-09-28",
  log: [{ id: "1", date: "2026-09-28", title: "Recorded as sent", tone: "good", by: "R. Lind" }],
};

const letters = [release, vendor, notice, reminder, minutes];

/** The treasurer signed in: she may approve the vendor letter but not record a board vote, so the lien release says why. */
export const Treasurer = () => <ApprovalsInbox today="2026-10-03" letters={letters} me="M. Chen" people={people} onAction={() => {}} onOpen={() => {}} />;

/** The secretary signed in: Record board approval shows on the board's letter; the treasurer's letter is not hers to approve. */
export const Secretary = () => <ApprovalsInbox today="2026-10-03" letters={letters} me="R. Lind" people={people} onAction={() => {}} onOpen={() => {}} go={() => {}} />;

/** Nothing waiting at all: each group's empty line under zero counts. */
export const Empty = () => <ApprovalsInbox today="2026-10-03" letters={[]} me="D. Okafor" people={people} onAction={() => {}} />;

/** Only sent letters on file, and no one picked as signed in. */
export const SentOnly = () => <ApprovalsInbox today="2026-10-03" letters={[reminder, minutes]} me="" people={people} onAction={() => {}} onOpen={() => {}} />;
