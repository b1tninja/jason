import { MeetingStage, type PacketCopy, type StageContent } from "jason-ui";

// The stage is sized by its container (cqw units); each cell gives it a fixed width so the type scales the same way everywhere.
const Frame = ({ content, item, caption, progress, live = true, audience, packetCopy }: { content: StageContent; item: { label: string; title: string }; caption: string; progress: number; live?: boolean; audience?: "board" | "owner"; packetCopy?: PacketCopy }) => (
  <div style={{ width: 720 }}>
    <MeetingStage wordmark="Juniper Court HOA" legal="Juniper Court Homeowners Association" item={item} content={content} caption={caption} progress={progress} live={live} time="6:47 pm"
      audience={audience} packetCopy={packetCopy} />
  </div>
);

// A packet file in Drive, and jason's copy of it as the server answers it: static, so nothing is fetched. The opened view
// is an image standing in for the copy's PDF, which the stage shows inline from jason's document link.
const BID = "1ExampleBidDoc01";
const bidFile = { id: BID, name: "Greenway Landscape bid 2027", kind: "doc", url: `https://docs.google.com/document/d/${BID}/edit`, real: true };
const bidPage = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='850' height='420'><rect width='850' height='420' fill='#fff'/>"
  + "<text x='40' y='56' font-family='Georgia' font-size='26' fill='#222'>Greenway Landscape: proposal for 2027</text>"
  + [96, 124, 152, 180, 208, 236, 264, 292, 320].map((y) => `<rect x='40' y='${y}' width='${y % 56 ? 760 : 520}' height='8' fill='#d6d9de'/>`).join("")
  + "</svg>",
);
const bidAnswer = {
  found: true, address: `drive:${BID}`, label: bidFile.name, kind: "drive" as const, sources: [], changed: false, changedNote: "",
  link: bidFile.url, refresh: [], caveats: [], note: "",
  documents: [{ id: "pdf", name: `${bidFile.name}.pdf`, kind: "pdf" as const, size: 120_000, readAt: "2099-10-03T15:00:00+00:00", note: "" }],
};

/** Facts on an action item: jason's caption under the content, the progress bar part way. */
export const Facts = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.45} caption="jason: two bids are in the packet; the current contract ends 2026-12-31."
    content={{ kind: "facts", facts: ["Greenway Landscape, $1,850.00 a month, two years", "Sierra Turf Care, $1,640.00 a month, one year", "The current contract ends 2026-12-31", "H. Quinn disclosed an interest and does not vote"] }} />
);

/** A motion on the floor: the kicker, the text, the byline. */
export const Motion = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.5} caption="The chair calls the roll."
    content={{ kind: "motion", text: "Move to approve the contract with Greenway Landscape for 2027 at $1,850.00 a month, and authorize the president to sign.", mover: "E. Lind", second: "F. Marsh" }} />
);

/** The same motion decided: the result line in the accent. */
export const MotionCarried = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.55} caption="Recorded in the minutes."
    content={{ kind: "motion", text: "Move to approve the contract with Greenway Landscape for 2027 at $1,850.00 a month, and authorize the president to sign.", mover: "E. Lind", second: "F. Marsh", result: "Carries, 3–1–0; H. Quinn recused" }} />
);

/** Attendance at the call to order: the roster in two columns, a dot per present director, the quorum line. */
export const Attendance = () => (
  <Frame item={{ label: "Call to order", title: "Roll call and quorum" }} progress={0.05} caption="jason: four of five directors present; a quorum is three."
    content={{ kind: "attendance", rows: [{ name: "D. Okafor", role: "president", present: true }, { name: "E. Lind", role: "treasurer", present: true }, { name: "F. Marsh", role: "secretary", present: true }, { name: "G. Petrov", present: false }, { name: "H. Quinn", present: true }], quorum: "Quorum present: 4 of 5 directors." }} />
);

/** Open forum: the speaker clock and who has the floor. */
export const Countdown = () => (
  <Frame item={{ label: "Open forum (CIV 4925)", title: "Member comment" }} progress={0.2} caption="Three minutes a speaker; the board listens and may respond briefly (CIV 4930(b))."
    content={{ kind: "countdown", seconds: 127, speaker: "Speaker 2 of 4 · a member, unit 7" }} />
);

/** Executive session: what members see while the board meets without them. */
export const Executive = () => (
  <Frame item={{ label: "Executive session (CIV 4935)", title: "The board is in executive session" }} progress={0.85} caption=""
    content={{ kind: "executive", note: "Member discipline and a payment plan. The open meeting resumes afterwards." }} />
);

/** The options on stage: the brief's lettered cards in three columns on the hero surface, the criteria in order. */
export const Options = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.4} caption="jason lays out the options; the board chooses."
    content={{ kind: "options", decision: { question: "Which landscape bid, and for how long?", criteria: ["Monthly cost", "Term", "Insurance on file"],
      options: [{ label: "Greenway, two years", values: ["$1,850.00", "24 months", "yes"] }, { label: "Sierra Turf, one year", values: ["$1,640.00", "12 months", "pending"] }, { label: "Rebid in spring", values: ["—", "month to month", "—"] }] } }} />
);

/** A sample packet file: no real reference, so the stage shows the hatched stand-in instead of a frame. */
export const PacketSample = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.42} caption="Page 2 of the Greenway bid."
    content={{ kind: "packet", file: { id: "f1", name: "Greenway Landscape bid 2027.pdf", kind: "pdf" } }} />
);

/** The board's stage with a packet file up: jason's copy, opened as one logged view and shown inline; never a Google frame. */
export const PacketCopyForBoard = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.42} caption="The Greenway bid, from jason's copy."
    content={{ kind: "packet", file: bidFile }}
    packetCopy={{ signedIn: true, evidence: bidAnswer, view: { kind: "image", name: `${bidFile.name}, page 2`, readAt: "2099-10-03T15:00:00+00:00", url: bidPage, expires: "", caveats: [] } }} />
);

/** No copy yet: the file's preview card on the stage, with Read from Drive and Open in Google for the host. */
export const PacketNoCopy = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.42} caption="jason keeps no copy of the bid yet."
    content={{ kind: "packet", file: bidFile }} packetCopy={{ signedIn: true, evidence: { ...bidAnswer, documents: [] } }} />
);

/** What members see while the host shows a packet file: a card that names it, never the file. */
export const PacketForMembers = () => (
  <Frame item={{ label: "Item 3 · Action", title: "Renew the landscape contract" }} progress={0.42} caption="The board discusses the bids."
    content={{ kind: "packet", file: bidFile }} audience="owner" />
);

/** Adjourned: the closing line and the minutes deadline, the bar full. */
export const Adjourned = () => (
  <Frame item={{ label: "Adjournment", title: "Thank you for attending" }} progress={1} caption="" live={false}
    content={{ kind: "adjourned", at: "8:12 pm" }} />
);

/** A topic not on the posted agenda: the warn box with what the board may do (CIV 4930). */
export const OffAgenda = () => (
  <Frame item={{ label: "Open forum (CIV 4925)", title: "The pool gate" }} progress={0.22} caption="The chair may place it on a future agenda."
    content={{ kind: "off-agenda" }} />
);
