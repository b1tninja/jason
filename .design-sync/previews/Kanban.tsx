import { Badge, Card, DueDate, Kanban, Pill } from "jason-ui";

type Item = { id: string; status: string; priority: string; category: string; title: string; ask: string; due?: string; executive?: boolean };

const LANES = ["open", "proposed", "on agenda", "in progress", "deferred"] as const;

const items: Item[] = [
  { id: "1", status: "open", priority: "urgent", category: "insurance", title: "Master policy renews with a 32% premium increase", ask: "Approve the renewal quote or direct the broker to bid it out.", due: "2026-10-10" },
  { id: "2", status: "open", priority: "normal", category: "records", title: "Owner request for the 2025 general ledger", ask: "Confirm the ten-business-day response (CIV 5210).", due: "2026-10-14" },
  { id: "3", status: "proposed", priority: "high", category: "reserves", title: "Pool deck resurfacing bid, three quotes in hand", ask: "Select a bidder and fund from reserves ($41,500).", due: "2026-10-28" },
  { id: "4", status: "on agenda", priority: "normal", category: "rules", title: "Parking rule change: 28-day comment period closed", ask: "Adopt, amend, or withdraw the proposed rule (CIV 4360).", due: "2026-10-21" },
  { id: "5", status: "on agenda", priority: "high", category: "collections", title: "Unit 14 delinquency at $2,340, pre-lien notice sent", ask: "Vote to record a lien, in open session by roll call (CIV 5673).", due: "2026-10-21", executive: false },
  { id: "6", status: "in progress", priority: "normal", category: "maintenance", title: "Elevator annual inspection, permit expired", ask: "None yet; vendor scheduled for 10/08.", due: "2026-10-08" },
  { id: "7", status: "deferred", priority: "low", category: "landscaping", title: "Drought-tolerant conversion of the east bed", ask: "Revisit after the reserve study update.", due: "2027-01-15" },
];

/** One board action item in its lane: priority pill, category badge, due date, the matter, and the ask. */
const ItemCard = ({ item }: { item: Item }) => (
  <article className="item" data-priority={item.priority}>
    <header className="row wrap">
      <Pill word={item.priority} />
      <Badge>{item.category}</Badge>
      {item.executive && <Badge tone="warn">executive</Badge>}
      <DueDate iso={item.due} today={new Date("2026-10-03T00:00:00")} />
    </header>
    <h4>{item.title}</h4>
    <p className="ask">
      <strong>Ask:</strong> {item.ask}
    </p>
  </article>
);

/** Board action items across the five open lanes. A lane shows its count; an empty lane stays in place. */
export const BoardActionItems = () => (
  <Kanban lanes={LANES} items={items} laneOf={(i) => i.status} keyOf={(i) => i.id} render={(i) => <ItemCard item={i} />} />
);

/** Three lanes, one of them empty: the empty lane keeps its header and count of zero. */
export const WithEmptyLane = () => (
  <Kanban
    lanes={["open", "proposed", "deferred"]}
    items={items.filter((i) => i.status !== "deferred")}
    laneOf={(i) => i.status}
    keyOf={(i) => i.id}
    render={(i) => (
      <Card title={i.title}>
        <p className="muted">{i.ask}</p>
      </Card>
    )}
  />
);

/** No items at all: every lane present and empty. */
export const Empty = () => <Kanban lanes={LANES} items={[] as Item[]} laneOf={(i) => i.status} keyOf={(i) => i.id} render={() => null} />;
