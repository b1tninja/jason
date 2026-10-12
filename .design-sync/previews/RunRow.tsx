import type { ReactNode } from "react";
import { RunRow } from "jason-ui";

// Made-up runs for "Oakview", with 2099 dates. `today` is pinned so "in 5 days" does not drift with the real clock.
const TODAY = new Date("2099-10-09T12:00:00Z");

const BASIS = {
  law: { basis: "law", basisLabel: "LEGAL", legal: true, proposed: false },
  documents: { basis: "documents", basisLabel: "DOCUMENTS", legal: false, proposed: false },
  person: { basis: "person", basisLabel: "PERSON", legal: false, proposed: false },
};
const due = (date: string, basis: keyof typeof BASIS, days: number, over: object = {}) => ({
  date, label: "", cite: "", status: days < 0 ? "overdue" : "upcoming", days, step: "", ...BASIS[basis], ...over,
});
const row = (over: object): any => ({
  id: "item-1", definition: "owner-info-cycle", definitionTitle: "Owner information cycle", family: "members", subjectKind: "campaign",
  label: "Owner information 2099", state: "active", group: "yours", mine: true,
  current: { id: "oi.read-forms", title: "Read the returned forms", n: 6, of: 12, kind: "person", state: "needs a person", role: "manager" },
  owner: "manager", waitingOn: { kind: "office", word: "the manager", role: "manager", detail: "" },
  due: null, pastLaw: false, age: { days: 8, opened: "2099-10-01", idleDays: 1, updated: "2099-10-08T08:12:00Z" },
  paused: false, pausedReason: "", ...over,
});

const List = ({ children }: { children: ReactNode }) => <ul className="work-rows" style={{ maxWidth: 900 }}>{children}</ul>;

/** The canonical row: it is the viewer's move, with a date a document set. The whole width links to the run. */
export const YourMove = () => (
  <List>
    <RunRow today={TODAY} row={row({ due: due("2099-10-23", "documents", 14, { label: "Answers by" }) })} />
  </List>
);

/** One row for each group the list sorts runs into: yours, waiting on a person, waiting on a clock, and the board's. */
export const EachGroup = () => (
  <List>
    <RunRow today={TODAY} row={row({
      id: "item-2", definition: "bill-attach", definitionTitle: "Bill attachment", family: "money", label: "Bill attach: Example Electric, Oct",
      current: { id: "ba.approve", title: "Approve the attachments", n: 4, of: 7, kind: "person", state: "needs a person", role: "treasurer" },
      waitingOn: { kind: "office", word: "the treasurer", role: "treasurer", detail: "" }, due: due("2099-10-14", "person", 5),
    })} />
    <RunRow today={TODAY} row={row({
      id: "item-3", definition: "hearing", definitionTitle: "Hearing", label: "Hearing H-7", group: "others", mine: false,
      current: { id: "hr.reply", title: "The member's reply", n: 6, of: 9, kind: "wait", state: "waiting", role: "secretary" },
      waitingOn: { kind: "arrival", word: "an arrival", role: "secretary", detail: "the member's written reply" }, due: due("2099-11-02", "documents", 24),
    })} />
    <RunRow today={TODAY} row={row({
      id: "item-4", definition: "backflow-annual", definitionTitle: "Annual backflow test", family: "life-safety", label: "Annual backflow test", group: "clock", mine: false,
      current: { id: "bf.report", title: "The vendor's report", n: 3, of: 6, kind: "wait", state: "waiting", role: "manager" },
      waitingOn: { kind: "clock", word: "a clock", role: "manager", detail: "report due" }, due: due("2099-12-01", "documents", 53),
    })} />
    <RunRow today={TODAY} row={row({
      id: "item-5", definition: "rule-change", definitionTitle: "Rule change", family: "governance", label: "Rule change: quiet hours", group: "board", mine: false,
      current: { id: "rc.decide", title: "The board decides", n: 13, of: 18, kind: "decision", state: "needs a person", role: "secretary" },
      waitingOn: { kind: "board", word: "the board; the secretary records", role: "secretary", detail: "" }, due: due("2099-11-14", "law", 36, { cite: "EX 321.1" }),
    })} />
  </List>
);

/** Past a legal date: the row says so in words with a glyph, and the date carries the law's citation. */
export const PastALegalDate = () => (
  <List>
    <RunRow today={TODAY} row={row({
      id: "item-6", definition: "election", definitionTitle: "Election", family: "governance", label: "Election 2099", group: "board", mine: false, pastLaw: true,
      current: { id: "el.inspector", title: "Appoint the inspector", n: 4, of: 14, kind: "decision", state: "needs a person", role: "secretary" },
      waitingOn: { kind: "board", word: "the board; the secretary records", role: "secretary", detail: "" }, due: due("2099-10-02", "law", -7, { cite: "EX 321.2" }),
    })} />
  </List>
);

/** A run's most urgent person step shows as a nudge mark under the date: its band, how far off, which step, how many items remain. */
export const WithNudge = () => (
  <List>
    <RunRow today={TODAY} row={row({
      due: due("2099-10-23", "documents", 14, { label: "Answers by" }),
      nudge: { band: "soon", word: "due soon", due: "2099-10-23", days: 14, basis: "documents", basisLabel: "DOCUMENTS", legal: false, proposed: true,
        items: { total: 12, notDone: 5, earliest: "2099-10-23" }, step: "oi.read-forms", n: 6, title: "Read the returned forms" },
    })} />
    <RunRow today={TODAY} row={row({
      id: "item-7", label: "Owner information 2098", due: due("2099-10-02", "law", -7, { cite: "EX 123.4" }), pastLaw: true,
      nudge: { band: "legal", word: "LEGAL", due: "2099-10-02", days: -7, basis: "law", basisLabel: "LEGAL", legal: true, proposed: false,
        items: null, step: "oi.resend", n: 10, title: "Resend to owners who have not answered" },
    })} />
  </List>
);

/** A paused run says why where the move would be; a run with no date says "No date". Another run is held outside the private view and shows only its general title. */
export const PausedAndHeld = () => (
  <List>
    <RunRow today={TODAY} row={row({
      id: "item-8", paused: true, pausedReason: "waiting for the board's reply on the list", state: "paused", group: "others", mine: false,
      age: { days: 21, opened: "2099-09-18", idleDays: 6, updated: "2099-10-03T08:12:00Z" },
    })} />
    <RunRow today={TODAY} row={row({
      id: "item-9", held: true, definitionTitle: "Held matter", label: "", group: "others", mine: false, state: "active",
      current: { id: "", title: "In progress", n: 0, of: 0, kind: "person", state: "needs a person", role: "manager" },
      waitingOn: null, due: due("2099-11-20", "documents", 42),
    })} />
  </List>
);
