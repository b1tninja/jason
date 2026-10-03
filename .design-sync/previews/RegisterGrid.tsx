import { Card, RegisterGrid } from "jason-ui";

/** The vendor register: jason's columns from the records, the board's columns editable per kind. */
const columns = [
  { name: "Vendor", owner: "jason" as const, kind: "text" as const, choices: [] },
  { name: "Service", owner: "jason" as const, kind: "text" as const, choices: [] },
  { name: "Last invoice", owner: "jason" as const, kind: "money" as const, choices: [] },
  { name: "Contract ends", owner: "board" as const, kind: "date" as const, choices: [] },
  { name: "Standing", owner: "board" as const, kind: "choice" as const, choices: ["keep", "rebid", "end"] },
  { name: "Insured", owner: "board" as const, kind: "checkbox" as const, choices: [] },
  { name: "Portal", owner: "board" as const, kind: "link" as const, choices: [] },
];

const rows = [
  { Vendor: "Greenway Landscape", Service: "landscaping", "Last invoice": 2450, "Contract ends": "2027-03-31", Standing: "keep", Insured: true, Portal: "https://example.com/greenway" },
  { Vendor: "Clearwater Pools", Service: "pool service", "Last invoice": 680, "Contract ends": "2026-12-31", Standing: "rebid", Insured: true, Portal: "" },
  { Vendor: "Summit Roofing", Service: "roof repair", "Last invoice": 18000, "Contract ends": "", Standing: "", Insured: false, Portal: "", pendingSync: true, pendingColumns: ["Standing"] },
  { Vendor: "Delta Elevator", Service: "elevator maintenance", "Last invoice": 1320.5, "Contract ends": "2027-06-30", Standing: "keep", Insured: true, Portal: "https://example.com/delta" },
];

const log = [
  { seen: "2026-10-02T21:10:00Z", key: "Clearwater Pools", column: "Standing", before: "keep", after: "rebid", by: "M. Chen" },
  { seen: "2026-10-03T15:02:00Z", key: "Summit Roofing", column: "Insured", before: true, after: false, by: "D. Okafor" },
];

/** The full register with a name entered: jason's cells plain, each board cell with its edit link, one row pending sync, the log open. */
export const Vendors = () => <RegisterGrid registerKey="vendors" columns={columns} rows={rows} log={log} by="D. Okafor" />;

/** Fewer columns and no log: a short register, the log details collapsed. */
export const Compact = () => (
  <RegisterGrid
    registerKey="committees"
    columns={[
      { name: "Committee", owner: "jason", kind: "text", choices: [] },
      { name: "Members", owner: "jason", kind: "number", choices: [] },
      { name: "Chair", owner: "board", kind: "text", choices: [] },
      { name: "Active", owner: "board", kind: "checkbox", choices: [] },
    ]}
    rows={[
      { Committee: "Landscape", Members: 4, Chair: "Reyes", Active: true },
      { Committee: "Architectural review", Members: 3, Chair: "Patel", Active: true },
      { Committee: "Social", Members: 2, Chair: "", Active: false },
    ]}
    log={[]}
    by="D. Okafor"
  />
);

/** In a card, as the registers page shows each register under its Sheet link. */
export const InCard = () => (
  <Card title="Vendors">
    <p className="muted">The Sheet is the board's copy; an edit here is saved in the snapshot and logged, and the Sheet catches up at the next sync.</p>
    <RegisterGrid registerKey="vendors" columns={columns.slice(0, 5)} rows={rows.slice(0, 2)} log={log.slice(0, 1)} by="D. Okafor" />
  </Card>
);
