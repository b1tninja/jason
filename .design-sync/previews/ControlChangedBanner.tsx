import { ControlChangedBanner } from "jason-ui";

// A provision changed since adoption (an amendment). The old and new words are plainly fake sample text, not a statute.
const CHANGED: any = {
  was: "Sample text, not a statute: payments are signed by two officers.",
  now: "Sample text, not a statute: payments over a limit the board sets are signed by two officers; others by one.",
  changedOn: "2099-08-15", basis: "an amendment of the sample bylaws", citation: "EX 123.4",
};

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 820 }}>{children}</div>;

/** Old and new words side by side, both recited, with the date and basis, and the link to the board item that follows it. */
export const AmendedWithBoardItem = () => <Frame><ControlChangedBanner changed={CHANGED} citation="EX 123.4" itemId="item-1" /></Frame>;

/** Only the old words are stored (the provision no longer reads the same and the new text is not on file): one column, and no link. */
export const OnlyTheOldWords = () => (
  <Frame><ControlChangedBanner changed={{ was: CHANGED.was, changedOn: "2099-08-15" } as any} citation="EX 123.4" /></Frame>
);

/** A change with no date or basis: the citation falls back to the control's own, and the sentence stays plain. */
export const NoDateOrBasis = () => (
  <Frame><ControlChangedBanner changed={{ was: CHANGED.was, now: CHANGED.now } as any} citation="EX 123.4(b)" /></Frame>
);
