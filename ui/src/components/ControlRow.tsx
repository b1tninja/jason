import { ControlProposeConfirm } from "./ControlProposeConfirm";
import { ControlStateWord } from "./ControlStateWord";
import { Glyph } from "./Glyph";
import { Recitation } from "./Recitation";
import { boardHref, controlHref, dayOf, isSuggestion, lastAct, lookOf, type ControlQuestion, type ControlRowData, type ProposeAnswer, type RefusedControl } from "../lib/controls";

/** What the viewer's session says, passed down so a row asks the server nothing: the name a proposal goes under, and, for an
 * administrator viewing as someone else, whom (the proposal is refused then). */
export interface ProposeAs { by?: string; actingAs?: string; onProposed?: (answer: ProposeAnswer) => void }

/** Whether the loader's sentence only says what the badge beside it already says ("adopted, in force" twice): the same words, or the badge's
 * words with nothing but punctuation added. */
export function sameAsBadge(sentence: string, badge: string | undefined): boolean {
  if (!badge) return false;
  const plain = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();
  const a = plain(sentence), b = plain(badge);
  return a === b || (a.includes(b) && !/[a-z0-9]/.test(a.replace(b, "")));
}

/** The line a declined, deferred, or retired control carries: its reason, its date, and the date it may be asked again. */
function Closing({ row }: { row: ControlRowData }) {
  const act = row.state === "declined" || row.state === "deferred" || row.state === "retired" ? lastAct(row.history, row.state === "declined" ? "decline" : row.state === "deferred" ? "defer" : "retire") : undefined;
  if (!act) return null;
  return (
    <p className="muted control-row-closing">
      {act.at && <>On <time dateTime={dayOf(act.at)}>{dayOf(act.at)}</time>. </>}
      {act.why && <>{act.why}{/[.!?]$/.test(act.why) ? "" : "."} </>}
      {act.againOn && <>May be asked again after <time dateTime={act.againOn}>{act.againOn}</time> (the board's date).</>}
    </p>
  );
}

/** One control in the list: its title, its standing in a word and a glyph, the provision's citation, a line of what it
 * requires (the loader's), and "Propose" when it is a suggestion. The title is the link to the card and covers the row's
 * width; "Propose" stays its own control above it. A suggestion never says it is in force. `inStep` is the onboarding step's
 * row: the provision's words under a disclosure, and no per-row Propose (the step's one button does it for every row). */
export function ControlRow({ row, as = {}, inStep = false }: { row: ControlRowData; as?: ProposeAs; inStep?: boolean }) {
  const effective = row.effective;
  return (
    <li className="control-row" data-key={row.key} data-standing={row.standing}>
      <div className="control-row-head">
        <h3 className="control-row-title"><a className="control-row-link" href={controlHref(row.key)}>{row.title}</a></h3>
        <ControlStateWord standing={row.standing} word={row.stateWord} effective={effective} />
        {row.basis.citation && <cite className="control-row-cite muted">{row.basis.citation}</cite>}
      </div>
      <p className="control-row-summary">{row.summary}</p>
      {row.state === "adopted" && row.stateWord && !sameAsBadge(row.stateWord, lookOf(row.standing, effective)?.word) && <p className="muted control-row-words">{row.stateWord}</p>}
      {row.state === "proposed" && (
        <p className="muted control-row-words">
          {row.proposedAs ? <>Before the board as item <a href={boardHref(row.proposedAs)}>{row.proposedAs}</a>{row.proposedStatus ? ` (${row.proposedStatus})` : ""}.</> : "Put before the board."} The board decides; the secretary records it.
        </p>
      )}
      <Closing row={row} />
      {inStep && row.basis.words && (
        <details className="control-row-provision">
          <summary>The provision, whole</summary>
          <Recitation citation={{ found: true, citation: row.basis.citation, text: row.basis.words }} />
        </details>
      )}
      {isSuggestion(row) && !inStep && (
        <div className="control-row-act">
          <ControlProposeConfirm controlKey={row.key} title={row.title} by={as.by} actingAs={as.actingAs} compact onProposed={as.onProposed} />
        </div>
      )}
    </li>
  );
}

/** A provision jason cannot read cleanly: a question for the board or counsel, not a suggestion. Its words are recited and
 * the loader says why they are unclear. There is nothing to propose. */
export function ControlQuestionRow({ q }: { q: ControlQuestion }) {
  return (
    <li className="control-row control-question" data-key={q.key} data-kind="question">
      <div className="control-row-head">
        <h3 className="control-row-title">{q.citation || q.title}</h3>
        <span className="badge badge-warn"><Glyph name="circle-question-mark" size="1em" className="badge-glyph" />question for the board or counsel</span>
      </div>
      <p className="control-row-summary">No suggestion: {q.whyQuestion || "this provision does not read cleanly"}</p>
      {q.words && <Recitation citation={{ found: true, citation: q.citation, text: q.words }} />}
    </li>
  );
}

/** A control that would go below a floor is never offered: it is listed with the floor, recited, and a plain sentence.
 * It has no Propose and no Adopt. */
export function RefusedRow({ r }: { r: RefusedControl }) {
  return (
    <li className="control-row control-refused" data-kind="refused">
      <div className="control-row-head">
        <h3 className="control-row-title">{r.title}</h3>
        <span className="badge badge-bad"><Glyph name="ban" size="1em" className="badge-glyph" />refused</span>
      </div>
      <p className="control-row-summary">Refused: {r.why} A control only adds.</p>
      <Recitation citation={{ found: true, citation: r.floor.citation, text: r.floor.words }} />
    </li>
  );
}
