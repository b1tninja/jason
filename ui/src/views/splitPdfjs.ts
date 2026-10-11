/// <reference types="vite/client" />
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { DrawnPage, PdfEngine, PdfLib, SelfTestResult } from "./splitClient";
import { SELF_TEST_PAGES } from "./splitSelfTestData";

/** pdf.js for the splitter (docs/pdf-splitter-client-side.md). This module is only ever loaded by a dynamic `import()` when a splitter
 * screen opens a draft, so the console's main bundle does not carry it. Everything pdf.js loads at run time is the console's own: the
 * worker is a hashed asset, and the JPEG 2000 and colour decoders (`wasm`), character maps, standard fonts, and ICC profiles are served
 * from `pdfjs/` beside the page (`ui/pdfjs-assets.ts`); no CDN is reached. Without `wasmUrl` pdf.js draws JPEG 2000 as a white page with no
 * error, which is why `selfTest` exists. */

const base = (): string => `${(import.meta.env?.BASE_URL as string | undefined) ?? "/"}pdfjs/`;
let configured = false;

function configure(): void {
  if (configured) return;
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  configured = true;
}

function options(data: Uint8Array) {
  const root = base();
  return {
    data,
    wasmUrl: `${root}wasm/`, cMapUrl: `${root}cmaps/`, cMapPacked: true, standardFontDataUrl: `${root}standard_fonts/`, iccUrl: `${root}iccs/`,
    isEvalSupported: false, enableXfa: false, useSystemFonts: false,
  };
}

/** Pixels in `ctx`'s canvas that are not white (any of red, green, blue below 245), read every `step`th pixel along each row and column. */
export function inkPixelsIn(ctx: CanvasRenderingContext2D, w: number, h: number, step = 1, from = 0, to = w): number {
  const px = ctx.getImageData(0, 0, w, h).data;
  let n = 0;
  for (let y = 0; y < h; y += step) {
    for (let x = from; x < to; x += step) {
      const i = (y * w + x) * 4;
      if (px[i] < 245 || px[i + 1] < 245 || px[i + 2] < 245) n += 1;
    }
  }
  return n;
}

async function paint(doc: pdfjs.PDFDocumentProxy, n: number, px: number, signal?: AbortSignal): Promise<{ canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D }> {
  const page = await doc.getPage(n);
  try {
    const natural = page.getViewport({ scale: 1 });
    // No finer than the page's own detail: 300 dpi (the units of a page are 1/72 inch), however large the cell. Up to 1600 px otherwise.
    const wanted = Math.min(px, Math.ceil(Math.max(natural.width, natural.height) * 300 / 72));
    const vp = page.getViewport({ scale: wanted / Math.max(natural.width, natural.height) });
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(vp.width)); canvas.height = Math.max(1, Math.round(vp.height));
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("this browser has no canvas");
    const task = page.render({ canvas, canvasContext: ctx, viewport: vp });
    const stop = () => task.cancel();
    signal?.addEventListener("abort", stop, { once: true });
    try { await task.promise; } catch (e) {
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      throw e;
    } finally { signal?.removeEventListener("abort", stop); }
    return { canvas, ctx };
  } finally { page.cleanup(); }
}

const toBlob = (canvas: HTMLCanvasElement, quality: number): Promise<Blob> =>
  new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error("the picture could not be made"))), "image/webp", quality));

/** Give the main thread a turn between pictures, so a scroll or a key is never queued behind a run of drawings. */
const breathe = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

class Engine implements PdfEngine {
  constructor(private doc: pdfjs.PDFDocumentProxy) {}
  get pages(): number { return this.doc.numPages; }
  async draw(page: number, px: number, signal: AbortSignal): Promise<DrawnPage> {
    if (signal.aborted) throw new DOMException("aborted", "AbortError");
    await breathe();
    const { canvas, ctx } = await paint(this.doc, page, px, signal);
    const inkPixels = inkPixelsIn(ctx, canvas.width, canvas.height, px >= 800 ? 2 : 1);
    const blob = await toBlob(canvas, px >= 800 ? 0.8 : 0.7);
    canvas.width = canvas.height = 0;
    return { blob, inkPixels };
  }
  destroy(): void { void this.doc.destroy(); }
}

let selfTested: Promise<SelfTestResult> | null = null;

/** Draw each embedded test page (left half black, right half white) with the self-hosted decoders. A codec fails when its left half is not
 * dark or its right half is not light: a blank page, a flipped page, or an error. Run once per page load. */
export function selfTest(): Promise<SelfTestResult> {
  selfTested ??= (async () => {
    configure();
    const failed: string[] = [];
    for (const t of SELF_TEST_PAGES) {
      try {
        const data = Uint8Array.from(atob(t.base64), (c) => c.charCodeAt(0));
        const doc = await pdfjs.getDocument(options(data)).promise;
        try {
          const { canvas, ctx } = await paint(doc, 1, 64);
          const w = canvas.width, h = canvas.height, half = Math.floor(w / 2);
          const left = inkPixelsIn(ctx, w, h, 1, 0, half) / (h * half);
          const right = inkPixelsIn(ctx, w, h, 1, half, w) / (h * (w - half));
          if (!(left > 0.9 && right < 0.1)) failed.push(t.codec);
        } finally { void doc.destroy(); }
      } catch { failed.push(t.codec); }
    }
    return { ok: failed.length === 0, failed };
  })();
  return selfTested;
}

export const pdfLib: PdfLib = {
  async open(bytes: ArrayBuffer): Promise<PdfEngine> {
    configure();
    const doc = await pdfjs.getDocument(options(new Uint8Array(bytes))).promise;
    return new Engine(doc);
  },
  selfTest,
};

export default pdfLib;
