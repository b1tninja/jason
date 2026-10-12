import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Badge } from "../components";
import { Glyph } from "../components/Glyph";
import {
  filtersOn, kindWord, libraryFiles, NO_QUERY, SORT_WORDS, sourceWord,
  type LibraryAnswer, type LibraryFile, type LibraryQuery, type LibrarySort, type TextFilter,
} from "./libraryModel";
import { busyOf, type Busy } from "./splitApi";
import { BusyNotice } from "./splitNotices";
import { sizeText, splitRoute } from "./splitModel";

type Fetcher = (q: LibraryQuery, page?: string) => Promise<LibraryAnswer>;

/** The words for one place a file came from, with its count: "PayHOA (12)". */
function chipText(label: string, n: number): string { return `${label} (${n})`; }

/** The library explorer (docs/pdf-splitter.md, "Choosing a file from the library"): search by name, chips for kind and source with
 * their counts, a sortable list that fills 50 files at a time, and one file chosen with a radio button (so the keyboard, a screen reader,
 * and a thumb all choose it the same way). It reads the library on this machine through `POST /api/write/library/files`, so a name
 * searched for is never in a web address. Choosing opens nothing: the parent checks the file, then opens it. */
export function LibraryBrowser({ selectedId, onSelect, fetcher = libraryFiles }: {
  selectedId: string; onSelect: (f: LibraryFile) => void; fetcher?: Fetcher;
}) {
  const id = useId();
  const [applied, setApplied] = useState<LibraryQuery>(NO_QUERY);
  const [form, setForm] = useState({ q: "", minPages: "", since: "", until: "" });
  const [rows, setRows] = useState<LibraryFile[]>([]);
  const [answer, setAnswer] = useState<LibraryAnswer | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  // the library could not be read just now (a 503 with Retry-After): nothing was changed, and Try again asks the same question again
  const [wait, setWait] = useState<{ note: Busy; q: LibraryQuery; page: string; n: number } | null>(null);
  const [said, setSaid] = useState("");
  const ticket = useRef(0);

  const load = useCallback(async (q: LibraryQuery, page = "") => {
    const mine = ++ticket.current;            // an answer that arrives after a newer question is dropped
    setBusy(true); setError(""); setWait(null);
    try {
      const a = await fetcher(q, page);
      if (mine !== ticket.current) return;
      setAnswer(a);
      setRows((prev) => (page ? [...prev, ...(a.files ?? [])] : a.files ?? []));
      if (a.found) setSaid(`${a.total} ${a.total === 1 ? "file" : "files"}${page ? ", more shown" : ""}`);
    } catch (e) {
      const b = busyOf(e);
      if (mine === ticket.current && b) { setWait((was) => ({ note: b, q, page, n: (was?.n ?? 0) + 1 })); setAnswer(null); setRows([]); }
      else if (mine === ticket.current) { setError((e as Error).message); setAnswer(null); setRows([]); }
    } finally {
      if (mine === ticket.current) setBusy(false);
    }
  }, [fetcher]);

  useEffect(() => { void load(NO_QUERY); }, [load]);

  const ask = (next: LibraryQuery) => { setApplied(next); void load(next); };
  const apply = () => ask({ ...applied, q: form.q, minPages: form.minPages, since: form.since, until: form.until });
  const clear = () => { setForm({ q: "", minPages: "", since: "", until: "" }); ask({ ...NO_QUERY, sort: applied.sort, order: applied.order }); };
  const chip = (field: "kind" | "source", value: string) => ask({ ...applied, [field]: applied[field] === value ? "" : value });

  const counts = answer?.counts;
  const on = filtersOn(applied);
  const kinds = Object.entries(counts?.kinds ?? {});
  const sources = Object.entries(counts?.sources ?? {});
  const labelOfSource = (key: string) => rows.find((r) => r.source === key)?.sourceLabel ?? sourceWord(key);

  return (
    <div className="lib-browser">
      <form role="search" aria-label="Search the library" className="lib-search" onSubmit={(e) => { e.preventDefault(); apply(); }}>
        <label htmlFor={`${id}-q`}>Search by file name</label>
        <div className="row wrap">
          <input id={`${id}-q`} type="search" value={form.q} maxLength={100} onChange={(e) => setForm({ ...form, q: e.target.value })} autoComplete="off" />
          <button type="submit" disabled={busy}>Search</button>
          {on > 0 && <button type="button" onClick={clear}>Clear {on === 1 ? "the filter" : `${on} filters`}</button>}
        </div>
        <details className="lib-more">
          <summary>More filters</summary>
          <div className="lib-more-body">
            <div className="split-field"><label htmlFor={`${id}-pg`}>Smallest page count</label>
              <input id={`${id}-pg`} type="number" min={1} inputMode="numeric" value={form.minPages} onChange={(e) => setForm({ ...form, minPages: e.target.value })} /></div>
            <div className="split-field"><label htmlFor={`${id}-s`}>Changed on or after</label>
              <input id={`${id}-s`} type="date" value={form.since} onChange={(e) => setForm({ ...form, since: e.target.value })} /></div>
            <div className="split-field"><label htmlFor={`${id}-u`}>Changed on or before</label>
              <input id={`${id}-u`} type="date" value={form.until} onChange={(e) => setForm({ ...form, until: e.target.value })} /></div>
            <p className="muted">These apply when you press Search. The name you type goes to jason in a request body and never sits in a web address.</p>
          </div>
        </details>
      </form>

      <div role="group" aria-label="Kind of document" className="lib-chips">
        <button type="button" aria-pressed={!applied.kind} onClick={() => ask({ ...applied, kind: "" })}>{chipText("All kinds", Object.values(counts?.kinds ?? {}).reduce((a, b) => a + b, 0))}</button>
        {kinds.map(([k, n]) => (
          <button key={k} type="button" aria-pressed={applied.kind === k} onClick={() => chip("kind", k)}>{chipText(kindWord(k), n)}</button>
        ))}
      </div>
      <div role="group" aria-label="Where the file came from" className="lib-chips">
        <button type="button" aria-pressed={!applied.source} onClick={() => ask({ ...applied, source: "" })}>All sources</button>
        {sources.map(([k, n]) => (
          <button key={k} type="button" aria-pressed={applied.source === k} onClick={() => chip("source", k)}>{chipText(labelOfSource(k), n)}</button>
        ))}
      </div>

      <div className="row wrap lib-tools">
        <div className="split-field"><label htmlFor={`${id}-t`}>Text</label>
          <select id={`${id}-t`} value={applied.text} onChange={(e) => ask({ ...applied, text: e.target.value as TextFilter })}>
            <option value="">Any</option><option value="yes">jason holds its text</option><option value="no">no text held{counts ? ` (${counts.noText})` : ""}</option>
          </select></div>
        <div className="split-field"><label htmlFor={`${id}-d`}>Drafts</label>
          <select id={`${id}-d`} value={applied.draft} onChange={(e) => ask({ ...applied, draft: e.target.value as "" | "yes" | "no" })}>
            <option value="">Any</option><option value="yes">has a draft{counts ? ` (${counts.withDraft})` : ""}</option><option value="no">no draft</option>
          </select></div>
        <div className="split-field"><label htmlFor={`${id}-o`}>Sort by</label>
          <select id={`${id}-o`} value={applied.sort} onChange={(e) => ask({ ...applied, sort: e.target.value as LibrarySort, order: "" })}>
            {(Object.keys(SORT_WORDS) as LibrarySort[]).map((s) => <option key={s} value={s}>{SORT_WORDS[s]}</option>)}
          </select></div>
        <button type="button" aria-label={`${answer?.order === "asc" ? "Ascending" : "Descending"}: ${answer?.order === "asc" ? "smallest or earliest first" : "largest or latest first"}. Press to reverse the order`}
          onClick={() => ask({ ...applied, order: (answer?.order ?? "desc") === "asc" ? "desc" : "asc" })} disabled={busy}>{answer?.order === "asc" ? "Ascending" : "Descending"}</button>
      </div>

      <div className="sr-only" role="status" aria-live="polite">{said}</div>
      {busy && rows.length === 0 && <p className="muted" role="status">Reading the library</p>}
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {wait && <BusyNotice busy={wait.note} again={wait.n} working={busy} onRetry={() => void load(wait.q, wait.page)} />}
      {answer && !answer.found && (
        <div className="notice notice-warn" role="alert">
          <p>{answer.why ?? "The library could not be listed."}</p>
          {answer.command && <p>A person runs <code>{answer.command}</code> in a terminal. The other two tabs still work.</p>}
        </div>
      )}
      {answer?.found && (
        <>
          <p className="muted lib-count" data-testid="lib-count">
            {answer.total === 0 ? "No files" : `${rows.length} of ${answer.total} ${answer.total === 1 ? "file" : "files"} shown`}
            {answer.uncounted > 0 ? `. ${answer.uncounted} files have no page count yet and are left out of a pages filter or sort` : ""}.
          </p>
          {rows.length > 0 ? (
            <div className="split-table-wrap lib-table-wrap">
              <table className="lib-table">
                <caption className="sr-only">Files in the library. Choose one to split.</caption>
                <thead><tr><th scope="col">File</th><th scope="col">Kind</th><th scope="col">Pages</th><th scope="col">Size</th><th scope="col">Changed</th><th scope="col">Text</th><th scope="col">Draft</th></tr></thead>
                <tbody>
                  {rows.map((f, i) => {
                    const rid = `${id}-r${i}`;
                    const chosen = !!f.id && f.id === selectedId;
                    return (
                      <tr key={`${f.id || "held"}-${i}`} data-file={f.id || undefined} data-selected={chosen ? "" : undefined} data-off={f.openable ? undefined : ""}
                          onClick={(e) => { if (f.openable && !(e.target as HTMLElement).closest("a, input, label")) onSelect(f); }}>
                        <th scope="row" data-label="File">
                          <input type="radio" id={rid} name={`${id}-pick`} checked={chosen} disabled={!f.openable} onChange={() => onSelect(f)} />{" "}
                          <label htmlFor={rid}>
                            <span className="lib-name">{f.name}</span>{" "}
                            <span className="muted">{f.sourceLabel}{f.copies > 1 ? `, filed ${f.copies} times` : ""}</span>
                          </label>
                          {chosen && <span className="record-selected"> selected</span>}
                          {(f.why || f.opens) && <p className="muted lib-why">{f.opens || f.why}</p>}
                        </th>
                        <td data-label="Kind">{kindWord(f.kind)}{f.held && <> <Badge tone="warn" glyph="file-lock">confidential</Badge></>}</td>
                        <td data-label="Pages">{f.pages ?? "unknown"}</td>
                        <td data-label="Size">{f.size === null ? "unknown" : sizeText(f.size)}</td>
                        <td data-label="Changed">{f.modified || "unknown"}</td>
                        <td data-label="Text">{f.hasText ? <span className="lib-text"><Glyph name="file-text" size="1em" /> text held</span> : <span className="muted">no text held</span>}</td>
                        <td data-label="Draft">{f.draft
                          ? <><Badge tone="neutral" glyph="pencil">draft exists</Badge> <a href={splitRoute(f.draft.id)} aria-label={`Continue the ${f.draft.status} draft of ${f.name}`}>continue ({f.draft.status})</a></>
                          : <span className="muted">none</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : <p className="muted">{answer.empty}</p>}
          {answer.next && <button type="button" onClick={() => void load(applied, answer.next ?? "")} disabled={busy}>Show 50 more</button>}
          {(answer.caveats ?? []).length > 0 && <ul className="muted lib-caveats">{answer.caveats!.map((c) => <li key={c}>{c}</li>)}</ul>}
        </>
      )}
    </div>
  );
}
