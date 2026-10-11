import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Confirm } from "../components";
import { Glyph } from "../components/Glyph";
import type { SplitBackend } from "./splitApi";
import type { FactsCache } from "./splitFacts";
import type { ApplyAnswer, Review, ReviewPart, SidewaysPage, Turn, Turns } from "./splitModel";
import { TURN_DEGREES, flagItems, pagesList, rangeWords, turnBody, turnWord } from "./splitModel";
import type { ThumbLoader } from "./splitThumbs";

/** The review step (docs/pdf-splitter.md, sections 5.7 and 9.5): the checkpoint before anything is written. Counts that must add up, the first
 * page of every part, the pages to leave out and to turn, where the new files go (held, the library, or their slots), the flags the server
 * read, the collisions and duplicates, then the apply as a dry run and one confirm. */

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
  library: "Goes to the library intake; kept in the store with the reason if it cannot be filed",
};

/** The request-wide choice of where the new files go. The default is the server's: a part with a slot fills it, any other is held. */
export type Filing = "" | "held" | "library" | "slots";
const FILINGS: { id: Filing; words: string; help: string }[] = [
  { id: "", words: "As each part is labelled", help: "A part with a slot fills it; any other is kept in jason's store. This is the default." },
  { id: "held", words: "Held", help: "Every part is kept in jason's store, none put in a slot." },
  { id: "library", words: "Library", help: "Every part is given to the library intake, which files it by the kind it reads." },
  { id: "slots", words: "Slots", help: "Each part goes into the slot it names; a part naming none is kept in the store." },
];
type PartFiling = "" | "held" | "library" | "slot";
const NO_TURNS: Turns = {};

function turnOf(v: string): Turn | null { return v === "fix" ? "fix" : v === "90" || v === "180" || v === "270" ? (Number(v) as Turn) : null; }

export function SplitReview({ backend, id, by, loader, facts, status, drop, setDrop, onBack, onDone, confidential, onRename, turns = NO_TURNS, setTurns, onReviewPages, onBusy }: {
  backend: SplitBackend; id: string; by: string; loader: ThumbLoader; facts: FactsCache; status: string; drop: number[]; setDrop(d: number[]): void;
  onBack(): void; onDone(): void; confidential: boolean; onRename(page: number, title: string): Promise<void>;
  /** pages a person chose to turn in the new files, and the way to change them (the page menu sets them too) */
  turns?: Turns; setTurns?(t: Turns): void;
  /** jump to the listed pages (leaves the review): "Review these pages" */
  onReviewPages?(pages: number[], why: string): void;
  /** told whenever a request is running, so a drawer around the review does not close under a write */
  onBusy?(busy: boolean): void;
}) {
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { onBusy?.(busy); }, [busy, onBusy]);
  useEffect(() => () => onBusy?.(false), [onBusy]);
  const [preview, setPreview] = useState<ApplyAnswer | null>(null);
  const [result, setResult] = useState<ApplyAnswer | null>(null);
  const [keepCopies, setKeepCopies] = useState(false);
  const [blanks, setBlanks] = useState<number[] | null>(null);
  const [filing, setFiling] = useState<Filing>("");
  const [partFiling, setPartFiling] = useState<Record<string, PartFiling>>({});
  const [seen, setSeen] = useState<Map<number, SidewaysPage>>(new Map());
  const heading = useRef<HTMLHeadingElement>(null);

  const partsBody = () => { const rows = Object.entries(partFiling).filter(([, v]) => v).map(([segment, f]) => ({ segment, filing: f })); return rows.length ? rows : undefined; };
  const choices = () => ({ drop, keepCopies, filing: filing || undefined, rotate: turnBody(turns), parts: partsBody() });

  const read = useCallback(async () => {
    setError(""); setPreview(null);
    try { setReview((await backend.act(id, { act: "review", drop, keepCopies, filing: filing || undefined, rotate: turnBody(turns), parts: partsBody() })).review ?? null); }
    catch (e) { setReview(null); setError((e as Error).message); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backend, id, drop, keepCopies, filing, partFiling, turns]);
  useEffect(() => { void read(); }, [read]);
  useEffect(() => { heading.current?.focus(); }, [review === null]);
  // the pages measured sideways, from the flags (disk only); a page already turned still has its row so the choice can be changed back
  useEffect(() => {
    let live = true;
    try {
      void Promise.resolve(backend.session(id, { flags: true })).then((a) => {
        if (!live) return;
        const m = new Map<number, SidewaysPage>();
        for (const f of a.flags?.segments ?? []) if (f.level === 0) for (const s of f.sideways) m.set(s.page, s);
        setSeen(m);
      }, () => undefined);
    } catch { /* flags are readings; a review does not need them */ }
    return () => { live = false; };
  }, [backend, id]);

  const findBlanks = async () => {
    await facts.loadAll();
    const out: number[] = [];
    for (let n = 1; n <= facts.pages; n++) if (facts.get(n)?.blank === "blank") out.push(n);
    setBlanks(out);
  };

  const send = async (dry: boolean) => {
    setBusy(true); setError("");
    try {
      const a = await backend.act(id, { act: "apply", dryRun: dry, confirm: !dry, by: by || undefined, ...choices() });
      if (dry) setPreview(a); else { setResult(a); onDone(); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  if (result) return <Written result={result} busy={busy} heading={heading} onBack={onBack} onAgain={() => { setResult(null); void read(); }} />;

  const parts: ReviewPart[] = review?.parts ?? [];
  const can = !!review && review.totalsOk && status === "draft" && parts.length > 0;
  const turnPages = [...new Set([...seen.keys(), ...Object.keys(turns).map(Number)])].sort((a, b) => a - b);
  const sidewaysAll = [...seen.keys()];
  const setTurn = (page: number, t: Turn | null) => {
    if (!setTurns) return;
    const next: Record<number, Turn> = { ...turns };
    if (t === null) delete next[page]; else next[page] = t;
    setTurns(next);
  };
  const shown = preview?.review ?? review;
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

          <fieldset className="split-filing" disabled={status !== "draft"}>
            <legend>Where the new files go</legend>
            <div className="split-filing-opts">
              {FILINGS.map((f) => (
                <label key={f.id || "default"} className="split-filing-opt">
                  <input type="radio" name="split-filing" checked={filing === f.id} onChange={() => setFiling(f.id)} />
                  <span><strong>{f.words}</strong> <span className="muted">{f.help}</span></span>
                </label>
              ))}
            </div>
            {(filing === "library" || parts.some((p) => p.filing === "library")) && (
              <p className="muted" role="note">
                <Glyph name="info" size={12} /> The library intake reads each part's text layer and files it by the kind it finds. It does not run OCR in this step, so a scan with no text layer usually comes back kept in the store with the reason, until someone classifies it. Nothing is lost.
              </p>
            )}
            <p className="muted">A part can be given its own choice in the table below; it overrides this one.</p>
          </fieldset>

          <div className="split-table-wrap">
            <table className="split-review-table">
              <caption className="sr-only">The files this split would make, in page order</caption>
              <thead><tr><th scope="col">Part</th><th scope="col">First page</th><th scope="col">Pages</th><th scope="col">Title (a guess until you confirm)</th><th scope="col">What happens</th></tr></thead>
              <tbody>
                {parts.map((p) => {
                  const items = flagItems({ ...p.flags, sideways: p.sideways }, p.flags?.overPartLimit ? p.size : undefined);
                  return (
                    <tr key={p.segment} data-action={p.action}>
                      <th scope="row" data-label="Part">{p.ordinal}{p.level > 0 ? " (nested)" : ""}</th>
                      <td data-label="First page"><LazyChip page={p.start} loader={loader} /></td>
                      <td data-label="Pages">{rangeWords(p.start, p.end)}</td>
                      <td data-label="Title">{confidential ? <span className="muted">hidden</span> : <ReviewTitle page={p.start} value={p.title} onCommit={onRename} onSaved={read} />}
                        {p.kind && !confidential && <span className="muted split-kind"> looks like: {p.kind}, a guess</span>}</td>
                      <td data-label="What happens">
                        <span className="split-action">{ACTION_WORDS[p.action] ?? p.action}</span>{p.why ? <span className="muted"> {p.why}</span> : null}{p.slot ? <span className="muted"> Slot: {p.slot}</span> : null}
                        {(p.rotated?.length ?? 0) > 0 && <span className="split-turned"><Glyph name="refresh-cw" size={12} /> Turns {p.rotated!.length === 1 ? "page" : "pages"} {p.rotated!.map((r) => `${r.page} by ${r.degrees}°`).join(", ")} in this file.</span>}
                        <label className="split-part-filing">
                          <span className="sr-only">Where part {p.ordinal} goes</span>
                          <select value={partFiling[p.segment] ?? ""} disabled={status !== "draft"} onChange={(e) => setPartFiling({ ...partFiling, [p.segment]: e.target.value as PartFiling })}>
                            <option value="">Where it goes: as chosen above</option>
                            <option value="held">Where it goes: held</option>
                            <option value="library">Where it goes: library</option>
                            {p.slot && <option value="slot">{`Where it goes: its slot (${p.slot})`}</option>}
                          </select>
                        </label>
                        {items.length > 0 && (
                          <ul className="split-flag-list" aria-label={`Flags for part ${p.ordinal}`}>
                            {items.map((i) => (
                              <li key={i.key} data-flag={i.key}><Glyph name={i.glyph} size={12} /> <strong>{i.short}.</strong> <span className="muted">{i.long}</span>
                                {i.key === "mayHoldMore" && i.pages && onReviewPages && <> <button type="button" onClick={() => onReviewPages(i.pages!, "it may hold another document")}>Review these pages</button></>}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <section className="split-drops" aria-label="Pages to turn">
            <h3>Pages to turn</h3>
            <p className="muted">Turning is done in the new files only; the original and the pictures here are not changed. A page with no text layer is never called sideways, because nothing was measured; name its degrees yourself in its page menu.</p>
            {turnPages.length === 0 ? <p className="muted">No page is measured sideways, and none is chosen to be turned.</p> : (
              <ul className="split-turn-list">
                {turnPages.map((p) => {
                  const info = seen.get(p);
                  const t = turns[p];
                  return (
                    <li key={p}>
                      <label className="row wrap">
                        <span className="split-turn-page">Page {p}{info ? `: sideways, its text is turned ${info.turn}°` : ": chosen by you"}</span>
                        <select aria-label={`Turn for page ${p}`} value={t === undefined ? "" : String(t)} disabled={status !== "draft" || !setTurns} onChange={(e) => setTurn(p, turnOf(e.target.value))}>
                          <option value="">Leave as it is</option>
                          {info && <option value="fix">{turnWord("fix", info.fix)}</option>}
                          {TURN_DEGREES.map((d) => <option key={d} value={String(d)}>{turnWord(d)} clockwise</option>)}
                        </select>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="row wrap">
              {sidewaysAll.length > 0 && <button type="button" disabled={status !== "draft" || !setTurns || sidewaysAll.every((p) => turns[p] === "fix")}
                onClick={() => setTurns?.({ ...turns, ...Object.fromEntries(sidewaysAll.map((p) => [p, "fix" as Turn])) })}>Fix all {sidewaysAll.length} sideways {sidewaysAll.length === 1 ? "page" : "pages"}</button>}
              {Object.keys(turns).length > 0 && <button type="button" disabled={status !== "draft" || !setTurns} onClick={() => setTurns?.({})}>Leave every page as it is</button>}
            </div>
            <p className="muted">To turn another page, open its page menu (the key L on the page) and choose a turn.</p>
          </section>

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
          <Plan review={shown!} />
          <p className="muted">{review.result}. Nothing is written until you confirm below.</p>
          {preview?.dryRun && (
            <div className="split-preview" role="region" aria-label="What the split will do" tabIndex={-1}>
              <h3>What will happen</h3>
              <p>{preview.would ? `${preview.would.files} new files will be written as ${preview.would.by || "you"}.` : ""} {preview.note}</p>
              {preview.review && <Plan review={preview.review} dry />}
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

/** What the choices come to, from the server's own counts: where the files go and which pages are turned (the dry run's words). */
function Plan({ review, dry = false }: { review: Review; dry?: boolean }) {
  const f = review.filing;
  const turned = review.rotated ?? [];
  const left = review.sidewaysLeft ?? 0;
  if (!f && !turned.length && !left) return null;
  return (
    <ul className="split-plan" aria-label={dry ? "The dry run's counts" : "What the choices come to"}>
      {f && (
        <li data-plan="filing"><Glyph name="folder-open" size={12} /> Filing ({f.asked}): {f.held} held, {f.library} to the library, {f.slots} into {f.slots === 1 ? "a slot" : "slots"}
          {f.collisions > 0 && `, ${f.collisions} kept held because the slot is full`}{f.duplicates > 0 && `, ${f.duplicates} skipped as identical to a file jason has`}.</li>
      )}
      {(turned.length > 0 || left > 0) && (
        <li data-plan="turns"><Glyph name="refresh-cw" size={12} /> {turned.length} {turned.length === 1 ? "page" : "pages"} turned in the new files{turned.length ? ` (${pagesList(turned.map((r) => r.page))})` : ""}; {left} measured sideways {left === 1 ? "stays" : "stay"} as {left === 1 ? "it is" : "they are"}.</li>
      )}
    </ul>
  );
}

function Written({ result, busy, heading, onBack, onAgain }: { result: ApplyAnswer; busy: boolean; heading: React.RefObject<HTMLHeadingElement>; onBack(): void; onAgain(): void }) {
  const library = result.library ?? [];
  const held = result.held ?? [];
  const why = held.filter((h) => h.why);
  const queued = typeof result.ocrQueued === "number" ? result.ocrQueued : Array.isArray(result.ocrQueued) ? result.ocrQueued.length : 0;
  return (
    <section className="split-review" aria-labelledby="split-review-h">
      <h2 id="split-review-h" tabIndex={-1} ref={heading}>{result.ok ? "The split was written" : "The split was partly written"}</h2>
      <p role="status">{result.ok ? "The original was not changed." : result.failed?.map((f) => `Segment ${f.segment}: ${f.why}`).join(" ")}</p>
      <ul>
        <li>{result.filled?.length ?? 0} files filled a record slot.</li>
        {library.length > 0 && <li>{library.length} {library.length === 1 ? "file was" : "files were"} taken in by the library{library.some((l) => l.kind) ? `: ${library.map((l) => `${l.segment}${l.kind ? ` as ${l.kind}` : ""}${l.libraryId ? ` (${l.libraryId})` : ""}`).join("; ")}` : ""}.</li>}
        <li>{held.length} files are kept in jason's store for filing later.</li>
        {why.length > 0 && <li>Kept, with the reason: {why.map((h) => `${h.segment} (${h.why})`).join("; ")}.</li>}
        {queued > 0 && <li>{queued} {queued === 1 ? "part was" : "parts were"} queued for OCR.</li>}
        {(result.rotated?.length ?? 0) > 0 && <li>{result.rotated!.length} {result.rotated!.length === 1 ? "page was" : "pages were"} turned in the new files: {result.rotated!.map((r) => `${r.page} by ${r.degrees}°`).join(", ")}.</li>}
        {(result.skipped?.length ?? 0) > 0 && <li>{result.skipped!.length} were skipped: {result.skipped!.map((s) => `${s.segment} (${s.why || s.action})`).join("; ")}.</li>}
        {(result.dropped?.length ?? 0) > 0 && <li>Pages left out of every file: {result.dropped!.join(", ")}.</li>}
      </ul>
      {result.note && <p className="muted">{result.note}</p>}
      <div className="row wrap"><button type="button" onClick={onBack}>Back to the pages</button>{!result.ok && <button type="button" className="primary" disabled={busy} onClick={onAgain}>Review again to finish the rest</button>}</div>
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
