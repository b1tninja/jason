import { SIZE_PX, type PageFact, type Size } from "./splitModel";
import { LoadError, fetchPicture, type Fetcher } from "./splitThumbs";

/** Page pictures drawn in the browser (docs/pdf-splitter-client-side.md; docs/pdf-splitter.md, section 3.7). `ClientPictures` is the picture
 * source the splitter's `ThumbLoader` asks, one `size:page` key at a time. It draws from a PDF engine (pdf.js, loaded only when the splitter
 * is opened: `splitPdfjs.ts`) and falls back to the server's pictures
 * - for the whole session, when browser drawing is off, the file is over the limit, the browser fails the start-up self-test (a JPEG 2000
 *   and a CCITT test page), or the file cannot be opened here;
 * - for one page, when the browser drew it and it came out entirely white although the server's measure says the page has ink, or when the
 *   engine could not draw it.
 * Whatever it does is said in words (`status`), and a drawn picture is a display only: no value read here is ever sent as a fact. */

/** One drawn page: the picture and how many of its sampled pixels were not white. */
export interface DrawnPage { blob: Blob; inkPixels: number }
export interface PdfEngine {
  readonly pages: number;
  /** Draw page `page` so its longest side is `px` pixels. Rejects with an AbortError when `signal` aborts. */
  draw(page: number, px: number, signal: AbortSignal): Promise<DrawnPage>;
  destroy(): void;
}
export interface SelfTestResult { ok: boolean; failed: string[] }
export interface PdfLib { open(bytes: ArrayBuffer): Promise<PdfEngine>; selfTest(): Promise<SelfTestResult> }

export type PictureWhy = "waiting" | "ok" | "off" | "limit" | "selftest" | "failed" | "memory";
export interface PictureStatus {
  why: PictureWhy;
  /** whether pictures are being drawn in this browser now */
  client: boolean;
  /** where the file came from: "computer" is a file chosen here and not yet (or never) read back from the server */
  origin: "computer" | "copy";
  /** pages the server is drawing although the browser is the source (a page the browser drew blank, or could not draw) */
  serverPages: number;
  detail: string;
  words: string;
}

/** A file this big on a device with this little memory is drawn by the server: the browser holds the whole file while it draws. */
export const LOW_MEMORY_GB = 2;
export const LOW_MEMORY_BYTES = 80 * 1024 * 1024;
export const CLIENT_CONCURRENCY = 4;

export interface PicturesOpts {
  /** `split.client_render` */
  enabled: boolean;
  /** `split.client_render_max_pages` */
  maxPages: number;
  /** the pages the server says the file has, or 0 until known (the engine then counts) */
  pages: number;
  origin: "computer" | "copy";
  /** the file's bytes (a chosen file, or the stored copy fetched once) */
  bytes: () => Promise<ArrayBuffer>;
  loadLib: () => Promise<PdfLib>;
  /** the server's address for a picture, or "" while the draft does not exist yet */
  serverUrl: (page: number, size: Size) => string;
  /** the server's measure of a page, when it has arrived (never sent anywhere; read to catch a blank drawing) */
  factOf?: (page: number) => PageFact | undefined;
  memoryGB?: number;
  fileBytes?: number;
  serverFetch?: Fetcher;
}

/** What a picture loader needs of the source: it can drop one page's pictures and draw them again, and try the failed ones again. */
export interface Reloadable { reload(page: number): void; retryFailed(): void; setConcurrency(n: number): void }

const abortError = () => new DOMException("aborted", "AbortError");
const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

export function statusWords(why: PictureWhy, origin: "computer" | "copy", serverPages: number, detail: string, maxPages: number): string {
  switch (why) {
    case "waiting": return "Getting ready to draw the pages in this browser…";
    case "ok": {
      const base = origin === "computer" ? "Preview from this computer: the pictures are drawn in this browser from the file you chose." : "The pictures are drawn in this browser from a copy fetched once.";
      return serverPages > 0 ? `${base} ${serverPages} ${serverPages === 1 ? "page is" : "pages are"} drawn by the server instead, because the browser's drawing of ${serverPages === 1 ? "it was blank" : "them was blank"} or failed.` : base;
    }
    case "off": return "The pictures are drawn by the server: browser drawing is off for this community.";
    case "limit": return `The pictures are drawn by the server: this file is longer than the ${maxPages} pages the browser draws.`;
    case "memory": return "The pictures are drawn by the server: this file is large for this device's memory.";
    case "selftest": return `The pictures are drawn by the server for this visit: this browser did not draw the ${detail} test page correctly, so browser drawing was turned off.`;
    case "failed": return `The pictures are drawn by the server: this browser could not open the file${detail ? ` (${detail})` : ""}.`;
  }
}

export class ClientPictures {
  private engine: PdfEngine | null = null;
  private why: PictureWhy = "waiting";
  private detail = "";
  private serverPages = new Set<number>();
  private unverified = new Set<number>();
  private listeners = new Set<() => void>();
  private loader: Reloadable | null = null;
  private started = false;
  private status: PictureStatus;
  private done!: () => void;
  readonly ready: Promise<void> = new Promise<void>((r) => { this.done = r; });

  constructor(private o: PicturesOpts) { this.status = this.make(); }

  subscribe = (fn: () => void): (() => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  getStatus = (): PictureStatus => this.status;
  /** The pages the engine counted, once it is ready; 0 when the browser is not the source. */
  get pages(): number { return this.engine?.pages ?? 0; }
  get drawing(): boolean { return this.engine !== null; }

  /** Take the picture loader: it draws four at a time while the browser is the source. */
  attach(loader: Reloadable): void { this.loader = loader; if (this.engine) loader.setConcurrency(CLIENT_CONCURRENCY); }

  /** Where the server's measures of pages are read from (the facts cache), once the editor has one. */
  useFacts(factOf: (page: number) => PageFact | undefined): void { this.o = { ...this.o, factOf }; }

  /** Begin loading the engine. Idempotent. */
  start(): void {
    if (this.started) return;
    this.started = true;
    void this.init();
  }

  /** The draft now exists on the server: pictures that could not be had before (nothing to fall back to) are asked for again. */
  serverReady(): void { this.loader?.retryFailed(); }

  dispose(): void {
    this.engine?.destroy();
    this.engine = null;
    this.listeners.clear();
  }

  /** Called when the server's measures of pages arrive: a page the browser drew white, before the server had spoken, is checked now. */
  reconcile(): void {
    let changed = false;
    for (const page of [...this.unverified]) {
      const f = this.o.factOf?.(page);
      if (!f || f.pending) continue;
      this.unverified.delete(page);
      if (f.blank !== "blank") { this.serverPages.add(page); changed = true; this.loader?.reload(page); }
    }
    if (changed) this.change();
  }

  /** The picture loader's source. `key` is `size:page`. */
  fetcher: Fetcher = async (key, signal) => {
    const cut = key.indexOf(":");
    const size = key.slice(0, cut) as Size, page = Number(key.slice(cut + 1));
    await this.ready;
    if (signal.aborted) throw abortError();
    const engine = this.engine;
    if (engine && !this.serverPages.has(page)) {
      try {
        const drawn = await engine.draw(page, SIZE_PX[size], signal);
        if (drawn.inkPixels > 0 || !this.whiteIsWrong(page)) return URL.createObjectURL(drawn.blob);
      } catch (e) {
        if (isAbort(e)) throw e;
        this.serverPages.add(page);
        this.change();
      }
    }
    return this.fromServer(page, size, signal);
  };

  // ---- inside

  /** Whether a page drawn entirely white is wrong: yes when the server has measured the page and says it is not blank; not yet known
   * otherwise (the white picture is shown, and `reconcile` looks again when the measure arrives). */
  private whiteIsWrong(page: number): boolean {
    const f = this.o.factOf?.(page);
    if (!f || f.pending) { this.unverified.add(page); return false; }
    if (f.blank === "blank") return false;
    this.serverPages.add(page);
    this.change();
    return true;
  }

  private async fromServer(page: number, size: Size, signal: AbortSignal): Promise<string> {
    const url = this.o.serverUrl(page, size);
    if (!url) throw new LoadError(0, "This picture will load when the draft is saved on the server.");
    return (this.o.serverFetch ?? fetchPicture)(url, signal);
  }

  private async init(): Promise<void> {
    const o = this.o;
    if (!o.enabled) return this.settle("off");
    if (o.pages > o.maxPages) return this.settle("limit");
    if (o.memoryGB !== undefined && o.memoryGB <= LOW_MEMORY_GB && (o.fileBytes ?? 0) > LOW_MEMORY_BYTES) return this.settle("memory");
    let lib: PdfLib;
    try { lib = await o.loadLib(); } catch (e) { return this.settle("failed", (e as Error).message); }
    let test: SelfTestResult;
    try { test = await lib.selfTest(); } catch (e) { test = { ok: false, failed: ["the test pages"] }; }
    if (!test.ok) return this.settle("selftest", test.failed.join(" and "));
    let bytes: ArrayBuffer;
    try { bytes = await o.bytes(); } catch (e) { return this.settle("failed", (e as Error).message); }
    let engine: PdfEngine;
    try { engine = await lib.open(bytes); } catch (e) { return this.settle("failed", (e as Error).message || "its pages could not be read"); }
    if (engine.pages > o.maxPages) { engine.destroy(); return this.settle("limit"); }
    if (o.pages > 0 && engine.pages !== o.pages) { engine.destroy(); return this.settle("failed", "its page count is not the server's"); }
    this.engine = engine;
    this.loader?.setConcurrency(CLIENT_CONCURRENCY);
    this.settle("ok");
  }

  private settle(why: PictureWhy, detail = ""): void {
    this.why = why;
    this.detail = detail;
    this.change();
    this.done();
  }

  private make(): PictureStatus {
    const client = this.engine !== null;
    return { why: this.why, client, origin: this.o.origin, serverPages: this.serverPages.size, detail: this.detail,
      words: statusWords(this.why, this.o.origin, this.serverPages.size, this.detail, this.o.maxPages) };
  }

  private change(): void {
    this.status = this.make();
    for (const l of this.listeners) l();
  }
}
