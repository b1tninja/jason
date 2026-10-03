import { Caveats, Card } from "jason-ui";

/** One caveat, the usual case under a money card. */
export const Single = () => <Caveats items={["A finding is a question for the treasurer, not a verdict."]} />;

/** Several caveats stack as paragraphs under one warn rule. */
export const Several = () => (
  <Caveats
    items={[
      "A payment is evidence that a duty was done, not proof.",
      "The report the board saw is the record of what it was told; the ledger is what the bank was told.",
      "Plaid balances can lag the bank by a business day.",
      "A lead is evidence, not a pin.",
    ]}
  />
);

/** A long caveat wraps inside the rule without breaking the left border. */
export const LongText = () => (
  <Caveats
    items={[
      "A lien standing comes from the recorder's index as of the last sync. A release recorded after that date, or indexed under another spelling of the association's name, does not show here; confirm against the recorder before any notice is sent, and treat a RELEASE_DUE standing as a question for counsel rather than a finding.",
    ]}
  />
);

/** Where it sits: after the card's content, in the muted voice, never behind a toggle. */
export const UnderACard = () => (
  <div style={{ display: "grid", gap: 12 }}>
    <Card title="Reserve contributions against the budget">
      <p style={{ margin: 0 }}>Nine of nine monthly transfers landed; the October transfer is due 2026-10-15.</p>
    </Card>
    <Caveats items={["The schedule is the adopted budget's; a transfer that lands a day late is still counted in its month."]} />
  </div>
);
