import { Glyph } from "./Glyph";
import { BasisPill } from "./BasisPill";
import { DueDate } from "./DueDate";
import { Pill } from "./Pill";
import { ReadingLabel } from "./ReadingLabel";
import { Recitation, type Citation } from "./Recitation";
import type { LawWords, RunClock } from "../lib/work";

/** The statute's words as the authorities shelf holds them, as a `Citation` for `Recitation`. A shelf that lacks the
 * section recites nothing and says why. A path the server may have named as the source is not shown. */
export function lawCitation(law: LawWords, cite: string): Citation {
  const citation = law.section || law.citation || cite;
  if (law.missing || !law.words) return { found: false, citation, detail: law.missing || "The authorities shelf holds no words for it" };
  const caveat = [law.restatement, ...law.caveats].filter(Boolean).join(" ");
  return { found: true, citation, text: law.words, inForce: law.note || undefined, caveat: caveat || undefined };
}

/** A legal clock's recited words (the operative words, then the citation), and only after them jason's reading, labeled. */
export function LawBlock({ law, cite }: { law: LawWords; cite: string }) {
  const versions = law.versions.length > 1 ? law.versions : null;
  return (
    <div className="work-law">
      {versions ? (
        versions.map((v) => (
          <Recitation key={v.digest} citation={{ found: !!v.words, citation: law.section || law.citation || cite, text: v.words, inForce: v.label }} />
        ))
      ) : (
        <Recitation citation={lawCitation(law, cite)} />
      )}
      {law.undecided && <p className="notice notice-warn">Two versions of this provision are on the shelf; which governs is not decided here. The board asks counsel.</p>}
      {law.reading && (
        <ReadingLabel whose="jason">
          <p>{law.reading}</p>
          <p className="muted">{law.readingLabel}</p>
        </ReadingLabel>
      )}
    </div>
  );
}

function ClockCard({ clock, today }: { clock: RunClock; today?: Date }) {
  const satisfied = clock.status === "satisfied";
  const pastLegal = clock.legal && clock.past;
  return (
    <li className={`work-clock${clock.past ? " work-clock-past" : ""}`}>
      <div className="work-clock-head">
        <strong>{clock.label || clock.key}</strong>{" "}
        <DueDate iso={clock.due} today={today} settled={satisfied} /> <BasisPill basis={clock.basis} label={clock.basisLabel} />
        {clock.status && clock.status !== "upcoming" && <> <Pill word={clock.status} /></>}
        {clock.cite && <span className="muted"> {clock.cite}</span>}
      </div>
      <p className="muted work-clock-scope">{clock.scope === "step" && clock.stepTitle ? `Step: ${clock.stepTitle}` : "The whole run"}</p>
      {pastLegal && (
        <p className="work-past" role="note">
          <Glyph name="triangle-alert" size="1em" /> Past a legal date{clock.days !== null ? `: ${Math.abs(clock.days)} ${Math.abs(clock.days) === 1 ? "day" : "days"} ago` : ""}.
          {" "}The law's words are below.
        </p>
      )}
      {clock.law && <LawBlock law={clock.law} cite={clock.cite} />}
    </li>
  );
}

/** The run's deadlines, each with whose date it is. A `law` clock recites the statute's operative words from the stored text
 * before any reading, and jason's reading follows, labeled as a reading. A run past a legal clock says so in the law's
 * words. A proposed number is never drawn as a stamp (`BasisPill`). */
export function ClockStrip({ clocks, today }: { clocks: readonly RunClock[]; today?: Date }) {
  if (!clocks.length) return <p className="muted">This run has no dates yet.</p>;
  return <ul className="work-clocks">{clocks.map((c) => <ClockCard key={c.key} clock={c} today={today} />)}</ul>;
}
