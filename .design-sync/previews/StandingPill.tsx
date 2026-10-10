import { StandingPill } from "jason-ui";

/** The seven words a cited section can have against the authorities shelf. A gap is warn, never bad: a gap is a lead, not a finding. The meaning is the title. */
export const SevenWords = () => (
  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
    <StandingPill standing="ON_SHELF" />
    <StandingPill standing="NOT_EXPORTED" />
    <StandingPill standing="NOT_FOUND" />
    <StandingPill standing="RENUMBERED" />
    <StandingPill standing="REGULATION" />
    <StandingPill standing="OTHER_CODE" />
    <StandingPill standing="UNCHECKED" />
  </div>
);

/** The gaps, which sort first in every list: not found, not exported, renumbered. */
export const Gaps = () => (
  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
    <StandingPill standing="NOT_FOUND" />
    <StandingPill standing="NOT_EXPORTED" />
    <StandingPill standing="RENUMBERED" />
  </div>
);

/** A code this build does not know shows as its own words, neutral. */
export const UnknownCode = () => (
  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
    <StandingPill standing="ON_SHELF" />
    <StandingPill standing="SUPERSEDED_ON_SHELF" />
  </div>
);
