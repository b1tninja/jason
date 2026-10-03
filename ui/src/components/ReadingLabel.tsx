import type { ReactNode } from "react";

export type Whose = "jason" | "board" | "counsel" | "open";

const WHOSE: Record<Whose, string> = {
  jason: "jason's reading",
  board: "The board's reading",
  counsel: "Counsel's reading",
  open: "Two readings remain",
};

const BASIS: Record<Whose, string> = {
  jason: "A reading, not legal advice. The recited words govern; the board decides.",
  board: "",
  counsel: "",
  open: "The board asks counsel. Until then, jason applies neither.",
};

/** How recited words are read, always labeled with whose reading it is: jason's, the board's (with the day it adopted it),
 * or counsel's; or, where two readings remain, both (`options`), for the board to take to counsel. It follows a
 * `Recitation` and never stands in for one. `inline` is the bare label, for a sentence or a table cell. */
export function ReadingLabel({ whose, adopted, by, options, inline = false, children }: {
  whose: Whose; adopted?: string; by?: string; options?: readonly string[]; inline?: boolean; children?: ReactNode;
}) {
  const label = whose === "counsel" && by ? `Counsel's reading (${by})` : WHOSE[whose];
  if (inline) return <span className={`reading-label reading-${whose}`}>{label}</span>;
  return (
    <aside className={`reading reading-${whose}`} aria-label={label}>
      <p className="reading-head">
        <span className="reading-tag">{whose === "open" ? "Open" : "Reading"}</span> <strong>{label}</strong>
        {adopted && <span className="muted"> adopted <time dateTime={adopted}>{adopted}</time></span>}
      </p>
      {children}
      {options && options.length > 0 && <ol className="reading-options">{options.map((o) => <li key={o}>{o}</li>)}</ol>}
      {BASIS[whose] && <p className="muted">{BASIS[whose]}</p>}
    </aside>
  );
}
