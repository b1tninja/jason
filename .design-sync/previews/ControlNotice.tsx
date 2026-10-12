import { ControlNotice } from "jason-ui";

// Made-up notices for the approval kind "payhoa-attach-bills" (Oakview), in the shape of `GET /api/control-notices?subject=`. Dates are fake 2099 ones.
const base: any = {
  found: true, subject: "payhoa-attach-bills", subjectKind: "approval kind", title: "Payment plans", builtin: "one person", why: "",
  stricter: false, second: { always: false, aboveCents: null }, roles: [], mustInclude: [], clash: "", asOf: "2099-10-12",
  controls: [], waiting: [], refusals: [], caveats: [],
};
const inForce = {
  key: "payment-signers", title: "Payment signers", adoptedOn: "2099-09-05T20:00:00+00:00", effective: "2099-09-20", effect: "signers: 2", link: "#/controls?key=payment-signers",
};
const waiting = {
  key: "delivery-class", title: "Delivery class", adoptedOn: "2099-10-03T20:00:00+00:00", effective: "2099-11-14", effect: "first class",
  link: "#/controls?key=delivery-class", reason: "adopted, not in force until 2099-11-14",
};

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 720 }}>{children}</div>;

/** One control in force at the point of an act: the shield line, the board's date, the loader's sentence and effect, and the kind's own rule beneath. */
export const InForce = () => (
  <Frame>
    <ControlNotice data={{ ...base, stricter: true, why: "Two signers are required above $2,500.00.", controls: [inForce] }} />
  </Frame>
);

/** Adopted but the date has not come: the muted calendar line, "Takes effect DATE; not yet required". */
export const NotYetRequired = () => <Frame><ControlNotice data={{ ...base, waiting: [waiting] }} /></Frame>;

/** In force, and the roster cannot satisfy it: the server's words, as a refusal. */
export const Refused = () => (
  <Frame>
    <ControlNotice data={{ ...base, controls: [inForce], refusals: ["Monthly review requires a treasurer and a vice president; the roster has no vice president"] }} />
  </Frame>
);

/** The three lines at once: required, waiting, and refused. */
export const EveryLine = () => (
  <Frame>
    <ControlNotice
      data={{
        ...base, stricter: true, why: "Two signers are required above $2,500.00.", controls: [inForce], waiting: [waiting],
        refusals: ["Monthly review requires a treasurer and a vice president; the roster has no vice president"],
      }}
    />
  </Frame>
);
