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
    form: "Owner information 2099", unit: "12", submitted: "2099-09-28", status: "Pending",
    questions: [
      { question: "Owner's full name", answer: "Jane Doe", kind: "text" },
      { question: "Mailing address", answer: "123 Main St\nExample City, CA 90000", kind: "text" },
      { question: "Do you rent the unit to a tenant?", answer: "No", kind: "choice" },
      { question: "Date you bought the unit", answer: "2091-04-15", kind: "date" },
      { question: "Second phone", answer: "", kind: "text" },
      { question: "Anything else the board should know?", answer: "", kind: "other" },
    ],
  },
  caveats: [UNMASKED, STORED],
};

/** A PayHOA form submission as the owner filled it in: each question in order, a blank shown as "(no answer)", Print. */
export const Submission = () => (
  <div style={frame}><DocumentViewer inline today={today} data={submission} position={{ index: 0, count: 3 }} onGo={() => {}} /></div>
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
