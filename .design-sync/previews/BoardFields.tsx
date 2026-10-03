import { BoardFields } from "jason-ui";

/** The board's four fields on an action item (`BoardItem`); jason's own columns live elsewhere. */
const item = {
  id: "reserve-roof-2",
  title: "Building 2 roof repair: reserve transfer",
  summary: "The roof over units 5-8 leaks at the parapet; the bid is $18,000 and the operating account cannot cover it.",
  ask: "Decide whether to borrow from reserves and on what repayment schedule.",
  category: "Reserves",
  priority: "high",
  status: "on agenda",
  authority: "CIV 5515",
  evidence: ["Drive/Maintenance/roof-bid-2026-09.pdf", "Drive/Finance/reserve-balance-2026-09.pdf"],
  session: "open",
  special_notice: "",
  due: "2026-10-21",
  opened: "2026-09-16",
  owner: "M. Chen",
  meeting: "2026-10-21",
  notes: "Treasurer to bring a 12-month repayment schedule.",
  source: "digest",
  history: ["2026-09-16: opened from the digest", "2026-09-30: status, meeting changed by the board"],
};

/** Idle: the fields as saved, nothing changed, so the foot says "No changes." */
export const Idle = () => <BoardFields item={item} onSaved={() => {}} today="2026-10-03" />;

/** A new item with every board field blank; the status select still shows the first status. */
export const Blank = () => (
  <BoardFields item={{ ...item, id: "pool-fence-gate", title: "Pool fence gate latch", status: "open", owner: "", meeting: "", notes: "", history: ["2026-10-02: opened from a request"] }} onSaved={() => {}} today="2026-10-03" />
);

/** A profile that uses its own statuses. */
export const CustomStatuses = () => (
  <BoardFields item={{ ...item, status: "waiting on bid" }} statuses={["new", "waiting on bid", "scheduled", "done"]} onSaved={() => {}} today="2026-10-03" />
);
