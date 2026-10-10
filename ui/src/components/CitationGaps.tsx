import { Caveats } from "./Caveats";
import { Command } from "./Command";
import { DataTable, type Column } from "./DataTable";
import { Proposal } from "./CitedSections";
import { Stat } from "./Stat";
import { StandingPill } from "./StandingPill";
import { EmptyState } from "./States";
import { STANDINGS, rank, type CitationRow, type GapsData } from "../lib/citations";

/** What every surveyed source cites that the shelf lacks, together: the sections, who cites each and how often, the one
 * proposal a person copies, and how many sections a survey left unchecked. A section the shelf holds now is not listed. */
export function CitationGaps({ data, onOpenWork }: { data: GapsData; onOpenWork?: (source: string) => void }) {
  const rows = [...data.gaps].sort((a, b) => rank(a.standing) - rank(b.standing) || a.citation.localeCompare(b.citation, undefined, { numeric: true }));
  const columns: Column<CitationRow>[] = [
    { key: "citation", header: "Section" },
    { key: "standing", header: "Standing", value: (r) => STANDINGS[r.standing]?.word ?? r.standing, render: (r) => <StandingPill standing={r.standing} /> },
    {
      key: "citedBy", header: "Cited by", value: (r) => r.citedBy.join("; "),
      render: (r) => (
        <span>
          {r.citedBy.map((s, i) => (
            <span key={s}>{i > 0 && "; "}{onOpenWork ? <button className="linklike" onClick={() => onOpenWork(s)}>{s}</button> : s}</span>
          ))}
        </span>
      ),
    },
    { key: "mentions", header: "Cited", align: "right", value: (r) => r.mentions, render: (r) => <span className="num">{r.mentions}</span> },
    { key: "page", header: "Page", align: "right", value: (r) => Number(r.page) || 0, render: (r) => <span className="num">{r.page}</span> },
    { key: "quote", header: "The sentence", render: (r) => <span className="muted">{r.quote}</span> },
  ];
  return (
    <div className="stack">
      <div className="stats">
        <Stat label="Gaps" value={data.total} hint="not exported, not found, or renumbered" />
        <Stat label="Unchecked" value={data.unchecked} hint="the survey did not ask lawlibrary" />
        <Stat label="Surveys" value={data.surveys.length} hint="reference works and ingests" />
      </div>
      {data.unchecked > 0 && (
        <div>
          <p className="muted">{data.unchecked} sections are off the shelf and were not asked of lawlibrary. Ask it with:</p>
          <Command cmd="jason reference --cites WORK" note="Names a reference work's file. An ingest asks lawlibrary unless it was run with --no-law." />
        </div>
      )}
      <Proposal text={data.proposal} />
      {rows.length ? <DataTable rows={rows} columns={columns} rowKey={(r) => r.citation} caption="Sections cited and not on the shelf" /> : <EmptyState>No gap: every section the surveyed sources cite is on the shelf or is not a lead.</EmptyState>}
      {data.total > data.shown && <p className="muted">{data.shown} of {data.total} shown.</p>}
      <details>
        <summary>{data.surveys.length} surveys behind this list</summary>
        <ul>
          {data.surveys.map((s) => (
            <li key={`${s.kind}:${s.name}`}>{s.name} <span className="muted">({s.kind}; {s.made ?? "undated"}; {s.lawChecked ? "lawlibrary asked" : "lawlibrary not asked"})</span></li>
          ))}
        </ul>
      </details>
      <Caveats items={data.caveats} />
    </div>
  );
}
