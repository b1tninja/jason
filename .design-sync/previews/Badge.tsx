import { Badge } from "jason-ui";

/** The four tones side by side; the border is currentColor, so the tone carries the whole badge. */
export const Tones = () => (
  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
    <Badge>landscaping</Badge>
    <Badge tone="good">kept</Badge>
    <Badge tone="warn">no minutes</Badge>
    <Badge tone="bad">none</Badge>
  </div>
);

/** Neutral is a category word: a payment's category, a record's delivery, a file's kind. */
export const Categories = () => (
  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
    <Badge>operating</Badge>
    <Badge>reserve</Badge>
    <Badge>insurance</Badge>
    <Badge>elevator</Badge>
    <Badge>meeting minutes</Badge>
    <Badge>annexation</Badge>
  </div>
);

/** A count in a card's action slot: red while anything is missing, green at zero. */
export const Counts = () => (
  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
    <Badge tone="bad">{`${3} gaps`}</Badge>
    <Badge tone="good">{`${0} gaps`}</Badge>
    <Badge tone="warn">{`${2} unreadable`}</Badge>
    <Badge tone="good">{`${12} of ${12} attached`}</Badge>
  </div>
);

/** Inline with body text, the badge sits on the baseline and keeps its small size. */
export const InlineWithText = () => (
  <p style={{ margin: 0 }}>
    Harbor Insurance Agency <Badge>insurance</Badge> paid 2026-09-15; the attachment names another vendor <Badge tone="warn">other vendor</Badge>.
    Minutes for 2026-07-10 <Badge tone="bad">missing</Badge>; the 2026-08-14 set is <Badge tone="good">in the library</Badge>.
  </p>
);
