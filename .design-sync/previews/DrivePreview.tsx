import { DrivePreview, type EvidenceAnswer } from "jason-ui";

// Each cell renders from a static evidence answer with the sign-in fixed (`signedIn`), so nothing is fetched: the
// thumbnail is a data URL standing in for `/api/drive/thumb/<id>`.
const ID = "1ExampleDocId01";
const today = new Date("2099-10-03T12:00:00");

const thumb = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='285'><rect width='220' height='285' fill='#fff'/>"
  + "<text x='22' y='40' font-family='Georgia' font-size='15' fill='#222'>Example Village</text>"
  + "<text x='22' y='62' font-family='Georgia' font-size='12' fill='#444'>Notice of Hearing</text>"
  + [90, 104, 118, 132, 146, 160, 174, 188, 202, 216].map((y) => `<rect x='22' y='${y}' width='${y % 28 ? 176 : 130}' height='4' fill='#d6d9de'/>`).join("")
  + "</svg>",
);

const source = (name: string, readAt: string) => ({ name, readAt, digest: "", fields: [], text: "", citation: "", caveat: "", note: "" });
const answer = (over: Partial<EvidenceAnswer> = {}): EvidenceAnswer => ({
  found: true, address: `drive:${ID}`, label: "Notice of Hearing", kind: "drive" as EvidenceAnswer["kind"],
  sources: [source("Copy from Drive", "2099-10-03T15:00:00+00:00"), source("Drive catalog", "2099-10-02T08:00:00+00:00")],
  changed: false, changedNote: "", link: `https://docs.google.com/document/d/${ID}/edit`,
  refresh: [], caveats: [], note: "", refreshable: { system: "Google Drive", what: "Export this file again from Drive" },
  documents: [{ id: "pdf", name: "Notice of Hearing.pdf", kind: "pdf", size: 48_000, readAt: "2099-10-03T15:00:00+00:00", note: "" }],
  ...over,
});
const cell = { width: 240 };
// The acts are wired to promises that never settle: a cell shows them enabled, and a click changes nothing.
const idle = { onRead: () => new Promise<EvidenceAnswer>(() => {}), onView: () => new Promise<never>(() => {}) };

/** jason's copy, read from Drive on Oct 3: the thumbnail as a sheet of paper, its age, and Preview, Read from Drive,
 * and Open in Google beneath it. */
export const WithThumbnail = () => (
  <div style={cell}><DrivePreview driveId={ID} name="Notice of Hearing" evidence={answer()} signedIn thumb={thumb} today={today} by="Jane Example" {...idle} /></div>
);

/** No copy yet: a paper-shaped placeholder; Preview waits for a read, which is a person's click. */
export const NoPreview = () => (
  <div style={cell}>
    <DrivePreview driveId={ID} name="Notice of Hearing" signedIn today={today} by="Jane Example" {...idle}
      evidence={answer({ sources: [source("Drive catalog", "2099-10-02T08:00:00+00:00")], documents: [], changed: null })} />
  </div>
);

/** Signed out: the placeholder asks for a sign-in, never a broken image; Open in Google stays. */
export const SignedOut = () => (
  <div style={cell}><DrivePreview driveId={ID} name="Notice of Hearing" evidence={answer()} signedIn={false} thumb={thumb} today={today} /></div>
);

/** Drive's listing is newer than the copy: "Changed in Drive since this copy", in the warning tone. */
export const ChangedInDrive = () => (
  <div style={cell}><DrivePreview driveId={ID} name="Notice of Hearing" evidence={answer({ changed: true })} signedIn thumb={thumb} today={today} by="Jane Example" {...idle} /></div>
);
