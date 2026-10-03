import { MeetingStage, type StageContent } from "jason-ui";

// The stage is sized by its container (cqw units); each cell gives it a fixed width so the type scales the same way everywhere.
const Frame = ({ content, item, caption, progress, live = true }: { content: StageContent; item: { label: string; title: string }; caption: string; progress: number; live?: boolean }) => (
  <div style={{ width: 720 }}>
    <MeetingStage wordmark="Juniper Court HOA" legal="Juniper Court Homeowners Association" item={item} content={content} caption={caption} progress={progress} live={live} time="6:47 pm" />
  </div>
);

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
