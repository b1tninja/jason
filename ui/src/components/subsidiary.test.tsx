import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HostPanel, MeetingStage, motionFor, motionWord, type MeetingRoomData, type Motion } from "./MeetingStage";
import { EXEC_ITEM, SECRET_TITLE, roomData } from "../views/meetingroom.fixture";
import { script, stageContent } from "../views/MeetingRoomView";

// Table, continue, and refer are motions the board votes on by roll call; withdraw is the mover's act before the vote.
// Made-up directors and items only.

const tally = (over: Partial<Motion["tally"]> = {}): Motion["tally"] => ({ aye: 0, no: 0, abstain: 0, recused: 0, recusedNames: [], voters: ["D. Okafor", "E. Lind", "F. Marsh", "H. Quinn"], needs: 3, answered: false, state: "open", line: "", ...over });
const MAIN: Motion = { id: "m1", itemId: "landscape", title: "Renew the landscape contract", text: "Move to approve the contract with Vendor A.", mover: "D. Okafor", second: "E. Lind",
  recused: [], threshold: "majority", votes: {}, result: "", decidedAt: "", movedAt: "", tally: tally(), kind: "main", appliesTo: "" };
const TABLE: Motion = { ...MAIN, id: "m2", text: "Move to table this item.", mover: "F. Marsh", second: "H. Quinn", kind: "table", appliesTo: "m1" };
const withMotions = (motions: Motion[]): MeetingRoomData => roomData({}, { motions });
const action = () => vi.fn(async (_a: string, _b?: Record<string, unknown>) => true);

describe("Subsidiary motions in the host panel", () => {
  it("offers table, continue, and refer against the motion on the floor, each put on the floor with a mover and a second", async () => {
    const onAction = action();
    const user = userEvent.setup();
    render(<HostPanel room={withMotions([MAIN])} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    const floor = screen.getByRole("group", { name: "On the floor" });
    expect(within(floor).getByRole("button", { name: "Move to table" })).toBeInTheDocument();
    expect(within(floor).getByRole("button", { name: "Move to refer" })).toBeInTheDocument();
    await user.click(within(floor).getByRole("button", { name: "Move to continue" }));
    expect(screen.getByRole("textbox", { name: "Motion" })).toHaveValue("Move to continue this item to the meeting of [date].");
    // No main-motion templates while drafting against the motion on the floor.
    expect(within(screen.getByRole("group", { name: "Common motions" })).queryByRole("button", { name: "Adopt a resolution" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Moved by"), "F. Marsh");
    await user.selectOptions(screen.getByLabelText("Seconded by"), "D. Okafor");
    expect(screen.getByText("Name the later meeting's date.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Put the motion on the floor" })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("To the meeting of"), "2026-11-18");
    await user.click(screen.getByRole("button", { name: "Put the motion on the floor" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("The board votes on it by roll call; carried, the item is continued to the meeting of 2026-11-18, and the motion on the floor goes with it.");
    expect(onAction).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith("motion_draft", expect.objectContaining({ itemId: "landscape", kind: "continue", meeting: "2026-11-18", mover: "F. Marsh", second: "D. Okafor", threshold: "majority" }));
  });

  it("a motion to refer names whom it goes to before it can be moved", async () => {
    const onAction = action();
    const user = userEvent.setup();
    render(<HostPanel room={roomData()} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    await user.click(screen.getByRole("button", { name: "Refer to a committee or a person" }));
    await user.selectOptions(screen.getByLabelText("Moved by"), "D. Okafor");
    await user.selectOptions(screen.getByLabelText("Seconded by"), "E. Lind");
    expect(screen.getByText("Name the committee or the person it goes to.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Referred to/), "the landscape committee");
    await user.click(screen.getByRole("button", { name: "Put the motion on the floor" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith("motion_draft", expect.objectContaining({ kind: "refer", to: "the landscape committee" }));
  });

  it("withdraw is the mover's logged act: one confirm, no roll call", async () => {
    const onAction = action();
    const user = userEvent.setup();
    render(<HostPanel room={withMotions([MAIN])} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    await user.click(screen.getByRole("button", { name: "Withdraw (the mover, before the vote)" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("D. Okafor, the mover, withdrew");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction.mock.calls).toEqual([["withdraw", { motion: "m1", name: "D. Okafor" }]]);
  });

  it("votes the motion to table first, by roll call, and says what it does when carried", async () => {
    const onAction = action();
    const user = userEvent.setup();
    render(<HostPanel room={withMotions([MAIN, TABLE])} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    expect(screen.getByText(/On the floor \(motion to table\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Move to refer" })).not.toBeInTheDocument();   // one at a time
    await user.click(screen.getByRole("tab", { name: "Roll call" }));
    expect(screen.getByText(/Roll call on the motion to table:/)).toBeInTheDocument();
    for (const n of ["D. Okafor", "E. Lind", "F. Marsh"]) await user.click(screen.getByLabelText(`${n}: aye`));
    await user.click(screen.getByLabelText("H. Quinn: no"));
    await user.click(screen.getByRole("button", { name: "Record the vote" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent('Carried, the item is tabled and stays on the board\'s list for a later motion to take it from the table; the decision\'s outcome is "tabled".');
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction.mock.calls.map((c) => c[0])).toEqual(["vote", "vote", "vote", "vote", "decide"]);
    expect(onAction).toHaveBeenLastCalledWith("decide", { motion: "m2" });
  });

  it("holds a subsidiary vote the two recusal readings decide differently", async () => {
    const user = userEvent.setup();
    render(<HostPanel room={withMotions([{ ...TABLE, appliesTo: "", recused: ["H. Quinn"] }])} onAction={action()} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Roll call" }));
    await user.click(screen.getByLabelText("D. Okafor: aye"));
    await user.click(screen.getByLabelText("E. Lind: aye"));
    await user.click(screen.getByLabelText("F. Marsh: no"));
    expect(screen.getByText(/The two readings decide this vote differently/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record the vote" })).not.toBeInTheDocument();
  });

  it("drafts against an executive motion on its own matter, in the executive record", async () => {
    const onAction = action();
    const user = userEvent.setup();
    const items = roomData().items.slice();
    items.splice(3, 0, { ...EXEC_ITEM, executiveMatters: [{ ref: "1", subject: "member_discipline", general: "member discipline", named: true, id: "hearing-7", title: SECRET_TITLE }] });
    const x1: Motion = { ...MAIN, id: "x1", itemId: "hearing-7", title: SECRET_TITLE, text: "Move to fine the owner." };
    const data = roomData({ items, executive: { shown: true, active: true, note: "", record: { date: "2026-10-21", admitted: [], sessions: [], log: [], motions: [x1] } } },
      { current: 3, executive: { active: true, startedAt: "2026-10-21T19:00:00+00:00", endedAt: "", note: "member discipline (Civil Code 4935(a), (b))" } });
    render(<HostPanel room={data} onAction={onAction} me="S. Clerk" />);
    await user.click(screen.getByRole("tab", { name: "Motion" }));
    await user.click(screen.getByRole("button", { name: "Move to table" }));
    await user.selectOptions(screen.getByLabelText("Moved by"), "F. Marsh");
    await user.selectOptions(screen.getByLabelText("Seconded by"), "H. Quinn");
    await user.click(screen.getByRole("button", { name: "Put the motion on the floor" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("Logged in the executive session record, kept apart from the open minutes.");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onAction).toHaveBeenCalledWith("motion_draft", expect.objectContaining({ itemId: "hearing-7", kind: "table" }));
  });
});

describe("The stamp after the vote", () => {
  const carried: Motion[] = [{ ...MAIN, result: "tabled", disposedBy: "m2" }, { ...TABLE, result: "carried", tally: tally({ aye: 3, no: 1 }) }];

  it("names the motion's own word", () => {
    expect(motionWord(carried[1])).toBe("tabled");
    expect(motionWord({ ...TABLE, kind: "refer", result: "carried" })).toBe("referred");
    expect(motionWord({ ...TABLE, result: "failed" })).toBe("failed");
    expect(motionWord({ ...MAIN, result: "carried" })).toBe("carried");
    expect(motionWord({ ...TABLE, result: "withdrawn" })).toBe("withdrawn");
    expect(motionWord(MAIN)).toBe("");
    // The latest motion still on the floor is the one voted first.
    expect(motionFor(withMotions([MAIN, TABLE]).room, roomData().items[2])?.id).toBe("m2");
  });

  it("shows the stamp on the stage, in the agenda, and in the caption", async () => {
    const d = withMotions(carried);
    const item = d.items[2];
    const content = stageContent(d, item, {}, 0, 0);
    expect(content).toMatchObject({ kind: "motion", word: "tabled", heading: "Motion to table" });
    const { container, unmount } = render(<MeetingStage wordmark="S" item={{ label: item.label, title: item.title }} content={content} caption="" progress={0} />);
    expect(container.querySelector('.stamp[data-word="tabled"]')).not.toBeNull();
    expect(screen.getByText(/Carried, 3–1–0: the item is tabled/)).toBeInTheDocument();
    unmount();
    expect(script(d, item)).toContain("The motion to table carried, 3–1–0. The item is tabled");
    render(<HostPanel room={d} onAction={action()} me="S. Clerk" />);
    expect(screen.getByRole("img", { name: "Tabled" })).toBeInTheDocument();
  });

  it("a withdrawn motion shows withdrawn, with no tally", () => {
    const d = withMotions([{ ...MAIN, result: "withdrawn", withdrawnBy: "D. Okafor" }]);
    expect(stageContent(d, d.items[2], {}, 0, 0)).toMatchObject({ word: "withdrawn", result: "Withdrawn by the mover before the vote." });
    expect(script(d, d.items[2])).toContain("The motion was withdrawn by the mover before the vote.");
  });
});
