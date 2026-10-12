import { ChangedSince } from "jason-ui";

const H1 = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
const H2 = "0f9e8d7c6b5a49382716f5e4d3c2b1a0";
const H3 = "5c4b3a29181716f5e4d3c2b1a0918273";
const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 640 }}>{children}</div>;

/** One store moved under a step that was done: which step, what moved, what it was and what it is now. */
export const OneStep = () => (
  <Frame>
    <ChangedSince
      changed={[{ step: "gather-bids", stepTitle: "Gather the bids", n: 3, address: "vendors:oakview-sample.json", was: H1, now: H2, at: "2099-03-02T09:00:00+00:00", pending: false }]}
    />
  </Frame>
);

/** Two stores under one step, and a second step: the steps are grouped, each with its own list and a way to jump to it. */
export const SeveralSteps = () => (
  <Frame>
    <ChangedSince
      onGo={() => {}}
      changed={[
        { step: "gather-bids", stepTitle: "Gather the bids", n: 3, address: "vendors:oakview-sample.json", was: H1, now: H2, at: "2099-03-02T09:00:00+00:00", pending: false },
        { step: "gather-bids", stepTitle: "Gather the bids", n: 3, address: "bids:item-1.json", was: H3, now: null, at: "2099-03-02T09:00:00+00:00", pending: false },
        { step: "notice-owners", stepTitle: "Notice the owners", n: 5, address: "notices:sample-notice.md", was: null, now: H2, at: "2099-03-04T14:30:00+00:00", pending: false },
      ]}
    />
  </Frame>
);

/** A read that found the change before any event holds it: the banner says it will be recorded when the run is opened. */
export const FoundByThisRead = () => (
  <Frame>
    <ChangedSince
      onGo={() => {}}
      changed={[{ step: "notice-owners", stepTitle: "Notice the owners", n: 5, address: "notices:sample-notice.md", was: H1, now: H3, at: "2099-03-05T08:00:00+00:00", pending: true }]}
    />
  </Frame>
);
