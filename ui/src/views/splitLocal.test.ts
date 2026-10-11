import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ActBody, AnyAnswer, ListAnswer, OpenAnswer, OpenRef, SplitBackend } from "./splitApi";
import type { PdfLib } from "./splitClient";
import { LocalBackend } from "./splitLocal";
import { SplitStore } from "./splitStore";
import type { SessionAnswer, SessionView, Size } from "./splitModel";

/** A file chosen on this computer: answered from the browser until the server's draft exists, then handed over. */

beforeEach(() => {
  (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = () => "blob:x";
});

const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));

function view(id: string, pages: number, version = 1, starts = [1]): SessionView {
  return {
    id, status: "draft", version, created: "", updated: "", by: "A", source: { sha256: "abc", size: 10, pages, kind: "upload", ref: "", confidential: false },
    counts: { pages, segments: starts.length, nested: 0, boundaries: starts.length, suggestionsOpen: 0, undo: 0, redo: 0 },
    boundaries: starts.map((page) => ({ page, level: 0 })), segments: [], suggestions: [], confirmed: {}, applied: {}, suggestedAt: "", notes: [],
  };
}

class FakeServer implements SplitBackend {
  readonly demo = false;
  version = 1;
  starts = [1];
  opened: (() => void)[] = [];
  acts: ActBody[] = [];
  sessions: string[] = [];
  refuse = "";
  constructor(private pages: number) {}
  thumbUrl(id: string, page: number, size: Size): string { return `/thumb?id=${id}&page=${page}&size=${size}`; }
  async list(): Promise<ListAnswer> { return { sessions: [] }; }
  async session(id: string): Promise<SessionAnswer> { this.sessions.push(id); return { ...view("srv00001", this.pages, this.version, this.starts) }; }
  async open(_ref: OpenRef): Promise<OpenAnswer> {
    await new Promise<void>((r) => this.opened.push(r));
    if (this.refuse) throw Object.assign(new Error(this.refuse), { status: 400 });
    return { ok: true, session: view("srv00001", this.pages, this.version) };
  }
  async act(id: string, body: ActBody): Promise<AnyAnswer> {
    this.acts.push({ ...body, id });
    if (body.version !== this.version) throw Object.assign(new Error("moved on"), { status: 409, body: { conflict: true, current: view("srv00001", this.pages, this.version, this.starts) } });
    if (body.act === "mark") { this.starts = [...new Set([...this.starts, ...(body.pages as number[])])].sort((a, b) => a - b); this.version += 1; }
    return { act: body.act, ok: true, session: view("srv00001", this.pages, this.version, this.starts) } as AnyAnswer;
  }
  async finishOpen(): Promise<void> { while (!this.opened.length) await tick(5); this.opened.splice(0).forEach((f) => f()); }
}

const engineLib = (pages: number): PdfLib => ({
  open: async () => ({ pages, draw: async () => ({ blob: new Blob(["x"]), inkPixels: 5 }), destroy: () => undefined }),
  selfTest: async () => ({ ok: true, failed: [] }),
});

const BYTES = { bytes: async () => new ArrayBuffer(4) };
const file = () => new File([new Uint8Array([37, 80, 68, 70])], "scan.pdf", { type: "application/pdf" });

describe("a file chosen on this computer", () => {
  it("answers from the browser before the server has the draft: its pages, one start, every page still being measured", async () => {
    const server = new FakeServer(13);
    const b = new LocalBackend(file(), server, "A Manager", { enabled: true, maxPages: 3000 }, async () => engineLib(13), BYTES);
    const a = await b.session("local", { facts: [1, 4] });
    expect(a.source.pages).toBe(13);
    expect(a.boundaries).toEqual([{ page: 1, level: 0, source: "first" }]);
    expect(a.facts?.map((f) => [f.n, f.pending])).toEqual([[1, true], [2, true], [3, true], [4, true]]);
    expect(server.sessions).toEqual([]);                      // nothing asked of the server
    expect(b.thumbUrl("local", 2, "tiny")).toBe("");          // no server address yet
    expect(b.background.get().phase).toBe("uploading");
    b.pictures.dispose();
  });

  it("holds the marks and sends them, in order, from the draft's own version, once the server has it", async () => {
    const server = new FakeServer(13);
    const b = new LocalBackend(file(), server, "A Manager", { enabled: true, maxPages: 3000 }, async () => engineLib(13), BYTES);
    const heard = vi.fn();
    b.onServer(heard);
    const store = new SplitStore(b, "local", "A Manager");
    await store.load();
    store.mark([4]);
    store.mark([9]);
    expect(store.getSnapshot().starts.has(4) && store.getSnapshot().starts.has(9)).toBe(true);      // on the page numbers, at once
    await tick(20);
    expect(server.acts).toEqual([]);                                                                  // held
    await server.finishOpen();
    await store.idle();
    expect(b.background.get()).toMatchObject({ phase: "saved", id: "srv00001" });
    expect(heard).toHaveBeenCalledTimes(1);
    expect(server.acts.map((a) => [a.act, a.id, a.version])).toEqual([["mark", "srv00001", 1], ["mark", "srv00001", 2]]);
    expect([...store.getSnapshot().starts.keys()]).toEqual([1, 4, 9]);
    expect(store.getSnapshot().save).toBe("saved");
    b.pictures.dispose();
  });

  it("after the draft exists every question goes to the server's draft", async () => {
    const server = new FakeServer(13);
    const b = new LocalBackend(file(), server, "A Manager", { enabled: true, maxPages: 3000 }, async () => engineLib(13), BYTES);
    await server.finishOpen();
    await tick(10);
    const a = await b.session("local", { facts: [1, 2] });
    expect(a.id).toBe("srv00001");
    expect(server.sessions).toEqual(["srv00001"]);
    expect(b.thumbUrl("local", 2, "tiny")).toBe("/thumb?id=srv00001&page=2&size=tiny");
    b.pictures.dispose();
  });

  it("a refusal from the server is shown in its words and the held marks are not sent anywhere", async () => {
    const server = new FakeServer(13);
    server.refuse = "This file is 140 MB; the largest upload is 100 MB.";
    const b = new LocalBackend(file(), server, "A Manager", { enabled: true, maxPages: 3000 }, async () => engineLib(13), BYTES);
    const store = new SplitStore(b, "local", "A Manager");
    await store.load();
    store.mark([4]);
    await server.finishOpen();
    await store.idle();
    expect(b.background.get()).toEqual({ phase: "refused", id: "", words: "This file is 140 MB; the largest upload is 100 MB." });
    expect(server.acts).toEqual([]);
    expect(store.getSnapshot().message).toContain("140 MB");
    b.pictures.dispose();
  });

  it("without a browser engine, the page count and the draft wait for the server", async () => {
    const server = new FakeServer(13);
    const b = new LocalBackend(file(), server, "A Manager", { enabled: false, maxPages: 3000 }, async () => engineLib(13), BYTES);
    let answered = false;
    const asked = b.session("local").then((a) => { answered = true; return a; });
    await tick(20);
    expect(answered).toBe(false);
    await server.finishOpen();
    const a = await asked;
    expect(a.source.pages).toBe(13);
    b.pictures.dispose();
  });
});
