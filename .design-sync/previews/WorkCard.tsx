import type { ReactNode } from "react";
import { WorkCard } from "jason-ui";
import type { ReferenceWork } from "jason-ui";

const work: ReferenceWork = {
  title: "A Guide to Understanding Residential Subdivisions in California", file: "ResidentialSubdivisionsGuide.pdf",
  author: "Alberto Esquivel and Jaime R. Alvayay", publisher: "California Department of Real Estate and CSU Sacramento", year: 2014,
  url: "https://example.test/ResidentialSubdivisionsGuide.pdf",
  covers: "how a residential subdivision is made and sold, and the public report",
  caveat: "an explanation, not the law: it predates later amendments, so read a section it cites from the current text on the authorities shelf",
  topics: [], onDisk: true, pages: 104, surveyed: "2026-10-03", lawChecked: true,
  counts: { ON_SHELF: 48, NOT_EXPORTED: 28, REGULATION: 18, RENUMBERED: 6, NOT_FOUND: 1 }, command: null,
};

const Frame = ({ children }: { children: ReactNode }) => <ul style={{ listStyle: "none", margin: 0, padding: 0, maxWidth: 640 }}>{children}</ul>;

/** A surveyed work, selected: the caveat open, the survey's date, the standing strip, and "Read its citations". */
export const Surveyed = () => <Frame><WorkCard work={work} selected onRead={() => {}} /></Frame>;

/** On disk and never surveyed: the survey command instead of a strip. */
export const NotSurveyed = () => (
  <Frame><WorkCard work={{ ...work, surveyed: null, lawChecked: false, counts: null, command: "jason reference --cites ResidentialSubdivisionsGuide.pdf" }} onRead={() => {}} /></Frame>
);

/** Not on disk: the fetch command, and no way to read its citations. */
export const NotOnDisk = () => <Frame><WorkCard work={{ ...work, onDisk: false, pages: 0, surveyed: null, counts: null }} onRead={() => {}} /></Frame>;
