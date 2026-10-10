import { Badge } from "./Badge";
import { Caveats } from "./Caveats";
import { Command } from "./Command";
import { StandingStrip } from "./StandingPill";
import type { ReferenceWork, WorksData } from "../lib/citations";

/** One published guide on the reference shelf. How far to trust it is always open: a work is an explanation, and where it
 * is out of date is the first thing a reader needs. The survey is dated and says whether lawlibrary was asked. */
export function WorkCard({ work, selected, onRead }: { work: ReferenceWork; selected?: boolean; onRead?: (file: string) => void }) {
  return (
    <li className={selected ? "work-card selected" : "work-card"} aria-label={work.title}>
      <h3>{work.title}</h3>
      <p className="muted">
        {work.author} · {work.publisher} · {work.year}
        {work.pages ? ` · ${work.pages} pages` : ""}
      </p>
      <p><strong>How far to trust it.</strong> {work.caveat}</p>
      <p className="muted">{work.covers}</p>
      <p>
        <Badge tone={work.onDisk ? "good" : "warn"}>{work.onDisk ? "on disk" : "not on disk"}</Badge>{" "}
        <span className="muted">
          {work.surveyed ? `Citations surveyed ${work.surveyed}; ${work.lawChecked ? "lawlibrary asked" : "lawlibrary not asked"}.` : "Citations not surveyed yet."}
        </span>
      </p>
      {work.counts && <StandingStrip counts={work.counts} label={`Sections cited by ${work.title}, by standing`} />}
      {!work.onDisk && <Command cmd="jason reference --fetch" note="Downloads the works not on disk, with their text. The page never runs it." />}
      {work.onDisk && work.command && <Command cmd={work.command} note="Reads the statutes the work cites and keeps the survey. The page never runs it." />}
      <p className="row">
        {onRead && work.onDisk && (
          <button onClick={() => onRead(work.file)} aria-pressed={selected} aria-label={`Read the citations in ${work.title}`}>Read its citations</button>
        )}
        <a href={work.url} target="_blank" rel="noreferrer">Open the original</a>
      </p>
    </li>
  );
}

/** The works on the shelf. A reference work is not the law and not the association's record. */
export function ReferenceShelf({ data, selected, onRead }: { data: WorksData; selected?: string; onRead?: (file: string) => void }) {
  return (
    <div className="stack">
      <ul className="work-list">
        {data.works.map((w) => <WorkCard key={w.file} work={w} selected={w.file === selected} onRead={onRead} />)}
      </ul>
      <Caveats items={data.caveats} />
    </div>
  );
}
