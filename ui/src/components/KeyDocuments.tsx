import { useState } from "react";
import { Badge, type Tone } from "./Badge";
import { Caveats } from "./Caveats";
import { Confirm } from "./Confirm";
import { Doc, type DocStatic } from "./Doc";
import { postJson } from "../lib/api";
import type { DocRef } from "../lib/docref";

/** One copy jason sees without a person's link: a Drive pin in the specification, or a recorded copy on disk. `doc` is
 * its document reference (`drive:<id>`, or `file:<path>` as "Recorded copy"), shown as a `Doc` chip. */
export interface KeyCopy { kind: "drive" | "disk" | string; ref: string; name: string; source: string; url?: string; doc?: DocRef }
/** A copy a person linked here (`file`, `drive`, `payhoa`, `upload`), and who unlinked it when they did; `doc` is its
 * document reference when jason can show it. */
export interface KeyLink {
  id: string; kind: string; ref: string; name: string; by: string; at: string; note?: string; url?: string; sha256?: string;
  unlinked?: { by: string; at: string; note?: string } | null; doc?: DocRef;
}
/** A locator's find for this entry: a lead, not a pin. */
export interface KeyLead { number?: string; recorded?: string; filing?: string; tie?: string; via?: string; source?: string }
export interface KeyEntry {
  key: string; item: string; title: string; number: string; recorded: string; phase?: number | null; role?: string; filing?: string;
  supersededBy?: string; sections?: string[]; status: KeyStatusWord; statusWhy?: string;
  copies: KeyCopy[]; links: KeyLink[]; unlinked?: KeyLink[]; leads: KeyLead[]; notes: string[]; sources?: string[];
}
export interface KeyGroup { item: string; title: string; why?: string; source?: string; recorded?: boolean; repeats?: boolean; entries: KeyEntry[] }
export type KeyStatusWord = "expected" | "located" | "held" | "linked" | "missing";
/** The `/api/key-documents` payload (`jason.tasks.key_documents.checklist`). */
export interface KeyDocumentsData {
  found?: boolean; note?: string; association?: string; county?: string; counts?: Record<string, number>;
  statuses?: { value: KeyStatusWord; meaning: string }[]; groups: KeyGroup[];
  limits?: { maxUploadBytes: number; suffixes: string[] }; notes?: string[]; caveats?: string[];
}

type Post = (path: string, body: unknown) => Promise<unknown>;

const TONE: Record<KeyStatusWord, Tone> = { linked: "good", held: "good", located: "neutral", expected: "neutral", missing: "bad" };
const KIND_WORD: Record<string, string> = { file: "file", upload: "uploaded", drive: "Drive", payhoa: "PayHOA", disk: "on disk" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Oct 3, 2099" in a `<time>` with the ISO date inside. */
export function Day({ iso }: { iso?: string | null }) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  if (!m) return null;
  return <time dateTime={m[0]}>{`${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}`}</time>;
}

function StatusWord({ word, why }: { word: KeyStatusWord; why?: string }) {
  return <span title={why}><Badge tone={TONE[word] ?? "neutral"}>{word}</Badge></span>;
}

/** The key documents checklist: each document with its recording number, its status as a word, the copies jason sees,
 * the copies people linked (open, unlink), the locator's lead labeled as a lead, and a link, upload, or status action
 * behind a `Confirm` in a person's name. Every write goes to `POST /api/write/key-documents/<key>`; nothing reaches
 * Drive, PayHOA, or the county. */
export function KeyDocuments({ data, by = "", onChanged, post = postJson, docProps }: {
  data: KeyDocumentsData; by?: string; onChanged?: () => void; post?: Post;
  /** Passed to each copy's `Doc` (previews, tests): the sign-in, the view, the private view. */
  docProps?: DocStatic;
}) {
  const [name, setName] = useState(by);
  const [show, setShow] = useState<"all" | "open">("all");
  if (data.found === false) return <p className="muted">{data.note ?? "Key documents are unavailable."}</p>;
  const counts = data.counts ?? {};
  const open = (e: KeyEntry) => e.status === "expected" || e.status === "located" || e.status === "missing";
  return (
    <div className="stack key-documents">
      <div className="row wrap" role="group" aria-label="Status counts">
        {(["linked", "held", "located", "expected", "missing"] as KeyStatusWord[]).map((w) => (
          <span key={w} className="row"><StatusWord word={w} why={data.statuses?.find((s) => s.value === w)?.meaning} /><span className="num">{counts[w] ?? 0}</span></span>
        ))}
      </div>
      <div className="row wrap">
        {!by && (
          <label className="row">Your name
            <input value={name} onChange={(ev) => setName(ev.target.value)} autoComplete="name" />
          </label>
        )}
        {by && <span className="muted">Writing as {by}</span>}
        <label className="row">Show
          <select value={show} onChange={(ev) => setShow(ev.target.value as "all" | "open")}>
            <option value="all">every document</option>
            <option value="open">not yet held or linked</option>
          </select>
        </label>
      </div>
      {data.groups.map((g) => {
        const rows = g.entries.filter((e) => show === "all" || open(e));
        if (show === "open" && !rows.length) return null;
        return (
          <section key={g.item} aria-labelledby={`kd-${g.item}`} className="stack-sm">
            <h3 id={`kd-${g.item}`}>{g.title}</h3>
            {g.why && <p className="muted">{g.why}</p>}
            {!rows.length ? <p className="muted">None on record yet. None on record is not none given.</p> : (
              <ul className="stack-sm" style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {rows.map((e) => <EntryRow key={e.key} entry={e} by={by || name} post={post} onChanged={onChanged} limits={data.limits} docProps={docProps} />)}
              </ul>
            )}
          </section>
        );
      })}
      {data.notes?.length ? <ul className="muted">{data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : null}
      <Caveats items={data.caveats} />
    </div>
  );
}

/** A copy by its document reference: a `Doc` chip (one logged view on a click) with its original ("Open in Google")
 * beside it; with no reference (a PayHOA document jason keeps no copy of), its name as text. Never a URL into data/. */
function CopyDoc({ doc, name, docProps }: { doc?: DocRef; name: string; docProps?: DocStatic }) {
  if (!doc) return <span>{name}</span>;
  return (
    <>
      <Doc doc={doc} variant="chip" {...docProps} />
      {doc.original && <> <a href={doc.original.url} target="_blank" rel="noreferrer">{doc.original.label}<span className="visually-hidden"> (opens in a new tab)</span></a></>}
    </>
  );
}

function EntryRow({ entry: e, by, post, onChanged, limits, docProps }: {
  entry: KeyEntry; by: string; post: Post; onChanged?: () => void; limits?: KeyDocumentsData["limits"]; docProps?: DocStatic;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [acting, setActing] = useState<"" | "link" | "status">("");
  const write = async (body: Record<string, unknown>, done: string) => {
    setBusy(true);
    setResult(null);
    try {
      await post(`/api/write/key-documents/${e.key.split("/").map(encodeURIComponent).join("/")}`, { ...body, by });
      setResult({ ok: true, text: done });
      setActing("");
      onChanged?.();
    } catch (err) {
      setResult({ ok: false, text: `${(err as Error).message}. Nothing was written.` });
    } finally {
      setBusy(false);
    }
  };
  const label = `${e.title}${e.number ? ` (${e.number})` : ""}`;
  return (
    <li className="card stack-sm" aria-label={label}>
      <div className="row wrap" style={{ justifyContent: "space-between" }}>
        <strong>{e.title}</strong>
        <StatusWord word={e.status} why={e.statusWhy} />
      </div>
      <div className="row wrap muted">
        {e.number ? <code>{e.number}</code> : <span>No recording number on record</span>}
        {e.recorded && <span>recorded <Day iso={e.recorded} /></span>}
        {e.phase != null && <span>phase {e.phase}</span>}
        {e.sections?.length ? <span>sections {e.sections.join(", ")}</span> : null}
      </div>
      {e.statusWhy && <p className="muted">{e.statusWhy}</p>}
      {e.supersededBy && <p className="notice-warn">Rescinded and superseded by <code>{e.supersededBy}</code>.</p>}
      {e.notes.map((n, i) => <p key={i} className="muted">{n}</p>)}
      {e.copies.length > 0 && (
        <div>
          <span className="muted">Copies jason sees</span>
          <ul>
            {e.copies.map((c) => (
              <li key={`${c.kind}:${c.ref}`}><Badge>{KIND_WORD[c.kind] ?? c.kind}</Badge> <CopyDoc doc={c.doc} name={c.name} docProps={docProps} />{" "}
                <span className="muted">· {c.kind === "disk" ? c.doc?.source ?? c.source : c.doc?.source ? `${c.doc.source} (${c.source})` : c.source}</span></li>
            ))}
          </ul>
        </div>
      )}
      {e.links.length > 0 && (
        <div>
          <span className="muted">Linked by a person</span>
          <ul>
            {e.links.map((l) => (
              <li key={l.id} className="row wrap">
                <Badge tone="good">{KIND_WORD[l.kind] ?? l.kind}</Badge>
                <CopyDoc doc={l.doc} name={l.name} docProps={docProps} />
                <span className="muted">by {l.by}, <Day iso={l.at} /></span>
                <Confirm label="Unlink" busy={busy || !by} onConfirm={() => write({ action: "unlink", link: l.id }, `Unlinked ${l.name} as ${by}. The file stays where it is.`)}
                  summary={<>Unlink <strong>{l.name}</strong> from {label} as {by || "(your name)"}. The file is not deleted; the record keeps who linked and who unlinked it.</>}>
                  Unlink
                </Confirm>
              </li>
            ))}
          </ul>
        </div>
      )}
      {e.leads.length > 0 && (
        <div className="notice">
          <span className="muted">Lead from the county index, not a pin: read the recorded copy before relying on it.</span>
          <ul>
            {e.leads.map((d, i) => (
              <li key={i}><code>{d.number}</code> {d.recorded && <Day iso={d.recorded} />} {d.filing} {d.tie && <span className="muted">· {d.tie}{d.via ? ` (${d.via})` : ""}</span>}</li>
            ))}
          </ul>
        </div>
      )}
      {(e.unlinked?.length ?? 0) > 0 && (
        <details>
          <summary className="muted">{e.unlinked!.length} unlinked</summary>
          <ul>{e.unlinked!.map((l) => <li key={l.id} className="muted">{l.name}: linked by {l.by}, unlinked by {l.unlinked?.by} <Day iso={l.unlinked?.at} /></li>)}</ul>
        </details>
      )}
      <div className="row wrap">
        <button className="link" aria-expanded={acting === "link"} onClick={() => setActing(acting === "link" ? "" : "link")}>Link or upload a copy</button>
        <button className="link" aria-expanded={acting === "status"} onClick={() => setActing(acting === "status" ? "" : "status")}>Record a status</button>
      </div>
      {acting === "link" && <LinkForm label={label} by={by} busy={busy} limits={limits} onWrite={write} />}
      {acting === "status" && <StatusForm label={label} by={by} busy={busy} onWrite={write} />}
      {!by && acting && <p className="muted" role="note">Give your name above: every write names its person.</p>}
      {result && <p role={result.ok ? "status" : "alert"} className={result.ok ? "notice notice-good" : "notice notice-error"}>{result.text}</p>}
    </li>
  );
}

type LinkWay = "drive" | "file" | "payhoa" | "upload";
const WAYS: { way: LinkWay; label: string; field: string; hint: string }[] = [
  { way: "drive", label: "A Drive file", field: "Drive link or id", hint: "The file's link, or the id inside it" },
  { way: "file", label: "A file under data/", field: "Path under data/", hint: "A file already in the data folder" },
  { way: "payhoa", label: "A PayHOA library document", field: "PayHOA document number", hint: "The number in the library's link" },
  { way: "upload", label: "Upload a file", field: "File to upload", hint: "Copied into data/key-documents; the original stays" },
];

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${Math.round(bytes / (1024 * 1024))} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).replace(/^data:[^,]*,/, ""));
    reader.onerror = () => reject(reader.error ?? new Error("the file could not be read"));
    reader.readAsDataURL(file);
  });
}

function LinkForm({ label, by, busy, limits, onWrite }: {
  label: string; by: string; busy: boolean; limits?: KeyDocumentsData["limits"];
  onWrite: (body: Record<string, unknown>, done: string) => Promise<void>;
}) {
  const [way, setWay] = useState<LinkWay>("drive");
  const [ref, setRef] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const cap = limits?.maxUploadBytes ?? 25 * 1024 * 1024;
  const tooBig = file != null && file.size > cap;
  const ready = way === "upload" ? file != null && !tooBig : ref.trim() !== "";
  const what = way === "upload" ? file?.name ?? "" : ref.trim();
  const go = async () => {
    if (way === "upload" && file) {
      const body = await readBase64(file);
      await onWrite({ action: "upload", name: file.name, base64: body, note }, `Uploaded ${file.name} and linked it as ${by}.`);
    } else {
      await onWrite({ action: "link", kind: way, ref: ref.trim(), note }, `Linked ${ref.trim()} as ${by}.`);
    }
  };
  const chosen = WAYS.find((w) => w.way === way)!;
  const hintId = `hint-${way}-${label.replace(/[^A-Za-z0-9]+/g, "-")}`;
  return (
    <fieldset className="stack-sm" disabled={busy}>
      <legend>Link or upload a copy of {label}</legend>
      <div className="row wrap" role="radiogroup" aria-label="Where the copy is">
        {WAYS.map((w) => (
          <label key={w.way} className="row"><input type="radio" name={`way-${label}`} checked={way === w.way} onChange={() => { setWay(w.way); setRef(""); setFile(null); }} />{w.label}</label>
        ))}
      </div>
      <div className="stack-tight">
        <label className="stack-tight">{chosen.field}
          {way === "upload"
            ? <input type="file" accept={(limits?.suffixes ?? [".pdf"]).join(",")} aria-describedby={hintId} onChange={(ev) => setFile(ev.target.files?.[0] ?? null)} />
            : <input value={ref} onChange={(ev) => setRef(ev.target.value)} aria-describedby={hintId} />}
        </label>
        <span id={hintId} className="muted">{chosen.hint}{way === "upload" ? `. At most ${size(cap)}; a larger file goes on Drive and is linked there.` : ""}</span>
      </div>
      {tooBig && <p role="alert" className="notice notice-error">{file!.name} is over {size(cap)}. Put it on Drive and link it there.</p>}
      <label className="stack-tight">Note (optional)<input value={note} onChange={(ev) => setNote(ev.target.value)} /></label>
      {ready && by && (
        <Confirm label="Link" busy={busy} onConfirm={() => void go()}
          summary={<>{way === "upload" ? "Upload and link" : "Link"} <strong>{what}</strong> to {label} as {by}.{way === "upload" ? " The file is copied into data/key-documents; nothing is sent anywhere." : " Nothing is copied or sent."}</>}>
          {way === "upload" ? "Upload and link" : "Link this copy"}
        </Confirm>
      )}
    </fieldset>
  );
}

const PERSON_WORDS: { value: KeyStatusWord; label: string }[] = [
  { value: "missing", label: "missing: the association does not hold it" },
  { value: "held", label: "held: a copy is kept elsewhere (say where)" },
  { value: "located", label: "located: the recording number is known" },
  { value: "expected", label: "expected: clear what was recorded" },
];

function StatusForm({ label, by, busy, onWrite }: {
  label: string; by: string; busy: boolean; onWrite: (body: Record<string, unknown>, done: string) => Promise<void>;
}) {
  const [value, setValue] = useState<KeyStatusWord>("missing");
  const [note, setNote] = useState("");
  const needsNote = value === "missing" && !note.trim();
  return (
    <fieldset className="stack-sm" disabled={busy}>
      <legend>Record a status for {label}</legend>
      <label className="stack-tight">Status
        <select value={value} onChange={(ev) => setValue(ev.target.value as KeyStatusWord)}>
          {PERSON_WORDS.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
        </select>
      </label>
      <label className="stack-tight">{value === "missing" ? "What was looked for, and where" : "Note (optional)"}
        <input value={note} onChange={(ev) => setNote(ev.target.value)} aria-invalid={needsNote || undefined} />
      </label>
      {needsNote && <p className="muted">Missing is a person's finding: say what was looked for and where.</p>}
      {!needsNote && by && (
        <Confirm label="Record" busy={busy} onConfirm={() => void onWrite({ action: "status", value, note }, `Recorded ${value} as ${by}.`)}
          summary={<>Record <strong>{value}</strong> for {label} as {by}{note ? `: ${note}` : ""}.</>}>
          Record {value}
        </Confirm>
      )}
    </fieldset>
  );
}
