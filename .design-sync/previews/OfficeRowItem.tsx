import { OfficeRowItem } from "jason-ui";

// The rows are the office-view loader's (`GET /api/office-view`): an office's counts, kinds, and titles of items, never a name.
// `DueDate` reads today's date when none is passed, so the clock is pinned to a made-up day and the cells do not drift.
const FIXED = "2099-10-09T12:00:00Z";
const RealDate = Date;
class PinnedDate extends RealDate {
  constructor(...a: any[]) { super(...((a.length ? a : [FIXED]) as [any])); }
  static now() { return new RealDate(FIXED).getTime(); }
}
(globalThis as any).Date = PinnedDate;

const List = ({ rows }: { rows: any[] }) => (
  <ul className="office-rows" style={{ maxWidth: 760 }}>
    {rows.map((r, i) => <OfficeRowItem key={i} row={r} />)}
  </ul>
);

/** A notice waiting on the office: the count and kind in words, the urgency as a pill, and a link to the screen that owns it. */
export const NoticeWaiting = () => (
  <List rows={[{ type: "letter", office: "treasurer", kind: "Sample notice", approver: "the treasurer", count: 2, urgency: "overdue", screen: "approvals", text: "2 Sample notices waiting for the treasurer" }]} />
);

/** A board item and a duty: the board's own item is marked, and a duty carries the basis it rests on and its date. */
export const BoardItemAndDuty = () => (
  <List rows={[
    { type: "board-item", office: "treasurer", id: "item-1", title: "A sample matter", priority: "normal", status: "proposed", due: null, shared: true, screen: "actions", text: "Board item: A sample matter" },
    { type: "duty", office: "secretary", key: "books", title: "Review the sample reconciliations", due: "2099-10-20", standing: "upcoming", urgency: "due soon", basis: "law", screen: "people", text: "Review the sample reconciliations, due 2099-10-20" },
    { type: "duty", office: "manager", key: "walk", title: "Walk the sample common area", due: "2099-12-05", standing: "upcoming", urgency: "coming up", basis: "documents", backup: true, screen: "people", text: "Walk the sample common area, due 2099-12-05" },
  ]} />
);

/** A run in the office's work: it links to the run itself, not to a screen. */
export const RunRow = () => (
  <List rows={[{ type: "run", office: "treasurer", id: "run-1", definition: "example-cycle", label: "Example cycle 2099", step: "example-cycle.2", stepTitle: "Approve the sample", due: "2099-10-23", screen: "", text: "Example cycle 2099: Approve the sample" }]} />
);

/** The person-step bands in the digest's order: a legal clock, late, needs a date, due soon, open a while, and a step shown only because no one holds its office. */
export const PersonStepBands = () => (
  <List rows={[
    { type: "person-step", band: "legal", urgency: "LEGAL", due: "2099-10-12", days: 3, holder: "the secretary", forOffice: true, definition: "example-cycle", id: "run-1", text: "Example cycle 2099: send the second notice" },
    { type: "person-step", band: "late", urgency: "OVERDUE", due: "2099-10-05", days: -4, holder: "the treasurer", forOffice: true, definition: "example-cycle", id: "run-2", text: "Bill attach, Oct: approve the attachments" },
    { type: "person-step", band: "date", urgency: "needs a date", due: null, days: null, holder: "the manager", forOffice: true, definition: "example-cycle", id: "run-3", text: "Annual sample test: set the report date" },
    { type: "person-step", band: "soon", urgency: "due soon", due: "2099-10-14", days: 5, holder: "the manager", forOffice: false, escalatedTo: "the whole board", definition: "example-cycle", id: "run-4", text: "Hearing H-7: record the reply" },
    { type: "person-step", band: "stale", urgency: "open a while", due: null, days: null, holder: "the president", forOffice: true, escalatedTo: "secretary", definition: "example-cycle", id: "run-5", text: "Sample request: decide" },
    { type: "person-step", band: "quiet", urgency: "no one holds the vice president's office", holder: "the vice president", forOffice: false, definition: "example-cycle", id: "run-6", text: "Sample vote: second the motion" },
  ]} />
);

/** A plan signed and waiting to be applied (the signed-waiting band): why it waits, in words, beside the plan. */
export const PlanToApply = () => (
  <List rows={[
    { type: "plan-to-apply", office: "manager", id: "apr-1", urgency: "2 days", screen: "approvals", needsSecond: false, waitingHours: 48, reminderDue: true, note: "Signed 2 days ago by A. Manager.", text: "Sample tags: PayHOA tag changes, signed and waiting" },
    { type: "plan-to-apply", office: "manager", id: "apr-2", screen: "approvals", stale: true, terminalOnly: true, pausing: true, waitingHours: 190, note: "Older than this kind allows.", text: "Sample letters: mailing plan, signed and waiting" },
  ]} />
);
