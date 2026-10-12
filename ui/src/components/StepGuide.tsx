import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import "../styles/work-guide.css";
import { Badge, type Tone } from "./Badge";
import { BasisPill } from "./BasisPill";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Glyph, type GlyphName } from "./Glyph";
import { ReadingLabel } from "./ReadingLabel";
import { Recitation } from "./Recitation";
import { PHONE_QUERY, useMediaQuery } from "../lib/useMediaQuery";
import {
  safeAddress, type EnableState, type GuideAsk, type GuideCommand, type GuideLook, type GuideRule, type NudgeBand, type StepEnable,
  type StepNudge,
} from "../lib/work";

// The step panel's guide, enable strip, and nudge line (docs/console/screens/work-guide.md). Every state is a word and a glyph,
// never colour alone. Nothing here runs a command, sends a message, or decides: it reads what the loader sent and offers Copy.

// -- the enable strip -------------------------------------------------------------------------------------------------------

export const ENABLE_LOOK: Readonly<Record<EnableState, { glyph: GlyphName; tone: Tone }>> = {
  ready: { glyph: "user-check", tone: "good" },
  "not yours": { glyph: "user-x", tone: "neutral" },
  "not ready": { glyph: "hourglass", tone: "neutral" },
  "needs an integration": { glyph: "key-round", tone: "warn" },
  "needs a second person": { glyph: "users", tone: "warn" },
  "terminal only": { glyph: "monitor", tone: "neutral" },
  "viewing as": { glyph: "user-cog", tone: "warn" },
  draft: { glyph: "circle-dashed", tone: "neutral" },
  paused: { glyph: "circle-pause", tone: "warn" },
  closed: { glyph: "lock", tone: "neutral" },
  done: { glyph: "circle-check", tone: "good" },
  skipped: { glyph: "ban", tone: "neutral" },
  "not applicable": { glyph: "minus", tone: "neutral" },
  superseded: { glyph: "minus", tone: "neutral" },
};

const officeWords = (office: string) => (office === "anyone" ? "anyone" : `the ${office}`);

/** Who holds the offices that may act on the step, on the roster: names only, and "no one holds" for a vacant office. */
function Holders({ enable }: { enable: StepEnable }) {
  if (!enable.holders.length) return null;
  return (
    <ul className="guide-holders" aria-label="Who holds this step">
      {enable.holders.map((h) => (
        <li key={h.office}>
          {h.owner ? (
            <>The run's owner sees to it{h.names.length ? `: ${h.names.join(", ")}` : ""}.</>
          ) : h.vacant ? (
            <><strong>No one holds the {h.office} office.</strong>{h.backup ? ` Backup: ${officeWords(h.backup.office)}${h.backup.basis ? ` (${h.backup.basis})` : ""}.` : ""}</>
          ) : (
            <>Held by {officeWords(h.office)}: {h.names.join(", ")}.{enable.state === "not yours" && h.backup ? ` Backup: ${officeWords(h.backup.office)}${h.backup.basis ? ` (${h.backup.basis})` : ""}.` : ""}</>
          )}
        </li>
      ))}
    </ul>
  );
}

/** The enable strip: one line with the state word and glyph, the reason under it, and what is missing. Never collapsed. */
export function StepEnableStrip({ enable }: { enable: StepEnable }) {
  const look = ENABLE_LOOK[enable.state] ?? { glyph: "info" as GlyphName, tone: "neutral" as Tone };
  const settled = ["done", "skipped", "not applicable", "superseded"].includes(enable.state);
  return (
    <div className={`guide-enable guide-enable-${enable.state.replace(/\s+/g, "-")}`} data-state={enable.state}>
      <p className="guide-enable-line">
        <Badge tone={look.tone} glyph={look.glyph}>{enable.state}</Badge> <span className="guide-enable-word">{enable.word}</span>
      </p>
      {enable.detail && <p className="muted guide-enable-detail">{enable.detail}</p>}
      {enable.missing.length > 0 && (
        <ul className="guide-missing">
          {enable.missing.map((m) => (
            <li key={m.what}>{m.why}. To connect it: <code>{m.fix}</code></li>
          ))}
        </ul>
      )}
      {enable.waitsOn && <p className="muted">Step {enable.waitsOn.n} must be done first.</p>}
      {!settled && <Holders enable={enable} />}
      {!settled && enable.accessNote && <p className="muted">{enable.accessNote}</p>}
    </div>
  );
}

// -- the nudge line ---------------------------------------------------------------------------------------------------------

export const BAND_LOOK: Readonly<Record<Exclude<NudgeBand, "quiet">, { glyph: GlyphName; tone: Tone }>> = {
  legal: { glyph: "flag", tone: "bad" },
  late: { glyph: "alarm-clock", tone: "bad" },
  date: { glyph: "calendar", tone: "warn" },
  soon: { glyph: "clock", tone: "warn" },
  stale: { glyph: "ellipsis", tone: "neutral" },
};

/** LEGAL, OVERDUE, due soon, open, or needs a date: the digest's own word, with a glyph. A quiet step has none. */
export function NudgeWord({ band, word }: { band: NudgeBand; word: string }) {
  if (band === "quiet" || !word) return null;
  const look = BAND_LOOK[band];
  return <span className={`guide-band guide-band-${band}`}><Badge tone={look.tone} glyph={look.glyph}>{word}</Badge></span>;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** How far off the date is, in words: "due today", "3 days to go", "6 days late". */
export function daysWords(days: number | null | undefined): string {
  if (days === null || days === undefined) return "";
  if (days === 0) return "due today";
  return days < 0 ? `${plural(-days, "day")} late` : `${plural(days, "day")} to go`;
}

/** The nudge line: the date and whose it is, the band word, how far off, who else sees it, and a claim with its one button. A
 * legal date carries no snooze; nothing here sends anything. */
export function StepNudgeLine({ nudge, claim }: { nudge: StepNudge; claim?: ReactNode }) {
  const items = nudge.items && nudge.items.total > 1
    ? `${nudge.items.notDone} of ${plural(nudge.items.total, "item")} not done${nudge.items.earliest ? `; the earliest due ${nudge.items.earliest}` : ""}.`
    : "";
  const proposed = (nudge.band === "soon" || nudge.band === "stale" || nudge.escalatedTo) && nudge.numbers.note;
  return (
    <div className={`guide-nudge guide-nudge-${nudge.band}`} data-band={nudge.band}>
      <p className="guide-nudge-line">
        {nudge.due ? (
          <>Due <time dateTime={nudge.due}>{nudge.due}</time> <BasisPill basis={nudge.basis} label={nudge.basisLabel} /></>
        ) : nudge.band === "date" ? (
          <>A clock needs a date, and none is set.</>
        ) : nudge.openDays !== null && nudge.band === "stale" ? (
          <>Open for {plural(nudge.openDays, "day")}.</>
        ) : (
          <span className="muted">No date.</span>
        )}{" "}
        <NudgeWord band={nudge.band} word={nudge.word} />
        {nudge.due && nudge.days !== null && <span className="guide-days"> {daysWords(nudge.days)}</span>}
      </p>
      {nudge.label && <p className="muted guide-nudge-label">{nudge.label}</p>}
      {items && <p className="guide-nudge-items">{items}</p>}
      {nudge.escalatedTo && (
        <p className="muted guide-escalated">Also seen by {nudge.escalatedTo === "the whole board" ? nudge.escalatedTo : officeWords(nudge.escalatedTo)}: {nudge.escalatedWhy}. Nothing is sent to anyone.</p>
      )}
      {nudge.claim && (
        <p className="guide-claim">
          <Glyph name="hand" size="1em" /> {nudge.claim.mine ? "You are" : `${nudge.claim.by} is`} on it since <time dateTime={nudge.claim.at.slice(0, 10)}>{nudge.claim.at.slice(0, 10)}</time>
          {nudge.claim.stale ? ", still open" : ""}.
        </p>
      )}
      {proposed && <p className="muted guide-proposed">The lead, the open-a-while threshold, and the escalation delay are {nudge.numbers.note}.</p>}
      {claim}
    </div>
  );
}

// -- a collapsible section --------------------------------------------------------------------------------------------------

/** A titled region of the guide. Open by default on a wide screen and collapsed to its heading and count on a phone; the button
 * in the heading toggles it. `fixed` sections (Do this) never collapse. Not drawn when there is nothing in it. */
export function GuideSection({ title, count, fixed = false, startClosed = false, children }: {
  title: string; count?: string; fixed?: boolean; startClosed?: boolean; children: ReactNode;
}) {
  const narrow = useMediaQuery(PHONE_QUERY);
  const [mine, setMine] = useState<boolean | null>(null);
  const id = useId();
  const open = fixed || (mine ?? (!narrow && !startClosed));
  return (
    <section className="guide-section work-step-part" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`}>
        {fixed ? (
          title
        ) : (
          <button type="button" className="guide-toggle" aria-expanded={open} aria-controls={`${id}-body`} onClick={() => setMine(!open)}>
            <Glyph name={open ? "chevron-down" : "chevron-right"} size="1em" /> {title}{count ? <span className="muted guide-count"> ({count})</span> : null}
          </button>
        )}
      </h3>
      <div id={`${id}-body`} hidden={!open}>{children}</div>
    </section>
  );
}

// -- look at ----------------------------------------------------------------------------------------------------------------

/** One read: its label, its count and when it was read, at most five handles, and the screen to open. A read that cannot read
 * says "could not read: REASON" and shows no count; it never says there is nothing to look at. */
export function LookAtList({ look }: { look: GuideLook }) {
  if (look.unavailable)
    return (
      <div className="guide-look guide-look-unavailable">
        <strong>{look.label}</strong>: <span className="guide-unreadable">could not read: {look.unavailable}</span>
      </div>
    );
  return (
    <div className="guide-look">
      <p className="guide-look-line">
        <strong>{look.label}</strong>:{" "}
        <span className="guide-count-number">{look.count}</span>{look.of !== undefined ? ` of ${look.of} on disk` : ""}
        <span className="muted"> as of {look.asOf}</span>
        {look.screen && <> <a href={look.screen.href}>Open in {look.screen.name}</a></>}
      </p>
      {look.kind === "read" && look.rows.length > 0 && (
        <ul className="guide-look-rows">{look.rows.map((r) => <li key={r}><code className="chip">{safeAddress(r)}</code></li>)}</ul>
      )}
    </div>
  );
}

// -- the rule ---------------------------------------------------------------------------------------------------------------

/** A cite recited whole from what is stored, with the version in force and the caveat, then jason's reading, labeled. A cite the
 * shelf cannot resolve says so, with the command that brings it down, and no paraphrase. */
export function RuleBlock({ rule }: { rule: GuideRule }) {
  if (rule.missing)
    return (
      <div className="guide-rule guide-rule-missing">
        <p><strong>{rule.key}</strong>: {rule.missing}</p>
        {rule.command && <Command cmd={rule.command} note="Run it in a terminal to put the words on the shelf." />}
        {rule.reading && <ReadingLabel whose="jason"><p>{rule.reading}</p></ReadingLabel>}
      </div>
    );
  return (
    <div className="guide-rule">
      <div className="guide-rule-words" tabIndex={0} role="region" aria-label={`The words of ${rule.key}`}>
        <Recitation citation={{ found: true, citation: rule.key, text: rule.words, inForce: rule.version, caveat: rule.restatement }} />
      </div>
      {rule.source && <p className="muted guide-rule-source">Source: {rule.source}</p>}
      {rule.caveats.map((c) => <p key={c} className="muted">{c}</p>)}
      {rule.reading && <ReadingLabel whose="jason"><p>{rule.reading}</p></ReadingLabel>}
    </div>
  );
}

// -- the checklist ----------------------------------------------------------------------------------------------------------

const tickKey = (run: string, step: string, text: string) => `jason.guide.${run}.${step}.${text}`;

function readTick(key: string): boolean {
  try { return window.localStorage.getItem(key) === "1"; } catch { return false; }
}
function writeTick(key: string, on: boolean) {
  try { if (on) window.localStorage.setItem(key, "1"); else window.localStorage.removeItem(key); } catch { /* storage may be unavailable */ }
}

export interface Checklist { ticks: boolean[]; toggle: (i: number) => void; required: number; done: number; left: number }

/** The viewer's ticks. A required item starts unticked each time the panel opens (it is a check the person makes before Mark done);
 * an unrequired tick is a convenience kept in this browser, wrapped because storage can be unavailable, and is never run state. */
export function useChecklist(run: string, step: string, items: readonly { text: string; required: boolean }[]): Checklist {
  const sig = items.map((it) => `${it.required ? "!" : ""}${it.text}`).join("\n");
  const initial = () => items.map((it) => !it.required && readTick(tickKey(run, step, it.text)));
  const [ticks, setTicks] = useState<boolean[]>(initial);
  const first = useRef(true);
  // a different step (or a changed list) starts again; the first render keeps what it just read
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    setTicks(initial());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, step, sig]);
  const toggle = (i: number) => setTicks((prev) => {
    const next = prev.slice();
    next[i] = !next[i];
    if (!items[i].required) writeTick(tickKey(run, step, items[i].text), next[i]);
    return next;
  });
  const required = items.filter((it) => it.required).length;
  const done = items.filter((it, i) => it.required && ticks[i]).length;
  return { ticks, toggle, required, done, left: required - done };
}

/** Real checkboxes, each labelled; "required" is in the label's text, not only a mark. */
export function GuideChecklist({ items, state }: { items: readonly { text: string; required: boolean }[]; state: Checklist }) {
  return (
    <div className="guide-checklist">
      <ul>
        {items.map((it, i) => (
          <li key={it.text}>
            <label>
              <input type="checkbox" checked={!!state.ticks[i]} onChange={() => state.toggle(i)} />{" "}
              <span>{it.text}{it.required ? <strong className="guide-required"> (required)</strong> : null}</span>
            </label>
          </li>
        ))}
      </ul>
      {state.required > 0 && (
        <p className="muted guide-progress" aria-live="polite">{state.done} of {state.required} required ticked{state.left > 0 ? ": Mark done waits for the rest." : "."}</p>
      )}
    </div>
  );
}

// -- the command ------------------------------------------------------------------------------------------------------------

/** Each command on its own line with Copy, the placeholders filled where known and the rest marked "fill in". The page never runs one. */
export function CommandList({ commands }: { commands: readonly GuideCommand[] }) {
  return (
    <ol className="guide-commands">
      {commands.map((c, i) => (
        <li key={`${i}-${c.raw}`}>
          <Command cmd={c.text} note={c.terminalOnly ? `A person applies this at a terminal.${c.note ? ` ${c.note}` : ""}` : c.note || "Run it in a terminal. The page never runs a command."} />
          {c.fillIn.length > 0 && <p className="muted guide-fill">{c.fillIn.join(", ")} {c.fillIn.length === 1 ? "is" : "are"} yours to fill in.</p>}
        </li>
      ))}
    </ol>
  );
}

// -- ask --------------------------------------------------------------------------------------------------------------------

/** The offices to ask, with the holder as the roster has it ("Vacant" if none); names only, never a phone or an email. */
export function AskOffices({ ask }: { ask: readonly GuideAsk[] }) {
  if (!ask.length) return <p>No one is named for this. Tell the president.</p>;
  return (
    <ul className="guide-ask">
      {ask.map((a) => (
        <li key={a.office}>{officeWords(a.office)}: {a.vacant || !a.names.length ? <strong>Vacant</strong> : a.names.join(", ")}</li>
      ))}
    </ul>
  );
}

// -- claim ------------------------------------------------------------------------------------------------------------------

/** "I'm on it" or "Release": a note on the step in the viewer's name, one confirm. It grants nothing and blocks nobody. */
export function ClaimButton({ stepN, stepTitle, mine, name, busy, onClaim }: {
  stepN: number; stepTitle: string; mine: boolean; name: string; busy: boolean; onClaim: (release: boolean) => void;
}) {
  return (
    <div className="guide-claim-act">
      <Confirm busy={busy} label={mine ? "Release" : "I'm on it"} onConfirm={() => onClaim(mine)}
        summary={<>Note on step {stepN}, {stepTitle}, under the name {name || "the signed-in person"}: {mine ? "no longer on it" : "is on it"}. It assigns nothing; anyone who holds the step may still act.</>}>
        {mine ? "Release" : "I'm on it"}
      </Confirm>
    </div>
  );
}

// -- the guide as a whole, for the panel to place ----------------------------------------------------------------------------

/** The words that count a section in its heading on a phone: "2 reads", "3 items". */
export const countWords = (n: number, one: string, many = `${one}s`) => plural(n, one, many);
