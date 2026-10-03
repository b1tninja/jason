import { ReadingLabel } from "jason-ui";

/** jason's reading: a lead, not legal advice; the recited words govern. */
export const Jasons = () => <ReadingLabel whose="jason">A month-to-month lease in writing meets Section 7.3; a room rented alone does not.</ReadingLabel>;

/** The board's reading, with the day it adopted it. */
export const Boards = () => <ReadingLabel whose="board" adopted="2025-06-10">"Thirty (30) days" means calendar days from the start of the lease.</ReadingLabel>;

/** Counsel's reading, named. */
export const Counsels = () => <ReadingLabel whose="counsel" by="Example Law Group">The 30 days run from when the tenant takes possession.</ReadingLabel>;

/** Two readings remain: the board asks counsel, and jason applies neither. */
export const Open = () => <ReadingLabel whose="open" options={["The 30 days run from when the lease is signed.", "The 30 days run from when the tenant takes possession."]} />;

/** The bare label inside a sentence. */
export const Inline = () => <p>Likely: the restated declaration <ReadingLabel whose="jason" inline /></p>;
