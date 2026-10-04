import { useContext, useEffect, useRef, useState } from "react";
import { getJson, signInRefusal } from "../lib/api";
import { useAccount, useMe } from "../lib/session";
import { DocumentViewer, viewDocument, type DocumentView, type DocumentViewRequest, type EvidenceDocument } from "./DocumentViewer";
import { DrivePreview, driveIdOf, useSeen, type DriveKind } from "./DrivePreview";
import { EvidenceVersion, evidenceUrl, type EvidenceAnswer, type EvidenceRefreshRequest } from "./Evidence";

/** The evidence address of a file under the data folder (`jason.approvals.evidence`'s `file:<path>` row). */
export const fileAddress = (path: string) => `file:${path}`;

/** The two copies a document may have, as the cell names them: the recorded or adopted PDF jason keeps on disk (the copy
 * that governs a recorded instrument), and the Drive file (a working copy). AGENTS.md: "Recite the version that governs". */
export const RECORDED_COPY = "Recorded copy";
export const DRIVE_COPY_LABEL = "Drive copy";

/** `GET /api/thumb?path=`: page 1 of a PDF under data/, rendered on the server from disk (never Google). `stamp` busts
 * the browser's cache when the file changed. */
export function thumbUrl(path: string, stamp = ""): string {
  return `/api/thumb?path=${encodeURIComponent(path)}${stamp ? `&v=${encodeURIComponent(stamp)}` : ""}`;
}

const sentence = (s: string) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);

const DRIVE_KINDS: Record<string, DriveKind> = { doc: "doc", docx: "doc", document: "doc", sheet: "sheet", xlsx: "sheet", spreadsheet: "sheet", slides: "slides", presentation: "slides", pdf: "pdf", image: "image" };
const DRIVE_ID = /^[A-Za-z0-9_-]{10,200}$/;

/** A file attached to an agenda item or a packet (`DriveFile`, `PacketFile`), as the copies a preview can show: its Drive
 * id (the id when it looks like one, else the one in its Google link) and its path under the data folder (a `ref` that is
 * no URL), each "" when it has none. A sample file (a short made-up id, no link) has neither. */
export function attachedCopies(f: { id?: string; kind?: string; url?: string; ref?: string; real?: boolean }): { driveId: string; path: string; kind: DriveKind } {
  const link = f.url || (f.ref && /^https?:/i.test(f.ref) ? f.ref : "");
  const fromLink = link ? driveIdOf(link) : "";
  const id = String(f.id ?? "");
  const driveId = fromLink || (f.real !== false && DRIVE_ID.test(id) ? id : "");
  const ref = String(f.ref ?? "").replace(/\\/g, "/");
  const path = ref && !/^[a-z]+:/i.test(ref) && !driveId ? ref.replace(/^\/+/, "").replace(/^data\//, "") : "";
  return { driveId, path, kind: DRIVE_KINDS[(f.kind ?? "").toLowerCase()] ?? (/\.pdf$/i.test(path) ? "pdf" : "drive") };
}

/** The document a Preview opens first: the file itself (a PDF or an image), else its text. */
function firstDocument(docs: EvidenceDocument[]): number {
  for (const id of ["pdf", "image", "text"]) {
    const i = docs.findIndex((d) => d.id === id);
    if (i >= 0) return i;
  }
  return docs.length ? 0 : -1;
}

/** A file jason keeps on disk (a recorded instrument's PDF, a packet file) as a sheet of paper: page 1 rendered by the
 * server (`GET /api/thumb?path=`), and **Preview**, which opens `DocumentViewer` on the file through the evidence's
 * `file:<path>` address (or the `address` given: a library or citation address), a logged view. There is no "Read
 * again": a recorded copy does not change. Signed out, a placeholder asks for a sign-in, never a broken image.
 *
 * For previews and tests: `evidence` is a static answer (nothing fetched), `signedIn` fixes the sign-in, `thumb` the
 * image's URL, and `onView` stands in for the server's view. */
export function LocalPreview({ path = "", address, name, label = RECORDED_COPY, evidence, signedIn, thumb, today, by, onView }: {
  path?: string; address?: string; name: string; label?: string;
  evidence?: EvidenceAnswer | null; signedIn?: boolean; thumb?: string; today?: Date; by?: string;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
}) {
  const at_ = address || (path ? fileAddress(path) : "");
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
  const [viewing, setViewing] = useState<{ index: number; data: DocumentView | null; busy: boolean; error: string; signIn?: string } | null>(null);
  const previewButton = useRef<HTMLButtonElement | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => { if (fixed) { setAnswer(evidence ?? null); setLoaded(true); } }, [fixed, evidence]);
  useEffect(() => {
    if (fixed || !seen || !at_) return;
    const ctl = new AbortController();
    getJson<EvidenceAnswer>(evidenceUrl(at_), ctl.signal).then(
      (a) => { setAnswer(a); setLoaded(true); },
      () => { if (!ctl.signal.aborted) setLoaded(true); },
    );
    return () => ctl.abort();
  }, [at_, fixed, seen, version]);

  const docs = answer?.documents ?? [];
  const first = firstDocument(docs);
  const kept = answer?.sources?.[0]?.readAt ?? "";
  const isPdf = /\.pdf$/i.test(path);
  const src = thumb ?? (isPdf ? thumbUrl(path, kept) : "");
  useEffect(() => { setImg("loading"); }, [src]);
  const showImage = known && isIn && !!src && img !== "failed";
  const signInWhy = !known ? "Checking your sign-in…" : isIn ? "" : "Sign in with Google to preview it";
  const viewWhy = signInWhy || (first < 0 ? (loaded ? (answer?.note || "Not on disk") : "Checking for jason's copy…") : "");
  const viewer = onView ?? (fixed ? null : viewDocument);

  const open = async (i: number) => {
    const d = docs[i];
    if (!d || !viewer) return;
    setViewing({ index: i, data: null, busy: true, error: "" });
    try {
      const v = await viewer({ address: at_, document: d.id, by: who });
      if (alive.current) setViewing({ index: i, data: v, busy: false, error: "" });
    } catch (e: unknown) {
      if (!alive.current) return;
      const asked = signInRefusal(e);
      setViewing({ index: i, data: null, busy: false, error: e instanceof Error ? e.message : String(e), signIn: asked?.href });
    }
  };
  const preview = () => { if (!viewWhy && !viewing) void open(first); };
  const close = () => { setViewing(null); previewButton.current?.focus(); };
  const placeholder = !known ? "" : !isIn ? "Sign in to see previews" : src && img !== "failed" ? "" : "No preview yet";

  return (
    <div className="drive-preview doc-preview-local" ref={ref}>
      <div className="drive-preview-sheet drive-preview-pdf" aria-busy={!known ? true : undefined}>
        {showImage && (
          <img src={src} alt={name} loading="lazy" width={96} className={img === "shown" ? "drive-preview-img is-shown" : "drive-preview-img"}
            onLoad={() => setImg("shown")} onError={() => setImg("failed")} />
        )}
        {img !== "shown" && (
          <span className="drive-preview-placeholder">
            <span className="drive-preview-kind">{isPdf ? "PDF" : "File"}</span>
            {placeholder && <span className="drive-preview-none">{placeholder}</span>}
          </span>
        )}
      </div>
      {known && !isIn && <a className="drive-preview-sign-in" href={account.href}>Sign in with Google</a>}
      <div className="drive-preview-acts">
        <button type="button" className="link" ref={previewButton} aria-label={`Preview ${name}, ${label.toLowerCase()}`}
          aria-disabled={viewWhy || !viewer ? true : undefined}
          title={viewWhy ? sentence(viewWhy) : "Opens jason's copy on disk; the view is logged under your name."}
          onClick={preview}>Preview</button>
      </div>
      {viewing && (
        <DocumentViewer data={viewing.data} document={docs[viewing.index]} documents={docs} busy={viewing.busy} error={viewing.error}
          signIn={viewing.signIn} position={{ index: viewing.index, count: docs.length }} onGo={(i) => void open(i)} onClose={close} today={today} />
      )}
    </div>
  );
}

/** One document's preview cell, whatever copies it has:
 * - `driveId` alone: `DrivePreview` as it is (thumbnail, copy's age, Preview, ↻ Read from Drive, Open in Google);
 * - `path` (or an evidence `address`) alone: `LocalPreview`, jason's file on disk;
 * - both: the two side by side, labelled "Recorded copy" (the copy that governs a recorded instrument) and "Drive copy"
 *   (a working copy), the recorded one first.
 *
 * A file on disk is always labelled; a Drive file alone is not, unless `labelled` (a list that mixes rows with one copy
 * and rows with two). `recordedLabel` names the
 * file on disk when it is not a recorded instrument ("File on disk" for a packet file). The static props are for
 * previews and tests: `driveEvidence`/`recordedEvidence` fix each copy's answer, `signedIn` the sign-in, `driveThumb`
 * and `recordedThumb` the images, `onRead` and `onView` the server's calls. */
export function DocumentPreview({ name, driveId = "", kind = "doc", path = "", address = "", labelled, recordedLabel = RECORDED_COPY,
  driveEvidence, recordedEvidence, signedIn, driveThumb, recordedThumb, today, by, onRead, onView }: {
  name: string; driveId?: string; kind?: DriveKind; path?: string; address?: string; labelled?: boolean; recordedLabel?: string;
  driveEvidence?: EvidenceAnswer | null; recordedEvidence?: EvidenceAnswer | null; signedIn?: boolean;
  driveThumb?: string; recordedThumb?: string; today?: Date; by?: string;
  onRead?: (req: EvidenceRefreshRequest) => Promise<EvidenceAnswer>;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
}) {
  const local = !!(path || address);
  const drive = !!driveId;
  const both = local && drive;
  const label = labelled ?? local;              // a file on disk always says which copy it is; a Drive file alone is as it was
  const localCell = local && (
    <LocalPreview path={path} address={address || undefined} name={name} label={recordedLabel} evidence={recordedEvidence}
      signedIn={signedIn} thumb={recordedThumb} today={today} by={by} onView={onView} />
  );
  const driveCell = drive && (
    <DrivePreview driveId={driveId} name={name} kind={kind} evidence={driveEvidence} signedIn={signedIn} thumb={driveThumb}
      today={today} by={by} onRead={onRead} onView={onView} />
  );
  if (!local && !drive) return <span className="muted doc-preview-none">No copy</span>;
  if (!label) return <>{localCell || driveCell}</>;
  return (
    <div className={both ? "doc-preview doc-preview-both" : "doc-preview"}>
      {local && (
        <section className="doc-preview-copy" aria-label={`${recordedLabel}: ${name}`}>
          <span className="doc-preview-label">{recordedLabel}</span>
          {localCell}
        </section>
      )}
      {drive && (
        <section className="doc-preview-copy" aria-label={`${DRIVE_COPY_LABEL}: ${name}`}>
          <span className="doc-preview-label">{DRIVE_COPY_LABEL}</span>
          {driveCell}
        </section>
      )}
    </div>
  );
}
