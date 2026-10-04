import { useEffect, useState } from "react";
import { Confirm } from "./Confirm";
import { Evidence } from "./Evidence";
import { EvidenceEntries } from "./EvidenceEntries";
import { Markdown } from "./Markdown";
import { Pill } from "./Pill";
import { RemoteView } from "./Remote";
import { useApi } from "../lib/useApi";
import type { EvidenceEntry } from "../lib/docref";
import { DOCK_EVENT, dockWrite } from "./Dock";

/** `sourceRefs` are the saved sources as the loader mapped them, one for one (a reference, a command, or text); an older
 * server leaves them out. */
export interface DockNote { id: string; title: string; status: string; body: string; sources: string[]; sourceRefs?: EvidenceEntry[]; created: string; updated: string; by: string; history?: string[] }
export interface DockNotes { found?: boolean; note?: string; count: number; notes: DockNote[]; statuses: string[]; caveat: string }

const NOTE_CAVEAT = "Working notes, not association records.";

/** The sources being edited as entries: a saved source takes the loader's reference; one added since the last save is
 * text until it is saved and the server maps it. Null when the loader gave no references. */
function sourceEntries(note: DockNote, sources: readonly string[]): EvidenceEntry[] | null {
  const refs = note.sourceRefs;
  if (!refs || refs.length !== note.sources.length) return null;
  const saved = new Map(note.sources.map((s, i) => [s, refs[i]] as const));
  return sources.map((s) => saved.get(s) ?? { text: s });
}

/** Working notes: a title, a status, a Markdown body, and the sources a note rests on. A note can hand a follow-up to
 * the action register. Notes are a person's working material, never association records; the label says so. */
export function Scratchpad({ me }: { me?: string }) {
  const r = useApi<DockNotes>("/api/dock?part=notes");
  const [sel, setSel] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [edit, setEdit] = useState<{ title: string; status: string; body: string; sources: string[] } | null>(null);
  const [src, setSrc] = useState("");
  const [preview, setPreview] = useState(false);
  const [sent, setSent] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const by = (me ?? "").trim() || name.trim();
  useEffect(() => {
    const on = () => r.reload();
    window.addEventListener(DOCK_EVENT, on);
    return () => window.removeEventListener(DOCK_EVENT, on);
  }, [r.reload]);

  const write = async <T,>(key: string, body: Parameters<typeof dockWrite>[1]): Promise<T | undefined> => {
    setError("");
    try { return await dockWrite<T>(key, body); } catch (e) { setError((e as Error).message); return undefined; }
  };

  return (
    <RemoteView r={r}>
      {(d) => {
        const cur = d.notes.find((n) => n.id === sel);
        const e = edit ?? (cur ? { title: cur.title, status: cur.status, body: cur.body, sources: cur.sources } : null);
        const changes = cur && e ? (["title", "status", "body", "sources"] as const).filter((k) => JSON.stringify(e[k]) !== JSON.stringify(cur[k])) : [];
        return (
          <div className="stack dock-panel">
            {!me && (
              <label className="dock-sub row">Your name
                <input value={name} onChange={(ev) => setName(ev.target.value)} placeholder="Who is writing" aria-label="Your name" />
              </label>
            )}
            {!cur && (
              <>
                <div className="dock-task-head">
                  <span className="dock-sub">{d.count} {d.count === 1 ? "note" : "notes"}</span>
                  <Confirm busy={!by} summary={<span>Open a new working note by {by}. {NOTE_CAVEAT}</span>}
                    onConfirm={async () => { const n = await write<DockNote>("new", { action: "note_add", by, title: "Untitled" }); if (n) { setSel(n.id); setEdit(null); } }}>
                    New note
                  </Confirm>
                </div>
                <ul className="dock-list dock-notes">
                  {d.notes.map((n) => (
                    <li key={n.id}>
                      <button type="button" className="dock-note" onClick={() => { setSel(n.id); setEdit(null); setSrc(""); setPreview(false); }}>
                        <span className="dock-task-head"><strong>{n.title || "Untitled"}</strong><Pill word={n.status} /></span>
                        <span className="dock-sub dock-preview">{n.body}</span>
                        <span className="dock-sub">updated {n.updated.slice(0, 10)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {cur && e && (
              <>
                <button type="button" className="link dock-back" onClick={() => { setSel(null); setEdit(null); }}>← All notes</button>
                <input value={e.title} onChange={(ev) => setEdit({ ...e, title: ev.target.value })} aria-label="Title" className="dock-title" />
                <label className="dock-sub row">Status
                  <select value={e.status} onChange={(ev) => setEdit({ ...e, status: ev.target.value })} aria-label="Status">
                    {d.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <Pill word={e.status} />
                  <span className="dock-right">updated {cur.updated.slice(0, 10)}</span>
                </label>
                <div className="dock-task-head"><span className="dock-sub">Notes (Markdown)</span><button type="button" className="link" onClick={() => setPreview(!preview)}>{preview ? "Edit" : "Preview"}</button></div>
                {preview ? <div className="dock-md"><Markdown text={e.body || "_Nothing written yet._"} /></div>
                  : <textarea rows={10} value={e.body} onChange={(ev) => setEdit({ ...e, body: ev.target.value })} aria-label="Notes" />}
                <div className="stack-tight">
                  <span className="dock-sub">Sources</span>
                  {(() => {
                    const entries = sourceEntries(cur, e.sources);
                    return entries ? <EvidenceEntries label="" entries={entries} /> : <Evidence label="" items={e.sources} />;
                  })()}
                  <div className="dock-add-row">
                    <input value={src} onChange={(ev) => setSrc(ev.target.value)} placeholder="A record, a Drive path, or a code section" aria-label="Add a source" />
                    <button type="button" onClick={() => { if (src.trim()) { setEdit({ ...e, sources: [...e.sources, src.trim()] }); setSrc(""); } }}>Add</button>
                  </div>
                </div>
                <div className="row wrap dock-actions">
                  <Confirm busy={!by || changes.length === 0}
                    summary={<span>Save {changes.join(", ") || "nothing"} on "{e.title || "Untitled"}" by {by}. {NOTE_CAVEAT}</span>}
                    onConfirm={async () => { const n = await write<DockNote>(cur.id, { action: "note_update", by, ...Object.fromEntries(changes.map((k) => [k, e[k]])) }); if (n) setEdit(null); }}>
                    Save note
                  </Confirm>
                  <Confirm busy={!by}
                    summary={<span>Add "Follow up: {e.title || "Untitled"}" to the action register with source Scratchpad, recorded by {by}; no owner or due date until a person sets them.</span>}
                    onConfirm={async () => { const t = await write("new", { action: "task_add", by, text: `Follow up: ${e.title || "Untitled"}`, source: "scratchpad" }); if (t) setSent({ ...sent, [cur.id]: true }); }}>
                    Add a follow-up to the register
                  </Confirm>
                  {sent[cur.id] && <span className="dock-sub dock-good">On the action register.</span>}
                </div>
              </>
            )}
            {error && <p className="notice notice-error">{error}</p>}
            <p className="dock-sub dock-caveat">{d.caveat || NOTE_CAVEAT} Notes live in jason's dock store until a person files them somewhere.</p>
          </div>
        );
      }}
    </RemoteView>
  );
}
