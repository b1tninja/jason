import { conflictOf, isOffline, type ActBody, type AnyAnswer, type Conflict, type SplitBackend } from "./splitApi";
import { documentNumbers, segmentsOf, sameStarts, startsOf, unionStarts, type Seg, type SessionView, type Suggestion } from "./splitModel";

/** The draft in the browser (docs/pdf-splitter.md, section 2, "Undo, redo, and autosave"). A person's change shows at once on a local copy of the
 * starts, and is sent to the server one act at a time in order, each carrying the version it started from. The server's answer replaces the
 * copy it was made from; a refusal puts the page back the way the server has it and says why in the server's words; a draft that moved on
 * (409) holds the queue and shows both copies. Nothing per page lives here as state: the snapshot is one object that changes once per act. */

export type SaveState = "saved" | "saving" | "error" | "offline" | "conflict";

export interface Snapshot {
  session: SessionView | null;
  starts: ReadonlyMap<number, number>;
  segs: Seg[];
  docNo: Uint16Array;
  sugByPage: ReadonlyMap<number, Suggestion>;
  version: number;
  save: SaveState;
  savedAt: string;
  message: string;
  conflict: Conflict | null;
  busy: boolean;
  pending: number;
  readOnly: boolean;
  restorable: number;
}

interface Op { body: ActBody; apply?: (s: Map<number, number>) => Map<number, number> }

const UNSAVED = "jason-split-unsaved-";

export class SplitStore {
  private listeners = new Set<() => void>();
  private snap: Snapshot;
  private server: ReadonlyMap<number, number> = new Map([[1, 0]]);
  private ops: Op[] = [];
  private sending = false;
  private stored: Map<number, number> | null = null;
  private pages = 0;
  private id: string;

  constructor(private backend: SplitBackend, id: string, public by = "") {
    this.id = id;
    this.snap = {
      session: null, starts: this.server, segs: [], docNo: new Uint16Array(1), sugByPage: new Map(), version: 0, save: "saved", savedAt: "", message: "",
      conflict: null, busy: false, pending: 0, readOnly: false, restorable: 0,
    };
  }

  subscribe = (fn: () => void): (() => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  getSnapshot = (): Snapshot => this.snap;

  private emit(patch: Partial<Snapshot> = {}): void {
    const session = patch.session !== undefined ? patch.session : this.snap.session;
    const starts = this.derive();
    const same = sameStarts(starts, this.snap.starts);
    const sug = new Map<number, Suggestion>();
    for (const s of session?.suggestions ?? []) if (s.state === "open") sug.set(s.page, s);
    const pages = session?.source.pages ?? this.pages;
    this.pages = pages;
    const next: Snapshot = {
      ...this.snap, ...patch, session, starts: same ? this.snap.starts : starts,
      segs: same && this.snap.segs.length && pages === this.snap.docNo.length - 1 ? this.snap.segs : segmentsOf(starts, pages),
      docNo: same && pages === this.snap.docNo.length - 1 ? this.snap.docNo : documentNumbers(starts, pages),
      sugByPage: sug, pending: this.ops.length, busy: this.ops.some((o) => !o.apply),
      readOnly: !!session && session.status !== "draft",
    };
    this.snap = next;
    for (const l of this.listeners) l();
  }

  private derive(): Map<number, number> {
    let s = new Map(this.server);
    for (const op of this.ops) if (op.apply) s = op.apply(s);
    s.set(1, 0);
    return s;
  }

  // ---- loading

  async load(): Promise<void> {
    const a = await this.backend.session(this.id);
    this.take(a);
    try {
      const raw = sessionStorage.getItem(UNSAVED + this.id);
      if (raw) {
        const saved = JSON.parse(raw) as { version: number; starts: [number, number][] };
        const m = new Map<number, number>(saved.starts);
        if (saved.version === a.version && !sameStarts(m, this.server)) { this.stored = m; this.emit({ restorable: m.size }); }
      }
    } catch { /* storage blocked */ }
  }

  private take(a: SessionView): void {
    this.server = startsOf(a.boundaries);
    this.emit({ session: a, version: a.version });
  }

  /** Read the draft again (after a decline, or when a person asks). Queued changes are kept on top. */
  async reload(): Promise<void> {
    this.take(await this.backend.session(this.id));
  }

  // ---- changes

  private push(op: Op, message = ""): void {
    if (this.snap.readOnly) { this.emit({ message: `This split is ${this.snap.session?.status}; only a draft can be changed.` }); return; }
    this.ops.push(op);
    this.emit(message ? { message } : {});
    void this.run();
  }

  has(page: number): boolean { return this.snap.starts.has(page); }

  toggle(page: number): void {
    if (page === 1) { this.emit({ message: "The first page always starts a segment." }); return; }
    if (this.has(page)) this.unmark([page]); else this.mark([page]);
  }

  mark(pages: number[], level = 0): void {
    const list = pages.filter((p) => p > 1);
    if (!list.length) return;
    this.push({ body: { act: "mark", pages: list, level }, apply: (s) => { for (const p of list) s.set(p, level); return s; } },
      list.length === 1 ? `Page ${list[0]} now starts a segment.` : `${list.length} pages now start a segment.`);
  }

  unmark(pages: number[]): void {
    const list = pages.filter((p) => p > 1 && this.has(p));
    if (!list.length) return;
    this.push({ body: { act: "unmark", pages: list }, apply: (s) => { for (const p of list) s.delete(p); return s; } },
      list.length === 1 ? `Page ${list[0]} no longer starts a segment.` : `${list.length} starts removed.`);
  }

  move(from: number, to: number): void {
    if (from === to || from === 1 || to === 1 || !this.has(from)) return;
    if (this.has(to)) { this.emit({ message: `Page ${to} already starts a segment.` }); return; }
    this.push({ body: { act: "move", from, to }, apply: (s) => { const l = s.get(from) ?? 0; s.delete(from); s.set(to, l); return s; } }, `The start moved from page ${from} to page ${to}.`);
  }

  setLevel(page: number, level: number): void {
    if (page === 1 || !this.has(page)) return;
    this.push({ body: { act: "level", page, level }, apply: (s) => { s.set(page, level); return s; } },
      level > 0 ? `Page ${page} now starts a nested segment.` : `Page ${page} now starts a top-level segment.`);
  }

  clear(): void {
    this.push({ body: { act: "clear" }, apply: (s) => new Map([[1, 0]]) }, "Your starts were cleared.");
  }

  range(first: number, last: number, every: number): void {
    this.push({ body: { act: "range", first, last, every }, apply: (s) => { for (let p = first; p <= last; p += every) if (p !== 1 && !s.has(p)) s.set(p, 0); return s; } });
  }

  label(page: number, field: string, value: string): void { this.push({ body: { act: "label", page, field, value } }); }
  /** Resolves when every queued change has been answered (or the queue is held by a conflict or a lost connection). */
  async idle(): Promise<void> {
    while ((this.ops.length || this.sending) && this.snap.save !== "conflict" && this.snap.save !== "offline") await new Promise((r) => setTimeout(r, 15));
  }
  undo(): void { this.push({ body: { act: "undo" } }, "Undone."); }
  redo(): void { this.push({ body: { act: "redo" } }, "Redone."); }
  accept(ids: string[]): void {
    const found = (this.snap.session?.suggestions ?? []).filter((s) => ids.includes(s.id));
    this.push({ body: { act: "accept", id: ids.join(",") }, apply: (s) => { for (const g of found) s.set(g.page, g.level); return s; } },
      ids.length === 1 ? "Suggestion accepted." : `${ids.length} suggestions accepted.`);
  }
  acceptBand(which: "high" | "medium"): void {
    const min = which === "medium" ? 0.6 : 0.85;
    const found = (this.snap.session?.suggestions ?? []).filter((s) => s.state === "open" && s.confidence >= min && s.reader !== "model");
    this.push({ body: { act: "accept", id: which === "medium" ? "medium" : "all" }, apply: (s) => { for (const g of found) s.set(g.page, g.level); return s; } },
      `${found.length} suggestions accepted.`);
  }
  reject(ids: string[]): void { this.push({ body: { act: "reject", id: ids.join(",") } }, "Suggestion rejected."); }
  suggest(): void { this.push({ body: { act: "suggest" } }, "Looking for starts again."); }
  /** Replace the whole set of starts (restoring unsaved marks, or a conflict's merge). */
  setAll(starts: ReadonlyMap<number, number>): void {
    const rows = [...starts.entries()].sort((a, b) => a[0] - b[0]);
    this.push({ body: { act: "boundaries", boundaries: rows }, apply: () => new Map(starts) });
  }

  // ---- sending

  private async run(): Promise<void> {
    if (this.sending || this.snap.save === "conflict" || this.snap.save === "offline") return;
    this.sending = true;
    this.emit({ save: "saving" });
    try {
      while (this.ops.length) {
        const op = this.ops[0];
        const body: ActBody = { ...op.body, version: this.snap.version, by: this.by || undefined };
        if (op.body.act === "suggest") delete body.version;
        let r: AnyAnswer;
        try {
          r = await this.backend.act(this.id, body);
        } catch (e) {
          const c = conflictOf(e);
          if (c) { this.emit({ save: "conflict", conflict: c, message: c.message }); this.persist(); return; }
          if (isOffline(e)) { this.emit({ save: "offline", message: "You are offline. Your marks are kept on this device and will be saved when you are back." }); this.persist(); return; }
          const status = (e as { status?: number }).status ?? 0;
          if (status >= 500) { this.emit({ save: "error", message: (e as Error).message }); this.persist(); return; }      // held: retry sends it again
          this.ops.shift();                                  // a refusal (4xx): the page goes back the way the server has it, in its words
          this.emit({ message: (e as Error).message });
          if (!this.ops.length) await this.resync();
          continue;
        }
        this.ops.shift();
        if (r.session) { this.server = startsOf(r.session.boundaries); this.emit({ session: r.session, version: r.session.version }); }
        else if (r.version !== undefined) this.emit({ version: r.version });
        if (r.act === "decline") await this.reload();
        if (r.act === "undo" && r.undone === false) this.emit({ message: "There is nothing to undo." });
        if (r.act === "redo" && r.redone === false) this.emit({ message: "There is nothing to redo." });
      }
      this.emit({ save: "saved", savedAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
      try { sessionStorage.removeItem(UNSAVED + this.id); } catch { /* storage blocked */ }
    } finally {
      this.sending = false;
    }
  }

  private async resync(): Promise<void> {
    try { this.take(await this.backend.session(this.id)); } catch { /* the next act tries again */ }
  }

  private persist(): void {
    try { sessionStorage.setItem(UNSAVED + this.id, JSON.stringify({ version: this.snap.version, starts: [...this.derive()] })); } catch { /* storage blocked */ }
  }

  /** Try the held changes again (after "Not saved", or when the browser says it is back online). */
  retry(): void {
    this.emit({ save: "saved" });
    void this.run();
  }

  restore(): void {
    if (!this.stored) return;
    const m = this.stored;
    this.stored = null;
    this.emit({ restorable: 0 });
    this.setAll(m);
  }

  // ---- a conflict

  keepTheirs(): void {
    const c = this.snap.conflict;
    if (!c) return;
    this.ops = [];
    this.server = startsOf(c.current.boundaries);
    this.emit({ session: c.current, version: c.current.version, conflict: null, save: "saved", message: "Kept the other copy." });
  }

  keepMine(merge = false): void {
    const c = this.snap.conflict;
    if (!c) return;
    const mine = this.derive();
    const theirs = startsOf(c.current.boundaries);
    const chosen = merge ? unionStarts(mine, theirs) : mine;
    this.ops = [];
    this.server = theirs;
    this.emit({ session: c.current, version: c.current.version, conflict: null, save: "saved" });
    this.setAll(chosen);
  }
}
