import { Evidence } from "jason-ui";

/** What a board item cites: a recorded instrument, a Drive path, and the command that produced the figure. */
export const BoardItemEvidence = () => (
  <Evidence
    items={[
      "instrument 2023-061501",
      "Drive/Board/2026/09-15 minutes.pdf",
      "jason books-check --month 2026-09",
    ]}
  />
);

/** A duty's outputs with the label changed to Tools. */
export const DutyTools = () => (
  <Evidence label="Tools" items={["jason calendar", "jason inbox --deadlines", "board_digest (MCP)"]} />
);

/** Chips with no label at all, as the definition list in Duties shows them. */
export const Unlabeled = () => (
  <Evidence label="" items={["data/mailroom/sent.jsonl", "data/payhoa/forms.json", "Reserve study 2024 (Drive)"]} />
);

/** One citation only. */
export const SingleRecord = () => <Evidence items={["Civil Code 5855(a) — 10 days' notice"]} />;

/** Many chips wrap inside a narrow column. */
export const WrappedInNarrowColumn = () => (
  <div style={{ maxWidth: 280 }}>
    <Evidence
      label="Records"
      items={[
        "2004-112233 Amended and Restated CC&Rs",
        "2019-083001 Notice of Delinquent Assessment",
        "2021-021001 Release of Lien",
        "Assessor parcel 123-456-789-0000",
        "PayHOA ledger, unit 207",
      ]}
    />
  </div>
);
