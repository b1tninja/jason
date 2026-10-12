import { OfficeToday } from "jason-ui";

// OfficeToday reads its lens from the URL's hash (`#/digest?as=treasurer`) and fetches `GET /api/office-view?office=`. The
// preview sets the hash once and installs a module-scope fetch stub with the loader's shape; the data is made up (Oakview,
// 2099 dates). Every cell on a page shares one hash, so the preview has one lens: the secretary reading the treasurer's page.
const FIXED = "2099-10-09T12:00:00Z";
const RealDate = Date;
class PinnedDate extends RealDate {
  constructor(...a: any[]) { super(...((a.length ? a : [FIXED]) as [any])); }
  static now() { return new RealDate(FIXED).getTime(); }
}
(globalThis as any).Date = PinnedDate;

try { window.location.hash = "#/digest?as=treasurer"; } catch { /* a preview without a hash still renders */ }

const OFFICES = ["president", "vice president", "secretary", "treasurer", "director", "manager"].map((office) => ({
  office, vacant: office === "vice president", holders: office === "vice president" ? 0 : 1,
}));

const duty = (due: string, urgency: string, standing: string) => ({
  type: "duty", office: "treasurer", key: "books", title: "Review the sample reconciliations", due, standing, urgency, basis: "law", screen: "people",
  text: `Review the sample reconciliations, due ${due}`,
});

const VIEW = {
  found: true, asOf: "2099-10-09", office: "treasurer", reading: ["treasurer"], title: "the treasurer", ownOffice: false, vacant: false,
  offices: OFFICES, mine: ["secretary"],
  bands: {
    waitingOnOffice: [
      { type: "letter", office: "treasurer", kind: "Sample notice", approver: "the treasurer", count: 2, screen: "approvals", text: "2 Sample notices waiting for the treasurer" },
      { type: "board-item", office: "treasurer", id: "item-1", title: "A sample matter", status: "proposed", due: null, shared: true, screen: "actions", text: "Board item: A sample matter" },
    ],
    signedWaiting: [
      { type: "plan-to-apply", office: "treasurer", id: "apr-1", screen: "approvals", waitingHours: 48, reminderDue: true, urgency: "2 days", text: "Sample tags: PayHOA tag changes, signed and waiting" },
    ],
    personSteps: [
      { type: "person-step", band: "legal", urgency: "LEGAL", due: "2099-10-12", days: 3, holder: "the treasurer", forOffice: true, definition: "example-cycle", id: "run-1", text: "Example cycle 2099: send the second notice" },
      { type: "person-step", band: "stale", urgency: "open a while", due: null, days: null, holder: "the treasurer", forOffice: true, definition: "example-cycle", id: "run-3", text: "Sample request: decide" },
    ],
    needsAttention: [duty("2099-10-02", "LEGAL", "overdue")],
    comingUp: [duty("2099-11-05", "coming up", "upcoming")],
    work: [{ type: "run", office: "treasurer", id: "run-2", definition: "example-cycle", label: "Example cycle 2099", step: "example-cycle.2", stepTitle: "Approve the sample", due: "2099-10-23", screen: "", text: "Example cycle 2099: Approve the sample" }],
  },
  counts: { waitingOnOffice: 2, signedWaiting: 1, personSteps: 2, needsAttention: 1, comingUp: 1, work: 1 },
  stepBands: { legal: 1, stale: 1 },
  stepNumbers: { leadDays: 7, afterHours: 168, escalateAfterHours: 336, adopted: false, note: "proposals the board has not adopted" },
  bandErrors: {},
  notComposed: [{ band: "waitingOnOffice", what: "Plans in the approvals engine", why: "No office is attached to a plan." }],
  caveats: ["Reading another office's page is a lens, not that person's session."],
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: any, init?: any) => {
  const url = String(typeof input === "string" ? input : input?.url ?? input);
  if (url.startsWith("/api/session")) return json(200, {});
  if (url.startsWith("/api/office-view")) return json(200, VIEW);
  return realFetch ? realFetch(input, init) : json(404, { error: "not here" });
}) as typeof fetch;

/** The Today page's office section: the lens, the "Reading as the treasurer" banner, the counts line, and the bands, over the loader. */
export const ReadingAnotherOffice = () => <div style={{ maxWidth: 900 }}><OfficeToday /></div>;
