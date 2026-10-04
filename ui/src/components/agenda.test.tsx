import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgendaWizard, ReadinessRow, addMinutes, clock, type AgendaCandidate, type AgendaPlan } from "./AgendaWizard";
import { BRIEF_FOOTER, DecisionBrief } from "./DecisionBrief";
import { DriveAttach } from "./DriveAttach";

afterEach(() => vi.unstubAllGlobals());

const loan: AgendaCandidate = {
  id: "reserve-loan", title: "Reserve loan not restored", ask: "Decide whether to restore the loan", session: "open session", authority: "CIV 5515(d)", evidence: ["jason reserves --transfers"],
  kind: "action", include: true, motion: "", allot: 15, order: 0, packet: [],
  readiness: { ready: false, checks: [{ label: "Motion drafted", ok: false, why: "no motion drafted yet" }, { label: "Supporting documents", ok: true }, { label: "Notice can still be given by 2026-10-17 (CIV 4920)", ok: true }] },
  suggestion: "no motion drafted yet",
};
const plan7: AgendaCandidate = {
  id: "payment-plan-7", title: "Payment plan, unit 7", ask: "Decide the plan", session: "executive session", kind: "executive", include: true, motion: "", allot: 10, order: 1, packet: [],
  readiness: { ready: true, checks: [{ label: "Executive session marked (CIV 4935)", ok: true }] }, suggestion: "",
};
const plan: AgendaPlan = {
  found: true, date: "2026-10-21", today: "2026-10-03", noticeBy: "2026-10-17", executiveNoticeBy: "2026-10-19", directors: ["A. Director"], decisions: [],
  basics: { date: "2026-10-21", start: "18:30", format: "hybrid", location: "Clubhouse, 123 Main St", join: "", dialIn: "", help: "" },
  zoom: { topic: "", joinUrl: "", dialIn: "", command: null, note: "jason has no command that creates a board meeting on Zoom. Enter the join link and dial-in here." },
  candidates: [loan, plan7], kinds: ["consent", "discussion", "action", "executive"], formats: ["in person", "hybrid", "teleconference"],
  rules: ["Notice and the agenda to members four days ahead (CIV 4920)."],
  noticeDays: 4, noticeAuthority: "CIV 4920(a)", executiveNoticeDays: 2, executiveNoticeAuthority: "CIV 4920(b)(2)",
  forum: { onFile: false, minutes: 0, source: "", label: "No limit on record; the board sets it (CIV 4925(b))." },
  notice: { by: "2026-10-17", executiveBy: "2026-10-19", required: [{ label: "Time and place of the meeting (CIV 4920(a))", ready: true }, { label: "A physical location where members may attend, with a director or designee present (CIV 4090(b))", ready: true }] },
  steps: ["Meeting", "Ready to act", "Order and motions", "Notice"],
  commands: { agendaDoc: "jason board --agenda <id> --date 2026-10-21 --doc --yes", packetDoc: "jason board --packet --date 2026-10-21 --doc --yes", minutesDraft: "jason board --minutes 2026-10-21", notice: 'jason board --set <item id> --status "on agenda" --meeting 2026-10-21', onAgenda: ['jason board --set reserve-loan --status "on agenda" --meeting 2026-10-21'] },
  updated: "", history: [], caveats: ["The board sets the agenda."],
};

describe("ReadinessRow", () => {
  it("shows a failing check as ✗, jason's line, and the executive badge only for executive matters", () => {
    const { rerender } = render(<ReadinessRow candidate={loan} />);
    expect(screen.getByText("✗ Motion drafted")).toHaveClass("check-bad");
    expect(screen.getByText("✓ Supporting documents")).toHaveClass("check-ok");
    expect(screen.getByText("jason: no motion drafted yet")).toBeInTheDocument();
    expect(screen.getByText("needs work")).toBeInTheDocument();
    expect(screen.queryByText("executive session")).not.toBeInTheDocument();
    rerender(<ReadinessRow candidate={plan7} />);
    expect(screen.getByText("executive session")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
  });
});

describe("AgendaWizard", () => {
  it("steps through, computes start times, and on step 4 shows commands and a checklist but never a send button", async () => {
    const user = userEvent.setup();
    const saved: unknown[] = [];
    render(<AgendaWizard plan={plan} onSave={(b) => { saved.push(b); }} />);
    expect(screen.getByRole("button", { name: "1 Meeting" })).toHaveAttribute("aria-current", "step");
    expect(screen.getByDisplayValue("Clubhouse, 123 Main St")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("0 ready")).toBeInTheDocument();
    expect(screen.getByText("1 need work")).toBeInTheDocument();
    expect(screen.getByText("1 executive session")).toBeInTheDocument();
    expect(screen.getByText("✗ Motion drafted")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText(/Runs about 44 minutes, 6:30 pm to 7:14 pm/)).toBeInTheDocument();
    expect(screen.getAllByText("6:30 pm")[0]).toBeInTheDocument();
    expect(screen.getByText("6:33 pm")).toBeInTheDocument();
    expect(screen.getByText(/Adjourn to executive session/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Proposed motion"), "Move to restore the loan.");
    await user.click(screen.getByRole("button", { name: "Review the notice" }));
    expect(screen.getByText('jason board --set reserve-loan --status "on agenda" --meeting 2026-10-21')).toBeInTheDocument();
    expect(screen.getByText("jason board --agenda <id> --date 2026-10-21 --doc --yes")).toBeInTheDocument();
    expect(screen.getByText(/jason has no command that creates a board meeting on Zoom/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Draft it in Approvals" })).toHaveAttribute("href", "#/approvals");
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /mail/i })).not.toBeInTheDocument();
    expect(screen.getByText("Enter your name to save 1 change.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Saved by"), "D. Okafor");
    await user.click(screen.getByRole("button", { name: "Save the plan" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    expect(confirm).toHaveTextContent("Reserve loan not restored, motion: — → Move to restore the loan.");
    await user.click(within(confirm).getByRole("button", { name: "Yes, do it" }));
    expect(saved).toEqual([{ by: "D. Okafor", items: { "reserve-loan": { motion: "Move to restore the loan." } } }]);
  });

  it("cites a hybrid meeting to 4090(b), never 4926; shows the notice period with its source; assumes no forum limit", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<AgendaWizard plan={plan} onSave={() => {}} />);
    expect(screen.getByLabelText("Join link for members attending remotely")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /4926/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Who can help/)).not.toBeInTheDocument();
    expect(screen.getByText(/4 days ahead \(CIV 4920\(a\)\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "4 Notice" }));
    expect(screen.getByText("What the notice must carry (CIV 4920, 4090(b))")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "3 Order and motions" }));
    expect(screen.getByText(/no limit on record; the board sets it \(CIV 4925\(b\)\)/)).toBeInTheDocument();
    expect(screen.queryByText(/3 minutes/)).not.toBeInTheDocument();
    // Entirely by teleconference: 4926's lines, and a documents' longer notice period with its source.
    const tele: AgendaPlan = { ...plan, basics: { ...plan.basics, format: "teleconference", location: "" }, noticeBy: "2026-10-11", noticeDays: 10, noticeAuthority: "Bylaws 1.2; CIV 4920(b)(3)" };
    rerender(<AgendaWizard key="tele" plan={tele} onSave={() => {}} />);
    await user.click(screen.getByRole("button", { name: "1 Meeting" }));
    expect(screen.getByLabelText("Join instructions or link (CIV 4926(a)(1)(A))")).toBeInTheDocument();
    expect(screen.getByLabelText("Who can help before and during, phone and email (CIV 4926(a)(1)(B))")).toBeInTheDocument();
    expect(screen.getByText(/10 days ahead \(Bylaws 1\.2; CIV 4920\(b\)\(3\)\)/)).toBeInTheDocument();
  });

  it("clocks", () => {
    expect(addMinutes("18:30", 44)).toBe("19:14");
    expect(clock("18:30")).toBe("6:30 pm");
    expect(clock("09:05")).toBe("9:05 am");
    expect(clock("")).toBe("—");
  });
});

describe("DecisionBrief", () => {
  it("letters the options with the same criteria and shows the footer line", () => {
    render(<DecisionBrief decision={{ question: "Which contract?", criteria: ["Monthly cost", "Term"], options: [{ label: "Renew", values: ["$1,850.00", "two years"] }, { label: "Rebid", values: ["not known"] }], facts: ["Both bids are in the packet"] }} />);
    expect(screen.getByText("Which contract?")).toBeInTheDocument();
    const a = screen.getByRole("article", { name: "Option A" });
    const b = screen.getByRole("article", { name: "Option B" });
    expect(within(a).getByText("A")).toBeInTheDocument();
    expect(within(b).getByText("B")).toBeInTheDocument();
    expect(within(a).getAllByRole("term").map((t) => t.textContent)).toEqual(["Monthly cost", "Term"]);
    expect(within(b).getAllByRole("term").map((t) => t.textContent)).toEqual(["Monthly cost", "Term"]);
    expect(within(b).getAllByRole("definition").map((t) => t.textContent)).toEqual(["not known", ""]);
    expect(screen.getByText("Both bids are in the packet")).toBeInTheDocument();
    expect(screen.getByText(BRIEF_FOOTER)).toBeInTheDocument();
    expect(screen.queryByText(/recommend(ed|s|ation)\b/)).not.toBeInTheDocument();
  });
});

describe("DriveAttach", () => {
  it("searches the catalog on disk, attaches picked files, opens only real URLs, and removes", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({
      found: true, syncedAt: "2026-10-02T10:00:00+00:00", matching: 2,
      files: [{ id: "f1", name: "Resolution.docx", path: "Board/2026", kind: "doc", link: "https://docs.google.com/document/d/f1", modified: "2026-10-02" },
              { id: "f2", name: "Bid.pdf", path: "Vendors", kind: "drive", link: "", modified: "2026-09-20" }].filter((f) => f.name.toLowerCase().includes(decodeURIComponent(url.split("q=")[1].split("&")[0]).toLowerCase())),
    }), { status: 200 })));
    const user = userEvent.setup();
    let files: { id: string; name: string; kind: string; url: string }[] = [];
    const { rerender } = render(<DriveAttach files={files} onChange={(f) => { files = f; }} />);
    expect(screen.getByText(/Google Picker is not configured; this searches the Drive catalog jason synced/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Attach from Drive" }));
    const dialog = screen.getByRole("dialog", { name: "Choose files from Drive" });
    expect(await within(dialog).findByText("Resolution.docx")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Search the Drive catalog"), "bid");
    await waitFor(() => expect(within(dialog).queryByText("Resolution.docx")).not.toBeInTheDocument());
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(within(dialog).getByRole("button", { name: "Attach 1" }));
    expect(files).toEqual([{ id: "f2", name: "Bid.pdf", kind: "drive", url: "" }]);
    files = [...files, { id: "f1", name: "Resolution.docx", kind: "doc", url: "https://docs.google.com/document/d/f1" }];
    rerender(<DriveAttach files={files} onChange={(f) => { files = f; }} />);
    expect(screen.getAllByRole("link", { name: "Open" })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "https://docs.google.com/document/d/f1");
    await user.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    expect(files.map((f) => f.id)).toEqual(["f1"]);
  });
});
