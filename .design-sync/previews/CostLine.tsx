import { CostLine } from "jason-ui";

/** A kind with no cost: the engine's `costCents: null` and the planner's words. */
export const NoCharge = () => <CostLine costCents={null} summary={{ cost: "No charge: PayHOA tag changes and request status" }} />;

/** A kind that charges the association, in integer cents, with how it was priced. Made-up prices. */
export const Letters = () => <CostLine costCents={816} summary={{ cost: "4 letters × 3 billed pages, estimate from the mailroom preview" }} />;

/** No total on the plan: the sum of the approved items' costs. */
export const FromItems = () => <CostLine items={[{ class: "approvable", decision: "approved", costCents: 204 }, { class: "approvable", decision: "approved", costCents: 204 }, { class: "approvable", decision: "rejected", costCents: 204 }]} />;
