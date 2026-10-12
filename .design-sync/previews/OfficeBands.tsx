import { OfficeBands } from "jason-ui";

// The office-view loader's shape (`GET /api/office-view`), made up: Oakview's offices, 2099 dates. The clock is pinned to a
// made-up day so `DueDate` does not drift.
const FIXED = "2099-10-09T12:00:00Z";
const RealDate = Date;
class PinnedDate extends RealDate {
  constructor(...a: any[]) { super(...((a.length ? a : [FIXED]) as [any])); }
  static now() { return new RealDate(FIXED).getTime(); }
}
(globalThis as any).Date = PinnedDate;

const OFFICES = ["president", "vice president", "secretary", "treasurer", "director", "manager"].map((office) => ({
  office, vacant: office === "vice president", holders: office === "vice president" ? 0 : 1,
}));

const duty = (due: string, urgency: string, standing: string) => ({
  type: "duty", office: "secretary", key: "books", title: "Review the sample reconciliations", due, standing, urgency, basis: "law", screen: "people",
  text: `Review the sample reconciliations, due ${due}`,
});

const FULL = {
  waitingOnOffice: [
    { type: "letter", office: "secretary", kind: "Sample notice", approver: "the secretary", count: 2, screen: "approvals", text: "2 Sample notices waiting for the secretary" },
    { type: "board-item", office: "secretary", id: "item-1", title: "A sample matter", status: "proposed", due: null, shared: true, screen: "actions", text: "Board item: A sample matter" },
  ],
  signedWaiting: [
    { type: "plan-to-apply", office: "secretary", id: "apr-1", screen: "approvals", waitingHours: 48, reminderDue: true, urgency: "2 days", text: "Sample tags: PayHOA tag changes, signed and waiting" },
  ],
  personSteps: [
    { type: "person-step", band: "legal", urgency: "LEGAL", due: "2099-10-12", days: 3, holder: "the secretary", forOffice: true, definition: "example-cycle", id: "run-1", text: "Example cycle 2099: send the second notice" },
  ],
  needsAttention: [duty("2099-10-02", "LEGAL", "overdue")],
  comingUp: [duty("2099-11-05", "coming up", "upcoming")],
  work: [
    { type: "run", office: "secretary", id: "run-1", definition: "example-cycle", label: "Example cycle 2099", step: "example-cycle.2", stepTitle: "Approve the sample", due: "2099-10-23", screen: "", text: "Example cycle 2099: Approve the sample" },
  ],
};

const base = {
  found: true, asOf: "2099-10-09", offices: OFFICES, notComposed: [] as any[], caveats: [] as string[], bandErrors: {} as any,
};

/** The secretary reading their own page: every band, and what the page could not compose with the caveat that a lens is not that person's session. */
export const OwnOffices = () => (
  <div style={{ maxWidth: 820 }}>
    <OfficeBands data={{
      ...base, office: "", reading: ["secretary"], title: "my offices", ownOffice: true, vacant: false, mine: ["secretary"], bands: FULL,
      counts: { waitingOnOffice: 2, signedWaiting: 1, personSteps: 1, needsAttention: 1, comingUp: 1, work: 1 },
      notComposed: [{ band: "waitingOnOffice", what: "Plans in the approvals engine", why: "No office is attached to a plan." }],
      caveats: ["Reading another office's page is a lens, not that person's session."],
    } as any} />
  </div>
);

/** A vacant office read by someone else: every band is empty and says so for the office, one band failed, and the page lists what it could not build. */
export const VacantOfficeEmpty = () => (
  <div style={{ maxWidth: 820 }}>
    <OfficeBands data={{
      ...base, office: "vice president", reading: ["vice president"], title: "the vice president", ownOffice: false, vacant: true, mine: ["secretary"],
      bands: { waitingOnOffice: [], signedWaiting: [], needsAttention: [], comingUp: [], work: [] },
      counts: { waitingOnOffice: 0, signedWaiting: 0, needsAttention: 0, comingUp: 0, work: 0 },
      bandErrors: { comingUp: "the duties register could not be read (sample error)" },
      notComposed: [{ band: "work", what: "Runs held by the office", why: "No one holds the office, so no run names it." }],
      caveats: ["A vacant office has no one to do what waits."],
    } as any} />
  </div>
);
