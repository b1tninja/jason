/** A document reference (docs/console/doc-component.md, "The reference"): what a loader returns for each document a
 * screen names, built on the server by `jason.approvals.docref`. It names the document by its evidence address, never
 * by a URL into data/, an absolute path, or its contents. The server decides the level; the client never infers it. */

/** What a document renders as; the renderer is chosen by kind, never by the address. */
export type DocKind = "submission" | "form" | "pdf" | "image" | "text" | "table" | "html" | "message" | "audio" | "file";

/** A document's data level (`jason.web.access.Level`); P4 is never served, so never referenced. */
export type DocLevel = "P0" | "P1" | "P2" | "P3";

export interface DocRef {
  /** The evidence address: "payhoa:submission:1234", "drive:ID", "library:ID", "file:board/minutes-draft-2099-01-01.md",
   * "CIV 4920(a)", "jason://decl/6.2(a)". */
  address: string;
  /** One document of the address ("pdf", "text", "submission", a file id); default: its first. */
  document?: string;
  /** What a person calls it, masked by the server if it held contact details. */
  name: string;
  kind: DocKind;
  level?: DocLevel;
  /** Which copy: "Recorded copy", "Drive copy", "PayHOA", "Scan", "Mailroom", "Library copy", "File on disk". */
  source?: string;
  /** When jason's copy was read, ISO. */
  readAt?: string;
  /** Bytes. */
  size?: number;
  /** The server has, or can make from disk, a thumbnail. */
  thumb?: boolean;
  /** "Open in Google", "Open in PayHOA", "Open in Gmail". */
  original?: { url: string; label: string };
  refreshable?: { system: string; what: string };
  /** "Changed in Drive since this copy", when the server knows. */
  stale?: string;
}

/** What `jason.approvals.docref.refs_from_strings` makes of an older store's free-text evidence: a reference, a command
 * (shown to copy, never run), or text as written (masked). */
export type EvidenceEntry = DocRef | { command: string } | { text: string };

export const isDocRef = (e: EvidenceEntry | null | undefined): e is DocRef => !!e && typeof (e as DocRef).address === "string";

export const DOC_KIND_WORD: Record<DocKind, string> = {
  submission: "Form submission", form: "Form", pdf: "PDF", image: "Image", text: "Text", table: "Table", html: "Page",
  message: "Message", audio: "Audio", file: "File",
};

/** The kind in words; an unknown kind is "File". */
export function docKindWord(kind: string): string {
  return DOC_KIND_WORD[kind as DocKind] ?? "File";
}

/** A P2 or P3 document: shown unmasked only by a person's click, never on mount. */
export function isRestricted(level: string | undefined): boolean {
  return level === "P2" || level === "P3";
}

/** The address's scheme: "drive", "file", "library", "payhoa", or "" for a citation or a command. */
export function addressScheme(address: string): string {
  const m = /^(drive|file|library|payhoa):/.exec(address);
  return m ? m[1] : "";
}

/** The Drive id of a `drive:<id>` address, else "". */
export function driveIdOfAddress(address: string): string {
  return address.startsWith("drive:") ? address.slice(6) : "";
}

/** The path under data/ of a `file:<path>` address, else "". */
export function pathOfAddress(address: string): string {
  return address.startsWith("file:") ? address.slice(5) : "";
}

/** A reference built in the browser from what an older loader gives (a Drive id, a path under data/): no level, which
 * the server decides when the document is opened. New loaders return `DocRef`s instead. */
export function driveDocRef(driveId: string, name: string, extra: Partial<DocRef> = {}): DocRef {
  return { address: `drive:${driveId}`, name, kind: "pdf", source: "Drive copy", ...extra };
}

export function fileDocRef(path: string, name: string, extra: Partial<DocRef> = {}): DocRef {
  const kind: DocKind = /\.pdf$/i.test(path) ? "pdf" : /\.(png|jpe?g|gif|webp)$/i.test(path) ? "image"
    : /\.(md|txt|csv)$/i.test(path) ? "text" : "file";
  return { address: `file:${path.replace(/\\/g, "/").replace(/^\/+/, "").replace(/^data\//, "")}`, name, kind, ...extra };
}
