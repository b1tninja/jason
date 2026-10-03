import { StageSteps, type StageGate } from "jason-ui";

const gates: StageGate[] = [
  { stage: "start", title: "Accounts and the profile set", open: true },
  { stage: "ingest", title: "The library read and classified", open: true },
  { stage: "establish", title: "The governing documents settled", open: false, waiting: [{ key: "declaration", status: "partial" }, { key: "bylaws", status: "missing" }], checks: [{ passed: false, evidence: "2 high-stakes answers a second person confirms" }] },
  { stage: "operate", title: "Running the calendar", open: false, opensWhen: "establish" },
  { stage: "adopt", title: "The board adopts the policies", open: false, opensWhen: "the board's vote" },
];

/** Onboarding midway: two gates open, establish being worked and naming what it waits on. */
export const Midway = () => <StageSteps gates={gates} current="establish" label="Onboarding stages" />;

/** Every gate open. */
export const AllOpen = () => <StageSteps gates={gates.map((g) => ({ ...g, open: true }))} current="adopt" />;

/** Just started: only the first stage is being worked. */
export const Starting = () => <StageSteps gates={gates.map((g, n) => ({ ...g, open: false, waiting: n === 0 ? [{ key: "payhoa-account", status: "missing" }] : g.waiting }))} current="start" />;
