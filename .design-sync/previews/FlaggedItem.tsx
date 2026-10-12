import { useEffect, useRef, type ReactNode } from "react";
import { FlaggedItem } from "jason-ui";

// One flagged change from an approvals plan (held for the board by jason's policy finding). Made-up: Oakview, "A. Owner",
// "A. Manager", a sample rule row, 2099 dates, fake fingerprints. The item is a closed disclosure; a cell that shows what a
// reviewer sees opens it after mount (no prop does).
const APPROVAL = { id: "apr-20991001T090000-ab12", fingerprint: "f12f68bc95107ae48a4247a73ab578d6bd8a324fdb64e6aead6cc6ea4e418b59" };

const ITEM = {
  id: "item-1", op: "unit tag -", target: "unit:1", label: "101 Example Way: A. Owner", value: "Rental", group: "101 Example Way: A. Owner",
  why: "says owner-occupied; the unit is tagged Rented out: held for the board by the response policy (sample-occupancy-vs-tag)",
  rule: "sample_rules.RULES: sample-occupancy-vs-tag", class: "held_for_board", boardItem: "sample-board-item",
  basis: "4cd8072d3d4c7b2b49bc8218e77e4462c9236566a3b7826acecb5ffeaa791549", dependsOn: [], highStakes: false, costCents: 0,
  decision: "undecided", decidedBy: "", decidedAt: "", reason: "", result: "pending", resultDetail: "",
  evidence: [{ label: "PayHOA request 1", address: "payhoa:submission:1" }, { label: "Board item sample-board-item", address: "board-item:sample-board-item" }],
  change: { op: "remove", field: "unit tags", value: "Rental", before: "Rental", after: "", text: "- Rental (unit tags)" },
} as any;

const HISTORY = [
  { at: "2099-09-10T15:00:00+00:00", approval: "apr-20990910T150000-cd34", item: "item-9", finding: "sample-occupancy-vs-tag", by: "A. Manager", decision: "approved", reason: "Owner confirmed in writing", secondBy: "A. Secretary", applied: true },
  { at: "2099-09-24T16:30:00+00:00", approval: "apr-20990924T163000-ef56", item: "item-7", finding: "sample-occupancy-vs-tag", by: "A. Director", decision: "held", reason: "Waiting on the owner's reply" },
  { at: "2099-10-01T09:20:00+00:00", approval: APPROVAL.id, item: "item-4", finding: "sample-occupancy-vs-tag", by: "A. Manager", decision: "rejected", reason: "Unit is still rented per the lease on file" },
] as any;

/** Opens the item's disclosure once mounted, since the component keeps it closed. */
function Opened({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.querySelectorAll("details").forEach((d) => { d.open = true; }); }, []);
  return <div ref={ref} style={{ maxWidth: 760 }}>{children}</div>;
}

const boardHref = (id: string) => `#/actions/${id}`;

/** A reviewer's view while the plan is open: the change, why it is flagged and the rule, evidence, the board item, no exceptions yet, and the four ways to act (disabled until a reason is written). */
export const OpenForDecision = () => (
  <Opened><FlaggedItem item={ITEM} approval={APPROVAL} me="A. Manager" editable boardHref={boardHref} /></Opened>
);

/** The finding has been decided by exception three times: the nudge says the board may want a rule, and the history lists who decided what (read-only, so the cell shows it whole). */
export const NudgeAndHistory = () => (
  <Opened>
    <FlaggedItem item={{ ...ITEM, evidence: [], exceptionCount: 3, exceptions: HISTORY }} approval={APPROVAL} me="A. Manager" boardHref={boardHref} nudge={2} />
  </Opened>
);

/** Decided as a one-off exception and read-only: the decision, who made it, the reason, and that a second person still signs. */
export const DecidedApproved = () => (
  <Opened>
    <FlaggedItem approval={APPROVAL} boardHref={boardHref}
      item={{ ...ITEM, exception: true, decision: "approved", decidedBy: "A. Manager", decidedAt: "2099-10-02T10:15:00+00:00", reason: "Owner confirmed in writing", exceptionCount: 1, exceptions: [{ ...HISTORY[0], approval: APPROVAL.id, item: "item-1", secondBy: "", applied: false, at: "2099-10-02T10:15:00+00:00" }] }} />
  </Opened>
);

/** Not yet referred to the board and no one signed in: no board item exists, and the item says decisions open only while the plan is open. */
export const ReadOnlyNoBoardItem = () => (
  <Opened><FlaggedItem item={{ ...ITEM, boardItem: "", evidence: ITEM.evidence.slice(0, 1) }} approval={APPROVAL} /></Opened>
);

/** The plan's list view of a decided item: the disclosure is closed and its summary says what was decided. */
export const CollapsedSummary = () => (
  <div style={{ maxWidth: 760 }}>
    <FlaggedItem approval={APPROVAL} item={{ ...ITEM, exception: true, decision: "rejected", decidedBy: "A. Manager", decidedAt: "2099-10-02T10:15:00+00:00", reason: "Unit is still rented per the lease on file", exceptionCount: 1 }} />
  </div>
);
