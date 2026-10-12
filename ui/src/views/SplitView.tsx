import { useEffect, useState } from "react";
import { Badge, Caveats, RemoteView, ScreenHeader, type Tone } from "../components";
import type { GlyphName } from "../components/Glyph";
import { useApi } from "../lib/useApi";
import { useHash } from "../lib/useHash";
import { useSession, NO_PEOPLE } from "../lib/session";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { SplitEditor } from "./SplitEditor";
import { busyOf, realBackend, type Busy, type ListAnswer, type OpenAnswer, type OpenRef, type SplitBackend, type SplitLimits } from "./splitApi";
import { BusyNotice } from "./splitNotices";
import { UnfinishedBadge } from "./SplitRecover";
import { LOCAL_ID, currentLocal, dropLocal, startLocal } from "./splitLocal";
import { DemoBackend } from "./splitDemo";
import { DEMO_ID, parseSplitRoute, sizeText, splitRoute, type ListedSession } from "./splitModel";
import { useFileBytes, useUploadCap } from "./RecordActs";
import { DriveChooser, NotConnected, type ChooserSlot } from "./DriveChooser";
import { LibraryBrowser } from "./LibraryBrowser";
import { HeldCopies, OpenHeld, PickOutcome } from "./PickPanels";
import { PickStart } from "./PickStart";
import { usePickReturn } from "../lib/pick";
import { libraryFiles, type LibraryFile } from "./libraryModel";
import "./records.css";
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
type OpenTab = "upload" | "library" | "drive";
const DRIVE_SLOT: ChooserSlot = { key: "split", title: "splitting", cardinality: "one", source: "" };

export function OpenPanel({ backend, by, libraryFetcher, limits, limitsReady = true }: { backend: SplitBackend; by: string; libraryFetcher?: typeof libraryFiles; limits?: SplitLimits; limitsReady?: boolean }) {
  const [tab, setTab] = useState<OpenTab>("upload");
  // a file chosen before the community's settings have arrived waits for them: which way it opens depends on them
  const [held, setHeld] = useState<File | null>(null);
  // A file chosen on this computer is opened at once, drawn by this browser, when the community allows it (`split.client_render`); the
  // server's copy is made in the background. Without it the file is read, checked, and opened in the steps below.
  const local = backend === realBackend && !!limits?.clientRender;
  const [chosen, setChosen] = useState<{ name: string; size: number } | null>(null);
  const file = useFileBytes();
  const cap = useUploadCap();
  const [lib, setLib] = useState<LibraryFile | null>(null);
  const [drive, setDrive] = useState<{ ref: string; name: string; size: number | null } | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [checked, setChecked] = useState<OpenAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ref: OpenRef | null = tab === "upload" ? (file.file ? { kind: "upload", name: file.file.name, base64: file.file.base64 } : null)
    : tab === "library" ? (lib?.id ? { kind: "library", id: lib.id } : null) : drive ? { kind: "drive", id: drive.ref } : null;
  const tooBig = tab === "upload" && (local ? chosen : file.file) !== null && cap.bytes !== null && (local ? chosen!.size : file.file!.size) > cap.bytes;
  const choose = (f: File | undefined) => {
    reset();
    if (!limitsReady) { setHeld(f ?? null); return; }
    if (!local) { file.choose(f); return; }
    if (!f) { setChosen(null); return; }
    setChosen({ name: f.name, size: f.size });
    if (cap.bytes !== null && f.size > cap.bytes) return;           // the words below say so; nothing is started
    startLocal(f, backend, by, { enabled: true, maxPages: limits?.clientRenderMaxPages ?? limits?.maxPages ?? 3000 });
    window.location.hash = splitRoute(LOCAL_ID).slice(1);
  };
  const reset = () => { setChecked(null); setError(""); setWait(null); };
  useEffect(() => {
    if (!limitsReady || !held) return;
    const f = held;
    setHeld(null);
    choose(f);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limitsReady, held]);
  // the library could not be read while the file was being found: nothing was changed, and Try again asks the same question again
  const [wait, setWait] = useState<{ note: Busy; dry: boolean; n: number } | null>(null);
  const go = async (dry: boolean) => {
    if (!ref) return;
    setBusy(true); setError(""); setWait(null);
    try {
      const a = await backend.open(ref, dry, by);
      if (a.driveConnected === false) setChecked(a);
      else if (dry) setChecked(a);
      else if (a.session) window.location.hash = splitRoute(a.session.id).slice(1);
    } catch (e) {
      setChecked(null);
      const b = busyOf(e);
      if (b) setWait((was) => ({ note: b, dry, n: (was?.n ?? 0) + 1 }));
      else setError((e as Error).message);
    } finally { setBusy(false); }
  };
  return (
    <section className="split-open" aria-labelledby="split-open-h">
      <h2 id="split-open-h">Open a PDF</h2>
      <div role="group" aria-label="Where the file is" className="row wrap">
        <button type="button" aria-pressed={tab === "upload"} onClick={() => { setTab("upload"); reset(); }}>From this computer</button>
        <button type="button" aria-pressed={tab === "library"} onClick={() => { setTab("library"); reset(); }}>From the library</button>
        <button type="button" aria-pressed={tab === "drive"} onClick={() => { setTab("drive"); reset(); }}>From Drive</button>
      </div>
      {tab === "upload" ? (
        <div className="split-field">
          <label htmlFor="split-file">PDF file</label>
          <input id="split-file" type="file" accept="application/pdf,.pdf" onChange={(e) => choose(e.target.files?.[0])} />
          {held && <p className="muted" role="status">Waiting for this community's settings before opening {held.name}…</p>}
          {local && !chosen && !held && <p className="muted">The pages appear here as soon as you choose the file, drawn in this browser. The file is saved on the server in the background.</p>}
          {file.busy && <p className="muted" role="status">Reading the file in this browser…</p>}
          {file.error && <p className="notice notice-error" role="alert">{file.error}</p>}
          {!local && file.file && <p className="muted">{file.file.name}, {sizeText(file.file.size)}. {cap.words ? `The largest upload is ${cap.words}.` : ""}</p>}
          {tooBig && <p className="notice notice-warn" role="alert">This file is {sizeText(local ? chosen!.size : file.file!.size)}; the largest upload is {cap.words}. Nothing was sent. Split the scan into smaller files first, or ask your community's administrator to raise the limit.</p>}
        </div>
      ) : tab === "library" ? (
        <div className="split-field">
          <LibraryBrowser selectedId={lib?.id ?? ""} fetcher={libraryFetcher} onSelect={(f) => { setLib(f); reset(); }} />
          <p className="muted" role="status">{lib ? `Chosen: ${lib.name}${lib.pages ? `, ${lib.pages} pages` : ""}${lib.size !== null ? `, ${sizeText(lib.size)}` : ""}.` : "No file chosen yet."}</p>
        </div>
      ) : (
        <div className="split-field">
          <p>
            <button type="button" onClick={() => setChoosing(true)}>{drive ? "Choose a different file in Drive" : "Choose a PDF in Drive"}</button>
          </p>
          {drive
            ? <p role="status">Chosen in Drive: <strong>{drive.name}</strong>{drive.size !== null ? `, ${sizeText(drive.size)}` : ""}.</p>
            : <p className="muted" role="status">No file chosen yet.</p>}
          <p className="muted">jason reads Drive with its own account and writes nothing there. A file that account cannot see is not listed: share it with the account shown, or upload the file.</p>
          <PickStart purpose="split" />
          {choosing && <DriveChooser slot={DRIVE_SLOT} by={by} startTab="drive" onClose={() => setChoosing(false)} onDone={() => undefined}
            pick={{ title: "Choose a PDF in Drive to split", onChoose: (f) => { setDrive(f); reset(); } }} />}
        </div>
      )}
      <p className="muted">The splitter reads a copy and never changes the original, wherever it is.</p>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {wait && <BusyNotice busy={wait.note} again={wait.n} working={busy} onRetry={() => void go(wait.dry)} />}
      {checked && checked.driveConnected === false && <NotConnected d={checked} />}
      {checked?.dryRun && checked.would && (
        <div className="split-preview" role="region" aria-label="What opening will do">
          <h3>What will happen</h3>
          {checked.would.pages === null
            ? <p>{checked.would.size !== null ? `${sizeText(checked.would.size)}. ` : ""}{checked.would.fetches ? `${checked.would.fetches.charAt(0).toUpperCase()}${checked.would.fetches.slice(1)}. ` : ""}Its pages are counted when it is read. It keeps {checked.would.keeps}. {checked.note}</p>
            : <p>{checked.would.pages} pages, {sizeText(checked.would.size ?? 0)}. It keeps {checked.would.keeps}. {checked.note}</p>}
        </div>
      )}
      <div className="row wrap">
        {!checked?.dryRun ? <button type="button" className="primary" disabled={!ref || busy || tooBig} onClick={() => go(true)}>Check the file</button>
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
              <th scope="row" data-label="Draft"><a href={splitRoute(r.id)} aria-label={`Open the draft ${r.label}${r.unfinishedApply ? ". An earlier apply did not finish" : ""}`}>{r.label}</a> <span className="muted">{r.id}</span>{r.confidential && <> <Badge tone="warn" glyph="file-lock">confidential</Badge></>}</th>
              <td data-label="Status"><StatusBadge status={r.status} />{r.unfinishedApply && <div className="split-unfinished-row" data-unfinished><UnfinishedBadge u={r.unfinishedApply} /></div>}</td>
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
  useDocumentTitle("Split document");
  const r = useApi<ListAnswer>("/api/split-sessions");
  const { me } = useSession(NO_PEOPLE);
  useEffect(() => { dropLocal(); }, []);                  // coming back to the list lets go of a file held for the editor
  const back = usePickReturn("split");
  return (
    <div className="stack split-view">
      <ScreenHeader title="Split document" summary="Open a combined PDF, see its pages, and tap the first page of each document. jason can suggest starts; you decide. Nothing is written until you review and confirm, and the original is never changed." />
      <section className="split-demo-card" aria-label="Try it">
        <p><a className="split-demo-link" href={splitRoute(DEMO_ID)}>Try it on a made-up 120-page file</a> <span className="muted">No server, no real documents: the pages are invented and the draft lives in this tab.</span></p>
      </section>
      {back.value && (
        <PickOutcome value={back.value} onClose={back.close} level={2} action={(row, n) => <OpenHeld backend={realBackend} by={me} heldId={row.heldId} label={`file ${n}`} />}
          again={<PickStart purpose="split" />} />
      )}
      <OpenPanel backend={realBackend} by={me} limits={r.status === "ready" ? r.data.limits : undefined} limitsReady={r.status !== "loading"} />
      <HeldCopies backend={realBackend} by={me} />
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

function SplitLost() {
  useDocumentTitle("Split document: The file is gone");
  return (
    <div className="stack split-view">
      <ScreenHeader title="Split document" summary="A file chosen on this computer is held by this tab only." />
      <p className="notice notice-warn" role="note">That file was held by the tab before it was reloaded. If it was saved, it is in the list of drafts; otherwise choose it again. <a href="#/setup/split">Back to the splitter</a></p>
    </div>
  );
}

export function SplitView() {
  const [hash] = useHash(`setup/split`);
  const { id, query } = parseSplitRoute(hash);
  if (!id) return <SplitStart />;
  if (id === LOCAL_ID) {
    const held = currentLocal();
    if (!held) return <SplitLost />;
    return <SplitEditor key="local" backend={held} id={LOCAL_ID} />;
  }
  if (id === DEMO_ID) {
    const pages = Math.max(10, Math.min(3000, Number(query.get("pages")) || 120));
    return <SplitEditor key={`demo-${pages}`} backend={demoBackend(pages)} id={DEMO_ID} />;
  }
  return <SplitEditor key={id} backend={realBackend} id={id} />;
}
