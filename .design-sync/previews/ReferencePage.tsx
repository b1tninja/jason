import { ReferencePage } from "jason-ui";
import type { ReferencePageData } from "jason-ui";

const base: ReferencePageData = {
  found: true, work: "A Guide to Understanding Residential Subdivisions in California", page: 60, pages: 104, noText: false,
  banner: "An explanation, not the law and not the association's record.",
  caveat: "It predates later amendments: read a section it cites from the current text on the authorities shelf before relying on it.",
  text: [
    "48 A Guide to Understanding Residential Subdivisions in California",
    "Subdivisions Subject to the Map Act vs. the SLA",
    "Government Code Section 66424 of the Map Act defines a subdivision as the division, by any subdivider, of any unit or units of",
    "improved or unimproved land, for the purpose of sale, lease, or financing, whether immediate or future.",
    "",
    "In defining “subdivision” the SLA also explains that the Map Act is an “undivided interest” subdivision as defined in",
    "BPC Section 11001.1 of the SLA. Not all subdivisions subject to the Map Act are subject to the SLA, and not all subdivisions",
    "subject to the SLA are subject to the Map Act.",
  ].join("\n"),
};

/** The page of a work a citation names, with the sentence the citation was read from marked (it can wrap across lines). The banner and the work's own caveat are on every page. */
export const SentenceMarked = () => (
  <ReferencePage data={base} sentence={"the Map Act is an “undivided interest” subdivision as defined in BPC Section 11001.1 of the SLA."} onPage={() => {}} />
);

/** The first page: Previous is disabled. A sentence the page does not hold is not marked. */
export const FirstPage = () => <ReferencePage data={{ ...base, page: 1 }} sentence="a sentence this page does not hold" onPage={() => {}} />;

/** A page with no text layer says so, and points to the original. */
export const NoTextLayer = () => <ReferencePage data={{ ...base, page: 104, noText: true, text: "" }} onPage={() => {}} />;
