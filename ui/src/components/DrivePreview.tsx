import { useContext, useEffect, useId, useRef, useState } from "react";
import { ApiError, getJson, postJson, signInRefusal } from "../lib/api";
import { useAccount, useMe } from "../lib/session";
import { DocumentViewer, viewDocument, type DocumentView, type DocumentViewRequest, type EvidenceDocument } from "./DocumentViewer";
import { EvidenceVersion, RereadIcon, evidenceUrl, refreshEvidence, type EvidenceAnswer, type EvidenceRefreshRequest } from "./Evidence";

/** What a Drive file is, for its placeholder's word and the link to it when jason has none from Drive. */
export type DriveKind = "doc" | "sheet" | "slides" | "pdf" | "image" | "drive";

/** The evidence address of a Drive file (`jason.approvals.evidence`'s `drive:<id>` row). */
export const driveAddress = (driveId: string) => `drive:${driveId}`;

/** The name the evidence gives jason's copy (`Copy from Drive`): its `readAt` is when a person last read it from Drive. */
export const DRIVE_COPY = "Copy from Drive";
export const CHANGED_IN_DRIVE = "Changed in Drive since this copy";

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

/** `POST /api/evidence/refresh-many`'s answer: which addresses were read again, which could not be (and why), and how
 * many the server does not read again. The answers themselves are not returned: the page refetches what it shows. */
export interface EvidenceRefreshMany { by: string; at: string; refreshed: string[]; failed: { address: string; error: string }[]; skipped: number }

/** A page's list of evidence addresses read again on one sign-in, as a named person's act, through the write guard. */
export function refreshManyEvidence(req: { addresses: string[]; by: string; batch?: string }): Promise<EvidenceRefreshMany> {
  return postJson<EvidenceRefreshMany>("/api/evidence/refresh-many", req);
}

const sentence = (s: string) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);

/** "Oct 3", with the year when it is not this year's. */
export function copyDay(iso: string, today: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const same = d.getFullYear() === today.getFullYear();
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(same ? {} : { year: "numeric" }) });
}

/** Whether the element has scrolled into view (once); true at once where the browser has no IntersectionObserver. */
function useSeen(enabled: boolean) {
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

/** The document a Preview opens: the copy's PDF, else its image, else its text. */
function previewDocument(docs: EvidenceDocument[]): number {
  for (const id of ["pdf", "image", "text", "csv"]) {
    const i = docs.findIndex((d) => d.id === id);
    if (i >= 0) return i;
  }
  return -1;
}

const KIND_WORD: Record<DriveKind, string> = { doc: "Doc", sheet: "Sheet", slides: "Slides", pdf: "PDF", image: "Image", drive: "File" };

/** One Drive file as a sheet of paper: jason's thumbnail of it (`GET /api/drive/thumb/<id>`, from disk, never Google),
 * the copy's age, "Changed in Drive since this copy", and three small acts:
 * - **Preview** opens `DocumentViewer` on the copy's PDF (`POST /api/evidence/view`, a logged view);
 * - **↻ Read from Drive** exports it again (`POST /api/evidence/refresh` with `drive:<id>`), a signed-in person's click,
 *   never automatic;
 * - **Open in Google**, the original in a new tab.
 *
 * The evidence answer (`GET /api/evidence?address=drive:<id>`) is fetched once the cell scrolls into view, and again when
 * an `EvidenceVersion` around it changes (a batch read it). Nothing here calls Google. Signed out, the cell is a
 * placeholder that says "Sign in to see previews", never a broken image.
 *
 * For previews and tests: `evidence` is a static answer (nothing fetched), `signedIn` fixes the sign-in, `thumb` the
 * image's URL; `onRead` and `onView` stand in for the server's calls. */
export function DrivePreview({ driveId, name, kind = "doc", evidence, signedIn, thumb, today, by, onRead, onView }: {
  driveId: string; name: string; kind?: DriveKind;
  evidence?: EvidenceAnswer | null; signedIn?: boolean; thumb?: string; today?: Date; by?: string;
  onRead?: (req: EvidenceRefreshRequest) => Promise<EvidenceAnswer>;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
}) {
  const address = driveAddress(driveId);
  const fixed = evidence !== undefined;
  const account = useAccount(signedIn === undefined);
  const known = signedIn !== undefined || account.known;
  const isIn = signedIn ?? !!account.account;
  const sessionMe = useMe(by === undefined && signedIn === undefined);
  const who = (by ?? sessionMe).trim();
  const version = useContext(EvidenceVersion);
  const { ref, seen } = useSeen(!fixed);
  const [answer, setAnswer] = useState<EvidenceAnswer | null>(evidence ?? null);
  const [loaded, setLoaded] = useState(fixed);
  const [img, setImg] = useState<"loading" | "shown" | "failed">("loading");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<{ tone: "status" | "error"; text: string; signIn?: string } | null>(null);
  const [viewing, setViewing] = useState<{ index: number; data: DocumentView | null; busy: boolean; error: string; signIn?: string } | null>(null);
  const previewButton = useRef<HTMLButtonElement | null>(null);
  const alive = useRef(true);
  const whyId = useId();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => { if (fixed) { setAnswer(evidence ?? null); setLoaded(true); } }, [fixed, evidence]);
  useEffect(() => {
    if (fixed || !seen) return;
    const ctl = new AbortController();
    getJson<EvidenceAnswer>(evidenceUrl(address), ctl.signal).then(
      (a) => { setAnswer(a); setLoaded(true); },
      () => { if (!ctl.signal.aborted) setLoaded(true); },
    );
    return () => ctl.abort();
  }, [address, fixed, seen, version]);

  const copy = answer?.sources?.find((s) => s.name === DRIVE_COPY) ?? null;
  const docs = answer?.documents ?? [];
  const at = previewDocument(docs);
  const src = thumb ?? (copy ? `/api/drive/thumb/${encodeURIComponent(driveId)}?v=${encodeURIComponent(copy.readAt)}` : "");
  useEffect(() => { setImg("loading"); }, [src]);
  const showImage = known && isIn && !!src && img !== "failed";
  const link = answer?.link || googleLink(driveId, kind);
  const signInWhy = !known ? "Checking your sign-in…" : isIn ? "" : "Sign in with Google";
  const readWhy = signInWhy ? `${signInWhy === "Sign in with Google" ? "Sign in with Google to read it from Drive" : signInWhy}` : "";
  const viewWhy = signInWhy ? (signInWhy === "Sign in with Google" ? "Sign in with Google to preview it" : signInWhy)
    : at < 0 ? (loaded ? "No copy yet: read it from Drive first" : "Checking for jason's copy…") : "";
  const reader = onRead ?? (fixed ? null : refreshEvidence);
  const viewer = onView ?? (fixed ? null : viewDocument);

  const read = async () => {
    if (busy || readWhy || !reader) return;
    setBusy(true);
    setSaid({ tone: "status", text: "Reading from Google Drive…" });
    try {
      const fresh = await reader({ address, by: who });
      if (!alive.current) return;
      setAnswer(fresh);
      setLoaded(true);
      setSaid({ tone: "status", text: `Read from Google Drive just now by ${fresh.refreshed?.by || who}.` });
    } catch (e: unknown) {
      if (!alive.current) return;
      const message = e instanceof Error ? e.message : String(e);
      const status = e instanceof ApiError ? e.status : undefined;
      const asked = signInRefusal(e);
      setSaid({ tone: "error", text: asked || (status && [400, 403, 405, 409].includes(status)) ? message : `jason-web did not answer: ${message}`, signIn: asked?.href });
    } finally {
      if (alive.current) setBusy(false);
    }
  };

  const open = async (i: number) => {
    const d = docs[i];
    if (!d || !viewer) return;
    setViewing({ index: i, data: null, busy: true, error: "" });
    try {
      const v = await viewer({ address, document: d.id, by: who });
      if (alive.current) setViewing({ index: i, data: v, busy: false, error: "" });
    } catch (e: unknown) {
      if (!alive.current) return;
      const asked = signInRefusal(e);
      setViewing({ index: i, data: null, busy: false, error: e instanceof Error ? e.message : String(e), signIn: asked?.href });
    }
  };
  const preview = () => { if (!viewWhy && !viewing) void open(at); };
  const close = () => { setViewing(null); previewButton.current?.focus(); };

  const placeholder = !known ? "" : !isIn ? "Sign in to see previews" : (copy || !loaded) && img !== "failed" ? "" : "No preview yet";
  return (
    <div className="drive-preview" ref={ref}>
      <div className={`drive-preview-sheet drive-preview-${kind}`} aria-busy={!known || (isIn && !loaded) ? true : undefined}>
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
      {known && !isIn && <a className="drive-preview-sign-in" href={account.href}>Sign in with Google</a>}
      {(copy || answer?.changed === true) && (
        <div className="drive-preview-age">
          {copy && copy.readAt && <span className="muted">copy from <time dateTime={copy.readAt}>{copyDay(copy.readAt, today)}</time></span>}
          {answer?.changed === true && <span className="drive-preview-changed">{CHANGED_IN_DRIVE}</span>}
        </div>
      )}
      <div className="drive-preview-acts">
        <button type="button" className="link" ref={previewButton} aria-label={`Preview ${name}`}
          aria-disabled={viewWhy || !viewer ? true : undefined} title={viewWhy ? sentence(viewWhy) : "Opens jason's copy; the view is logged under your name."}
          onClick={preview}>Preview</button>
        <button type="button" className="link drive-preview-read" aria-label={`Read ${name} from Drive`}
          aria-disabled={readWhy || busy || !reader ? true : undefined} aria-busy={busy ? true : undefined}
          aria-describedby={readWhy ? whyId : undefined}
          title={readWhy ? sentence(readWhy) : "Exports it from Google Drive now, under your name; writes nothing to Drive."}
          onClick={read}><RereadIcon />Read from Drive</button>
        <a href={link} target="_blank" rel="noreferrer">Open in Google<span className="visually-hidden"> (opens in a new tab)</span></a>
      </div>
      {readWhy && <span id={whyId} className="visually-hidden">{sentence(readWhy)}</span>}
      <span aria-live="polite" className="drive-preview-status">
        {said && <span className={said.tone === "error" ? "notice notice-error" : "muted"}>{said.text}{said.signIn && <> <a href={said.signIn}>Sign in with Google</a></>}</span>}
      </span>
      {viewing && (
        <DocumentViewer data={viewing.data} document={docs[viewing.index]} documents={docs} busy={viewing.busy} error={viewing.error}
          signIn={viewing.signIn} position={{ index: viewing.index, count: docs.length }} onGo={(i) => void open(i)} onClose={close} today={today} />
      )}
    </div>
  );
}

const plural = (n: number, what: string) => `${n} ${n === 1 ? what : `${what}s`}`;

/** "Read every template from Drive": each of `driveIds` exported again from Drive (`POST /api/evidence/refresh-many`)
 * on one sign-in, as a signed-in person's act; never on load. A summary line says what was read and what was not;
 * `onDone` runs after a batch the server answered, so the cells fetch their answers again. */
export function ReadAllFromDrive({ driveIds, what = "template", by, batch = "", onDone }: {
  driveIds: readonly string[]; what?: string; by?: string; batch?: string; onDone?: (r: EvidenceRefreshMany) => void;
}) {
  const ids = [...new Set(driveIds.filter(Boolean))];
  const account = useAccount(ids.length > 0);
  const sessionMe = useMe(by === undefined && ids.length > 0);
  const who = (by ?? sessionMe).trim();
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<{ tone: "status" | "warn" | "error"; text: string; signIn?: string } | null>(null);
  const whyId = useId();
  if (!ids.length) return null;
  const why = !account.known ? "Checking your sign-in…" : account.account ? "" : `Sign in with Google to read them from Drive.`;

  const readAll = async () => {
    if (busy || why) return;
    setBusy(true);
    setSaid({ tone: "status", text: `Reading ${plural(ids.length, what)} from Google Drive…` });
    try {
      const r = await refreshManyEvidence({ addresses: ids.map(driveAddress), by: who, ...(batch ? { batch } : {}) });
      const failed = r.failed ?? [];
      const done = `Read ${plural((r.refreshed ?? []).length, what)} from Google Drive just now by ${r.by || who}.`;
      const missed = failed.length ? ` ${failed.length} could not be read: ${failed.map((f) => f.error).join("; ")}` : "";
      setSaid({ tone: failed.length ? "warn" : "status", text: sentence(done + missed) });
      onDone?.(r);
    } catch (e: unknown) {
      const status = e instanceof ApiError ? e.status : undefined;
      const message = e instanceof Error ? e.message : String(e);
      const asked = signInRefusal(e);
      setSaid({ tone: "error", text: asked || (status && [400, 403, 405, 409].includes(status)) ? message : `jason-web did not answer: ${message}`, signIn: asked?.href });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="evidence-reread-all-row">
      <button type="button" className="evidence-reread-all"
        title={`Exports each ${what} from Google Drive now, under your name; writes nothing to Drive.`}
        aria-disabled={busy || !!why ? true : undefined} aria-busy={busy ? true : undefined}
        aria-describedby={why ? whyId : undefined} onClick={readAll}>
        <RereadIcon />Read every {what} from Drive
      </button>
      {why && <span className="muted evidence-reread-all-why"><span id={whyId}>{why}</span>{account.known && !account.account && <> <a href={account.href}>Sign in with Google</a></>}</span>}
      <span aria-live="polite" className="evidence-reread-all-status">
        {said && <span className={said.tone === "error" ? "notice notice-error" : said.tone === "warn" ? "notice notice-warn" : "muted"}>{said.text}{said.signIn && <> <a href={said.signIn}>Sign in with Google</a></>}</span>}
      </span>
    </div>
  );
}
