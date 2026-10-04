import { SEAL_WORDS, Seal, type SealState, type SealWord } from "jason-ui";

const row = { display: "flex", gap: 18, flexWrap: "wrap", alignItems: "start", padding: "6px 2px" } as const;
const of = (state: SealState) => (Object.keys(SEAL_WORDS) as SealWord[]).filter((w) => SEAL_WORDS[w].state === state);

/** Open: an empty box, a person still has to act. */
export const Open = () => <div style={row}>{of("open").map((w) => <Seal key={w} word={w} />)}</div>;

/** Done: a checked box, jason's part is finished. `filed` is jason's, a seal and never a stamp. */
export const Done = () => <div style={row}>{of("done").map((w) => <Seal key={w} word={w} />)}</div>;

/** Unresolved and not jason's: a question (a person checks or decides) and a strike (a person answers). */
export const UnresolvedAndNotJasons = () => <div style={row}>{[...of("question"), ...of("not")].map((w) => <Seal key={w} word={w} />)}</div>;

/** With whom and when. A county filing is `read` with its instrument number, never "recorded". */
export const WithDetail = () => (
  <div style={row}>
    <Seal word="read" instrument="2024-0001234" date="as of 2026-10-03" size="7em" />
    <Seal word="proposes" detail="for the treasurer" size="7em" />
    <Seal word="waiting-on" detail="the manager" date="since 2026-09-28" size="7em" />
    <Seal word="not-jason" detail="ask counsel" size="7em" />
  </div>
);

/** On one line, for a table cell or a folder's state ("not found" is a place to look, never a red "missing"). */
export const Inline = () => (
  <div style={{ display: "grid", gap: 10 }}>
    <span>Reserve study <Seal word="could-not-confirm" inline /></span>
    <span>Notice of the October meeting <Seal word="drafted" inline date="2026-10-03" /></span>
    <span>Deed of trust <Seal word="read" inline instrument="2024-0001234" /></span>
  </div>
);
