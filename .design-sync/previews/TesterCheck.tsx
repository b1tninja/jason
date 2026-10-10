import { TesterCheck, inspectionFixtures as fx } from "jason-ui";

const today = new Date("2030-10-04T12:00:00");

/** Listed on every list checked, each as "listed on the list dated D". Contacts are masked and not shown. */
export const ListedEverywhere = () => <TesterCheck check={fx.testerListed} today={today} />;

/** Listed on one list only. */
export const ListedOnOne = () => <TesterCheck check={fx.testerOne} today={today} />;

/** Matched on the tester's name under a different business. */
export const OtherBusiness = () => <TesterCheck check={fx.testerOtherBusiness} today={today} />;

/** Not listed. */
export const NotListed = () => <TesterCheck check={fx.testerNotListed} today={today} />;

/** A list older than a year says so. */
export const OldList = () => <TesterCheck check={fx.testerOld} today={today} />;

/** Lists not fetched: nothing is said about the tester. */
export const NotFetched = () => <TesterCheck check={fx.testerNotFetched} today={today} />;
