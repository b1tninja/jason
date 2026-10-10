import { useEffect, useRef, useState } from "react";
import { Badge } from "../components";
import { Glyph } from "../components/Glyph";
import type { FactsCache } from "./splitFacts";
import { BAND_GLYPH, pageAlt, stateWord, type Size, type Suggestion } from "./splitModel";
import type { ThumbLoader } from "./splitThumbs";

/** The compare and zoom pane, and the page menu (docs/pdf-splitter.md, sections 5.2 and 5.3). */

export type Zoom = "fit" | "full" | "enlarged";
export const ZOOMS: { id: Zoom; words: string }[] = [
  { id: "fit", words: "Fit width" },
  { id: "full", words: "800 px" },
  { id: "enlarged", words: "Enlarged (from the 800 px picture)" },
];

export function Figure({ page, loader, caption, zoom, sizes = ["large"], facts, confidential, note }: {
  page: number; loader: ThumbLoader; caption: string; zoom: Zoom; sizes?: Size[]; facts: FactsCache; confidential: boolean; note?: string;
}) {
  const img = useRef<HTMLImageElement>(null);
  const [failed, setFailed] = useState("");
  useEffect(() => {
    const el = img.current;
    if (!el) return;
    setFailed("");
    return loader.attach(el, page, sizes, { onState: (s, w) => setFailed(s === "failed" ? w || "This page could not be drawn" : "") });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loader, page, sizes.join(",")]);
  const f = facts.get(page);
  return (
    <figure className="split-figure" data-zoom={zoom}>
      <figcaption><strong>{caption}</strong> <span className="muted">page {page}{f ? `, ${stateWord(f)}` : ""}{note ? `. ${note}` : ""}</span></figcaption>
      <div className="split-figure-pic"><img ref={img} alt={pageAlt(page, f, confidential)} draggable={false} />{failed && <p className="notice notice-warn" role="alert">{failed}</p>}</div>
    </figure>
  );
}

export function ComparePane({ page, prev, prevSegFirst, loader, zoom, onZoom, onClose, facts, confidential, starts }: {
  page: number; prev: number | null; prevSegFirst: number | null; loader: ThumbLoader; zoom: Zoom; onZoom(z: Zoom): void; onClose(): void;
  facts: FactsCache; confidential: boolean; starts: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  return (
    <section ref={ref} className="split-compare" aria-label="Compare pages">
      <div className="row wrap split-compare-head">
        <h2>Compare</h2>
        <div role="group" aria-label="Zoom" className="row">
          {ZOOMS.map((z) => <button key={z.id} type="button" aria-pressed={zoom === z.id} onClick={() => onZoom(z.id)}>{z.words}</button>)}
        </div>
        <span className="muted">Keys + and - change the zoom.</span>
        <button type="button" onClick={onClose}>Close the compare pane</button>
      </div>
      <div className="split-compare-grid">
        {prev !== null && <Figure page={prev} loader={loader} caption="The page before" zoom={zoom} facts={facts} confidential={confidential} />}
        <Figure page={page} loader={loader} caption="This page" zoom={zoom} facts={facts} confidential={confidential} note={starts ? "It starts a segment" : undefined} />
        {prevSegFirst !== null && prevSegFirst !== prev && <Figure page={prevSegFirst} loader={loader} caption="First page of the segment before" zoom={zoom} facts={facts} confidential={confidential} />}
      </div>
    </section>
  );
}

export interface MenuActions {
  isStart: boolean; first: boolean; readOnly: boolean; sug: Suggestion | undefined; selectionSize: number; canNest: boolean; nested: boolean;
  mark(): void; unmark(): void; nest(): void; level(l: number): void; larger(): void; accept(): void; reject(): void; retry(): void;
  everyNth(n: number): void; markEach(): void; mergeSelection(): void; close(): void;
}

/** The page menu: a long press, a right click, or `L`. A sheet, not a pop-up at the pointer, so a thumb reaches it. */
export function PageMenu({ page, a }: { page: number; a: MenuActions }) {
  const menu = useRef<HTMLDivElement>(null);
  const [every, setEvery] = useState(2);
  const [why, setWhy] = useState(false);
  useEffect(() => { menu.current?.querySelector<HTMLElement>("button")?.focus(); }, []);
  const done = (fn: () => void) => () => { fn(); a.close(); };
  return (
    <div className="split-menu-wrap" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); a.close(); } }}>
      <div className="split-menu-backdrop" onClick={a.close} />
      <div ref={menu} role="dialog" aria-label={`Page ${page}`} className="split-menu" aria-modal="true">
        <h2>Page {page}</h2>
        {a.first && <p className="muted"><Glyph name="lock" size={12} /> The first page always starts a segment.</p>}
        <ul>
          {!a.first && !a.readOnly && !a.isStart && <li><button type="button" onClick={done(a.mark)}>Starts a segment</button></li>}
          {!a.first && !a.readOnly && a.canNest && !a.nested && <li><button type="button" onClick={done(a.nest)}>{a.isStart ? "Make this start nested (inside the one before)" : "Starts a segment inside this one"}</button></li>}
          {!a.first && !a.readOnly && a.isStart && a.nested && <li><button type="button" onClick={done(() => a.level(0))}>Make this a top-level start</button></li>}
          {!a.first && !a.readOnly && a.isStart && <li><button type="button" onClick={done(a.unmark)}>Remove this start (merge with the previous)</button></li>}
          {a.sug && !a.readOnly && <li><button type="button" onClick={done(a.accept)}>Accept the suggestion</button></li>}
          {a.sug && !a.readOnly && <li><button type="button" onClick={done(a.reject)}>Reject the suggestion</button></li>}
          {a.sug && <li><button type="button" aria-expanded={why} onClick={() => setWhy(!why)}>Why was this suggested?</button></li>}
          {a.sug && why && <li className="split-menu-why"><Badge tone="neutral">{`${a.sug.band} ${BAND_GLYPH[a.sug.band] ?? ""}`}</Badge> {a.sug.why}
            <ul>{a.sug.signals.map((s) => <li key={s.signal}>{s.said} <span className="muted">({s.signal}, weight {s.weight})</span></li>)}</ul></li>}
          <li><button type="button" onClick={done(a.larger)}>Show larger (compare)</button></li>
          <li><button type="button" onClick={done(a.retry)}>Load this picture again</button></li>
        </ul>
        {a.selectionSize > 1 && !a.readOnly && (
          <div className="split-menu-sel" role="group" aria-label={`The ${a.selectionSize} selected pages`}>
            <h3>{a.selectionSize} pages selected</h3>
            <label className="row">Every <input type="number" min={1} max={500} value={every} onChange={(e) => setEvery(Math.max(1, Number(e.target.value) || 1))} aria-label="Every how many pages" /> pages
              <button type="button" onClick={done(() => a.everyNth(every))}>Every {every}{every === 1 ? "st" : every === 2 ? "nd" : every === 3 ? "rd" : "th"} page in the selection starts a segment</button></label>
            <button type="button" onClick={done(a.markEach)}>Mark each page in the selection as a start</button>
            <button type="button" onClick={done(a.mergeSelection)}>Merge the selection into one segment</button>
          </div>
        )}
        <div className="row"><button type="button" onClick={a.close}>Close</button></div>
      </div>
    </div>
  );
}

export const KEYS: [string, string][] = [
  ["Arrow keys", "Move between pages (up and down by a row in the album)"],
  ["Space or Enter", "Mark or unmark the page as the first page of a segment"],
  ["N and P", "Next and previous start or suggestion"],
  ["A and X", "Accept and reject the suggestion on this page"],
  ["M", "Merge this page's segment with the one before (remove its start)"],
  ["[ and ]", "Move this start one page earlier or later"],
  ["L", "Open the page menu"],
  ["Shift and arrows", "Extend a selection; Shift and click selects a range"],
  ["Home, End, Page Up, Page Down", "First page, last page, one screen"],
  ["G or /", "Go to a page"],
  ["V and 1 to 4", "Change the view"],
  ["+ and -", "Zoom in the compare pane, or resize the album"],
  ["Z and Shift Z", "Undo and redo (also Y, and Ctrl Z)"],
  ["?", "This list"],
  ["Esc", "Close a menu or the compare pane; clear the selection"],
];

export function KeyHelp({ onClose }: { onClose(): void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => { close.current?.focus(); }, []);
  return (
    <div className="split-menu-wrap" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}>
      <div className="split-menu-backdrop" onClick={onClose} />
      <div role="dialog" aria-label="Keyboard map" className="split-menu" aria-modal="true">
        <h2>Keyboard map</h2>
        <dl className="split-keys">{KEYS.map(([k, v]) => <div key={k}><dt><kbd>{k}</kbd></dt><dd>{v}</dd></div>)}</dl>
        <p className="muted">On a touch screen: tap marks, press and hold opens the page menu, and the grip on a start can be dragged to another page.</p>
        <button type="button" ref={close} onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
