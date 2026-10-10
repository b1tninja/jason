import { Pill } from "./Pill";
import { Confirm } from "./Confirm";
import type { NotOurs } from "../lib/inspections";

/** Mail addressed to another party at a shared address. It names what is visible on the envelope, already masked by the
 * server, and exposes none of the other party's details. "Mark not ours" is a write and goes through `Confirm`;
 * "return to the manager" only drafts a note (nothing is sent), and the note is a person's to send. */
export function NotOursNotice({ item, onMarkNotOurs, onDraftReturn }: { item: NotOurs; onMarkNotOurs?: (item: NotOurs) => void; onDraftReturn?: (item: NotOurs) => void }) {
  const what = item.subject.toLowerCase();
  return (
    <section className="insp-notours" role="note" aria-label={`${item.subject} that may not be ours`}>
      <header className="row wrap">
        <strong>This {what} appears to be for {item.addressee}</strong>
        <Pill word={item.marked ? "not ours" : "possibly not ours"} meaning="Addressed to another party. A reading of the envelope, not a finding." glyph="mail-warning" />
      </header>
      <ul>{item.visible.map((v) => <li key={v}>{v}</li>)}</ul>
      <p className="muted">The other party's details are not shown.</p>
      {item.marked
        ? <p role="status">Marked not ours by {item.marked.by} on {item.marked.on}.</p>
        : (
          <div className="row wrap">
            {onMarkNotOurs && <Confirm summary={<>Mark this {what} as not ours. Nothing is sent or deleted.</>} onConfirm={() => onMarkNotOurs(item)} label="Mark">Mark not ours</Confirm>}
            {onDraftReturn && <button onClick={() => onDraftReturn(item)}>Draft a note returning it to the manager (nothing is sent)</button>}
          </div>
        )}
    </section>
  );
}
