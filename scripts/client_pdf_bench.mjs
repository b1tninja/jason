// Drives scripts/client_pdf_bench.html in Chromium (Playwright) over the made-up PDFs from scripts/client_pdf_make.py.
// Usage (from a scratch folder that has `npm install pdfjs-dist playwright`; the repository is not touched):
//   node client_pdf_bench.mjs PDF_DIR OUT_DIR [--rss]
// Serves PDF_DIR, node_modules/pdfjs-dist and this page from one local origin with cross-origin isolation headers (so the browser can
// report memory), prints one JSON object. No network. No browser is downloaded: the Chromium already cached by Playwright is used.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(path.join(process.cwd(), "x.js"));
const { chromium } = require("playwright");
const here = path.dirname(fileURLToPath(import.meta.url));
const [pdfDir, outDir] = process.argv.slice(2);
const pdfjsDir = path.join(process.cwd(), "node_modules", "pdfjs-dist");
const types = { ".mjs": "text/javascript", ".js": "text/javascript", ".html": "text/html", ".pdf": "application/pdf", ".bin": "application/octet-stream", ".wasm": "application/wasm" };

const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split("?")[0]);
  let file;
  if (u === "/" || u === "/bench.html") file = path.join(here, "client_pdf_bench.html");
  else if (u.startsWith("/pdfjs/")) file = path.join(pdfjsDir, u.slice(7));
  else file = path.join(pdfDir, path.basename(u));
  if (!file || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
  const stat = fs.statSync(file);
  const h = { "Content-Type": types[path.extname(file)] || "application/octet-stream", "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp", "Cross-Origin-Resource-Policy": "same-origin", "Accept-Ranges": "bytes" };
  const range = req.headers.range && /bytes=(\d+)-(\d*)/.exec(req.headers.range);
  if (range) {
    const s = +range[1], e = range[2] ? +range[2] : stat.size - 1;
    res.writeHead(206, { ...h, "Content-Range": `bytes ${s}-${e}/${stat.size}`, "Content-Length": e - s + 1 });
    return fs.createReadStream(file, { start: s, end: e }).pipe(res);
  }
  res.writeHead(200, { ...h, "Content-Length": stat.size });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;

import { execFile } from "node:child_process";
// the browser's own processes (renderer, GPU, utility), found by the profile folder Playwright gives them: working sets, summed
const rss = () => new Promise((res) => execFile("powershell", ["-NoProfile", "-Command",
  "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*playwright_chromiumdev_profile*' } | Measure-Object WorkingSetSize -Sum).Sum"],
  (e, out) => res(e ? 0 : Math.round(Number(out.trim() || 0) / 1e6))));
let peak = 0, sampling = true;
(async () => { while (sampling) { peak = Math.max(peak, await rss()); } })();
const browser = await chromium.launch({ args: ["--enable-precise-memory-info", "--js-flags=--expose-gc"] });
const page = await browser.newPage();
page.on("pageerror", (e) => console.error("pageerror", String(e).slice(0, 200)));
await page.goto(`${base}/bench.html`);
await page.waitForFunction(() => window.ready === true);
if (process.argv.includes("--noassets")) await page.evaluate(() => window.setAssets(false));   // pdf.js without its wasm, cmaps, fonts
const first = (n, k) => Array.from({ length: k }, (_, i) => n + i);
const out = { env: await page.evaluate(() => window.bench.env()), version: browser.version(), runs: {} };
fs.mkdirSync(outDir, { recursive: true });

for (const name of ["ccitt100", "jpeg100", "flate100", "jpx100", "text500"]) {
  if (!fs.existsSync(path.join(pdfDir, `${name}.pdf`))) continue;
  out.runs[name] = await page.evaluate(([u, pages]) => window.bench.render(u, pages, [96, 200, 800]), [`${base}/${name}.pdf`, first(1, 30)]);
  for (const size of [200, 800]) {
    const r = await page.evaluate(([u, s]) => window.bench.pageDataUrl(u, 1, s), [`${base}/${name}.pdf`, size]);
    fs.writeFileSync(path.join(outDir, `${name}-p1-${size}.png`), Buffer.from(r.dataUrl.split(",")[1], "base64"));
    out.runs[name][`ink${size}`] = { inkShare: +r.inkShare.toFixed(4), factMs: r.tFactMs, w: r.w, h: r.h };
  }
}
if (fs.existsSync(path.join(pdfDir, "ccitt2000.pdf"))) {
  const probe = [1, 500, 1000, 1500, 2000];
  out.runs.ccitt2000 = await page.evaluate(([u, pages]) => window.bench.render(u, pages, [96, 200]), [`${base}/ccitt2000.pdf`, probe]);
  out.runs.ccitt2000_range = await page.evaluate(([u, pages]) => window.bench.render(u, pages, [96, 200], "range"), [`${base}/ccitt2000.pdf`, probe]);
}
if (fs.existsSync(path.join(pdfDir, "big.bin"))) {
  out.hash = await page.evaluate((u) => window.bench.hash(u), `${base}/big.bin`);
}
sampling = false;
out.browserWorkingSetPeakMB = peak;
console.log(JSON.stringify(out, null, 1));
await browser.close();
server.close();
