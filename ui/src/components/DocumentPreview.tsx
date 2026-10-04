import { fileDocRef } from "../lib/docref";
import { DRIVE_COPY_LABEL, Doc, RECORDED_COPY, driveIdOf, type DriveKind } from "./Doc";
import type { DocumentView, DocumentViewRequest } from "./DocumentViewer";
import { DrivePreview } from "./DrivePreview";
import type { EvidenceAnswer, EvidenceRefreshRequest } from "./Evidence";

// The card and its helpers live in `Doc` (docs/console/doc-component.md); these names stay for their callers.
export { DRIVE_COPY_LABEL, RECORDED_COPY, fileAddress, thumbUrl } from "./Doc";

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

/** A file jason keeps on disk (a recorded instrument's PDF, a packet file) as a sheet of paper: a thin wrapper over
 * `<Doc variant="card">` for its `file:<path>` address (or the `address` given: a library or citation address), with
 * page 1 rendered by the server (`GET /api/thumb?path=`) and Preview, a logged view. New screens pass the loader's
 * `DocRef` to `Doc` instead.
 *
 * For previews and tests: `evidence` is a static answer (nothing fetched), `signedIn` fixes the sign-in, `thumb` the
 * image's URL, and `onView` stands in for the server's view. */
export function LocalPreview({ path = "", address, name, label = RECORDED_COPY, evidence, signedIn, thumb, today, by, onView }: {
  path?: string; address?: string; name: string; label?: string;
  evidence?: EvidenceAnswer | null; signedIn?: boolean; thumb?: string; today?: Date; by?: string;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
}) {
  const doc = address ? { address, name, kind: (/\.pdf$/i.test(path) ? "pdf" : "file") as "pdf" | "file" } : fileDocRef(path, name);
  return (
    <Doc doc={doc} variant="card" label={label} showName={false} thumbPath={path} evidence={evidence}
      signedIn={signedIn} thumb={thumb} today={today} by={by} onView={onView} />
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
