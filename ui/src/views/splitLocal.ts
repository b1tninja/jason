import { ClientPictures, type PdfLib, type PicturesOpts } from "./splitClient";
import type { ActBody, AnyAnswer, Background, ListAnswer, OpenAnswer, OpenRef, SplitBackend } from "./splitApi";
import type { PageFact, SessionAnswer, SessionView, Size } from "./splitModel";

/** A file chosen on this computer, opened at once (docs/pdf-splitter.md, section 3.7). The browser counts and draws the pages from the
 * `File` itself, so the grid and the marks are there the moment the file is chosen; the upload and the server's open run in the background.
 * Until the draft exists on the server this backend answers from the browser: a draft with page 1 as its only start and every page's facts
 * "still being measured". A mark is held in the editor's queue and is sent, in order, once the draft exists (the editor says so, in words).
 * After that every question goes to the server's draft, whose answer replaces the placeholder. A browser value is never sent as a fact. */

export interface ClientLimits { enabled: boolean; maxPages: number }
export const LOCAL_ID = "local";
const NOW = () => new Date().toISOString();

const readBase64 = (file: File): Promise<string> => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => { const url = String(reader.result ?? ""); resolve(url.slice(url.indexOf(",") + 1)); };
  reader.onerror = () => reject(new Error("The browser could not read that file."));
  reader.readAsDataURL(file);
});

const defaultLib = (): Promise<PdfLib> => import("./splitPdfjs").then((m) => m.pdfLib);

export class LocalBackend implements SplitBackend {
  readonly demo = false;
  readonly local = true;
  readonly pictures: ClientPictures;
  private bg: Background = { phase: "uploading", id: "", words: "" };
  private listeners = new Set<() => void>();
  private serverListeners = new Set<() => void>();
  private opened: Promise<SessionView>;
  private sid = "";
  private synced = false;

  constructor(readonly file: File, private real: SplitBackend, private by: string, limits: ClientLimits, lib: () => Promise<PdfLib> = defaultLib,
              extra: Partial<PicturesOpts> = {}) {
    this.pictures = new ClientPictures({
      enabled: limits.enabled, maxPages: limits.maxPages, pages: 0, origin: "computer", bytes: () => file.arrayBuffer(), loadLib: lib,
      serverUrl: (page, size) => (this.sid ? real.thumbUrl(this.sid, page, size) : ""),
      memoryGB: typeof navigator !== "undefined" ? (navigator as unknown as { deviceMemory?: number }).deviceMemory : undefined, fileBytes: file.size, ...extra,
    });
    this.pictures.start();
    this.opened = this.openOnServer();
    this.opened.catch(() => undefined);                  // a refusal is shown through `background`; the acts that wait on it see it too
  }

  // ---- the background work

  readonly background = {
    subscribe: (fn: () => void): (() => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; },
    get: (): Background => this.bg,
  };
  /** Called once when the draft exists on the server (the editor reads it again, to show its suggestions and starts). */
  onServer(fn: () => void): () => void { this.serverListeners.add(fn); return () => { this.serverListeners.delete(fn); }; }
  get serverId(): string { return this.sid; }

  private set(bg: Background): void { this.bg = bg; for (const l of this.listeners) l(); }

  private async openOnServer(): Promise<SessionView> {
    try {
      const base64 = await readBase64(this.file);
      const a = await this.real.open({ kind: "upload", name: this.file.name, base64 }, false, this.by);
      if (!a.session) throw new Error(a.note || "The server did not keep this file.");
      this.sid = a.session.id;
      this.set({ phase: "saved", id: a.session.id, words: a.resumed ? "This file was opened before; its earlier draft was resumed." : "" });
      this.pictures.serverReady();
      try { if (typeof window !== "undefined" && window.location.hash.startsWith("#/setup/split/local")) window.history.replaceState(null, "", `#/setup/split/${encodeURIComponent(this.sid)}`); } catch { /* no history */ }
      for (const l of this.serverListeners) l();
      return a.session;
    } catch (e) {
      this.set({ phase: "refused", id: "", words: (e as Error).message });
      throw e;
    }
  }

  // ---- the SplitBackend

  thumbUrl(_id: string, page: number, size: Size): string { return this.sid ? this.real.thumbUrl(this.sid, page, size) : ""; }
  list(): Promise<ListAnswer> { return this.real.list(); }
  open(ref: OpenRef, dryRun: boolean, by?: string): Promise<OpenAnswer> { return this.real.open(ref, dryRun, by); }

  async session(_id: string, q: { facts?: [number, number]; review?: boolean; flags?: boolean } = {}): Promise<SessionAnswer> {
    if (this.sid) return this.real.session(this.sid, q);
    if (q.review || q.flags) { await this.opened; return this.real.session(this.sid, q); }
    const pages = await this.pagesKnown();
    const out: SessionAnswer = {
      ...this.placeholder(pages), renderer: "browser", sizes: ["tiny", "small", "large"], confidential: false,
      limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 }, caveats: [],
    };
    if (q.facts) {
      const [a, b] = q.facts;
      out.facts = Array.from({ length: Math.max(0, Math.min(pages, b) - Math.max(1, a) + 1) }, (_, i) => waiting(Math.max(1, a) + i));
    }
    return out;
  }

  async act(_id: string, body: ActBody): Promise<AnyAnswer> {
    await this.opened;                                    // the marks wait for the draft; a refusal reaches the editor in the server's words
    const next: ActBody = { ...body };
    if (!this.synced) {                                   // the placeholder's version is not the server's: the first act starts from the draft as it is
      this.synced = true;
      next.version = (await this.real.session(this.sid)).version;
    }
    return this.real.act(this.sid, next);
  }

  // ---- inside

  /** The pages, from the browser's engine or the server's open, whichever answers first; a refusal only counts when the browser cannot draw. */
  private pagesKnown(): Promise<number> {
    return new Promise<number>((resolve, reject) => {
      let settled = false;
      const done = (n: number) => { if (!settled && n > 0) { settled = true; resolve(n); } };
      void this.pictures.ready.then(() => done(this.pictures.pages));
      this.opened.then((s) => done(s.source.pages), (e: Error) => {
        void this.pictures.ready.then(() => { if (!settled && this.pictures.pages === 0) { settled = true; reject(e); } });
      });
      void this.pictures.ready.then(() => {
        if (!settled && this.pictures.pages === 0) this.opened.then((s) => done(s.source.pages), () => undefined);
      });
    });
  }

  private placeholder(pages: number): SessionView {
    return {
      id: LOCAL_ID, status: "draft", version: 0, created: NOW(), updated: NOW(), by: this.by,
      source: { sha256: "", size: this.file.size, pages, kind: "upload", ref: "", confidential: false },
      counts: { pages, segments: 1, nested: 0, boundaries: 1, suggestionsOpen: 0, undo: 0, redo: 0 },
      boundaries: [{ page: 1, level: 0, source: "first" }],
      segments: [{ key: "1", path: "1", start: 1, end: pages, pages, level: 0, parent: "", source: "first", labels: {} }],
      suggestions: [], confirmed: {}, applied: {}, suggestedAt: "", notes: [],
    };
  }
}

/** A page the server has not measured: the editor shows it as "Measuring…". Never a browser value. */
function waiting(n: number): PageFact {
  return { n, width: 0, height: 0, rotation: 0, blank: "content", has_text: false, words: 0, label: null, pending: true };
}

// ---- the file held between the Open panel and the editor

let current: LocalBackend | null = null;

/** Start a chosen file: the browser begins to count and draw it, and the upload begins, before the screen changes. */
export function startLocal(file: File, real: SplitBackend, by: string, limits: ClientLimits): LocalBackend {
  current?.pictures.dispose();
  current = new LocalBackend(file, real, by, limits);
  return current;
}
export function currentLocal(): LocalBackend | null { return current; }
export function dropLocal(): void { current?.pictures.dispose(); current = null; }
