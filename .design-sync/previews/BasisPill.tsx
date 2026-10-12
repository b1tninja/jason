import { BasisPill } from "jason-ui";

const row = { display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" } as const;

/** Whose date it is, as one word and a glyph: the law's, the governing documents', a counterparty's, a provider's, a person's. */
export const Bases = () => (
  <div style={row}>
    <BasisPill basis="law" />
    <BasisPill basis="documents" />
    <BasisPill basis="counterparty" />
    <BasisPill basis="provider" />
    <BasisPill basis="person" />
  </div>
);

/** A proposed number is drawn outlined and never as a stamp. */
export const Proposed = () => (
  <div style={row}>
    <BasisPill basis="proposed policy" />
    <BasisPill basis="law" />
  </div>
);

/** The loader may send its own label; it replaces the word but keeps the glyph. */
export const WithLabel = () => (
  <div style={row}>
    <BasisPill basis="law" label="LEGAL" />
    <BasisPill basis="documents" label="BYLAWS" />
    <BasisPill basis="person" label="A. OWNER" />
  </div>
);

/** A basis outside the five is shown plainly as it came, with no glyph. */
export const UnknownBasis = () => (
  <div style={row}>
    <BasisPill basis="board resolution" />
    <BasisPill basis="" />
  </div>
);
