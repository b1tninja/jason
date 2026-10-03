import { Money } from "jason-ui";

/** Integer cents in, dollars out: a thousands separator, always two decimals. */
export const Amounts = () => (
  <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "baseline" }}>
    <Money cents={0} />
    <Money cents={6120} />
    <Money cents={185000} />
    <Money cents={1240000} />
    <Money cents={48210033} />
  </div>
);

/** A negative amount carries a sign and the bad color; never color alone. */
export const Negative = () => (
  <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "baseline" }}>
    <Money cents={-2500} />
    <Money cents={-1250000} />
    <Money cents={-25275} />
  </div>
);

/** In a right-aligned column, tabular numerals keep the decimals in line. */
export const Column = () => (
  <div className="num" style={{ display: "grid", gap: 4, width: 160 }}>
    <Money cents={412377} />
    <Money cents={96000} />
    <Money cents={1240000} />
    <Money cents={-18900} />
    <Money cents={52500} />
  </div>
);

/** Inline in a sentence: the span inherits the surrounding size and weight. */
export const InSentence = () => (
  <p style={{ margin: 0 }}>
    Valley Landscape Co. was paid <Money cents={185000} /> on 2026-09-02 against a budget of <Money cents={180000} />, a gap of <Money cents={-5000} /> for the month.
  </p>
);
