import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Confirm } from "../components";
import type { SplitBackend } from "./splitApi";
import type { FactsCache } from "./splitFacts";
import type { ApplyAnswer, Review, ReviewPart } from "./splitModel";
import { rangeWords } from "./splitModel";
import type { ThumbLoader } from "./splitThumbs";

/** The review step (docs/pdf-splitter.md, section 5.7): the checkpoint before anything is written. Counts that must add up, the first page
 * of every part, the pages to leave out, the collisions and duplicates, then the apply as a dry run and one confirm. */

function useInView<T extends Element>(): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(typeof IntersectionObserver === "undefined");
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((es) => setSeen(es.some((e) => e.isIntersecting)), { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, seen];
}

/** A first-page picture that asks for its image only while it is on screen (an IntersectionObserver), so a review of hundreds of parts holds no more pictures than a screen. */
function LazyChip({ page, loader }: { page: number; loader: ThumbLoader }) {
  const [box, seen] = useInView<HTMLSpanElement>();
  const img = useRef<HTMLImageElement>(null);
  useEffect(() => { const el = img.current; if (seen && el) return loader.attach(el, page, ["small"]); }, [seen, loader, page]);
  return <span className="split-chip" ref={box}>{seen && <img ref={img} alt="" draggable={false} />}</span>;
}

const ACTION_WORDS: Record<string, string> = {
  held: "Kept in jason's store, not filed yet", fill: "Fills its record slot", collision: "Its slot already holds a file: kept in the store instead",
  duplicate: "Identical to a file jason has: will not be written again", filled: "Filled its slot", skip: "Skipped",
};

export function SplitReview({ backend, id, by, loader, facts, status, drop, setDrop, onBack, onDone, confidential, onRename }: {
  backend: SplitBackend; id: string; by: string; loader: ThumbLoader; facts: FactsCache; status: string; drop: number[]; setDrop(d: number[]): void;
  onBack(): void; onDone(): void; confidential: boolean; onRename(page: number, title: string): Promise<void>;
}) {
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<ApplyAnswer | null>(null);
  const [result, setResult] = useState<ApplyAnswer | null>(null);
  const [keepCopies, setKeepCopies] = useState(false);
  const [blanks, setBlanks] = useState<number[] | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const read = useCallback(async () => {
    setError(""); setPreview(null);
    try { setReview((await backend.act(id, { act: "review", drop, keepCopies })).review ?? null); }
    catch (e) { setReview(null); setError((e as Error).message); }
  }, [backend, id, drop, keepCopies]);
  useEffect(() => { void read(); }, [read]);
  useEffect(() => { heading.current?.focus(); }, [review === null]);

  const findBlanks = async () => {
    await facts.loadAll();
    const out: number[] = [];
    for (let n = 1; n <= facts.pages; n++) if (facts.get(n)?.blank === "blank") out.push(n);
    setBlanks(out);
  };

  const send = async (dry: boolean) => {
    setBusy(true); setError("");
    try {
      const a = await backend.act(id, { act: "apply", dryRun: dry, confirm: !dry, drop, keepCopies, by: by || undefined });
      if (dry) setPreview(a); else { setResult(a); onDone(); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  if (result) {
    return (
      <section className="split-review" aria-labelledby="split-review-h">
        <h2 id="split-review-h" tabIndex={-1} ref={heading}>{result.ok ? "The split was written" : "The split was partly written"}</h2>
        <p role="status">{result.ok ? "The original was not changed." : result.failed?.map((f) => `Segment ${f.segment}: ${f.why}`).join(" ")}</p>
        <ul>
          <li>{result.filled?.length ?? 0} files filled a record slot.</li>
          <li>{result.held?.length ?? 0} files are kept in jason's store for filing later.</li>
          {(result.skipped?.length ?? 0) > 0 && <li>{result.skipped!.length} were skipped: {result.skipped!.map((s) => `${s.segment} (${s.why || s.action})`).join("; ")}.</li>}
          {(result.dropped?.length ?? 0) > 0 && <li>Pages left out of every file: {result.dropped!.join(", ")}.</li>}
        </ul>
        {result.note && <p className="muted">{result.note}</p>}
        <div className="row wrap"><button type="button" onClick={onBack}>Back to the pages</button>{!result.ok && <button type="button" className="primary" disabled={busy} onClick={() => { setResult(null); void read(); }}>Review again to finish the rest</button>}</div>
      </section>
    );
  }

  const parts: ReviewPart[] = review?.parts ?? [];
  const can = !!review && review.totalsOk && status === "draft" && parts.length > 0;
  return (
    <section className="split-review" aria-labelledby="split-review-h">
      <h2 id="split-review-h" tabIndex={-1} ref={heading}>{review ? `Review: ${review.files} ${review.files === 1 ? "document" : "documents"} from ${review.sourcePages} pages` : "Review"}</h2>
      {error && <div className="notice notice-error" role="alert"><span>{error}</span></div>}
      {!review && !error && <p role="status" className="muted">Reading the draft…</p>}
      {status !== "draft" && <p className="notice notice-warn" role="note">This split is {status}; it can no longer be applied.</p>}
      {review && (
        <>
          <p className={review.totalsOk ? "" : "notice notice-warn"} role={review.totalsOk ? undefined : "alert"}>
            <Badge tone={review.totalsOk ? "good" : "bad"} glyph={review.totalsOk ? "circle-check" : "triangle-alert"}>{review.totalsOk ? "Pages add up" : "Pages do not add up"}</Badge>{" "}
            {review.pagesInFiles} pages in files + {review.dropped.length} left out = {review.pagesInFiles + review.dropped.length} of {review.sourcePages}.
          </p>
          {review.problems.map((p) => <p key={p} className="notice notice-warn" role="alert">{p}</p>)}
          <div className="split-table-wrap">
            <table className="split-review-table">
              <caption className="sr-only">The files this split would make, in page order</caption>
              <thead><tr><th scope="col">Part</th><th scope="col">First page</th><th scope="col">Pages</th><th scope="col">Title (a guess until you confirm)</th><th scope="col">What happens</th></tr></thead>
              <tbody>
                {parts.map((p) => (
                  <tr key={p.segment} data-action={p.action}>
                    <th scope="row" data-label="Part">{p.ordinal}{p.level > 0 ? " (nested)" : ""}</th>
                    <td data-label="First page"><LazyChip page={p.start} loader={loader} /></td>
                    <td data-label="Pages">{rangeWords(p.start, p.end)}</td>
                    <td data-label="Title">{confidential ? <span className="muted">hidden</span> : <ReviewTitle page={p.start} value={p.title} onCommit={onRename} onSaved={read} />}</td>
                    <td data-label="What happens">{ACTION_WORDS[p.action] ?? p.action}{p.why ? <span className="muted"> {p.why}</span> : null}{p.slot ? <span className="muted"> Slot: {p.slot}</span> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <section className="split-drops" aria-label="Pages left out">
            <h3>Pages not in any file</h3>
            {drop.length === 0 ? <p className="muted">None. Every page stays with its segment.</p> : <p>{drop.length} pages are left out of every new file: {drop.join(", ")}.</p>}
            <div className="row wrap">
              {blanks === null ? <button type="button" onClick={findBlanks}>Find the blank pages</button> : blanks.length === 0 ? <span className="muted">No blank pages were found.</span> : (
                <label className="row"><input type="checkbox" checked={blanks.every((b) => drop.includes(b))} onChange={(e) => setDrop(e.target.checked ? [...new Set([...drop, ...blanks])].sort((a, b) => a - b) : drop.filter((d) => !blanks.includes(d)))} />
                  Leave out the {blanks.length} blank pages ({blanks.slice(0, 12).join(", ")}{blanks.length > 12 ? ", …" : ""})</label>
              )}
              {drop.length > 0 && <button type="button" onClick={() => setDrop([])}>Keep every page</button>}
            </div>
          </section>
          {review.collisions.length > 0 && <p className="notice notice-warn" role="note">A slot already holds a file for: {review.collisions.join(", ")}. Those parts are kept in the store instead; nothing is replaced.</p>}
          {review.duplicates.length > 0 && (
            <p className="notice" role="note">Identical to a file jason already has: {review.duplicates.join(", ")}.{" "}
              <label><input type="checkbox" checked={keepCopies} onChange={(e) => setKeepCopies(e.target.checked)} /> Keep a copy anyway</label></p>
          )}
          <p className="muted">{review.result}. Nothing is written until you confirm below.</p>
          {preview?.dryRun && (
            <div className="split-preview" role="region" aria-label="What the split will do" tabIndex={-1}>
              <h3>What will happen</h3>
              <p>{preview.would ? `${preview.would.files} new files will be written as ${preview.would.by || "you"}.` : ""} {preview.note}</p>
            </div>
          )}
        </>
      )}
      <div className="row wrap">
        <button type="button" onClick={onBack} disabled={busy}>Back to the pages</button>
        {!preview ? <button type="button" className="primary" disabled={!can || busy} onClick={() => send(true)}>Preview the split</button>
          : <button type="button" className="primary" disabled={!can || busy} onClick={() => send(false)}>{`Write ${review?.files} ${review?.files === 1 ? "file" : "files"}${by ? ` as ${by}` : ""}`}</button>}
        {!can && review && status === "draft" && !review.totalsOk && <span className="muted">The page counts must add up first.</span>}
        {status === "draft" && (
          <Confirm label="Decline" summary={<p>Decline this split? Nothing is written, and the draft is kept as declined.</p>} busy={busy}
            onConfirm={() => { void backend.act(id, { act: "decline", by: by || undefined }).then(() => onDone(), (e) => setError((e as Error).message)); }}>Decline this split</Confirm>
        )}
      </div>
    </section>
  );
}

function ReviewTitle({ page, value, onCommit, onSaved }: { page: number; value: string; onCommit(page: number, v: string): Promise<void>; onSaved(): void }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <label>
      <span className="sr-only">Title for the part starting at page {page}</span>
      <input value={v} maxLength={200} onChange={(e) => setV(e.target.value)} onBlur={() => { if (v !== value) { void onCommit(page, v).then(onSaved); } }} />
    </label>
  );
}
