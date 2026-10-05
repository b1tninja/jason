import { Timeline, Badge } from "jason-ui";

/** The governing instruments of record, oldest first; superseded ones in neutral, the controlling one in green. */
export const GoverningInstruments = () => (
  <Timeline
    events={[
      { id: "1", date: "1979-06-14", title: <>Declaration of Covenants, Conditions and Restrictions <span style={{ color: "var(--muted)" }}>79-061400</span></>, detail: "declaration · phase 1 · superseded by 2004-112233", tone: "neutral" },
      { id: "2", date: "1981-03-02", title: <>First Annexation <span style={{ color: "var(--muted)" }}>81-030201</span></>, detail: "annexation · phase 2", tone: "good" },
      { id: "3", date: "2004-11-22", title: <>Amended and Restated Declaration <span style={{ color: "var(--muted)" }}>2004-112233</span></>, detail: "declaration · controls today", tone: "good" },
      { id: "4", date: "2019-08-30", title: <>Notice of Delinquent Assessment <span style={{ color: "var(--muted)" }}>2019-083001</span></>, detail: "assessment lien · released 2021-02-10", tone: "warn" },
    ]}
  />
);

/** A lien's lifecycle: the steps in the index. Undated steps sort last. */
export const LienLifecycle = () => (
  <Timeline
    events={[
      { id: "a", date: "2023-05-01", title: "Pre-lien notice mailed (CIV 5660)", tone: "neutral" },
      { id: "b", date: "2023-06-15", title: "Notice of Delinquent Assessment recorded", detail: "instrument 2023-061501", tone: "warn" },
      { id: "c", date: "2024-01-20", title: "Paid in full at sale", detail: "escrow closed", tone: "good" },
      { id: "d", date: "", title: <><Badge tone="bad">release due</Badge> no release of record (CIV 5685, 21 days)</>, tone: "bad" },
    ]}
  />
);

/** Nothing to show. */
export const Empty = () => <Timeline events={[]} />;

/** Provenance glyphs on each event: proposed, decided, sent, taken back, locked. */
export const ProvenanceGlyphs = () => (
  <Timeline
    events={[
      { id: "1", date: "2026-09-02", title: "Late-fee waiver proposed to the board", glyph: "proposal" },
      { id: "2", date: "2026-09-10", title: "Board approved the waiver", detail: "2 of 3 directors", glyph: "badge-check", tone: "good" },
      { id: "3", date: "2026-09-12", title: "Letter sent to the owner", detail: "mailed by a person", glyph: "send" },
      { id: "4", date: "2026-09-20", title: "Waiver taken back after a payment bounced", glyph: "undo-2", tone: "warn" },
      { id: "5", date: "2026-09-21", title: "Account locked from further changes", glyph: "lock", tone: "bad" },
    ]}
  />
);

/** Tone only, no glyph given: good, warn, and bad take the attention glyph for their tone; the neutral one keeps a blank slot so titles align. */
export const MixedTones = () => (
  <Timeline
    events={[
      { id: "a", date: "2026-08-01", title: "Reserve study received", tone: "neutral" },
      { id: "b", date: "2026-08-15", title: "Transfer landed", tone: "good" },
      { id: "c", date: "2026-09-15", title: "Transfer late", tone: "warn" },
      { id: "d", date: "2026-10-01", title: "Transfer missing", tone: "bad" },
    ]}
  />
);
