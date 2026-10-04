import { useEffect, useRef, useState } from "react";
import { HostPanel, type MeetingRoomData } from "jason-ui";

// The panel keeps its tab in state and takes no active-tab prop, so a cell for another tab clicks that tab once after
// mount, as the host would. Every write is behind a Confirm that renders its idle button only; onAction records nothing.

const FIVE = ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"];
const LANDSCAPE_MOTION = "Move to approve the contract with Greenway Landscape for 2027 at $1,850.00 a month, and authorize the president to sign.";

function room(over: Partial<MeetingRoomData> = {}, rec: Partial<MeetingRoomData["room"]> = {}): MeetingRoomData {
  return {
    found: true, date: "2026-10-21", today: "2026-10-21", directors: FIVE, quorum: 3,
    items: [
      { id: "call", kind: "call", label: "Call to order", title: "Call to order and roll call", facts: [], motion: "", threshold: "majority", recused: [], allot: 3, packet: [], brief: null, session: "open session" },
      { id: "forum", kind: "forum", label: "Open forum", title: "Member comment (CIV 4925)", facts: [], motion: "", threshold: "majority", recused: [], allot: 15, packet: [], brief: null, session: "open session" },
      { id: "minutes", kind: "consent", label: "Item 1 · Consent", title: "Approve the September minutes", facts: [], motion: "Move to approve the minutes of the 2026-09-16 open meeting as presented.", threshold: "majority", recused: [], allot: 3, packet: [{ id: "f-min", name: "Minutes 2026-09-16 (draft)", kind: "doc" }], brief: null, session: "open session" },
      { id: "landscape", kind: "action", label: "Item 2 · Action", title: "Renew the landscape contract", facts: ["Two bids in the packet", "The current contract ends 2026-12-31"], motion: LANDSCAPE_MOTION, threshold: "majority", recused: ["H. Quinn"], allot: 15,
        packet: [{ id: "f-bid-a", name: "Greenway Landscape bid 2027.pdf", kind: "pdf" }, { id: "f-bid-b", name: "Sierra Turf Care proposal.pdf", kind: "pdf" }],
        brief: { question: "Which landscape contract?", criteria: ["Monthly cost", "Term"], options: [{ label: "Renew with Greenway", values: ["$1,850.00", "two years"] }, { label: "Switch to Sierra Turf", values: ["$1,640.00", "one year"] }] }, session: "open session" },
      { id: "loan", kind: "discussion", label: "Item 3 · Discussion", title: "Reserve loan not restored", facts: ["$18,000.00 borrowed 2026-07-15 (CIV 5515)"], motion: "", threshold: "majority", recused: [], allot: 10, packet: [], brief: null, session: "open session" },
      { id: "exec", kind: "exec", label: "Executive session", title: "Adjourn to executive session", facts: [], motion: "", threshold: "majority", recused: [], allot: 10, packet: [], brief: null, session: "executive session", matters: ["a payment plan"] },
      { id: "adjourn", kind: "adjourn", label: "Adjournment", title: "Adjourn", facts: [], motion: "", threshold: "majority", recused: [], allot: 1, packet: [], brief: null, session: "open session" },
    ],
    room: {
      date: "2026-10-21", directors: FIVE, current: 3, presenter: "jason", view: "host", mode: "co-host",
      attendance: { "D. Okafor": "present", "E. Lind": "present", "F. Marsh": "remote", "H. Quinn": "present" }, calledToOrder: "2026-10-21T18:31:00",
      openForum: { count: 2, limitMinutes: 3 },
      motions: [{ id: "m1", itemId: "minutes", title: "Approve the September minutes", text: "Move to approve the minutes of the 2026-09-16 open meeting as presented.", mover: "F. Marsh", second: "E. Lind", recused: [], threshold: "majority",
        votes: { "D. Okafor": "aye", "E. Lind": "aye", "F. Marsh": "aye", "H. Quinn": "aye" }, result: "carried", decidedAt: "2026-10-21T18:52:00", movedAt: "2026-10-21T18:50:00",
        tally: { aye: 4, no: 0, abstain: 0, recused: 0, recusedNames: [], voters: ["D. Okafor", "E. Lind", "F. Marsh", "H. Quinn"], needs: 3, answered: true, state: "carries", line: "Carries, 4–0–0." } }],
      log: [
        { at: "2026-10-21T18:31:00", title: "Called to order.", tone: "good", by: "D. Okafor" },
        { at: "2026-10-21T18:32:00", title: "Attendance: D. Okafor present, E. Lind present, F. Marsh remote, H. Quinn present, G. Petrov absent. Quorum, 4 of 5." },
        { at: "2026-10-21T18:34:00", title: "Open forum: 2 speakers, 3 minutes each." },
        { at: "2026-10-21T18:50:00", title: "Motion on the floor: approve the September minutes. Moved by F. Marsh, seconded by E. Lind." },
        { at: "2026-10-21T18:52:00", title: "Carries, 4–0–0. The September minutes are approved.", tone: "good" },
        { at: "2026-10-21T18:53:00", title: "Opened: Renew the landscape contract. H. Quinn disclosed an interest and is recused.", tone: "warn" },
      ],
      executive: { active: false, startedAt: "", endedAt: "", note: "" }, polls: [], admitted: ["a member, unit 12"],
      transcriptSuggestions: [{ at: "2026-10-21T18:36:00", text: "The pool gate sticks in the evening; the latch needs adjusting.", who: "a member, unit 7", state: "suggested" }],
      adjournedAt: "", present: ["D. Okafor", "E. Lind", "F. Marsh", "H. Quinn"], quorum: 3, history: [], ...rec,
    },
    decisions: [], plan: { found: true, count: 4 }, roster: { synced: "2026-10-20", count: 48, rows: [{ name: "a member", unit: "unit 7" }], note: "" },
    offAgendaPaths: [
      { path: "b", text: "The board responds briefly, asks a question, or announces." },
      { path: "c", text: "The board asks the manager to report back or places it on a future agenda." },
      { path: "d1", text: "A majority finds an emergency." },
      { path: "d2", text: "Two-thirds find an immediate need that arose after posting." },
      { path: "d3", text: "It was on an agenda within 30 days and was continued." },
    ],
    zoom: { commands: { sync: "jason zoom --sync" }, admitCommand: "", note: "The host acts in Zoom; jason keeps the record here." },
    commands: { minutesDraft: "jason board --minutes 2026-10-21" }, minutesKey: "minutes/2026-10-21", notes: [], caveats: ["The chair runs the meeting."], ...over,
  };
}

const onTheFloor = room({}, {
  motions: [
    ...room().room.motions,
    { id: "m2", itemId: "landscape", title: "Renew the landscape contract", text: LANDSCAPE_MOTION, mover: "E. Lind", second: "F. Marsh", recused: ["H. Quinn"], threshold: "majority", votes: {}, result: "", decidedAt: "", movedAt: "2026-10-21T18:58:00",
      tally: { aye: 0, no: 0, abstain: 0, recused: 1, recusedNames: ["H. Quinn"], voters: [], needs: 2, answered: false, state: "open", line: "" } },
  ],
});

function OnTab({ tab, data }: { tab: string; data: MeetingRoomData }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const buttons = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []);
    buttons.find((b) => b.textContent === tab)?.click();
  }, [tab]);
  return (
    <div ref={ref} style={{ display: "flex" }}>
      <HostPanel room={data} onAction={async () => true} me="F. Marsh" legal="Juniper Court Homeowners Association" shown={{}} onShow={() => {}} />
    </div>
  );
}

/** Agenda: the run of the meeting with the current item in bold, a carried badge on the decided one, the stage and off-agenda buttons. */
export const Agenda = () => <OnTab tab="Agenda" data={room()} />;

/** Motion: the common-motion chips, the item's drafted text, mover and second (the recused director left out), and the recusal boxes. */
export const Motion = () => <OnTab tab="Motion" data={room()} />;

/** Roll call: attendance per director, the quorum badge, and the vote by name on the motion on the floor, the recused director noted. */
export const RollCall = () => <OnTab tab="Roll call" data={onTheFloor} />;

/** Minutes: the log as recorded, a transcript lead for the secretary with Add and Dismiss, and the draft-minutes command. */
export const Minutes = () => <OnTab tab="Minutes" data={room()} />;

/** Packet: the current item's files with their kind badges and a Show on stage link each. */
export const Packet = () => <OnTab tab="Packet" data={room()} />;

/** On a phone: the bottom sheet, open on Agenda; the handle ("Hide the panel") collapses it to the handle and the tab row,
 * and a tab opens it. The frame's transform holds the fixed sheet inside a 375px cell. */
export const Sheet = () => {
  const [open, setOpen] = useState(true);
  return (
    <div style={{ position: "relative", width: 375, height: 560, transform: "translateZ(0)", overflow: "hidden" }}>
      <HostPanel sheet open={open} onOpenChange={setOpen} room={room()} onAction={async () => true} me="F. Marsh" legal="Juniper Court Homeowners Association" shown={{}} onShow={() => {}} />
    </div>
  );
};

/** No name entered: the warn notice under the tabs; every entry waits for who is recording. */
export const NoRecorder = () => {
  return (
    <div style={{ display: "flex" }}>
      <HostPanel room={room()} onAction={async () => true} me="" />
    </div>
  );
};
