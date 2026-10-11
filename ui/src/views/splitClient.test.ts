import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CLIENT_CONCURRENCY, ClientPictures, LOW_MEMORY_BYTES, type DrawnPage, type PdfEngine, type PdfLib, type PicturesOpts, type Reloadable } from "./splitClient";
import { LoadError, ThumbLoader } from "./splitThumbs";
import type { PageFact, Size } from "./splitModel";

/** The browser's picture source with a fake pdf.js: what it draws, when it falls back to the server, and what it says. */

let urls = 0;
beforeEach(() => {
  urls = 0;
  (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = () => `blob:fake-${++urls}`;
  (URL as unknown as { revokeObjectURL: (u: string) => void }).revokeObjectURL = () => undefined;
});
afterEach(() => vi.restoreAllMocks());

const fact = (n: number, blank: string, pending = false): PageFact => ({ n, width: 612, height: 792, rotation: 0, blank, has_text: false, words: 0, label: null, pending });
const tick = () => new Promise((r) => setTimeout(r, 0));

class FakeEngine implements PdfEngine {
  drawn: { page: number; px: number }[] = [];
  inflight = 0;
  peak = 0;
  gates: (() => void)[] = [];
  hold = false;
  ink: (page: number) => number = () => 1000;
  fail: (page: number) => boolean = () => false;
  destroyed = false;
  constructor(readonly pages: number) {}
  async draw(page: number, px: number, signal: AbortSignal): Promise<DrawnPage> {
    this.inflight += 1; this.peak = Math.max(this.peak, this.inflight);
    try {
      if (this.hold) await new Promise<void>((res, rej) => { this.gates.push(res); signal.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")), { once: true }); });
      if (this.fail(page)) throw new Error("this page cannot be drawn");
      this.drawn.push({ page, px });
      return { blob: new Blob(["x"]), inkPixels: this.ink(page) };
    } finally { this.inflight -= 1; }
  }
  destroy(): void { this.destroyed = true; }
  release(): void { const g = this.gates.splice(0); g.forEach((f) => f()); }
}

function lib(engine: FakeEngine | Error, test: { ok: boolean; failed: string[] } = { ok: true, failed: [] }): PdfLib {
  return {
    open: async () => { if (engine instanceof Error) throw engine; return engine; },
    selfTest: async () => test,
  };
}

function make(engine: FakeEngine | Error, over: Partial<PicturesOpts> = {}, test?: { ok: boolean; failed: string[] }) {
  const server = vi.fn(async (url: string) => `server:${url}`);
  const bytes = vi.fn(async () => new ArrayBuffer(8));
  const p = new ClientPictures({
    enabled: true, maxPages: 3000, pages: 0, origin: "computer", bytes, loadLib: async () => lib(engine, test),
    serverUrl: (page: number, size: Size) => `/thumb/${size}/${page}`, serverFetch: server, ...over,
  });
  return { p, server, bytes };
}

const ctl = () => new AbortController().signal;

describe("drawing in the browser", () => {
  it("draws from the engine at the size's pixels and asks the server for nothing", async () => {
    const e = new FakeEngine(13);
    const { p, server } = make(e);
    p.start();
    await p.ready;
    expect(p.pages).toBe(13);
    expect(await p.fetcher("tiny:2", ctl())).toMatch(/^blob:/);
    await p.fetcher("small:3", ctl());
    await p.fetcher("large:4", ctl());
    expect(e.drawn).toEqual([{ page: 2, px: 96 }, { page: 3, px: 200 }, { page: 4, px: 800 }]);
    expect(server).not.toHaveBeenCalled();
    expect(p.getStatus()).toMatchObject({ why: "ok", client: true });
    expect(p.getStatus().words).toContain("Preview from this computer");
  });

  it("says where a fetched copy was drawn from", async () => {
    const { p } = make(new FakeEngine(3), { origin: "copy" });
    p.start(); await p.ready;
    expect(p.getStatus().words).toBe("The pictures are drawn in this browser from a copy fetched once.");
  });

  it("starts once and reads the file once", async () => {
    const { p, bytes } = make(new FakeEngine(3));
    p.start(); p.start(); p.start();
    await p.ready;
    expect(bytes).toHaveBeenCalledTimes(1);
  });

  it("is held to the render pool: no more than four pictures at once, however many cells ask", async () => {
    const e = new FakeEngine(40);
    e.hold = true;
    const { p } = make(e);
    const loader = new ThumbLoader({ urlOf: (page, size) => `${size}:${page}`, fetcher: p.fetcher, concurrency: 6 });
    p.attach(loader);
    p.start();
    await p.ready;
    const imgs = Array.from({ length: 30 }, (_, i) => { const el = document.createElement("img"); loader.attach(el, i + 1, ["tiny"]); return el; });
    await tick(); await tick();
    expect(e.inflight).toBe(CLIENT_CONCURRENCY);
    for (let i = 0; i < 40 && e.drawn.length < 30; i++) { e.release(); await tick(); }
    expect(e.peak).toBe(CLIENT_CONCURRENCY);
    expect(e.drawn.length).toBe(30);
    expect(imgs.every((el) => el.dataset.state === "ready" && el.src.startsWith("blob:"))).toBe(true);
    loader.clear();
  });

  it("stops drawing a page whose cell left the window", async () => {
    const e = new FakeEngine(10);
    e.hold = true;
    const { p } = make(e);
    p.start(); await p.ready;
    const ctrl = new AbortController();
    const asked = p.fetcher("small:5", ctrl.signal);
    await tick();
    ctrl.abort();
    await expect(asked).rejects.toMatchObject({ name: "AbortError" });
    expect(e.drawn).toEqual([]);
  });
});

describe("falling back to the server, in words", () => {
  it("browser drawing off: the server's picture, and the words say so", async () => {
    const e = new FakeEngine(5);
    const { p, server, bytes } = make(e, { enabled: false });
    p.start(); await p.ready;
    expect(await p.fetcher("tiny:1", ctl())).toBe("server:/thumb/tiny/1");
    expect(server).toHaveBeenCalledTimes(1);
    expect(bytes).not.toHaveBeenCalled();
    expect(p.getStatus()).toMatchObject({ why: "off", client: false });
    expect(p.getStatus().words).toContain("browser drawing is off");
  });

  it("a file past the page limit is never opened", async () => {
    const { p, bytes } = make(new FakeEngine(5), { pages: 4000, maxPages: 3000 });
    p.start(); await p.ready;
    expect(bytes).not.toHaveBeenCalled();
    expect(p.getStatus().why).toBe("limit");
    expect(p.getStatus().words).toContain("3000 pages");
  });

  it("counts the pages itself when the server has not, and refuses a file past the limit then", async () => {
    const e = new FakeEngine(50);
    const { p } = make(e, { maxPages: 40 });
    p.start(); await p.ready;
    expect(e.destroyed).toBe(true);
    expect(p.getStatus().why).toBe("limit");
  });

  it("a large file on a small device is the server's", async () => {
    const { p, bytes } = make(new FakeEngine(5), { memoryGB: 2, fileBytes: LOW_MEMORY_BYTES + 1 });
    p.start(); await p.ready;
    expect(bytes).not.toHaveBeenCalled();
    expect(p.getStatus().why).toBe("memory");
    const big = make(new FakeEngine(5), { memoryGB: 8, fileBytes: LOW_MEMORY_BYTES + 1 });
    big.p.start(); await big.p.ready;
    expect(big.p.getStatus().why).toBe("ok");
  });

  it("a failed self-test turns browser drawing off for the visit and names the codec", async () => {
    const e = new FakeEngine(5);
    const { p, bytes } = make(e, {}, { ok: false, failed: ["JPEG 2000"] });
    p.start(); await p.ready;
    expect(bytes).not.toHaveBeenCalled();
    expect(await p.fetcher("small:2", ctl())).toBe("server:/thumb/small/2");
    expect(p.getStatus()).toMatchObject({ why: "selftest", client: false });
    expect(p.getStatus().words).toBe("The pictures are drawn by the server for this visit: this browser did not draw the JPEG 2000 test page correctly, so browser drawing was turned off.");
  });

  it("a library that cannot load, a file that cannot be read, and a file the engine cannot open each say why", async () => {
    const broken = new ClientPictures({ enabled: true, maxPages: 10, pages: 0, origin: "copy", bytes: async () => new ArrayBuffer(1), loadLib: async () => { throw new Error("the script did not load"); }, serverUrl: () => "" });
    broken.start(); await broken.ready;
    expect(broken.getStatus().words).toContain("the script did not load");
    const unread = make(new FakeEngine(3), { bytes: async () => { throw new Error("Browser drawing is off for this community."); } });
    unread.p.start(); await unread.p.ready;
    expect(unread.p.getStatus()).toMatchObject({ why: "failed", detail: "Browser drawing is off for this community." });
    const unopened = make(new Error("Invalid PDF structure"));
    unopened.p.start(); await unopened.p.ready;
    expect(unopened.p.getStatus().words).toBe("The pictures are drawn by the server: this browser could not open the file (Invalid PDF structure).");
  });

  it("a page count that is not the server's is not trusted", async () => {
    const e = new FakeEngine(7);
    const { p } = make(e, { pages: 13 });
    p.start(); await p.ready;
    expect(p.getStatus().why).toBe("failed");
    expect(e.destroyed).toBe(true);
  });

  it("a page the engine cannot draw comes from the server, and is counted", async () => {
    const e = new FakeEngine(5);
    e.fail = (page) => page === 3;
    const { p, server } = make(e);
    p.start(); await p.ready;
    expect(await p.fetcher("tiny:2", ctl())).toMatch(/^blob:/);
    expect(await p.fetcher("tiny:3", ctl())).toBe("server:/thumb/tiny/3");
    expect(server).toHaveBeenCalledTimes(1);
    expect(p.getStatus().serverPages).toBe(1);
    expect(p.getStatus().words).toContain("1 page is drawn by the server instead");
  });

  it("before the draft exists there is nothing to fall back to: the picture fails in words, and loads when the draft arrives", async () => {
    let id = "";
    const { p } = make(new FakeEngine(3), { enabled: false, serverUrl: (page, size) => (id ? `/thumb/${size}/${page}` : "") });
    p.start(); await p.ready;
    await expect(p.fetcher("tiny:1", ctl())).rejects.toBeInstanceOf(LoadError);
    const loader: Reloadable = { reload: vi.fn(), retryFailed: vi.fn(), setConcurrency: vi.fn() };
    p.attach(loader);
    id = "abcd1234";
    p.serverReady();
    expect(loader.retryFailed).toHaveBeenCalled();
    expect(await p.fetcher("tiny:1", ctl())).toBe("server:/thumb/tiny/1");
  });
});

describe("a page drawn entirely white", () => {
  it("is replaced by the server's picture when the server says the page has ink", async () => {
    const e = new FakeEngine(5);
    e.ink = (page) => (page === 2 ? 0 : 900);
    const facts = new Map<number, PageFact>([[2, fact(2, "content")], [4, fact(4, "content")]]);
    const { p, server } = make(e, { factOf: (n) => facts.get(n) });
    p.start(); await p.ready;
    expect(await p.fetcher("small:2", ctl())).toBe("server:/thumb/small/2");
    expect(await p.fetcher("small:4", ctl())).toMatch(/^blob:/);
    expect(server).toHaveBeenCalledTimes(1);
    expect(p.getStatus().serverPages).toBe(1);
    await p.fetcher("tiny:2", ctl());                              // later sizes of the page do not try the browser again
    expect(e.drawn.filter((d) => d.page === 2)).toEqual([{ page: 2, px: 200 }]);
  });

  it("is kept when the server says the page is blank", async () => {
    const e = new FakeEngine(5);
    e.ink = () => 0;
    const { p, server } = make(e, { factOf: (n) => fact(n, "blank") });
    p.start(); await p.ready;
    expect(await p.fetcher("small:2", ctl())).toMatch(/^blob:/);
    expect(server).not.toHaveBeenCalled();
    expect(p.getStatus().serverPages).toBe(0);
  });

  it("is shown at first when the server has not measured it, and looked at again when the measure arrives", async () => {
    const e = new FakeEngine(5);
    e.ink = () => 0;
    const facts = new Map<number, PageFact>([[2, fact(2, "content", true)], [3, fact(3, "content", true)]]);
    const { p, server } = make(e, { factOf: (n) => facts.get(n) });
    const loader: Reloadable = { reload: vi.fn(), retryFailed: vi.fn(), setConcurrency: vi.fn() };
    p.attach(loader);
    p.start(); await p.ready;
    expect(await p.fetcher("small:2", ctl())).toMatch(/^blob:/);     // no flicker: the white picture stays until there is a reason
    expect(await p.fetcher("small:3", ctl())).toMatch(/^blob:/);
    p.reconcile();
    expect(loader.reload).not.toHaveBeenCalled();                   // still pending
    facts.set(2, fact(2, "content"));                                // page 2 has ink: its white picture was wrong
    facts.set(3, fact(3, "blank"));                                  // page 3 is blank: its white picture was right
    p.reconcile();
    expect(loader.reload).toHaveBeenCalledTimes(1);
    expect(loader.reload).toHaveBeenCalledWith(2);
    expect(await p.fetcher("small:2", ctl())).toBe("server:/thumb/small/2");
    expect(server).toHaveBeenCalledTimes(1);
    p.reconcile();
    expect(loader.reload).toHaveBeenCalledTimes(1);                  // each page is settled once
  });
});

describe("the loader's side of a replaced picture", () => {
  it("keeps the picture on screen until its replacement arrives", async () => {
    let n = 0;
    const fetcher = vi.fn(async () => `blob:p-${++n}`);
    const loader = new ThumbLoader({ urlOf: (page, size) => `${size}:${page}`, fetcher });
    const el = document.createElement("img");
    loader.attach(el, 7, ["tiny"]);
    await tick(); await tick();
    expect(el.src).toBe("blob:p-1");
    loader.reload(7);
    expect(el.src).toBe("blob:p-1");                                 // not cleared
    expect(el.dataset.state).toBe("ready");
    await tick(); await tick();
    expect(el.src).toBe("blob:p-2");
    expect(fetcher).toHaveBeenCalledTimes(2);
    loader.clear();
  });

  it("retries failed pictures when asked", async () => {
    let ok = false;
    const fetcher = vi.fn(async () => { if (!ok) throw new LoadError(0, "later"); return "blob:ok"; });
    const loader = new ThumbLoader({ urlOf: (page, size) => `${size}:${page}`, fetcher });
    const el = document.createElement("img");
    loader.attach(el, 1, ["tiny"]);
    await tick(); await tick();
    expect(el.dataset.state).toBe("failed");
    ok = true;
    loader.retryFailed();
    await tick(); await tick();
    expect(el.dataset.state).toBe("ready");
    loader.clear();
  });
});
