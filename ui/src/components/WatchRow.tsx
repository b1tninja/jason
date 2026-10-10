import { Pill } from "./Pill";
import { type DocStatic } from "./Doc";
import { EvidenceEntries } from "./EvidenceEntries";
import { NOT_SEEN, WATCH_GLYPH, WATCH_MEANINGS, type WatchItem } from "../lib/inspections";

/** One item of the watchlist: its standing as a word (overdue, unknown, partly answered, current, not applicable) with
 * its meaning, the records it rests on as document chips, and one line on what would change it. `unknown` is a search that
 * found nothing, never "not done": it shows what jason searched and by what, and that a record under another name is not
 * seen. An unknown row is drawn dashed, so it differs from an overdue one by weight and not only by hue. */
export function WatchRow({ item, docProps }: { item: WatchItem; docProps?: DocStatic }) {
  const unknown = item.standing === "unknown";
  return (
    <article className={`insp-watch${unknown ? " insp-watch-unknown" : ""}`} data-standing={item.standing} aria-label={`${item.item}: ${item.standing}`}>
      <header className="row wrap">
        <strong>{item.item}</strong>
        <Pill word={item.standing} meaning={WATCH_MEANINGS[item.standing]} glyph={WATCH_GLYPH[item.standing]} />
      </header>
      {item.evidence.length > 0 && (
        <div className="insp-watch-evidence"><EvidenceEntries entries={item.evidence} {...docProps} /></div>
      )}
      <p><span className="muted">What would change this: </span>{item.changes}</p>
      <p className="muted insp-searched">Searched {item.searched}.{unknown && <> {NOT_SEEN} Nothing here says it was not done.</>}</p>
    </article>
  );
}
