import { RemedyNote } from "jason-ui";

// Steps of an Oakview sample run: step 3 is a check that failed, step 4 is its remedy.
const steps = [
  { id: "bf.check", n: 3, title: "Check the vendor's license" },
  { id: "bf.fix", n: 4, title: "Renew the license" },
];

const wide = { maxWidth: 960 } as const;
const noop = () => {};

/** On the remedy step: it says it remedies the failed check above, and the check stays recorded as failed. */
export const OnTheRemedyStep = () => (
  <div style={wide}><RemedyNote step={{ remedyOf: "bf.check" }} steps={steps} onGo={noop} /></div>
);

/** On the failed check: it stays failed, the remedy step is named, and the run goes on there. */
export const OnTheFailedCheck = () => (
  <div style={wide}><RemedyNote step={{ remedy: "bf.fix" }} steps={steps} onGo={noop} /></div>
);

/** Without a way to move to the other step (read only, or the page has none), the sentence stands alone. */
export const WithoutGo = () => (
  <div style={wide}>
    <RemedyNote step={{ remedyOf: "bf.check" }} steps={steps} />
    <RemedyNote step={{ remedy: "bf.fix" }} steps={steps} />
  </div>
);

/** A remedy step that is not among the steps read still gets the plain sentence. */
export const RemedyNotFound = () => (
  <div style={wide}><RemedyNote step={{ remedy: "bf.gone" }} steps={steps} onGo={noop} /></div>
);
