import { Stat, Money, Badge } from "jason-ui";

/** Money values need room: a six-figure amount at 1.5rem clips in a 150px column, so the grid here uses 200px columns. */
const wide = { gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" };

/** The budget row: money values, a hint under each with the budgeted figure. */
export const BudgetRow = () => (
  <div className="stats" style={wide}>
    <Stat label="Revenue YTD" value={<Money cents={21456000} />} hint="budget $21,900.00" />
    <Stat label="Expense YTD" value={<Money cents={19873245} />} hint="budget $20,400.00" />
    <Stat label="Net YTD" value={<Money cents={1582755} />} />
    <Stat label="Reserves" value={<Money cents={48210033} />} hint="Plaid balance; can lag the bank" />
  </div>
);

/** Plain counts, with and without a hint. */
export const Counts = () => (
  <div className="stats">
    <Stat label="Files in the library" value={1284} hint="1,271 distinct" />
    <Stat label="Unclassified" value={37} hint="no rule or model placed them" />
    <Stat label="Records covered" value={20} hint="of the CIV 5200 kinds" />
    <Stat label="Treasurer's runs" value={9} />
  </div>
);

/** A negative amount is marked by sign and color; a date or a word can be the value too. */
export const MixedValues = () => (
  <div className="stats" style={wide}>
    <Stat label="Outstanding" value={<Money cents={-1250000} />} hint="borrowed 2025-11-03" />
    <Stat label="Restore by" value="2026-11-03" hint="Civil Code 5515, one year" />
    <Stat label="Latest balance sheet" value="2026-08" hint="as of 2026-08-31" />
    <Stat label="Standing" value={<Badge tone="warn">outstanding</Badge>} />
  </div>
);

/** One stat alone, as a card's action slot shows the total past due. */
export const Single = () => (
  <div style={{ display: "inline-block" }}>
    <Stat label="past due" value={<Money cents={742150} />} />
  </div>
);
