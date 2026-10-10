import { useState } from "react";
import { Badge, Caveats, RemoteView, ScreenHeader, type Tone } from "../components";
import type { GlyphName } from "../components/Glyph";
import { useApi } from "../lib/useApi";
import { useHash } from "../lib/useHash";
import { useSession } from "../lib/session";
import { SplitEditor } from "./SplitEditor";
import { realBackend, type ListAnswer, type OpenAnswer, type OpenRef, type SplitBackend } from "./splitApi";
import { DemoBackend } from "./splitDemo";
import { DEMO_ID, parseSplitRoute, sizeText, splitRoute, type ListedSession } from "./splitModel";
import { useFileBytes, useUploadCap } from "./RecordActs";
import "./split.css";

let demo: DemoBackend | null = null;
let demoPages = 120;
/** The made-up draft, answered from memory (`#/setup/split/demo`, 120 pages; `?pages=3000` for a long one to feel the scrolling). One per
 * page load, so a reload starts it over. */
export function demoBackend(pages = 120): DemoBackend {
  if (!demo || pages !== demoPages) { demo = new DemoBackend({ latency: 25, pages }); demoPages = pages; }
  return demo;
}
export function resetDemo(): void { demo = null; }

const STATUS: Record<string, { tone: Tone; glyph: GlyphName; words: string }> = {
  draft: { tone: "neutral", glyph: "pencil", words: "draft" },
  confirmed: { tone: "warn", glyph: "clock", words: "confirmed, not finished" },
  applied: { tone: "good", glyph: "circle-check", words: "applied" },
  stale: { tone: "warn", glyph: "triangle-alert", words: "stale: the file changed" },
  declined: { tone: "neutral", glyph: "ban", words: "declined" },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { tone: "neutral" as Tone, glyph: "circle-dashed" as GlyphName, words: status };
  return <Badge tone={s.tone} glyph={s.glyph}>{s.words}</Badge>;
}

function stamp(t: string): string { return t ? t.slice(0, 16).replace("T", " ") : ""; }

/** Opening a file: choose one (upload, or a library id), check it (a dry run, in the server's words: its pages, its size, the limit it
 * may hit), then open it. A draft write keeps a copy and a session; no PDF is written until the review's confirm. */
function OpenPanel({ backend, by }: { backend: SplitBackend; by: string }) {
  const [tab, setTab] = useState<"upload" | "library">("upload");
  const file = useFileBytes();
  const cap = useUploadCap();
  const [lib, setLib] = useState("");
  const [checked, setChecked] = useState<OpenAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ref: OpenRef | null = tab === "upload" ? (file.file ? { kind: "upload", name: file.file.name, base64: file.file.base64 } : null) : lib.trim() ? { kind: "library", id: lib.trim() } : null;
  const tooBig = tab === "upload" && !!file.file && cap.bytes !== null && file.file.size > cap.bytes;
  const reset = () => { setChecked(null); setError(""); };
  const go = async (dry: boolean) => {
    if (!ref) return;
    setBusy(true); setError("");
    try {
      const a = await backend.open(ref, dry, by);
      if (dry) setChecked(a);
      else if (a.session) window.location.hash = splitRoute(a.session.id).slice(1);
    } catch (e) { setChecked(null); setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <section className="split-open" aria-labelledby="split-open-h">
      <h2 id="split-open-h">Open a PDF</h2>
      <div role="group" aria-label="Where the file is" className="row wrap">
        <button type="button" aria-pressed={tab === "upload"} onClick={() => { setTab("upload"); reset(); }}>From this computer</button>
        <button type="button" aria-pressed={tab === "library"} onClick={() => { setTab("library"); reset(); }}>From the library</button>
      </div>
      {tab === "upload" ? (
        <div className="split-field">
          <label htmlFor="split-file">PDF file</label>
          <input id="split-file" type="file" accept="application/pdf,.pdf" onChange={(e) => { reset(); file.choose(e.target.files?.[0]); }} />
          {file.busy && <p className="muted" role="status">Reading the file in this browser…</p>}
          {file.error && <p className="notice notice-error" role="alert">{file.error}</p>}
          {file.file && <p className="muted">{file.file.name}, {sizeText(file.file.size)}. {cap.words ? `The largest upload is ${cap.words}.` : ""}</p>}
          {tooBig && <p className="notice notice-warn" role="alert">This file is {sizeText(file.file!.size)}; the largest upload is {cap.words}. Nothing was sent. Split the scan into smaller files first, or ask your community's administrator to raise the limit.</p>}
        </div>
      ) : (
        <div className="split-field">
          <label htmlFor="split-lib">Library file id</label>
          <input id="split-lib" value={lib} onChange={(e) => { setLib(e.target.value); reset(); }} placeholder="for example 1a2b3c" autoComplete="off" />
          <p className="muted">The id the library gives a file (the Library action "Split document" opens it the same way).</p>
        </div>
      )}
      <p className="muted">A file in Drive: put it in the library or upload it first. The splitter reads a copy and never changes the original.</p>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {checked?.dryRun && checked.would && (
        <div className="split-preview" role="region" aria-label="What opening will do">
          <h3>What will happen</h3>
          <p>{checked.would.pages} pages, {sizeText(checked.would.size)}. It keeps {checked.would.keeps}. {checked.note}</p>
        </div>
      )}
      <div className="row wrap">
        {!checked ? <button type="button" className="primary" disabled={!ref || busy || tooBig} onClick={() => go(true)}>Check the file</button>
          : <button type="button" className="primary" disabled={busy} onClick={() => go(false)}>Open it for splitting</button>}
      </div>
    </section>
  );
}

function Drafts({ rows }: { rows: ListedSession[] }) {
  if (rows.length === 0) return <p className="muted">No drafts yet. Open a PDF above, or try the demo.</p>;
  return (
    <div className="split-table-wrap">
      <table className="split-drafts">
        <caption className="sr-only">Split drafts, newest first</caption>
        <thead><tr><th scope="col">Draft</th><th scope="col">Status</th><th scope="col">Pages</th><th scope="col">Segments</th><th scope="col">Suggestions open</th><th scope="col">Updated</th><th scope="col">By</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-split={r.id}>
              <th scope="row" data-label="Draft"><a href={splitRoute(r.id)} aria-label={`Open the draft ${r.label}`}>{r.label}</a> <span className="muted">{r.id}</span>{r.confidential && <> <Badge tone="warn" glyph="file-lock">confidential</Badge></>}</th>
              <td data-label="Status"><StatusBadge status={r.status} /></td>
              <td data-label="Pages">{r.pages}</td>
              <td data-label="Segments">{r.segments}</td>
              <td data-label="Suggestions open">{r.suggestionsOpen}</td>
              <td data-label="Updated">{stamp(r.updated)}</td>
              <td data-label="By">{r.by}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Setup > Split document (`#/setup/split`): drafts and the ways to open a file. `#/setup/split/<id>` is one draft; `#/setup/split/demo` is
 * a made-up 120-page draft that needs no server. Board only (officers, managers, administrators); never the owner view. */
function SplitStart() {
  const r = useApi<ListAnswer>("/api/split-sessions");
  const { me } = useSession([]);
  return (
    <div className="stack split-view">
      <ScreenHeader title="Split document" summary="Open a combined PDF, see its pages, and tap the first page of each document. jason can suggest starts; you decide. Nothing is written until you review and confirm, and the original is never changed." />
      <section className="split-demo-card" aria-label="Try it">
        <p><a className="split-demo-link" href={splitRoute(DEMO_ID)}>Try it on a made-up 120-page file</a> <span className="muted">No server, no real documents: the pages are invented and the draft lives in this tab.</span></p>
      </section>
      <OpenPanel backend={realBackend} by={me} />
      <section aria-labelledby="split-drafts-h">
        <h2 id="split-drafts-h">Drafts</h2>
        <RemoteView r={r}>
          {(d) => (<>
            <Drafts rows={d.sessions} />
            {d.limits && <p className="muted">Files of up to {d.limits.maxPages} pages open here. A draft is kept {d.limits.draftDays} days after its last change. Suggestions are {d.limits.suggestEnabled ? "on" : "off"} for this community.</p>}
            <Caveats items={d.caveats ?? []} />
          </>)}
        </RemoteView>
      </section>
    </div>
  );
}

export function SplitView() {
  const [hash] = useHash(`setup/split`);
  const { id, query } = parseSplitRoute(hash);
  if (!id) return <SplitStart />;
  if (id === DEMO_ID) {
    const pages = Math.max(10, Math.min(3000, Number(query.get("pages")) || 120));
    return <SplitEditor key={`demo-${pages}`} backend={demoBackend(pages)} id={DEMO_ID} />;
  }
  return <SplitEditor key={id} backend={realBackend} id={id} />;
}
