import { RereadIcon } from "jason-ui";

/** The icon alone at its 16px size, in the text color and in the muted and accent tokens. */
export const Alone = () => (
  <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
    <span style={{ color: "var(--ink)" }}><RereadIcon /></span>
    <span style={{ color: "var(--muted)" }}><RereadIcon /></span>
    <span style={{ color: "var(--accent)" }}><RereadIcon /></span>
    <span style={{ color: "var(--bad)" }}><RereadIcon /></span>
  </div>
);

/** Inline beside text, as the plan's header and a panel's read-again note use it, at body and small sizes. */
export const BesideText = () => (
  <div style={{ display: "grid", gap: 10 }}>
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 15, color: "var(--ink)" }}>
      <RereadIcon />Read every request again
    </span>
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--muted)" }}>
      <RereadIcon />Read from PayHOA just now by Jane Example.
    </span>
  </div>
);
