import { IngestCitations } from "jason-ui";
import type { CitationRow, CitationsData } from "jason-ui";

const row = (citation: string, standing: CitationRow["standing"], citedBy: string[], quote: string, extra: Partial<CitationRow> = {}): CitationRow => ({
  citation, standing, meaning: "", mentions: citedBy.length, citedBy, page: "", subdivisions: [], quote, ...extra,
});

const data: CitationsData = {
  found: true, source: "ingest", report: "ingest-2026-10-03.json", lawChecked: true,
  counts: { NOT_EXPORTED: 1, RENUMBERED: 1, ON_SHELF: 3 }, total: 5, shown: 5, proposal: "GOV 66427", notes: [],
  sections: [
    row("GOV 66427", "NOT_EXPORTED", ["notice-example.pdf", "letter-example.pdf"], "Under Government Code Section 66427 a notice of the change is given."),
    row("CIV 1351", "RENUMBERED", ["notice-example.pdf"], "See also Civil Code Section 1351."),
    row("CIV 5650", "ON_SHELF", ["notice-example.pdf", "collection-policy-example.pdf"], "Pursuant to Civil Code Section 5650 the association may record a lien."),
    row("CIV 4920", "ON_SHELF", ["agenda-example.pdf"], "Notice of the meeting is given under Civil Code Section 4920."),
    row("CIV 5855", "ON_SHELF", ["collection-policy-example.pdf"], "A hearing is offered under Civil Code Section 5855."),
  ],
  caveats: ["An ingest report names the association's files: it is private."],
};

/** What the files of the last ingest cite: how many sections each file names and how many are gaps, then the sections themselves. The list names the association's files, so it appears only where the ingestion screen does. */
export const LastIngest = () => <IngestCitations data={data} />;

/** An ingest that cited nothing the survey could read. */
export const NothingCited = () => <IngestCitations data={{ ...data, counts: {}, total: 0, shown: 0, sections: [], proposal: "" }} />;
