import { Discrepancy, inspectionFixtures as fx } from "jason-ui";

const docProps = { signedIn: true, evidence: null } as const;

/** Each source in its own column; the next step is a command. */
export const NextIsCommand = () => <Discrepancy discrepancy={fx.discrepancy} docProps={docProps} />;

/** The next step is a question a person answers. */
export const NextIsQuestion = () => <Discrepancy discrepancy={fx.discrepancyQuestion} docProps={docProps} />;
