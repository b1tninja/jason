import { DocumentViewer, type DocumentView } from "jason-ui";

// Each cell renders the viewer in place (`inline`), from a static `data`, so nothing is fetched and nothing is modal.
const UNMASKED = "Unmasked: shown because Jane Doe asked; this view is logged.";
const STORED = "A stored copy is what jason read then, not the record now.";
const today = new Date("2099-10-03T12:00:00");
const frame = { maxWidth: 880, height: 620 };

const pdfPlaceholder = "data:text/html;charset=utf-8," + encodeURIComponent(
  "<body style='margin:0;display:grid;place-items:center;height:100vh;background:#f6f7f9;color:#5f6b7a;font:15px system-ui'>pdf here</body>",
);
const photo = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800'><rect width='1200' height='800' fill='#dde1e7'/><text x='600' y='410' text-anchor='middle' font-family='system-ui' font-size='40' fill='#5f6b7a'>photo of the fence at 123 Main St</text></svg>",
);

const submission: DocumentView = {
  kind: "submission", name: "Owner information, Unit 12", readAt: "2099-09-30T18:38:00+00:00", url: "", expires: "",
  submission: {
    form: "Owner information 2099", unit: "12", submitted: "2099-09-28", completed: "2099-10-02", status: "Pending",
    intro: "Please tell the board how to reach you by October 23.\n\nThank you,\nThe board of Example Village",
    questions: [
      { question: "Owner", answer: "", kind: "section" },
      { question: "1. Owner's full name", answer: "Jane Doe", kind: "text", help: "As on the deed.", required: true },
      { question: "Answer for the unit named above.", answer: "", kind: "note" },
      { question: "Notice delivery", answer: "", kind: "section" },
      { question: "2. How should the Association deliver notices?", answer: "By mail; By email", kind: "choice", help: "Choose any." },
      { question: "3. Mailing address for notices", answer: "Same as my unit address; PO Box 12\nExample City, CA 90000", kind: "choice", help: "Tick it, or write another address.", flag: "both given" },
      { question: "4. Pets in the unit", answer: "None chosen", kind: "choice" },
      { question: "5. Lease (optional)", answer: "lease.pdf; addendum.pdf", kind: "file", files: ["77_lease.pdf"] },
      { question: "6. Second phone", answer: "", kind: "text" },
      { question: "Certification", answer: "", kind: "section" },
      { question: "I certify that I am an owner of record of this unit.", answer: "Certified", kind: "check", help: "Required to submit.", required: true },
    ],
  },
  caveats: [UNMASKED, STORED],
};

const listed = [
  { id: "submission", name: "Owner information, Unit 12", kind: "submission" as const, size: 0, readAt: "2099-09-30T18:38:00+00:00", note: "" },
  { id: "77_lease.pdf", name: "77_lease.pdf", kind: "pdf" as const, size: 48_000, readAt: "2099-09-30T18:38:00+00:00", note: "" },
  { id: "notes.txt", name: "notes.txt", kind: "text" as const, size: 812, readAt: "2099-09-30T18:38:00+00:00", note: "" },
];

/** A PayHOA form submission as the owner filled it in: the form's introduction, its sections as headings, a "choose
 * any" question as one answer, a "Same as" box and its line as one (flagged when both were given), each question's
 * help and "required", a saved file to open, a blank shown as "(no answer)", Print. */
export const Submission = () => (
  <div style={frame}><DocumentViewer inline today={today} data={submission} documents={listed} position={{ index: 0, count: 3 }} onGo={() => {}} /></div>
);

/** A PDF in a frame (a placeholder here), with the new-tab link and the link's expiry in the header. */
export const Pdf = () => (
  <div style={frame}>
    <DocumentViewer inline today={today} position={{ index: 1, count: 3 }} onGo={() => {}} data={{
      kind: "pdf", name: "Example Village lease addendum.pdf", readAt: "2099-09-30T18:38:00+00:00",
      url: pdfPlaceholder, expires: "2099-10-03T19:12:00+00:00", caveats: [UNMASKED],
    }} />
  </div>
);

/** An image, fitted to the dialog; the toggle shows it at its actual size. */
export const Image = () => (
  <div style={frame}>
    <DocumentViewer inline today={today} position={{ index: 2, count: 3 }} onGo={() => {}} data={{
      kind: "image", name: "Fence photo.jpg", readAt: "2099-10-01T09:15:00+00:00",
      url: photo, expires: "2099-10-03T19:12:00+00:00", caveats: [UNMASKED],
    }} />
  </div>
);

/** Stored text that reads as Markdown, shown through the sanitizing renderer in the reading face. */
export const Text = () => (
  <div style={frame}>
    <DocumentViewer inline today={today} data={{
      kind: "text", name: "Letter to the board.md", readAt: "2099-09-29T16:00:00+00:00", url: "", expires: "",
      text: "# Example Village\n\n## The fence at 123 Main St\n\nTo the board,\n\nThe fence between my unit and the common area leans after the storm. Please have it looked at.\n\nJane Doe",
      caveats: [UNMASKED, STORED],
    }} />
  </div>
);

/** A refused view: the server's words in the error tone, inside the dialog, which stays open. */
export const Error = () => (
  <div style={{ maxWidth: 880 }}>
    <DocumentViewer inline today={today}
      document={{ id: "pdf-7", name: "Example Village lease addendum.pdf", kind: "pdf", size: 2_200_000, readAt: "2099-09-30T18:38:00+00:00", note: "" }}
      error="Example Village lease addendum.pdf is no longer on disk. Run jason sync-catalog --requests, then view it again." />
  </div>
);
