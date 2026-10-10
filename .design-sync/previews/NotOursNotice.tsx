import { NotOursNotice, inspectionFixtures as fx } from "jason-ui";

/** Mail for another party at a shared address: what is visible, with "mark not ours" behind a confirm. */
export const Possible = () => <NotOursNotice item={fx.notOurs} onMarkNotOurs={() => {}} onDraftReturn={() => {}} />;

/** Marked by a person. */
export const Marked = () => <NotOursNotice item={fx.notOursMarked} onMarkNotOurs={() => {}} />;
