import { useState } from "react";
import { Badge, Card, Tabs, type TabSpec } from "jason-ui";

const meetingTabs: TabSpec[] = [
  {
    id: "agenda",
    label: "Agenda",
    content: (
      <ol style={{ margin: ".75rem 0 0", paddingLeft: "1.4rem" }}>
        <li>Call to order and quorum</li>
        <li>Open forum (CIV 4925)</li>
        <li>Insurance renewal: approve quote or rebid</li>
        <li>Pool deck resurfacing: select bidder, fund from reserves</li>
        <li>Adjourn to executive session</li>
      </ol>
    ),
  },
  {
    id: "notice",
    label: "Notice",
    content: <p style={{ margin: ".75rem 0 0" }}>Posted on the clubhouse board and emailed to the owners list on 2026-09-28, four days before the meeting (CIV 4920).</p>,
  },
  {
    id: "minutes",
    label: "Minutes",
    content: (
      <p style={{ margin: ".75rem 0 0" }}>
        <Badge tone="warn">draft</Badge> Due to owners within 30 days of the meeting (CIV 4950).
      </p>
    ),
  },
];

function Controlled({ initial, tabs }: { initial: string; tabs: TabSpec[] }) {
  const [active, setActive] = useState(initial);
  return <Tabs tabs={tabs} active={active} onChange={setActive} />;
}

/** A meeting's three tabs with the first selected: the active tab in ink with an accent underline, the rest muted. */
export const MeetingAgenda = () => <Controlled initial="agenda" tabs={meetingTabs} />;

/** The same tabs with the last one selected, inside a card as the views use them. */
export const MinutesSelected = () => (
  <Card title="Board meeting, October 2">
    <Controlled initial="minutes" tabs={meetingTabs} />
  </Card>
);

/** Two tabs over a payments split: a short label set. */
export const TwoTabs = () => (
  <Controlled
    initial="operating"
    tabs={[
      { id: "operating", label: "Operating", content: <p style={{ margin: ".75rem 0 0" }}>Twelve payments, $38,912.45, two with questions.</p> },
      { id: "reserve", label: "Reserve", content: <p style={{ margin: ".75rem 0 0" }}>One transfer in, $6,000.00.</p> },
    ]}
  />
);
