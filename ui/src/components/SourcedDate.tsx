import { Badge, type Tone } from "./Badge";
import { Doc } from "./Doc";
import type { GlyphName } from "./Glyph";
import type { DocRef } from "../lib/docref";

/** A date with where it came from (docs/paint-ui-design.md: "Every date is labeled by where it came from"). */
export interface SourcedDate {
  /** ISO date, year-month, or year. */
  date?: string;
  source: "recorded" | "implied" | "reported" | "needs input";
  docs?: DocRef[];
  /** For an implied date: "due 2027 minus a 7-year life". */
  arithmetic?: string;
  /** For a reported date: how many owners reported or confirmed it. */
  count?: number;
}

const WORD: Record<SourcedDate["source"], string> = { recorded: "recorded", implied: "implied", reported: "reported", "needs input": "needs input" };
const MEANING: Record<SourcedDate["source"], string> = {
  recorded: "From a document the association holds.",
  implied: "Worked out from other dates; not a recorded fact.",
  reported: "Reported by an owner; not the association's record.",
  "needs input": "No date on record yet. A person can enter one with its source.",
};
const TONE: Record<SourcedDate["source"], Tone> = { recorded: "good", implied: "neutral", reported: "neutral", "needs input": "warn" };
const GLYPH: Record<SourcedDate["source"], GlyphName> = { recorded: "file-check", implied: "calculator", reported: "user", "needs input": "pencil" };

export const NEEDS_INPUT_INVITATION = "None on record yet. Add the date with its source.";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2099-10-03" as "Oct 3, 2099", "2099-10" as "Oct 2099", "2099" as "2099"; anything else as given. */
export function dateText(date: string): string {
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(date);
  if (!m) return date;
  const [, y, mo, d] = m;
  if (!mo) return y;
  const month = MONTHS[Number(mo) - 1];
  if (!month) return date;
  return d ? `${month} ${Number(d)}, ${y}` : `${month} ${y}`;
}

/** A date and its source. The word is the status (recorded, implied, reported, needs input); the glyph and the tone repeat
 * it. An implied date shows its arithmetic, a reported one says how many owners reported it, a recorded one names its
 * documents, and a date that needs input is an invitation to enter it, never a blank. */
export function SourcedDate({ value, onEnter }: { value: SourcedDate; onEnter?: () => void }) {
  const { source, date } = value;
  const missing = source === "needs input" || !date;
  const word = WORD[source];
  const reported = source === "reported" && value.count !== undefined
    ? `reported by ${value.count} ${value.count === 1 ? "owner" : "owners"}` : word;
  return (
    <span className={`paint-date paint-date-${source.replace(/\s+/g, "-")}`}>
      {missing ? (
        <span className="paint-date-invite">{NEEDS_INPUT_INVITATION}</span>
      ) : (
        <time dateTime={date} className="paint-date-value">{dateText(date)}</time>
      )}{" "}
      <span title={MEANING[source]}><Badge tone={TONE[source]} glyph={GLYPH[source]}>{reported}</Badge></span>
      {source === "implied" && value.arithmetic && <span className="paint-date-arithmetic muted"> {value.arithmetic}</span>}
      {source === "reported" && <span className="paint-date-note muted"> Owner-reported, not the association's record.</span>}
      {!!value.docs?.length && (
        <span className="paint-date-docs">{value.docs.map((d, i) => <Doc key={`${d.address}#${i}`} doc={d} variant="chip" />)}</span>
      )}
      {missing && onEnter && <button type="button" className="paint-date-enter" onClick={onEnter}>Enter the date</button>}
    </span>
  );
}
