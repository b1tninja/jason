import { CitationChip } from "jason-ui";

/** A statute named in running text, with whether jason holds its words: the standing is its word, as it is everywhere. */
export const InASentence = () => (
  <p style={{ maxWidth: 560, lineHeight: 1.9, margin: 0 }}>
    The association may record a lien under <CitationChip citation="CIV 5650" standing="ON_SHELF" />, after notice under{" "}
    <CitationChip citation="CIV 5660" standing="ON_SHELF" />. The subdivider's bond is read under{" "}
    <CitationChip citation="10 CCR 2792.9" standing="ON_SHELF" /> and the map under <CitationChip citation="GOV 66427" standing="NOT_EXPORTED" />;
    an older document cites <CitationChip citation="CIV 1351" standing="RENUMBERED" />.
  </p>
);

/** Each standing a chip can carry. */
export const EachStanding = () => (
  <div style={{ display: "grid", gap: 8, justifyItems: "start" }}>
    <CitationChip citation="CIV 5650" standing="ON_SHELF" />
    <CitationChip citation="GOV 66427" standing="NOT_EXPORTED" />
    <CitationChip citation="BPC 11001.1" standing="NOT_FOUND" />
    <CitationChip citation="CIV 1351" standing="RENUMBERED" />
    <CitationChip citation="10 CCR 2790" standing="REGULATION" />
    <CitationChip citation="CFC 901.6" standing="OTHER_CODE" />
    <CitationChip citation="HSC 18214" standing="UNCHECKED" />
  </div>
);
