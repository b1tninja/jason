export type EmbedKind = "doc" | "sheet" | "slides" | "form" | "drive" | "image" | "pdf" | "url";

export interface Attachment {
  kind: EmbedKind;
  ref: string;   // a Google file id, a URL (http, blob, or data), or a path under data/ (image, pdf)
  title?: string;
}

/** The Google file id in a Docs/Sheets/Slides/Forms/Drive URL, or the string itself when it already is one. */
export function googleId(ref: string): string {
  const m = ref.match(/\/(?:d|folders|file\/d)\/([A-Za-z0-9_-]{10,})/) ?? ref.match(/[?&]id=([A-Za-z0-9_-]{10,})/);
  return m ? m[1] : ref;
}

/** Where each kind embeds and opens. A local file goes through the server's read-only /api/file. */
export function embedUrls(a: Attachment): { frame: string; open: string } {
  const id = googleId(a.ref);
  switch (a.kind) {
    case "doc": return { frame: `https://docs.google.com/document/d/${id}/preview`, open: `https://docs.google.com/document/d/${id}/edit` };
    case "sheet": return { frame: `https://docs.google.com/spreadsheets/d/${id}/preview`, open: `https://docs.google.com/spreadsheets/d/${id}/edit` };
    case "slides": return { frame: `https://docs.google.com/presentation/d/${id}/embed`, open: `https://docs.google.com/presentation/d/${id}/edit` };
    case "form": return { frame: `https://docs.google.com/forms/d/${id}/viewform?embedded=true`, open: `https://docs.google.com/forms/d/${id}/edit` };
    case "drive": return { frame: `https://drive.google.com/file/d/${id}/preview`, open: `https://drive.google.com/file/d/${id}/view` };
    case "image":
    case "pdf": {
      const u = /^(https?:|blob:|data:)/.test(a.ref) ? a.ref : `/api/file?path=${encodeURIComponent(a.ref)}`;
      return { frame: u, open: u };
    }
    default: return { frame: a.ref, open: a.ref };
  }
}

/** A Google Doc, Sheet, Slides deck, Form, or Drive file in a frame; a photo as an image; a PDF in the browser's viewer.
 * The viewer must already have access to the Google file: the frame shows Google's own sign-in otherwise. */
export function Embed({ a, height = 480 }: { a: Attachment; height?: number }) {
  const { frame, open } = embedUrls(a);
  const title = a.title || `${a.kind}: ${a.ref}`;
  return (
    <figure className="embed">
      {a.kind === "image" ? <img src={frame} alt={title} loading="lazy" /> : <iframe src={frame} title={title} height={height} loading="lazy" allow="fullscreen" />}
      <figcaption className="row wrap"><span>{title}</span><a href={open} target="_blank" rel="noreferrer">open</a></figcaption>
    </figure>
  );
}
