import { CitedSections, Freshness, Proposal } from "jason-ui";
import type { CitationRow, CitationsData } from "jason-ui";

const GUIDE = "A Guide to Understanding Residential Subdivisions in California";
const row = (citation: string, standing: CitationRow["standing"], extra: Partial<CitationRow> = {}): CitationRow => ({
  citation, standing, meaning: "", mentions: 1, citedBy: [GUIDE], page: "", subdivisions: [], quote: "", ...extra,
});

const guideRows: CitationRow[] = [
  row("BPC 11001.1", "NOT_FOUND", { page: "60", quote: "the Map Act is an “undivided interest” subdivision as defined in BPC Section 11001.1 of the SLA." }),
  row("BPC 11500", "NOT_EXPORTED", { page: "90", quote: "Sections 10131.01, 10153.2, 10177, 11003, 11003.2, 11004, 11500, 11502 of the Business and Professions Code were amended." }),
  row("GOV 66427", "NOT_EXPORTED", { page: "62", mentions: 3, subdivisions: ["(b)", "(e)"], quote: "Government Code Section 66427 allows the local agency to approve a condominium project's map without reviewing its condominium plan." }),
  row("CIV 1351", "RENUMBERED", { page: "62", subdivisions: ["(k)"], quote: "SLA defines planned development by reference to Section 1351(k) of the DSA (Civil Code Section 4175), which says:" }),
  row("10 CCR 2792.9", "ON_SHELF", { page: "65", mentions: 2, quote: "DRE regulations (specifically Regulation 2792.9) require a subdivider to assure the availability of funds." }),
  row("BPC 11018.5", "ON_SHELF", { page: "62", quote: "The scope of the application review process is found in BPC Section 11018.5 of the SLA." }),
  row("CIV 4175", "ON_SHELF", { page: "50", quote: "Planned development means a real property development having either or both of the following features." }),
  row("10 CCR 2790", "REGULATION", { page: "58", quote: "Article 12 addresses subdivisions in Sections 2790-2804." }),
];

const guide: CitationsData = {
  found: true, source: GUIDE, made: "2026-10-03", lawChecked: true,
  counts: { NOT_FOUND: 1, NOT_EXPORTED: 2, RENUMBERED: 1, ON_SHELF: 3, REGULATION: 1 },
  total: 8, shown: 8, sections: guideRows, proposal: "BPC 11500; GOV 66427", notes: [],
  caveats: [
    "Citations are read by a grammar: a range is read as its two ends, a citation the grammar misses stays missed, and a document is never said to cite nothing else.",
    "A reference work explains a process. It is not the law and not the association's record: quote a section from the authorities shelf, never from the work.",
  ],
};

const ingest: CitationsData = {
  found: true, source: "ingest", report: "ingest-2026-10-03.json", lawChecked: true,
  counts: { ON_SHELF: 2, NOT_EXPORTED: 1, RENUMBERED: 1 }, total: 4, shown: 4, proposal: "GOV 66427", notes: [],
  sections: [
    row("GOV 66427", "NOT_EXPORTED", { citedBy: ["notice-example.pdf", "letter-example.pdf"], mentions: 2, quote: "Under Government Code Section 66427 a notice of the change is given." }),
    row("CIV 1351", "RENUMBERED", { citedBy: ["notice-example.pdf"], quote: "See also Civil Code Section 1351." }),
    row("CIV 5650", "ON_SHELF", { citedBy: ["notice-example.pdf"], quote: "Pursuant to Civil Code Section 5650 the association may record a lien." }),
    row("CIV 4920", "ON_SHELF", { citedBy: ["agenda-example.pdf"], quote: "Notice of the meeting is given under Civil Code Section 4920." }),
  ],
  caveats: ["An ingest report names the association's files: it is private."],
};

/** A reference work's citations after a survey that asked lawlibrary: the gaps first (not found, not exported, renumbered), then what is on the shelf; the proposal is a string a person copies, never a button. A page opens the reader. */
export const ReferenceWork = () => <CitedSections data={guide} onOpenPage={() => {}} />;

/** The files of an ingest: the same list with the files that cite each section in place of pages. */
export const IngestedFiles = () => <CitedSections data={ingest} />;

/** A survey that did not ask lawlibrary: the freshness line says so, and a section off the shelf reads "unchecked", not missing. */
export const NotLookedUp = () => (
  <CitedSections
    data={{
      ...ingest, lawChecked: false, report: undefined, made: null,
      counts: { ON_SHELF: 2, UNCHECKED: 2 }, proposal: "",
      sections: ingest.sections.map((s) => (s.standing === "NOT_EXPORTED" || s.standing === "RENUMBERED" ? { ...s, standing: "UNCHECKED" as const } : s)),
    }}
  />
);

/** The proposal on its own: sections the shelf lacks, as a duty's `sections` string. */
export const ProposalOnly = () => <Proposal text="BPC 10000, 11500, 11502; CCP 726.5; CIV 1675; GOV 66427" />;

/** How a list was made, in words. */
export const FreshnessLines = () => (
  <div style={{ display: "grid", gap: 4 }}>
    <Freshness made="2026-10-03" lawChecked />
    <Freshness lawChecked={false} report="ingest-2026-10-03.json" />
  </div>
);
