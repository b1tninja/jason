import { Glyph } from "./Glyph";
import { BasisPill } from "./BasisPill";
import { DueDate } from "./DueDate";
import { Pill } from "./Pill";
import { ReadingLabel } from "./ReadingLabel";
import { Recitation, type Citation } from "./Recitation";
import { clockWords, type LawWords, type RunClock } from "../lib/work";

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
        {/* a dated overdue clock is already "7d overdue" in the date: the status word would say it a second time */}
        {clock.status && clock.status !== "upcoming" && !(clock.status === "overdue" && clock.due) && <> <Pill word={clock.status} /></>}
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

/** The clocks one step keeps for each of its items, as one card: how many, how many are late, and the nearest date, with the
 * basis word. Each item's own date and words are in the step's item table; the law's words (if the basis is the law) are once. */
function ItemClockCard({ clocks, today }: { clocks: readonly RunClock[]; today?: Date }) {
  const head = clocks[0];
  const late = clocks.filter((c) => clockWords(c).late);
  const open = clocks.filter((c) => c.due && ["upcoming", "due", "overdue"].includes(c.status)).map((c) => c.due as string).sort();
  const next = open[0] ?? null;
  const pastLegal = head.legal && late.length > 0;
  return (
    <li className={`work-clock work-clock-items${late.length ? " work-clock-past" : ""}`} data-item-clocks={clocks.length}>
      <div className="work-clock-head">
        <strong>{head.label || head.stepTitle || head.key}</strong> <BasisPill basis={head.basis} label={head.basisLabel} />
        {head.cite && <span className="muted"> {head.cite}</span>}
      </div>
      <p className="muted work-clock-scope">{head.stepTitle ? `Step: ${head.stepTitle}` : "A step"} · one clock for each of its {clocks.length} {clocks.length === 1 ? "item" : "items"}</p>
      <p>
        {late.length ? <><Glyph name="triangle-alert" size="1em" /> <strong>{late.length} late</strong>, </> : "None late, "}
        {next ? <>next due <DueDate iso={next} today={today} /></> : "no date to come"}. Each item's date is in the step's table.
      </p>
      {pastLegal && (
        <p className="work-past" role="note"><Glyph name="triangle-alert" size="1em" /> Past a legal date for {late.length} {late.length === 1 ? "item" : "items"}. The law's words are below.</p>
      )}
      {head.law && <LawBlock law={head.law} cite={head.cite} />}
    </li>
  );
}

/** The run's deadlines, each with whose date it is. A `law` clock recites the statute's operative words from the stored text
 * before any reading, and jason's reading follows, labeled as a reading. A run past a legal clock says so in the law's
 * words. A proposed number is never drawn as a stamp (`BasisPill`). */
export function ClockStrip({ clocks, today }: { clocks: readonly RunClock[]; today?: Date }) {
  if (!clocks.length) return <p className="muted">This run has no dates yet.</p>;
  const perItem = new Map<string, RunClock[]>();
  for (const c of clocks) if (c.item) perItem.set(c.step, [...(perItem.get(c.step) ?? []), c]);
  const seen = new Set<string>();
  return (
    <ul className="work-clocks">
      {clocks.map((c) => {
        if (!c.item) return <ClockCard key={c.key} clock={c} today={today} />;
        if (seen.has(c.step)) return null;           // the step's item clocks are one card, drawn where the first of them stands
        seen.add(c.step);
        return <ItemClockCard key={`items-${c.step}`} clocks={perItem.get(c.step) ?? [c]} today={today} />;
      })}
    </ul>
  );
}
