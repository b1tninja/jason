import { Glyph } from "./Glyph";
import { BASES, isBasisWord } from "../lib/work";

/** Whose date it is, as one word and a glyph: LEGAL (the law's), DOCUMENTS, COUNTERPARTY, PROPOSED, PERSON. The word is the
 * label and the glyph repeats it; hovering says what the date is. A proposed date is drawn outlined and says "proposed, not
 * the law's", never as a stamp. `basis` is the engine's word ("law", "documents", "counterparty", "proposed policy",
 * "person"); one outside the five is shown plainly as it came, with no glyph. */
export function BasisPill({ basis, label }: { basis: string | null | undefined; label?: string }) {
  if (!basis) return null;
  if (!isBasisWord(basis)) return <span className="badge badge-neutral basis-pill basis-unknown">{label || basis}</span>;
  const look = BASES[basis];
  const proposed = basis === "proposed policy";
  return (
    <span className={`badge basis-pill basis-${basis.replace(/\s+/g, "-")} badge-neutral${proposed ? " basis-proposed" : ""}`} title={look.meaning}>
      <Glyph name={look.glyph} size="1em" className="badge-glyph" />
      {label || look.word}
      {proposed && <span className="visually-hidden">: proposed, not the law's</span>}
    </span>
  );
}
