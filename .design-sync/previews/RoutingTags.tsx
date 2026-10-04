import { RoutingTags } from "jason-ui";

/** A duty two offices share, as the profile's assignments name them. */
export const Several = () => <RoutingTags owners={[{ role: "president" }, { role: "secretary", adoption: "proposed" }]} />;

/** An empty list from the server: no assignment covers it, so it is unassigned. */
export const NoneAssigned = () => <RoutingTags owners={[]} />;
