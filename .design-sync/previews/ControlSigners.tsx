import { ControlSigners } from "jason-ui";

// Made-up notices at the second-signature step of an approval kind (Oakview); the roles are office words, never a person's name.
const base: any = {
  found: true, subject: "payhoa-attach-bills", subjectKind: "approval kind", title: "Payment plans", builtin: "one person", why: "",
  stricter: true, second: { always: false, aboveCents: 250000 }, roles: ["treasurer", "director"], mustInclude: [], clash: "", asOf: "2099-10-12",
  controls: [{ key: "payment-signers", title: "Payment signers", adoptedOn: "2099-09-05T20:00:00+00:00", effective: "2099-09-20", effect: "signers: 2", link: "#/controls?key=payment-signers" }],
  waiting: [], refusals: [], caveats: [],
};

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 720 }}>{children}</div>;

/** One control in force narrows who signs: its title links to its card, the adoption date is said, and the offices that may sign follow. */
export const OnlyTheseOffices = () => <Frame><ControlSigners data={base} /></Frame>;

/** An office that must be among the signers, as well as the offices that may sign. */
export const MustBeAmongThem = () => <Frame><ControlSigners data={{ ...base, mustInclude: ["treasurer"] }} /></Frame>;

/** Two controls in force at the kind: each is named, and the date is left out because it would belong to only one. */
export const TwoControls = () => (
  <Frame>
    <ControlSigners
      data={{
        ...base, roles: ["treasurer", "president", "director"], mustInclude: ["treasurer"],
        controls: [...base.controls, { key: "reserve-withdrawals", title: "Reserve withdrawals", adoptedOn: "2099-09-06T20:00:00+00:00", effective: "2099-09-20", effect: "signers: 2", link: "#/controls?key=reserve-withdrawals" }],
      }}
    />
  </Frame>
);
