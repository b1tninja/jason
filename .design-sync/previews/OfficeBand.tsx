import { OfficeBand } from "jason-ui";

// The office-view loader's shape (`GET /api/office-view`), made up: Oakview's offices, 2099 dates. `DueDate` reads today's
// date when none is passed, so the clock is pinned to a made-up day and the cells do not drift.
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
  type: "duty", office: "treasurer", key: "books", title: "Review the sample reconciliations", due, standing, urgency, basis: "law", screen: "people",
  text: `Review the sample reconciliations, due ${due}`,
});

const BANDS = {
  waitingOnOffice: [
    { type: "letter", office: "treasurer", kind: "Sample notice", approver: "the treasurer", count: 2, screen: "approvals", text: "2 Sample notices waiting for the treasurer" },
    { type: "board-item", office: "treasurer", id: "item-1", title: "A sample matter", status: "proposed", due: null, shared: true, screen: "actions", text: "Board item: A sample matter" },
  ],
  signedWaiting: [] as any[],
  personSteps: [] as any[],
  needsAttention: [duty("2099-10-02", "LEGAL", "overdue")],
  comingUp: [duty("2099-11-05", "coming up", "upcoming")],
  work: [{ type: "run", office: "treasurer", id: "run-1", definition: "example-cycle", label: "Example cycle 2099", step: "example-cycle.2", stepTitle: "Approve the sample", due: "2099-10-23", screen: "", text: "Example cycle 2099: Approve the sample" }],
};

function data(over: any = {}): any {
  const bands = { ...BANDS, ...(over.bands ?? {}) };
  return {
    found: true, asOf: "2099-10-09", office: "", reading: ["secretary"], title: "my offices", ownOffice: true, vacant: false, offices: OFFICES, mine: ["secretary"],
    bands, counts: Object.fromEntries(Object.entries(bands).map(([k, v]) => [k, (v as any[]).length])), bandErrors: {}, notComposed: [], caveats: [], ...over, ...(over.bands ? { bands } : {}),
  };
}

/** Waiting on the viewer's own office: a notice with its count and a shared board item, headed "Waiting on you". */
export const WaitingOnYou = () => <div style={{ maxWidth: 820 }}><OfficeBand band="waitingOnOffice" data={data()} /></div>;

/** Another office's page: the heading names that office and says "for the treasurer", never "you". */
export const AnotherOffice = () => (
  <div style={{ maxWidth: 820 }}><OfficeBand band="needsAttention" data={data({ office: "treasurer", ownOffice: false })} /></div>
);

/** The steps waiting on a person, with the note that says the lead time and open-a-while threshold are proposals the board has not adopted. */
export const PersonSteps = () => (
  <div style={{ maxWidth: 820 }}>
    <OfficeBand band="personSteps" data={data({
      bands: { personSteps: [
        { type: "person-step", band: "legal", urgency: "LEGAL", due: "2099-10-12", days: 3, holder: "the secretary", forOffice: true, definition: "example-cycle", id: "run-1", text: "Example cycle 2099: send the second notice" },
        { type: "person-step", band: "late", urgency: "OVERDUE", due: "2099-10-05", days: -4, holder: "the treasurer", forOffice: false, definition: "example-cycle", id: "run-2", text: "Bill attach, Oct: approve the attachments" },
        { type: "person-step", band: "stale", urgency: "open a while", due: null, days: null, holder: "the manager", forOffice: true, definition: "example-cycle", id: "run-3", text: "Sample request: decide" },
      ] },
      stepNumbers: { leadDays: 7, afterHours: 168, escalateAfterHours: 336, adopted: false, note: "proposals the board has not adopted" },
    })} />
  </div>
);

/** An empty band says so, so its absence is not read as a failure to load. */
export const EmptyBand = () => <div style={{ maxWidth: 820 }}><OfficeBand band="signedWaiting" data={data()} /></div>;

/** A band whose loader failed says why, in a warning notice, instead of showing nothing. */
export const BandCouldNotBeRead = () => (
  <div style={{ maxWidth: 820 }}><OfficeBand band="comingUp" data={data({ bands: { comingUp: [] }, bandErrors: { comingUp: "the duties register could not be read (sample error)" } })} /></div>
);

/** More rows than the loader sent, and the viewer's own work band linking to all their runs. */
export const MoreThanShown = () => (
  <div style={{ maxWidth: 820 }}>
    <OfficeBand band="work" data={data({ counts: { work: 4 } })} />
  </div>
);
