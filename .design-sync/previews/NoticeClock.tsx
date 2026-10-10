import { NoticeClock, inspectionFixtures as fx } from "jason-ui";

/** A program's notice: four dates side by side with the days each gives. No date is picked. */
export const ProgramNotice = () => <NoticeClock clock={fx.deadline} />;

/** A statute's own clock, cited differently from a program's notice. */
export const StatuteClock = () => <NoticeClock clock={fx.deadlineStatute} />;

/** Passed on every reading. */
export const Passed = () => <NoticeClock clock={{ ...fx.deadline, standing: "passed", runsFrom: fx.deadline.runsFrom.map((r) => ({ ...r, met: false })) }} />;

/** Met on every reading. */
export const Met = () => <NoticeClock clock={{ ...fx.deadline, standing: "met", runsFrom: fx.deadline.runsFrom.map((r) => ({ ...r, met: true })) }} />;
