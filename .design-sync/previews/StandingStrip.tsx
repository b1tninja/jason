import { StandingStrip } from "jason-ui";

/** The counts for a reference work's citations: the bar is decoration, the list says every number in words. */
export const Guide = () => (
  <StandingStrip counts={{ ON_SHELF: 48, NOT_EXPORTED: 28, REGULATION: 18, RENUMBERED: 6, NOT_FOUND: 1 }} />
);

/** A survey that did not ask lawlibrary: most sections are off the shelf and unchecked, which reads as "not asked yet". */
export const MostlyUnchecked = () => (
  <StandingStrip counts={{ ON_SHELF: 33, UNCHECKED: 28, REGULATION: 2, RENUMBERED: 3 }} label="Sections cited by an ingested file, by standing" />
);

/** Every section the document cites is on the shelf. */
export const AllOnShelf = () => <StandingStrip counts={{ ON_SHELF: 12 }} />;

/** A document that cites no statute says so, in words, not an empty bar. */
export const NoneCited = () => <StandingStrip counts={{}} />;
