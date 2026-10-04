import { useState } from "react";
import { Badge, BoardFields, Card, DueDate, Evidence, Kanban, Pill, RemoteView, Timeline, type EvidenceEntry, type TimelineEvent } from "../components";
import { EvidenceEntries } from "../components/EvidenceEntries";
import { useApi } from "../lib/useApi";
import { BOARD_STATUSES, type BoardItem } from "./types";

/** A board item as `/api/board-items` answers it: its evidence strings, and beside them `evidenceRefs`, each string as
 * the server mapped it (a document reference, a command, or text; docs/console/doc-component.md). */
export type BoardItemWithRefs = BoardItem & { evidenceRefs?: EvidenceEntry[] };

/** An item's history lines ("YYYY-MM-DD: what") as Timeline events; a line without a day is undated. */
function historyEvents(history: readonly string[]): TimelineEvent[] {
  return history.map((h, i) => {
    const m = h.match(/^(\d{4}-\d{2}-\d{2})[:\s]\s*(.*)$/);
    return { id: String(i), date: m ? m[1] : "", title: m ? m[2] : h };
  });
}

/** One matter the board is asked to decide. jason's columns are read-only; the board's four are editable (BoardFields). */
export function BoardItemCard({ item, onSaved }: { item: BoardItemWithRefs; onSaved: (next: BoardItemWithRefs) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <article className="item" data-priority={item.priority}>
      <header className="row wrap">
        <Pill word={item.priority} />
        <Badge>{item.category}</Badge>
        {item.session === "executive session" && <Badge tone="warn">executive</Badge>}
        <DueDate iso={item.due} />
      </header>
      <h4>{item.title}</h4>
      <p className="ask">
        <strong>Ask:</strong> {item.ask}
      </p>
      {item.authority && <p className="muted">Authority: {item.authority}</p>}
      {item.special_notice && <p className="notice notice-warn">{item.special_notice}</p>}
      <button className="link" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? "Hide" : "Details and board fields"}
      </button>
      {open && (
        <div className="stack">
          <p>{item.summary}</p>
          {/* Each string as the server mapped it: a document opens as a Doc chip; an older server's strings stay chips. */}
          {item.evidenceRefs ? <EvidenceEntries entries={item.evidenceRefs} /> : <Evidence items={item.evidence} />}
          <BoardFields key={item.id + item.history.length} item={item} statuses={BOARD_STATUSES} onSaved={(n) => { onSaved(n); setOpen(false); }} />
          {item.history.length > 0 && (
            <details>
              <summary>History ({item.history.length})</summary>
              <Timeline events={historyEvents(item.history)} />
            </details>
          )}
        </div>
      )}
    </article>
  );
}

export function BoardItemsView() {
  const [closed, setClosed] = useState(false);
  const r = useApi<{ found: boolean; items: BoardItemWithRefs[] }>(`/api/board-items?closed=${closed}`);
  const [patched, setPatched] = useState<Record<string, BoardItemWithRefs>>({});
  return (
    <div className="stack">
      <Card title="Board action items" actions={<label><input type="checkbox" checked={closed} onChange={(e) => setClosed(e.target.checked)} /> show closed</label>}>
        <p className="muted">Each item is a matter to decide, never the decision. Status, owner, meeting, and notes are the board's; the rest is what jason found.</p>
      </Card>
      <RemoteView r={r}>
        {(d) => {
          const items = d.items.map((i) => (patched[i.id] ? { ...i, ...patched[i.id] } : i));
          return (
            <Kanban
              lanes={closed ? BOARD_STATUSES : BOARD_STATUSES.filter((s) => s !== "closed")}
              items={items}
              laneOf={(i) => i.status}
              keyOf={(i) => i.id}
              render={(i) => <BoardItemCard item={i} onSaved={(n) => setPatched((p) => ({ ...p, [n.id]: n }))} />}
            />
          );
        }}
      </RemoteView>
    </div>
  );
}
