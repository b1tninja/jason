import { ControlStepNotice } from "jason-ui";

// The gates an adopted control adds to a workflow step (`StepControl`). Made-up controls for Oakview.
const inForce = { key: "ctl-two-signers", title: "Two signers for payments over the limit", why: "a payment over the limit needs two board members to sign", gate: "resolution", state: "in force", effective: "2099-01-01" };
const second = { key: "ctl-two-signers", title: "Two signers for payments over the limit", why: "a second person confirms the payment", gate: "second", state: "in force", effective: "2099-01-01", firstBy: "Person 1 office" };
const waiting = { key: "ctl-reserve-vote", title: "Board vote before a reserve withdrawal", why: "the board votes before money leaves the reserve", gate: "resolution", state: "waiting", effective: "2099-07-01" };
const refused = { key: "ctl-roles", title: "Treasurer and director sign together", why: "the roster has no director seated, so no pair can satisfy it", gate: "roles", state: "refused", effective: "2099-01-01", roles: ["treasurer", "director"] };

const wide = { maxWidth: 720 } as const;

/** A control in force at the step: the engine's own sentence, with the control's title linking to its card. */
export const InForce = () => <div style={wide}><ControlStepNotice controls={[inForce]} /></div>;

/** A second-signature gate says who made the first, and that a different person confirms. */
export const SecondSignature = () => <div style={wide}><ControlStepNotice controls={[second]} /></div>;

/** Adopted, but its date has not come: muted, with the date, so it is not read as required yet. */
export const NotYetRequired = () => <div style={wide}><ControlStepNotice controls={[waiting]} /></div>;

/** In force, but the roster cannot satisfy it: a refusal in the engine's words, with the glyph repeating the word. */
export const Refused = () => <div style={wide}><ControlStepNotice controls={[refused]} /></div>;

/** A step that several controls bite on shows one line for each. */
export const SeveralControls = () => <div style={wide}><ControlStepNotice controls={[inForce, second, waiting, refused]} /></div>;
