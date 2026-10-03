import { Card, Clock, type ClockStage } from "jason-ui";

/** Every preview is read as of October 3, 2026 so each stage's distance is the same on every capture. */
const today = new Date("2026-10-03T12:00:00");

const hearing: ClockStage[] = [
  { key: "notice", label: "Hearing notice sent", date: "2026-09-20", authority: "CIV 5855(b): 10 days before", done: true },
  { key: "hearing", label: "Hearing", date: "2026-10-06", authority: "executive session" },
  { key: "decision", label: "Decision notice due", date: "2026-10-20", authority: "CIV 5855(f): within 14 days" },
];

/** A disciplinary hearing's three stages: the notice done (green), the hearing next (accent), the decision notice ahead. */
export const Hearing = () => <Clock stages={hearing} today={today} />;

/** A stage that passed without being marked done reads overdue in red: the budget mailing before the fiscal year. */
export const Overdue = () => (
  <Clock
    today={today}
    stages={[
      { key: "draft", label: "Draft budget to the board", date: "2026-08-15", done: true },
      { key: "mail", label: "Budget mailed to owners", date: "2026-09-01", authority: "CIV 5300: 30 to 90 days before" },
      { key: "fy", label: "Fiscal year begins", date: "2026-10-01" },
      { key: "assess", label: "First assessment at the new rate", date: "2026-10-01" },
    ]}
  />
);

/** A completed clock: every stage done, all green, muted. */
export const AllDone = () => (
  <Clock
    today={today}
    stages={[
      { key: "quote", label: "Quotes received", date: "2026-08-02", done: true },
      { key: "vote", label: "Board approved the policy", date: "2026-08-19", done: true },
      { key: "bound", label: "Coverage bound", date: "2026-09-01", done: true },
    ]}
  />
);

/** The clock in a hearing card under its heading, as the hearings page shows each one. */
export const InCard = () => (
  <Card title="Hearing: 123 Main St, unit 7">
    <p className="muted">Unauthorized patio enclosure. Stages are the record; the board decides.</p>
    <Clock stages={hearing} today={today} />
  </Card>
);
