import { useState } from "react";
import { Badge, Card, Confirm, DueDate, Evidence, Kanban, Pill, RemoteView } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { BOARD_STATUSES, type BoardItem } from "./types";

type Fields = Pick<BoardItem, "status" | "owner" | "meeting" | "notes">;

/** One matter the board is asked to decide. jason's columns are read-only; the board's four are editable. */
export function BoardItemCard({ item, onSaved }: { item: BoardItem; onSaved: (next: BoardItem) => void }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Fields>({ status: item.status, owner: item.owner, meeting: item.meeting, notes: item.notes });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const changes = (Object.keys(draft) as (keyof Fields)[]).filter((k) => draft[k] !== item[k]);

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const body = Object.fromEntries(changes.map((k) => [k, draft[k]]));
      onSaved(await postJson<BoardItem>(`/api/board-items/${encodeURIComponent(item.id)}`, body));
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

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
          <Evidence items={item.evidence} />
          <div className="fields">
            <label>
              Status
              <select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })}>
                {BOARD_STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Owner <input value={draft.owner} onChange={(e) => setDraft({ ...draft, owner: e.target.value })} />
            </label>
            <label>
              Meeting <input value={draft.meeting} placeholder="YYYY-MM-DD" onChange={(e) => setDraft({ ...draft, meeting: e.target.value })} />
            </label>
            <label className="wide">
              Notes <textarea value={draft.notes} rows={2} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
            </label>
          </div>
          {changes.length > 0 && (
            <Confirm
              busy={busy}
              onConfirm={save}
              summary={
                <ul>
                  {changes.map((k) => (
                    <li key={k}>
                      {k}: <s>{String(item[k]) || "—"}</s> → {draft[k] || "—"}
                    </li>
                  ))}
                </ul>
              }
            >
              Save board fields
            </Confirm>
          )}
          {error && <p className="notice notice-error">{error}</p>}
          {item.history.length > 0 && (
            <details>
              <summary>History ({item.history.length})</summary>
              <ul className="muted">
                {item.history.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </article>
  );
}

export function BoardItemsView() {
  const [closed, setClosed] = useState(false);
  const r = useApi<{ found: boolean; items: BoardItem[] }>(`/api/board-items?closed=${closed}`);
  const [patched, setPatched] = useState<Record<string, BoardItem>>({});
  return (
    <div className="stack">
      <Card title="Board action items" actions={<label><input type="checkbox" checked={closed} onChange={(e) => setClosed(e.target.checked)} /> show closed</label>}>
        <p className="muted">Each item is a matter to decide, never the decision. Status, owner, meeting, and notes are the board's; the rest is what jason found.</p>
      </Card>
      <RemoteView r={r}>
        {(d) => {
          const items = d.items.map((i) => patched[i.id] ?? i);
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
