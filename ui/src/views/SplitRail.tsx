import { memo, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "../components";
import { Glyph } from "../components/Glyph";
import { BAND_GLYPH, rangeWords, type SegmentRow, type Suggestion } from "./splitModel";
import type { ThumbLoader } from "./splitThumbs";

/** The segment list (docs/pdf-splitter.md, sections 5.3 and 5.4): the table-twin of the whole draft, windowed with a fixed row height, with
 * jason's open suggestions in their page order as dashed rows. The rail is the same list in a compact form. */

export type ListItem =
  | { kind: "seg"; seg: SegmentRow; no: number }
  | { kind: "sug"; sug: Suggestion };

export const ROW_H = 76;
export const ROW_H_COMPACT = 60;
/** On a phone each row has a second line for its buttons. */
export const ROW_H_TALL = 128;
export const ROW_H_TALL_COMPACT = 112;
const BUFFER_ROWS = 8;

export function itemsOf(segments: readonly SegmentRow[], suggestions: readonly Suggestion[], showRejected: boolean): ListItem[] {
  const out: ListItem[] = [];
  let no = 0;
  for (const seg of segments) {
    if (seg.level === 0) no += 1;
    out.push({ kind: "seg", seg, no: seg.level === 0 ? no : 0 });
  }
  for (const sug of suggestions) {
    if (sug.state === "open" || (showRejected && sug.state === "rejected")) out.push({ kind: "sug", sug });
  }
  const page = (i: ListItem) => (i.kind === "seg" ? i.seg.start : i.sug.page);
  // a suggestion sits after the segment that holds its page
  return out.sort((a, b) => page(a) - page(b) || (a.kind === "seg" ? -1 : 1));
}

function Chip({ page, loader }: { page: number; loader: ThumbLoader }) {
  const img = useRef<HTMLImageElement>(null);
  useEffect(() => { const el = img.current; if (el) return loader.attach(el, page, ["small"]); }, [loader, page]);
  return <span className="split-chip"><img ref={img} alt="" draggable={false} /></span>;
}

interface RowProps {
  item: ListItem; compact: boolean; tall: boolean; loader: ThumbLoader; readOnly: boolean; confidential: boolean; current: boolean; index: number; of: number;
  onGo(page: number): void; onRemove(page: number): void; onLevel(page: number, level: number): void; onTitle(page: number, title: string): void;
  onAccept(id: string): void; onReject(id: string): void; onWhy(s: Suggestion): void;
}

const Row = memo(function Row(p: RowProps) {
  const { item, compact, readOnly } = p;
  const h = p.tall ? (compact ? ROW_H_TALL_COMPACT : ROW_H_TALL) : compact ? ROW_H_COMPACT : ROW_H;
  if (item.kind === "sug") {
    const s = item.sug;
    return (
      <li className="split-row-item" data-kind="sug" data-state={s.state} data-tall={p.tall || undefined} style={{ height: h }} aria-posinset={p.index + 1} aria-setsize={p.of}>
        <Chip page={s.page} loader={p.loader} />
        <div className="split-row-main">
          <strong>Page {s.page}: suggested start</strong>{" "}
          <Badge tone={s.band === "High" ? "good" : s.band === "Medium" ? "warn" : "neutral"}>{`${s.band} ${BAND_GLYPH[s.band] ?? ""}`.trim()}</Badge>
          {s.state === "rejected" && <span className="muted"> rejected</span>}
          <p className="muted split-why">{s.why}</p>
        </div>
        <div className="split-row-acts">
          <button type="button" onClick={() => p.onGo(s.page)} aria-label={`Go to page ${s.page}`}>Go to</button>
          {s.state === "open" && !readOnly && <>
            <button type="button" onClick={() => p.onAccept(s.id)} aria-label={`Accept the suggested start at page ${s.page}`}>Accept</button>
            <button type="button" onClick={() => p.onReject(s.id)} aria-label={`Reject the suggested start at page ${s.page}`}>Reject</button>
          </>}
          <button type="button" onClick={() => p.onWhy(s)} aria-label={`Why page ${s.page} was suggested`}>Why</button>
        </div>
      </li>
    );
  }
  const { seg, no } = item;
  const guess = seg.labels.title || "";
  return (
    <li className="split-row-item" data-kind="seg" data-level={seg.level} data-current={p.current || undefined} data-tall={p.tall || undefined} style={{ height: h, paddingLeft: seg.level * 18 }} aria-posinset={p.index + 1} aria-setsize={p.of}>
      <Chip page={seg.start} loader={p.loader} />
      <div className="split-row-main">
        <strong>{seg.level > 0 ? "Nested" : `Segment ${no}`}</strong> <span>{rangeWords(seg.start, seg.end)}</span>
        {seg.start === 1 && <span className="muted"> <Glyph name="lock" size={12} /> first page</span>}
        {!compact && !p.confidential && !readOnly ? (
          <TitleField page={seg.start} value={guess} onCommit={p.onTitle} />
        ) : guess && <p className="muted split-why">{p.confidential ? "" : guess}</p>}
        {!compact && <p className="muted split-why">Start set by {seg.source === "first" ? "the first page" : seg.source === "accepted" ? "an accepted suggestion" : "you"}</p>}
      </div>
      <div className="split-row-acts">
        <button type="button" onClick={() => p.onGo(seg.start)} aria-label={`Go to page ${seg.start}`}>Go to</button>
        {!readOnly && seg.start !== 1 && <>
          <button type="button" onClick={() => p.onRemove(seg.start)} aria-label={`Merge segment starting at page ${seg.start} with the previous`}>Merge up</button>
          {!compact && <button type="button" onClick={() => p.onLevel(seg.start, seg.level > 0 ? 0 : 1)} aria-label={seg.level > 0 ? `Make the start at page ${seg.start} a top-level segment` : `Make the start at page ${seg.start} nested`}>{seg.level > 0 ? "Make top-level" : "Make nested"}</button>}
        </>}
      </div>
    </li>
  );
});

function TitleField({ page, value, onCommit }: { page: number; value: string; onCommit(page: number, v: string): void }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <label className="split-title-field">
      <span className="sr-only">Title guess for the segment starting at page {page}</span>
      <input value={v} placeholder="Title (optional; a guess until you confirm)" onChange={(e) => setV(e.target.value)}
        onBlur={() => { if (v !== value) onCommit(page, v); }} onKeyDown={(e) => { if (e.key === "Enter") { (e.target as HTMLInputElement).blur(); } }} maxLength={200} />
    </label>
  );
}

export interface SegmentListProps {
  items: ListItem[]; loader: ThumbLoader; compact?: boolean; tall?: boolean; readOnly: boolean; confidential: boolean; label: string; height?: number;
  currentPage: number; scrollToPage?: number;
  onGo(page: number): void; onRemove(page: number): void; onLevel(page: number, level: number): void; onTitle(page: number, title: string): void;
  onAccept(id: string): void; onReject(id: string): void; onWhy(s: Suggestion): void;
}

export function SegmentList(p: SegmentListProps) {
  const compact = !!p.compact;
  const h = p.tall ? (compact ? ROW_H_TALL_COMPACT : ROW_H_TALL) : compact ? ROW_H_COMPACT : ROW_H;
  const box = useRef<HTMLDivElement>(null);
  const [state, setState] = useState({ top: 0, view: p.height ?? 480 });
  const total = p.items.length * h;
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setState((s) => (s.view === el.clientHeight || !el.clientHeight ? s : { ...s, view: el.clientHeight })));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const first = Math.max(0, Math.floor(state.top / h) - BUFFER_ROWS);
  const last = Math.min(p.items.length - 1, Math.ceil((state.top + state.view) / h) + BUFFER_ROWS);
  const frame = useRef(0);
  const onScroll = () => {
    if (frame.current) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = 0;
      const top = box.current?.scrollTop ?? 0;
      setState((s) => (Math.abs(s.top - top) < h / 2 ? s : { ...s, top }));
    });
  };
  useEffect(() => () => { if (frame.current) cancelAnimationFrame(frame.current); }, []);
  // a request to show a page: scroll to the row that holds it
  const row = useMemo(() => {
    if (!p.scrollToPage) return -1;
    let at = -1;
    p.items.forEach((it, i) => { if ((it.kind === "seg" ? it.seg.start : it.sug.page) <= p.scrollToPage!) at = i; });
    return at;
  }, [p.items, p.scrollToPage]);
  useEffect(() => { if (row >= 0 && box.current) { box.current.scrollTop = Math.max(0, row * h - h); setState((s) => ({ ...s, top: box.current!.scrollTop })); } }, [row, h]);
  let curIdx = -1;
  p.items.forEach((it, i) => { if (it.kind === "seg" && it.seg.start <= p.currentPage) curIdx = i; });
  const rows = [];
  for (let i = first; i <= last; i++) {
    const it = p.items[i];
    rows.push(
      <Row key={it.kind === "seg" ? `s${it.seg.start}` : `g${it.sug.id}`} item={it} compact={compact} tall={!!p.tall} loader={p.loader} readOnly={p.readOnly} confidential={p.confidential}
        current={i === curIdx}
        index={i} of={p.items.length} onGo={p.onGo} onRemove={p.onRemove} onLevel={p.onLevel} onTitle={p.onTitle} onAccept={p.onAccept} onReject={p.onReject} onWhy={p.onWhy} />,
    );
  }
  return (
    <div ref={box} className={`split-list${compact ? " is-compact" : ""}`} onScroll={onScroll} style={p.height ? { maxHeight: p.height } : undefined} role="region" aria-label={p.label} tabIndex={-1}>
      <ul style={{ height: total, position: "relative", margin: 0, padding: 0 }} aria-label={p.label}>
        <li aria-hidden="true" style={{ height: first * h, listStyle: "none" }} />
        {rows}
      </ul>
    </div>
  );
}
