import { ReferenceShelf } from "jason-ui";
import type { ReferenceWork } from "jason-ui";

const guide: ReferenceWork = {
  title: "A Guide to Understanding Residential Subdivisions in California", file: "ResidentialSubdivisionsGuide.pdf",
  author: "Alberto Esquivel and Jaime R. Alvayay", publisher: "California Department of Real Estate and CSU Sacramento", year: 2014,
  url: "https://example.test/ResidentialSubdivisionsGuide.pdf",
  covers: "how a residential subdivision is made and sold: the Subdivision Map Act and the Subdivided Lands Act side by side, the kinds of common interest development, and the public report",
  caveat: "an explanation, not the law: it predates later amendments, so read a section it cites from the current text on the authorities shelf before relying on it",
  topics: [], onDisk: true, pages: 104, surveyed: "2026-10-03", lawChecked: true,
  counts: { ON_SHELF: 48, NOT_EXPORTED: 28, REGULATION: 18, RENUMBERED: 6, NOT_FOUND: 1 }, command: null,
};

const manual: ReferenceWork = {
  ...guide, title: "A Manager's Handbook for Common Interest Developments", file: "ManagersHandbook.pdf", author: "A. Author", publisher: "An Example Agency", year: 2019,
  covers: "how an association's meetings, budgets, and records run through the year",
  caveat: "a practice guide, written for associations that follow its model rules: read the association's own documents before the handbook's examples",
  pages: 62, surveyed: null, lawChecked: false, counts: null, command: "jason reference --cites ManagersHandbook.pdf",
};

const missing: ReferenceWork = {
  ...guide, title: "A Buyer's Guide to Common Interest Developments", file: "BuyersGuide.pdf", author: "An Example Agency", publisher: "An Example Agency", year: 2016,
  covers: "what a buyer is given before a binding contract, and what the association's reports say",
  caveat: "a consumer booklet: it summarizes the statutes it cites and quotes none of them",
  onDisk: false, pages: 0, surveyed: null, lawChecked: false, counts: null, command: null,
};

const caveats = [
  "A reference work explains a process. It is not the law and not the association's record: quote a section from the authorities shelf, never from the work.",
];

/** The shelf: each work with how far to trust it always open, its survey (dated, and whether lawlibrary was asked), and the way to read its citations. */
export const Shelf = () => <ReferenceShelf data={{ works: [guide, manual, missing], caveats }} selected="ResidentialSubdivisionsGuide.pdf" onRead={() => {}} />;

/** A shelf with one work, surveyed. */
export const OneWork = () => <ReferenceShelf data={{ works: [guide], caveats }} onRead={() => {}} />;
