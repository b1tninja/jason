import { PrivateAsk, PrivateBand, PrivateSwitch, type PrivateView } from "jason-ui";

// Static cells: a fixed clock, no server. The band's countdown reads `now`; nothing here posts or reloads.
const NOW = () => new Date("2026-10-03T21:03:00Z");
const OFF: PrivateView = { open: false, mayOpen: true, why: "", minutes: [15, 30, 60], default: 30 };
const ON: PrivateView = { open: true, mayOpen: true, id: "a1b2c3d4", reason: "executive session prep", until: "2026-10-03T21:15:00Z" };
const noop = () => {};

/** Off: a quiet button in the header, beside the signed-in account. */
export const Off = () => (
  <div className="console-bar-inner">
    <span className="console-signin">Signed in as <strong className="console-signin-name">R. Lind, secretary</strong></span>
    <PrivateSwitch view={OFF} name="R. Lind" onOpen={noop} />
  </div>
);

/** Disabled: an office that does not open restricted material sees the switch off and the reason beside it, never blank. */
export const Disabled = () => (
  <div className="console-bar-inner">
    <span className="console-signin">Signed in as <strong className="console-signin-name">M. Chen, treasurer</strong></span>
    <PrivateSwitch view={{ open: false, mayOpen: false, why: "The treasurer's office doesn't open executive-session and other restricted material (P3)." }}
      name="M. Chen" onOpen={noop} />
  </div>
);

/** Asking: why (required, logged), for how long (30 by default), and the act in words, as the Confirm stamp. */
export const Asking = () => (
  <div style={{ maxWidth: 440, paddingTop: 12 }}>
    <PrivateAsk name="R. Lind" onOpen={noop} onCancel={noop} autoFocus={false} />
  </div>
);

/** On: the hatched band under the header, in words, with the time left and Close; the switch says on. */
export const On = () => (
  <div>
    <div className="console-bar-inner">
      <span className="console-signin">Signed in as <strong className="console-signin-name">R. Lind, secretary</strong></span>
      <PrivateSwitch view={ON} name="R. Lind" onOpen={noop} />
    </div>
    <PrivateBand view={ON} onClose={noop} now={NOW} />
  </div>
);
