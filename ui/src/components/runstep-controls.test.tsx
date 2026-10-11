import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import type { StepControl } from "../lib/controls";
import { OWNER_INFO_RUN, step as makeStep } from "../lib/work.fixtures";
import { ControlStepNotice } from "./ControlNotice";
import { useActs, type Acts } from "./RunActs";
import { RunStepPanel } from "./RunStepPanel";

// The "required by a control" line on a workflow step (docs/console/screens/controls.md): one line for each gate an adopted
// control adds, in the engine's own sentence, linking to the control; silent when the step carries none; and the writer's
// refusal shown as it is given. Made-up steps and controls throughout.

const RESOLUTION: StepControl = {
  key: "contracts", title: "Contract authorization", gate: "resolution", state: "in force", effective: "2099-01-01",
  why: "a control the board adopted on 2099-01-01 requires a board resolution on record before this step: cite the id of the decision recorded in Decisions in the record",
};
const SECOND: StepControl = {
  key: "confirm", title: "Second-person confirmation", gate: "second", state: "in force", effective: "2099-01-01", firstBy: "A. Manager",
  why: "a control the board adopted on 2099-01-01 requires a second, different person to confirm this step",
};
const SOON: StepControl = {
  key: "recorder", title: "Recorder", gate: "roles", state: "waiting", effective: "2100-01-01", roles: ["secretary"],
  why: "a control the board adopted on 2099-01-01 will allow, from 2100-01-01, only the secretary to record this step",
};
const LACKS: StepControl = {
  key: "confirm", title: "Second-person confirmation", gate: "second", state: "refused", effective: "2099-01-01",
  why: "a control the board adopted on 2099-01-01 requires a second, different person to confirm this step; the roster lacks a second manager",
};

const STEP = makeStep({ id: "ex.2", n: 2, title: "Send the example notice", kind: "person", state: "needs a person", yours: true, acts: ["attest"] });
const VIEWER = { known: true, name: "A. Manager", actingAs: "" };
const acts = (over: Partial<Acts> = {}): Acts => ({ busy: false, said: null, send: async () => true, clear: () => {}, ...over });

beforeEach(() => resetServerSession());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetServerSession(); });

describe("ControlStepNotice", () => {
  it("says nothing for a step with no controls", () => {
    const { container, rerender } = render(<ControlStepNotice controls={undefined} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ControlStepNotice controls={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names each gate in the engine's sentence, with the control's title linking to its card", () => {
    render(<ControlStepNotice controls={[RESOLUTION, SECOND]} />);
    const note = screen.getByRole("complementary", { name: "Required by a control" });
    const lines = within(note).getAllByText(/Required by a control:/);
    expect(lines).toHaveLength(2);
    expect(note).toHaveTextContent("A control the board adopted on 2099-01-01 requires a board resolution on record before this step");
    expect(note).toHaveTextContent("A control the board adopted on 2099-01-01 requires a second, different person to confirm this step.");
    expect(within(note).getByRole("link", { name: "Contract authorization" })).toHaveAttribute("href", "#/controls?key=contracts");
    expect(within(note).getByRole("link", { name: "Second-person confirmation" })).toHaveAttribute("href", "#/controls?key=confirm");
    expect(note).toHaveTextContent("A. Manager made the first; a different person confirms.");
  });

  it("shows a control whose date has not come as not yet required, and never as required", () => {
    render(<ControlStepNotice controls={[SOON]} />);
    const note = screen.getByRole("complementary", { name: "Required by a control" });
    expect(note).toHaveTextContent("Takes effect 2100-01-01; not yet required: Recorder.");
    expect(note.textContent).not.toMatch(/Required by a control:/);
  });

  it("shows a control in force that the roster cannot satisfy as a refusal", () => {
    render(<ControlStepNotice controls={[LACKS]} />);
    const refused = screen.getByRole("note");
    expect(refused).toHaveTextContent("Refused:");
    expect(refused).toHaveTextContent("the roster lacks a second manager");
    expect(refused).toHaveTextContent("A control never falls back to fewer.");
  });
});

describe("RunStepPanel with controls", () => {
  const panel = (s = STEP, a: Acts = acts()) =>
    render(<RunStepPanel step={s} run={OWNER_INFO_RUN} viewer={VIEWER} acts={a} childHref={() => null} />);

  it("shows the control's line on the step that carries it, above the step's why", () => {
    panel({ ...STEP, why: "The notice goes out once.", controls: [RESOLUTION] });
    const section = screen.getByRole("heading", { level: 2, name: "2. Send the example notice" }).closest("section")!;
    const note = within(section).getByRole("complementary", { name: "Required by a control" });
    expect(note).toHaveTextContent("requires a board resolution on record");
    expect(note.compareDocumentPosition(within(section).getByText("The notice goes out once."))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("is silent when the step has no controls", () => {
    panel(STEP);
    expect(screen.queryByRole("complementary", { name: "Required by a control" })).toBeNull();
  });

  it("shows the writer's refusal sentence, as it is given, when the act is refused", async () => {
    const sentence = `${RESOLUTION.why}`;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token" }), { status: 200, headers: { "Content-Type": "application/json" } });
      expect(init?.method).toBe("POST");
      return new Response(JSON.stringify({ error: sentence }), { status: 400, headers: { "Content-Type": "application/json" } });
    }));
    function Harness() {
      const a = useActs(OWNER_INFO_RUN, () => {});
      return <RunStepPanel step={{ ...STEP, controls: [RESOLUTION] }} run={OWNER_INFO_RUN} viewer={VIEWER} acts={a} childHref={() => null} />;
    }
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Mark done" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(sentence);
  });
});
