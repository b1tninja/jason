import { SourcedDate } from "jason-ui";

/** The four sources a date can come from, each labeled in words and a glyph: a recorded date carries the document it came
 * from; an implied one shows its arithmetic; a reported one says how many owners reported it; a missing one invites an entry. */
export const FourSources = () => (
  <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 10 }}>
    <li>
      <SourcedDate
        value={{ date: "2099-06-12", source: "recorded", docs: [{ address: "file:paint/sample-invoice.pdf", document: "pdf", name: "Sample painting invoice", kind: "pdf", level: "P1" }] }}
      />
    </li>
    <li><SourcedDate value={{ date: "2092", source: "implied", arithmetic: "due 2099 minus a 7-year life" }} /></li>
    <li><SourcedDate value={{ date: "2095", source: "reported", count: 3 }} /></li>
    <li><SourcedDate value={{ source: "needs input" }} onEnter={() => {}} /></li>
  </ul>
);

/** Precision follows the source: a year alone stays a year, a month stays a month, and nothing invents a day. */
export const Precision = () => (
  <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 10 }}>
    <li><SourcedDate value={{ date: "2092", source: "implied", arithmetic: "due 2099 minus a 7-year life" }} /></li>
    <li><SourcedDate value={{ date: "2098-04", source: "reported", count: 1 }} /></li>
    <li><SourcedDate value={{ date: "2099-06-12", source: "recorded", docs: [] }} /></li>
  </ul>
);
