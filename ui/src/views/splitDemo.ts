import type { ActBody, AnyAnswer, ListAnswer, OpenAnswer, SplitBackend } from "./splitApi";
import { segmentsOf, startsOf, type PageFact, type Review, type ReviewPart, type SessionAnswer, type SessionView, type Size, type Start, type Suggestion } from "./splitModel";

/** The demo draft: a made-up 120-page scan of "Example Village HOA" papers, answered from memory so a person can try the splitter's
 * interactions with no server (`#/setup/split/demo`). Every name, title, and number here is invented. The acts follow the server's
 * (`jason.community.split_session`): same words, same refusals, same undo and version rules. A reload starts the demo over. */

export const DEMO_DOCS: { title: string; pages: number; kind?: "blank" | "scan" | "map" | "numbered" | "letter" }[] = [
  { title: "Welcome letter", pages: 1, kind: "letter" },
  { title: "Board meeting agenda", pages: 2, kind: "letter" },
  { title: "Meeting minutes", pages: 5, kind: "numbered" },
  { title: "", pages: 1, kind: "blank" },
  { title: "Annual budget", pages: 8, kind: "numbered" },
  { title: "Notice of assessment", pages: 1, kind: "letter" },
  { title: "Site map", pages: 1, kind: "map" },
  { title: "Reserve study", pages: 24, kind: "numbered" },
  { title: "", pages: 1, kind: "blank" },
  { title: "Certificate of insurance", pages: 3, kind: "scan" },
  { title: "Landscape contract", pages: 12, kind: "numbered" },
  { title: "", pages: 1, kind: "blank" },
  { title: "Spring newsletter", pages: 4, kind: "letter" },
  { title: "Courtesy reminder", pages: 1, kind: "letter" },
  { title: "Pool rules", pages: 2, kind: "letter" },
  { title: "Parking policy", pages: 3, kind: "numbered" },
  { title: "", pages: 1, kind: "blank" },
  { title: "Vendor invoice", pages: 2, kind: "scan" },
  { title: "Insurance renewal", pages: 6, kind: "numbered" },
  { title: "Rule change notice", pages: 2, kind: "letter" },
  { title: "Annual meeting packet", pages: 39, kind: "numbered" },
];

function hash(n: number): number {
  let x = (n * 2654435761) >>> 0;
  x ^= x >>> 13; x = Math.imul(x, 1274126177) >>> 0; x ^= x >>> 16;
  return x >>> 0;
}

function lqipOf(n: number, blank: boolean, first: boolean, marked: boolean): string {
  let out = "";
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
    let v = blank ? 0xfa : 0xf2;
    if (!blank) {
      if (first && y >= 1 && y <= 2 && x >= 2 && x <= 13) v = 0x6a;
      else if (y >= 4 && y <= 13 && y % 2 === 0 && x >= 2 && x <= 12 + (hash(n * 31 + y) % 3)) v = 0xa4;
      if (marked && y >= 9 && y <= 12 && x >= 9 && x <= 13) v = 0x30;
    }
    out += v.toString(16).padStart(2, "0");
  }
  return out;
}

/** The demo's per-page facts. `pages` extends the list by repeating the sample documents, so a test can ask for 3,000. */
export function demoFacts(pages = 120): PageFact[] {
  const facts: PageFact[] = [];
  let n = 0;
  for (let i = 0; n < pages; i++) {
    const doc = DEMO_DOCS[i % DEMO_DOCS.length];
    for (let k = 1; k <= doc.pages && n < pages; k++) {
      n += 1;
      const blank = doc.kind === "blank";
      const scan = doc.kind === "scan";
      const landscape = doc.kind === "map";
      const marked = doc.kind === "letter" && doc.title === "Notice of assessment";
      facts.push({
        n, width: landscape ? 792 : 612, height: landscape ? 612 : 792, rotation: 0,
        blank: blank ? "blank" : marked ? "marked" : "content", has_text: !blank && !scan, words: blank ? 0 : scan ? 0 : 180 + (hash(n) % 200),
        dpi: scan ? 200 : 300, colour: scan ? "grey" : "bilevel", header: blank ? "" : k > 1 || doc.kind === "numbered" ? "Example Village HOA" : "",
        footer: doc.kind === "numbered" ? `Page ${k} of ${doc.pages}` : "", label: doc.kind === "numbered" ? [k, doc.pages] : null,
        title: k === 1 && !blank ? doc.title : "", date: k === 1 && !blank ? "2099-0" + (1 + (i % 9)) + "-" + String(1 + (hash(i) % 27)).padStart(2, "0") : "",
        lqip: lqipOf(n, blank, k === 1, marked),
      });
    }
  }
  return facts;
}

const svgCache = new Map<string, string>();

/** A made-up page as an SVG data URL: letterhead on a first page, grey lines for text, a footer with its number, a big page number. */
export function demoPicture(f: PageFact, size: Size): string {
  const key = `${f.n}:${size}`;
  const hit = svgCache.get(key);
  if (hit) return hit;
  const w = f.width, h = f.height;
  const lines: string[] = [];
  if (f.blank !== "blank") {
    if (f.title) lines.push(`<rect x="48" y="40" width="${w - 96}" height="34" fill="#cfd6e2"/><text x="58" y="64" font-family="sans-serif" font-size="20" fill="#26324a">Example Village HOA</text>`,
      `<text x="48" y="118" font-family="serif" font-size="26" font-weight="bold" fill="#1a2028">${f.title.replace(/&/g, "&amp;")}</text>`);
    else if (f.header) lines.push(`<text x="48" y="48" font-family="sans-serif" font-size="12" fill="#6b7686">${f.header}</text>`);
    const rows = size === "large" ? 30 : size === "small" ? 22 : 14;
    for (let r = 0; r < rows; r++) {
      const y = 150 + r * ((h - 260) / rows);
      const len = (w - 110) * (0.55 + (hash(f.n * 17 + r) % 45) / 100);
      lines.push(`<rect x="52" y="${y.toFixed(0)}" width="${len.toFixed(0)}" height="${size === "tiny" ? 7 : 5}" fill="${f.has_text ? "#8a93a3" : "#a9afba"}"/>`);
    }
    if (f.blank === "marked") lines.push(`<rect x="${w - 190}" y="${h - 250}" width="120" height="90" fill="none" stroke="#8a1c1c" stroke-width="5"/>`);
    if (f.footer) lines.push(`<text x="${w / 2 - 36}" y="${h - 36}" font-family="sans-serif" font-size="13" fill="#6b7686">${f.footer}</text>`);
  } else lines.push(`<text x="${w / 2 - 30}" y="${h / 2}" font-family="sans-serif" font-size="14" fill="#c8ccd4">(blank)</text>`);
  lines.push(`<text x="${w - 150}" y="${h - 60}" font-family="sans-serif" font-size="${size === "tiny" ? 120 : 90}" font-weight="bold" fill="#2457c5" fill-opacity=".16">${f.n}</text>`);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${size === "tiny" ? 96 : size === "small" ? 200 : 800}"><rect width="${w}" height="${h}" fill="#fff"/>${lines.join("")}<rect x=".5" y=".5" width="${w - 1}" height="${h - 1}" fill="none" stroke="#c3cad4"/></svg>`;
  const url = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  if (svgCache.size > 600) svgCache.clear();
  svgCache.set(key, url);
  return url;
}

const confidenceOf = (score: number) => 1 / (1 + Math.exp(-3 * (score - 0.6)));
const bandOf = (c: number) => (c >= 0.85 ? "High" : c >= 0.6 ? "Medium" : "Low");

/** The demo's rule pass: the same kinds of signals as the server's (a numbering restart, a blank page before, a change of size), each with its words. */
export function demoSuggestions(facts: PageFact[]): Suggestion[] {
  const out: Suggestion[] = [];
  for (let p = 2; p < facts.length + 1; p++) {
    const f = facts[p - 1], prev = facts[p - 2];
    if (f.blank === "blank") continue;
    const signals: { signal: string; weight: number; said: string }[] = [];
    if (f.label && f.label[0] === 1) signals.push({ signal: "page-one", weight: 1.5, said: `Page numbering restarts at 1 of ${f.label[1]}` });
    if (prev.blank === "blank") signals.push({ signal: "blank-before", weight: 0.9, said: "The page before is blank" });
    if (f.title && !signals.some((s) => s.signal === "page-one")) signals.push({ signal: "title-block", weight: 0.45, said: "The page opens with a title and a letterhead" });
    if (f.width !== prev.width) signals.push({ signal: "size-change", weight: 0.9, said: "The page is a different size from the page before" });
    if (f.dpi !== prev.dpi) signals.push({ signal: "dpi-change", weight: 0.35, said: "The scan resolution changes here" });
    const score = signals.reduce((s, x) => s + x.weight, 0);
    if (score < 0.55) continue;
    const c = confidenceOf(score);
    const top = [...signals].sort((a, b) => b.weight - a.weight).slice(0, 3);
    out.push({ id: `g${p}`, page: p, level: 0, confidence: Math.round(c * 1000) / 1000, band: bandOf(c), tier: "suggested", signals: signals.map((s) => ({ ...s })),
      why: `Page ${p}. ${top.map((s) => s.said).join(". ")}.`, reader: "rules", state: "open" });
  }
  return out;
}

interface Snap { b: Start[]; l: Record<string, Record<string, string>>; s: Record<string, string> }
const stamp = () => new Date().toISOString();

export class DemoBackend implements SplitBackend {
  readonly demo = true;
  private facts: PageFact[];
  private boundaries: Start[];
  private labels: Record<string, Record<string, string>> = {};
  private suggestions: Suggestion[];
  private undo: Snap[] = [];
  private redo: Snap[] = [];
  private version = 1;
  private status = "draft";
  private updated = stamp();
  private applied: Record<string, unknown> = {};
  readonly id = "demo";

  constructor(private opts: { pages?: number; latency?: number } = {}) {
    this.facts = demoFacts(opts.pages ?? 120);
    this.suggestions = demoSuggestions(this.facts);
    this.boundaries = [{ page: 1, level: 0, source: "person" }];
  }

  get pages(): number { return this.facts.length; }
  thumbUrl(_id: string, page: number, size: Size): string { return demoPicture(this.facts[page - 1], size); }
  private wait(): Promise<void> { return this.opts.latency ? new Promise((r) => setTimeout(r, this.opts.latency)) : Promise.resolve(); }

  async list(): Promise<ListAnswer> {
    await this.wait();
    return { sessions: [this.listed()], limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 }, caveats: [] };
  }
  private listed() {
    const v = this.view();
    return { id: this.id, status: this.status, pages: this.pages, segments: v.counts.segments, suggestionsOpen: v.counts.suggestionsOpen, updated: this.updated, by: "Demo", confidential: false, kind: "demo", label: `${this.pages} made-up pages` };
  }

  view(): SessionView {
    const starts = startsOf(this.boundaries);
    const segs = segmentsOf(starts, this.pages);
    const open = this.suggestions.filter((s) => s.state === "open").length;
    const top = segs.filter((s) => s.level === 0).length;
    return {
      id: this.id, status: this.status, version: this.version, created: this.updated, updated: this.updated, by: "Demo",
      source: { sha256: "demo", size: this.pages * 41000, pages: this.pages, kind: "demo", ref: "", confidential: false },
      counts: { pages: this.pages, segments: top, nested: segs.length - top, boundaries: segs.length, suggestionsOpen: open, undo: this.undo.length, redo: this.redo.length },
      boundaries: [...this.boundaries].sort((a, b) => a.page - b.page),
      segments: segs.map((s) => ({ key: s.key, path: s.key, start: s.start, end: s.end, pages: s.end - s.start + 1, level: s.level, parent: "", source: s.start === 1 ? "first" : "person", labels: { ...(this.labels[String(s.start)] ?? {}) } })),
      suggestions: this.suggestions.map((s) => ({ ...s })), confirmed: {}, applied: this.applied, suggestedAt: this.updated,
      notes: ["This is a demo: made-up pages, kept in this tab only. Nothing is sent anywhere."],
    };
  }

  async session(_id: string, q: { facts?: [number, number]; review?: boolean } = {}): Promise<SessionAnswer> {
    await this.wait();
    const out: SessionAnswer = { ...this.view(), renderer: "demo", sizes: ["tiny", "small", "large"], confidential: false, limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 }, caveats: ["A suggestion is jason's guess, with its reasons; it is not a boundary until a person accepts it."] };
    if (q.facts) out.facts = this.facts.slice(Math.max(0, q.facts[0] - 1), q.facts[1]);
    if (q.review) out.review = this.review([], []);
    return out;
  }

  async open(): Promise<OpenAnswer> { await this.wait(); return { ok: true, resumed: true, session: this.view() }; }

  private snap(): Snap {
    return { b: this.boundaries.map((b) => ({ ...b })), l: JSON.parse(JSON.stringify(this.labels)), s: Object.fromEntries(this.suggestions.map((s) => [s.id, s.state])) };
  }
  private restore(s: Snap) {
    this.boundaries = s.b.map((b) => ({ ...b }));
    this.labels = JSON.parse(JSON.stringify(s.l));
    for (const g of this.suggestions) if (g.id in s.s) g.state = s.s[g.id];
  }
  private check(p: number) {
    if (!Number.isInteger(p) || p < 1 || p > this.pages) throw new Error(`page ${p} is not in a file of ${this.pages} pages`);
    return p;
  }
  private change(go: () => void): boolean {
    if (this.status !== "draft") throw new Error(`this split is ${this.status}; only a draft can be changed`);
    const before = this.snap();
    go();
    const byPage = new Map(this.boundaries.map((b) => [b.page, b]));
    this.boundaries = [...byPage.values()].filter((b) => b.page >= 1 && b.page <= this.pages);
    if (!this.boundaries.some((b) => b.page === 1)) this.boundaries.push({ page: 1, level: 0, source: "person" });
    let prev = 0;
    this.boundaries = this.boundaries.sort((a, b) => a.page - b.page).map((b, i) => { const level = i === 0 ? 0 : Math.min(b.level, prev + 1); prev = level; return level === b.level ? b : { ...b, level }; });
    const keep = new Set(this.boundaries.map((b) => String(b.page)));
    this.labels = Object.fromEntries(Object.entries(this.labels).filter(([k]) => keep.has(k)));
    if (JSON.stringify(this.snap()) === JSON.stringify(before)) return false;
    this.undo.push(before);
    this.undo.splice(0, Math.max(0, this.undo.length - 200));
    this.redo = [];
    this.version += 1;
    this.updated = stamp();
    return true;
  }

  private pagesOf(v: unknown): number[] {
    if (v === undefined || v === null || v === "") return [];
    if (typeof v === "number") return [v];
    if (typeof v === "string") return v.split(",").flatMap((part) => { const [a, b] = part.trim().split("-"); return Array.from({ length: Number(b ?? a) - Number(a) + 1 }, (_, i) => Number(a) + i); });
    return (v as unknown[]).map(Number);
  }

  async act(_id: string, body: ActBody): Promise<AnyAnswer> {
    await this.wait();
    const act = body.act;
    if (body.version !== undefined && Number(body.version) !== this.version && !["review", "apply", "suggest"].includes(act)) {
      const err = Object.assign(new Error("The draft changed since you opened it (another tab or person). Nothing was saved; compare and choose."), { status: 409, body: { conflict: true, current: this.view() } });
      throw err;
    }
    const out: AnyAnswer = { act, ok: true };
    const by = "Demo";
    const mark = (p: number, level = 0) => {
      this.check(p);
      if (p === 1 && level !== 0) throw new Error("The first page always starts a document, at level 0");
      this.boundaries = this.boundaries.filter((b) => b.page !== p);
      this.boundaries.push({ page: p, level, by, at: stamp(), source: "person" });
    };
    let changed = false;
    switch (act) {
      case "review": return { act, ok: true, review: this.review(body.parts as unknown[] ?? [], this.pagesOf(body.drop)) };
      case "apply": return this.apply(body);
      case "decline": this.status = "declined"; this.version += 1; return { act, ok: true, version: this.version, session: this.view() };
      case "suggest": this.suggestions = demoSuggestions(this.facts).map((s) => {
        const old = this.suggestions.find((o) => o.page === s.page);
        return old && (old.state === "rejected" || old.state === "edited") ? { ...s, state: old.state } : this.boundaries.some((b) => b.page === s.page) ? { ...s, state: "accepted" } : s;
      }); out.count = this.suggestions.length; break;
      case "mark": changed = this.change(() => this.pagesOf(body.pages ?? body.page).forEach((p) => mark(p, Number(body.level ?? 0)))); break;
      case "unmark": changed = this.change(() => this.pagesOf(body.pages ?? body.page).forEach((p) => { if (this.check(p) === 1) throw new Error("The first page always starts a segment"); this.boundaries = this.boundaries.filter((b) => b.page !== p); })); break;
      case "move": {
        const from = this.check(Number(body.from)), to = this.check(Number(body.to));
        if (from === 1) throw new Error("The first page always starts a segment and cannot be moved");
        const held = this.boundaries.find((b) => b.page === from);
        if (!held) throw new Error(`page ${from} does not start a segment`);
        if (from !== to && this.boundaries.some((b) => b.page === to)) throw new Error(`page ${to} already starts a segment`);
        if (to === 1) throw new Error("Page 1 already starts the first segment");
        changed = this.change(() => { this.boundaries = this.boundaries.filter((b) => b.page !== from); this.boundaries.push({ ...held, page: to, by, at: stamp(), source: "person" }); if (this.labels[String(from)]) { this.labels[String(to)] = this.labels[String(from)]; delete this.labels[String(from)]; } });
        break;
      }
      case "level": {
        const p = this.check(Number(body.page));
        if (!this.boundaries.some((b) => b.page === p)) throw new Error(`page ${p} does not start a segment`);
        changed = this.change(() => mark(p, Number(body.level ?? 0)));
        break;
      }
      case "clear": { const pages = this.pagesOf(body.pages); const t = new Set(pages.length ? pages : this.boundaries.map((b) => b.page)); t.delete(1); out.cleared = this.boundaries.filter((b) => t.has(b.page)).length; changed = this.change(() => { this.boundaries = this.boundaries.filter((b) => !t.has(b.page)); }); break; }
      case "range": {
        const first = this.check(Number(body.first)), last = this.check(Number(body.last)), every = Number(body.every ?? 1);
        if (every < 1 || first > last) throw new Error("a range runs from a first page to a later one, marking every 1st page or more");
        const add: number[] = []; for (let p = first; p <= last; p += every) if (p !== 1 && !this.boundaries.some((b) => b.page === p)) add.push(p);
        out.added = add.length; changed = this.change(() => add.forEach((p) => mark(p, Number(body.level ?? 0)))); break;
      }
      case "boundaries": {
        const rows = (body.boundaries as [number, number][] | undefined) ?? this.pagesOf(body.pages).map((p) => [p, 0] as [number, number]);
        const held = new Map(this.boundaries.map((b) => [b.page, b]));
        changed = this.change(() => { const want = new Map<number, number>(rows.map(([p, l]) => [this.check(p), l ?? 0])); want.set(1, 0); this.boundaries = [...want].map(([p, l]) => { const o = held.get(p); return o && o.level === l ? o : { page: p, level: l, by, at: stamp(), source: "person" }; }); });
        break;
      }
      case "label": {
        const p = this.check(Number(body.page));
        if (!this.boundaries.some((b) => b.page === p)) throw new Error(`page ${p} does not start a segment`);
        const text = String(body.value ?? "").split(/\s+/).filter(Boolean).join(" ").slice(0, 200);
        if (body.field === "nested" && text && !["inside", "file"].includes(text)) throw new Error("a nested segment stays inside its parent or is also made a file (inside | file); taking it out comes later");
        changed = this.change(() => { const row = { ...(this.labels[String(p)] ?? {}) }; if (text) row[String(body.field)] = text; else delete row[String(body.field)]; if (Object.keys(row).length) this.labels[String(p)] = row; else delete this.labels[String(p)]; });
        break;
      }
      case "undo": if (this.undo.length) { this.redo.push(this.snap()); this.restore(this.undo.pop()!); this.version += 1; out.undone = true; changed = true; } else out.undone = false; break;
      case "redo": if (this.redo.length) { this.undo.push(this.snap()); this.restore(this.redo.pop()!); this.version += 1; out.redone = true; changed = true; } else out.redone = false; break;
      case "accept": {
        const which = String(body.id ?? "").trim().toLowerCase();
        const ids = which === "all" || which === "high" || which === "medium"
          ? this.suggestions.filter((s) => s.state === "open" && s.confidence >= (which === "medium" ? 0.6 : 0.85) && s.reader !== "model").map((s) => s.id)
          : which.split(/[,\s]+/).filter(Boolean);
        if (!ids.length && !["all", "high", "medium"].includes(which)) throw new Error("accept names a suggestion (g12), a list, or all (High and better)");
        changed = this.change(() => ids.forEach((id) => {
          const s = this.suggestions.find((x) => x.id === id);
          if (!s) throw new Error(id);
          this.boundaries = this.boundaries.filter((b) => b.page !== s.page);
          this.boundaries.push({ page: s.page, level: s.level, by, at: stamp(), source: "accepted", suggestion: s.id });
          s.state = "accepted";
        }));
        out.accepted = ids.length; break;
      }
      case "reject": {
        const ids = String(body.id ?? "").split(/[,\s]+/).filter(Boolean);
        if (!ids.length) throw new Error("reject names a suggestion (g12) or a list");
        changed = this.change(() => ids.forEach((id) => { const s = this.suggestions.find((x) => x.id === id); if (!s) throw new Error(id); s.state = "rejected"; }));
        out.rejected = ids.length; break;
      }
      default: throw new Error(`act is one of mark, unmark, move, level, clear, range, label, undo, redo, accept, reject, suggest, review, apply, decline`);
    }
    return { ...out, version: this.version, changed, session: this.view() };
  }

  private review(_parts: unknown[], dropped: number[]): Review {
    const segs = segmentsOf(startsOf(this.boundaries), this.pages);
    const drop = [...new Set(dropped)].sort((a, b) => a - b);
    const parts: ReviewPart[] = [];
    let ordinal = 0, inFiles = 0;
    for (const s of segs) {
      const lab = this.labels[String(s.start)] ?? {};
      if (s.level > 0 && lab.nested !== "file") continue;
      ordinal += 1;
      const pages: number[] = [];
      for (let p = s.start; p <= s.end; p++) if (!drop.includes(p)) pages.push(p);
      if (!pages.length) throw new Error(`segment ${s.key} would be empty after the pages left out; merge it or keep its pages`);
      const runs: [number, number][] = [];
      for (const p of pages) { const last = runs[runs.length - 1]; if (last && p === last[1] + 1) last[1] = p; else runs.push([p, p]); }
      if (s.level === 0) inFiles += pages.length;
      parts.push({ segment: s.key, level: s.level, start: s.start, end: s.end, ordinal, slot: "", title: lab.title ?? "", kind: lab.kind ?? null, pages: runs, count: pages.length, name: "", action: "held" });
    }
    parts.forEach((p) => { p.name = `Part ${p.ordinal} of ${parts.length} (pages ${p.start}-${p.end})`; });
    const totalsOk = inFiles + drop.length === this.pages;
    return { id: this.id, status: this.status, version: this.version, sourcePages: this.pages, files: parts.length, parts, dropped: drop, pagesInFiles: inFiles, totalsOk, problems: totalsOk ? [] : [`the pages do not add up: ${inFiles} in files + ${drop.length} left out is not ${this.pages}`], collisions: [], duplicates: [], held: parts.map((p) => p.segment), result: `${parts.length} new files; the original is kept untouched`, caveats: [] };
  }

  private apply(body: ActBody): AnyAnswer {
    const review = this.review([], this.pagesOf(body.drop));
    if (!(body.confirm === true && body.dryRun === false)) {
      return { act: "apply", ok: true, dryRun: true, would: { act: "apply", id: this.id, by: "Demo", files: review.files }, review, note: "A dry run: nothing was written. Confirm as a person (--yes) to write the files." };
    }
    if (!review.totalsOk) throw new Error(review.problems.join("; "));
    if (this.status === "applied") throw new Error("this split was applied already; nothing was written again");
    this.status = "applied";
    this.version += 1;
    this.applied = { partial: false, by: "Demo", parts: review.parts.map((p) => ({ segment: p.segment, action: "held" })) };
    return { act: "apply", ok: true, dryRun: false, filled: [], held: review.parts.map((p) => ({ segment: p.segment, ordinal: p.ordinal })), skipped: [], failed: [], dropped: review.dropped, autoRead: false };
  }
}
