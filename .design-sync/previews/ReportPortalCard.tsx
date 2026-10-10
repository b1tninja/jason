import { ReportPortalCard, inspectionFixtures as fx } from "jason-ui";

/** Not found yet: names the command that finds it. */
export const NotFound = () => <ReportPortalCard portal={null} vendor="Example Alarm Co." findCommand={fx.findCommand} />;

/** The vendor's row says it has no portal. */
export const VendorHasNone = () => <ReportPortalCard portal={null} vendor="Example Pest Co." vendorHasNone />;

/** Found from a document's code, not synced: nothing has been read from the portal. */
export const FoundNotSynced = () => <ReportPortalCard portal={fx.portalFoundNotSynced} syncCommand={fx.portalCommand} onSync={() => {}} />;

/** Synced: the loader's counts, the last read, and each report with where it is held. */
export const Synced = () => <ReportPortalCard portal={fx.portal} syncCommand={fx.portalCommand} onPlanFiling={() => {}} />;

/** Protected: a stop with a person's step. jason enters neither a password nor a phone code. */
export const Protected = () => <ReportPortalCard portal={fx.portalProtected} />;

/** Two portals for one customer: this one is listed once, pointing at the other. */
export const SameCustomer = () => <ReportPortalCard portal={fx.portalSameCustomer} />;

/** Unreachable: the error and the command. */
export const Unreachable = () => <ReportPortalCard portal={fx.portalUnreachable} syncCommand={fx.portalCommand} />;
