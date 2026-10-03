import { DecisionCard } from "jason-ui";

const directors = ["Alvarez (President)", "Chen (Treasurer)", "Okafor (Secretary)", "Patel", "Reyes"];

/** A fresh card for an agenda item: motion empty, vote open, no Record button until the motion is typed. */
export const Fresh = () => <DecisionCard title="Pool deck resurfacing: select bidder" directors={directors} onSave={() => {}} />;

/** A motion made and the roll call marked: the tally reads on its face, the outcome still the board's to choose, the Record button shown. */
export const VoteTaken = () => (
  <DecisionCard
    title="Insurance renewal: approve the quote"
    directors={directors}
    onSave={() => {}}
    initial={{
      motion: "Accept the master policy renewal quote of $41,250 for the 2026-27 term and authorize the president to sign.",
      mover: "Chen (Treasurer)",
      second: "Patel",
      votes: { "Alvarez (President)": "aye", "Chen (Treasurer)": "aye", "Okafor (Secretary)": "aye", Patel: "aye", Reyes: "no" },
      by: "D. Okafor",
    }}
  />
);

/** Recorded as approved: the outcome pill replaces the vote-open badge. */
export const Approved = () => (
  <DecisionCard
    title="Reserve transfer for roof repair"
    directors={directors}
    onSave={() => {}}
    initial={{
      motion: "Transfer $18,000 from the reserve account to operating for the Building 2 roof repair, to be repaid within one year (CIV 5515).",
      mover: "Alvarez (President)",
      second: "Okafor (Secretary)",
      votes: { "Alvarez (President)": "aye", "Chen (Treasurer)": "aye", "Okafor (Secretary)": "aye", Patel: "abstain", Reyes: "absent" },
      outcome: "approved",
      by: "D. Okafor",
      notes: "Repayment schedule to the treasurer's report.",
    }}
  />
);

/** An executive-session decision: the warn badge marks it, and the outcome is denied. */
export const ExecutiveDenied = () => (
  <DecisionCard
    title="Hearing: 123 Main St, unit 7"
    directors={directors}
    onSave={() => {}}
    initial={{
      session: "executive session",
      motion: "Find a violation of CC&R section 7.2 and impose the fine in the schedule.",
      mover: "Reyes",
      second: "Patel",
      votes: { "Alvarez (President)": "no", "Chen (Treasurer)": "no", "Okafor (Secretary)": "aye", Patel: "aye", Reyes: "no" },
      outcome: "denied",
      by: "D. Okafor",
    }}
  />
);

/** Busy: a save in flight disables the Record button. */
export const Saving = () => (
  <DecisionCard
    title="Adopt the 2027 operating budget"
    directors={directors}
    busy
    onSave={() => {}}
    initial={{ motion: "Adopt the 2027 operating budget as presented.", mover: "Chen (Treasurer)", second: "Reyes", votes: { "Alvarez (President)": "aye", "Chen (Treasurer)": "aye", Reyes: "aye" }, by: "D. Okafor" }}
  />
);
