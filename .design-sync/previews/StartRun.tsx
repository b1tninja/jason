import { useEffect, useRef, type ReactNode } from "react";
import { StartRun } from "jason-ui";

// Made-up definitions for "Oakview". Nothing is posted until a person types: the Idle, NoDates, NotStartable and ViewingAs cells
// need no stub. The Checked cells type into the form on mount, and the dry run they trigger answers from the stub below (there is no
// server in the capture; the shape is `StartDry`).
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  if (url.startsWith("/api/session")) return json({ token: "", header: "X-Jason-Token" });
  if (url.startsWith("/api/write/work/") && url.endsWith("/start")) {
    const body = JSON.parse(String(init?.body ?? "{}"));
    const d = body.dates ?? {};
    const bad = d.answer_by && d.send && d.answer_by < d.send;
    return json({
      ok: !bad, dryRun: true, definition: body.definition,
      problems: bad ? [`answer_by may not come before send: Answers by ${d.answer_by} is before Send on ${d.send}.`] : [],
    });
  }
  return realFetch(input, init);
}) as typeof fetch;

/** Type into the real form the way a person would, so the form's own checks run. */
function Typing({ values, children }: { values: Record<string, string>; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = box.current;
    if (!root) return;
    const t = setTimeout(() => {
      for (const [sel, value] of Object.entries(values)) {
        const el = root.querySelector<HTMLInputElement>(sel);
        if (!el) continue;
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(el, value);
        el.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }, 30);
    return () => clearTimeout(t);
  }, []);
  return <div ref={box}>{children}</div>;
}
const def = (over: object): any => ({
  subjectKind: "campaign", steps: 12, phases: [{ key: "a", title: "Prepare", steps: 4 }], dates: [], legalClock: false, procedure: "",
  procedureSteps: null, drift: { ok: true, why: [] }, cadence: "", startable: true, startedBy: [], needsYes: false,
  roles: ["manager"], mySteps: true, lessons: [], ...over,
});

const DEFINITIONS = [
  def({
    key: "owner-info-cycle", title: "Owner information cycle", family: "members", steps: 25, procedure: "owner-info-cycle", procedureSteps: 25,
    legalClock: true, needsYes: true, cadence: "yearly",
    dates: [
      { name: "answer_by", label: "Answers by", required: true, after: "send", rule: "May not come before the send date." },
      { name: "send", label: "Send on", required: true, after: "" },
    ],
  }),
  def({ key: "respond", title: "Respond to a request", family: "members", steps: 14, procedure: "respond", procedureSteps: 14, subjectKind: "request" }),
  def({ key: "bill-attach", title: "Bill attachment", family: "money", steps: 7, procedure: "bill-attach", procedureSteps: 7, subjectKind: "bill" }),
  def({
    key: "hearing", title: "Hearing", family: "members", steps: 9, startable: false, startedBy: ["manager", "secretary"], mySteps: false,
    startableWhy: "Only the manager or the secretary starts a hearing.",
  }),
];

const noop = () => {};
const frame = { maxWidth: 560 } as const;
// The card is a column card (config.json viewport 1000x1400), so the tall form shows whole at full size.
const tall = frame;

/** The form before anything is chosen: one select, grouped by family. The rest of the form appears with a definition. */
export const Idle = () => (
  <div style={frame}><StartRun definitions={DEFINITIONS} by="A. Manager" onStarted={noop} /></div>
);

/** A definition with a legal clock and two dates: each date shows its rule, and the start waits on a plain yes. */
export const WithDatesAndLegalClock = () => (
  <div style={tall}><StartRun definitions={DEFINITIONS} initial="owner-info-cycle" by="A. Manager" onStarted={noop} /></div>
);

/** A definition with no dates: a subject, an optional name, and the Start control. */
export const NoDates = () => (
  <div style={frame}><StartRun definitions={DEFINITIONS} initial="bill-attach" by="A. Manager" onStarted={noop} /></div>
);

/** A definition the viewer may not start: the engine's own sentence says why, and the Start control stays unavailable. */
export const NotStartable = () => (
  <div style={frame}><StartRun definitions={DEFINITIONS} initial="hearing" by="A. Manager" onStarted={noop} /></div>
);

/** An administrator viewing as someone else cannot start a run: it is recorded in a person's own name. */
export const ViewingAs = () => (
  <div style={frame}><StartRun definitions={DEFINITIONS} by="A. Manager" actingAs="A. Owner" onStarted={noop} /></div>
);

/** Typed and checked: the dates pass their rule, and the legal-clock yes is the one thing still needed. */
export const CheckedAndPassing = () => (
  <div style={tall}>
    <Typing values={{ 'input[type="text"]': "campaign:OI-2099", 'input[id$="-answer_by"]': "2099-11-20", 'input[id$="-send"]': "2099-10-20" }}>
      <StartRun definitions={DEFINITIONS} initial="owner-info-cycle" by="A. Manager" debounceMs={0} onStarted={noop} />
    </Typing>
  </div>
);

/** Typed and checked, and a date breaks its rule: the sentence shows beside the date it names, and Start stays unavailable. */
export const CheckedWithProblem = () => (
  <div style={tall}>
    <Typing values={{ 'input[type="text"]': "campaign:OI-2099", 'input[id$="-answer_by"]': "2099-10-01", 'input[id$="-send"]': "2099-10-20" }}>
      <StartRun definitions={DEFINITIONS} initial="owner-info-cycle" by="A. Manager" debounceMs={0} onStarted={noop} />
    </Typing>
  </div>
);
