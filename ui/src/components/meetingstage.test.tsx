import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import type { EvidenceAnswer } from "./Evidence";
import { EXECUTIVE_HELD, HostPanel, MEMBERS_PACKET_LINE, MeetingStage, generalNote, minutesLetter, type MeetingRoomData, type MinutesLetter } from "./MeetingStage";
import { DRIVE_BID, EXEC_ITEM, SECRET_MOTION, SECRET_TITLE, roomData } from "../views/meetingroom.fixture";
import { RollCall, outcome } from "./RollCall";

describe("RollCall, extended", () => {
  it("computes the tally line from present, recused, and threshold", () => {
    expect(outcome({ A: "aye" }, { present: ["A", "B", "C"] }).line).toBe("Yes 1 · No 0 · Abstain 0 · Recused 0. Needs 2 yes. Vote open.");
    expect(outcome({ A: "aye", B: "no", C: "no" }, { present: ["A", "B", "C"] }).state).toBe("fails");
    // Two-thirds of four voters is three; with only three of five present, every director present must agree.
    expect(outcome({ A: "aye", B: "aye", C: "no", D: "aye" }, { present: ["A", "B", "C", "D"], threshold: "two-thirds", seats: 5 }).needs).toBe(3);
    expect(outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C"], threshold: "two-thirds", seats: 5 })).toMatchObject({ needs: 3, state: "fails" });
    // A majority of the directors in office, where the bylaws say so.
    expect(outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C"], basis: "majority-in-office", seats: 5 })).toMatchObject({ needs: 3, state: "fails" });
    // Without present, everyone who voted is present; it reads the same as the plain tally.
    expect(outcome({ A: "aye", B: "abstain" })).toMatchObject({ yes: 1, abstain: 1, needs: 2, state: "fails" });
  });

  it("works a recusal both ways when the rule is not on file, and holds a vote the readings decide differently", () => {
    const either = outcome({ A: "aye", B: "aye", C: "aye" }, { present: ["A", "B", "C", "D"], recused: ["D"] });
    expect(either.line).toBe("Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes counting the recused director as present, 2 yes if not. Carries under either reading.");
    // Counted as present, a majority of four is three; not counted, a majority of three is two. Two ayes: held.
    const held = outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C", "D"], recused: ["D"], quorum: 3 });
    expect(held).toMatchObject({ state: "held", readings: { counted: { needs: 3, state: "fails" }, notCounted: { needs: 2, state: "carries" } } });
    expect(held.line).toContain("not on file; ask counsel");
    // Not counted, three present with one recused leaves two: no quorum of three under that reading.
    expect(outcome({ A: "aye", B: "aye" }, { present: ["A", "B", "C"], recused: ["C"], quorum: 3 })).toMatchObject({ state: "held" });
    // With the rule on file, one reading, no hedge.
    expect(outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C", "D"], recused: ["D"], interested: true })).toMatchObject({ needs: 3, state: "fails" });
    expect(outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C", "D"], recused: ["D"], interested: false, quorum: 3 })).toMatchObject({ needs: 2, state: "carries" });
  });

  it("shows a recused row as recused with its radios off, the tally line, and that the rule is not on file", () => {
    render(<RollCall directors={["A", "B", "C"]} votes={{ A: "aye", B: "aye" }} onChange={() => {}} present={["A", "B", "C"]} recused={["C"]} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[2]).getByText("recused")).toBeInTheDocument();
    expect(screen.getByLabelText("C: aye")).toBeDisabled();
    expect(screen.getByLabelText("A: aye")).toBeEnabled();
    expect(screen.queryByLabelText("A: absent")).not.toBeInTheDocument();
    expect(screen.getByText("Yes 2 · No 0 · Abstain 0 · Recused 1. Needs 2 yes counting the recused director as present, 2 yes if not. Carries under either reading.")).toBeInTheDocument();
    expect(screen.getByText(/counts toward the quorum and among the directors present is not on file; ask counsel/)).toBeInTheDocument();
    expect(screen.queryByText(/counted toward the quorum, never toward the vote|Still counts toward the quorum/)).not.toBeInTheDocument();
  });

  it("marks a recused director recused in a plain roll call too, never absent", () => {
    render(<RollCall directors={["A", "B"]} votes={{ A: "aye" }} recused={["B"]} onChange={() => {}} />);
    expect(screen.getByText("recused")).toBeInTheDocument();
    expect(screen.getByLabelText("B: absent")).toBeDisabled();
  });

  it("renders as before without the new props", () => {
    const { container } = render(<RollCall directors={["A"]} votes={{}} />);
    expect(container.firstElementChild?.tagName).toBe("TABLE");
    expect(screen.getByLabelText("A: absent")).toBeInTheDocument();
    expect(screen.queryByText(/Needs/)).not.toBeInTheDocument();
  });
});

describe("MeetingStage", () => {
  it("shows the item, a content block, the caption, and the progress", () => {
    render(<MeetingStage wordmark="Sample" item={{ label: "Item 1 · Action", title: "Renew the contract" }} content={{ kind: "motion", text: "Move it.", mover: "A", second: "B" }} caption={<span>jason · line</span>} progress={0.5} live />);
    expect(screen.getByRole("heading", { name: "Renew the contract" })).toBeInTheDocument();
    expect(screen.getByText("Moved by A, seconded by B")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("live")).toBeInTheDocument();
  });
  it("renders attendance, the clock, and a sample packet", () => {
    const { rerender } = render(<MeetingStage wordmark="S" item={{ label: "Call to order", title: "Roll call" }} content={{ kind: "attendance", rows: [{ name: "A", present: true }, { name: "B", present: false }], quorum: "2 of 2. A quorum is 2." }} caption="" progress={0} />);
    expect(screen.getByText("2 of 2. A quorum is 2.")).toBeInTheDocument();
    rerender(<MeetingStage wordmark="S" item={{ label: "Open forum", title: "Open forum" }} content={{ kind: "countdown", seconds: 125, speaker: "3 minutes each" }} caption="" progress={0} />);
    expect(screen.getByText("2:05")).toBeInTheDocument();
    rerender(<MeetingStage wordmark="S" item={{ label: "Item", title: "x" }} content={{ kind: "packet", file: { name: "Bid.pdf", kind: "pdf" } }} caption="" progress={0} />);
    expect(screen.getByText(/document preview/)).toBeInTheDocument();
  });
});

describe("MeetingStage packet files", () => {
  afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });
  const bid = () => roomData().items[2].packet[1];
  const stage = (props: Partial<Parameters<typeof MeetingStage>[0]> = {}) => (
    <MeetingStage wordmark="S" item={{ label: "Item 1", title: "Renew the contract" }} content={{ kind: "packet", file: bid() }} caption="" progress={0} {...props} />
  );
  const noGoogleFrame = (root: HTMLElement) => {
    for (const f of Array.from(root.querySelectorAll("iframe"))) expect(f.getAttribute("src") ?? "").not.toMatch(/google\.com/);
  };
  const copy = (): EvidenceAnswer => ({
    found: true, address: `drive:${DRIVE_BID}`, label: "Vendor B bid", kind: "drive", sources: [], changed: false, changedNote: "",
    link: `https://docs.google.com/document/d/${DRIVE_BID}/edit`, refresh: [], caveats: [], note: "",
    documents: [{ id: "pdf", name: "Vendor B bid.pdf", kind: "pdf", size: 10, readAt: "2026-10-03T15:00:00+00:00", note: "" }],
  });

  it("shows the board jason's copy, inline, from its document link", () => {
    const view = { kind: "pdf" as const, name: "Vendor B bid.pdf", readAt: "2026-10-03T15:00:00+00:00", url: "/api/evidence/document/tok", expires: "", caveats: [] };
    const { container } = render(stage({ packetCopy: { evidence: copy(), view, signedIn: true } }));
    const region = screen.getByRole("region", { name: "Vendor B bid, jason's copy" });
    expect(within(region).getByTitle("Vendor B bid.pdf")).toHaveAttribute("src", "/api/evidence/document/tok");
    noGoogleFrame(container);
  });

  it("with no copy, the board sees the preview card with Read from Drive and Open in Google, never a frame", () => {
    const { container } = render(stage({ packetCopy: { evidence: { ...copy(), documents: [] }, signedIn: true } }));
    expect(screen.getByText("Vendor B bid: No copy yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read Vendor B bid from Drive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", `https://docs.google.com/document/d/${DRIVE_BID}/edit`);
    expect(container.querySelector("iframe")).toBeNull();
  });

  it("members see only a card that names it", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(stage({ audience: "owner" }));
    expect(screen.getByRole("note")).toHaveTextContent(MEMBERS_PACKET_LINE("Vendor B bid"));
    expect(screen.getByText("The host is showing Vendor B bid; members receive the packet with the agenda.")).toBeInTheDocument();
    expect(container.querySelector("iframe, img")).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();                                                 // members are not signed in
  });

  it("opens the copy as one logged view, through jason only, and never frames Google", async () => {
    const calls: [string, string][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push([init?.method ?? "GET", url]);
      const body = url.startsWith("/api/session") ? { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true } }
        : url === "/api/evidence/view" ? { kind: "pdf", name: "Vendor B bid.pdf", readAt: "", url: "/api/evidence/document/tok", expires: "", caveats: [] }
        : copy();
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    const { container } = render(stage());
    const frame = await screen.findByTitle("Vendor B bid.pdf");
    expect(frame).toHaveAttribute("src", "/api/evidence/document/tok");
    expect(calls.filter(([m]) => m === "POST")).toEqual([["POST", "/api/evidence/view"]]);
    expect(calls.every(([, u]) => u.startsWith("/api/"))).toBe(true);
    noGoogleFrame(container);
  });

  it("the host panel links the original, never frames it", () => {
    const { container } = render(<HostPanel room={roomData()} onAction={vi.fn(async () => true)} me="S. Clerk" />);
    expect(container.querySelector("iframe")).toBeNull();
  });
});

describe("HostPanel", () => {
  it("offers exactly the five CIV 4930 paths in the off-agenda guard, each behind a confirm that logs", async () => {
    const onAction = vi.fn(async (_a: string, _b?: Record<string, unknown>) => true);
    const user = userEvent.setup();
    render(<HostPanel room={roomData()} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("button", { name: "A topic not on the agenda" }));
    const guard = screen.getByRole("group", { name: "Off-agenda guard" });
    const paths = within(guard).getAllByRole("button").filter((b) => /CIV 4930/.test(b.textContent ?? ""));
    expect(paths).toHaveLength(5);
    expect(paths.map((b) => b.textContent)).toEqual([
      "Respond briefly, ask a question, or announce (CIV 4930(b))", "Ask staff to report back, or place it on a future agenda (CIV 4930(c))",
      "A majority finds an emergency (CIV 4930(d)(1))", "Two-thirds find an immediate need that arose after posting (CIV 4930(d)(2))",
      "It was on an agenda within 30 days and was continued (CIV 4930(d)(3))",
    ]);
    expect(within(guard).queryByRole("button", { name: /vote|approve/i })).not.toBeInTheDocument();
    await user.type(within(guard).getByLabelText("Topic, for the log"), "the pool gate");
    await user.click(paths[1]);
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent('Log in the minutes: "the pool gate". c text');
    expect(onAction).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith("off_agenda", { path: "c", topic: "the pool gate" });
  });

  it("puts a motion on the floor only with two different present directors, then records the vote behind a confirm that spells the tally", async () => {
    const onAction = vi.fn(async (_a: string, _b?: Record<string, unknown>) => true);
    const user = userEvent.setup();
    const { rerender } = render(<HostPanel room={roomData()} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    expect(screen.getByRole("textbox", { name: "Motion" })).toHaveValue("Move to approve the contract with Vendor A.");
    expect(screen.getByText("Choose two different directors: one moves, one seconds.")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Moved by")).queryByRole("option", { name: "H. Quinn" })).not.toBeInTheDocument(); // recused
    await user.selectOptions(screen.getByLabelText("Moved by"), "D. Okafor");
    await user.selectOptions(screen.getByLabelText("Seconded by"), "D. Okafor");
    expect(screen.queryByRole("button", { name: "Put the motion on the floor" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Seconded by"), "E. Lind");
    await user.click(screen.getByRole("button", { name: "Put the motion on the floor" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("moved by D. Okafor, seconded by E. Lind; H. Quinn recused. Threshold: majority. 4 of 5 directors present, quorum 3.");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith("motion_draft", { itemId: "landscape", title: "Renew the landscape contract", text: "Move to approve the contract with Vendor A.", mover: "D. Okafor", second: "E. Lind", recused: ["H. Quinn"], threshold: "majority" });
    // The room now holds the motion; the roll call votes by name, and "Record the vote" is a confirm.
    const motion = { id: "m1", itemId: "landscape", title: "Renew the landscape contract", text: "Move to approve the contract with Vendor A.", mover: "D. Okafor", second: "E. Lind", recused: ["H. Quinn"], threshold: "majority", votes: {}, result: "" as const, decidedAt: "", movedAt: "",
      tally: { aye: 0, no: 0, abstain: 0, recused: 1, recusedNames: ["H. Quinn"], voters: ["D. Okafor", "E. Lind", "F. Marsh"], needs: 3, answered: false, state: "open" as const, line: "" } };
    rerender(<HostPanel room={roomData({}, { motions: [motion] })} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Roll call" }));
    expect(screen.getByText("Roll call. Needs a majority of the directors present: 3 yes.")).toBeInTheDocument();
    expect(screen.getByLabelText("H. Quinn: aye")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Record the vote" })).not.toBeInTheDocument();
    await user.click(screen.getByLabelText("D. Okafor: aye"));
    await user.click(screen.getByLabelText("E. Lind: aye"));
    await user.click(screen.getByLabelText("F. Marsh: no"));
    // Counted as present, three of four are needed; not counted, two of three. The recusal rule is not on file: held.
    expect(screen.getByText(/Recused 1\. Needs 3 yes counting the recused director as present, 2 yes if not\. Held/)).toBeInTheDocument();
    expect(screen.getByText(/The two readings decide this vote differently/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record the vote" })).not.toBeInTheDocument();
    await user.click(screen.getByLabelText("F. Marsh: aye"));
    expect(screen.getByText("Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes counting the recused director as present, 2 yes if not. Carries under either reading.")).toBeInTheDocument();
    expect(screen.getByText(/H\. Quinn disclosed an interest and does not vote\. CIV 5350\(b\)/)).toBeInTheDocument();
    expect(screen.getByText(/The vote rule is not on file; ask counsel/)).toBeInTheDocument();
    onAction.mockClear();
    await user.click(screen.getByRole("button", { name: "Record the vote" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("D. Okafor aye, E. Lind aye, F. Marsh aye. Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes counting the recused director as present, 2 yes if not. Carries under either reading. Threshold: majority.");
    expect(onAction).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction.mock.calls.map((c) => c[0])).toEqual(["vote", "vote", "vote", "decide"]);
    expect(onAction).toHaveBeenLastCalledWith("decide", { motion: "m1" });
  });

  it("recites the quorum rule's words with its provision, and says what is not on file", async () => {
    const user = userEvent.setup();
    render(<HostPanel room={roomData()} onAction={vi.fn(async () => true)} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Roll call" }));
    expect(screen.getByText("A quorum is 3 (Bylaws 1.1).")).toBeInTheDocument();
    expect(screen.getByText("Bylaws 1.1, as written")).toBeInTheDocument();
    expect(screen.getByText("A majority of the Directors then in office shall constitute a quorum.")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Agenda" }));
    expect(screen.queryByText(/3 min each|3 minutes/)).not.toBeInTheDocument();
  });

  it("drafts the minutes from the log for the secretary, and shows roster not synced in the Zoom tab", async () => {
    const onMinutes = vi.fn(async (_l: MinutesLetter): Promise<string | void> => undefined);
    const user = userEvent.setup();
    render(<HostPanel room={roomData()} onAction={vi.fn(async () => true)} me="S. Clerk" onMinutes={onMinutes} legal="Sample Association" />);
    await user.click(screen.getByRole("tab", { name: "Minutes" }));
    expect(screen.getByText("Called to order.")).toBeInTheDocument();
    expect(screen.getByText("The gate sticks.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Prepare draft minutes" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("key minutes/2026-10-21, approver the secretary");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    const letter = onMinutes.mock.calls[0][0];
    expect(letter).toMatchObject({ key: "minutes/2026-10-21", approver: "the secretary", signoff: "Secretary, Sample Association" });
    expect(letter.body[0]).toContain("Present: D. Okafor, E. Lind, F. Marsh, H. Quinn. Absent: G. Petrov. A quorum is 3 directors.");
    expect(letter.body[1]).toMatch(/Called to order\.$/);
    expect(await screen.findByText(/queued in Approvals for the secretary/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Zoom" }));
    expect(screen.getByText(/roster not synced/)).toBeInTheDocument();
    expect(screen.getByText("Polls are for members' input, never for board votes. Director votes are a roll call by name (required for a meeting held entirely by teleconference, CIV 4926(a)(3)).")).toBeInTheDocument();
    expect(screen.getByText(/No executive matter is on the agenda/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start executive session" })).not.toBeInTheDocument();
  });

  it("asks for a name before any entry", () => {
    render(<HostPanel room={roomData()} onAction={vi.fn(async () => true)} me="" />);
    expect(screen.getByText(/Enter who is recording/)).toBeInTheDocument();
  });
});

// -- the executive session, kept apart (CIV 4935(e): "generally noted in the minutes") ------------------------------------

const NOTE = "member discipline (Civil Code 4935(a), (b))";
/** A room in executive session: the open log holds the general note; the executive record (when shown) the rest. */
function inSession(record: boolean): MeetingRoomData {
  const items = roomData().items.slice();
  items.splice(3, 0, EXEC_ITEM);
  return roomData({
    items,
    executive: record
      ? { shown: true, active: true, note: "", record: { date: "2026-10-21", admitted: [], sessions: [{ startedAt: "2026-10-21T19:00:00+00:00", endedAt: "", matters: [{ id: "hearing-7", subject: "member_discipline", title: SECRET_TITLE }] }],
          log: [{ at: "2026-10-21T19:01:00+00:00", title: `Item opened: ${SECRET_TITLE}` }, { at: "2026-10-21T19:05:00+00:00", title: `Motion by D. Okafor, seconded by E. Lind: ${SECRET_MOTION}` }], motions: [] } }
      : { shown: false, active: true, note: EXECUTIVE_HELD, record: null },
  }, {
    current: 3,
    executive: { active: true, startedAt: "2026-10-21T19:00:00+00:00", endedAt: "", note: NOTE, subjects: ["member_discipline"] },
    log: [{ at: "2026-10-21T18:30:00+00:00", title: "Called to order.", tone: "good" },
      { at: "2026-10-21T19:00:00+00:00", title: `The board adjourned to executive session at 12:00 PM to discuss ${NOTE}. Members left the open session.`, tone: "warn" }],
  });
}

describe("The executive session in the host panel", () => {
  it("builds the open minutes letter from the open log only: the general note, never the executive record", () => {
    const letter = minutesLetter(inSession(true), "Sample Association");
    const text = letter.body.join("\n");
    expect(text).toContain(`to discuss ${NOTE}`);
    expect(text).not.toContain(SECRET_TITLE);
    expect(text).not.toContain(SECRET_MOTION);
    expect(text).not.toContain("unit 7");
    expect(letter.body).toHaveLength(3);                                  // the heading line and the two open entries
  });

  it("shows the executive log only when the private view gives it, else the held line", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<HostPanel room={inSession(false)} onAction={vi.fn(async () => true)} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Minutes" }));
    expect(screen.getByText(EXECUTIVE_HELD)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(SECRET_TITLE);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    expect(screen.getByText(EXECUTIVE_HELD)).toBeInTheDocument();       // no motion drafted where the host could not vote on it
    unmount();
    render(<HostPanel room={inSession(true)} onAction={vi.fn(async () => true)} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Minutes" }));
    const shut = screen.getByRole("region", { name: "Executive session record" });
    expect(shut).toHaveTextContent(SECRET_MOTION);
    expect(screen.queryByText(EXECUTIVE_HELD)).not.toBeInTheDocument();
  });

  it("starts executive session only once every matter has its 4935 subject, and sends no title", async () => {
    const onAction = vi.fn(async (_a: string, _b?: Record<string, unknown>) => true);
    const user = userEvent.setup();
    const d = inSession(false);
    const data = roomData({ items: d.items }, { current: 3 });
    render(<HostPanel room={data} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Zoom" }));
    expect(screen.queryByRole("button", { name: "Start executive session" })).not.toBeInTheDocument();
    expect(screen.getByText(/name the 4935 subject first/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/Matter 2: name its 4935 subject/), "litigation");
    await user.click(screen.getByRole("button", { name: "Start executive session" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("to discuss member discipline and litigation (Civil Code 4935(a), (b))");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith("executive_start", { matters: [{ ref: "1", subject: "member_discipline" }, { ref: "2", subject: "litigation" }] });
  });

  it("words the general note as the server does", () => {
    expect(generalNote(["litigation", "personnel"])).toBe("litigation and personnel matters (Civil Code 4935(a))");
    expect(generalNote(["foreclosure"])).toBe("whether to foreclose on a lien (Civil Code 4935(d))");
    expect(generalNote(["a title", ""])).toBe("");
  });
});
