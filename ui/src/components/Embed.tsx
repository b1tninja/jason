import { useEffect, useRef, useState } from "react";

export type EmbedKind =
  | "doc" | "sheet" | "slides" | "form" | "drive" | "image" | "pdf" | "url"
  | "calendar" | "zoom" | "audio" | "map" | "chart" | "thread";

export interface EmbedOptions {
  /** calendar: Google's embed view. */
  mode?: "AGENDA" | "WEEK" | "MONTH";
  /** calendar: the range shown, `YYYYMMDD/YYYYMMDD`. */
  dates?: string;
  /** calendar: an IANA time zone for the embed. */
  tz?: string;
  /** chart (bare Sheet id): the sheet tab. */
  gid?: string;
  /** chart (bare Sheet id): the range, e.g. `A1:D20`. */
  range?: string;
}

export interface Attachment {
  kind: EmbedKind;
  /** A Google file id, a URL (http, blob, or data), a path under data/ (image, pdf, audio), a calendar id,
   * an address or "lat,lng" (map), a Sheet id or published chart URL (chart), or a Gmail thread id or URL (thread). */
  ref: string;
  title?: string;
  opts?: EmbedOptions;
}

/** The Google file id in a Docs/Sheets/Slides/Forms/Drive URL, or the string itself when it already is one. */
export function googleId(ref: string): string {
  const m = ref.match(/\/(?:d|folders|file\/d)\/([A-Za-z0-9_-]{10,})/) ?? ref.match(/[?&]id=([A-Za-z0-9_-]{10,})/);
  return m ? m[1] : ref;
}

const isWebRef = (ref: string) => /^(https?:|blob:|data:)/.test(ref);

/** A local file goes through the server's read-only /api/file; a URL is used as it is. */
function fileUrl(ref: string): string {
  return isWebRef(ref) ? ref : `/api/file?path=${encodeURIComponent(ref)}`;
}

/** The calendar id in a calendar.google.com embed URL (`src=`), or the string itself when it already is one. */
function calendarId(ref: string): string {
  if (/^https?:\/\//.test(ref)) {
    try {
      const u = new URL(ref);
      const src = u.searchParams.get("src") ?? u.searchParams.get("cid");
      if (src) return src;
    } catch { /* not a URL after all; fall through */ }
  }
  return ref;
}

/** The thread id at the end of a Gmail URL (`#all/<id>`, `#inbox/<id>`, `/#thread/<id>`), or the string itself. */
function threadId(ref: string): string {
  const m = ref.match(/#[a-z]+\/(?:[^/]+\/)?([A-Za-z0-9_-]+)\s*$/);
  return m ? m[1] : ref;
}

/** Where each kind embeds and opens. */
export function embedUrls(a: Attachment): { frame: string; open: string } {
  switch (a.kind) {
    case "doc": { const id = googleId(a.ref); return { frame: `https://docs.google.com/document/d/${id}/preview`, open: `https://docs.google.com/document/d/${id}/edit` }; }
    case "sheet": { const id = googleId(a.ref); return { frame: `https://docs.google.com/spreadsheets/d/${id}/preview`, open: `https://docs.google.com/spreadsheets/d/${id}/edit` }; }
    case "slides": { const id = googleId(a.ref); return { frame: `https://docs.google.com/presentation/d/${id}/embed`, open: `https://docs.google.com/presentation/d/${id}/edit` }; }
    case "form": { const id = googleId(a.ref); return { frame: `https://docs.google.com/forms/d/${id}/viewform?embedded=true`, open: `https://docs.google.com/forms/d/${id}/edit` }; }
    case "drive": { const id = googleId(a.ref); return { frame: `https://drive.google.com/file/d/${id}/preview`, open: `https://drive.google.com/file/d/${id}/view` }; }
    case "image":
    case "pdf":
    case "audio": {
      const u = fileUrl(a.ref);
      return { frame: u, open: u };
    }
    case "calendar": {
      const id = calendarId(a.ref);
      const p = new URLSearchParams({ src: id, mode: a.opts?.mode ?? "AGENDA" });
      if (a.opts?.tz) p.set("ctz", a.opts.tz);
      if (a.opts?.dates) p.set("dates", a.opts.dates);
      return { frame: `https://calendar.google.com/calendar/embed?${p}`, open: `https://calendar.google.com/calendar/u/0/r?cid=${encodeURIComponent(id)}` };
    }
    case "zoom": return { frame: a.ref, open: a.ref };
    case "map": {
      const q = encodeURIComponent(a.ref);
      return { frame: `https://maps.google.com/maps?q=${q}&output=embed`, open: `https://maps.google.com/maps?q=${q}` };
    }
    case "chart": {
      if (/\/pubchart/.test(a.ref)) return { frame: a.ref, open: a.ref };
      const id = googleId(a.ref);
      const p = new URLSearchParams();
      if (a.opts?.gid) p.set("gid", a.opts.gid);
      if (a.opts?.range) p.set("range", a.opts.range);
      const qs = p.toString();
      return { frame: `https://docs.google.com/spreadsheets/d/${id}/preview${qs ? `?${qs}` : ""}`, open: `https://docs.google.com/spreadsheets/d/${id}/edit${qs ? `?${qs}` : ""}` };
    }
    case "thread": {
      const u = /^https?:\/\//.test(a.ref) ? a.ref : `https://mail.google.com/mail/u/0/#all/${threadId(a.ref)}`;
      return { frame: u, open: u };
    }
    default: return { frame: a.ref, open: a.ref };
  }
}

/** Kinds that never go in a frame: Gmail refuses framing, so a thread is a link card. */
const LINK_ONLY: ReadonlySet<EmbedKind> = new Set<EmbedKind>(["thread"]);

function hostOf(url: string): string {
  try { return new URL(url, window.location.href).host; } catch { return ""; }
}

/** A card standing in for a frame: the title, the host, and a link out. */
function LinkCard({ title, open, note, openLabel = "open" }: { title: string; open: string; note?: string; openLabel?: string }) {
  return (
    <div className="embed-link">
      <div className="embed-link-title">{title}</div>
      <div className="embed-link-host">{hostOf(open)}</div>
      <a href={open} target="_blank" rel="noreferrer">{openLabel}</a>
      {note && <p className="embed-link-note">{note}</p>}
    </div>
  );
}

/** An iframe that gives up: when no `load` event arrives within `timeoutMs`, or an `error` event fires, `onRefused` is called.
 * Honest limit: a cross-origin frame that refuses embedding through X-Frame-Options or CSP still fires `load` in Chromium
 * (the browser shows its own error page inside the frame), so this mainly catches hosts that are unreachable or very slow.
 * It cannot see a refusal the browser hides from the page. */
export function Frame({ src, title, height, timeoutMs = 4000, onRefused }: { src: string; title: string; height: number; timeoutMs?: number; onRefused: () => void }) {
  const loaded = useRef(false);
  const refused = useRef(onRefused);
  refused.current = onRefused;
  useEffect(() => {
    loaded.current = false;
    const t = window.setTimeout(() => { if (!loaded.current) refused.current(); }, timeoutMs);
    return () => window.clearTimeout(t);
  }, [src, timeoutMs]);
  return <iframe src={src} title={title} height={height} loading="lazy" allow="fullscreen" onLoad={() => { loaded.current = true; }} onError={() => refused.current()} />;
}

/** A Google Doc, Sheet, Slides deck, Form, Drive file, calendar, Zoom recording, map, or Sheets chart in a frame; a photo as an
 * image; audio in the browser's player; a PDF in the browser's viewer; a Gmail thread as a link card.
 * The viewer must already have access to the Google file: the frame shows Google's own sign-in otherwise.
 * A frame that never loads (within `timeoutMs`) is swapped for a link card. */
export function Embed({ a, height = 480, timeoutMs = 4000 }: { a: Attachment; height?: number; timeoutMs?: number }) {
  const { frame, open } = embedUrls(a);
  const title = a.title || `${a.kind}: ${a.ref}`;
  const [refused, setRefused] = useState(false);
  useEffect(() => { setRefused(false); }, [frame]);

  let body;
  if (a.kind === "image") body = <img src={frame} alt={title} loading="lazy" />;
  else if (a.kind === "audio") body = <audio controls src={frame} title={title} />;
  else if (LINK_ONLY.has(a.kind)) body = <LinkCard title={title} open={open} openLabel="open in Gmail" />;
  else if (refused) body = <LinkCard title={title} open={open} note="This page does not allow embedding." />;
  else body = <Frame src={frame} title={title} height={height} timeoutMs={timeoutMs} onRefused={() => setRefused(true)} />;

  return (
    <figure className="embed">
      {body}
      <figcaption className="row wrap"><span>{title}</span><a href={open} target="_blank" rel="noreferrer">open</a></figcaption>
    </figure>
  );
}
