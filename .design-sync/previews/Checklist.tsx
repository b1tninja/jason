import { Card, Checklist } from "jason-ui";

/** A meeting notice's required contents, two still missing, with the count in the head. */
export const NoticeContents = () => (
  <Checklist
    title="Notice contents (CIV 4920)"
    items={[
      { label: "Date, time, and place", ready: true },
      { label: "Agenda", ready: false, detail: "no items yet" },
      { label: "Posted four days ahead", ready: true, detail: "by 2026-10-17" },
      { label: "Executive session items named in general terms", ready: false },
    ]}
  />
);

/** Everything ready: the head says "all ready". */
export const AllReady = () => (
  <Checklist
    title="Annual policy statement"
    items={[
      { label: "Address for notices to the association", ready: true },
      { label: "Secondary address request", ready: true },
      { label: "Fine schedule", ready: true },
      { label: "Dispute resolution summary", ready: true },
    ]}
  />
);

/** No title: just the lines, inside a card. */
export const Untitled = () => (
  <Card title="Minutes packet">
    <Checklist items={[{ label: "Draft minutes", ready: true, detail: "2026-09-28" }, { label: "Treasurer's report", ready: false, detail: "awaiting bank statement" }]} />
  </Card>
);

/** Nothing required. */
export const Empty = () => <Checklist title="Hearing packet" items={[]} />;
