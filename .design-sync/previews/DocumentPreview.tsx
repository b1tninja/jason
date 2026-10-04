import { DocumentPreview, type EvidenceAnswer } from "jason-ui";

// Each cell renders from static evidence answers with the sign-in fixed (`signedIn`), so nothing is fetched: the
// thumbnails are data URLs standing in for `/api/thumb?path=` (the recorded PDF's page 1) and `/api/drive/thumb/<id>`.
const ID = "1ExampleDocId01";
const PATH = "governing/Example Declaration.pdf";
const today = new Date("2099-10-03T12:00:00");

const sheet = (title: string, stamp: boolean) => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='285'><rect width='220' height='285' fill='#fff'/>"
  + (stamp ? "<rect x='130' y='14' width='76' height='30' fill='none' stroke='#555' stroke-width='1.5'/><text x='136' y='34' font-family='monospace' font-size='9' fill='#333'>RECORDED</text>" : "")
  + `<text x='22' y='70' font-family='Georgia' font-size='14' fill='#222'>${title}</text>`
  + [94, 108, 122, 136, 150, 164, 178, 192, 206, 220].map((y) => `<rect x='22' y='${y}' width='${y % 28 ? 176 : 130}' height='4' fill='#d6d9de'/>`).join("")
  + "</svg>",
);

const source = (name: string, readAt: string) => ({ name, readAt, digest: "", fields: [], text: "", citation: "", caveat: "", note: "" });
const drive: EvidenceAnswer = {
  found: true, address: `drive:${ID}`, label: "Declaration", kind: "drive",
  sources: [source("Copy from Drive", "2099-10-03T15:00:00+00:00"), source("Drive catalog", "2099-10-02T08:00:00+00:00")],
  changed: false, changedNote: "", link: `https://docs.google.com/document/d/${ID}/edit`, refresh: [], caveats: [], note: "",
  refreshable: { system: "Google Drive", what: "Export this file again from Drive" },
  documents: [{ id: "pdf", name: "Declaration.pdf", kind: "pdf", size: 48_000, readAt: "2099-10-03T15:00:00+00:00", note: "" }],
};
const recorded: EvidenceAnswer = {
  found: true, address: `file:${PATH}`, label: "Example Declaration.pdf", kind: "file",
  sources: [source("Recorded copy", "2099-01-15T00:00:00+00:00")], changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "",
  refreshable: null,
  documents: [{ id: "pdf", name: "Example Declaration.pdf", kind: "pdf", size: 2_100_000, readAt: "2099-01-15T00:00:00+00:00", note: "Recorded copy" },
    { id: "text", name: "Example Declaration.pdf, its text", kind: "text", size: 180_000, readAt: "2099-01-15T00:00:00+00:00", note: "" }],
};
const cell = { width: 480 };
// The acts are wired to promises that never settle: a cell shows them enabled, and a click changes nothing.
const idle = { onRead: () => new Promise<EvidenceAnswer>(() => {}), onView: () => new Promise<never>(() => {}) };

/** A Drive file alone: exactly `DrivePreview` (thumbnail, the copy's age, Preview, Read from Drive, Open in Google). */
export const Drive = () => (
  <div style={cell}><DocumentPreview name="Declaration" driveId={ID} driveEvidence={drive} signedIn driveThumb={sheet("Declaration", false)} today={today} by="Jane Example" {...idle} /></div>
);

/** A recorded PDF on disk: page 1 rendered by jason, labelled "Recorded copy", and Preview; no read again, since a
 * recorded instrument does not change. */
export const Recorded = () => (
  <div style={cell}><DocumentPreview name="Declaration" path={PATH} recordedEvidence={recorded} signedIn recordedThumb={sheet("Declaration", true)} today={today} by="Jane Example" {...idle} /></div>
);

/** Both: the recorded copy first (the one that governs), the Drive Doc beside it (a working copy), each labelled. */
export const Both = () => (
  <div style={cell}>
    <DocumentPreview name="Declaration" driveId={ID} path={PATH} driveEvidence={drive} recordedEvidence={recorded} signedIn
      driveThumb={sheet("Declaration", false)} recordedThumb={sheet("Declaration", true)} today={today} by="Jane Example" {...idle} />
  </div>
);

/** Signed out: both placeholders ask for a sign-in, never a broken image; Open in Google stays. */
export const SignedOut = () => (
  <div style={cell}>
    <DocumentPreview name="Declaration" driveId={ID} path={PATH} driveEvidence={drive} recordedEvidence={recorded} signedIn={false}
      driveThumb={sheet("Declaration", false)} recordedThumb={sheet("Declaration", true)} today={today} />
  </div>
);
