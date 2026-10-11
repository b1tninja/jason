/// <reference types="vite/client" />
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import { ApplyButton, ApplyPrefsNote, PauseHold } from "./ApplyPanel";
import { OfficeRowItem } from "./OfficeLens";
import { PlanReview } from "./PlanReview";
import { holdClock, listState, typedCountProblem, waitingWords, type ApplyHold, type ApplyPrefs, type Approval, type KindFacts } from "../lib/approvals";

const NOW = "2026-10-03T19:00:00+00:00";
const A = { name: "A Manager", at: NOW, fingerprint: "f", role: "manager", via: "console" as const };
const KIND: KindFacts = {
  key: "payhoa-attach-bills", title: "Bills", system: "payhoa", risk: "R1", riskWords: "private outside jason",
  approver: "one person", twoPerson: false, reversible: "a person deletes the attachment", maxAgeHours: 6,
};

/** Every approvable change marked approved and the plan signed by A Manager: waiting to be applied. */
function signed(): Approval {
  const a = structuredClone(plannedJson) as unknown as Approval;
  for (const i of a.items) if (i.class === "approvable") Object.assign(i, { decision: "approved", decidedBy: "A Manager", decidedAt: NOW, highStakes: false });
  return { ...a, status: "approved", first: A };
}

const rows = (over: Partial<Record<string, string>> = {}) => (["where", "who", "pause", "typed", "reminder"] as const).map((setting) => ({
  setting, title: { where: "Where apply happens", who: "Who may apply", pause: "A pause before apply", typed: "A typed count", reminder: "A reminder for a signed plan" }[setting],
  words: over[setting] ?? `words for ${setting}`, default: true, source: "the default; the board has not adopted one", controls: [],
}));
const PREFS = (more: Partial<ApplyPrefs> = {}): ApplyPrefs => ({
  kind: "payhoa-attach-bills", where: "terminal", who: "board_or_manager", pauseMinutes: 0, pauseUntilNextDay: false, typedCountOver: null,
  reminderHours: 24, consoleFloor: "", consoleFloored: false, consoleAllowed: false, clash: "", rows: rows(), waiting: [], ...more,
});
const CONSOLE = PREFS({ where: "console", consoleAllowed: true });
const HOLD: ApplyHold = { endsAt: "2026-10-03T19:30:00+00:00", secondsLeft: 1800, words: "Apply is offered after the pause the board adopted. Until then the plan can be withdrawn." };

afterEach(() => { vi.useRealTimers(); });

describe("the default is a terminal: a console button only where the board adopted one", () => {
  it("offers no Apply button and says where apply is when the board has not adopted a console button, though the server allows apply", () => {
    render(<PlanReview approval={signed()} me="A Manager" now={NOW} kind={KIND} onApply={vi.fn()} prefs={PREFS()} />);
    expect(screen.queryByRole("button", { name: /^Apply/ })).toBeNull();
    expect(screen.getByText(/Apply is at a terminal\. words for where/)).toBeInTheDocument();
    expect(screen.getByText("A person applies this at a terminal:")).toBeInTheDocument();
    expect(screen.getByText(/jason approvals apply apr-20261003T183801-4f5b --yes --by "A Manager"/)).toBeInTheDocument();
  });

  it("offers the button where the board adopted a console button and the kind allows it", async () => {
    const onApply = vi.fn(async () => {});
    const user = userEvent.setup();
    const a = signed();
    render(<PlanReview approval={a} me="A Manager" now={NOW} kind={KIND} onApply={onApply} prefs={CONSOLE} />);
    await user.click(screen.getByRole("button", { name: /^Apply 12 changes to PayHOA now/ }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onApply).toHaveBeenCalledWith({ by: "A Manager", confirm: a.fingerprint });
  });

  it("never offers a button for a kind applied only at a terminal, whatever the preferences say", () => {
    const mail: KindFacts = { ...KIND, key: "payhoa-mailroom-send", terminalOnly: true, cli: "jason mailroom --send --yes --expect FINGERPRINT --approval ID" };
    render(<PlanReview approval={signed()} me="A Manager" now={NOW} kind={mail} onApply={vi.fn()} prefs={CONSOLE} />);
    expect(screen.queryByRole("button", { name: /^Apply/ })).toBeNull();
  });

  it("keeps the old behavior for a caller that passes no preferences", () => {
    render(<PlanReview approval={signed()} me="A Manager" now={NOW} kind={KIND} onApply={vi.fn()} />);
    expect(screen.getByRole("button", { name: /^Apply 12 changes to PayHOA now/ })).toBeInTheDocument();
  });
});

describe("the plan's effective preferences, in words", () => {
  it("lists the five settings, each with where it comes from, and the one adopted but not in force yet", () => {
    const adopted = PREFS({ rows: rows({ pause: "A pause of 30 minutes after the last signature." }).map((r) => r.setting === "pause" ? { ...r, default: false, source: "the board adopted this on 2026-10-01" } : r), waiting: [{ control: "c", setting: "typed-count-over", why: "adopted, not in force until 2026-11-01" }] });
    const { container } = render(<ApplyPrefsNote prefs={adopted} />);
    const list = container.querySelector(".plan-prefs-list") as HTMLElement;
    expect([...list.querySelectorAll("li[data-setting]")].map((li) => li.getAttribute("data-setting"))).toEqual(["where", "who", "pause", "typed", "reminder"]);
    expect(within(list).getByText("A pause of 30 minutes after the last signature.", { exact: false })).toBeInTheDocument();
    expect(within(list).getByText("(the board adopted this on 2026-10-01)")).toBeInTheDocument();
    expect(within(list).getByText(/adopted, not in force until 2026-11-01/)).toBeInTheDocument();
    expect(container).toHaveTextContent("None lowers a signature count or removes a control");
  });

  it("is silent when the server sent no preferences", () => {
    expect(render(<ApplyPrefsNote prefs={null} />).container).toBeEmptyDOMElement();
  });
});

describe("a pause before apply", () => {
  it("counts down, offers Withdraw beside it, and offers no Apply until it ends", () => {
    render(<PlanReview approval={signed()} me="A Manager" now={NOW} kind={KIND} onApply={vi.fn()} onWithdraw={vi.fn()} prefs={CONSOLE} hold={HOLD} />);
    const hold = screen.getByRole("group", { name: "Pause before apply" });
    expect(hold).toHaveTextContent("Held for 30:00 more.");
    expect(hold).toHaveTextContent(HOLD.words);
    expect(within(hold).getByText("Withdraw this plan")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Apply/ })).toBeNull();
    expect(screen.queryByText(/jason approvals apply/)).toBeNull();                 // the command waits for the pause too
    expect(screen.getByText(/Held by the board's pause until 2026-10-03 19:30 UTC/)).toBeInTheDocument();
    expect(screen.getAllByText("Withdraw this plan")).toHaveLength(1);
  });

  it("ticks each second and reads the plan again when the pause ends", () => {
    vi.useFakeTimers();
    const onElapsed = vi.fn();
    render(<PauseHold hold={{ ...HOLD, secondsLeft: 3 }} onElapsed={onElapsed} />);
    expect(screen.getByRole("timer")).toHaveTextContent("00:03");
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByRole("timer")).toHaveTextContent("00:01");
    expect(onElapsed).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(onElapsed).toHaveBeenCalledTimes(1);
  });

  it("shows the Apply button once the server says there is no hold", () => {
    render(<PlanReview approval={signed()} me="A Manager" now={NOW} kind={KIND} onApply={vi.fn()} prefs={CONSOLE} hold={null} />);
    expect(screen.getByRole("button", { name: /^Apply 12 changes/ })).toBeInTheDocument();
  });

  it("formats the clock", () => {
    expect([holdClock(0), holdClock(59), holdClock(1800), holdClock(3725)]).toEqual(["00:00", "00:59", "30:00", "1:02:05"]);
  });
});

describe("a typed count over the board's number", () => {
  it("asks for the count before Apply is available, refuses a wrong one, and sends the right one", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<ApplyButton typedCount={{ needed: true, over: 5, changes: 12 }} summary={<p>sure?</p>} onConfirm={onConfirm}>Apply 12 changes</ApplyButton>);
    const field = screen.getByLabelText("Type the number of changes this plan makes, to apply it");
    const button = screen.getByRole("button", { name: "Apply 12 changes" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    await user.click(button);
    expect(screen.getByRole("alert")).toHaveTextContent("Type the number of changes this plan makes (12) to apply it.");
    await user.type(field, "11");
    await user.click(screen.getByRole("button", { name: "Apply 12 changes" }));
    expect(screen.getByRole("alert")).toHaveTextContent("11 is not the number of changes this plan makes.");
    await user.clear(field);
    await user.type(field, "12");
    await user.click(screen.getByRole("button", { name: "Apply 12 changes" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onConfirm).toHaveBeenCalledWith(12);
  });

  it("asks for nothing at or under the board's number, and sends no count", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<ApplyButton typedCount={{ needed: false, over: 12, changes: 12 }} summary={<p>sure?</p>} onConfirm={onConfirm}>Apply 12 changes</ApplyButton>);
    expect(screen.queryByLabelText(/Type the number of changes/)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Apply 12 changes" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onConfirm).toHaveBeenCalledWith(undefined);
  });

  it("is carried through the plan's apply dialog as the count", async () => {
    const onApply = vi.fn(async () => {});
    const user = userEvent.setup();
    const a = signed();
    render(<PlanReview approval={a} me="A Manager" now={NOW} kind={KIND} onApply={onApply} prefs={CONSOLE} typedCount={{ needed: true, over: 5, changes: 12 }} />);
    await user.type(screen.getByLabelText(/Type the number of changes/), "12");
    await user.click(screen.getByRole("button", { name: /^Apply 12 changes to PayHOA now/ }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(onApply).toHaveBeenCalledWith({ by: "A Manager", confirm: a.fingerprint, count: 12 });
  });

  it("checks the typed count before the server does", () => {
    const tc = { needed: true, over: 5, changes: 12 };
    expect([typedCountProblem(tc, ""), typedCountProblem(tc, "12"), typedCountProblem(tc, " 12 "), typedCountProblem(tc, "1x"), typedCountProblem({ ...tc, needed: false }, ""), typedCountProblem(null, "")])
      .toEqual(["Type the number of changes this plan makes (12) to apply it.", "", "", "1x is not the number of changes this plan makes.", "", ""]);
  });
});

describe("the reminder", () => {
  const WAIT = { waitingToApply: true, waitingHours: 30, waitingStale: false, terminalOnly: false };

  it("adds reminder due to the waiting words, in the list and nowhere else, when the server says it is due", () => {
    expect(waitingWords({ ...WAIT, reminderDue: true })).toBe("Signed, waiting to be applied · 30 hours · reminder due");
    expect(waitingWords({ ...WAIT, reminderDue: false })).toBe("Signed, waiting to be applied · 30 hours");
    expect(waitingWords({ ...WAIT, terminalOnly: true, reminderDue: true })).toBe("Signed, waiting to be applied · 30 hours · applied at the terminal · reminder due");
    expect(listState({ status: "approved", ...WAIT, reminderDue: true })).toMatch(/reminder due$/);
  });

  it("marks a waiting row on Today as reminder due, and as held by a pause", () => {
    const row = { type: "plan-to-apply", id: "apr-1", kind: "x", title: "A sample plan", office: "", waitingHours: 30, stale: false, terminalOnly: false, needsSecond: false, note: "", screen: "approvals", text: "A sample plan: signed, waiting to be applied · 30 hours", reminderDue: true, pausing: true };
    render(<ul><OfficeRowItem row={row as never} /></ul>);
    expect(screen.getByText("reminder due")).toBeInTheDocument();
    expect(screen.getByText("held by the board's pause")).toBeInTheDocument();
  });
});
