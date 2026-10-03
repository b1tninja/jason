import { useEffect, useState } from "react";
import { Badge, Card, Command, Confirm, EmptyState, Kanban, Pill, RemoteView } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useHash } from "../lib/useHash";

export interface Clip { at: string; source: string; text: string; label: string; args: Record<string, unknown> }
export interface Canvas {
  key: string; title: string; question: string; status: string; matter: string; duty: string; notes: string;
  clips: Clip[]; links: { label: string; url: string }[]; checklist: { text: string; done: boolean }[]; created: string; updated: string; history: string[];
}
type Summary = Omit<Canvas, "clips"> & { clips: number };
interface Listing { found?: boolean; note?: string; count: number; statuses: string[]; canvases: Summary[] }

const DUTIES = ["", "Governing documents", "Developer file", "Notice", "Meetings", "Elections", "Records", "Annual disclosures", "Money", "Assessments", "Insurance", "Maintenance", "Exclusive use", "Architecture", "Protected uses", "Transfers", "Discipline", "Manager's own duties"];

function NewCanvas({ onMade }: { onMade: (key: string) => void }) {
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [duty, setDuty] = useState("");
  const [error, setError] = useState("");
  const make = async () => {
    try {
      const c = await postJson<Canvas>("/api/canvases", { title, question, duty });
      onMade(c.key);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <Card title="Open a canvas">
      <div className="fields">
        <label>Topic <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Reserve loan: restore by March" /></label>
        <label>Duty <select value={duty} onChange={(e) => setDuty(e.target.value)}>{DUTIES.map((d) => <option key={d} value={d}>{d || "—"}</option>)}</select></label>
        <label className="wide">The question <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What will the board be asked, or what is being found out?" /></label>
      </div>
      <div className="row"><button className="primary" onClick={make} disabled={!title.trim()}>Open</button>{error && <span className="notice notice-error">{error}</span>}</div>
    </Card>
  );
}

/** The canvases as lanes by status: research, preparing, on agenda, done. */
export function CanvasList({ go }: { go: (key: string) => void }) {
  const r = useApi<Listing>("/api/canvases");
  const [made, setMade] = useState(0);
  useEffect(() => { if (made) r.reload(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [made]);
  return (
    <div className="stack">
      <p className="muted">A canvas is the work before a board item: the question, your notes, clips of what the records show, links, and a checklist. jason reads it as research; it decides nothing.</p>
      <NewCanvas onMade={(k) => { setMade((n) => n + 1); go(k); }} />
      <RemoteView r={r}>
        {(d) => d.count === 0 ? <EmptyState>No canvases yet.</EmptyState> : (
          <Kanban lanes={d.statuses} items={d.canvases} laneOf={(c) => c.status} keyOf={(c) => c.key} render={(c) => (
            <article className="item">
              <header className="row wrap">{c.duty && <Badge>{c.duty}</Badge>}{c.matter && <Badge tone="good">{`item ${c.matter}`}</Badge>}<span className="muted">{c.clips} clips</span></header>
              <h4><button className="link" onClick={() => go(c.key)}>{c.title}</button></h4>
              {c.question && <p className="ask">{c.question}</p>}
              <p className="muted">updated {c.updated.slice(0, 10)}</p>
            </article>
          )} />
        )}
      </RemoteView>
    </div>
  );
}

/** One canvas: notes, checklist, links, and the clips kept from the tools, with the commands that take it to the board. */
export function CanvasWorkspace({ keyName, back }: { keyName: string; back: () => void }) {
  const r = useApi<{ found: boolean; canvas: Canvas; note?: string }>(`/api/canvases?key=${encodeURIComponent(keyName)}`);
  return (
    <RemoteView r={r}>
      {(d) => <Editor initial={d.canvas} back={back} />}
    </RemoteView>
  );
}

function Editor({ initial, back }: { initial: Canvas; back: () => void }) {
  const [c, setC] = useState(initial);
  const [draft, setDraft] = useState({ title: c.title, question: c.question, duty: c.duty, matter: c.matter, notes: c.notes, status: c.status });
  const [newLink, setNewLink] = useState({ label: "", url: "" });
  const [newTask, setNewTask] = useState("");
  const [clip, setClip] = useState({ source: "", label: "", text: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = (Object.keys(draft) as (keyof typeof draft)[]).filter((k) => draft[k] !== c[k]);

  const put = async (body: Record<string, unknown>) => {
    setBusy(true); setError("");
    try {
      const next = await postJson<Canvas>(`/api/canvases/${encodeURIComponent(c.key)}`, body);
      setC(next);
      setDraft({ title: next.title, question: next.question, duty: next.duty, matter: next.matter, notes: next.notes, status: next.status });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div className="stack">
      <div className="row wrap">
        <button onClick={back}>← Canvases</button>
        <Pill word={c.status} />
        {c.duty && <Badge>{c.duty}</Badge>}
        <span className="muted">opened {c.created.slice(0, 10)} · updated {c.updated.slice(0, 10)}</span>
      </div>
      <div className="grid-2">
        <Card title="Notes" actions={dirty.length > 0 && <button className="primary" onClick={() => put(Object.fromEntries(dirty.map((k) => [k, draft[k]])))} disabled={busy}>Save</button>}>
          <div className="fields">
            <label className="wide">Topic <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
            <label className="wide">The question <input value={draft.question} onChange={(e) => setDraft({ ...draft, question: e.target.value })} /></label>
            <label>Status <select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })}>{["research", "preparing", "on agenda", "done"].map((s) => <option key={s}>{s}</option>)}</select></label>
            <label>Duty <select value={draft.duty} onChange={(e) => setDraft({ ...draft, duty: e.target.value })}>{DUTIES.map((d) => <option key={d} value={d}>{d || "—"}</option>)}</select></label>
            <label className="wide">Board item id, once one exists <input value={draft.matter} onChange={(e) => setDraft({ ...draft, matter: e.target.value })} placeholder="reserve-loan-not-restored" /></label>
            <label className="wide">Notes (Markdown) <textarea rows={12} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label>
          </div>
          {error && <p className="notice notice-error">{error}</p>}
        </Card>
        <div className="stack">
          <Card title={`Clips (${c.clips.length})`}>
            <p className="muted">What the records show, kept from a tool with where it came from. A clip is evidence, not a finding.</p>
            {c.clips.map((k, i) => (
              <blockquote key={i} className="passage">
                {k.label && <strong>{k.label} </strong>}<span>{k.text}</span>
                <footer className="muted"><code className="chip">{k.source}</code> {k.at.slice(0, 10)}{Object.keys(k.args).length > 0 && <> · {JSON.stringify(k.args)}</>}</footer>
              </blockquote>
            ))}
            <div className="fields">
              <label>Source <input value={clip.source} onChange={(e) => setClip({ ...clip, source: e.target.value })} placeholder="reserve_transfers, a URL, a file" /></label>
              <label>Shows <input value={clip.label} onChange={(e) => setClip({ ...clip, label: e.target.value })} /></label>
              <label className="wide">Text <textarea rows={3} value={clip.text} onChange={(e) => setClip({ ...clip, text: e.target.value })} /></label>
            </div>
            <button onClick={() => put({ clip }).then(() => setClip({ source: "", label: "", text: "" }))} disabled={busy || !clip.text.trim()}>Keep clip</button>
          </Card>
          <Card title={`Checklist (${c.checklist.filter((t) => t.done).length}/${c.checklist.length})`}>
            <ul className="findings">
              {c.checklist.map((t, i) => (
                <li key={i}><label><input type="checkbox" checked={t.done} onChange={(e) => put({ checklist: c.checklist.map((x, j) => (j === i ? { ...x, done: e.target.checked } : x)) })} /> {t.done ? <s>{t.text}</s> : t.text}</label></li>
              ))}
            </ul>
            <div className="row"><input className="search" aria-label="New task" value={newTask} onChange={(e) => setNewTask(e.target.value)} placeholder="find the resolution" /><button onClick={() => put({ checklist: [...c.checklist, { text: newTask, done: false }] }).then(() => setNewTask(""))} disabled={!newTask.trim() || busy}>Add</button></div>
          </Card>
          <Card title={`Links (${c.links.length})`}>
            <ul>{c.links.map((l, i) => <li key={i}><a href={l.url} target="_blank" rel="noreferrer">{l.label || l.url}</a></li>)}</ul>
            <div className="row wrap"><input className="search" aria-label="Link label" value={newLink.label} onChange={(e) => setNewLink({ ...newLink, label: e.target.value })} placeholder="label" /><input className="search" aria-label="Link URL" value={newLink.url} onChange={(e) => setNewLink({ ...newLink, url: e.target.value })} placeholder="https://" /><button onClick={() => put({ links: [...c.links, newLink] }).then(() => setNewLink({ label: "", url: "" }))} disabled={!newLink.url.trim() || busy}>Add</button></div>
          </Card>
        </div>
      </div>
      <Card title="To the board">
        <p className="muted">When the research is done, it becomes a board item (a matter to decide, never the decision) and a packet section. The page runs nothing.</p>
        {c.matter ? (
          <>
            <Command cmd={`jason board --set ${c.matter} --status "on agenda" --meeting YYYY-MM-DD --notes "canvas: ${c.key}"`} note="Notices the board item for a meeting and points it at this canvas; the board's own columns." />
            <Command cmd="jason board --packet --doc --yes" note={`Writes the packet with item ${c.matter} as a section; a Drive write, so a person passes --yes.`} />
          </>
        ) : (
          <p className="muted">No board item yet. jason's reviews add items (`jason board` lists them), and the board adds its own on the Sheet; enter the item's id above once it exists.</p>
        )}
        {dirty.includes("status") && draft.status === "on agenda" && (
          <Confirm summary={<p>Mark this canvas on agenda. The board item and the meeting are set separately.</p>} onConfirm={() => put({ status: "on agenda" })}>Mark on agenda</Confirm>
        )}
        {c.history.length > 0 && <details><summary>History ({c.history.length})</summary><ul className="muted">{c.history.map((h, i) => <li key={i}>{h}</li>)}</ul></details>}
      </Card>
    </div>
  );
}

export function CanvasesView() {
  const [hash, go] = useHash("canvases");
  const key = hash.startsWith("canvases/") ? hash.slice("canvases/".length) : "";
  if (key) return <CanvasWorkspace keyName={key} back={() => go("canvases")} />;
  return <CanvasList go={(k) => go(`canvases/${k}`)} />;
}
