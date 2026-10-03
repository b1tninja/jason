import { useState } from "react";
import { Confirm } from "./Confirm";
import { postJson } from "../lib/api";

/** The board's own fields on an action item. jason's columns are elsewhere and read-only; these four are the board's. */
export interface BoardFieldsItem {
  id: string;
  status: string;
  owner: string;
  meeting: string;
  notes: string;
  /** The item's trail, one line each; a save appends to it. */
  history: string[];
}

type Field = "status" | "owner" | "meeting" | "notes";
const FIELDS: { key: Field; label: string }[] = [
  { key: "status", label: "Status" },
  { key: "owner", label: "Owner" },
  { key: "meeting", label: "Meeting" },
  { key: "notes", label: "Notes" },
];
const show = (k: Field, v: string) => v || (k === "meeting" ? "not scheduled" : "(blank)");
const DEFAULT_STATUSES = ["open", "proposed", "on agenda", "in progress", "deferred", "closed"] as const;

/** The board's fields behind `Confirm`. The summary lists "Label: old → new" and ends "Saved to the board fields only.";
 * with nothing changed it says "No changes." A save posts the changed fields to `/api/board-items/<id>`; the item that
 * comes back has the save appended to its history (the server writes that line), so the Timeline grows by one. */
export function BoardFields<T extends BoardFieldsItem>({ item, onSaved, statuses = DEFAULT_STATUSES, today }: {
  item: T;
  onSaved: (next: T) => void;
  statuses?: readonly string[];
  /** The day a locally appended history line carries when the server did not append one. */
  today?: string;
}) {
  const [draft, setDraft] = useState<Record<Field, string>>({ status: item.status, owner: item.owner, meeting: item.meeting, notes: item.notes });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const changes = FIELDS.filter((f) => (draft[f.key] || "") !== (item[f.key] || ""));
  const set = (k: Field, v: string) => setDraft((d) => ({ ...d, [k]: v }));
  const reset = () => setDraft({ status: item.status, owner: item.owner, meeting: item.meeting, notes: item.notes });

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const body = Object.fromEntries(changes.map((f) => [f.key, draft[f.key]]));
      const next = await postJson<T>(`/api/board-items/${encodeURIComponent(item.id)}`, body);
      const day = today ?? new Date().toISOString().slice(0, 10);
      const history = next.history.length > item.history.length ? next.history : [...next.history, `${day}: ${changes.map((f) => f.label.toLowerCase()).join(", ")} changed by the board`];
      onSaved({ ...next, history });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="board-fields">
      <div className="fields">
        <label>
          Status
          <select value={draft.status} onChange={(e) => set("status", e.target.value)}>
            {statuses.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>
          Owner <input value={draft.owner} onChange={(e) => set("owner", e.target.value)} />
        </label>
        <label>
          Meeting <input value={draft.meeting} placeholder="YYYY-MM-DD" onChange={(e) => set("meeting", e.target.value)} />
        </label>
        <label className="wide">
          Notes <textarea value={draft.notes} rows={2} onChange={(e) => set("notes", e.target.value)} />
        </label>
      </div>
      <div className="row wrap board-fields-foot">
        {changes.length > 0 ? (
          <>
            <Confirm
              busy={busy}
              onConfirm={save}
              summary={
                <>
                  <p className="muted">The board's fields {changes.map((f) => f.key).join(", ")} on this item:</p>
                  <ul>
                    {changes.map((f) => (
                      <li key={f.key}>{f.label}: <s>{show(f.key, item[f.key])}</s> → {show(f.key, draft[f.key])}</li>
                    ))}
                  </ul>
                  <p>Saved to the board fields only.</p>
                </>
              }
            >
              Save board fields
            </Confirm>
            <button className="link" onClick={reset} disabled={busy}>Discard</button>
          </>
        ) : (
          <span className="muted">No changes.</span>
        )}
      </div>
      {error && <p className="notice notice-error">{error}</p>}
    </div>
  );
}
