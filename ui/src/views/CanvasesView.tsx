import { useEffect, useState } from "react";
import { Badge, Card, Command, Confirm, Doc, Embed, EmptyState, Kanban, Markdown, Pill, RemoteView, type Attachment, type DocRef, type EmbedKind } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useHash } from "../lib/useHash";

/** A clip; `doc` is its source as a document reference when the source names one (an address, a path under data/, a
 * citation), from the loader. */
export interface Clip { at: string; source: string; text: string; label: string; args: Record<string, unknown>; doc?: DocRef }
/** An attachment; `doc` is the Drive file or the photo or PDF under data/ it names, from the loader. */
export type CanvasAttachment = Attachment & { doc?: DocRef };
export interface Canvas {
  key: string; title: string; question: string; status: string; matter: string; duty: string; notes: string;
  clips: Clip[]; links: { label: string; url: string }[]; checklist: { text: string; done: boolean }[]; attachments: CanvasAttachment[]; created: string; updated: string; history: string[];
}
const KINDS: { kind: EmbedKind; label: string }[] = [
  { kind: "doc", label: "Google Doc" }, { kind: "sheet", label: "Google Sheet" }, { kind: "slides", label: "Google Slides" }, { kind: "form", label: "Google Form" },
  { kind: "drive", label: "Drive file" }, { kind: "image", label: "Photo (data/ path or URL)" }, { kind: "pdf", label: "PDF (data/ path or URL)" }, { kind: "url", label: "Web page" },
  { kind: "calendar", label: "Google Calendar (calendar id)" }, { kind: "zoom", label: "Zoom recording (share link)" }, { kind: "audio", label: "Audio (data/ path or URL)" },
  { kind: "map", label: "Map (address)" }, { kind: "chart", label: "Sheets chart (published chart link, or Sheet id)" }, { kind: "thread", label: "Gmail thread (link card)" },
];
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
  const [preview, setPreview] = useState(true);
  const [newAtt, setNewAtt] = useState<Attachment>({ kind: "doc", ref: "", title: "" });
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
            <label className="wide">Notes (Markdown; a ```mermaid fence draws a diagram; put a photo on the canvas below to show it beside the notes)
              <textarea rows={12} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
            </label>
          </div>
          <div className="row"><button className="link" onClick={() => setPreview((p) => !p)} aria-pressed={preview}>{preview ? "Hide preview" : "Show preview"}</button></div>
          {preview && draft.notes.trim() && <div className="preview"><Markdown text={draft.notes} /></div>}
          {error && <p className="notice notice-error">{error}</p>}
        </Card>
        <div className="stack">
          <Card title={`Clips (${c.clips.length})`}>
            <p className="muted">What the records show, kept from a tool with where it came from. A clip is evidence, not a finding.</p>
            {c.clips.map((k, i) => (
              <blockquote key={i} className="passage">
                {k.label && <strong>{k.label} </strong>}<span>{k.text}</span>
                <footer className="muted">{k.doc ? <Doc doc={k.doc} variant="chip" /> : <code className="chip">{k.source}</code>} {k.at.slice(0, 10)}{Object.keys(k.args).length > 0 && <> · {JSON.stringify(k.args)}</>}</footer>
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
      <Card title={`On the canvas (${(c.attachments ?? []).length})`}>
        <p className="muted">A Google file, or a photo or PDF under data/, shows as jason's copy: opening it is a view logged under your name, and a Drive file keeps Open in Google beside it. A calendar, map, published chart, or Zoom recording loads when you click it.</p>
        <div className="embeds">
          {(c.attachments ?? []).map((a, i) => (
            <div key={i} className="stack">
              <AttachmentView a={a} />
              <button className="link" onClick={() => put({ attachments: (c.attachments ?? []).filter((_, j) => j !== i).map(plain) })}>remove from the canvas</button>
            </div>
          ))}
        </div>
        <div className="fields">
          <label>Kind <select value={newAtt.kind} onChange={(e) => setNewAtt({ ...newAtt, kind: e.target.value as EmbedKind })}>{KINDS.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}</select></label>
          <label>Title <input value={newAtt.title ?? ""} onChange={(e) => setNewAtt({ ...newAtt, title: e.target.value })} /></label>
          <label className="wide">Link, Google file id, or path under data/ <input value={newAtt.ref} onChange={(e) => setNewAtt({ ...newAtt, ref: e.target.value })} placeholder="a Google file's link or id, or photos/east-bed.jpg" /></label>
        </div>
        <Picker onPick={(a) => setNewAtt(a)} />
        <button onClick={() => put({ attachments: [...(c.attachments ?? []).map(plain), newAtt] }).then(() => setNewAtt({ kind: "doc", ref: "", title: "" }))} disabled={!newAtt.ref.trim() || busy}>Add to the canvas</button>
      </Card>
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

/** An attachment as the store keeps it: its reference is the loader's, built afresh on each read. */
const plain = ({ doc: _doc, ...a }: CanvasAttachment): Attachment => a;

const DRIVE_KIND: Partial<Record<EmbedKind, "doc" | "sheet" | "slides" | "drive">> = { doc: "doc", sheet: "sheet", slides: "slides", form: "drive", drive: "drive" };

/** One attachment: the document it names as a `Doc` (a photo or a recording under data/ inline, a Drive file or a PDF
 * as a card), from the loader's reference; anything else (a calendar, a map, a chart, a Zoom share page, remote audio,
 * a web page, a mail thread) as `Embed` shows it. */
function AttachmentView({ a }: { a: CanvasAttachment }) {
  if (!a.doc) return <Embed a={plain(a)} />;
  const driveKind = DRIVE_KIND[a.kind];
  return <Doc doc={a.doc} variant={a.kind === "image" || a.kind === "audio" ? "inline" : "card"} {...(driveKind ? { driveKind } : {})} />;
}

interface DriveFile { id: string; name: string; path: string; kind: EmbedKind; link: string }
interface Album { slug: string; label: string; count: number; items: { filename: string; path: string; createTime: string }[] }
interface Recording { date: string; topic: string; uuid: string; shareUrl: string; playUrl: string; files: { type: string; name: string; path: string }[] }
interface Embeds { found: boolean; note?: string; calendarId: string; timeZone: string; recordings: Recording[] }

const isAudioFile = (f: { type: string; name: string }) => f.type === "audio" || /\.(m4a|mp3|wav|ogg)$/i.test(f.name);

/** Search the Drive catalog, the photo albums on disk, and the kept Zoom recordings and calendar; a pick fills the attachment form. */
function Picker({ onPick }: { onPick: (a: Attachment) => void }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => { const h = setTimeout(() => setDebounced(q), 300); return () => clearTimeout(h); }, [q]);
  const drive = useApi<{ found: boolean; note?: string; files: DriveFile[] }>(`/api/drive-files?q=${encodeURIComponent(debounced)}&limit=12`);
  const photos = useApi<{ found: boolean; note?: string; albums: Album[] }>("/api/photos");
  const embeds = useApi<Embeds>("/api/embeds");
  const em = embeds.status === "ready" && embeds.data.found !== false ? embeds.data : null;
  const recordings = em?.recordings ?? [];
  return (
    <details className="picker">
      <summary>Pick from Drive, the photo albums, or the recordings</summary>
      <input className="search" aria-label="Search Drive" placeholder="Search Drive…" value={q} onChange={(e) => setQ(e.target.value)} />
      {drive.status === "ready" && drive.data.found !== false && (
        <ul className="picks">{(drive.data.files ?? []).map((f) => <li key={f.id}><button className="link" onClick={() => onPick({ kind: f.kind, ref: f.id, title: f.name })}>{f.name}</button> <span className="muted">{f.path} · {f.kind}</span></li>)}</ul>
      )}
      {drive.status === "ready" && drive.data.found === false && <p className="muted">{drive.data.note}</p>}
      {photos.status === "ready" && photos.data.found !== false && (photos.data.albums ?? []).map((al) => (
        <details key={al.slug}><summary>{al.label || al.slug} <span className="muted">({al.count})</span></summary>
          <ul className="picks">{(al.items ?? []).map((i) => <li key={i.path}><button className="link" onClick={() => onPick({ kind: "image", ref: i.path, title: i.filename })}>{i.filename}</button> <span className="muted">{i.createTime?.slice(0, 10)}</span></li>)}</ul>
        </details>
      ))}
      {em && em.calendarId && (
        <p><button className="link" onClick={() => onPick({ kind: "calendar", ref: em.calendarId, title: "Association calendar", opts: { mode: "AGENDA", tz: em.timeZone } })}>The association's calendar</button></p>
      )}
      {recordings.length > 0 && (
        <details><summary>Zoom recordings <span className="muted">({recordings.length})</span></summary>
          <ul className="picks">
            {recordings.map((rec) => {
              const title = `${rec.topic} (${rec.date})`;
              return (
                <li key={rec.uuid || `${rec.date}-${rec.topic}`}>
                  {rec.shareUrl || rec.playUrl ? <button className="link" onClick={() => onPick({ kind: "zoom", ref: rec.shareUrl || rec.playUrl, title })}>{rec.topic}</button> : <span>{rec.topic} <span className="muted">(no share link on file; the files below)</span></span>} <span className="muted">{rec.date}</span>
                  {(rec.files ?? []).filter(isAudioFile).map((f) => (
                    <span key={f.path}> · <button className="link" onClick={() => onPick({ kind: "audio", ref: f.path, title })}>{f.name || "audio"}</button></span>
                  ))}
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </details>
  );
}

export function CanvasesView() {
  const [hash, go] = useHash("canvases");
  const key = hash.startsWith("canvases/") ? hash.slice("canvases/".length) : "";
  if (key) return <CanvasWorkspace keyName={key} back={() => go("canvases")} />;
  return <CanvasList go={(k) => go(`canvases/${k}`)} />;
}
