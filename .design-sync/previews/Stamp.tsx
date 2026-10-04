import { STAMP_WORDS, Stamp, type StampWord } from "jason-ui";

const row = { display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center", padding: "10px 4px" } as const;

/** Every word a person or the board decides in, each in its tone. `sent` carries the record of the sending. */
export const Words = () => (
  <div style={row}>
    {(Object.keys(STAMP_WORDS) as StampWord[]).map((w) => <Stamp key={w} word={w} sentRef={w === "sent" ? "comm-0001" : undefined} />)}
  </div>
);

/** On a motion, with who and when: the roll call's tally and the meeting's date. */
export const WithWhoAndWhen = () => (
  <div style={row}>
    <Stamp word="carried" by="4 yes, 0 no, 1 recused" date="2026-10-21" size="3.2em" />
    <Stamp word="tabled" by="to 2026-11-18" size="3.2em" />
    <Stamp word="approved" by="Jane Example, treasurer" date="2026-10-02" size="3.2em" />
  </div>
);

/** Flat, in a table cell or a heading. */
export const Flat = () => (
  <div style={row}>
    <Stamp word="failed" tilt={0} size="1.6em" />
    <Stamp word="denied" tilt={0} size="1.6em" />
    <Stamp word="referred" tilt={0} size="1.6em" />
    <Stamp word="sent" sentRef="comm-0001" date="2026-10-01" tilt={0} size="1.9em" />
  </div>
);

/** A motion's own word the set lacks keeps its word, in the neutral tone, so the record is never lost. */
export const OwnWord = () => (
  <div style={row}><Stamp word="Postponed" by="to the annual meeting" /></div>
);
