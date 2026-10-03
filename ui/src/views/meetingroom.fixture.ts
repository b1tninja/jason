/** A made-up meeting for the meeting room tests: five directors, four present, one recused on the contract item. */
import type { MeetingRoomData } from "../components/MeetingStage";

const FIVE = ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"];

export function roomData(over: Partial<MeetingRoomData> = {}, room: Partial<MeetingRoomData["room"]> = {}): MeetingRoomData {
  return {
    found: true, date: "2026-10-21", today: "2026-10-03", directors: FIVE, quorum: 3,
    items: [
      { id: "call", kind: "call", label: "Call to order", title: "Call to order and roll call", facts: [], motion: "", threshold: "majority", recused: [], allot: 3, packet: [], brief: null, session: "open session" },
      { id: "forum", kind: "forum", label: "Open forum", title: "Open forum", facts: [], motion: "", threshold: "majority", recused: [], allot: 15, packet: [], brief: null, session: "open session" },
      { id: "landscape", kind: "action", label: "Item 1 · Action", title: "Renew the landscape contract", facts: ["Two bids in the packet"], motion: "Move to approve the contract with Vendor A.", threshold: "majority", recused: ["H. Quinn"], allot: 15,
        packet: [{ id: "f1", name: "Vendor A bid.pdf", kind: "pdf" }], brief: { question: "Which contract?", criteria: ["Cost"], options: [{ label: "A", values: ["$1"] }, { label: "B", values: ["$2"] }] }, session: "open session" },
      { id: "adjourn", kind: "adjourn", label: "Adjournment", title: "Adjourn", facts: [], motion: "", threshold: "majority", recused: [], allot: 1, packet: [], brief: null, session: "open session" },
    ],
    room: {
      date: "2026-10-21", directors: FIVE, current: 2, presenter: "jason", view: "host", mode: "co-host",
      attendance: { "D. Okafor": "present", "E. Lind": "present", "F. Marsh": "remote", "H. Quinn": "present" }, calledToOrder: "2026-10-21T18:30:00+00:00",
      openForum: { count: 0, limitMinutes: 3 }, motions: [], log: [{ at: "2026-10-21T18:30:00+00:00", title: "Called to order.", tone: "good", by: "S" }],
      executive: { active: false, startedAt: "", endedAt: "", note: "" }, polls: [], admitted: [], transcriptSuggestions: [{ at: "", text: "The gate sticks.", who: "a member", state: "suggested" }],
      adjournedAt: "", present: ["D. Okafor", "E. Lind", "F. Marsh", "H. Quinn"], quorum: 3, history: [], ...room,
    },
    decisions: [], plan: { found: true, count: 3 }, roster: { synced: "", count: 0, rows: [], note: "roster not synced" },
    offAgendaPaths: [{ path: "b", text: "b text" }, { path: "c", text: "c text" }, { path: "d1", text: "d1 text" }, { path: "d2", text: "d2 text" }, { path: "d3", text: "d3 text" }],
    zoom: { commands: { sync: "jason zoom" }, admitCommand: "", note: "the host acts in Zoom" }, commands: { minutesDraft: "jason board --minutes 2026-10-21" },
    minutesKey: "minutes/2026-10-21", notes: [], caveats: ["The chair runs the meeting."], ...over,
  };
}
