import { useId, useState } from "react";
import { ApiError, postJson, signInRefusal } from "../lib/api";
import { driveDocRef } from "../lib/docref";
import { useAccount, useMe } from "../lib/session";
import { Doc, driveAddress, type DriveKind } from "./Doc";
import type { DocumentView, DocumentViewRequest } from "./DocumentViewer";
import { RereadIcon, type EvidenceAnswer, type EvidenceRefreshRequest } from "./Evidence";

// The card and its helpers live in `Doc` (docs/console/doc-component.md); these names stay for their callers.
export { CHANGED_IN_DRIVE, DRIVE_COPY, copyDay, driveAddress, driveIdOf, googleLink, useSeen, type DriveKind } from "./Doc";

/** `POST /api/evidence/refresh-many`'s answer: which addresses were read again, which could not be (and why), and how
 * many the server does not read again. The answers themselves are not returned: the page refetches what it shows. */
export interface EvidenceRefreshMany { by: string; at: string; refreshed: string[]; failed: { address: string; error: string }[]; skipped: number }

/** A page's list of evidence addresses read again on one sign-in, as a named person's act, through the write guard. */
export function refreshManyEvidence(req: { addresses: string[]; by: string; batch?: string }): Promise<EvidenceRefreshMany> {
  return postJson<EvidenceRefreshMany>("/api/evidence/refresh-many", req);
}

const sentence = (s: string) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);

/** One Drive file as a sheet of paper: a thin wrapper over `<Doc variant="card">` for a `drive:<id>` reference (the
 * thumbnail from disk, the copy's age, "Changed in Drive since this copy", Preview, ↻ Read from Drive, Open in Google).
 * New screens pass the loader's `DocRef` to `Doc` instead.
 *
 * For previews and tests: `evidence` is a static answer (nothing fetched), `signedIn` fixes the sign-in, `thumb` the
 * image's URL; `onRead` and `onView` stand in for the server's calls. */
export function DrivePreview({ driveId, name, kind = "doc", evidence, signedIn, thumb, today, by, onRead, onView }: {
  driveId: string; name: string; kind?: DriveKind;
  evidence?: EvidenceAnswer | null; signedIn?: boolean; thumb?: string; today?: Date; by?: string;
  onRead?: (req: EvidenceRefreshRequest) => Promise<EvidenceAnswer>;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
}) {
  return (
    <Doc doc={driveDocRef(driveId, name, { kind: kind === "image" ? "image" : "pdf" })} variant="card" driveKind={kind} showName={false}
      evidence={evidence} signedIn={signedIn} thumb={thumb} today={today} by={by} onRead={onRead} onView={onView} />
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
