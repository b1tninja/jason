import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  AssemblyRegister, CodeRow, Discrepancy, DocumentCodes, FilingPlan, HoldingChips, NoticeClock, NotOursNotice, PortalReportRow, ReportPortalCard, TesterCheck, TextGrade, WatchRow,
} from "./index";
import { filingButtonLabel, groupByAction, sortWatch, testerSummary } from "../lib/inspections";
import * as fx from "../lib/inspections.fixtures";

const docProps = { signedIn: true, evidence: null } as const;
const today = new Date("2030-10-04T12:00:00");

describe("DocumentCodes", () => {
  it("shows the host first and the full link second, with no control on the first line", () => {
    const { container } = render(<DocumentCodes codes={[fx.codeLink]} onOpenLink={() => {}} />);
    const first = container.querySelector(".insp-code-first") as HTMLElement;
    expect(first.querySelector("button, a")).toBeNull();
    const host = first.querySelector(".insp-host") as HTMLElement;
    const link = first.querySelector(".insp-code-text") as HTMLElement;
    expect(host).toHaveTextContent("reports.example.com");
    expect(link).toHaveTextContent("https://reports.example.com/r/abc123");
    expect(host.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("opens only as a second step that shows the host again and says jason has not opened it", async () => {
    const onOpenLink = vi.fn();
    render(<CodeRow code={fx.codeLink} onOpenLink={onOpenLink} />);
    await userEvent.click(screen.getByRole("button", { name: "Review before opening" }));
    expect(onOpenLink).not.toHaveBeenCalled();
    const step = screen.getByRole("group", { name: "Open reports.example.com" });
    expect(within(step).getByText("reports.example.com")).toBeInTheDocument();
    expect(step).toHaveTextContent("jason has not opened this link");
    await userEvent.click(within(step).getByRole("button", { name: "Open reports.example.com" }));
    expect(onOpenLink).toHaveBeenCalledWith(fx.codeLink);
  });

  it("offers the portal's reports for a vendor portal", async () => {
    const onOpenPortal = vi.fn();
    render(<CodeRow code={fx.codePortal} onOpenPortal={onOpenPortal} />);
    await userEvent.click(screen.getByRole("button", { name: "Open the portal's reports" }));
    expect(onOpenPortal).toHaveBeenCalledWith(fx.codePortal.portal);
  });

  it("shows a meeting's number and a missing index record as a lead", () => {
    const { rerender } = render(<CodeRow code={fx.codeMeetingRecorded} />);
    expect(screen.getByText("123456789")).toBeInTheDocument();
    expect(screen.getByText("recorded")).toBeInTheDocument();
    rerender(<CodeRow code={fx.codeMeetingUnrecorded} />);
    expect(screen.getByText("lead")).toBeInTheDocument();
    expect(screen.getByText(/no record in the Zoom index/)).toBeInTheDocument();
  });

  it("shows a masked payload as given and says a passcode is in the link", () => {
    render(<CodeRow code={fx.codeMasked} />);
    expect(screen.getByText(/passcode=\*\*\*/)).toBeInTheDocument();
    expect(screen.getByText("masked")).toBeInTheDocument();
    expect(screen.getByText(/passcode is in the link/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review before opening" })).toBeNull();   // nothing to open without the server
  });

  it("shows a payload that is not a link as plain text, with no open step", () => {
    render(<CodeRow code={fx.codeText} onOpenLink={() => {}} />);
    expect(screen.getByText(/Plain text, not a link/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the decoder is missing, with the command, and never says there are no codes", () => {
    render(<DocumentCodes codes={[]} decoderMissing installCommand={fx.installCommand} />);
    expect(screen.getByRole("status")).toHaveTextContent("Codes are not read");
    expect(screen.getByText(fx.installCommand)).toBeInTheDocument();
    expect(screen.queryByText(/No code was read/)).toBeNull();
  });

  it("says plainly when none was read", () => {
    render(<DocumentCodes codes={[]} />);
    expect(screen.getByText(/No code was read/)).toBeInTheDocument();
  });
});

describe("HoldingChips", () => {
  it("has one chip per place and marks a copy that is not identical", () => {
    render(<HoldingChips holdings={[{ place: "library", where: "Email Attachments/x", identical: true }, { place: "drive", where: "My Drive/Reports", identical: false }]} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText(/a different copy/)).toBeInTheDocument();
  });
  it("says none in words", () => {
    render(<HoldingChips holdings={[]} />);
    expect(screen.getByText(/No place holds it/)).toBeInTheDocument();
  });
});

describe("PortalReportRow and ReportPortalCard", () => {
  it("shows a held word for each report and a record of completion as such", () => {
    render(<>{fx.portal.reports.map((r) => <PortalReportRow key={r.urlUuid} report={r} />)}</>);
    expect(screen.getByText("not filed")).toBeInTheDocument();
    expect(screen.getByText("library and drive")).toBeInTheDocument();
    expect(screen.getByText("library only")).toBeInTheDocument();
    expect(screen.getByText("record of completion")).toBeInTheDocument();
  });
  it("says a report was held back by the name check", () => {
    render(<PortalReportRow report={fx.portalRefused.reports[0]} />);
    expect(screen.getByText("held back")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("its text does not name the site");
  });
  it("names the command that finds a portal when none is found", () => {
    render(<ReportPortalCard portal={null} vendor="Example Alarm Co." findCommand={fx.findCommand} />);
    expect(screen.getByText("not found")).toBeInTheDocument();
    expect(screen.getByText(fx.findCommand)).toBeInTheDocument();
  });
  it("says the vendor row has none", () => {
    render(<ReportPortalCard portal={null} vendorHasNone />);
    expect(screen.getByText(/says it has no report portal/)).toBeInTheDocument();
  });
  it("shows found-not-synced with the sync command", () => {
    render(<ReportPortalCard portal={fx.portalFoundNotSynced} syncCommand={fx.portalCommand} />);
    expect(screen.getByText("found, not synced")).toBeInTheDocument();
    expect(screen.getByText(fx.portalCommand)).toBeInTheDocument();
  });
  it("renders the loader's counts and every report when synced, without computing missing", () => {
    render(<ReportPortalCard portal={fx.portal} syncCommand={fx.portalCommand} />);
    const counts = screen.getByLabelText("Counts from the loader");
    expect(counts).toHaveTextContent("Listed3");
    expect(counts).toHaveTextContent("Not filed1");
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getByText("synced")).toBeInTheDocument();
  });
  it("makes a protected portal a stop with a person's step, not an error", () => {
    render(<ReportPortalCard portal={fx.portalProtected} syncCommand={fx.portalCommand} />);
    expect(screen.getByText("protected")).toBeInTheDocument();
    expect(screen.getByText(/asks for a password or a phone code. jason enters neither/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(fx.portalCommand)).toBeNull();
  });
  it("lists a same-customer portal once, pointing at the other", () => {
    render(<ReportPortalCard portal={fx.portalSameCustomer} />);
    expect(screen.getByText(/The same customer as portal/)).toBeInTheDocument();
  });
  it("shows an unreachable portal's error as an alert with the command", () => {
    render(<ReportPortalCard portal={fx.portalUnreachable} syncCommand={fx.portalCommand} />);
    expect(screen.getByRole("alert")).toHaveTextContent("did not answer");
    expect(screen.getByText(fx.portalCommand)).toBeInTheDocument();
  });
  it("starts the sync only behind a Confirm", async () => {
    const onSync = vi.fn();
    render(<ReportPortalCard portal={fx.portalFoundNotSynced} onSync={onSync} />);
    await userEvent.click(screen.getByRole("button", { name: "Read the portal's list" }));
    expect(onSync).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onSync).toHaveBeenCalledTimes(1);
  });
});

describe("FilingPlan", () => {
  it("names the numbers on the button, and the button comes after the whole plan", () => {
    const { container } = render(<FilingPlan plan={fx.filingPlan} onConfirmFile={() => {}} />);
    expect(filingButtonLabel(fx.filingPlan)).toBe("File 8, copy 5, move 2");
    const button = screen.getByRole("button", { name: "File 8, copy 5, move 2" });
    const rows = container.querySelectorAll(".insp-plan-row");
    expect(rows.length).toBe(fx.filingPlan.rows.length);
    rows.forEach((r) => expect(r.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy());
    const counts = screen.getByLabelText("Counts by action");
    expect(counts.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("writes only after two clicks, and spells out the copy, the move, and that nothing deletes", async () => {
    const onConfirmFile = vi.fn();
    render(<FilingPlan plan={fx.filingPlan} onConfirmFile={onConfirmFile} />);
    await userEvent.click(screen.getByRole("button", { name: "File 8, copy 5, move 2" }));
    expect(onConfirmFile).not.toHaveBeenCalled();
    const stamp = screen.getByRole("group", { name: "File" });
    expect(stamp).toHaveTextContent("The original stays");
    expect(stamp).toHaveTextContent("keeps its id, its link, and its sharing");
    expect(stamp).toHaveTextContent("Nothing is deleted");
    await userEvent.click(within(stamp).getByRole("button", { name: "Yes, do it" }));
    expect(onConfirmFile).toHaveBeenCalledWith(fx.filingPlan);
  });
  it("says in each row what happens to the original and the file", () => {
    render(<FilingPlan plan={fx.filingPlan} onConfirmFile={() => {}} />);
    expect(screen.getByText(/It stays at Email Attachments/)).toBeInTheDocument();
    expect(screen.getAllByText(/keeps its id, its link, and its sharing/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Held for a person to verify first/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
  });
  it("recites the rule's condition behind a Why disclosure", () => {
    render(<FilingPlan plan={fx.filingPlan} />);
    expect(screen.getAllByText("Why")).toHaveLength(fx.filingPlan.rows.length);
  });
  it("says everything is filed and has no button when there is nothing to write", () => {
    render(<FilingPlan plan={fx.filingPlanEmpty} onConfirmFile={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Everything is filed");
    expect(screen.queryByRole("button", { name: /^File/ })).toBeNull();
  });
  it("shows the filing under way", () => {
    render(<FilingPlan plan={fx.filingPlan} onConfirmFile={() => {}} running />);
    expect(screen.getByRole("status")).toHaveTextContent("Filing: File 8, copy 5, move 2");
    expect(screen.queryByRole("button", { name: "File 8, copy 5, move 2" })).toBeNull();
  });
  it("groups rows by action in a fixed order", () => {
    expect(groupByAction(fx.filingPlan.rows).map((g) => g.action)).toEqual(["file", "copy", "move", "in drive", "filed before", "held"]);
  });
});

describe("NoticeClock", () => {
  it("renders all four dates with their elapsed days and met, not met, or unknown in words", () => {
    render(<NoticeClock clock={fx.deadline} />);
    const dates = screen.getAllByRole("listitem");
    expect(dates).toHaveLength(4);
    for (const d of ["2030-05-05", "2030-06-02", "2030-06-11", "2030-07-03"]) expect(screen.getByText(d)).toBeInTheDocument();
    expect(screen.getByText("44 days elapsed")).toBeInTheDocument();
    expect(screen.getByText("0 days elapsed")).toBeInTheDocument();
    expect(within(dates[2]).getByText("met")).toBeInTheDocument();
    expect(within(dates[0]).getByText("not met")).toBeInTheDocument();
    expect(within(dates[3]).getByText("unknown")).toBeInTheDocument();
    expect(screen.getByText("Which date counts is the program's to say.")).toBeInTheDocument();
  });
  it("picks no winner", () => {
    const { container } = render(<NoticeClock clock={fx.deadline} />);
    expect(container.innerHTML).not.toMatch(/winner|selected|best/i);
    const classes = [...container.querySelectorAll(".insp-date")].map((e) => e.className);
    expect(new Set(classes).size).toBe(1);
  });
  it("cites a statute differently from a program's notice", () => {
    const { rerender } = render(<NoticeClock clock={fx.deadlineStatute} />);
    expect(screen.getByText(/The statute's own clock/)).toBeInTheDocument();
    rerender(<NoticeClock clock={fx.deadline} />);
    expect(screen.getByText(/A program's notice, in its own words/)).toBeInTheDocument();
  });
});

describe("AssemblyRegister and Discrepancy", () => {
  it("makes each source a column and never merges the ids", () => {
    render(<AssemblyRegister assemblies={fx.assemblies} docProps={docProps} />);
    const first = screen.getByRole("article", { name: /fire DC SN-0001/ });
    const headers = within(first).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["County", "City"]);
    expect(within(first).getByText("A-100")).toBeInTheDocument();
    expect(within(first).getByText("B-200")).toBeInTheDocument();
  });
  it("shows a device no source has, and a failed device with its repair clock", () => {
    const orphan = { ...fx.assemblies[2], ids: [] };
    render(<AssemblyRegister assemblies={[fx.assemblies[1], orphan]} repairClocks={{ "SN-0002": fx.deadline }} docProps={docProps} />);
    expect(screen.getByText("no source lists it")).toBeInTheDocument();
    expect(screen.getAllByText("failed").length).toBeGreaterThan(0);
    expect(screen.getByText(/Example City cross-connection program: 15 days/)).toBeInTheDocument();
  });
  it("shows 'not read' in a device's history, never a guess", () => {
    render(<AssemblyRegister assemblies={[fx.assemblies[1]]} docProps={docProps} />);
    expect(screen.getByText(/History \(2\)/)).toBeInTheDocument();
    expect(screen.getAllByText("not read").length).toBeGreaterThan(0);
  });
  it("lists each source's statement in its own column and picks no side", () => {
    render(<Discrepancy discrepancy={fx.discrepancy} docProps={docProps} />);
    const t = screen.getByRole("table");
    expect(within(t).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["County", "City", "Reserve study"]);
    expect(within(t).getAllByText("four on the fire service")).toHaveLength(2);
    expect(within(t).getByText("five on the fire service")).toBeInTheDocument();
    expect(screen.getByText(/does not say which is right/)).toBeInTheDocument();
  });
  it("shows the next step as a command, or as a question", () => {
    const { rerender } = render(<Discrepancy discrepancy={fx.discrepancy} docProps={docProps} />);
    expect(screen.getByText("jason backflow --reconcile --service fire")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy command" })).toBeInTheDocument();
    rerender(<Discrepancy discrepancy={fx.discrepancyQuestion} docProps={docProps} />);
    expect(screen.getByText(/Which source lists the fifth device/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy command" })).toBeNull();
  });
  it("renders the register's discrepancies above the devices", () => {
    render(<AssemblyRegister assemblies={fx.assemblies} discrepancies={[fx.discrepancy]} docProps={docProps} />);
    expect(screen.getByText("Devices on the fire service")).toBeInTheDocument();
  });
});

describe("TesterCheck", () => {
  it("says listed on the list dated D, never 'certified', and prints no phone or email", () => {
    const { container } = render(<TesterCheck check={fx.testerListed} today={today} />);
    expect(screen.getByText(/listed on the list dated 2030-09-01/)).toBeInTheDocument();
    expect(screen.getByText("listed on every list checked")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/certified/i);
    expect(container.textContent).not.toMatch(/@|\(\d{3}\)|\d{3}[-. ]\d{4}/);
    expect(screen.getByText(/Contact details are masked/)).toBeInTheDocument();
  });
  it("covers listed on one only, another business, not listed, and not fetched", () => {
    const { rerender } = render(<TesterCheck check={fx.testerOne} today={today} />);
    expect(screen.getByText("listed on one only")).toBeInTheDocument();
    rerender(<TesterCheck check={fx.testerOtherBusiness} today={today} />);
    expect(screen.getByText(/matched on the tester's name/)).toBeInTheDocument();
    expect(screen.getByText("listed under a different business")).toBeInTheDocument();
    rerender(<TesterCheck check={fx.testerNotListed} today={today} />);
    expect(screen.getAllByText("not listed").length).toBeGreaterThan(0);
    rerender(<TesterCheck check={fx.testerNotFetched} today={today} />);
    expect(screen.getByText(/nothing is said about this list/)).toBeInTheDocument();
    expect(testerSummary(fx.testerNotFetched.lists)).toBe("lists not fetched");
  });
  it("says a list older than a year is dated so", () => {
    render(<TesterCheck check={fx.testerOld} today={today} />);
    expect(screen.getByRole("note")).toHaveTextContent("This list is dated 2025-06-01, more than a year ago");
  });
});

describe("TextGrade", () => {
  it("shows the grade as visible text beside the words, and a digest says confirm at the source", () => {
    render(<TextGrade grade="digest" />);
    expect(screen.getByText("digest")).toBeInTheDocument();
    expect(screen.getByText(/a summary of a code reader/)).toBeVisible();
    expect(screen.getByText(/confirm at the source/)).toBeVisible();
  });
  it("covers every grade with a word and its label, and no endorsement", () => {
    const { container } = render(<>{(["legislature", "official", "digest", "quoted by a notice", "not found"] as const).map((g) => <TextGrade key={g} grade={g} />)}</>);
    expect(screen.getByText(/the Legislature's text/)).toBeInTheDocument();
    expect(screen.getByText(/quoted by a notice$/, { selector: ".insp-grade-label" })).toBeInTheDocument();
    expect(container.querySelector('[data-grade="legislature"] .badge-good')).toBeNull();
    expect(container.querySelector('[data-grade="digest"] svg')).not.toBeNull();   // a glyph second
  });
});

describe("NotOursNotice", () => {
  it("marks not ours only behind a Confirm, and drafts a return without sending", async () => {
    const onMark = vi.fn();
    const onDraft = vi.fn();
    render(<NotOursNotice item={fx.notOurs} onMarkNotOurs={onMark} onDraftReturn={onDraft} />);
    expect(screen.getByText(/The other party's details are not shown/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark not ours" }));
    expect(onMark).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onMark).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: /Draft a note returning it/ }));
    expect(onDraft).toHaveBeenCalledTimes(1);
  });
  it("shows who marked it", () => {
    render(<NotOursNotice item={fx.notOursMarked} onMarkNotOurs={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Marked not ours by Jane Example on 2030-10-04");
    expect(screen.queryByRole("button", { name: "Mark not ours" })).toBeNull();
  });
});

describe("WatchRow", () => {
  it("shows the searched line and that another name is not seen on unknown, and never reads as not done", () => {
    render(<WatchRow item={fx.watchItems[1]} docProps={docProps} />);
    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(screen.getByText(/Searched by email subject and Drive file name/)).toBeVisible();
    expect(screen.getByText(/A record under another name is not seen/)).toBeVisible();
    expect(screen.getByText(/Nothing here says it was not done/)).toBeInTheDocument();
    expect(screen.queryByText("overdue")).toBeNull();
  });
  it("shows each standing as a word, with evidence as document chips", () => {
    render(<>{fx.watchItems.map((w) => <WatchRow key={w.item} item={w} docProps={docProps} />)}</>);
    for (const w of ["current", "unknown", "overdue", "partly answered", "not applicable"]) expect(screen.getByText(w)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Fire Alarm 2029-09-19.pdf" })).toBeInTheDocument();
    expect(screen.getAllByText(/What would change this/)).toHaveLength(5);
  });
  it("sorts overdue first, then unknown, before current", () => {
    expect(sortWatch(fx.watchItems).map((w) => w.standing)).toEqual(["overdue", "unknown", "partly answered", "current", "not applicable"]);
  });
});

describe("evidence the loader could not resolve", () => {
  // The loaders return a document reference when they can make one, and the name as text (or a command) when they cannot.
  const text = { text: "AES 2.1 - 03-14-2023 Annual Fire Sprinkler Inspection Report.pdf" };
  it("WatchRow shows a name given as text, and a command to copy", () => {
    render(<WatchRow item={{ ...fx.watchItems[1], evidence: [text, { command: "jason ingest SOURCE" }] }} docProps={docProps} />);
    expect(screen.getByText(text.text)).toBeInTheDocument();
    expect(screen.getByText("jason ingest SOURCE")).toBeInTheDocument();
  });
  it("Discrepancy and AssemblyRegister show a source's name given as text", () => {
    render(<Discrepancy discrepancy={{ subject: "Count", sources: [{ source: "the lists", says: "four" }, { source: "the study", says: "five", doc: text }] }} docProps={docProps} />);
    expect(screen.getByText(text.text)).toBeInTheDocument();
  });
  it("AssemblyRegister takes a device whose optional fields are left out", () => {
    const bare = { service: "fire", type: "DC", sizeIn: 6, serial: "S1", location: "north", ids: [], testDue: "2030-05-31", history: [{ date: "2030-05-01", result: "passed", document: text }] } as never;
    render(<AssemblyRegister assemblies={[bare]} docProps={docProps} />);
    expect(screen.getByText(text.text)).toBeInTheDocument();
  });
});
