import { FilingPlan, inspectionFixtures as fx } from "jason-ui";

/** The plan first: counts by action, every row with its action word, destination, and a Why; then the one button, which names the numbers. */
export const PlanOnly = () => <FilingPlan plan={fx.filingPlan} onConfirmFile={() => {}} />;

/** Filing under way. */
export const Running = () => <FilingPlan plan={fx.filingPlan} onConfirmFile={() => {}} running />;

/** Nothing to do: everything is filed, and there is no button. */
export const NothingToDo = () => <FilingPlan plan={fx.filingPlanEmpty} onConfirmFile={() => {}} />;

/** Without a callback the plan shows only its command. */
export const CommandOnly = () => <FilingPlan plan={fx.filingPlan} />;
