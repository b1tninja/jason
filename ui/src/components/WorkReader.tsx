import { Fragment, type ReactNode } from "react";
import { RemoteView } from "./Remote";
import { Command } from "./Command";
import { useApi } from "../lib/useApi";
import type { ReferencePageData } from "../lib/citations";

/** The sentence a citation was read from, found in the page's text (the sentence is whitespace-folded, the page is not), and
 * marked: the first match only. A sentence the page does not hold is not marked. */
export function marked(text: string, sentence?: string): ReactNode {
  const words = (sentence ?? "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return text;
  const pattern = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  const hit = new RegExp(pattern).exec(text);
  if (!hit) return text;
  return (
    <Fragment>
      {text.slice(0, hit.index)}
      <mark>{hit[0]}</mark>
      {text.slice(hit.index + hit[0].length)}
    </Fragment>
  );
}

/** One page of a reference work's text. The banner and the work's own caveat are on every page: the page is an explanation,
 * never the law's words. `page` counts PDF pages. */
export function ReferencePage({ data, sentence, onPage }: { data: ReferencePageData; sentence?: string; onPage?: (page: number) => void }) {
  const page = data.page ?? 1;
  const pages = data.pages ?? page;
  return (
    <section className="work-reader" aria-label={`${data.work}, page ${page}`}>
      <div className="notice" role="note">
        <strong>{data.banner}</strong> {data.caveat}
      </div>
      <h3 tabIndex={-1}>{data.work} <span className="muted">· page {page} of {pages} (PDF pages)</span></h3>
      {data.noText ? (
        <p className="muted">This page has no text layer. Open the original to read it.</p>
      ) : (
        <div className="work-page" tabIndex={0} aria-label={`Text of page ${page}`}>{marked(data.text ?? "", sentence)}</div>
      )}
      {onPage && (
        <p className="row">
          <button onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page">Previous</button>
          <span className="num" aria-live="polite">{page} of {pages}</span>
          <button onClick={() => onPage(page + 1)} disabled={page >= pages} aria-label="Next page">Next</button>
        </p>
      )}
    </section>
  );
}

/** Reads `page` of `work` and shows it. A work not on disk shows the command that brings it. */
export function WorkReader({ work, page, sentence, onPage }: { work: string; page: number; sentence?: string; onPage?: (page: number) => void }) {
  const r = useApi<ReferencePageData>(`/api/reference-page?work=${encodeURIComponent(work)}&page=${page}`);
  if (r.status === "ready" && r.data.found === false) {
    return (
      <div className="stack">
        <p className="muted">{r.data.note}</p>
        {r.data.command && <Command cmd={r.data.command} />}
      </div>
    );
  }
  return <RemoteView r={r}>{(d) => <ReferencePage data={d} sentence={sentence} onPage={onPage} />}</RemoteView>;
}
