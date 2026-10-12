import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { stepBandsText, todayCounts } from "../lib/officeView";
import type { OfficeViewData } from "../lib/officeView";
import { row } from "../lib/work.fixtures";
import type { RowNudge } from "../lib/work";
import { OfficeBands } from "./OfficeLens";
import { RunRow } from "./RunRow";

/* The read side of the person-step reminders (docs/workflows/person-steps.md, section 6): the Today band, the Today counts line,
   and the mark on a Work row. Made-up runs ("Oakview", 2099 dates). A reading only: nothing here sends, snoozes, or stores. */

afterEach(cleanup);

const STEP_ROWS = [
  { type: "person-step", band: "legal", urgency: "LEGAL", office: "manager", holder: "the manager", forOffice: false, id: "run-1", definition: "owner-info-cycle",
    title: "Last day to enter the answers", label: "Owner information 2099", step: "oi.read", n: 6, held: false, due: "2099-10-23", days: 0,
    basis: "LEGAL", legal: true, proposed: false, escalatedTo: "the whole board", items: null, screen: "",
    text: "Owner information 2099: Last day to enter the answers" },
  { type: "person-step", band: "late", urgency: "OVERDUE", office: "treasurer", holder: "the treasurer", forOffice: true, id: "run-2", definition: "bill-attach",
    title: "Review the attachments", label: "Bill attach: Example Electric, Oct", step: "ba.review", n: 4, held: false, due: "2099-10-14", days: -6,
    basis: "PERSON", legal: false, proposed: false, escalatedTo: "president", items: { total: 14, notDone: 3 }, screen: "",
    text: "Bill attach: Example Electric, Oct: Review the attachments (3 of 14 not done)" },
  { type: "person-step", band: "soon", urgency: "due soon", office: "secretary", holder: "the secretary", forOffice: false, id: "run-3", definition: "annual-test",
    title: "Read the report", label: "Held matter", step: "", n: 0, held: true, due: "2099-11-01", days: 12,
    basis: "COUNTERPARTY", legal: false, proposed: false, escalatedTo: null, items: null, screen: "", text: "Held matter: a step is due soon" },
];

function page(over: Partial<OfficeViewData> = {}): OfficeViewData {
  return {
    found: true, asOf: "2099-10-20", office: "treasurer", reading: ["treasurer"], title: "the treasurer", ownOffice: false, vacant: false,
    offices: [], mine: ["secretary"],
    bands: { waitingOnOffice: [], signedWaiting: [], personSteps: STEP_ROWS as never, needsAttention: [], comingUp: [], work: [] },
    counts: { waitingOnOffice: 0, signedWaiting: 0, personSteps: 3, needsAttention: 0, comingUp: 0, work: 0 },
    stepBands: { legal: 1, late: 1, soon: 1 },
    stepNumbers: { leadDays: 14, afterHours: 168, escalateAfterHours: 72, adopted: false, note: "proposed, not the law's" },
    bandErrors: {}, notComposed: [], caveats: [], ...over,
  };
}

describe("the Steps waiting on a person band", () => {
  it("titles the band, marks each step with the digest's word, and says who holds it", () => {
    render(<OfficeBands data={page()} />);
    expect(screen.getByRole("heading", { level: 2, name: "Steps waiting on a person" })).toBeInTheDocument();
    expect(document.querySelectorAll(".guide-band-legal")).toHaveLength(1);
    expect(screen.getByText("OVERDUE")).toBeInTheDocument();
    expect(screen.getByText("due soon")).toBeInTheDocument();
    expect(screen.getByText("6 days late")).toBeInTheDocument();
    expect(screen.getByText("COUNTERPARTY")).toBeInTheDocument();                         // whose date it is stays beside the word
    expect(screen.getByText("the treasurer")).toBeInTheDocument();                      // the office read holds it: no "another office"
    expect(screen.getByText("the manager (another office)")).toBeInTheDocument();
  });

  it("links a run row to the run and shows a per-item step as one row with its count", () => {
    render(<OfficeBands data={page()} />);
    const links = screen.getAllByRole("link", { name: "Open the run" }).map((a) => a.getAttribute("href"));
    expect(links).toEqual(["#/work/owner-info-cycle/run-1", "#/work/bill-attach/run-2", "#/work/annual-test/run-3"]);
    expect(screen.getByText(/3 of 14 not done/)).toBeInTheDocument();
  });

  it("says escalation is visibility only and that the lead time is a proposal", () => {
    render(<OfficeBands data={page()} />);
    expect(screen.getByText(/Escalation is visibility only/)).toHaveTextContent("proposed, not the law's");
    expect(screen.getByText("also seen by the whole board")).toBeInTheDocument();
    expect(screen.getByText("also seen by the president")).toBeInTheDocument();
  });

  it("is not drawn when nothing is due, and says so when it could not be read", () => {
    const quiet = page({
      bands: { waitingOnOffice: [], signedWaiting: [], needsAttention: [], comingUp: [], work: [] },
      counts: { waitingOnOffice: 0, signedWaiting: 0, needsAttention: 0, comingUp: 0, work: 0 },
    });
    const { rerender } = render(<OfficeBands data={quiet} />);
    expect(screen.queryByRole("heading", { name: "Steps waiting on a person" })).toBeNull();
    rerender(<OfficeBands data={{ ...quiet, bandErrors: { personSteps: "OSError: the runs are not readable" } }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("OSError: the runs are not readable");
  });
});

describe("the Today counts line", () => {
  it("counts the steps by band in the digest's words, most urgent first", () => {
    expect(stepBandsText({ soon: 2, legal: 1, late: 3 })).toBe("1 on a legal clock, 3 overdue, 2 due soon");
    expect(stepBandsText({ legal: 0 })).toBe("");
    expect(todayCounts(page({ office: "" }))).toBe("3 steps waiting on a person (1 on a legal clock, 1 overdue, 1 due soon)");
  });

  it("is silent about steps when there are none, and still says the rest", () => {
    const c = page({ counts: { waitingOnOffice: 2, signedWaiting: 0, personSteps: 0, needsAttention: 0, comingUp: 0, work: 0 }, stepBands: {} });
    expect(todayCounts({ ...c, office: "" })).toBe("2 waiting on you");
  });
});

describe("the mark on a Work row", () => {
  const nudge = (over: Partial<RowNudge> = {}): RowNudge => ({
    band: "late", word: "OVERDUE", due: "2099-10-14", days: -6, basis: "person", basisLabel: "PERSON", legal: false, proposed: false,
    items: null, step: "ba.review", n: 4, title: "Review the attachments", ...over,
  });
  const base = { id: "run-2", definition: "bill-attach", label: "Bill attach: Example Electric, Oct", group: "yours" } as const;

  it("carries the band's word, how far off the date is, and the step", () => {
    render(<ul><RunRow row={row({ ...base, nudge: nudge() })} /></ul>);
    expect(screen.getByText("OVERDUE")).toBeInTheDocument();
    expect(screen.getByText(/6 days late/)).toBeInTheDocument();
    expect(screen.getByText(/step 4/)).toBeInTheDocument();
  });

  it("says a legal date is LEGAL and a missing date needs a date", () => {
    const legal = nudge({ band: "legal", word: "LEGAL", days: 0, legal: true, basisLabel: "LEGAL" });
    const { rerender } = render(<ul><RunRow row={row({ ...base, nudge: legal })} /></ul>);
    expect(screen.getByText("LEGAL")).toBeInTheDocument();
    expect(screen.getByText(/due today/)).toBeInTheDocument();
    rerender(<ul><RunRow row={row({ ...base, nudge: nudge({ band: "date", word: "needs a date", due: null, days: null }) })} /></ul>);
    expect(screen.getByText("needs a date")).toBeInTheDocument();
    expect(screen.queryByText(/days? late|to go/)).toBeNull();
  });

  it("marks a due-soon or open band as resting on a proposal, and a per-item step with its count", () => {
    const soon = nudge({ band: "soon", word: "due soon", days: 9, items: { total: 14, notDone: 3, earliest: "2099-10-30" } });
    const { container } = render(<ul><RunRow row={row({ ...base, nudge: soon })} /></ul>);
    expect(container.querySelector(".work-row-nudge")).toHaveAttribute("title", expect.stringContaining("proposed, not the law's"));
    expect(screen.getByText(/3 of 14 not done/)).toBeInTheDocument();
  });

  it("shows nothing for a run with no step due, or a server that sends no nudge", () => {
    const { container, rerender } = render(<ul><RunRow row={row({ ...base, nudge: null })} /></ul>);
    expect(container.querySelector(".work-row-nudge")).toBeNull();
    rerender(<ul><RunRow row={row(base)} /></ul>);
    expect(container.querySelector(".work-row-nudge")).toBeNull();
  });
});
