import { Pill } from "./Pill";
import { GRADES, CONFIRM_AT_SOURCE, type TextGradeWord } from "../lib/inspections";

/** Where the words of a `Recitation` came from, attached to them: the grade's word first (a `Pill` with its meaning),
 * its glyph second, and the grade in plain text beside it. A digest, or a notice's quotation, always shows "confirm at
 * the source" as text, never only in a tooltip. A `legislature` grade says where the words came from; it is not an
 * endorsement, so it carries no good tone. */
export function TextGrade({ grade }: { grade: TextGradeWord }) {
  const g = GRADES[grade];
  if (!g) return null;
  return (
    <span className="insp-grade" data-grade={grade}>
      <Pill word={grade} meaning={g.meaning} glyph={g.glyph} />
      <span className="insp-grade-label"> {g.label}</span>
      {g.confirm && <span className="insp-grade-confirm"> · {CONFIRM_AT_SOURCE}</span>}
      <span className="visually-hidden">. {g.meaning}</span>
    </span>
  );
}
