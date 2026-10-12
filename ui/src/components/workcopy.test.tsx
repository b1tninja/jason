/** Work screens' copy (the review of the console, October 2026): a role word that takes no article gets none, nothing is said twice,
 * and a section with nothing in it is not drawn. Made-up steps, people, and dates. */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OWNER_INFO_RUN, step as makeStep } from "../lib/work.fixtures";
import { refusalsFor, waitingWords, type StepEnable, type StepGuide, type StepNudge } from "../lib/work";
import { noRoleArticle, roleWords, roleWordsCap } from "../lib/marks";
import { theOffice } from "../lib/officeView";
import { signerWords } from "../lib/controls";
import { flaggedHow } from "./WriteRow";
import { RunRow, moveWords } from "./RunRow";
import { Recitation, missWords } from "./Recitation";
import { RunStepPanel } from "./RunStepPanel";
import { StepEnableStrip, officeWords, saysWaitsOn } from "./StepGuide";
import { TextConfirm, type Acts } from "./RunActs";
import { ROWS } from "../lib/work.fixtures";

afterEach(cleanup);

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
  authored: ["instruction"], instruction: "Read each form that has arrived.", why: "", lookAt: [], rule: [], checklist: [], requiredChecks: 0, commands: [],
  doneWhen: "", record: "", blocked: "Add a note.", notApplicable: "This step is required.", naOffered: false, skippable: false, ask: [],
  lessons: [], sop: null, inHand: [], accessNote: "", integrations: [], secondPerson: false, terminalOnly: false,
};
const VIEWER = { known: true, name: "A. Manager", actingAs: "" };
const acts: Acts = { busy: false, said: null, send: async () => true, clear: () => {} };
const panel = (s: ReturnType<typeof makeStep>) => render(<RunStepPanel step={s} run={OWNER_INFO_RUN} viewer={VIEWER} acts={acts} childHref={() => null} />);

describe("a role that takes no article", () => {
  it("names jason, the owners, and anyone as themselves and every office with 'the'", () => {
    expect(roleWords("jason")).toBe("jason");
    expect(roleWords("Jason")).toBe("jason");
    expect(roleWords("owners")).toBe("owners");
    expect(roleWords("anyone")).toBe("anyone");
    expect(roleWords("treasurer")).toBe("the treasurer");
    expect(roleWordsCap("treasurer")).toBe("The treasurer");
    expect(roleWordsCap("jason")).toBe("jason");
    expect(roleWordsCap("anyone")).toBe("Anyone");
    expect(noRoleArticle("Waiting on the jason")).toBe("Waiting on jason");
    expect(noRoleArticle("Waiting on the treasurer")).toBe("Waiting on the treasurer");
    expect(theOffice("jason")).toBe("jason");
    expect(officeWords("jason")).toBe("jason");
    expect(waitingWords({ kind: "system", word: "the jason", role: "manager", detail: "" })).toBe("Waiting on jason");
  });

  it("says 'a check for jason' and 'jason may resolve it' on a step jason holds", () => {
    panel(makeStep({ id: "oi.check", n: 3, title: "Read the inbox", kind: "check", role: "jason", state: "failed", reason: "the inbox was not readable" }));
    expect(screen.getByText("a check for jason")).toBeInTheDocument();
    expect(screen.getByText(/jason may resolve it\./)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/the jason/i);
  });

  it("keeps 'the' before an office", () => {
    panel(makeStep({ id: "oi.p", n: 3, title: "Read the inbox", kind: "check", role: "secretary", state: "failed", reason: "x" }));
    expect(screen.getByText("a check for the secretary")).toBeInTheDocument();
    expect(screen.getByText(/The secretary may resolve it\./)).toBeInTheDocument();
  });

  it("reads a row's move and the control's signers the same way", () => {
    const row = { ...ROWS[0], paused: false, group: "waiting" as const, waitingOn: { kind: "system", word: "the jason", role: "jason", detail: "" } };
    expect(moveWords(row as never)).toBe("Waiting on jason");
    render(<ul><RunRow row={row as never} /></ul>);
    expect(document.body).not.toHaveTextContent(/the jason/);
    expect(signerWords({ found: true, controls: [{}] as never, roles: ["treasurer", "jason"] } as never)).toContain("the treasurer or jason");
  });
});

describe("nothing is said twice", () => {
  it("stops a not-found sentence once, even when the server's detail ends with its own period", () => {
    const c = { found: false, citation: "CIV 5800", reason: "not_on_shelf", detail: "Fetch it with (jason export-authorities)." };
    expect(missWords(c)).toBe("Not found: CIV 5800 (not on shelf). Fetch it with (jason export-authorities).");
    expect(missWords({ ...c, detail: "Fetch it with (jason export-authorities)" })).toBe("Not found: CIV 5800 (not on shelf). Fetch it with (jason export-authorities).");
    expect(missWords({ found: false, citation: "CIV 5800" })).toBe("Not found: CIV 5800.");
    render(<Recitation citation={c} />);
    expect(document.body.textContent).not.toMatch(/\.\./);
    expect(document.body).toHaveTextContent("(jason export-authorities). Nothing is quoted.");
  });

  it("names the record in the label and says only that it is required in the hint", () => {
    render(<TextConfirm single trigger="Mark done" field="The record: the count of forms read" summary={() => <>x</>} onConfirm={() => {}} />);
    expect(screen.getAllByText(/The record: the count of forms read/)).toHaveLength(1);
    expect(screen.getByText("Required: the button stays off until this is filled in.")).toBeInTheDocument();
  });

  it("does not say which step it waits on when its own words already do", () => {
    const waits = { id: "oi.x", n: 12, title: "Close the cycle" };
    expect(saysWaitsOn({ word: "Waits on step 12.", detail: "", waitsOn: waits })).toBe(true);
    expect(saysWaitsOn({ word: "Not yet.", detail: "It waits on step 12, Close the cycle.", waitsOn: waits })).toBe(true);
    expect(saysWaitsOn({ word: "Waits on step 112.", detail: "", waitsOn: waits })).toBe(false);
    expect(saysWaitsOn({ word: "Not yet.", detail: "", waitsOn: waits })).toBe(false);
    const said = render(<StepEnableStrip enable={{ ...ENABLE, state: "not ready", word: "Waits on step 12.", waitsOn: waits }} />);
    expect(screen.queryByText(/must be done first/)).toBeNull();
    said.unmount();
    render(<StepEnableStrip enable={{ ...ENABLE, state: "not ready", word: "Not ready.", waitsOn: waits }} />);
    expect(screen.getByText("Step 12 must be done first.")).toBeInTheDocument();
  });

  it("does not say 'approved' twice in a flagged item's line", () => {
    expect(flaggedHow("approved", "approved")).toBe("as a one-off exception");
    expect(flaggedHow("rejected", "rejected")).toBe("as a one-off exception");
    expect(flaggedHow("approved", "applied")).toBe("approved as a one-off exception");
    expect(flaggedHow("held", "flagged")).toBe("kept flagged");
  });
});

describe("a section with nothing in it is not drawn", () => {
  const guided = (g: Partial<StepGuide>) => makeStep({
    id: "oi.read-forms", n: 9, of: 25, title: "Read the returned forms", kind: "person", state: "needs a person", yours: true, acts: ["attest"],
    enable: ENABLE, nudge: NUDGE, guide: { ...GUIDE, ...g },
  });

  it("leaves out Learn more when there is no procedure command and no lesson", () => {
    panel(guided({ sop: { address: "x#1", key: "x", index: 1, command: "" }, lessons: [] }));
    expect(screen.queryByRole("button", { name: /Learn more/ })).toBeNull();
    expect(screen.queryByText(/Learn more/i)).toBeNull();
  });

  it("draws it for a procedure command, or for a lesson alone", () => {
    panel(guided({ sop: { address: "x#1", key: "x", index: 1, command: "jason sop x" }, lessons: [] }));
    expect(screen.getByRole("button", { name: /Learn more/ })).toBeInTheDocument();
    cleanup();
    panel(guided({ sop: null, lessons: [{ key: "a-lesson", status: "fixed" }] }));
    expect(screen.getByRole("button", { name: /Learn more/ })).toBeInTheDocument();
  });
});

describe("what a person can do on a step that has not started", () => {
  const notStarted = makeStep({ id: "oi.record", n: 8, title: "Record what the answers say", kind: "person", state: "not started", role: "manager",
    notOffered: { attest: "This step is not started, not waiting on a person." } });

  it("says when it opens, not that it waits on nobody", () => {
    const [why] = refusalsFor(notStarted);
    expect(why.act).toBe("attest");
    expect(why.why).toBe("This step has not started. It opens for the manager when the steps it needs are done; there is nothing to do on it yet.");
    expect(why.why).not.toMatch(/not waiting on a person/);
  });

  it("leaves the server's sentence where it is true or where the step is not a person's", () => {
    const wait = makeStep({ id: "oi.w", n: 2, title: "Wait", kind: "wait", state: "not started", role: "manager", notOffered: { attest: "x", arrived: "The wait is not open." } });
    expect(refusalsFor(wait).find((r) => r.act === "arrived")?.why).toBe("The wait is not open.");
    const done = makeStep({ id: "oi.d", n: 2, title: "Done", kind: "person", state: "done", role: "manager", notOffered: { attest: "This step is done, not waiting on a person." } });
    expect(refusalsFor(done).find((r) => r.act === "attest")?.why).toBe("This step is done, not waiting on a person.");
  });

  it("draws that sentence in the panel", () => {
    panel(notStarted);
    expect(screen.getByText(/It opens for the manager when the steps it needs are done/)).toBeInTheDocument();
  });
});
