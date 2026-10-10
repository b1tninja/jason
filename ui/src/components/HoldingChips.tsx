import { DIFFERENT_COPY, PLACE_WORDS, type Holding } from "../lib/inspections";

/** One chip per place the same content lives: the library, Drive (with its path), the PayHOA library, an email attachment,
 * the vendor's portal. A copy that is not byte-identical says "a different copy". None says so in words, which is a lead,
 * not a finding that nothing is held. */
export function HoldingChips({ holdings }: { holdings: readonly Holding[] }) {
  if (!holdings.length) return <p className="muted insp-holdings-none">No place holds it, in the places jason looked.</p>;
  return (
    <ul className="insp-holdings" aria-label="Where it is held">
      {holdings.map((h, i) => (
        <li key={`${h.place}-${i}`} className="chip insp-holding" data-place={h.place}>
          <strong>{PLACE_WORDS[h.place]}</strong>
          <span className="muted"> {h.where}</span>
          {!h.identical && <span className="insp-different"> · {DIFFERENT_COPY}</span>}
        </li>
      ))}
    </ul>
  );
}
