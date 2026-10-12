/** The second batch of console review fixes: nothing is said twice (an overdue clock, a "no date yet", a badge and its muted line), a
 * fragment is a sentence, a held run shows a general title, and the remedy note keeps its glyph in a column of its own. Made-up data. */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { HELD_ROW, ITEM_CLOCKS, ITEM_IDS, ROWS, step as makeStep } from "../lib/work.fixtures";
import { PAYMENT_SIGNERS, KIND_NOTICES } from "../lib/controls.fixtures";
import type { RunClock } from "../lib/work";
import { ClockStrip } from "./ClockStrip";
import { ControlNotice, effectWords } from "./ControlNotice";
import { ControlRow, sameAsBadge } from "./ControlRow";
import { ChangedSince } from "./ChangedSince";
import { ItemTable, RemedyNote } from "./RunItems";
import { RunRow, rowLabel } from "./RunRow";

afterEach(cleanup);

describe("an overdue legal clock says it once", () => {
  const clock = (over: Partial<RunClock> = {}): RunClock => ({
    key: "oi.resend", step: "oi.resend", label: "Resend by", due: "2099-10-05", status: "overdue", days: -7, cite: "EX 123.4", past: true,
    stepTitle: "Resend", scope: "step", basis: "law", basisLabel: "LEGAL", legal: true, proposed: false, ...over,
  });

  it("shows the date's own 'overdue' and no second status word beside it", () => {
    const { container } = render(<ClockStrip clocks={[clock()]} today={new Date("2099-10-12T12:00:00Z")} />);
    const head = container.querySelector(".work-clock-head")!;
    expect(head.textContent!.match(/overdue/gi)).toHaveLength(1);
  });

  it("still shows another status word, and an overdue clock that has no date", () => {
    const due = render(<ClockStrip clocks={[clock({ status: "due", due: "2099-10-12", days: 0, past: false })]} today={new Date("2099-10-12T12:00:00Z")} />);
    expect([...due.container.querySelectorAll(".work-clock-head .badge")].map((b) => b.textContent)).toContain("due");
    due.unmount();
    const undated = render(<ClockStrip clocks={[clock({ due: null })]} />);
    expect([...undated.container.querySelectorAll(".work-clock-head .badge")].map((b) => b.textContent)).toContain("overdue");
  });
});

describe("an item with a clock and no date says 'no date yet' once", () => {
  const items = ITEM_IDS.slice(0, 2).map((item) => ({ item, state: "needs a person" }));
  const stepWith = makeStep({ id: "ri.decide", n: 2, title: "Decide each request", kind: "person", items, itemAware: true, perItem: true });

  it("drops the 'no date' beside the clock's own words", () => {
    const [a, b] = ITEM_CLOCKS.slice(5, 7);
    const clocks: RunClock[] = [
      { ...a, item: ITEM_IDS[0], step: "ri.decide", due: null, status: "undated", days: null, past: false },
      { ...b, item: ITEM_IDS[1], step: "ri.decide" },
    ];
    const { container } = render(<ItemTable step={stepWith} clocks={clocks} />);
    const first = container.querySelectorAll("tbody tr")[0];
    expect(first.textContent).toMatch(/no date yet/);
    expect(first.textContent).not.toMatch(/no date no date/);
    expect((first.textContent!.match(/no date/g) ?? [])).toHaveLength(1);
    expect(container.querySelectorAll("tbody tr")[1].textContent).not.toMatch(/no date/);
  });

  it("keeps 'no date' where the item has no clock at all", () => {
    const { container } = render(<ItemTable step={stepWith} clocks={[{ ...ITEM_CLOCKS[5], item: ITEM_IDS[1], step: "ri.decide" }]} />);
    expect(container.querySelectorAll("tbody tr")[0].textContent).toMatch(/no clock/);
  });
});

describe("a remedy note", () => {
  it("keeps its glyph in a column of its own, the words and the button in the other", () => {
    const { container } = render(<RemedyNote step={{ remedy: "ri.fix", remedyOf: undefined }} steps={[{ id: "ri.fix", n: 3, title: "Fix it" }]} onGo={() => {}} />);
    const note = container.querySelector(".work-remedy")!;
    expect(note.children).toHaveLength(2);
    expect(note.children[0].tagName.toLowerCase()).toBe("svg");
    expect(note.children[1]).toHaveClass("work-remedy-body");
    expect(note.children[1]).toHaveTextContent("Step 3, Fix it, is its remedy");
    expect(screen.getByRole("button", { name: "Go to the remedy" })).toBeInTheDocument();
  });
});

describe("a control's notice", () => {
  it("makes the effect a sentence and capitalises a waiting control's reason", () => {
    expect(effectWords("signers: 2")).toBe("Signers needed: 2.");
    expect(effectWords("first class")).toBe("First class.");
    expect(effectWords("Two signers.")).toBe("Two signers.");
    const { container } = render(<ControlNotice data={KIND_NOTICES} />);
    expect(container).toHaveTextContent("Signers needed: 2.");
    expect(container).not.toHaveTextContent("signers: 2");
    const waiting = container.querySelector(".control-notice-waiting")!;
    expect(waiting).toHaveTextContent("adopted on 2099-10-03. Adopted, not in force until 2099-11-14.");
  });
});

describe("an adopted control row does not say its standing twice", () => {
  it("compares the badge's words with the line under it", () => {
    expect(sameAsBadge("adopted, in force", "adopted, in force")).toBe(true);
    expect(sameAsBadge("Adopted, in force.", "adopted, in force")).toBe(true);
    expect(sameAsBadge("adopted, in force since 2099-09-20", "adopted, in force")).toBe(false);
    expect(sameAsBadge("adopted, in force", undefined)).toBe(false);
  });

  it("drops the muted line when it only repeats the badge, and keeps one that says more", () => {
    const same = render(<ul><ControlRow row={{ ...PAYMENT_SIGNERS, stateWord: "adopted, in force" }} /></ul>);
    expect(same.container.querySelector(".control-row-words")).toBeNull();
    same.unmount();
    const more = render(<ul><ControlRow row={PAYMENT_SIGNERS} /></ul>);
    expect(more.container.querySelector(".control-row-words")).toHaveTextContent("adopted, in force since 2099-09-20");
  });
});

describe("a held run's label", () => {
  it("is the general title when it has no label of its own, never its opaque id", () => {
    const held = { ...HELD_ROW, label: "" };
    expect(rowLabel(held)).toBe("A member's hearing");
    render(<ul><RunRow row={held} /></ul>);
    expect(screen.getByRole("link")).not.toHaveTextContent(held.id);
    expect(screen.getByRole("link")).toHaveTextContent("A member's hearing");
  });

  it("keeps a label, and an ordinary run falls back to its id", () => {
    expect(rowLabel(HELD_ROW)).toBe(HELD_ROW.label);
    expect(rowLabel({ ...ROWS[0], label: "" })).toBe(ROWS[0].id);
  });
});

describe("the changed-since banner", () => {
  it("offers 'Go to the step' as a button.link inside .work-changed, which the stylesheet makes a link", () => {
    render(<ChangedSince onGo={() => {}} changed={[{ step: "oi.read", n: 6, stepTitle: "Read the forms", address: "file:a/b.json", was: "aa11bb22", now: "cc33dd44", at: "2099-10-10T00:00:00Z", pending: false } as never]} />);
    const go = screen.getByRole("button", { name: "Go to the step" });
    expect(go).toHaveClass("link");
    expect(go.closest(".work-changed")).not.toBeNull();
  });
});
