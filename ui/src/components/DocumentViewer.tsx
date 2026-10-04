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

/** What a row of a submitted form is: a `section` heading (a divider and its title), a `note` (the form's own words),
 * a lone box (`check`), or a question and its answer. */
export type SubmissionRowKind = "section" | "note" | "text" | "choice" | "date" | "file" | "check" | "other";

/** One row of a submitted form, as the owner answered it: the question (a section's heading, a note's words), the
 * answer, the question's help, whether it was required, a `flag` the server raises ("both given"), and for a file
 * question the ids of the documents saved for its files (the address's own documents, opened with a new view). */
export interface SubmissionQuestion {
  question: string; answer: string; kind: SubmissionRowKind;
  help?: string; required?: boolean; flag?: string; files?: string[];
}

/** A form as the owner filled it in, unmasked: the form's own introduction (`intro`), when it was submitted, and when
 * it was completed (`completed`, YYYY-MM-DD) once it was. */
export interface DocumentSubmission {
  form: string; unit: string; submitted: string; completed?: string; status: string; intro?: string;
  questions: SubmissionQuestion[];
}

/** `POST /api/evidence/view`'s answer: one document, unmasked, for the person who asked. `url` is a short-lived
 * `/api/evidence/document/<token>` for a pdf, image, or file (`expires` says until when). */
export interface DocumentView {
  kind: EvidenceDocumentKind; name: string; readAt: string; url: string; expires: string;
  submission?: DocumentSubmission | null; text?: string | null; caveats: string[];
}

/** The body of a view: the address, the approval whose plan it was read for, the document, and the person viewing. */
export interface DocumentViewRequest { address: string; approval?: string; document: string; by: string }

/** `POST /api/evidence/view`: one document opened unmasked, as the signed-in person's act, through the write guard. A
 * 400, 403, 404, or 409 carries the server's `error`, said as it is; a 401 asks for a Google sign-in (`signIn`). */
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

/** How the sheet opens another document of the address: by its place in `documents`, through the same logged view
 * Previous and Next take. */
interface Opener { documents: EvidenceDocument[]; open: (index: number) => void; busy: boolean }

/** A file question's answer: each file's name, a button that opens it in the viewer when jason saved it (a new
 * logged view), plain text when it did not. A saved file whose name the answer does not carry follows by its own. */
function FileAnswer({ q, opener }: { q: SubmissionQuestion; opener: Opener }) {
  const docs = opener.documents;
  const names = answerText(q.answer).split("; ").map((n) => n.trim()).filter(Boolean);
  const linked = (q.files ?? []).map((id) => docs.findIndex((d) => d.id === id)).filter((i) => i >= 0);
  const used = new Set<number>();
  const items = names.map((name) => {
    const index = linked.find((i) => !used.has(i) && (docs[i].name === name || docs[i].name.endsWith(`_${name}`)));
    if (index !== undefined) used.add(index);
    return { name, index };
  });
  for (const i of linked) if (!used.has(i)) items.push({ name: docs[i].name, index: i });
  if (!items.length) return <span className="muted">(no answer)</span>;
  return (
    <>
      {items.map((it, k) => (
        <span key={k} className="doc-answer-file">
          {k > 0 && "; "}
          {it.index !== undefined ? (
            <button type="button" className="doc-answer-open" aria-disabled={opener.busy ? true : undefined}
              title={`Open ${it.name} in the viewer`} onClick={() => { if (!opener.busy) opener.open(it.index!); }}>
              {it.name}
            </button>
          ) : it.name}
        </span>
      ))}
    </>
  );
}

function AnswerRow({ q, opener }: { q: SubmissionQuestion; opener?: Opener }) {
  const a = answerText(q.answer).trim();
  return (
    <div className="doc-answer">
      <dt>
        <span className="doc-answer-question">{q.question}</span>
        {q.required && <> <span className="doc-answer-required">required</span></>}
        {q.help && <small className="doc-answer-help">{q.help}</small>}
      </dt>
      <dd className={`doc-answer-${q.kind || "other"}`}>
        {q.kind === "file" && q.files?.length && opener ? <FileAnswer q={q} opener={opener} />
          : a || <span className="muted">(no answer)</span>}
        {q.flag && <> <span className="chip doc-answer-flag">{q.flag}</span></>}
      </dd>
    </div>
  );
}

type Block = { kind: "section"; q: SubmissionQuestion } | { kind: "note"; q: SubmissionQuestion }
  | { kind: "answers"; rows: SubmissionQuestion[] };

/** The rows as the form lays them out: a heading per section, the form's notes, and the answers between them. */
function blocks(rows: SubmissionQuestion[]): Block[] {
  const out: Block[] = [];
  for (const q of rows) {
    if (q.kind === "section") out.push({ kind: "section", q });
    else if (q.kind === "note") out.push({ kind: "note", q });
    else {
      const last = out[out.length - 1];
      if (last && last.kind === "answers") last.rows.push(q);
      else out.push({ kind: "answers", rows: [q] });
    }
  }
  return out;
}

function Submission({ s, opener }: { s: DocumentSubmission; opener?: Opener }) {
  const questions = s.questions ?? [];
  return (
    <article className="doc-sheet doc-submission doc-print">
      <header className="doc-submission-head">
        <div>
          <h3 className="doc-submission-form">{s.form || "Form"}</h3>
          <p className="doc-submission-meta">
            {s.unit && <span>Unit {s.unit}</span>}
            {s.submitted && <span>Submitted <time dateTime={s.submitted.slice(0, 10)}>{s.submitted.slice(0, 10)}</time></span>}
            {s.completed && <span>Completed <time dateTime={s.completed.slice(0, 10)}>{s.completed.slice(0, 10)}</time></span>}
            {s.status && <span className="badge badge-neutral">{s.status}</span>}
          </p>
        </div>
        <button type="button" className="doc-print-hide" onClick={() => window.print()}>Print</button>
      </header>
      {s.intro && <p className="muted doc-submission-intro">{s.intro}</p>}
      {questions.length ? (
        blocks(questions).map((b, i) => {
          if (b.kind === "section") return <h4 key={i} className="doc-submission-section">{b.q.question}</h4>;
          if (b.kind === "note") return <p key={i} className="muted doc-submission-note">{b.q.question}</p>;
          return (
            <dl key={i} className="doc-answers">
              {b.rows.map((q, k) => <AnswerRow key={k} q={q} opener={opener} />)}
            </dl>
          );
        })
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

function Body({ v, opener }: { v: DocumentView; opener?: Opener }) {
  if (v.kind === "submission") {
    return v.submission ? <Submission s={v.submission} opener={opener} /> : <p className="muted">The server sent no submission to show.</p>;
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
 * `inline` renders it open in place, not modal (previews).
 *
 * `documents` is the address's list (the one `position` counts): given with `onGo`, a submission's file answer names
 * each saved file as a button that opens it, by `onGo` with its place in the list, a new logged view. */
export function DocumentViewer({ data, document: listed, documents, busy = false, error = "", signIn = "", position, onGo, onClose, today, inline = false }: {
  data?: DocumentView | null; document?: EvidenceDocument; documents?: EvidenceDocument[]; busy?: boolean; error?: string;
  /** Where "Sign in with Google" goes, when the `error` is the server asking for a sign-in (401). */
  signIn?: string;
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
  const opener: Opener | undefined = documents?.length && onGo
    ? { documents, open: (i) => go(i, i >= 0 && i < documents.length), busy }
    : undefined;

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
          {error && !busy && (
            <p className="notice notice-error">{error}{signIn && <> <a className="doc-viewer-sign-in" href={signIn}>Sign in with Google</a></>}</p>
          )}
        </div>
        {v && !busy && <Body v={v} opener={opener} />}
      </div>
    </dialog>
  );
  if (inline || typeof document === "undefined") return dialog;
  return createPortal(dialog, document.body);
}
