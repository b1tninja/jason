import DOMPurify from "dompurify";
import { marked } from "marked";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { fileDocRef } from "../lib/docref";
import { Doc } from "./Doc";

// DOMPurify's default drops data: and blob: sources; a clip or a preview may carry an inline image, so images keep them.
const URI = /^(?:(?:(?:f|ht)tps?|mailto|tel|blob|data:image\/[a-z+]+;|[^a-z]|[a-z+.-]+(?:[^a-z+.:-]|$)):|[^a-z]|[a-z+.-]+(?:[^a-z+.:-]|$))/i;

/** Where Mermaid is loaded from on first use: a few megabytes that belong in no bundle. Override before the first
 * diagram renders (`setMermaidUrl`) to serve it from the app's own host. */
let mermaidUrl = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
export function setMermaidUrl(url: string) {
  mermaidUrl = url;
}

/** Renders a ```mermaid fence. The library loads at render time from `mermaidUrl` and never blocks the text. */
function Mermaid({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const m = (await import(/* @vite-ignore */ mermaidUrl)).default;
        m.initialize({ startOnLoad: false, securityLevel: "strict", theme: window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "default" });
        const { svg } = await m.render(`m${Math.random().toString(36).slice(2)}`, code);
        if (live && ref.current) ref.current.innerHTML = DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true, html: true } });
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    })();
    return () => { live = false; };
  }, [code]);
  if (error) return <pre className="notice notice-error">{`diagram did not render: ${error}\n\n${code}`}</pre>;
  return <div ref={ref} className="mermaid" aria-label="diagram" />;
}

const SLOT = "data-doc-file";
const SLOT_NAME = "data-doc-name";
const IMG = /<img\b[^>]*>/gi;

function attr(tag: string, name: string): string | null {
  const m = new RegExp(`\\s${name}="([^"]*)"`, "i").exec(tag);
  return m ? m[1] : null;
}

const unescape = (s: string) => s.replace(/&quot;/g, "\"").replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** The path under data/ an image's source names through jason-web's `/api/file?path=` (relative, or on this page's own
 * origin), else null. */
export function apiFilePath(src: string): string | null {
  let rest = src;
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  if (origin && rest.startsWith(origin)) rest = rest.slice(origin.length);
  const m = /^\/api\/file\?path=([^&#]*)/.exec(rest);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1].replace(/\+/g, " "));
  } catch {
    return m[1];
  }
}

/** Sanitized HTML with each `<img>` of a file under data/ (`/api/file?path=P`) replaced by an empty placeholder that
 * names the path, so the page renders a `Doc` card in its place: a signed-out or forbidden reader sees the state's
 * words, never a broken image. Runs after DOMPurify, on its output; the placeholder carries only escaped text. */
export function slotFileImages(html: string): string {
  return html.replace(IMG, (tag) => {
    const src = attr(tag, "src");
    const path = src === null ? null : apiFilePath(unescape(src));
    if (path === null) return tag;
    const alt = unescape(attr(tag, "alt") ?? "");
    return `<span class="doc-md-slot" ${SLOT}="${escape(path)}"${alt ? ` ${SLOT_NAME}="${escape(alt)}"` : ""}></span>`;
  });
}

/** One sanitized piece of Markdown, with a `Doc` card portalled into each placeholder `slotFileImages` left. */
function Html({ html }: { html: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [slots, setSlots] = useState<{ el: Element; path: string; name: string }[]>([]);
  useLayoutEffect(() => {
    const found = ref.current ? Array.from(ref.current.querySelectorAll(`[${SLOT}]`)) : [];
    setSlots(found.map((el) => {
      const path = el.getAttribute(SLOT) ?? "";
      return { el, path, name: el.getAttribute(SLOT_NAME) || path.split("/").pop() || path };
    }));
  }, [html]);
  return (
    <>
      <div key={html} ref={ref} dangerouslySetInnerHTML={{ __html: html }} />
      {slots.map((s, i) => createPortal(<Doc doc={fileDocRef(s.path, s.name)} variant="card" />, s.el, `${i}:${s.path}`))}
    </>
  );
}

/** Markdown with ```mermaid fences rendered as diagrams, HTML sanitized, links opening in a new tab. An image of a file
 * under data/ (`/api/file?path=...`, the way older notes embed one) renders as a `Doc` card of that file
 * (docs/console/doc-component.md), never a raw image; any other image renders as given. */
export function Markdown({ text }: { text: string }) {
  const parts = useMemo(() => {
    const out: { kind: "md" | "mermaid"; body: string }[] = [];
    const re = /```mermaid\s*\n([\s\S]*?)```/g;
    let last = 0;
    for (const m of text.matchAll(re)) {
      if (m.index! > last) out.push({ kind: "md", body: text.slice(last, m.index) });
      out.push({ kind: "mermaid", body: m[1] });
      last = m.index! + m[0].length;
    }
    if (last < text.length) out.push({ kind: "md", body: text.slice(last) });
    return out.map((p) => p.kind === "mermaid" ? p : {
      kind: p.kind,
      body: slotFileImages(DOMPurify.sanitize(marked.parse(p.body, { async: false }) as string, { ADD_ATTR: ["target"], ALLOWED_URI_REGEXP: URI }).replace(/<a /g, '<a target="_blank" rel="noreferrer" ')),
    });
  }, [text]);
  return (
    <div className="markdown">
      {parts.map((p, i) => (p.kind === "mermaid" ? <Mermaid key={i} code={p.body} /> : <Html key={i} html={p.body} />))}
    </div>
  );
}
