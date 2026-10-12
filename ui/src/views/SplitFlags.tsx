import { Glyph } from "../components/Glyph";
import { ModalSheet } from "./SplitDrawer";
import { flagItems, pagesList, segWord, type FlagItem, type SegmentFlags } from "./splitModel";

/** The splitter's flags (docs/pdf-splitter.md, 9.5): what the server read of each segment before the review. Each flag is a glyph and words,
 * never a colour alone. The rail shows the first two; the dialog gives every flag a full sentence and the acts that go with it. A flag is a
 * reading: nothing is marked, moved, or written because of one. */

export const FLAG_LINE_H = 30;

/** The chips on a rail row: at most two flags, then a button that opens the whole list. */
export function FlagChips({ flags, no, onOpen, max = 2 }: { flags: SegmentFlags | undefined; no: number; onOpen(): void; max?: number }) {
  const items = flags ? flagItems(flags) : [];
  if (!items.length) return <div className="split-flags" aria-hidden="true" />;
  const shown = items.slice(0, max);
  const label = no > 0 ? `segment ${no}` : "this nested segment";
  return (
    <div className="split-flags" role="group" aria-label={`Flags for ${label}`}>
      {shown.map((i) => <span key={i.key} className="split-flag" data-flag={i.key}><Glyph name={i.glyph} size={12} /> <span>{i.short}</span></span>)}
      <button type="button" className="split-flag-more" onClick={onOpen}
        aria-label={`${items.length > shown.length ? `+${items.length - shown.length} more` : "Details"}: all ${items.length} ${items.length === 1 ? "flag" : "flags"} for ${label}: ${items.map((i) => i.short).join("; ")}`}>
        {items.length > shown.length ? `+${items.length - shown.length} more` : "Details"}
      </button>
    </div>
  );
}

export interface FlagActions {
  readOnly: boolean;
  go(page: number): void;
  /** begin walking a list of pages (a "Review these pages" act); nothing is marked by it */
  walk(pages: number[], why: string): void;
  /** turn these pages in the new files, by the measured fix */
  fixSideways(pages: number[]): void;
  /** the first page of the segment with this key, if it is known */
  segStart(key: string): number | null;
  close(): void;
}

function ItemActs({ item, flags, a }: { item: FlagItem; flags: SegmentFlags; a: FlagActions }) {
  if (item.key === "mayHoldMore" && item.pages) {
    return <button type="button" className="primary" onClick={() => { a.walk(item.pages!, "may hold another document"); a.close(); }}>Review these pages</button>;
  }
  if (item.key === "sideways" && item.pages) {
    return (
      <div className="row wrap">
        {item.pages.slice(0, 6).map((p) => <button key={p} type="button" onClick={() => { a.go(p); a.close(); }} aria-label={`Go to page ${p}`}>Go to page {p}</button>)}
        {!a.readOnly && <button type="button" className="primary" onClick={() => { a.fixSideways(item.pages!); a.close(); }}>Fix {item.pages.length === 1 ? "this page" : `these ${item.pages.length} pages`} in the new files</button>}
      </div>
    );
  }
  if (item.key === "nearDuplicate" && flags.nearDuplicateOf) {
    const at = a.segStart(flags.nearDuplicateOf);
    return at ? <button type="button" onClick={() => { a.go(at); a.close(); }}>Go to {segWord(flags.nearDuplicateOf)}</button> : null;
  }
  if (item.key === "repeated") {
    return <div className="row wrap">{flags.repeatedBy.map((k) => { const at = a.segStart(k); return at ? <button key={k} type="button" onClick={() => { a.go(at); a.close(); }}>Go to {segWord(k)}</button> : null; })}</div>;
  }
  if (item.key === "blankOnly") return <button type="button" onClick={() => { a.go(flags.start); a.close(); }}>Go to page {flags.start}</button>;
  return null;
}

/** Every flag of one segment, in full sentences, with its acts. Opens as a sheet like the page menu. */
export function FlagsDialog({ flags, no, caveats, a, fallback }: { flags: SegmentFlags; no: number; caveats: readonly string[]; a: FlagActions; fallback?: () => void }) {
  const items = flagItems(flags);
  const name = no > 0 ? `Segment ${no}` : "Nested segment";
  const range = flags.start === flags.end ? `page ${flags.start}` : `pages ${flags.start}-${flags.end} (${flags.pages})`;
  return (
    <ModalSheet label={`Flags for ${name.toLowerCase()}`} onClose={a.close} fallback={fallback} className="split-flags-dialog">
        <h2>{name}: {range}</h2>
        {flags.measured < flags.pages && <p className="muted">{flags.measured} of {flags.pages} pages have been measured so far; a flag that needs a page's facts waits for it.</p>}
        {items.length === 0 ? <p className="muted">Nothing is flagged for this segment.</p> : (
          <ul>
            {items.map((i) => (
              <li key={i.key} className="split-flag-item" data-flag={i.key}>
                <p><Glyph name={i.glyph} size={14} /> <strong>{i.short}.</strong> {i.long}</p>
                <ItemActs item={i} flags={flags} a={a} />
              </li>
            ))}
          </ul>
        )}
        {caveats.map((c) => <p key={c} className="muted">{c}</p>)}
        <div className="row"><button type="button" onClick={a.close}>Close</button></div>
    </ModalSheet>
  );
}

/** "Review these pages": a walk through a list of pages one at a time. It marks nothing by itself; the start is a button you press. */
export function WalkBar({ pages, at, why, isStart, readOnly, onStep, onMark, onDone }: {
  pages: readonly number[]; at: number; why: string; isStart: boolean; readOnly: boolean; onStep(d: 1 | -1): void; onMark(page: number): void; onDone(): void;
}) {
  const page = pages[at];
  return (
    <section className="notice split-walk" role="region" aria-label="Reviewing pages">
      <p>
        <strong>Reviewing page {page}</strong> ({at + 1} of {pages.length}): {why}. Pages to review: {pagesList(pages, 12)}. Nothing is marked until you press the button.
      </p>
      <div className="row wrap">
        <button type="button" disabled={at === 0} onClick={() => onStep(-1)}>Previous page to review</button>
        <button type="button" disabled={at >= pages.length - 1} onClick={() => onStep(1)}>Next page to review</button>
        <button type="button" disabled={readOnly || isStart || page === 1} onClick={() => onMark(page)}>{isStart ? `Page ${page} already starts a segment` : `Mark page ${page} as a start`}</button>
        <button type="button" onClick={onDone}>Done reviewing</button>
      </div>
    </section>
  );
}
