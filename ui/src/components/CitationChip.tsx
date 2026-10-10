import { StandingPill } from "./StandingPill";
import type { Standing } from "../lib/citations";

/** A statute named in running text, with whether jason holds its words. The standing is its word, as everywhere. The hover
 * card the design handoff describes (the section's words from the shelf, the proposal for a gap) is the design's to decide. */
export function CitationChip({ citation, standing }: { citation: string; standing: Standing | string }) {
  return (
    <span className="citation-chip">
      <span>{citation}</span> <StandingPill standing={standing} />
    </span>
  );
}
