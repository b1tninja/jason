import { useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ApiError, getJson, serverSession, signInRefusal, type PrivateOpenBody, type PrivateView, type ServerSession } from "../lib/api";
import { docKindWord, isRestricted, pathOfAddress, driveIdOfAddress, type DocKind, type DocRef } from "../lib/docref";
import { privateActs, useAccount, useMe } from "../lib/session";
import { Caveats } from "./Caveats";
import { DocumentBody, DocumentViewer, humanSize, isConfidential, viewDocument, type DocumentView, type DocumentViewRequest, type EvidenceDocument, type EvidenceDocumentKind } from "./DocumentViewer";
import { EvidenceVersion, RereadIcon, evidenceUrl, refreshEvidence, type EvidenceAnswer, type EvidenceRefreshRequest } from "./Evidence";
import { PrivateAsk } from "./PrivateSwitch";

/* `Doc`: one component for every document reference (docs/console/doc-component.md). A screen passes a `DocRef` from its
 * loader and picks a variant: `chip` in a sentence, `row` in a list, `card` in a grid or a table's document column, and
 * `inline` when the document is the screen's subject. It absorbs DrivePreview and DocumentPreview's card (now thin
 * wrappers) and the evidence panel's Documents list (`DocList`, row). Every state is said in words, never a broken
 * image or an empty box. Opening is one logged `POST /api/evidence/view`, a person's act, never prefetched; an inline
 * P0 or P1 document is the exception, viewed on mount because it is the screen's subject. */

// --- shared words and helpers --------------------------------------------------------------------------------------------

/** What a Drive file is, for its placeholder's word and the link to it when jason has none from Drive. */
export type DriveKind = "doc" | "sheet" | "slides" | "pdf" | "image" | "drive";

/** The evidence address of a Drive file (`jason.approvals.evidence`'s `drive:<id>` row). */
export const driveAddress = (driveId: string) => `drive:${driveId}`;
/** The evidence address of a file under the data folder (`file:<path>`). */
export const fileAddress = (path: string) => `file:${path}`;

/** The name the evidence gives jason's copy (`Copy from Drive`): its `readAt` is when a person last read it from Drive. */
export const DRIVE_COPY = "Copy from Drive";
export const CHANGED_IN_DRIVE = "Changed in Drive since this copy";
/** The two copies a document may have, as a cell names them. AGENTS.md: "Recite the version that governs". */
export const RECORDED_COPY = "Recorded copy";
export const DRIVE_COPY_LABEL = "Drive copy";

/** The state lines (docs/console/doc-component.md, States). */
export const DOC_WORDS = {
  loading: "Opening…",
  signedOut: "Sign in with Google to open this",
  needsPrivate: "Confidential: open the private view to see it",
  noCopy: "No copy yet",
  missing: "Not on disk",
  show: "Show the document",
  logged: "Viewing shows it unmasked, under your name, and is logged.",
} as const;

const EDITORS: Record<DriveKind, string> = {
  doc: "https://docs.google.com/document/d/{id}/edit",
  sheet: "https://docs.google.com/spreadsheets/d/{id}/edit",
  slides: "https://docs.google.com/presentation/d/{id}/edit",
  pdf: "https://drive.google.com/file/d/{id}/view",
  image: "https://drive.google.com/file/d/{id}/view",
  drive: "https://drive.google.com/file/d/{id}/view",
};

/** The file's own page in Google, by its kind, for when the evidence has not said its `link` yet. */
export function googleLink(driveId: string, kind: DriveKind = "doc"): string {
  return (EDITORS[kind] ?? EDITORS.drive).replace("{id}", encodeURIComponent(driveId));
}

/** The Drive id in a Google link (`/d/ID/`, `?id=ID`), or "" when there is none. */
export function driveIdOf(link: string): string {
  const m = /\/d\/([A-Za-z0-9_-]{10,})/.exec(link) ?? /[?&]id=([A-Za-z0-9_-]{10,})/.exec(link);
  return m ? m[1] : "";
}

/** `GET /api/thumb?path=`: page 1 of a PDF under data/, rendered on the server from disk (never Google). `stamp` busts
 * the browser's cache when the file changed. */
export function thumbUrl(path: string, stamp = ""): string {
  return `/api/thumb?path=${encodeURIComponent(path)}${stamp ? `&v=${encodeURIComponent(stamp)}` : ""}`;
}

/** `GET /api/drive/thumb/<id>`: jason's kept thumbnail of a Drive file, from disk. */
export function driveThumbUrl(driveId: string, stamp = ""): string {
  return `/api/drive/thumb/${encodeURIComponent(driveId)}${stamp ? `?v=${encodeURIComponent(stamp)}` : ""}`;
}

/** "Oct 3", with the year when it is not this year's. */
export function copyDay(iso: string, today: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const same = d.getFullYear() === today.getFullYear();
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(same ? {} : { year: "numeric" }) });
}

/** Whether the element has scrolled into view (once); true at once where the browser has no IntersectionObserver. */
export function useSeen(enabled: boolean) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (!enabled || seen) return;
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setSeen(true); return; }
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { setSeen(true); io.disconnect(); }
    }, { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, [enabled, seen]);
  return { ref, seen };
}

const sentence = (s: string) => (s && !/[.!?…]$/.test(s) ? `${s}.` : s);
const REFUSALS = [400, 403, 404, 405, 409];

/** The server's words for a failed call: its own sentence for a refusal, else that jason-web did not answer. */
function failure(e: unknown): { text: string; signIn?: string; status?: number } {
  const status = e instanceof ApiError ? e.status : undefined;
  const message = e instanceof Error ? e.message : String(e);
  const asked = signInRefusal(e);
  return { text: asked || (status && REFUSALS.includes(status)) ? message : `jason-web did not answer: ${message}`, signIn: asked?.href, status };
}

/** The document a reference opens first: the file itself (a PDF, an image, a submission), else its text. */
export function firstDocument(docs: readonly { id: string; kind: string }[]): number {
  for (const id of ["submission", "pdf", "image", "text", "csv"]) {
    const i = docs.findIndex((d) => d.id === id || (id === "submission" && d.kind === "submission"));
    if (i >= 0) return i;
  }
  return docs.length ? 0 : -1;
}

/** A reference's one document as the viewer lists it. */
export function asEvidenceDocument(r: DocRef): EvidenceDocument {
  return { id: r.document ?? "", name: r.name, kind: (["submission", "pdf", "image", "text", "audio"].includes(r.kind) ? r.kind : "file") as EvidenceDocumentKind,
    size: r.size ?? 0, readAt: r.readAt ?? "", note: r.source ?? "", ...(r.level ? { level: r.level } : {}) };
}

/** An evidence document as a reference of its address (the evidence panel's Documents list). */
export function documentRef(address: string, d: EvidenceDocument): DocRef {
  return { address, document: d.id, name: d.name, kind: d.kind as DocKind, size: d.size, readAt: d.readAt,
    ...(d.note ? { source: d.note } : {}), ...(d.level === "P3" ? { level: "P3" as const } : {}) };
}

const GLYPH: Record<string, string> = {
  submission: "☑", form: "☐", pdf: "▤", image: "▣", text: "¶", table: "▦", html: "◫", message: "✉", audio: "♪", file: "▢",
};

/** The kind's glyph, hidden from screen readers; the kind in words is given beside it. */
function Glyph({ kind }: { kind: string }) {
  return <span className="doc-glyph" aria-hidden="true">{GLYPH[kind] ?? GLYPH.file}</span>;
}

/** The server's session, for what a document needs: whether someone is signed in, where to sign in, and the private
 * view (asked only for a P3 document, the one level it opens). `signedIn` and `privateView` fix them (previews,
 * tests): then nothing is asked. */
function useDocSession({ enabled, signedIn, privateView, by, level }: {
  enabled: boolean; signedIn?: boolean; privateView?: PrivateView | null; by?: string; level?: string;
}) {
  const fixed = signedIn !== undefined;
  const account = useAccount(enabled && !fixed);
  const [s, setS] = useState<ServerSession | null>(null);
  const askPrivate = enabled && level === "P3" && privateView === undefined;
  useEffect(() => {
    if (!askPrivate) return;
    let on = true;
    serverSession().then((x) => { if (on) setS(x); });
    return () => { on = false; };
  }, [askPrivate]);
  const sessionMe = useMe(enabled && by === undefined && !fixed);
  const known = fixed || account.known;
  const isIn = signedIn ?? !!account.account;
  const priv = privateView !== undefined ? privateView : s?.private ?? null;
  return { known, isIn, href: account.href, name: account.account?.name ?? "", who: (by ?? sessionMe).trim(), priv };
}

/** "Confidential: open the private view to see it", with the switch's action when the person may open it. */
function NeedsPrivate({ priv, name, onOpenPrivate }: { priv: PrivateView | null; name: string; onOpenPrivate?: (b: PrivateOpenBody) => Promise<void> | void }) {
  const [asking, setAsking] = useState(false);
  const button = useRef<HTMLButtonElement | null>(null);
  return (
    <span className="doc-state doc-state-private">
      <span className="private-chip">Confidential</span> {DOC_WORDS.needsPrivate.replace(/^Confidential: /, "")}.
      {priv?.mayOpen && (
        <> <button type="button" className="link" ref={button} aria-expanded={asking} onClick={() => setAsking((a) => !a)}>Open the private view</button>
          {asking && <PrivateAsk name={name} onOpen={onOpenPrivate ?? privateActs.open} onCancel={() => { setAsking(false); button.current?.focus(); }}
            minutes={priv.minutes} initial={priv.default} />}
        </>
      )}
      {priv && !priv.mayOpen && priv.why && <span className="muted"> {priv.why}</span>}
    </span>
  );
}

/** One state line, announced politely when it changes. */
function StateLine({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "warn" | "error" }) {
  const cls = tone === "error" ? "notice notice-error" : tone === "warn" ? "notice notice-warn" : "muted";
  return <span className={`doc-state ${cls}`}>{children}</span>;
}

/** "Not on disk" or "No copy yet", with the command that fills it (from the evidence answer) when there is one. */
function MissingLine({ answer, refreshable }: { answer: EvidenceAnswer | null; refreshable: boolean }) {
  const command = answer?.refresh?.find((r) => !r.live)?.command ?? answer?.refresh?.[0]?.command ?? "";
  return (
    <StateLine>
      {refreshable ? DOC_WORDS.noCopy : DOC_WORDS.missing}
      {command && !refreshable && <>: <code className="doc-command">{command}</code> fills it</>}
      {refreshable && ": read it again (↻)"}
    </StateLine>
  );
}

// --- the evidence answer, the view, and the read again --------------------------------------------------------------------

/** The evidence answer of an address (`GET /api/evidence`), once `when` is true, or `evidence` as given (nothing fetched).
 * Fetched again when an `EvidenceVersion` around it changes. */
function useAnswer(address: string, evidence: EvidenceAnswer | null | undefined, when: boolean) {
  const fixed = evidence !== undefined;
  const version = useContext(EvidenceVersion);
  const [answer, setAnswer] = useState<EvidenceAnswer | null>(evidence ?? null);
  const [loaded, setLoaded] = useState(fixed);
  const [error, setError] = useState("");
  useEffect(() => { if (fixed) { setAnswer(evidence ?? null); setLoaded(true); } }, [fixed, evidence]);
  useEffect(() => {
    if (fixed || !when || !address) return;
    const ctl = new AbortController();
    getJson<EvidenceAnswer>(evidenceUrl(address), ctl.signal).then(
      (a) => { setAnswer(a); setLoaded(true); setError(""); },
      (e: unknown) => {
        if (ctl.signal.aborted) return;
        const body = e instanceof ApiError ? (e.body as Partial<EvidenceAnswer> | null) : null;
        if (body && typeof body === "object" && body.found === false) setAnswer(body as EvidenceAnswer);
        else setError(failure(e).text);
        setLoaded(true);
      },
    );
    return () => ctl.abort();
  }, [address, fixed, when, version]);
  return { answer, setAnswer, loaded, setLoaded, error, fixed };
}

type Viewing = { index: number; data: DocumentView | null; busy: boolean; error: string; signIn?: string; status?: number };

/** One open document at a time from `docs` (each `{address, document}`), each a logged view; Previous and Next are views
 * of their own. Closing returns focus to the element that opened it. */
function useViewer(viewer: ((req: DocumentViewRequest) => Promise<DocumentView>) | null, who: string, approval?: string) {
  const [viewing, setViewing] = useState<Viewing | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const seq = useRef(0);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const open = async (i: number, target: { address: string; document: string } | undefined) => {
    if (!target || !viewer) return;
    const mine = ++seq.current;
    setViewing({ index: i, data: null, busy: true, error: "" });
    try {
      const v = await viewer({ address: target.address, ...(approval ? { approval } : {}), document: target.document, by: who });
      if (alive.current && seq.current === mine) setViewing({ index: i, data: v, busy: false, error: "" });
    } catch (e: unknown) {
      if (!alive.current || seq.current !== mine) return;
      const f = failure(e);
      setViewing({ index: i, data: null, busy: false, error: f.text, signIn: f.signIn, status: f.status });
    }
  };
  const close = () => {
    seq.current += 1;
    setViewing(null);
    opener.current?.focus();
  };
  return { viewing, open, close, opener };
}

/** ↻: read the address again from its system (`POST /api/evidence/refresh`), a signed-in person's click. */
function useReread(address: string, who: string, reader: ((req: EvidenceRefreshRequest) => Promise<EvidenceAnswer>) | null, onFresh: (a: EvidenceAnswer) => void) {
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<{ tone: "status" | "error"; text: string; signIn?: string } | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const read = async (system: string) => {
    if (busy || !reader) return;
    setBusy(true);
    setSaid({ tone: "status", text: `Reading from ${system}…` });
    try {
      const fresh = await reader({ address, by: who });
      if (!alive.current) return;
      onFresh(fresh);
      setSaid({ tone: "status", text: `Read from ${system} just now by ${fresh.refreshed?.by || who}.` });
    } catch (e: unknown) {
      if (!alive.current) return;
      const f = failure(e);
      setSaid({ tone: "error", text: f.text, signIn: f.signIn });
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  return { busy, said, read };
}

function Said({ said }: { said: { tone: "status" | "error"; text: string; signIn?: string } | null }) {
  return said ? <span className={said.tone === "error" ? "notice notice-error" : "muted"}>{said.text}{said.signIn && <> <a href={said.signIn}>Sign in with Google</a></>}</span> : null;
}

/** Shared static props: for previews and tests, `evidence` is a static answer (nothing fetched), `signedIn` fixes the
 * sign-in, `privateView` the private view, `thumb` the image's URL, `by` the person, and `onRead`, `onView`, and
 * `onOpenPrivate` stand in for the server's calls. */
export interface DocStatic {
  evidence?: EvidenceAnswer | null;
  signedIn?: boolean;
  privateView?: PrivateView | null;
  thumb?: string;
  today?: Date;
  by?: string;
  onRead?: (req: EvidenceRefreshRequest) => Promise<EvidenceAnswer>;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
  onOpenPrivate?: (body: PrivateOpenBody) => Promise<void> | void;
}

// --- card: a Drive file ---------------------------------------------------------------------------------------------------

const KIND_WORD: Record<DriveKind, string> = { doc: "Doc", sheet: "Sheet", slides: "Slides", pdf: "PDF", image: "Image", drive: "File" };

/** One Drive file as a sheet of paper (the card DrivePreview was): jason's thumbnail of it (`GET /api/drive/thumb/<id>`,
 * from disk, never Google), the copy's age, "Changed in Drive since this copy", Preview (a logged view), ↻ Read from
 * Drive (a signed-in person's click), and Open in Google. */
function DriveCard({ doc, driveKind = "doc", showName, evidence, signedIn, privateView, thumb, today, by, onRead, onView, onOpenPrivate }: DocStatic & {
  doc: DocRef; driveKind?: DriveKind; showName?: boolean;
}) {
  const driveId = driveIdOfAddress(doc.address);
  const address = doc.address;
  const name = doc.name;
  const kind = driveKind;
  const fixed = evidence !== undefined;
  const ses = useDocSession({ enabled: true, signedIn, privateView, by, level: doc.level });
  const { known, isIn, who } = ses;
  const held = doc.level === "P3" && !ses.priv?.open;
  const { ref, seen } = useSeen(!fixed);
  const { answer, setAnswer, loaded, setLoaded } = useAnswer(address, evidence, seen && !held);
  const [img, setImg] = useState<"loading" | "shown" | "failed">("loading");
  const previewButton = useRef<HTMLButtonElement | null>(null);
  const whyId = useId();
  const reader = onRead ?? (fixed ? null : refreshEvidence);
  const viewer = onView ?? (fixed ? null : viewDocument);
  const v = useViewer(viewer, who);
  const reread = useReread(address, who, reader, (fresh) => { setAnswer(fresh); setLoaded(true); });

  const copy = answer?.sources?.find((s) => s.name === DRIVE_COPY) ?? null;
  const docs = answer?.documents ?? [];
  const at = firstDocument(docs.filter((d) => d.id !== "submission"));
  const readAt = copy?.readAt || (answer ? "" : doc.readAt ?? "");
  const src = thumb ?? (copy || (!answer && doc.thumb) ? driveThumbUrl(driveId, readAt) : "");
  useEffect(() => { setImg("loading"); }, [src]);
  const showImage = known && isIn && !held && !!src && img !== "failed";
  const link = answer?.link || doc.original?.url || googleLink(driveId, kind);
  const signInWhy = !known ? "Checking your sign-in…" : isIn ? "" : "Sign in with Google";
  const readWhy = signInWhy ? `${signInWhy === "Sign in with Google" ? "Sign in with Google to read it from Drive" : signInWhy}` : held ? DOC_WORDS.needsPrivate : "";
  const viewWhy = signInWhy ? (signInWhy === "Sign in with Google" ? "Sign in with Google to preview it" : signInWhy)
    : held ? DOC_WORDS.needsPrivate
    : at < 0 ? (loaded ? "No copy yet: read it from Drive first" : "Checking for jason's copy…") : "";
  const changed = answer ? answer.changed === true : !!doc.stale;

  const preview = () => {
    if (viewWhy || v.viewing) return;
    v.opener.current = previewButton.current;
    void v.open(at, docs[at] ? { address, document: docs[at].id } : undefined);
  };
  const placeholder = !known ? "" : !isIn ? "Sign in to see previews" : held ? "Confidential" : (copy || !loaded || (!answer && doc.thumb)) && img !== "failed" ? "" : "No preview yet";
  return (
    <div className="drive-preview" ref={ref}>
      {showName && <span className="doc-card-name">{name}</span>}
      <div className={`drive-preview-sheet drive-preview-${kind}`} aria-busy={!known || (isIn && !loaded && !held) ? true : undefined}>
        {showImage && (
          <img src={src} alt={name} loading="lazy" width={96} className={img === "shown" ? "drive-preview-img is-shown" : "drive-preview-img"}
            onLoad={() => setImg("shown")} onError={() => setImg("failed")} />
        )}
        {img !== "shown" && (
          <span className="drive-preview-placeholder">
            <span className="drive-preview-kind">{KIND_WORD[kind] ?? "File"}</span>
            {placeholder && <span className="drive-preview-none">{placeholder}</span>}
          </span>
        )}
      </div>
      {known && !isIn && <a className="drive-preview-sign-in" href={ses.href}>Sign in with Google</a>}
      {known && isIn && held && <NeedsPrivate priv={ses.priv} name={ses.name || who} onOpenPrivate={onOpenPrivate} />}
      {(copy || changed || (!answer && readAt)) && (
        <div className="drive-preview-age">
          {readAt && <span className="muted">copy from <time dateTime={readAt}>{copyDay(readAt, today)}</time></span>}
          {changed && <span className="drive-preview-changed">{answer?.changed === true ? CHANGED_IN_DRIVE : doc.stale || CHANGED_IN_DRIVE}</span>}
        </div>
      )}
      <div className="drive-preview-acts">
        <button type="button" className="link" ref={previewButton} aria-label={`Preview ${name}`}
          aria-disabled={viewWhy || !viewer ? true : undefined} title={viewWhy ? sentence(viewWhy) : "Opens jason's copy; the view is logged under your name."}
          onClick={preview}>Preview</button>
        <button type="button" className="link drive-preview-read" aria-label={`Read ${name} from Drive`}
          aria-disabled={readWhy || reread.busy || !reader ? true : undefined} aria-busy={reread.busy ? true : undefined}
          aria-describedby={readWhy ? whyId : undefined}
          title={readWhy ? sentence(readWhy) : "Exports it from Google Drive now, under your name; writes nothing to Drive."}
          onClick={() => { if (!readWhy) void reread.read("Google Drive"); }}><RereadIcon />Read from Drive</button>
        <a href={link} target="_blank" rel="noreferrer">{doc.original?.label || "Open in Google"}<span className="visually-hidden"> (opens in a new tab)</span></a>
      </div>
      {readWhy && <span id={whyId} className="visually-hidden">{sentence(readWhy)}</span>}
      <span aria-live="polite" className="drive-preview-status"><Said said={reread.said} /></span>
      {v.viewing && (
        <DocumentViewer data={v.viewing.data} document={docs[v.viewing.index]} documents={docs} busy={v.viewing.busy} error={v.viewing.error}
          signIn={v.viewing.signIn} position={{ index: v.viewing.index, count: docs.length }}
          onGo={(i) => void v.open(i, docs[i] ? { address, document: docs[i].id } : undefined)} onClose={v.close} today={today} />
      )}
    </div>
  );
}

// --- card: a file on disk, a library document, a request ---------------------------------------------------------------

/** A document jason keeps on disk as a sheet of paper (the card LocalPreview was): page 1 rendered by the server for a
 * PDF under data/ (`GET /api/thumb?path=`), Preview (a logged view of the address's first document), ↻ when the
 * reference is refreshable, and the original when it names one. Signed out, a placeholder asks for a sign-in. */
function FileCard({ doc, label = RECORDED_COPY, showName, thumbPath, evidence, signedIn, privateView, thumb, today, by, onRead, onView, onOpenPrivate }: DocStatic & {
  doc: DocRef; label?: string; showName?: boolean; thumbPath?: string;
}) {
  const path = thumbPath || pathOfAddress(doc.address);
  const address = doc.address;
  const name = doc.name;
  const fixed = evidence !== undefined;
  const ses = useDocSession({ enabled: true, signedIn, privateView, by, level: doc.level });
  const { known, isIn, who } = ses;
  const held = doc.level === "P3" && !ses.priv?.open;
  const { ref, seen } = useSeen(!fixed);
  const { answer, setAnswer, loaded, setLoaded, error } = useAnswer(address, evidence, seen && !held);
  const [img, setImg] = useState<"loading" | "shown" | "failed">("loading");
  const previewButton = useRef<HTMLButtonElement | null>(null);
  const reader = onRead ?? (fixed ? null : refreshEvidence);
  const viewer = onView ?? (fixed ? null : viewDocument);
  const v = useViewer(viewer, who);
  const reread = useReread(address, who, reader, (fresh) => { setAnswer(fresh); setLoaded(true); });

  const docs = answer?.documents ?? [];
  const first = firstDocument(docs);
  const kept = answer?.sources?.[0]?.readAt ?? doc.readAt ?? "";
  const isPdf = /\.pdf$/i.test(path) || (!path && doc.kind === "pdf");
  const src = thumb ?? (path && /\.pdf$/i.test(path) ? thumbUrl(path, kept) : "");
  useEffect(() => { setImg("loading"); }, [src]);
  const showImage = known && isIn && !held && !!src && img !== "failed";
  const signInWhy = !known ? "Checking your sign-in…" : isIn ? "" : "Sign in with Google to preview it";
  const viewWhy = signInWhy || (held ? DOC_WORDS.needsPrivate : first < 0 ? (loaded ? (answer?.note || error || DOC_WORDS.missing) : "Checking for jason's copy…") : "");
  const refreshable = answer ? answer.refreshable ?? null : doc.refreshable ?? null;
  const link = answer?.link || doc.original?.url || "";

  const preview = () => {
    if (viewWhy || v.viewing) return;
    v.opener.current = previewButton.current;
    void v.open(first, docs[first] ? { address, document: docs[first].id } : undefined);
  };
  const placeholder = !known ? "" : !isIn ? "Sign in to see previews" : held ? "Confidential" : src && img !== "failed" ? "" : "No preview yet";
  const word = isPdf ? "PDF" : doc.kind === "file" ? "File" : docKindWord(doc.kind);
  return (
    <div className="drive-preview doc-preview-local" ref={ref}>
      {showName && <span className="doc-card-name">{name}</span>}
      <div className="drive-preview-sheet drive-preview-pdf" aria-busy={!known ? true : undefined}>
        {showImage && (
          <img src={src} alt={name} loading="lazy" width={96} className={img === "shown" ? "drive-preview-img is-shown" : "drive-preview-img"}
            onLoad={() => setImg("shown")} onError={() => setImg("failed")} />
        )}
        {img !== "shown" && (
          <span className="drive-preview-placeholder">
            <span className="drive-preview-kind">{word}</span>
            {placeholder && <span className="drive-preview-none">{placeholder}</span>}
          </span>
        )}
      </div>
      {known && !isIn && <a className="drive-preview-sign-in" href={ses.href}>Sign in with Google</a>}
      {known && isIn && held && <NeedsPrivate priv={ses.priv} name={ses.name || who} onOpenPrivate={onOpenPrivate} />}
      {showName && (kept || doc.stale) && (
        <div className="drive-preview-age">
          {kept && <span className="muted">copy from <time dateTime={kept}>{copyDay(kept, today)}</time></span>}
          {doc.stale && <span className="drive-preview-changed">{doc.stale}</span>}
        </div>
      )}
      {known && isIn && !held && loaded && first < 0 && showName && <MissingLine answer={answer} refreshable={!!refreshable} />}
      <div className="drive-preview-acts">
        <button type="button" className="link" ref={previewButton} aria-label={`Preview ${name}, ${label.toLowerCase()}`}
          aria-disabled={viewWhy || !viewer ? true : undefined}
          title={viewWhy ? sentence(viewWhy) : "Opens jason's copy on disk; the view is logged under your name."}
          onClick={preview}>Preview</button>
        {refreshable && (
          <button type="button" className="link drive-preview-read" aria-label={`Read ${name} again from ${refreshable.system}`}
            aria-disabled={signInWhy || held || reread.busy || !reader ? true : undefined} aria-busy={reread.busy ? true : undefined}
            title={signInWhy ? sentence(signInWhy) : `${sentence(refreshable.what)} Reads ${refreshable.system} now, under your name.`}
            onClick={() => { if (!signInWhy && !held) void reread.read(refreshable.system); }}><RereadIcon />Read again</button>
        )}
        {link && <a href={link} target="_blank" rel="noreferrer">{doc.original?.label || "Open the original"}<span className="visually-hidden"> (opens in a new tab)</span></a>}
      </div>
      <span aria-live="polite" className="drive-preview-status"><Said said={reread.said} /></span>
      {v.viewing && (
        <DocumentViewer data={v.viewing.data} document={docs[v.viewing.index]} documents={docs} busy={v.viewing.busy} error={v.viewing.error}
          signIn={v.viewing.signIn} position={{ index: v.viewing.index, count: docs.length }}
          onGo={(i) => void v.open(i, docs[i] ? { address, document: docs[i].id } : undefined)} onClose={v.close} today={today} />
      )}
    </div>
  );
}

// --- chip -----------------------------------------------------------------------------------------------------------------

/** A document in a sentence or a table cell: its kind's glyph and its name, a mark for P3. A click opens it in the viewer
 * (one logged view); a state that keeps it shut is said beside it in words. */
function DocChip({ doc, evidence, signedIn, privateView, today, by, onView, onOpenPrivate }: DocStatic & { doc: DocRef }) {
  const fixed = evidence !== undefined;
  const ses = useDocSession({ enabled: true, signedIn, privateView, by, level: doc.level });
  const [asked, setAsked] = useState(false);
  const [answer, setAnswer] = useState<EvidenceAnswer | null>(evidence ?? null);
  const [said, setSaid] = useState<ReactNode>(null);
  const [docs, setDocs] = useState<EvidenceDocument[]>(doc.document ? [asEvidenceDocument(doc)] : []);
  const viewer = onView ?? (fixed ? null : viewDocument);
  const v = useViewer(viewer, ses.who);
  const chip = useRef<HTMLButtonElement | null>(null);
  const kindId = useId();
  const held = doc.level === "P3" && !ses.priv?.open;

  const click = async () => {
    setAsked(true);
    if (!ses.known || v.viewing) return;
    if (!ses.isIn) { setSaid(<StateLine>{DOC_WORDS.signedOut}: <a href={ses.href}>Sign in with Google</a></StateLine>); return; }
    if (held) { setSaid(<NeedsPrivate priv={ses.priv} name={ses.name || ses.who} onOpenPrivate={onOpenPrivate} />); return; }
    let list = docs;
    let got = answer;
    if (!list.length) {
      try {
        got = got ?? (fixed ? null : await getJson<EvidenceAnswer>(evidenceUrl(doc.address)));
      } catch (e: unknown) {
        setSaid(<StateLine tone="error">{failure(e).text}</StateLine>);
        return;
      }
      setAnswer(got);
      list = got?.documents ?? [];
      setDocs(list);
    }
    const i = doc.document ? Math.max(0, list.findIndex((d) => d.id === doc.document)) : firstDocument(list);
    if (i < 0 || !list[i]) { setSaid(<MissingLine answer={got} refreshable={!!(got?.refreshable ?? doc.refreshable)} />); return; }
    setSaid(null);
    v.opener.current = chip.current;
    void v.open(i, { address: doc.address, document: list[i].id });
  };
  const busy = !!v.viewing?.busy;
  return (
    <span className="doc-chip-wrap">
      <button type="button" ref={chip} className="chip chip-open doc-chip" aria-label={`Open ${doc.name}`} aria-describedby={kindId}
        aria-busy={busy || (asked && !ses.known) ? true : undefined} onClick={() => void click()}>
        <Glyph kind={doc.kind} /><span className="doc-chip-name">{doc.name}</span>
        {doc.level === "P3" && <span className="doc-level-mark" aria-hidden="true">P3</span>}
      </button>
      <span id={kindId} className="visually-hidden">{docKindWord(doc.kind)}{doc.level === "P3" ? ", confidential" : ""}</span>
      <span aria-live="polite" className="doc-chip-status">{busy ? <StateLine>{DOC_WORDS.loading}</StateLine> : said}</span>
      {v.viewing && !v.viewing.busy && (
        <DocumentViewer data={v.viewing.data} document={docs[v.viewing.index]} documents={docs} busy={false} error={v.viewing.error}
          signIn={v.viewing.signIn} position={{ index: v.viewing.index, count: docs.length }}
          onGo={(i) => void v.open(i, docs[i] ? { address: doc.address, document: docs[i].id } : undefined)} onClose={v.close} today={today} />
      )}
    </span>
  );
}

// --- inline -----------------------------------------------------------------------------------------------------------------

/** The document as the screen's subject: a region labelled by its name, a slim header (name, source, age, ↻, the
 * original, Open in viewer), and the body rendered by kind. A P0 or P1 document is viewed on mount (one logged view); a
 * P2 or P3 one, or one whose level the reference does not give, shows "Show the document" first. */
function DocInline({ doc, headingLevel = 3, evidence, signedIn, privateView, today, by, onRead, onView, onOpenPrivate }: DocStatic & { doc: DocRef; headingLevel?: 2 | 3 | 4 | 5 }) {
  const fixed = evidence !== undefined;
  const ses = useDocSession({ enabled: true, signedIn, privateView, by, level: doc.level });
  const held = doc.level === "P3" && !ses.priv?.open;
  const auto = !!doc.level && !isRestricted(doc.level);
  const { answer, setAnswer, setLoaded } = useAnswer(doc.address, evidence, !doc.document && ses.isIn && !held);
  const viewer = onView ?? (fixed ? null : viewDocument);
  const v = useViewer(viewer, ses.who);
  const reader = onRead ?? (fixed ? null : refreshEvidence);
  const reread = useReread(doc.address, ses.who, reader, (fresh) => { setAnswer(fresh); setLoaded(true); });
  const [modal, setModal] = useState(false);
  const started = useRef(false);
  const showButton = useRef<HTMLButtonElement | null>(null);
  const titleId = useId();
  const docs: EvidenceDocument[] = answer?.documents?.length ? answer.documents : doc.document ? [asEvidenceDocument(doc)] : [];
  const index = doc.document ? Math.max(0, docs.findIndex((d) => d.id === doc.document)) : firstDocument(docs);
  const target = docs[index] ? { address: doc.address, document: docs[index].id } : undefined;
  const show = () => { if (!started.current && target && viewer && ses.isIn && !held) { started.current = true; void v.open(index, target); } };
  useEffect(() => { if (auto && ses.known) show(); });   // P0 or P1: the screen's subject, viewed once it can be
  const H = `h${headingLevel}` as "h3";
  const readAt = answer?.sources?.[0]?.readAt || doc.readAt || "";
  const refreshable = answer?.refreshable ?? doc.refreshable ?? null;
  const view = v.viewing;
  const caveats = view?.data?.caveats ?? [];
  const unmasked = caveats.filter((c) => /^unmasked\b/i.test(c));
  let state: ReactNode = null;
  if (!ses.known) state = <StateLine>{DOC_WORDS.loading}</StateLine>;
  else if (!ses.isIn) state = <StateLine>{DOC_WORDS.signedOut}: <a href={ses.href}>Sign in with Google</a></StateLine>;
  else if (held) state = <NeedsPrivate priv={ses.priv} name={ses.name || ses.who} onOpenPrivate={onOpenPrivate} />;
  else if (view?.busy) state = <StateLine>{DOC_WORDS.loading}</StateLine>;
  else if (view?.error) state = <StateLine tone="error">{view.error}{view.signIn && <> <a href={view.signIn}>Sign in with Google</a></>}</StateLine>;
  else if (!target && (answer || fixed)) state = <MissingLine answer={answer} refreshable={!!refreshable} />;
  return (
    <section className="doc-inline" role="region" aria-labelledby={titleId} aria-busy={view?.busy ? true : undefined}>
      <header className="doc-inline-head">
        <H id={titleId} className="doc-inline-name">{doc.name}</H>
        <span className="doc-inline-meta muted">
          <span>{docKindWord(doc.kind)}</span>
          {doc.source && <span>{doc.source}</span>}
          {readAt && <span>copy from <time dateTime={readAt}>{copyDay(readAt, today)}</time></span>}
          {doc.level === "P3" && <span className="private-chip">Confidential</span>}
        </span>
        {(answer?.changed === true || doc.stale) && <span className="drive-preview-changed">{doc.stale || CHANGED_IN_DRIVE}</span>}
        <span className="doc-inline-acts">
          {refreshable && (
            <button type="button" className="link" aria-label={`Read ${doc.name} again from ${refreshable.system}`}
              aria-disabled={!ses.isIn || held || reread.busy || !reader ? true : undefined} aria-busy={reread.busy ? true : undefined}
              onClick={() => { if (ses.isIn && !held) void reread.read(refreshable.system); }}><RereadIcon /><span className="visually-hidden">Read again</span></button>
          )}
          {doc.original && <a href={doc.original.url} target="_blank" rel="noreferrer">{doc.original.label}<span className="visually-hidden"> (opens in a new tab)</span></a>}
          {view?.data && <button type="button" className="link" onClick={() => setModal(true)}>Open in viewer</button>}
        </span>
      </header>
      <div aria-live="polite" className="doc-inline-status">{state}<Said said={reread.said} /></div>
      {ses.isIn && !held && !auto && !view && target && (
        <p className="doc-inline-show">
          <button type="button" ref={showButton} onClick={show} aria-disabled={!viewer ? true : undefined}>{DOC_WORDS.show}</button>
          <span className="muted"> {DOC_WORDS.logged}</span>
        </p>
      )}
      {view?.data && !view.busy && (
        <div className="doc-inline-body">
          {isConfidential(view.data) && <p className="notice notice-warn private-confidential-line">Confidential: shown in the private view; this view is logged.</p>}
          {unmasked.map((c, i) => <p key={i} className="notice notice-warn doc-viewer-unmasked">{c}</p>)}
          <Caveats items={caveats.filter((c) => !/^unmasked\b/i.test(c))} />
          <DocumentBody v={view.data} />
        </div>
      )}
      {modal && view?.data && (
        <DocumentViewer data={view.data} document={docs[view.index]} busy={false} onClose={() => setModal(false)} today={today} />
      )}
    </section>
  );
}

// --- row ----------------------------------------------------------------------------------------------------------------

/** One document in a list (the evidence panel's Documents row): its name, a Confidential chip for P3, its kind and size,
 * View, and its source; with `extras`, a 48px thumbnail, its age, the stale line, ↻, and the original. */
function DocRowBody({ doc, extras, why, whyId, busy, button, onOpen, today, signedIn }: {
  doc: DocRef; extras: boolean; why: string; whyId: string; busy: boolean; signedIn: boolean;
  button: (el: HTMLButtonElement | null) => void; onOpen: () => void; today?: Date;
}) {
  const size = doc.kind === "submission" || doc.size == null ? "" : humanSize(doc.size);
  const path = pathOfAddress(doc.address);
  const driveId = driveIdOfAddress(doc.address);
  const [img, setImg] = useState(true);
  const src = !extras || !doc.thumb || !signedIn || doc.level === "P3" ? ""
    : driveId ? driveThumbUrl(driveId, doc.readAt) : path && /\.pdf$/i.test(path) ? thumbUrl(path, doc.readAt) : "";
  return (
    <>
      {extras && (
        <span className="doc-row-thumb" aria-hidden={src && img ? undefined : true}>
          {src && img ? <img src={src} alt={doc.name} width={48} loading="lazy" onError={() => setImg(false)} /> : <Glyph kind={doc.kind} />}
        </span>
      )}
      <span className="evidence-document-name">{doc.name}</span>
      {isConfidential(doc) && <span className="private-chip">Confidential</span>}
      <span className="muted evidence-document-kind">{docKindWord(doc.kind)}{size ? ` · ${size}` : ""}{extras && doc.readAt ? <> · copy from <time dateTime={doc.readAt}>{copyDay(doc.readAt, today)}</time></> : null}</span>
      <button type="button" ref={button} aria-label={`View ${doc.name}`}
        aria-disabled={why || busy ? true : undefined} aria-describedby={why ? whyId : undefined}
        onClick={onOpen}>
        View
      </button>
      {extras && doc.original && <a href={doc.original.url} target="_blank" rel="noreferrer" className="doc-row-original">{doc.original.label}<span className="visually-hidden"> (opens in a new tab)</span></a>}
      {extras && doc.stale && <span className="drive-preview-changed evidence-document-note">{doc.stale}</span>}
      {doc.source && <span className="muted evidence-document-note">{doc.source}</span>}
    </>
  );
}

/** A list of documents (`DocList`): a heading, one line on what viewing does, and a row per reference, with one viewer
 * whose Previous and Next walk the list, each a logged view. The evidence panel's Documents list is this list, without
 * `extras`.
 *
 * `onView` stands in for the server's view (then no sign-in is asked); `noView` says the copy is shown as given and
 * opens nothing; `by` is who views (omitted: the session's name); `approval` goes with each view. */
export function DocList({ docs, variant = "row", title = "Documents", level = 4, lead = "Viewing shows the document unmasked, under your name, and is logged.",
  approval, by, onView, noView = false, extras = true, today, ...rest }: DocStatic & {
  docs: readonly DocRef[]; variant?: "row" | "card" | "chip"; title?: string; level?: 3 | 4 | 5 | 6; lead?: string;
  approval?: string; noView?: boolean; extras?: boolean;
}) {
  const titleId = useId();
  if (variant !== "row") {
    return (
      <section className={`doc-list doc-list-${variant}`} aria-labelledby={title ? titleId : undefined}>
        {title && <Heading level={level} id={titleId}>{title}</Heading>}
        <ul className={`doc-list-${variant}s`}>
          {docs.map((d, i) => <li key={`${d.address}#${d.document ?? ""}#${i}`}><Doc doc={d} variant={variant} by={by} onView={onView} today={today} {...rest} /></li>)}
        </ul>
      </section>
    );
  }
  return <DocRows docs={docs} title={title} level={level} lead={lead} approval={approval} by={by} onView={onView} noView={noView} extras={extras} today={today} signedIn={rest.signedIn} />;
}

function Heading({ level, id, children }: { level: 3 | 4 | 5 | 6; id: string; children: string }) {
  const H = `h${Math.min(level + 1, 6)}` as "h5";
  return <H id={id} className="evidence-documents-title">{children}</H>;
}

/** The region name a single `row` Doc takes: its document's name, said as the row in a list, so a screen that shows the
 * same document `inline` beside its row (mail triage) has two regions with two names. */
export const rowRegionName = (name: string) => `${name} (in the list)`;

function DocRows({ docs, title, level, lead, approval, by, onView, noView, extras, today, signedIn, regionLabel }: {
  docs: readonly DocRef[]; title: string; level: 3 | 4 | 5 | 6; lead: string; approval?: string; by?: string;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>; noView: boolean; extras: boolean; today?: Date; signedIn?: boolean;
  /** The region's name when it is not its heading's (a single row Doc: `rowRegionName`). */
  regionLabel?: string;
}) {
  const viewer = noView ? null : onView ?? viewDocument;
  const live = !onView && !!viewer;
  const account = useAccount(live && signedIn === undefined && docs.length > 0);
  const sessionMe = useMe(by === undefined && !!viewer && docs.length > 0);
  const who = (by ?? sessionMe).trim();
  const known = signedIn !== undefined || account.known;
  const isIn = signedIn ?? !!account.account;
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const inFlight = useRef(false);
  const v = useViewer(viewer, who, approval);
  const titleId = useId();
  const whyId = useId();
  const listed = docs.map(asEvidenceDocument);
  const needsSignIn = !live ? "" : !known ? "Checking your sign-in…" : isIn ? "" : "Sign in with Google to view it.";
  const why = !viewer
    ? "This copy is shown as given; the page does not open its documents."
    : needsSignIn || (!who ? "Sign in or pick your name to view it." : "");
  const open = async (i: number) => {
    if (inFlight.current || !docs[i]) return;
    inFlight.current = true;
    try {
      await v.open(i, { address: docs[i].address, document: docs[i].document ?? "" });
    } finally {
      inFlight.current = false;
    }
  };
  const view = (i: number) => {
    if (why || v.viewing) return;
    v.opener.current = buttons.current[i];
    void open(i);
  };
  const H = `h${Math.min(level + 1, 6)}` as "h5";
  return (
    <section className={`evidence-documents doc-list doc-list-row${extras ? " doc-list-extras" : ""}`}
      aria-labelledby={regionLabel ? undefined : titleId} aria-label={regionLabel}>
      <H id={titleId} className="evidence-documents-title">{title}</H>
      {lead && <p className="muted">{lead}</p>}
      {why && <p className="muted evidence-documents-why"><span id={whyId}>{why}</span>{needsSignIn && known && <> <a className="evidence-sign-in" href={account.href}>Sign in with Google</a></>}</p>}
      <ul>
        {docs.map((d, i) => (
          <li key={`${d.address}#${d.document ?? ""}#${i}`} className="evidence-document doc-row">
            <DocRowBody doc={d} extras={extras} why={why} whyId={whyId} busy={!!v.viewing?.busy} signedIn={isIn}
              button={(el) => { buttons.current[i] = el; }} onOpen={() => view(i)} today={today} />
          </li>
        ))}
      </ul>
      {v.viewing && (
        <DocumentViewer data={v.viewing.data} document={listed[v.viewing.index]} documents={listed} busy={v.viewing.busy} error={v.viewing.error} signIn={v.viewing.signIn}
          position={{ index: v.viewing.index, count: listed.length }} onGo={(i) => void open(i)} onClose={v.close} today={today} />
      )}
    </section>
  );
}

// --- Doc ----------------------------------------------------------------------------------------------------------------

export type DocVariant = "chip" | "row" | "card" | "inline";

export interface DocProps extends DocStatic {
  doc: DocRef;
  variant?: DocVariant;
  /** A Drive file's type, for its placeholder's word and the Google link before the evidence gives one (`card`). */
  driveKind?: DriveKind;
  /** The copy's label in the Preview button's name (`card` of a file on disk): "Recorded copy", "File on disk". */
  label?: string;
  /** The card's name line; off for the old wrappers, whose table cell names the document already. */
  showName?: boolean;
  /** The inline variant's heading level. */
  headingLevel?: 2 | 3 | 4 | 5;
  /** The file under data/ whose page 1 is the card's thumbnail, when the address is not a `file:` one (a wrapper's). */
  thumbPath?: string;
}

/** One document reference in the variant the screen needs (docs/console/doc-component.md). The prop is `doc`, not
 * `ref`, which React reserves. */
export function Doc({ doc, variant = "chip", driveKind, label, showName = true, headingLevel, thumbPath, ...rest }: DocProps) {
  if (variant === "card") {
    return driveIdOfAddress(doc.address)
      ? <DriveCard doc={doc} driveKind={driveKind ?? (doc.kind === "image" ? "image" : "doc")} showName={showName} {...rest} />
      : <FileCard doc={doc} label={label ?? doc.source ?? "File on disk"} showName={showName} thumbPath={thumbPath} {...rest} />;
  }
  if (variant === "inline") return <DocInline doc={doc} headingLevel={headingLevel} {...rest} />;
  if (variant === "row") {
    return <DocRows docs={[doc]} title={doc.name} level={4} lead="" by={rest.by} onView={rest.onView} noView={rest.evidence !== undefined && !rest.onView} extras today={rest.today} signedIn={rest.signedIn}
      regionLabel={rowRegionName(doc.name)} />;
  }
  return <DocChip doc={doc} {...rest} />;
}
