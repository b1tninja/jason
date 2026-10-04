import { useEffect, useRef, useState } from "react";
import { getJson, signInRefusal } from "../lib/api";
import { driveDocRef, fileDocRef } from "../lib/docref";
import { useAccount } from "../lib/session";
import { Doc, type DocStatic, type DriveKind } from "./Doc";

/* `Embed` (docs/console/documents.md, "The Embed component"): what is meant to be framed stays a frame, and a document
 * becomes a `Doc`.
 * - A private Google file (`doc`, `sheet`, `slides`, `form`, `drive`, and a chart by its Sheet id) is a `Doc` card on
 *   `drive:<id>`: jason's copy, a logged view, and "Open in Google". Never a Google frame, which many browsers show blank.
 * - A photo or PDF under data/ is a `Doc` on `file:<path>` (a photo inline, a PDF as a card): never a URL into data/.
 * - What stays a frame (the public calendar, a published chart or Google file, a map, a Zoom share page) is framed only
 *   on its kind's hosts (`EMBED_HOSTS`), with `sandbox` at the kind's minimum, `referrerpolicy="no-referrer"`, and a
 *   `title`; anything else is a link card. A frame loads on a person's click (rule 2: nothing outside is read on
 *   load), unless the screen passes `load="mount"` for a public frame that is its subject.
 * - Audio under data/ is still the browser's player on jason-web's file route, signed in: the evidence's `file:` row
 *   shows PDFs, images, and text, not audio, so it moves to `Doc` once that row plays audio. */

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

/** When a frame to an outside host loads: on a person's click (the default), or on mount for a public frame that is the
 * screen's subject (the association's calendar on the Calendar screen). */
export type EmbedLoad = "click" | "mount";

/** The Google file id in a Docs/Sheets/Slides/Forms/Drive URL, or the string itself when it already is one. */
export function googleId(ref: string): string {
  const m = ref.match(/\/(?:d|folders|file\/d)\/([A-Za-z0-9_-]{10,})/) ?? ref.match(/[?&]id=([A-Za-z0-9_-]{10,})/);
  return m ? m[1] : ref;
}

const isWebRef = (ref: string) => /^(https?:|blob:|data:)/.test(ref);
const isLocalUrl = (ref: string) => /^(blob:|data:)/.test(ref);
const DRIVE_ID = /^[A-Za-z0-9_-]{10,}$/;
const ABSOLUTE = /^(?:[A-Za-z]:[\\/]|[\\/]|~)/;

/** A local file goes through the server's read-only /api/file; a URL is used as it is. Kept for the audio player and
 * for links (`packetFrame`); a screen shows a file under data/ with `Doc`. */
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

// --- what may be framed -------------------------------------------------------------------------------------------------

/** One kind's frame rule: the hosts it may frame (a leading "." matches any subdomain), the path it must have, and the
 * kind's minimum `sandbox` tokens. */
export interface FrameRule { hosts: readonly string[]; path: RegExp; sandbox: string }

const POPUPS = "allow-popups allow-popups-to-escape-sandbox";
/** A published Google file (`/d/e/<id>/pub`, `pubhtml`, `embed`, `viewform`, `pubchart`): public, meant to be framed. */
const PUBLISHED: FrameRule = { hosts: ["docs.google.com"], path: /^\/(?:document|spreadsheets|presentation|forms)\/d\/e\/[^/]+\/(?:pub|pubhtml|embed|viewform|pubchart)\b/,
  sandbox: `allow-scripts allow-same-origin ${POPUPS}` };

/** The frames `Embed` keeps, by kind (docs/console/documents.md, "The Embed component"). Anything else is a link card. */
export const EMBED_HOSTS: Readonly<Partial<Record<EmbedKind, FrameRule>>> = {
  calendar: { hosts: ["calendar.google.com"], path: /^\/calendar\/embed\b/, sandbox: `allow-scripts allow-same-origin ${POPUPS}` },
  chart: { hosts: ["docs.google.com"], path: /^\/spreadsheets\/d\/e\/[^/]+\/pubchart\b/, sandbox: "allow-scripts allow-same-origin" },
  zoom: { hosts: ["zoom.us", ".zoom.us"], path: /^\/rec\/(?:share|play)\//, sandbox: `allow-scripts allow-same-origin allow-forms ${POPUPS}` },
  map: { hosts: ["maps.google.com", "www.google.com"], path: /^\/maps\b/, sandbox: `allow-scripts allow-same-origin ${POPUPS}` },
  doc: PUBLISHED, sheet: PUBLISHED, slides: PUBLISHED, form: PUBLISHED, drive: PUBLISHED,
};

const hostMatches = (host: string, hosts: readonly string[]) => hosts.some((h) => (h.startsWith(".") ? host.endsWith(h) : host === h));

/** The rule that lets `url` be framed for `kind`: an https URL on one of the kind's hosts with the kind's path; else
 * null (a link card). */
export function frameRule(kind: EmbedKind, url: string): FrameRule | null {
  const rule = EMBED_HOSTS[kind];
  if (!rule) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" && hostMatches(u.host.toLowerCase(), rule.hosts) && rule.path.test(u.pathname) ? rule : null;
  } catch {
    return null;
  }
}

const isPublished = (ref: string) => /^https:\/\/docs\.google\.com\/[a-z]+\/d\/e\//.test(ref);

function hostOf(url: string): string {
  try { return new URL(url, window.location.href).host; } catch { return ""; }
}

const DRIVE_KINDS: Partial<Record<EmbedKind, DriveKind>> = { doc: "doc", sheet: "sheet", slides: "slides", form: "drive", drive: "drive" };

/** The document an attachment names, as a reference built in the browser (the server decides its level when it is
 * opened): a private Google file (`drive:<id>`), or a photo or PDF under data/ (`file:<path>`); null for anything else,
 * which stays a frame, a player, or a link. A loader that returns `DocRef`s passes them instead. */
export function attachmentDocRef(a: Attachment) {
  const ref = (a.ref ?? "").trim();
  const title = a.title || "";
  const chartId = a.kind === "chart" && !/\/pubchart/.test(ref) ? googleId(ref) : "";
  if (DRIVE_KINDS[a.kind] || chartId) {
    if (isPublished(ref)) return null;
    const id = chartId || googleId(ref);
    if (!DRIVE_ID.test(id)) return null;
    return driveDocRef(id, title || `Drive file ${id}`, { original: { url: embedUrls(a).open, label: "Open in Google" } });
  }
  if ((a.kind === "image" || a.kind === "pdf") && ref && !isWebRef(ref) && !ABSOLUTE.test(ref)) {
    return fileDocRef(ref, title || ref.split("/").pop() || ref);
  }
  return null;
}

// --- the pieces --------------------------------------------------------------------------------------------------------------

/** A card standing in for a frame: the title, the host, and a link out. */
function LinkCard({ title, open, note, openLabel = "open" }: { title: string; open: string; note?: string; openLabel?: string }) {
  return (
    <div className="embed-link">
      <div className="embed-link-title">{title}</div>
      {open && <div className="embed-link-host">{hostOf(open)}</div>}
      {open && <a href={open} target="_blank" rel="noreferrer">{openLabel}</a>}
      {note && <p className="embed-link-note">{note}</p>}
    </div>
  );
}

/** A frame or remote media that waits for a person's click: the title, the host, and "Load from <host>". */
function ClickToLoad({ title, host, onLoad }: { title: string; host: string; onLoad: () => void }) {
  return (
    <div className="embed-link">
      <div className="embed-link-title">{title}</div>
      <div className="embed-link-host">{host}</div>
      <button type="button" aria-label={`Load ${title} from ${host}`} onClick={onLoad}>Load from {host}</button>
      <p className="embed-link-note">Nothing is asked of {host} until you click; it then sees your browser's own session there.</p>
    </div>
  );
}

/** An iframe that gives up: when no `load` event arrives within `timeoutMs`, or an `error` event fires, `onRefused` is called.
 * Every frame is sandboxed (`sandbox`, the kind's minimum tokens; none given is the strictest), sends no referrer, and
 * carries a `title`.
 * Honest limit: a cross-origin frame that refuses embedding through X-Frame-Options or CSP still fires `load` in Chromium
 * (the browser shows its own error page inside the frame), so this mainly catches hosts that are unreachable or very slow.
 * It cannot see a refusal the browser hides from the page. */
export function Frame({ src, title, height, timeoutMs = 4000, sandbox = "", onRefused }: {
  src: string; title: string; height: number; timeoutMs?: number; sandbox?: string; onRefused: () => void;
}) {
  const loaded = useRef(false);
  const refused = useRef(onRefused);
  refused.current = onRefused;
  useEffect(() => {
    loaded.current = false;
    const t = window.setTimeout(() => { if (!loaded.current) refused.current(); }, timeoutMs);
    return () => window.clearTimeout(t);
  }, [src, timeoutMs]);
  return <iframe src={src} title={title} height={height} loading="lazy" allow="fullscreen" sandbox={sandbox} referrerPolicy="no-referrer"
    onLoad={() => { loaded.current = true; }} onError={() => refused.current()} />;
}

/** A card standing in for a file jason-web did not serve: the reason in the server's words, and "Sign in with Google"
 * when a sign-in is what it needs. */
function FileCard({ title, text, signIn }: { title: string; text: string; signIn?: string }) {
  return (
    <div className="embed-link embed-file-card">
      <div className="embed-link-title">{title}</div>
      <p className="embed-link-note">{text}{signIn && <> <a href={signIn}>Sign in with Google</a></>}</p>
    </div>
  );
}

/** Audio under data/ in the browser's player, for a signed-in person (`jason.web.access`); a refusal is asked once more
 * as JSON for its reason, shown on a card. */
function ServedAudio({ title, src }: { title: string; src: string }) {
  const account = useAccount(true);
  const [notServed, setNotServed] = useState<{ text: string; signIn?: string } | null>(null);
  useEffect(() => { setNotServed(null); }, [src]);
  const why = async () => {
    try {
      await getJson<unknown>(src);
      setNotServed({ text: "The browser could not play this file." });
    } catch (e: unknown) {
      const asked = signInRefusal(e);
      setNotServed(asked ? { text: asked.message, signIn: asked.href } : { text: e instanceof Error ? e.message : String(e) });
    }
  };
  if (!account.known) return <FileCard title={title} text="Checking your sign-in…" />;
  if (!account.account) {
    return account.configured
      ? <FileCard title={title} text="Sign in with Google to see this file." signIn={account.href} />
      : <FileCard title={title} text="Console sign-in isn't set up on this jason-web; files under data/ open only for a signed-in person." />;
  }
  if (notServed) return <FileCard title={title} text={notServed.text} signIn={notServed.signIn} />;
  return <audio controls src={src} title={title} onError={() => void why()} />;
}

// --- Embed ----------------------------------------------------------------------------------------------------------------

/** One attachment as the rules above say: a `Doc` for a document, a sandboxed frame on its kind's hosts (on a click, or
 * on mount with `load="mount"`), the player for audio under data/, and a link card for anything else (a web page, a
 * Gmail thread, a host off the list, a frame that never loads within `timeoutMs`). `docProps` passes to the `Doc`
 * (previews, tests). */
export function Embed({ a, height = 480, timeoutMs = 4000, load = "click", docProps }: {
  a: Attachment; height?: number; timeoutMs?: number; load?: EmbedLoad; docProps?: DocStatic;
}) {
  const ref = (a.ref ?? "").trim();
  const published = DRIVE_KINDS[a.kind] && isPublished(ref);
  const { frame, open } = published ? { frame: ref, open: ref } : embedUrls(a);
  const title = a.title || `${a.kind}: ${ref}`;
  const [refused, setRefused] = useState(false);
  const [clicked, setClicked] = useState(false);
  useEffect(() => { setRefused(false); setClicked(false); }, [frame]);
  const doc = attachmentDocRef(a);

  if (doc) {
    const variant = a.kind === "image" ? "inline" : "card";
    const driveKind = a.kind === "chart" ? "sheet" : DRIVE_KINDS[a.kind];
    return (
      <figure className="embed">
        <Doc doc={doc} variant={variant} {...(driveKind ? { driveKind } : {})} {...docProps} />
      </figure>
    );
  }

  let body;
  const local = !isWebRef(ref);
  if ((a.kind === "image" || a.kind === "pdf") && local) {
    body = <FileCard title={title} text="Not a path under the data folder: give the file's path inside it (photos/east-bed.jpg)." />;
  } else if (a.kind === "audio" && local) {
    body = <ServedAudio title={title} src={frame} />;
  } else if ((a.kind === "image" || a.kind === "audio") && isLocalUrl(ref)) {
    body = a.kind === "image" ? <img src={ref} alt={title} /> : <audio controls src={ref} title={title} />;
  } else if (a.kind === "image" || a.kind === "audio") {
    const host = hostOf(ref);
    body = !clicked ? <ClickToLoad title={title} host={host} onLoad={() => setClicked(true)} />
      : a.kind === "image" ? <img src={ref} alt={title} referrerPolicy="no-referrer" /> : <audio controls src={ref} title={title} />;
  } else if (a.kind === "thread") {
    body = <LinkCard title={title} open={open} openLabel="open in Gmail" />;
  } else {
    const rule = frameRule(a.kind, frame);
    const host = hostOf(frame);
    if (!rule) body = <LinkCard title={title} open={open} note={a.kind === "url" || a.kind === "pdf" ? undefined : `jason frames a ${a.kind} only from ${(EMBED_HOSTS[a.kind]?.hosts ?? []).join(", ") || "no host"}.`} />;
    else if (refused) body = <LinkCard title={title} open={open} note="This page does not allow embedding." />;
    else if (load !== "mount" && !clicked) body = <ClickToLoad title={title} host={host} onLoad={() => setClicked(true)} />;
    else body = <Frame src={frame} title={title} height={height} timeoutMs={timeoutMs} sandbox={rule.sandbox} onRefused={() => setRefused(true)} />;
  }

  const outside = /^https?:/.test(open);
  return (
    <figure className="embed">
      {body}
      <figcaption className="row wrap"><span>{title}</span>{outside && <a href={open} target="_blank" rel="noreferrer">open</a>}</figcaption>
    </figure>
  );
}
