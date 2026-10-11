import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { Plugin } from "vite";

/** Self-hosts what pdf.js loads at run time (docs/pdf-splitter-client-side.md, "What did not work until configured"): the JPEG 2000 and
 * colour-management decoders (`wasm`), the character maps, the standard fonts, and the ICC profiles. They are not copied into the
 * repository: the build emits them from the pinned package under `pdfjs/`, and the dev server answers `/pdfjs/...` from it, so the
 * console never reaches a CDN. The worker script is imported by the code (`?url`) and Vite hashes it. */
export const PDFJS_FOLDERS = ["wasm", "cmaps", "standard_fonts", "iccs"] as const;

const MIME: Record<string, string> = { ".wasm": "application/wasm", ".js": "text/javascript", ".bcmap": "application/octet-stream", ".pfb": "application/octet-stream", ".ttf": "font/ttf", ".icc": "application/octet-stream" };

function walk(dir: string, rel = ""): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const path = rel ? `${rel}/${e.name}` : e.name;
    if (e.isDirectory()) out.push(...walk(join(dir, e.name), path)); else out.push(path);
  }
  return out;
}

export function pdfjsAssets(): Plugin {
  const root = resolve("node_modules", "pdfjs-dist");
  const files = (): string[] => PDFJS_FOLDERS.flatMap((f) => (existsSync(join(root, f)) ? walk(join(root, f), f) : []));
  return {
    name: "jason-pdfjs-assets",
    generateBundle() {
      for (const rel of files()) this.emitFile({ type: "asset", fileName: `pdfjs/${rel}`, source: readFileSync(join(root, rel)) });
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req as { url?: string }).url ?? "";
        const m = /^\/pdfjs\/((?:wasm|cmaps|standard_fonts|iccs)\/[A-Za-z0-9_.-]+)(?:\?.*)?$/.exec(url);
        if (!m || !existsSync(join(root, m[1]))) { next(); return; }
        const ext = m[1].slice(m[1].lastIndexOf("."));
        const r = res as unknown as { setHeader(k: string, v: string): void; end(b: Uint8Array): void };
        r.setHeader("Content-Type", MIME[ext] ?? "application/octet-stream");
        r.end(readFileSync(join(root, m[1])));
      });
    },
  };
}
