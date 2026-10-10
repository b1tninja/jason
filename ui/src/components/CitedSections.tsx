import { useMemo, useState } from "react";
import { Caveats } from "./Caveats";
import { Command } from "./Command";
import { DataTable, type Column } from "./DataTable";
import { StandingPill, StandingStrip } from "./StandingPill";
import { STANDINGS, STANDING_ORDER, rank, type CitationRow, type CitationsData, type Standing } from "../lib/citations";

/** What to add to the shelf, as a duty's `sections` string. A person copies it into the specification's authority list;
 * jason adds nothing, and the page says who does and where. */
export function Proposal({ text }: { text: string }) {
  if (!text) return null;
  return (
    <div className="proposal" role="group" aria-label="Sections to add to the shelf">
      <p>
        The shelf lacks these sections. A person adds the row in <code>jason.community.authorities</code>, with a reason; jason
        adds nothing. A gap is a lead, not a finding.
      </p>
      <Command cmd={text} note="The sections as a duty's sections string. Copy it; nothing here writes." />
    </div>
  );
}

/** How the list was made, in words: when, and whether lawlibrary was asked. */
export function Freshness({ made, lawChecked, report }: { made?: string | null; lawChecked: boolean; report?: string }) {
  const when = made ? ` ${made}` : report ? ` (${report})` : "";
  return (
    <p className="muted">
      {lawChecked ? `Looked up in lawlibrary${when}.` : `Not looked up in lawlibrary${when}: placed against the shelf only.`}{" "}
      Each section is placed against the shelf as it is now.
    </p>
  );
}

/** One source's cited sections, the gaps first: a standing strip, a filter by standing, and a table with each section's page
 * and sentence. `onOpenPage` makes the page a button (a reference work's reader); without it the page is text. */
export function CitedSections({ data, onOpenPage }: { data: CitationsData; onOpenPage?: (page: number, row: CitationRow) => void }) {
  const [only, setOnly] = useState<"" | "gaps" | Standing>("");
  const rows = useMemo(
    () => [...data.sections].sort((a, b) => rank(a.standing) - rank(b.standing) || a.citation.localeCompare(b.citation, undefined, { numeric: true })),
    [data.sections],
  );
  const shown = rows.filter((r) => (only === "" ? true : only === "gaps" ? STANDINGS[r.standing]?.gap : r.standing === only));
  const present = STANDING_ORDER.filter((s) => (data.counts[s] ?? 0) > 0);

  const columns: Column<CitationRow>[] = [
    { key: "citation", header: "Section", render: (r) => <span>{r.citation}{r.subdivisions.length ? <span className="muted"> {r.subdivisions.join(", ")}</span> : null}</span> },
    { key: "standing", header: "Standing", value: (r) => STANDINGS[r.standing]?.word ?? r.standing, render: (r) => <StandingPill standing={r.standing} /> },
    {
      key: "page", header: "Page", align: "right",
      value: (r) => Number(r.page) || 0,
      render: (r) => (r.page && onOpenPage ? <button onClick={() => onOpenPage(Number(r.page), r)} aria-label={`Open page ${r.page} for ${r.citation}`}>p. {r.page}</button> : <span className="num">{r.page || ""}</span>),
    },
    { key: "mentions", header: "Cited", align: "right", value: (r) => r.mentions, render: (r) => <span className="num">{r.mentions}</span> },
    { key: "citedBy", header: "Cited by", value: (r) => r.citedBy.join("; "), render: (r) => <span>{r.citedBy.join("; ")}</span> },
    { key: "quote", header: "The sentence", render: (r) => <span className="muted">{r.quote}</span> },
  ];

  return (
    <div className="stack">
      <Freshness made={data.made} lawChecked={data.lawChecked} report={data.report} />
      <StandingStrip counts={data.counts} />
      <Proposal text={data.proposal} />
      {rows.length > 0 && (
        <>
          <label className="row">
            <span>Show</span>
            <select value={only} onChange={(e) => setOnly(e.target.value as typeof only)}>
              <option value="">all sections</option>
              <option value="gaps">gaps only</option>
              {present.map((s) => <option key={s} value={s}>{STANDINGS[s].word}</option>)}
            </select>
          </label>
          <p role="status" className="muted">{shown.length} of {rows.length} sections</p>
          <DataTable rows={shown} columns={columns} rowKey={(r) => r.citation} caption="Cited sections" />
        </>
      )}
      {data.total > data.shown && <p className="muted">{data.shown} of {data.total} shown: the rest are in the tool.</p>}
      {data.notes.length > 0 && <ul>{data.notes.map((n, i) => <li key={i} className="muted">{n}</li>)}</ul>}
      <Caveats items={data.caveats} />
    </div>
  );
}
