import { DueDate } from "jason-ui";

/** Every preview is read as of October 3, 2026 so the distance is the same on every capture. */
const today = new Date("2026-10-03T12:00:00");

/** A deadline that passed: the annual budget mailing (Civil Code 5300) was due 30 days before the fiscal year. */
export const Overdue = () => <DueDate iso="2026-09-01" today={today} />;

/** Due within two weeks: the hearing notice reads warn. */
export const DueSoon = () => <DueDate iso="2026-10-12" today={today} />;

/** Due today. */
export const Today = () => <DueDate iso="2026-10-03" today={today} />;

/** Far off: the master policy term end, in neutral. */
export const FarOff = () => <DueDate iso="2027-03-31" today={today} />;

/** No date on file. */
export const NoDate = () => <DueDate iso={null} today={today} />;

/** The Next column of the calendar: one of each, stacked as rows would show them. */
export const CalendarColumn = () => (
  <div style={{ display: "grid", gap: 8 }}>
    <DueDate iso="2026-09-15" today={today} />
    <DueDate iso="2026-10-10" today={today} />
    <DueDate iso="2026-12-01" today={today} />
    <DueDate iso={undefined} today={today} />
  </div>
);
