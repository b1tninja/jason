import { DisabledForOffice } from "jason-ui";

const col = { display: "grid", gap: 16, justifyItems: "start", maxWidth: 520 } as const;

/** The viewer holds the office: the control renders exactly as it is, with no reason beside it. */
export const HoldsTheOffice = () => (
  <div style={col}>
    <DisabledForOffice office="treasurer" mine={["secretary", "treasurer"]} what="sign this">
      <button type="button">Sign the sample payment</button>
    </DisabledForOffice>
  </div>
);

/** The viewer does not: the control stays visible but disabled, with the reason and the viewer's own office in words. */
export const NotYourOffice = () => (
  <div style={col}>
    <DisabledForOffice office="treasurer" mine={["secretary"]} what="sign this">
      <button type="button">Sign the sample payment</button>
    </DisabledForOffice>
  </div>
);

/** An act that either of two offices may take: the reason names both. */
export const EitherOffice = () => (
  <div style={col}>
    <DisabledForOffice office={["president", "treasurer"]} mine={["secretary"]} what="approve this plan">
      <button type="button">Approve the plan</button>
    </DisabledForOffice>
  </div>
);

/** A viewer who holds no office, and a group of controls, all disabled together. */
export const NoOffice = () => (
  <div style={col}>
    <DisabledForOffice office="secretary" mine={[]} what="record the minutes">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input type="text" defaultValue="Item 1: Sample minute" aria-label="Minute text" />
        <button type="button">Record</button>
      </div>
    </DisabledForOffice>
  </div>
);
