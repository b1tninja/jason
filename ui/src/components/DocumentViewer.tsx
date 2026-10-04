import { useEffect, useId, useRef, useState, type KeyboardEvent, type SyntheticEvent } from "react";
import { createPortal } from "react-dom";
import { postJson } from "../lib/api";
import { when } from "../lib/approvals";
import { Caveats } from "./Caveats";
import { daysUntil } from "./DueDate";
import { Markdown } from "./Markdown";

export type EvidenceDocumentKind = "submission" | "pdf" | "image" | "text" | "file";

/** One document an evidence address holds (`GET /api/evidence`'s `documents`): what it is and how big, never its words.
 * Its contents come only from a view, a person's logged act. */
export interface EvidenceDocument { id: string; name: string; kind: EvidenceDocumentKind; size: number; readAt: string; note: string }

/** One question of a submitted form, as the owner answered it. */
export interface SubmissionQuestion { question: string; answer: string; kind: "text" | "choice" | "date" | "file" | "other" }

/** A form as the owner filled it in, unmasked. */
export interface DocumentSubmission { form: string; unit: string; submitted: string; status: string; questions: SubmissionQuestion[] }

/** `POST /api/evidence/view`'s answer: one document, unmasked, for the person who asked. `url` is a short-lived
 * `/api/evidence/document/<token>` for a pdf, image, or file (`expires` says until when). */
export interface DocumentView {
  kind: EvidenceDocumentKind; name: string; readAt: string; url: string; expires: string;
  submission?: DocumentSubmission | null; text?: string | null; caveats: string[];
}

/** The body of a view: the address, the approval whose plan it was read for, the document, and the person viewing. */
export interface DocumentViewRequest { address: string; approval?: string; document: string; by: string }

/** `POST /api/evidence/view`: one document opened unmasked, as a named person's act, through the write guard. A 400, 403,
 * 404, or 409 carries the server's `error`, said as it is. */
export function viewDocument(req: DocumentViewRequest): Promise<DocumentView> {
  return postJson<DocumentView>("/api/evidence/view", req);
}

const KIND_WORD: Record<EvidenceDocumentKind, string> = {
  submission: "Form submission", pdf: "PDF", image: "Image", text: "Text", file: "File",
};

/** The kind in words: "PDF", "Form submission". An unknown kind is "File". */
export function documentKindWord(kind: string): string {
  return KIND_WORD[kind as EvidenceDocumentKind] ?? "File";
}

/** A size people read: "812 bytes", "48 KB", "2.1 MB". Nothing for a size the server did not give. */
export function humanSize(bytes: number | null | undefined): string {
  if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} ${bytes === 1 ? "byte" : "bytes"}`;
  const units = ["KB", "MB", "GB", "TB"];
  let n = bytes / 1024;
  let u = 0;
  while (n >= 1024 && u < units.length - 1) { n /= 1024; u += 1; }
  return `${n < 10 ? n.toFixed(1).replace(/\.0$/, "") : Math.round(n)} ${units[u]}`;
}

function ago(iso: string, today?: Date): string {
  const days = -daysUntil(iso.slice(0, 10), today);
  if (Number.isNaN(days) || days < 0) return "";
  return days === 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`;
}

/** Text that reads as Markdown: it opens with a heading, or has `##` headings. */
export function looksLikeMarkdown(text: string): boolean {
  return /^\s*#{1,6}\s/.test(text) || /^#{2,6}\s/m.test(text);
}

const URL_KINDS: readonly string[] = ["pdf", "image", "file"];
const UNMASKED = /^unmasked\b/i;
const answerText = (a: unknown) => (Array.isArray(a) ? a.map(String).join(", ") : a == null ? "" : String(a));

function Submission({ s }: { s: DocumentSubmission }) {
  const questions = s.questions ?? [];
  return (
    <article className="doc-sheet doc-submission doc-print">
      <header className="doc-submission-head">
        <div>
          <h3 className="doc-submission-form">{s.form || "Form"}</h3>
          <p className="doc-submission-meta">
            {s.unit && <span>Unit {s.unit}</span>}
            {s.submitted && <span>Submitted <time dateTime={s.submitted.slice(0, 10)}>{s.submitted.slice(0, 10)}</time></span>}
            {s.status && <span className="badge badge-neutral">{s.status}</span>}
          </p>
        </div>
        <button type="button" className="doc-print-hide" onClick={() => window.print()}>Print</button>
      </header>
      {questions.length ? (
        <dl className="doc-answers">
          {questions.map((q, i) => {
            const a = answerText(q.answer).trim();
            return (
              <div key={i} className="doc-answer">
                <dt>{q.question}</dt>
                <dd className={`doc-answer-${q.kind || "other"}`}>{a || <span className="muted">(no answer)</span>}</dd>
              </div>
            );
          })}
        </dl>
      ) : (
        <p className="muted">The submission holds no questions.</p>
      )}
    </article>
  );
}

function ImageBody({ url, name }: { url: string; name: string }) {
  const [fit, setFit] = useState(true);
  return (
    <div className={`doc-image ${fit ? "doc-image-fit" : "doc-image-actual"}`}>
      <div className="seg doc-image-toggle" role="group" aria-label="Image size">
        <button type="button" aria-pressed={fit} onClick={() => setFit(true)}>Fit</button>
        <button type="button" aria-pressed={!fit} onClick={() => setFit(false)}>Actual size</button>
      </div>
      <div className="doc-image-frame">
        <img src={url} alt={name} />
      </div>
    </div>
  );
}

function Body({ v }: { v: DocumentView }) {
  if (v.kind === "submission") {
    return v.submission ? <Submission s={v.submission} /> : <p className="muted">The server sent no submission to show.</p>;
  }
  if (v.kind === "text") {
    const text = v.text ?? "";
    if (!text) return <p className="muted">The stored text is empty.</p>;
    return looksLikeMarkdown(text)
      ? <div className="doc-sheet doc-text doc-print"><Markdown text={text} /></div>
      : <div className="doc-sheet doc-text doc-text-plain doc-print">{text}</div>;
  }
  if (!v.url) return <p className="muted">The server gave no address for this document.</p>;
  if (v.kind === "pdf") {
    return (
      <div className="doc-pdf">
        <iframe src={v.url} title={v.name} className="doc-pdf-frame" />
        <p className="muted doc-pdf-fallback">
          Your browser can't show the PDF here; <a href={v.url} target="_blank" rel="noreferrer">open it in a new tab</a>.
        </p>
      </div>
    );
  }
  if (v.kind === "image") return <ImageBody url={v.url} name={v.name} />;
  return (
    <div className="doc-file">
      <p className="muted">jason shows no preview of this kind of file.</p>
      <p><a className="doc-download" href={v.url} download={v.name || true}>Download</a></p>
    </div>
  );
}

/** One document of an evidence address, shown unmasked in a modal `<dialog>` (the "pop out"): its name, when jason read
 * it, the server's caveats (the unmasked line in a notice), a new-tab link for a pdf, image, or file, Previous and Next
 * when the address holds several, and Close. The body is the document as its kind shows best: a submission as the form
 * the owner filled in, a pdf in a frame, an image fitted or at its actual size, text as read, a file to download.
 *
 * It fetches nothing: the panel POSTs the view on a person's click and passes the answer as `data` (`null` while it
 * opens, with `busy`), so each view is one logged act. `document` is the listed row, for the name while it opens. An
 * `error` stays in the dialog. Escape and Close call `onClose`, after the dialog has closed so focus can go back.
 * `inline` renders it open in place, not modal (previews). */
export function DocumentViewer({ data, document: listed, busy = false, error = "", position, onGo, onClose, today, inline = false }: {
  data?: DocumentView | null; document?: EvidenceDocument; busy?: boolean; error?: string;
  position?: { index: number; count: number }; onGo?: (index: number) => void; onClose?: () => void;
  today?: Date; inline?: boolean;
}) {
  const ref = useRef<HTMLDialogElement | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (!d.open) {
      if (!inline && typeof d.showModal === "function") d.showModal();
      else if (typeof d.show === "function") d.show();
      else d.setAttribute("open", "");
    }
    if (!inline) heading.current?.focus();
    return () => {
      if (d.open && typeof d.close === "function") d.close();
    };
  }, [inline]);

  const close = () => {
    const d = ref.current;
    if (d?.open && typeof d.close === "function" && !inline) d.close();
    onClose?.();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLDialogElement>) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    if (onClose) close();
  };
  const onCancel = (e: SyntheticEvent<HTMLDialogElement>) => {
    e.preventDefault();
    if (onClose) close();
  };

  const v = data ?? null;
  const kind = v?.kind ?? listed?.kind ?? "file";
  const name = v?.name || listed?.name || "Document";
  const readAt = v?.readAt || listed?.readAt || "";
  const since = readAt ? ago(readAt, today) : "";
  const caveats = v?.caveats ?? [];
  const unmasked = caveats.filter((c) => UNMASKED.test(c));
  const rest = caveats.filter((c) => !UNMASKED.test(c));
  const several = !!position && position.count > 1;
  const at = position?.index ?? 0;
  const hasPrev = several && at > 0;
  const hasNext = several && at < (position?.count ?? 0) - 1;
  const go = (i: number, ok: boolean) => { if (ok && !busy) onGo?.(i); };

  const dialog = (
    <dialog ref={ref} className={`doc-viewer doc-viewer-${kind}${inline ? " doc-viewer-inline" : ""}`}
      aria-labelledby={titleId} aria-modal={inline ? undefined : true}
      onKeyDown={onKeyDown} onCancel={onCancel}>
      <header className="doc-viewer-head">
        <div className="doc-viewer-titlebar">
          <h2 id={titleId} ref={heading} tabIndex={-1} className="doc-viewer-title">{name}</h2>
          <span className="doc-viewer-actions">
            {several && (
              <span className="doc-viewer-nav">
                <button type="button" aria-disabled={!hasPrev || busy ? true : undefined} onClick={() => go(at - 1, hasPrev)}>Previous</button>
                <span className="muted doc-viewer-count">{at + 1} of {position!.count}</span>
                <button type="button" aria-disabled={!hasNext || busy ? true : undefined} onClick={() => go(at + 1, hasNext)}>Next</button>
              </span>
            )}
            {onClose && <button type="button" onClick={close}>Close</button>}
          </span>
        </div>
        <p className="doc-viewer-meta muted">
          <span>{documentKindWord(kind)}</span>
          {readAt && <span>Read <time dateTime={readAt}>{when(readAt)}</time>{since ? ` (${since})` : ""}</span>}
          {v && v.url && URL_KINDS.includes(v.kind) && (
            <a href={v.url} target="_blank" rel="noreferrer">Open in a new tab<span className="visually-hidden"> ({name})</span></a>
          )}
          {v && v.url && v.expires && <span>The link works until <time dateTime={v.expires}>{when(v.expires)}</time>.</span>}
        </p>
        {unmasked.map((c, i) => <p key={i} className="notice notice-warn doc-viewer-unmasked">{c}</p>)}
        <Caveats items={rest} />
      </header>
      <div className={`doc-viewer-body doc-viewer-body-${kind}`} aria-busy={busy ? true : undefined}>
        <div aria-live="polite" className="doc-viewer-status">
          {busy && <p className="muted">Opening…</p>}
          {error && !busy && <p className="notice notice-error">{error}</p>}
        </div>
        {v && !busy && <Body v={v} />}
      </div>
    </dialog>
  );
  if (inline || typeof document === "undefined") return dialog;
  return createPortal(dialog, document.body);
}
