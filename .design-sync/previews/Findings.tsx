import { Findings } from "jason-ui";

/** Flags a review raised on one obligation; each is a warn badge and a sentence a person reads. */
export const InsuranceFindings = () => (
  <Findings
    items={[
      "D&O policy term ended 2026-09-30; no renewal certificate in Drive",
      "Fidelity bond below Civil Code 5806 minimum (reserves + 3 months of assessments)",
      "Master policy names the prior management company as additional insured",
    ]}
  />
);

/** A single flag, as a table cell shows it beside a kept record. */
export const OneGap = () => <Findings items={["no reserve study on file for fiscal year 2025"]} />;

/** Nothing flagged: the default empty text in muted type. */
export const NothingFlagged = () => <Findings items={[]} />;

/** A row that passed its check with a custom empty word, as the Notes column shows it. */
export const PassedWithDash = () => <Findings items={[]} empty="—" />;

/** Calendar history: late filings with how late, and a count of the on-time ones when there are none. */
export const LateHistory = () => (
  <div style={{ display: "grid", gap: 12 }}>
    <Findings items={["2025-11-30: late (12d late)", "2024-11-30: no evidence"]} />
    <Findings items={[]} empty="6 on time" />
  </div>
);

/** The default question mark, `glyph={false}` (off, for a dense cell), and a named glyph, one under another. */
export const GlyphVariants = () => (
  <div style={{ display: "grid", gap: 12 }}>
    <Findings items={["default: no reserve study on file"]} />
    <Findings items={["glyph off: no reserve study on file"]} glyph={false} />
    <Findings items={["named glyph: policy term ended 2026-09-30"]} glyph="calendar-clock" />
  </div>
);
