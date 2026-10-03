import DOMPurify from "dompurify";
import { marked } from "marked";
import { useEffect, useMemo, useRef, useState } from "react";

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

/** Markdown with ```mermaid fences rendered as diagrams, HTML sanitized, links opening in a new tab.
 * Images render as given: a local file under data/ is `/api/file?path=...`; a Drive image needs a public or served URL. */
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
    return out;
  }, [text]);
  return (
    <div className="markdown">
      {parts.map((p, i) =>
        p.kind === "mermaid" ? <Mermaid key={i} code={p.body} /> : (
          <div key={i} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(p.body, { async: false }) as string, { ADD_ATTR: ["target"], ALLOWED_URI_REGEXP: URI }).replace(/<a /g, '<a target="_blank" rel="noreferrer" ') }} />
        ))}
    </div>
  );
}
