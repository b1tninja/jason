import { DecisionBrief } from "jason-ui";

const landscape = {
  question: "Which landscape contract does the board sign for 2027?",
  criteria: ["Monthly cost", "Term", "Irrigation repairs", "Notice to cancel"],
  options: [
    { label: "Renew with Greenway Landscape", values: ["$1,850.00", "two years", "included, parts billed", "60 days"] },
    { label: "Switch to Sierra Turf Care", values: ["$1,640.00", "one year", "billed hourly", "30 days"] },
    { label: "Rebid in the spring", values: ["$1,850.00 month to month until then", "none", "as today", "30 days"] },
  ],
  facts: ["Both bids are in the packet.", "The current contract ends 2026-12-31.", "The reserve study funds no landscaping."],
};

/** The card: one question, lettered options with the same criteria in the same order, the facts on file, and the footer that says jason does not recommend. */
export const Card = () => <DecisionBrief decision={landscape} />;

/** Two options and a value not known: the empty cell stays in its row so the criteria still line up. */
export const TwoOptions = () => (
  <DecisionBrief
    decision={{
      question: "How is the reserve loan restored (CIV 5515)?",
      criteria: ["Source", "When", "Effect on operating"],
      options: [
        { label: "Transfer from operating", values: ["operating account", "by 2026-10-31", "cash on hand drops to $12,400.00"] },
        { label: "Repay over six months", values: ["monthly transfers of $3,000.00", "2026-11 through 2027-04"] },
      ],
      facts: ["The loan was $18,000.00 on 2026-07-15 for the Building 2 roof repair."],
    }}
  />
);

/** The three-column stage variant (`columns`), as the meeting stage shows the options to the room. */
export const Columns = () => <DecisionBrief decision={landscape} columns />;

/** No facts on file: the facts list is left out, the footer stays. */
export const NoFacts = () => (
  <DecisionBrief
    decision={{
      question: "Which pool hours for the winter?",
      criteria: ["Hours", "Heating cost a month"],
      options: [{ label: "Keep 6 am to 10 pm", values: ["16 hours", "$920.00"] }, { label: "Shorten to 8 am to 8 pm", values: ["12 hours", "$710.00"] }, { label: "Close December through February", values: ["none", "$0.00"] }],
    }}
  />
);
