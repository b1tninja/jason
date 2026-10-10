import type { SplitBackend } from "./splitApi";
import type { PageFact } from "./splitModel";

/** The per-page facts, loaded in chunks as the window reaches them (docs/pdf-splitter.md, section 3.5). A cell asks `get(n)`; a page
 * measured later arrives with the next read of its chunk, so a pending chunk is asked again every few seconds while a person is looking.
 * One version number changes when anything arrives, so the grid re-renders its few live cells and not a cell at a time. */
export class FactsCache {
  private rows: (PageFact | undefined)[] = [];
  private loaded = new Set<number>();
  private loading = new Set<number>();
  private timers = new Map<number, ReturnType<typeof setTimeout>>();
  private listeners = new Set<() => void>();
  version = 0;
  failed = "";

  constructor(private backend: SplitBackend, private id: string, readonly pages: number, readonly chunk = 300, private again = 4000) {}

  subscribe = (fn: () => void): (() => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  getVersion = (): number => this.version;
  get(n: number): PageFact | undefined { return this.rows[n]; }
  all(): (PageFact | undefined)[] { return this.rows; }

  /** How many pages have been read, and how many of those are still being measured. */
  progress(): { known: number; pending: number } {
    let known = 0, pending = 0;
    for (let n = 1; n <= this.pages; n++) { const f = this.rows[n]; if (f) { known += 1; if (f.pending) pending += 1; } }
    return { known, pending };
  }

  ensure(first: number, last: number): void {
    if (last < first) return;
    for (let c = Math.floor((Math.max(1, first) - 1) / this.chunk); c <= Math.floor((Math.min(this.pages, last) - 1) / this.chunk); c++) {
      if (!this.loaded.has(c) && !this.loading.has(c)) void this.read(c);
    }
  }

  /** Every chunk, for a bulk act that needs the whole file's facts. */
  async loadAll(): Promise<void> {
    const n = Math.ceil(this.pages / this.chunk);
    for (let c = 0; c < n; c++) if (!this.loaded.has(c)) await this.read(c);
  }

  dispose(): void {
    for (const t of this.timers.values()) clearTimeout(t);
    this.timers.clear();
    this.listeners.clear();
  }

  private async read(c: number): Promise<void> {
    this.loading.add(c);
    const first = c * this.chunk + 1, last = Math.min(this.pages, first + this.chunk - 1);
    try {
      const a = await this.backend.session(this.id, { facts: [first, last] });
      let pending = false;
      for (const f of a.facts ?? []) { this.rows[f.n] = f; if (f.pending) pending = true; }
      this.loaded.add(c);
      this.failed = "";
      if (pending) this.timers.set(c, setTimeout(() => { this.timers.delete(c); this.loaded.delete(c); this.loading.delete(c); void this.read(c); }, this.again));
      this.version += 1;
      for (const l of this.listeners) l();
    } catch (e) {
      this.failed = (e as Error).message;
      this.version += 1;
      for (const l of this.listeners) l();
    } finally {
      if (!this.timers.has(c)) this.loading.delete(c);
    }
  }
}
