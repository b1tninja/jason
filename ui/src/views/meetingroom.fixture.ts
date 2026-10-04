/** A made-up meeting for the meeting room tests: five directors, four present, one recused on the contract item. */
import type { MeetingRoomData } from "../components/MeetingStage";

const FIVE = ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"];
/** A made-up Drive id: the second bid is a Doc in Drive, so the stage shows jason's copy of it (never a Google frame). */
export const DRIVE_BID = "1FakeBidDoc00002";

/** A made-up executive item: two matters, one with its 4935 subject and one without; titles only as the private view
 * gives them. The general words are all an open view may carry. */
export const EXEC_ITEM: MeetingRoomData["items"][number] = {
  id: "exec", kind: "exec", label: "Executive session", title: "Adjourn to executive session", facts: [], motion: "Move to adjourn to executive session to discuss member discipline (Civil Code 4935(a), (b)).",
  threshold: "majority", recused: [], allot: 2, packet: [], brief: null, session: "open session", matters: ["member discipline"], unnamed: 1,
  subjectNote: "name the 4935 subject first: 1 executive matter without a Civil Code 4935 subject",
  executiveMatters: [{ ref: "1", subject: "member_discipline", general: "member discipline", named: true }, { ref: "2", subject: "", general: "", named: false }],
};
/** The words of a made-up executive record: none may reach an open view. */
export const SECRET_TITLE = "Hearing, unit 7 (made-up owner Q. Sample)";
export const SECRET_MOTION = "Move to fine the owner of unit 7 $100.";

const NO_LIMIT = "No limit on record; the board sets it (CIV 4925(b)).";
/** The loader's rules for a made-up profile: the quorum and the vote quoted from made-up bylaws; the recusal question
 * not on file, as the loader says it. */
export const RULES: NonNullable<MeetingRoomData["rules"]> = {
  quorum: { onFile: true, source: "Bylaws 1.1", label: "Bylaws 1.1", words: "A majority of the Directors then in office shall constitute a quorum." },
  voteBasis: { onFile: false, label: "The vote rule is not on file; ask counsel. The room counts a majority of the directors present, a reading, not the rule." },
  interested: { onFile: false, counts: null, label: "Whether a recused director counts toward the quorum and among the directors present is not on file; ask counsel." },
  openForum: { onFile: false, minutes: 0, source: "", label: NO_LIMIT },
};

export function roomData(over: Partial<MeetingRoomData> = {}, room: Partial<MeetingRoomData["room"]> = {}): MeetingRoomData {
  return {
    found: true, date: "2026-10-21", today: "2026-10-03", directors: FIVE, quorum: 3, rules: RULES,
    items: [
      { id: "call", kind: "call", label: "Call to order", title: "Call to order and roll call", facts: [], motion: "", threshold: "majority", recused: [], allot: 3, packet: [], brief: null, session: "open session" },
      { id: "forum", kind: "forum", label: "Open forum", title: "Open forum", facts: [], motion: "", threshold: "majority", recused: [], allot: 15, packet: [], brief: null, session: "open session" },
      { id: "landscape", kind: "action", label: "Item 1 · Action", title: "Renew the landscape contract", facts: ["Two bids in the packet"], motion: "Move to approve the contract with Vendor A.", threshold: "majority", recused: ["H. Quinn"], allot: 15,
        packet: [{ id: "f1", name: "Vendor A bid.pdf", kind: "pdf" },
          { id: DRIVE_BID, name: "Vendor B bid", kind: "doc", url: `https://docs.google.com/document/d/${DRIVE_BID}/edit`, real: true }], brief: { question: "Which contract?", criteria: ["Cost"], options: [{ label: "A", values: ["$1"] }, { label: "B", values: ["$2"] }] }, session: "open session" },
      { id: "adjourn", kind: "adjourn", label: "Adjournment", title: "Adjourn", facts: [], motion: "", threshold: "majority", recused: [], allot: 1, packet: [], brief: null, session: "open session" },
    ],
    room: {
      date: "2026-10-21", directors: FIVE, current: 2, presenter: "jason", view: "host", mode: "co-host",
      attendance: { "D. Okafor": "present", "E. Lind": "present", "F. Marsh": "remote", "H. Quinn": "present" }, calledToOrder: "2026-10-21T18:30:00+00:00",
      openForum: { count: 0, limitMinutes: 0, limitSource: "", limitNote: NO_LIMIT }, motions: [], log: [{ at: "2026-10-21T18:30:00+00:00", title: "Called to order.", tone: "good", by: "S" }],
      executive: { active: false, startedAt: "", endedAt: "", note: "" }, polls: [], admitted: [], transcriptSuggestions: [{ at: "", text: "The gate sticks.", who: "a member", state: "suggested" }],
      adjournedAt: "", present: ["D. Okafor", "E. Lind", "F. Marsh", "H. Quinn"], quorum: 3, history: [], ...room,
    },
    decisions: [], plan: { found: true, count: 3 }, roster: { synced: "", count: 0, rows: [], note: "roster not synced" },
    offAgendaPaths: [{ path: "b", text: "b text" }, { path: "c", text: "c text" }, { path: "d1", text: "d1 text" }, { path: "d2", text: "d2 text" }, { path: "d3", text: "d3 text" }],
    zoom: { commands: { sync: "jason zoom" }, admitCommand: "", note: "the host acts in Zoom" }, commands: { minutesDraft: "jason board --minutes 2026-10-21" },
    minutesKey: "minutes/2026-10-21", notes: [], caveats: ["The chair runs the meeting."], ...over,
  };
}
