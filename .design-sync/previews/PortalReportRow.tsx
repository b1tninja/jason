import { PortalReportRow, inspectionFixtures as fx } from "jason-ui";

/** Not filed: the portal lists it and no copy was found. A lead. */
export const NotFiled = () => <PortalReportRow report={fx.portal.reports[0]} />;

/** Held in the library and in Drive. */
export const LibraryAndDrive = () => <PortalReportRow report={fx.portal.reports[1]} />;

/** A record of completion, shown as such and not as an inspection; held in the library only. */
export const RecordOfCompletion = () => <PortalReportRow report={fx.portal.reports[2]} />;

/** A report the site's name check refused: held back with the reason. */
export const HeldBack = () => <PortalReportRow report={fx.portalRefused.reports[0]} />;
