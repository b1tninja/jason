import { ItemTable } from "jason-ui";

// A step that repeats over a set (made-up: Oakview's member requests). `RunStep` / `RunClock` are not exported types, so the
// props are cast from literals that carry the fields the table reads.
const step = (over: any): any => ({
  id: "ri.decide", n: 4, of: 7, title: "Decide each request", kind: "person", state: "running", perItem: true, itemAware: true, itemSet: "requests", items: [], ...over,
});
const clock = (item: string, status: string, days: number | null, due: string | null, basis = "person", basisLabel = "PERSON"): any => ({
  key: `ri.decide[${item}]`, step: "ri.decide", item, label: "Reply to the request", due, status, days, cite: "", past: status === "overdue", stepTitle: "Decide each request", scope: "step",
  basis, basisLabel, legal: false, proposed: false,
});

const wide = { maxWidth: 760 } as const;

const timedItems = [
  { item: "req:01", state: "done" }, { item: "req:02", state: "done" }, { item: "req:03", state: "running" },
  { item: "req:04", state: "needs a person" }, { item: "req:05", state: "waiting" },
];
const timedClocks = [
  clock("req:01", "satisfied", -4, "2099-10-05"), clock("req:02", "satisfied", -2, "2099-10-07"), clock("req:03", "upcoming", 2, "2099-10-11"),
  clock("req:04", "due", 0, "2099-10-09"), clock("req:05", "upcoming", 7, "2099-10-16"),
];

/** Each item of the step: its opaque id, its state word, its own clock with whose date it is, and the date in words. A roll-up line sits over the table. */
export const WithClocks = () => <div style={wide}><ItemTable step={step({ items: timedItems })} clocks={timedClocks} /></div>;

/** A late item is a word and a glyph beside its date, never colour alone; a failed and a skipped item are counted in the roll-up. */
export const LateAndFailed = () => (
  <div style={wide}>
    <ItemTable
      step={step({ items: [{ item: "req:01", state: "done" }, { item: "req:02", state: "failed" }, { item: "req:03", state: "needs a person" }, { item: "req:04", state: "skipped" }, { item: "req:05", state: "ready" }] })}
      clocks={[clock("req:01", "satisfied", -6, "2099-10-03"), clock("req:03", "overdue", -3, "2099-10-06", "law", "LEGAL"), clock("req:05", "upcoming", 5, "2099-10-14")]} />
  </div>
);

/** Items with no clock of their own show only the item and its state. */
export const Untimed = () => (
  <div style={wide}>
    <ItemTable step={step({ items: [{ item: "unit:101", state: "done" }, { item: "unit:102", state: "done" }, { item: "unit:103", state: "ready" }, { item: "unit:104", state: "not started" }] })} clocks={[]} />
  </div>
);

/** A step over a set with no items yet says so and what it waits for. */
export const NoItemsYet = () => <div style={wide}><ItemTable step={step({ items: [] })} clocks={[]} /></div>;

/** The empty sentence can be the page's own. */
export const NoItemsOwnWords = () => (
  <div style={wide}><ItemTable step={step({ items: [], itemSet: "" })} clocks={[]} empty="No requests came in this cycle, so there is nothing to decide." /></div>
);
