import { useId, type ReactNode } from "react";
import { ControlProposeConfirm } from "./ControlProposeConfirm";
import type { ProposeAs } from "./ControlRow";
import { ControlStateWord } from "./ControlStateWord";
import { Glyph } from "./Glyph";
import { ReadingLabel } from "./ReadingLabel";
import { Recitation, type Citation } from "./Recitation";
import { RosterCheck } from "./RosterCheck";
import { Stamp } from "./Stamp";
import {
  actWord, boardHref, dayOf, decisionHref, lastAct, paramWords, voteCounts, WORDS,
  type ControlChanged, type ControlRowData, type ControlTouch, type OneControl,
} from "../lib/controls";
import "../styles/controls.css";

const sentence = (s: string) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);

/** The card's dates in the board's words: when it was adopted and when it binds (the effective date is the board's). */
export function controlDates(row: ControlRowData): string {
  const adopt = lastAct(row.history, "adopt");
  const when = (a: string) => dayOf(lastAct(row.history, a)?.at);
  if (row.state === "adopted") {
    const day = dayOf(adopt?.at);
    const head = day ? `Adopted ${day}` : "Adopted";
    if (!row.effective) return `${head} · no effective date is set`;
    return row.inForce.ok
      ? `${head} · in force since ${row.effective} (the board's date)`
      : `${head} · takes effect ${row.effective} (the board's date)`;
  }
  const act = { proposed: "propose", suggested: "suggest", declined: "decline", deferred: "defer", retired: "retire" }[row.state];
  const day = act ? when(act) : "";
  return `${row.state.charAt(0).toUpperCase()}${row.state.slice(1)}${day ? ` ${day}` : ""}`;
}

function Band({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  const id = useId();
  return (
    <section className="card control-band" id={`control-band-${n}`} aria-labelledby={id} tabIndex={-1} data-band={n}>
      <header className="card-head"><h2 id={id}><span className="control-band-n">{n}</span> {title}</h2></header>
      {children}
    </section>
  );
}

/** A provision changed since the control was adopted (an amendment): above band 1, with the old and new words side by
 * side, both recited. The control stays as the board adopted it; the board decides whether it still serves. */
export function ControlChangedBanner({ changed, citation, itemId }: { changed: ControlChanged; citation: string; itemId?: string | null }) {
  const was = changed.was ?? changed.wasWords ?? "";
  const now = changed.now ?? changed.words ?? "";
  const cite = changed.citation || citation;
  return (
    <section className="changed-banner control-changed" aria-label="A provision changed">
      <h3><Glyph name="triangle-alert" size="1em" /> A provision changed since this control was adopted</h3>
      <p>
        {cite} changed{changed.changedOn ? <> on <time dateTime={dayOf(changed.changedOn)}>{dayOf(changed.changedOn)}</time></> : null}
        {changed.basis ? ` (${changed.basis})` : ""}. The control stays as the board adopted it. The board decides whether it still serves.
      </p>
      <div className="control-changed-pair">
        {was && <div><h4>As the control was adopted</h4><Recitation citation={{ found: true, citation: cite, text: was }} /></div>}
        {now && <div><h4>As the documents hold it now</h4><Recitation citation={{ found: true, citation: cite, text: now }} /></div>}
      </div>
      {itemId && <p><a href={boardHref(itemId)}>Open the board item</a></p>}
    </section>
  );
}

function Touch({ t }: { t: ControlTouch }) {
  if (t.kind === "approval kind" && t.key)
    return (
      <li>
        <a href="#/approvals">{t.title}</a> (<code>{t.key}</code>): {t.with ? sentence(t.with) : "no change asked."}{" "}
        {t.changes ? <strong>Stricter than the kind's own rule ({t.builtin}).</strong> : <>Unchanged: the kind's own rule is {t.builtin}.</>}
      </li>
    );
  return <li>{t.kind}: {t.what}{t.note ? <span className="muted"> {sentence(t.note)}</span> : null}</li>;
}

function History({ row }: { row: ControlRowData }) {
  const rows = [...row.history].reverse().map((h, i) => ({
    key: `${h.act}-${h.at}-${i}`, day: dayOf(h.at), word: actWord(h.act), by: h.by, why: h.why, decision: h.decision, again: h.againOn,
  }));
  const effective = row.state === "adopted" && row.effective
    ? { key: "effective", day: row.effective, word: row.inForce.ok ? "in force" : "takes effect (the board's date)", by: "", why: "", decision: "", again: "" }
    : null;
  const all = effective ? [effective, ...rows].sort((a, b) => b.day.localeCompare(a.day)) : rows;
  if (!all.length) return <p className="muted">No history is recorded.</p>;
  return (
    <ol className="control-trail" aria-label="History, newest first">
      {all.map((h, i) => (
        <li key={h.key} aria-current={i === 0 ? "true" : undefined}>
          <time dateTime={h.day || undefined} className="control-trail-date">{h.day || "undated"}</time>{" "}
          <strong>{h.word}</strong>
          {h.by ? <> by {h.by}</> : h.key !== "effective" ? <span className="muted"> by jason, from a reading of the provision</span> : null}
          {h.decision && <span className="muted"> · decision {h.decision}</span>}
          {h.why && <span className="muted"> · {h.why}</span>}
          {h.again && <span className="muted"> · may be asked again after {h.again} (the board's date)</span>}
          {i === 0 && <span className="control-trail-now"> (current)</span>}
        </li>
      ))}
    </ol>
  );
}

/** What the board adopted, or the state it stands in instead: the stamp and the decision for an adopted control; a reason
 * and dates for a declined, deferred, or retired one; where it waits for a proposed one. Not drawn for a suggestion. */
function Decided({ row, as, secretary }: { row: ControlRowData; as: ProposeAs; secretary: boolean }) {
  const adopt = lastAct(row.history, "adopt");
  if (row.state === "adopted")
    return (
      <>
        <div className="row wrap"><Stamp word="adopted" date={dayOf(adopt?.at)} tilt={0} /></div>
        <p><strong>{row.summary}</strong></p>
        {row.decision ? (
          <p>
            Decision <code className="chip">{row.decision.id}</code>
            {row.decision.meeting ? ` · ${row.decision.meeting}` : ""}
            {row.decision.outcome ? ` · ${row.decision.outcome}` : ""}
            {row.decision.tally ? ` · vote as taken: ${voteCounts(row.decision.tally)}` : ""}
            {" · "}{WORDS.recordedBy} <a href={decisionHref(row.decision.id)}>Open the decision</a>
          </p>
        ) : (
          <p className="muted">No decision is linked to this control.</p>
        )}
      </>
    );
  if (row.state === "proposed")
    return (
      <>
        <p>
          The board has not decided. It is before the board{row.proposedAs ? <> as item <a href={boardHref(row.proposedAs)}>{row.proposedAs}</a>{row.proposedStatus ? ` (${row.proposedStatus})` : ""}</> : ""}.
          The board decides at a meeting; the secretary records the decision.
        </p>
        <div className="row wrap">
          <ControlProposeConfirm controlKey={row.key} title={row.title} by={as.by} actingAs={as.actingAs} label="Refresh the board item" onProposed={as.onProposed} />
          {secretary && <a href={decisionHref()}>{WORDS.openInDecisions}</a>}
        </div>
      </>
    );
  const act = lastAct(row.history, { declined: "decline", deferred: "defer", retired: "retire" }[row.state as "declined"] ?? "");
  return (
    <>
      <p><ControlStateWord standing={row.standing} word={row.stateWord} /> {act?.at ? <time dateTime={dayOf(act.at)}>{dayOf(act.at)}</time> : null}</p>
      {act?.why && <p>Reason: {act.why}</p>}
      {act?.againOn && <p>May be asked again after <time dateTime={act.againOn}>{act.againOn}</time> (the board's date).</p>}
      {row.decision && <p className="muted">Decision <code className="chip">{row.decision.id}</code> · {WORDS.recordedBy} <a href={decisionHref(row.decision.id)}>Open the decision</a></p>}
      {(row.state === "declined" || row.state === "deferred") && (
        <ControlProposeConfirm controlKey={row.key} title={row.title} by={as.by} actingAs={as.actingAs} label="Propose again" onProposed={as.onProposed} />
      )}
    </>
  );
}

/** One control, the six bands in this order so the card reads from the document to its effect: the provision, what jason
 * suggested, what the board adopted, what it changes, whether the roster can satisfy it, and the history. A suggestion has
 * bands 1, 2, 4, 5, and 6 and a "Propose to the board" button; band 3 is the board's and a suggestion has none. The
 * provision's words are recited before jason's reading, which is labeled as jason's. */
export function ControlCard({ data, as = {}, secretary = false }: { data: OneControl; as?: ProposeAs; secretary?: boolean }) {
  const row = data.control;
  const suggestion = row.state === "suggested";
  const words = row.basis.words || (data.provision.found ? data.provision.words ?? "" : "");
  const cite: Citation = words
    ? { found: true, citation: row.basis.citation || data.provision.citation || row.title, text: words, address: data.provision.address || undefined }
    : { found: false, citation: row.basis.citation || row.title, reason: "no_words_stored", detail: data.provision.note || "The control stores no words for its provision" };
  const floorWords = row.floor.provision ? paramWords(row.floor.provision) : "";
  const lacking = row.standing === "in-force-roster-lacks";
  const ahead = row.standing === "adopted-not-in-force";
  const bands = ["The provision", "What jason suggested", ...(suggestion ? [] : ["What the board adopted"]), "What it changes", "Can the roster satisfy it", "History"];
  const go = (n: number) => {
    const el = document.getElementById(`control-band-${n}`);
    el?.focus();
    try { el?.scrollIntoView?.({ block: "start" }); } catch { /* not every window scrolls */ }
  };
  const nums = suggestion ? [1, 2, 4, 5, 6] : [1, 2, 3, 4, 5, 6];
  return (
    <div className="stack control-card" data-state={row.state} data-standing={row.standing}>
      {lacking && (
        <div className="notice notice-warn control-top" role="note">
          <Glyph name="user-x" size="1em" /> <strong>In force, and the roster cannot satisfy it.</strong> {row.inForce.lacks ? sentence(row.inForce.lacks) : ""}{" "}
          The acts it governs are refused, with this reason. A control never falls back to fewer.
        </div>
      )}
      {ahead && (
        <div className="notice control-top" role="note">
          <Glyph name="calendar-clock" size="1em" /> <strong>Adopted, not yet in force.</strong>{" "}
          {row.effective ? <>It takes effect {row.effective} (the board's date) and does not bind until then.</> : "No effective date is set, so it does not bind."}
          {row.inForce.lacks ? <> The roster could not satisfy it now: {sentence(row.inForce.lacks)}</> : null}
        </div>
      )}
      {row.changed && <ControlChangedBanner changed={row.changed} citation={row.basis.citation} itemId={row.proposedAs} />}
      <nav className="control-index" aria-label="Bands of this control">
        <ol>
          {nums.map((n, i) => (
            <li key={n}><button type="button" onClick={() => go(n)}>{n} {bands[i]}</button></li>
          ))}
        </ol>
      </nav>

      <Band n={1} title="The provision">
        <Recitation citation={cite} />
        {floorWords ? (
          <p className="control-floor"><Glyph name="scale" size="1em" /> <strong>The floor:</strong> {floorWords}. {WORDS.onlyAdds}.</p>
        ) : (
          <p className="control-floor muted"><Glyph name="scale" size="1em" /> {row.floor.note || "No floor is read for this provision."} {WORDS.onlyAdds}.</p>
        )}
      </Band>

      <Band n={2} title="What jason suggested">
        {row.reading ? (
          <ReadingLabel whose="jason">
            <p className="muted">{row.readingLabel || data.readingLabel || WORDS.reading}</p>
            <p>{row.reading}</p>
          </ReadingLabel>
        ) : (
          <p className="muted">jason made no reading of this provision. {WORDS.reading}.</p>
        )}
        {suggestion && <p className="muted">The suggestion is not the board's. It is not selected, and it adopts nothing.</p>}
      </Band>

      {!suggestion && (
        <Band n={3} title="What the board adopted">
          <Decided row={row} as={as} secretary={secretary} />
        </Band>
      )}

      <Band n={4} title="What it changes">
        {suggestion && <p className="muted">If the board adopts it, it would change:</p>}
        {row.touches.length ? <ul className="findings control-touches">{row.touches.map((t, i) => <Touch key={`${t.kind}-${t.key ?? t.what}-${i}`} t={t} />)}</ul> : <p className="muted">It changes nothing yet.</p>}
      </Band>

      <Band n={5} title="Can the roster satisfy it">
        <RosterCheck roster={row.roster} />
      </Band>

      <Band n={6} title="History">
        <History row={row} />
      </Band>

      {suggestion && (
        <div className="control-propose-bar">
          <ControlProposeConfirm controlKey={row.key} title={row.title} by={as.by} actingAs={as.actingAs} onProposed={as.onProposed} />
        </div>
      )}
    </div>
  );
}
