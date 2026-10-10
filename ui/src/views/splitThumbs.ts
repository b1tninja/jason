import { priorityOf, budgetFor, type Budget } from "./splitWindow";
import { type Size } from "./splitModel";

/** The page-picture loader (docs/pdf-splitter.md, section 3.4). A cell hands it an `<img>`, a page, and the sizes it wants (tiny first, then
 * small); the loader sets `img.src` itself, so a picture arriving costs no React render. It
 * - asks nearest the middle of the view first, and ahead of the way the person is scrolling before behind;
 * - holds a few requests at once and aborts the ones whose cell has left the window;
 * - in a fast scroll asks for nothing but tiny pictures, drops the rest, and asks again when the scroll settles;
 * - keeps at most a budget of decoded pictures per size (the ones on screen are never evicted). */

export class LoadError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export type Fetcher = (url: string, signal: AbortSignal) => Promise<string>;

/** A picture as an object URL; a `data:` address is its own picture. A refusal keeps the server's words. */
export const fetchPicture: Fetcher = async (url, signal) => {
  if (url.startsWith("data:")) return url;
  const res = await fetch(url, { signal });
  if (!res.ok) {
    let words = "";
    try { words = ((await res.json()) as { error?: string }).error ?? ""; } catch { /* not JSON */ }
    throw new LoadError(res.status, words || `${res.status} ${res.statusText}`);
  }
  return URL.createObjectURL(await res.blob());
};

const ORDER: Size[] = ["tiny", "small", "large"];
const rank = (s: Size) => ORDER.indexOf(s);

export interface AttachOpts { onState?: (state: "ready" | "failed", words?: string) => void }
interface Entry { el: HTMLImageElement; page: number; sizes: Size[]; shown: number; opts: AttachOpts }
interface Job { key: string; page: number; size: Size }

export interface LoaderOpts {
  urlOf: (page: number, size: Size) => string;
  fetcher?: Fetcher;
  budget?: Budget;
  concurrency?: number;
}

export interface LoaderStats { inflight: number; queued: number; attached: number; cached: Record<Size, number>; requested: number; aborted: number }

export class ThumbLoader {
  private urlOf: LoaderOpts["urlOf"];
  private fetcher: Fetcher;
  private budget: Budget;
  private concurrency: number;
  private entries = new Map<HTMLImageElement, Entry>();
  private byPage = new Map<number, Set<Entry>>();
  private cache = new Map<string, string>();
  private queue: Job[] = [];
  private inflight = new Map<string, AbortController>();
  private failed = new Map<string, string>();
  private center = 1;
  private dir: -1 | 0 | 1 = 0;
  private fast = false;
  private counts = { requested: 0, aborted: 0 };

  constructor(o: LoaderOpts) {
    this.urlOf = o.urlOf;
    this.fetcher = o.fetcher ?? fetchPicture;
    this.budget = o.budget ?? budgetFor();
    this.concurrency = o.concurrency ?? 6;
  }

  /** Register a picture element. Returns the function that detaches it (its requests are aborted when nothing else wants them). */
  attach(el: HTMLImageElement, page: number, sizes: Size[], opts: AttachOpts = {}): () => void {
    const entry: Entry = { el, page, sizes: [...sizes].sort((a, b) => rank(a) - rank(b)), shown: -1, opts };
    this.entries.set(el, entry);
    let set = this.byPage.get(page);
    if (!set) this.byPage.set(page, (set = new Set()));
    set.add(entry);
    this.want(entry);
    this.pump();
    return () => this.detach(el);
  }

  private detach(el: HTMLImageElement): void {
    const entry = this.entries.get(el);
    if (!entry) return;
    this.entries.delete(el);
    const set = this.byPage.get(entry.page);
    set?.delete(entry);
    if (set && set.size === 0) this.byPage.delete(entry.page);
    for (const size of entry.sizes) {
      const key = `${size}:${entry.page}`;
      if (this.wanted(entry.page, size)) continue;
      this.queue = this.queue.filter((j) => j.key !== key);
      const ctl = this.inflight.get(key);
      if (ctl) { ctl.abort(); this.inflight.delete(key); this.counts.aborted += 1; }
    }
    this.pump();
  }

  /** Where the person is looking, and which way the scroll is going: the order requests are taken in. */
  setView(center: number, dir: -1 | 0 | 1): void {
    this.center = center;
    if (dir !== 0) this.dir = dir;
  }

  /** In a fast scroll only tiny pictures are asked for: the rest of the queue is dropped and the larger requests in flight are aborted. */
  setFast(fast: boolean): void {
    if (fast === this.fast) return;
    this.fast = fast;
    if (fast) {
      this.queue = this.queue.filter((j) => j.size === "tiny");
      for (const [key, ctl] of this.inflight) {
        if (!key.startsWith("tiny:")) { ctl.abort(); this.inflight.delete(key); this.counts.aborted += 1; }
      }
    } else {
      for (const entry of this.entries.values()) this.want(entry);
    }
    this.pump();
  }

  get isFast(): boolean { return this.fast; }

  /** Try a failed picture again (the page menu's "Retry the picture"). */
  retry(page: number): void {
    for (const size of ORDER) this.failed.delete(`${size}:${page}`);
    for (const entry of this.byPage.get(page) ?? []) { entry.el.dataset.state = "loading"; this.want(entry); }
    this.pump();
  }

  /** Forget every held picture (a new file, or the person purged the cache). */
  clear(): void {
    for (const ctl of this.inflight.values()) ctl.abort();
    this.inflight.clear();
    this.queue = [];
    for (const url of this.cache.values()) this.release(url);
    this.cache.clear();
    this.failed.clear();
  }

  stats(): LoaderStats {
    const cached: Record<Size, number> = { tiny: 0, small: 0, large: 0 };
    for (const key of this.cache.keys()) cached[key.split(":")[0] as Size] += 1;
    return { inflight: this.inflight.size, queued: this.queue.length, attached: this.entries.size, cached, ...this.counts };
  }

  // ---- inside

  private wanted(page: number, size: Size): boolean {
    for (const e of this.byPage.get(page) ?? []) if (e.sizes.includes(size)) return true;
    return false;
  }

  private want(entry: Entry): void {
    this.show(entry);
    for (const size of entry.sizes) {
      const key = `${size}:${entry.page}`;
      if (this.cache.has(key) || this.failed.has(key) || this.inflight.has(key) || this.queue.some((j) => j.key === key)) continue;
      if (this.fast && size !== "tiny") continue;
      this.queue.push({ key, page: entry.page, size });
    }
  }

  private show(entry: Entry): void {
    let best = -1;
    for (const size of entry.sizes) if (this.cache.has(`${size}:${entry.page}`)) best = Math.max(best, rank(size));
    if (best > entry.shown) {
      const key = `${ORDER[best]}:${entry.page}`;
      const url = this.cache.get(key)!;
      entry.shown = best;
      entry.el.src = url;
      entry.el.dataset.size = ORDER[best];
      entry.el.dataset.state = "ready";
      this.touch(key, url);
      entry.opts.onState?.("ready");
    } else if (best < 0) {
      const err = entry.sizes.map((s) => this.failed.get(`${s}:${entry.page}`)).find((m) => m !== undefined);
      if (err !== undefined && entry.shown < 0) {
        entry.el.dataset.state = "failed";
        entry.opts.onState?.("failed", err);
      } else if (entry.shown < 0 && !entry.el.dataset.state) entry.el.dataset.state = "loading";
    }
  }

  private touch(key: string, url: string): void {
    this.cache.delete(key);
    this.cache.set(key, url);
  }

  private pump(): void {
    while (this.inflight.size < this.concurrency && this.queue.length) {
      let best = 0, bestP = Infinity;
      for (let i = 0; i < this.queue.length; i++) {
        const j = this.queue[i];
        const p = priorityOf(j.page, this.center, this.dir, j.size);
        if (p < bestP) { bestP = p; best = i; }
      }
      const job = this.queue.splice(best, 1)[0];
      this.start(job);
    }
  }

  private start(job: Job): void {
    const ctl = new AbortController();
    this.inflight.set(job.key, ctl);
    this.counts.requested += 1;
    this.fetcher(this.urlOf(job.page, job.size), ctl.signal).then(
      (url) => {
        if (this.inflight.get(job.key) !== ctl) { this.release(url); return; }     // aborted meanwhile
        this.inflight.delete(job.key);
        this.cache.set(job.key, url);
        for (const entry of this.byPage.get(job.page) ?? []) this.show(entry);
        this.evict(job.size);
        this.pump();
      },
      (e: unknown) => {
        if (this.inflight.get(job.key) !== ctl) return;
        this.inflight.delete(job.key);
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          this.failed.set(job.key, e instanceof Error ? e.message : "This page could not be drawn");
          for (const entry of this.byPage.get(job.page) ?? []) this.show(entry);
        }
        this.pump();
      },
    );
  }

  private evict(size: Size): void {
    const limit = this.budget[size];
    let over = [...this.cache.keys()].filter((k) => k.startsWith(`${size}:`)).length - limit;
    if (over <= 0) return;
    for (const key of [...this.cache.keys()]) {
      if (over <= 0) break;
      if (!key.startsWith(`${size}:`)) continue;
      const page = Number(key.slice(key.indexOf(":") + 1));
      if (this.wanted(page, size)) continue;                     // on screen: never
      this.release(this.cache.get(key)!);
      this.cache.delete(key);
      over -= 1;
    }
  }

  private release(url: string): void {
    if (url.startsWith("blob:") && typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url);
  }
}
