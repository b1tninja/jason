import { ClockStrip } from "jason-ui";

// A run's deadlines, as the work loader sends them (`_clock_row`). Made-up: Oakview's sample cycle, 2099 dates, plainly fake
// statute text ("EX 123.4"). `today` is passed so the due-date distances do not drift.
const TODAY = new Date("2099-10-09T12:00:00Z");
const BASIS = {
  law: { basis: "law", basisLabel: "LEGAL", legal: true, proposed: false },
  documents: { basis: "documents", basisLabel: "DOCUMENTS", legal: false, proposed: false },
  proposed: { basis: "proposed policy", basisLabel: "PROPOSED", legal: false, proposed: true },
  person: { basis: "person", basisLabel: "PERSON", legal: false, proposed: false },
};

const LAW = {
  citation: "EX 123.4", section: "EX 123.4(a)", digest: "d0c5a1", source: "authorities shelf: sample", note: "version in force on 2099-10-09",
  caveats: [] as string[], versions: [] as { digest: string; words: string; label: string }[], undecided: false, missing: "",
  readingLabel: "jason's reading, not the provision", restatement: "jason's consolidated text is not an official restatement.",
  words: "The association shall send a second notice to each member not later than 30 days before the answer-by date. (Sample text, not a statute.)",
  reading: "Resend the notice at least 30 days before answers are due",
};

const clock = (over: any): any => ({ key: "k", step: "", label: "", due: null, status: "upcoming", days: null, cite: "", past: false, stepTitle: "", scope: "run", ...over });

const ANSWERS = clock({ key: "oi.read-forms", step: "oi.read-forms", label: "Answers by", due: "2099-10-23", days: 14, stepTitle: "Read the returned forms", scope: "step", ...BASIS.documents });
const IN_PAYHOA = clock({ key: "run.0", label: "In PayHOA by", due: "2099-11-01", days: 23, ...BASIS.documents });
const RESEND = clock({ key: "oi.resend", step: "oi.resend", label: "Resend by", due: "2099-10-30", days: 21, cite: "EX 123.4", stepTitle: "Resend to owners who have not answered", scope: "step", law: LAW, ...BASIS.law });

const wide = { maxWidth: 780 } as const;

/** A run's dates: a step's date and the whole run's date, each with whose date it is (a documents basis), and a legal clock that recites the statute's words before jason's labeled reading. */
export const RunDeadlines = () => <div style={wide}><ClockStrip today={TODAY} clocks={[ANSWERS, IN_PAYHOA, RESEND]} /></div>;

/** A run past a legal date: the clock is flagged in the law's words, with the days gone by, and the clock that was met is shown settled. */
export const PastALegalDate = () => (
  <div style={wide}>
    <ClockStrip today={TODAY} clocks={[
      clock({ key: "el.inspector", step: "el.inspector", label: "Inspector appointed by", due: "2099-10-02", status: "overdue", days: -7, cite: "EX 321.2", past: true, stepTitle: "Appoint the inspector", scope: "step", ...BASIS.law,
        law: { ...LAW, citation: "EX 321.2", section: "EX 321.2", words: "An inspector of elections shall be appointed before the ballots are mailed. (Sample text, not a statute.)", reading: "" } }),
      clock({ key: "el.notice", step: "el.notice", label: "Notice sent by", due: "2099-09-20", status: "satisfied", days: -19, stepTitle: "Send the notice", scope: "step", ...BASIS.documents }),
    ]} />
  </div>
);

/** A proposed number is a plain pill, never a stamp, and a clock with no date yet says "no date" in the card. */
export const ProposedAndUndated = () => (
  <div style={wide}>
    <ClockStrip today={TODAY} clocks={[
      clock({ key: "bf.report", step: "bf.report", label: "Vendor's report due", due: "2099-12-01", days: 53, stepTitle: "The vendor's report", scope: "step", ...BASIS.proposed }),
      clock({ key: "bf.walk", step: "bf.walk", label: "Walk the property", due: null, status: "undated", stepTitle: "Walk the property", scope: "step", ...BASIS.person }),
    ]} />
  </div>
);

/** A step that keeps one clock for each of its items is one card: how many items, how many are late, and the nearest date. */
export const PerItemClocks = () => (
  <div style={wide}>
    <ClockStrip today={TODAY} clocks={Array.from({ length: 6 }, (_, i) => {
      const days = i < 2 ? 2 : i === 2 ? -3 : 5;
      return clock({ key: `ri.decide[req:0${i + 1}]`, step: "ri.decide", item: `req:0${i + 1}`, label: "Reply to the request", due: `2099-10-${String(9 + days).padStart(2, "0")}`,
        status: i < 2 ? "satisfied" : days < 0 ? "overdue" : "upcoming", days, past: days < 0, stepTitle: "Decide each request", scope: "step", ...BASIS.person });
    })} />
  </div>
);

/** A run with no dates yet says so. */
export const NoDates = () => <div style={wide}><ClockStrip today={TODAY} clocks={[]} /></div>;
