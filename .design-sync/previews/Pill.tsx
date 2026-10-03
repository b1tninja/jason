import { Pill } from "jason-ui";

/** A standing or status word with its tone; the meaning shows on hover. */
export const Standings = () => (
  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
    <Pill word="overdue" meaning="past due with no evidence it was done" />
    <Pill word="due soon" meaning="within 60 days" />
    <Pill word="upcoming" />
    <Pill word="done" />
    <Pill word="no evidence" meaning="no store shows it done" />
  </div>
);

export const BoardItemStatus = () => (
  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
    <Pill word="open" />
    <Pill word="proposed" />
    <Pill word="on agenda" />
    <Pill word="in progress" />
    <Pill word="deferred" />
    <Pill word="closed" />
  </div>
);

export const LienStandings = () => (
  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
    <Pill word="IN_DEFAULT" meaning="a default or sale notice is running against the current owner" />
    <Pill word="STANDS" meaning="stands against the current owner" />
    <Pill word="RELEASE_DUE" meaning="the association owes the release (Civil Code 5685)" />
    <Pill word="RELEASED" />
  </div>
);
