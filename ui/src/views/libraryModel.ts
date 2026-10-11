import { postJson } from "../lib/api";

/** One file of the library as the explorer lists it (docs/pdf-splitter.md, "Choosing a file from the library"). A confidential file
 * has no `id` outside the private view and is named by its kind. */
export interface LibraryFile {
  id: string; name: string; kind: string; source: string; sourceLabel: string; pages: number | null; size: number | null; modified: string; added: string;
  hasText: boolean; draft: { id: string; status: string } | null; held: boolean; copies: number; onDisk: boolean; openable: boolean; why: string; opens: string;
}

export interface LibraryCounts { kinds: Record<string, number>; sources: Record<string, number>; files: number; all: number; noText: number; withDraft: number; notHere: number }

export interface LibraryAnswer {
  found: boolean; files: LibraryFile[]; total: number; next: string | null; counts: LibraryCounts; uncounted: number; sort: string; order: string;
  empty: string; why?: string; command?: string; caveats?: string[];
}

export type TextFilter = "" | "yes" | "no";
export type LibrarySort = "modified" | "name" | "kind" | "pages" | "size";

/** What a person asked of the list. The name goes in a POST body, never a web address. */
export interface LibraryQuery {
  q: string; kind: string; source: string; text: TextFilter; minPages: string; since: string; until: string; draft: "" | "yes" | "no"; sort: LibrarySort; order: "" | "asc" | "desc";
}

export const NO_QUERY: LibraryQuery = { q: "", kind: "", source: "", text: "", minPages: "", since: "", until: "", draft: "", sort: "modified", order: "" };

export const SORT_WORDS: Record<LibrarySort, string> = { modified: "Date changed", name: "Name", kind: "Kind", pages: "Pages", size: "Size" };

export function libraryFiles(q: LibraryQuery, page = "", size = 50): Promise<LibraryAnswer> {
  const body: Record<string, unknown> = { size, sort: q.sort };
  if (q.q.trim()) body.q = q.q.trim();
  if (q.kind) body.kind = q.kind;
  if (q.source) body.source = q.source;
  if (q.text) body.text = q.text;
  if (q.minPages.trim()) body.minPages = q.minPages.trim();
  if (q.since) body.since = q.since;
  if (q.until) body.until = q.until;
  if (q.draft) body.draft = q.draft;
  if (q.order) body.order = q.order;
  if (page) body.page = page;
  return postJson<LibraryAnswer>("/api/write/library/files", body);
}

/** A kind in words: "bank_statement" is "bank statement"; a file the library has not classified is "unclassified". */
export function kindWord(kind: string): string { return !kind || kind === "(none)" ? "unclassified" : kind.replace(/_/g, " "); }

/** Where the library says a file came from, in words (the server sends the same word with each file). */
export function sourceWord(source: string): string {
  return ({ payhoa: "PayHOA", drive: "Drive", gmail: "Gmail", ingest: "Taken in by hand" } as Record<string, string>)[source] ?? (source || "unknown");
}

/** How many parts of the query narrow the list (for "3 filters on"). */
export function filtersOn(q: LibraryQuery): number {
  return [q.q.trim(), q.kind, q.source, q.text, q.minPages.trim(), q.since, q.until, q.draft].filter(Boolean).length;
}
