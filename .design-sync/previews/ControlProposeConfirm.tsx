import { ControlProposeConfirm } from "jason-ui";

// The write goes through the `post` prop; these cells never click it. Oakview made-up names.
const post: any = () => new Promise(() => { /* never settles: a card is read, not clicked */ });

// The card puts the button in a right-aligned bar (`control-propose-bar`); a row has its own `control-row-act`. Both size it to its words.
const Frame = ({ children }: { children: React.ReactNode }) => <div className="control-propose-bar" style={{ maxWidth: 520 }}>{children}</div>;

/** The card's button: "Propose to the board", which opens a two-click confirmation spelling out the change. */
export const OnTheCard = () => <Frame><ControlProposeConfirm controlKey="reserve-withdrawals" title="Reserve withdrawals" by="A. Secretary" post={post} /></Frame>;

/** The list row's compact button ("Propose"), with the control's title for a screen reader. */
export const CompactInARow = () => <Frame><ControlProposeConfirm controlKey="reserve-withdrawals" title="Reserve withdrawals" by="A. Secretary" compact post={post} /></Frame>;

/** A control already before the board: the same write refreshes its item, so the label says so. */
export const RefreshTheBoardItem = () => (
  <Frame><ControlProposeConfirm controlKey="contract-term" title="Contract term check" by="A. Secretary" label="Refresh the board item" post={post} /></Frame>
);

/** An administrator viewing as someone else: the server refuses the act then, so the button is replaced by the sentence. */
export const AdminViewingAsSomeoneElse = () => (
  <Frame><ControlProposeConfirm controlKey="reserve-withdrawals" title="Reserve withdrawals" actingAs="A. Manager" post={post} /></Frame>
);
