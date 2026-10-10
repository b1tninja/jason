import { CitationGaps } from "jason-ui";
import type { CitationRow, GapsData } from "jason-ui";

const GUIDE = "A Guide to Understanding Residential Subdivisions in California";
const row = (citation: string, standing: CitationRow["standing"], extra: Partial<CitationRow> = {}): CitationRow => ({
  citation, standing, meaning: "", mentions: 1, citedBy: [GUIDE], page: "", subdivisions: [], quote: "", ...extra,
});

const caveats = [
  "Citations are read by a grammar: a range is read as its two ends, a citation the grammar misses stays missed.",
  "A gap is a lead for a person, who adds the row; jason adds nothing.",
];

const gaps: GapsData = {
  found: true,
  surveys: [
    { name: GUIDE, kind: "reference", made: "2026-10-03", lawChecked: true },
    { name: "ingest", kind: "ingest", made: "2026-10-03", lawChecked: false },
  ],
  total: 5, shown: 5, unchecked: 2, proposal: "BPC 11500, 11502; CCP 726.5; GOV 66427",
  gaps: [
    row("BPC 11001.1", "NOT_FOUND", { page: "60", quote: "the Map Act is an “undivided interest” subdivision as defined in BPC Section 11001.1 of the SLA." }),
    row("GOV 66427", "NOT_EXPORTED", { citedBy: [GUIDE, "notice-example.pdf"], mentions: 4, page: "62", quote: "Government Code Section 66427 allows the local agency to approve a condominium project's map." }),
    row("BPC 11500", "NOT_EXPORTED", { page: "90", quote: "Sections 10131.01, 10153.2, 10177, 11500, 11502 of the Business and Professions Code were amended." }),
    row("CCP 726.5", "NOT_EXPORTED", { page: "90", quote: "Sections 86, 116.540, 564, 726.5, 729.035, and 736 of the Code of Civil Procedure." }),
    row("CIV 1351", "RENUMBERED", { page: "62", quote: "SLA defines planned development by reference to Section 1351(k) of the DSA." }),
  ],
  caveats,
};

/** Everything the surveyed sources cite that the shelf lacks, together: the counts, the one proposal a person copies, who cites each section, and the surveys behind the list. */
export const WithGaps = () => <CitationGaps data={gaps} onOpenWork={() => {}} />;

/** Nothing the surveyed sources cite is a gap: said plainly, with no proposal. */
export const NoGap = () => <CitationGaps data={{ ...gaps, total: 0, shown: 0, gaps: [], proposal: "", unchecked: 0 }} />;
