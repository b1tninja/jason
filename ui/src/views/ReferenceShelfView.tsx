import { useState } from "react";
import { Card, CitationGaps, CitedSections, Command, EmptyState, ReferenceShelf, RemoteView, Tabs, WorkReader } from "../components";
import type { CitationsData, GapsData, WorksData } from "../components";
import { useApi } from "../lib/useApi";

/** The gaps: what surveyed sources cite that the authorities shelf lacks. With no survey yet, the commands that make one. */
function GapsPanel({ onOpenWork }: { onOpenWork: (source: string) => void }) {
  const r = useApi<GapsData>("/api/citation-gaps");
  if (r.status === "ready" && r.data.found === false) {
    return (
      <div className="stack">
        <EmptyState>{r.data.note ?? "No citation survey yet."}</EmptyState>
        <Command cmd="jason reference --cites ResidentialSubdivisionsGuide.pdf" note="Surveys a reference work's citations against the shelf and lawlibrary. The page never runs it." />
        <Command cmd="jason ingest SOURCE" note="An ingest surveys every file it reads, and asks lawlibrary unless it is run with --no-law." />
      </div>
    );
  }
  return <RemoteView r={r}>{(d) => <CitationGaps data={d} onOpenWork={onOpenWork} />}</RemoteView>;
}

/** One work's citations beside its page: a citation's page opens the page with its sentence marked. */
function WorkPanel({ file }: { file: string }) {
  const r = useApi<CitationsData>(`/api/citations?source=${encodeURIComponent(file)}&limit=500`);
  const [reader, setReader] = useState<{ page: number; sentence?: string } | null>(null);
  return (
    <div className="stack">
      <RemoteView r={r}>{(d) => <CitedSections data={d} onOpenPage={(page, row) => setReader({ page, sentence: row.quote })} />}</RemoteView>
      {reader && (
        <Card title="Page" actions={<button onClick={() => setReader(null)}>Close the page</button>}>
          <WorkReader work={file} page={reader.page} sentence={reader.sentence} onPage={(page) => setReader({ page })} />
        </Card>
      )}
    </div>
  );
}

function WorksPanel({ chosen, onChoose }: { chosen: string; onChoose: (file: string) => void }) {
  const r = useApi<WorksData>("/api/reference-works");
  return (
    <div className="stack">
      <RemoteView r={r}>{(d) => <ReferenceShelf data={d} selected={chosen} onRead={onChoose} />}</RemoteView>
      {chosen && (
        <Card title="What it cites">
          <WorkPanel key={chosen} file={chosen} />
        </Card>
      )}
    </div>
  );
}

/** The reference shelf and the statutes the surveyed documents cite. Reading only: a survey is a command a person runs, and
 * adding a section to the shelf is a person's edit. A reference work is an explanation, not the law. */
export function ReferenceShelfView() {
  const [tab, setTab] = useState("gaps");
  const [chosen, setChosen] = useState("");
  const open = (file: string) => {
    setChosen(file);
    setTab("works");
  };
  return (
    <div className="stack">
      <p className="muted">
        Published guides that explain a process, and the statutes the documents jason reads cite. A guide is not the law and not the
        association's record: a section's words come from the authorities shelf.
      </p>
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "gaps", label: "Citation gaps", content: <GapsPanel onOpenWork={open} /> },
          { id: "works", label: "Reference works", content: <WorksPanel chosen={chosen} onChoose={open} /> },
        ]}
      />
    </div>
  );
}
