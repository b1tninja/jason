import { useEffect, useRef, useState } from "react";
import { Badge } from "../components";
import { Glyph } from "../components/Glyph";
import type { FactsCache } from "./splitFacts";
import { BAND_GLYPH, TURN_DEGREES, figureSizes, pageAlt, sidewaysWords, stateWord, turnWord, type PageFact, type Size, type Suggestion, type Turn } from "./splitModel";
import type { ThumbLoader } from "./splitThumbs";

/** The compare and zoom pane, and the page menu (docs/pdf-splitter.md, sections 5.2 and 5.3). */

export type Zoom = "fit" | "full" | "enlarged";
export const ZOOMS: { id: Zoom; words: string }[] = [
  { id: "fit", words: "Fit width" },
  { id: "full", words: "800 px" },
  { id: "enlarged", words: "Enlarged (the sharpest picture)" },
];

export function Figure({ page, loader, caption, zoom, sizes: given, facts, confidential, note }: {
  page: number; loader: ThumbLoader; caption: string; zoom: Zoom; sizes?: Size[]; facts: FactsCache; confidential: boolean; note?: string;
}) {
  const sizes = given ?? figureSizes(zoom, typeof window === "undefined" ? 700 : Math.min(window.innerWidth, 720), typeof window === "undefined" ? 1 : window.devicePixelRatio || 1);
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
      <div className="split-figure-pic" data-loupe={page}><img ref={img} alt={pageAlt(page, f, confidential)} draggable={false} />{failed && <p className="notice notice-warn" role="alert">{failed}</p>}</div>
    </figure>
  );
}

/** The compare pane (the "Compare" drawer): this page beside the page before and the first page of the segment before, with a step to the
 * previous and next page and a jump to the segment's first page. It stands in a drawer, which gives it its Close button. */
export function ComparePane({ page, pages, prev, prevSegFirst, segFirst, loader, zoom, onZoom, onGo, facts, confidential, starts }: {
  page: number; pages: number; prev: number | null; prevSegFirst: number | null; segFirst: number; loader: ThumbLoader; zoom: Zoom; onZoom(z: Zoom): void; onGo(page: number): void;
  facts: FactsCache; confidential: boolean; starts: boolean;
}) {
  return (
    <section className="split-compare" aria-label="Compare pages">
      <div className="row wrap split-compare-head">
        <div role="group" aria-label="Zoom" className="row">
          {ZOOMS.map((z) => <button key={z.id} type="button" aria-pressed={zoom === z.id} onClick={() => onZoom(z.id)}>{z.words}</button>)}
        </div>
        <span className="muted">Keys + and - change the zoom.</span>
      </div>
      <div className="row wrap split-compare-nav" role="group" aria-label="Pages to compare">
        <button type="button" disabled={page <= 1} onClick={() => onGo(page - 1)}>Previous page</button>
        <strong aria-live="polite">Page {page} of {pages}</strong>
        <button type="button" disabled={page >= pages} onClick={() => onGo(page + 1)}>Next page</button>
        <button type="button" disabled={segFirst === page} onClick={() => onGo(segFirst)}>{`First page of this segment (${segFirst})`}</button>
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
  /** the page's measured facts, the turn a person chose for it (applied in the new files only), and a way to set or clear it */
  fact?: PageFact; turn?: Turn; setTurn(t: Turn | null): void;
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
        {a.fact && !a.fact.pending && (
          <p className="muted split-menu-facts" data-sideways={a.fact.sideways || undefined}>
            {a.fact.sideways ? <><Glyph name="refresh-cw" size={12} /> {sidewaysWords(a.fact)}.</> : a.fact.has_text && a.fact.turn === 0 ? "Its text is upright." : a.fact.has_text ? "Its text was not read well enough to say which way up it is." : a.fact.blank === "blank" ? "" : "No text layer: nothing was measured, so it is never called sideways."}
            {a.fact.orientation ? ` Drawn ${a.fact.orientation}.` : ""}
          </p>
        )}
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
          {!a.readOnly && a.fact?.sideways && <li><button type="button" aria-pressed={a.turn === "fix"} onClick={done(() => a.setTurn("fix"))}>{`${turnWord("fix", a.fact.fix)} in the new files`}</button></li>}
          {!a.readOnly && TURN_DEGREES.map((d) => <li key={d}><button type="button" aria-pressed={a.turn === d} onClick={done(() => a.setTurn(d))}>{`${turnWord(d)} clockwise in the new files`}</button></li>)}
          {!a.readOnly && a.turn !== undefined && <li><button type="button" onClick={done(() => a.setTurn(null))}>Do not turn this page</button></li>}
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
  ["+ and -", "Zoom in the compare drawer, or resize the album"],
  ["F", "Focus: the pages fill the screen (the console's menu and header are hidden); Esc leaves it"],
  ["E", "Magnifier on or off (M is the merge key), in whichever mode View > Magnifier > Mode chose. With a mouse, hold the pointer over a page; Esc hides the lens or the corner viewer"],
  ["Alt and arrows", "Magnifier: show the lens beside the focused page (or the corner viewer on it) and move the spot it shows"],
  ["Alt and + or -", "Magnifier: zoom 2 to 6 times (Alt and the mouse wheel does the same)"],
  ["S", "Open or close the segments drawer"],
  ["C or a double click", "Open or close the compare drawer on this page"],
  ["Z and Shift Z", "Undo and redo (also Y, and Ctrl Z)"],
  ["?", "This list"],
  ["Esc", "Close a menu, a drawer, or focus; clear the selection"],
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
        <p className="muted">On a touch screen: tap marks, press and hold opens the page menu, and the grip on a start can be dragged to another page. With the Magnifier button on, press and hold a page for a moment, then drag: the lens rides above your finger (the page menu is then opened from the Pages menu or with the L key). In the fixed corner viewer mode the same hold shows the page in a band above the action bar.</p>
        <p className="muted">The corner viewer (the View menu, Magnifier, Mode: fixed corner viewer) keeps the last page after the pointer leaves, can be pinned to a page with its Pin button, shows a region or the whole page, hops to the opposite corner when the pointer stays under it (the View menu's Do not hop turns that off), and is resized by its corner grip (drag it, or focus it and use the arrow keys).</p>
        <button type="button" ref={close} onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
