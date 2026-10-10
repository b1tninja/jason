import { WatchRow, inspectionFixtures as fx } from "jason-ui";

const docProps = { signedIn: true, evidence: null } as const;

/** Current: a record answers it. */
export const Current = () => <WatchRow item={fx.watchItems[0]} docProps={docProps} />;

/** Unknown: nothing found either way, with what was searched, and never "not done". */
export const Unknown = () => <WatchRow item={fx.watchItems[1]} docProps={docProps} />;

/** Overdue. */
export const Overdue = () => <WatchRow item={fx.watchItems[2]} docProps={docProps} />;

/** Partly answered. */
export const PartlyAnswered = () => <WatchRow item={fx.watchItems[3]} docProps={docProps} />;

/** Not applicable. */
export const NotApplicable = () => <WatchRow item={fx.watchItems[4]} docProps={docProps} />;
