import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import type { EvidenceAnswer } from "./Evidence";
import { HostPanel, MEMBERS_PACKET_LINE, MeetingStage, type MinutesLetter } from "./MeetingStage";
import { DRIVE_BID, roomData } from "../views/meetingroom.fixture";
import { RollCall, outcome } from "./RollCall";

describe("RollCall, extended", () => {
  it("computes the tally line from present, recused, and threshold", () => {
    const o = outcome({ A: "aye", B: "aye", C: "aye" }, { present: ["A", "B", "C", "D"], recused: ["D"] });
    expect(o.line).toBe("Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes. Carries.");
    expect(outcome({ A: "aye" }, { present: ["A", "B", "C"] }).line).toBe("Yes 1 · No 0 · Abstain 0 · Recused 0. Needs 2 yes. Vote open.");
    expect(outcome({ A: "aye", B: "no", C: "no" }, { present: ["A", "B", "C"] }).state).toBe("fails");
    // Two-thirds of four voters is three; with only three of five present, every director present must agree.
    expect(outcome({ A: "aye", B: "aye", C: "no", D: "aye" }, { present: ["A", "B", "C", "D"], threshold: "two-thirds", seats: 5 }).needs).toBe(3);
    expect(outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C"], threshold: "two-thirds", seats: 5 })).toMatchObject({ needs: 3, state: "fails" });
    // The threshold counts the directors present, a recused one among them: the motion must carry without their vote.
    expect(outcome({ A: "aye", B: "aye" }, { present: ["A", "B", "C", "D"], recused: ["D"] })).toMatchObject({ needs: 3, state: "open" });
    expect(outcome({ A: "aye", B: "aye", C: "no" }, { present: ["A", "B", "C", "D"], recused: ["D"] })).toMatchObject({ needs: 3, state: "fails" });
    // Without present, everyone who voted is present; it reads the same as the plain tally.
    expect(outcome({ A: "aye", B: "abstain" })).toMatchObject({ yes: 1, abstain: 1, needs: 2, state: "fails" });
  });

  it("shows a recused row as recused with its radios off, and the tally line", () => {
    render(<RollCall directors={["A", "B", "C"]} votes={{ A: "aye", B: "aye" }} onChange={() => {}} present={["A", "B", "C"]} recused={["C"]} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[2]).getByText("recused")).toBeInTheDocument();
    expect(screen.getByLabelText("C: aye")).toBeDisabled();
    expect(screen.getByLabelText("A: aye")).toBeEnabled();
    expect(screen.queryByLabelText("A: absent")).not.toBeInTheDocument();
    expect(screen.getByText("Yes 2 · No 0 · Abstain 0 · Recused 1. Needs 2 yes. Carries.")).toBeInTheDocument();
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
    expect(screen.getByText("Yes 2 · No 1 · Abstain 0 · Recused 1. Needs 3 yes. Fails.")).toBeInTheDocument();
    await user.click(screen.getByLabelText("F. Marsh: aye"));
    expect(screen.getByText("Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes. Carries.")).toBeInTheDocument();
    onAction.mockClear();
    await user.click(screen.getByRole("button", { name: "Record the vote" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("D. Okafor aye, E. Lind aye, F. Marsh aye. Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes. Carries. Threshold: majority.");
    expect(onAction).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction.mock.calls.map((c) => c[0])).toEqual(["vote", "vote", "vote", "decide"]);
    expect(onAction).toHaveBeenLastCalledWith("decide", { motion: "m1" });
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
    expect(screen.getByText("Polls are for members' input, never for board votes. Director votes are a roll call by name (CIV 4926(a)(3)).")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start executive session" })).toBeInTheDocument();
  });

  it("asks for a name before any entry", () => {
    render(<HostPanel room={roomData()} onAction={vi.fn(async () => true)} me="" />);
    expect(screen.getByText(/Enter who is recording/)).toBeInTheDocument();
  });
});
