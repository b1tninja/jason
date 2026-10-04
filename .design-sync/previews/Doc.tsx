import { Doc, DocList, type DocRef, type DocumentView, type EvidenceAnswer, type PrivateView } from "jason-ui";

// Each cell renders from static references and answers with the sign-in fixed (`signedIn`), so nothing is fetched. The
// thumbnails are data URLs standing in for `/api/thumb?path=` and `/api/drive/thumb/<id>`. Everything here is made up.
const today = new Date("2099-10-03T12:00:00");
const sheet = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='285'><rect width='220' height='285' fill='#fff'/>"
  + "<text x='22' y='60' font-family='Georgia' font-size='14' fill='#222'>Example letter</text>"
  + [84, 98, 112, 126, 140, 154, 168, 182].map((y) => `<rect x='22' y='${y}' width='${y % 28 ? 176 : 130}' height='4' fill='#d6d9de'/>`).join("")
  + "</svg>",
);

const letter: DocRef = { address: "file:mail/100/contents.pdf", document: "pdf", name: "Letter from a vendor", kind: "pdf",
  level: "P2", source: "Scan", readAt: "2099-10-01T15:00:00+00:00", size: 90_000, thumb: true };
const minutes: DocRef = { address: "file:board/minutes-draft-2099-10-01.md", document: "text", name: "Minutes draft, Oct 1",
  kind: "text", level: "P1", source: "File on disk", readAt: "2099-10-02T15:00:00+00:00", size: 2048 };
const rules: DocRef = { address: "drive:1ExampleDriveFile01", document: "pdf", name: "Example rules", kind: "pdf", level: "P0",
  source: "Drive copy", readAt: "2099-09-20T15:00:00+00:00", size: 48_000, thumb: true, stale: "Changed in Drive since this copy",
  original: { url: "https://docs.google.com/document/d/1ExampleDriveFile01/edit", label: "Open in Google" },
  refreshable: { system: "Google Drive", what: "Export this file again from Drive" } };
const hearing: DocRef = { address: "file:zoom/hearings/Notice.pdf", document: "pdf", name: "Notice of hearing", kind: "pdf", level: "P3",
  source: "File on disk" };
const statute: DocRef = { address: "CIV 4920(a)", document: "section", name: "CIV 4920(a)", kind: "text", level: "P0", source: "Statutes on disk" };

const shut: PrivateView = { open: false, mayOpen: true, minutes: [15, 30, 60], default: 30 };
const source = (name: string, readAt: string) => ({ name, readAt, digest: "", fields: [], text: "", citation: "", caveat: "", note: "" });
const answer = (over: Partial<EvidenceAnswer>): EvidenceAnswer => ({
  found: true, address: letter.address, label: letter.name, kind: "file", sources: [source("Recorded copy", letter.readAt!)],
  changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "", refreshable: null,
  documents: [{ id: "pdf", name: "contents.pdf", kind: "pdf", size: 90_000, readAt: letter.readAt!, note: "" }], ...over,
});
const driveAnswer = answer({ address: rules.address, kind: "drive", changed: true, link: rules.original!.url, refreshable: rules.refreshable,
  sources: [source("Copy from Drive", rules.readAt!)], documents: [{ id: "pdf", name: "Example rules.pdf", kind: "pdf", size: 48_000, readAt: rules.readAt!, note: "" }] });
const missing = answer({ documents: [], refresh: [{ command: "jason mail --sync", live: false, what: "read the scanned mail into data/mail" }] });
const minutesView: DocumentView = { kind: "text", name: minutes.name, readAt: minutes.readAt!, url: "", expires: "", caveats: [],
  text: "# DRAFT Minutes of the October 1 meeting\n\n## Call to order\n\nThe president called the meeting to order at 6:30 p.m.\n\n## Approval of the agenda\n\nThe agenda was approved as posted." };
// The acts are wired to promises that never settle (a click changes nothing), except the inline P1 view, which answers.
const idle = { onRead: () => new Promise<EvidenceAnswer>(() => {}), onView: () => new Promise<never>(() => {}) };
const cell = { width: 520 };

/** Chips in a sentence: a scan, a statute, and a P3 hearing notice (marked). A click opens the viewer, a logged view. */
export const Chips = () => (
  <p style={cell}>
    The vendor's <Doc doc={letter} signedIn by="Jane Example" {...idle} /> answers the notice under <Doc doc={statute} signedIn by="Jane Example" {...idle} />;
    the hearing's <Doc doc={hearing} signedIn privateView={shut} by="Jane Example" {...idle} /> is confidential.
  </p>
);

/** A chip signed out: clicking says to sign in, in words. */
export const ChipSignedOut = () => <p style={cell}>See <Doc doc={letter} signedIn={false} /> (click it).</p>;

/** Rows: a list of documents with a thumbnail, kind and size, age, View, the original, and the stale line. */
export const Rows = () => (
  <div style={cell}><DocList docs={[letter, minutes, rules]} signedIn by="Jane Example" today={today} {...idle} /></div>
);

/** Rows signed out: View is off, and the list says why, with the sign-in link. */
export const RowsSignedOut = () => (
  <div style={cell}><DocList docs={[letter, minutes]} signedIn={false} by="" today={today} /></div>
);

/** Cards: a scan with page 1, a Drive copy changed in Drive since its copy, and a P3 document held for the private view. */
export const Cards = () => (
  <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
    <Doc doc={letter} variant="card" evidence={answer({})} signedIn thumb={sheet} today={today} by="Jane Example" {...idle} />
    <Doc doc={rules} variant="card" evidence={driveAnswer} signedIn thumb={sheet} today={today} by="Jane Example" {...idle} />
    <Doc doc={hearing} variant="card" evidence={answer({ documents: [] })} signedIn privateView={shut} today={today} by="Jane Example" {...idle} />
  </div>
);

/** Cards when the document cannot be shown: signed out, and not on disk (the command that fills it). */
export const CardStates = () => (
  <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
    <Doc doc={letter} variant="card" evidence={answer({})} signedIn={false} thumb={sheet} today={today} />
    <Doc doc={{ ...letter, document: undefined, readAt: undefined, thumb: false }} variant="card" evidence={missing} signedIn today={today} by="Jane Example" {...idle} />
  </div>
);

/** Inline P1: the minutes draft as the screen's subject, viewed on mount, with its slim header. */
export const InlineOpen = () => (
  <div style={{ width: 640 }}>
    <Doc doc={minutes} variant="inline" signedIn by="Jane Example" today={today} onView={async () => minutesView} />
  </div>
);

/** Inline P2: "Show the document" first; nothing is viewed until the click. */
export const InlineRestricted = () => (
  <div style={{ width: 640 }}><Doc doc={letter} variant="inline" signedIn by="Jane Example" today={today} {...idle} /></div>
);

/** Inline P3 outside the private view, and inline missing. */
export const InlineStates = () => (
  <div style={{ width: 640, display: "grid", gap: 24 }}>
    <Doc doc={hearing} variant="inline" signedIn privateView={shut} by="Jane Example" today={today} {...idle} />
    <Doc doc={{ ...letter, document: undefined }} variant="inline" evidence={missing} signedIn by="Jane Example" today={today} {...idle} />
  </div>
);
