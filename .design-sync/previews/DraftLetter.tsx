import { DraftLetter, type Letter } from "jason-ui";

/** The officers who may approve. "The board" approves only by a vote at a meeting, recorded by the president or secretary. */
const people = [
  { name: "D. Okafor", role: "president", approves: ["the president"], canApproveBoard: true },
  { name: "R. Lind", role: "secretary", approves: ["the secretary"], canApproveBoard: true },
  { name: "M. Chen", role: "treasurer", approves: ["the treasurer"], canApproveBoard: false },
  { name: "P. Varga", role: "manager", approves: ["the manager"], canApproveBoard: false },
];

/** The association's designated recipient for official communications (CIV 4035), as the server carries it. */
const REPLY_TO = "Secretary, Example Association, 123 Main St, Anytown, CA 90000; board@example.org";
const vote = { id: "3", date: "2026-10-03", title: "The board approved it by vote at its meeting of 2026-10-03 (CIV 4910); recorded by R. Lind, secretary", tone: "good" as const, by: "R. Lind" };

const release: Letter = {
  key: "Drive/Collections/Unit 7/release.docx",
  kind: "Lien release",
  title: "Release of Notice of Delinquent Assessment",
  date: "2026-10-03",
  to: "County Recorder; copy to the owner of record, Unit 7, 123 Main St",
  via: "Recording; first-class mail to the owner",
  body: [
    "The association recorded a Notice of Delinquent Assessment against Unit 7 on 2026-04-14. The account has since been paid in full, including the assessments, late charges, interest, and the costs of collection.",
    "The association therefore releases the notice and asks that this release be recorded against the parcel. A copy goes to the owner by first-class mail within twenty-one days of payment (CIV 5685).",
  ],
  signoff: "The Board of Directors",
  approver: "the board",
  stage: "requested",
  sentCommand: "jason letter release --unit 7 --yes",
  replyTo: REPLY_TO,
  log: [
    { id: "1", date: "2026-10-02", title: "Draft saved", by: "P. Varga" },
    { id: "2", date: "2026-10-02", title: "Approval requested from the board", by: "P. Varga" },
  ],
};

const vendor: Letter = {
  ...release,
  key: "Drive/Finance/Greenway/itemized-invoice.docx",
  kind: "Vendor inquiry",
  title: "Request for an itemized invoice",
  to: "Billing, Greenway Landscape",
  via: "Email",
  body: [
    "Invoice 4471 of 2026-09-18 bills $2,340.00 as a single line, \"September grounds\". The association pays from an itemized invoice.",
    "Please resend it with each visit, the crew hours, and any materials on their own lines, so the treasurer can match it to the contract schedule.",
  ],
  signoff: "M. Chen, Treasurer",
  approver: "the treasurer",
  sentCommand: "jason letter vendor-inquiry --yes",
};

/** A fresh draft: the warn badge, Save draft behind a confirm, Copy text, and the note field. No trail yet. The approval
 * line says jason drafts and nothing is saved, and that the reply address is not on file yet. */
export const Draft = () => <DraftLetter letter={{ ...vendor, stage: "draft", log: [], replyTo: undefined }} me="P. Varga" people={people} onStage={() => {}} />;

/** Saved to Drive: Ask the approver, and the path it was saved to. The approval line names who saved it. */
export const Saved = () => (
  <DraftLetter letter={{ ...vendor, stage: "saved", log: [{ id: "1", date: "2026-10-02", title: "Draft saved", by: "P. Varga" }] }} me="P. Varga" people={people} onStage={() => {}} />
);

/** Awaiting the board: the treasurer is signed in, who cannot record a board vote, so the footer says why (CIV 4910). */
export const RequestedCannotApprove = () => <DraftLetter letter={release} me="M. Chen" people={people} onStage={() => {}} />;

/** Awaiting the treasurer, who is signed in: Approve as her, Send back, Withdraw, and the trail. */
export const RequestedCanApprove = () => <DraftLetter letter={vendor} me="M. Chen" people={people} onStage={() => {}} />;

/** Approved: the terminal command a person runs and Record as sent. Nothing here sends. The approval line names the
 * board's meeting and the secretary who recorded the vote. */
export const Approved = () => (
  <DraftLetter
    letter={{ ...release, stage: "approved", meeting: "2026-10-03", log: [...release.log, vote] }}
    me="P. Varga"
    people={people}
    onStage={() => {}}
  />
);

/** Sent and logged: the green sent line and the full trail. */
export const Sent = () => (
  <DraftLetter
    letter={{
      ...release,
      stage: "sent",
      meeting: "2026-10-03",
      sentOn: "2026-10-03",
      sentRef: "mailroom 48213",
      log: [
        ...release.log,
        vote,
        { id: "4", date: "2026-10-03", title: "Recorded as sent", tone: "good", by: "P. Varga" },
      ],
    }}
    me="P. Varga"
    people={people}
  />
);

/** The owner's view: the document only, with the badge the owner sees, and no buttons; it still ends with the
 * approval line: who drafted, who approved, that the officers sign, and where replies go. */
export const Readonly = () => <DraftLetter letter={{ ...release, stage: "sent", meeting: "2026-10-03", log: [...release.log, vote], ownerBadge: "mailed" }} readonly />;
