import { NotComposed } from "jason-ui";

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 560 }}>{children}</div>;

/** One thing the page could not build, with the reason in plain words. */
export const OneItem = () => (
  <Frame>
    <NotComposed items={[{ band: "work", what: "The Oakview runs that wait on a vendor", why: "The runs store could not be read, so none is listed here" }]} />
  </Frame>
);

/** Several, one per band: each names what is missing and why, so an absent list is never read as an empty one. */
export const SeveralItems = () => (
  <Frame>
    <NotComposed
      items={[
        { band: "signedWaiting", what: "Plans signed and waiting to be applied", why: "The approvals store is locked by another session; try again in a minute" },
        { band: "comingUp", what: "Dates coming up for the treasurer", why: "The calendar has no source for this office yet" },
        { band: "needsAttention", what: "Sample notices to send", why: "The notice catalog was not offered to this viewer" },
      ]}
    />
  </Frame>
);
