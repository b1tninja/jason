import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { OWNER_INFO_RUN, step as makeStep } from "../lib/work.fixtures";
import type { EnableState, GuideLook, StepEnable, StepGuide, StepNudge } from "../lib/work";
import { useActs, type Acts } from "./RunActs";
import { RunStepPanel } from "./RunStepPanel";
import { ENABLE_LOOK, StepEnableStrip, StepNudgeLine, daysWords } from "./StepGuide";

// The step panel's guide, enable strip, and nudge line (docs/console/screens/work-guide.md). Made-up steps, people, and dates.

const NUDGE: StepNudge = {
  band: "quiet", word: "", due: null, days: null, basis: "", basisLabel: "", legal: false, proposed: false, label: "", cite: "", openDays: null,
  escalatedTo: null, escalatedWhy: "", snoozable: true, items: null,
  numbers: { leadDays: 14, afterHours: 168, escalateAfterHours: 72, adopted: false, note: "proposed, not the law's" }, claim: null,
};
const ENABLE: StepEnable = {
  state: "ready", word: "Yours: you hold the manager office. Nothing is missing.", holders: [{ office: "manager", names: ["A. Manager"], vacant: false }],
  missing: [], secondPerson: false, terminalOnly: false, youHold: ["manager"], owner: "A. Manager", inHand: [], accessNote: "",
};
const GUIDE: StepGuide = {
  authored: ["instruction", "rule", "checklist", "look-at"], instruction: "Read each form that has arrived and confirm the reading when it is right.",
  why: "An answer counts only once a person confirms the reading.",
  lookAt: [
    { label: "Forms that arrived", kind: "read", read: "responses-new", count: 4, rows: ["payhoa:1042", "payhoa:1043"], refs: [], asOf: "2099-10-20",
      unavailable: "", screen: { key: "responses", name: "Responses", href: "#/responses" } },
    { label: "Forms read and not confirmed", kind: "read", read: "responses-unconfirmed", count: null, rows: [], refs: [], asOf: "2099-10-20", unavailable: "the inbox is not readable" },
  ],
  rule: [{ key: "CIV 9999(b)", kind: "statute", words: "The operative words, whole.", version: "the words in force on 2099-10-20", source: "Example Legislature",
    reading: "Answers are entered before the reports go out.", readingLabel: "jason's reading", missing: "", caveats: [],
    restatement: "jason's consolidated text is not an official restatement.", command: "", versions: [] }],
  checklist: [{ text: "Each reading matches the form", required: true }, { text: "A form for the wrong unit is set aside", required: false },
              { text: "Nothing is marked an answer until you confirm", required: true }],
  requiredChecks: 2,
  commands: [
    { text: "jason responses --list --new", raw: "jason responses --list --new", note: "", terminalOnly: false, fillIn: [] },
    { text: 'jason responses --read ID --by "A. Manager"', raw: "jason responses --read ID --by NAME", note: "", terminalOnly: false, fillIn: ["ID"] },
  ],
  doneWhen: "The count of forms read and not confirmed is 0.", record: "the arrivals read (a count)", blocked: "Add a note naming the form id and what is wrong with it.",
  notApplicable: "This step is required: it has no not-applicable outcome.", naOffered: false, skippable: false,
  ask: [{ office: "manager", names: ["A. Manager"], vacant: false }, { office: "president", names: [], vacant: true }],
  lessons: [{ key: "returns-by-the-same-rules", status: "fixed" }],
  sop: { address: "owner-info-cycle#14", key: "owner-info-cycle", index: 14, command: "jason sop owner-info-cycle" },
  inHand: ["the response inbox open"], accessNote: "", integrations: [], secondPerson: false, terminalOnly: false,
};

const STEP = makeStep({
  id: "oi.read-forms", n: 9, of: 25, title: "Read the returned forms", kind: "person", state: "needs a person", yours: true, acts: ["attest"],
  needsRecord: "the arrivals read", enable: ENABLE, nudge: NUDGE, guide: GUIDE,
});
const VIEWER = { known: true, name: "A. Manager", actingAs: "" };
const acts = (over: Partial<Acts> = {}): Acts => ({ busy: false, said: null, send: async () => true, clear: () => {}, ...over });
const panel = (s = STEP, a: Acts = acts()) =>
  render(<RunStepPanel step={s} run={OWNER_INFO_RUN} viewer={VIEWER} acts={a} childHref={() => null} />);

beforeEach(() => { resetServerSession(); window.localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetServerSession(); });

describe("the enable strip", () => {
  const states = Object.keys(ENABLE_LOOK) as EnableState[];

  it.each(states)("draws %s as a word and a glyph", (state) => {
    const { container } = render(<StepEnableStrip enable={{ ...ENABLE, state, word: `Words for ${state}.` }} />);
    expect(screen.getByText(state)).toBeInTheDocument();
    expect(screen.getByText(`Words for ${state}.`)).toBeInTheDocument();
    expect(container.querySelector("svg[data-glyph]")).not.toBeNull();                      // never colour alone
  });

  it("names a vacant office, the backup as a proposal, and what is missing without a credential", () => {
    render(<StepEnableStrip enable={{
      ...ENABLE, state: "needs an integration", word: "Needs The Example signed in.",
      holders: [{ office: "treasurer", names: [], vacant: true, backup: { office: "president", names: [], basis: "proposed, not the law's" } }],
      missing: [{ what: "The Example", why: "The Example is needs sign-in", fix: "jason integrations check example --live" }],
    }} />);
    expect(screen.getByText("No one holds the treasurer office.")).toBeInTheDocument();
    expect(screen.getByText(/Backup: the president \(proposed, not the law's\)/)).toBeInTheDocument();
    expect(screen.getByText("jason integrations check example --live")).toBeInTheDocument();
  });
});

describe("the nudge line", () => {
  const legal: StepNudge = { ...NUDGE, band: "legal", word: "LEGAL", due: "2099-10-23", days: 0, basis: "law", basisLabel: "LEGAL", legal: true, snoozable: false,
    escalatedTo: "the whole board", escalatedWhy: "a legal date falls today or has passed" };

  it("says LEGAL with its date, its basis, and no snooze", () => {
    render(<StepNudgeLine nudge={legal} />);
    expect(screen.getByText("2099-10-23")).toBeInTheDocument();
    expect(screen.getAllByText("LEGAL").length).toBeGreaterThanOrEqual(2);                    // the word, and the basis pill
    expect(screen.getByText("due today")).toBeInTheDocument();
    expect(screen.queryByText(/snooze/i)).toBeNull();
    expect(screen.getByText(/Also seen by the whole board/)).toHaveTextContent("Nothing is sent to anyone.");
  });

  it("counts days in words and labels a proposed number as a proposal", () => {
    expect(daysWords(3)).toBe("3 days to go");
    expect(daysWords(-6)).toBe("6 days late");
    expect(daysWords(1)).toBe("1 day to go");
    render(<StepNudgeLine nudge={{ ...NUDGE, band: "soon", word: "due soon", due: "2099-10-23", days: 3, basis: "documents", basisLabel: "DOCUMENTS" }} />);
    expect(screen.getByText("due soon")).toBeInTheDocument();
    expect(screen.getByText(/are proposed, not the law's\./)).toBeInTheDocument();
  });

  it("is one line with a count for a step that repeats per item, and shows who is on it", () => {
    render(<StepNudgeLine nudge={{ ...NUDGE, band: "late", word: "OVERDUE", due: "2099-10-14", days: -6, basis: "person", basisLabel: "PERSON",
      items: { total: 14, notDone: 3, earliest: "2099-10-14" }, claim: { by: "A. Manager", at: "2099-10-09T10:00:00Z", stale: true, mine: false } }} />);
    expect(screen.getByText("3 of 14 items not done; the earliest due 2099-10-14.")).toBeInTheDocument();
    expect(screen.getByText(/A. Manager is on it since/)).toHaveTextContent("2099-10-09, still open.");
  });

  it("says a date is needed and does not call it late", () => {
    render(<StepNudgeLine nudge={{ ...NUDGE, band: "date", word: "needs a date" }} />);
    expect(screen.getByText("A clock needs a date, and none is set.")).toBeInTheDocument();
    expect(screen.queryByText(/late/)).toBeNull();
  });
});

describe("the guided step panel", () => {
  it("draws the sections in the page's order, with the fixed headings", () => {
    panel();
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent?.replace(/\s*\(.*\)\s*$/, "").trim());
    const wanted = ["Do this", "Look at", "The rule", "Check before you go on", "The command", "Done when", "If you are blocked", "If it does not apply", "Ask", "Learn more", "What you can do"];
    expect(names.filter((n) => wanted.includes(n ?? ""))).toEqual(wanted);
    expect(screen.getByText("Read each form that has arrived and confirm the reading when it is right.")).toBeInTheDocument();
    expect(screen.getByText("Yours: you hold the manager office. Nothing is missing.")).toBeInTheDocument();
  });

  it("shows a read's count and its handles, and says 'could not read' for one that failed, with no count", () => {
    panel();
    const ok = screen.getByText("Forms that arrived").closest(".guide-look")!;
    expect(within(ok as HTMLElement).getByText("4")).toBeInTheDocument();
    expect(within(ok as HTMLElement).getByRole("link", { name: "Open in Responses" })).toHaveAttribute("href", "#/responses");
    expect(within(ok as HTMLElement).getByText("payhoa:1042")).toBeInTheDocument();
    const bad = screen.getByText("Forms read and not confirmed").closest(".guide-look")!;
    expect(bad).toHaveTextContent("could not read: the inbox is not readable");
    expect(bad.querySelector(".guide-count-number")).toBeNull();
    expect(screen.queryByText(/nothing to look at/i)).toBeNull();
  });

  it("recites the rule whole before jason's reading, labeled, and says so when the words are not on the shelf", () => {
    const { rerender } = panel();
    const words = screen.getByText("The operative words, whole.");
    const reading = screen.getByText("Answers are entered before the reports go out.");
    expect(words.compareDocumentPosition(reading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText("jason's reading")).toBeInTheDocument();
    const missing = { ...GUIDE, rule: [{ ...GUIDE.rule[0], words: "", missing: "The words of CIV 9999(b) are not on the shelf here.", command: "jason export-authorities" }] };
    rerender(<RunStepPanel step={{ ...STEP, guide: missing }} run={OWNER_INFO_RUN} viewer={VIEWER} acts={acts()} childHref={() => null} />);
    expect(screen.getByText(/The words of CIV 9999\(b\) are not on the shelf here\./)).toBeInTheDocument();
    expect(screen.getByText("jason export-authorities")).toBeInTheDocument();
    expect(screen.queryByText("The operative words, whole.")).toBeNull();
  });

  it("copies the filled command, marks what is left to fill in, and never runs anything", async () => {
    const write = vi.fn(async () => {});
    vi.stubGlobal("navigator", { clipboard: { writeText: write } });
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    panel();
    expect(screen.getByText('jason responses --read ID --by "A. Manager"')).toBeInTheDocument();
    expect(screen.getByText("ID is yours to fill in.")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Copy command" })[1]);
    expect(write).toHaveBeenCalledWith('jason responses --read ID --by "A. Manager"');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("holds Mark done until each required item is ticked, and records what was checked", async () => {
    const send = vi.fn(async () => true);
    panel(STEP, acts({ send }));
    const mark = screen.getByRole("button", { name: "Mark done" });
    expect(mark).toBeDisabled();
    expect(screen.getByText(/Mark done waits: 2 of 2 required items are not ticked/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /Each reading matches the form \(required\)/ }));
    expect(screen.getByRole("button", { name: "Mark done" })).toBeDisabled();
    expect(screen.getByText(/1 of 2 required ticked/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /Nothing is marked an answer until you confirm \(required\)/ }));
    await userEvent.click(screen.getByRole("button", { name: "Mark done" }));
    await userEvent.type(screen.getByLabelText("The record: the arrivals read"), "7 arrivals");
    await userEvent.click(screen.getByRole("button", { name: "Mark done" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(send).toHaveBeenCalledWith(expect.objectContaining({ act: "attest", step: "oi.read-forms", record: "7 arrivals",
      what: "Read the returned forms; checked: 2 of 2 required" }));
  });

  it("keeps an unrequired tick in the browser only, and works when storage throws", async () => {
    panel();
    await userEvent.click(screen.getByRole("checkbox", { name: /A form for the wrong unit is set aside/ }));
    expect(window.localStorage.getItem("jason.guide.run-0a1b2c3d4e.oi.read-forms.A form for the wrong unit is set aside")).toBe("1");
    expect(Object.keys(window.localStorage).some((k) => k.includes("Each reading matches"))).toBe(false);          // a required tick is never kept
    cleanup();
    const real = Object.getOwnPropertyDescriptor(window, "localStorage");
    const boom = () => { throw new Error("blocked"); };
    Object.defineProperty(window, "localStorage", { configurable: true, value: { getItem: boom, setItem: boom, removeItem: boom } });
    try {
      panel();
      await userEvent.click(screen.getByRole("checkbox", { name: /A form for the wrong unit is set aside/ }));
      expect(screen.getByRole("checkbox", { name: /A form for the wrong unit is set aside/ })).toBeChecked();
    } finally {
      if (real) Object.defineProperty(window, "localStorage", real);
    }
  });

  it("offers 'I'm on it' as a note in the viewer's name, and Release to the one who claimed it", async () => {
    const send = vi.fn(async () => true);
    const { unmount } = panel(STEP, acts({ send }));
    await userEvent.click(screen.getByRole("button", { name: "I'm on it" }));
    expect(screen.getByText(/It assigns nothing; anyone who holds the step may still act\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(send).toHaveBeenCalledWith({ act: "claim", step: "oi.read-forms" });
    unmount();
    panel({ ...STEP, nudge: { ...NUDGE, claim: { by: "A. Manager", at: "2099-10-09T10:00:00Z", stale: false, mine: true } } }, acts({ send }));
    expect(screen.getByText(/You are on it since/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Release" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(send).toHaveBeenLastCalledWith({ act: "claim", step: "oi.read-forms", release: true });
  });

  it("offers no claim to a person who does not hold the step, or while an admin views as someone else", () => {
    const { unmount } = render(<RunStepPanel step={{ ...STEP, yours: false, acts: [], enable: { ...ENABLE, state: "not yours", word: "Waiting on the manager." } }}
      run={OWNER_INFO_RUN} viewer={VIEWER} acts={acts()} childHref={() => null} />);
    expect(screen.queryByRole("button", { name: "I'm on it" })).toBeNull();
    expect(screen.getByText("Waiting on the manager.")).toBeInTheDocument();
    expect(screen.getByText("Read each form that has arrived and confirm the reading when it is right.")).toBeInTheDocument();    // the words stay readable
    unmount();
    render(<RunStepPanel step={STEP} run={OWNER_INFO_RUN} viewer={{ ...VIEWER, actingAs: "Someone Else" }} acts={acts()} childHref={() => null} />);
    expect(screen.queryByRole("button", { name: "I'm on it" })).toBeNull();
  });

  it("is a collapsible region you can reach by keyboard, collapsed to its heading and count on a phone", async () => {
    const narrow = vi.fn().mockImplementation((query: string) => ({ matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {} }));
    vi.stubGlobal("matchMedia", narrow);
    panel();
    const toggle = screen.getByRole("button", { name: /Look at/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveTextContent("Look at (2 reads)");
    expect(screen.getByText("Read each form that has arrived and confirm the reading when it is right.")).toBeVisible();        // Do this never collapses
    toggle.focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: /Look at/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Forms that arrived")).toBeVisible();
  });

  it("is open on a wide screen and collapsed once the step is done, with the record shown by the strip", () => {
    panel();
    expect(screen.getByRole("button", { name: /Look at/ })).toHaveAttribute("aria-expanded", "true");
    cleanup();
    panel({ ...STEP, state: "done", yours: false, acts: [], enable: { ...ENABLE, state: "done", word: "Done by A. Manager on 2099-10-09." } });
    expect(screen.getByRole("button", { name: /Look at/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Done by A. Manager on 2099-10-09.")).toBeInTheDocument();
  });

  it("says a step is terminal-only and still asks for the record before it can be marked", () => {
    panel({ ...STEP, enable: { ...ENABLE, state: "terminal only", word: "A person does this at a terminal.", terminalOnly: true } });
    expect(screen.getByText("A person does this at a terminal.")).toBeInTheDocument();
    expect(screen.getByText(/Run the command first, then record the reference it gives here\./)).toBeInTheDocument();
  });

  it("draws a step with no guide as it was: why, look at, the command, and no guide sections", () => {
    const plain = makeStep({ id: "oi.plain", n: 4, title: "A plain step", kind: "person", state: "needs a person", yours: true, acts: ["attest"],
      why: "A reason.", command: "jason example --run", evidence: [{ address: "file:a/b.json", kept: null, now: "aa11", changed: false, present: true }] });
    panel(plain);
    for (const h of ["Why", "Look at", "Command"]) expect(screen.getByRole("heading", { level: 3, name: h })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 3, name: "Do this" })).toBeNull();
    expect(screen.queryByText(/proposed, not the law's/)).toBeNull();
  });

  it("says the legal step cannot be skipped and offers no snooze", () => {
    const legal = { ...STEP, legal: true, skip: null, nudge: { ...NUDGE, band: "legal" as const, word: "LEGAL", due: "2099-10-23", days: 0, basis: "law", basisLabel: "LEGAL", legal: true, snoozable: false } };
    panel(legal);
    expect(screen.getByText("Skip is not offered: this step is required by the law.")).toBeInTheDocument();
    expect(screen.queryByText(/snooze/i)).toBeNull();
  });

  it("posts a claim through the writer with the run's n and shows the server's refusal as given", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token" }), { status: 200, headers: { "Content-Type": "application/json" } });
      expect(JSON.parse(String(init?.body))).toEqual({ act: "claim", step: "oi.read-forms", expect: OWNER_INFO_RUN.n });
      return new Response(JSON.stringify({ error: "A. Manager is already on oi.read-forms" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }));
    function Harness() {
      const a = useActs(OWNER_INFO_RUN, () => {});
      return <RunStepPanel step={STEP} run={OWNER_INFO_RUN} viewer={VIEWER} acts={a} childHref={() => null} />;
    }
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "I'm on it" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A. Manager is already on oi.read-forms");
  });
});

describe("a read that has a look", () => {
  it("keeps its type honest", () => {
    const look: GuideLook = { label: "L", kind: "read", read: "r", count: 0, rows: [], refs: [], asOf: "2099-01-01", unavailable: "" };
    expect(look.count).toBe(0);                                                                    // a zero is a count, not 'nothing to look at'
  });
});
