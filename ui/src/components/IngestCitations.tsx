import { CitedSections } from "./CitedSections";
import { DataTable, type Column } from "./DataTable";
import { perFile, type CitationsData } from "../lib/citations";

/** What the files of the last ingest cite: how many sections each file names and how many of them are gaps, then the
 * sections themselves. The rows name the association's files, so this appears only where the ingestion screen does. */
export function IngestCitations({ data }: { data: CitationsData }) {
  const files = perFile(data.sections);
  const columns: Column<(typeof files)[number]>[] = [
    { key: "file", header: "File" },
    { key: "sections", header: "Sections cited", align: "right", render: (r) => <span className="num">{r.sections}</span> },
    { key: "gaps", header: "Gaps", align: "right", value: (r) => r.gaps, render: (r) => <span className="num">{r.gaps}</span> },
  ];
  return (
    <div className="stack">
      <p className="muted">This list names the association's files: it is private, like the ingest report it comes from.</p>
      {files.length > 0 && <DataTable rows={files} columns={columns} rowKey={(r) => r.file} caption="Sections cited by each file" />}
      <CitedSections data={data} />
    </div>
  );
}
