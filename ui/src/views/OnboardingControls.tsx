import { useState } from "react";
import { Card, Confirm, ControlRow, Glyph, Loading } from "../components";
import { ApiError, postJson } from "../lib/api";
import {
  CONTROLS_HREF, boardHref, proposeUrl, useControlsApi, useControlsViewer,
  type ControlRowData, type ControlsPage, type ProposeAnswer,
} from "../lib/controls";
import "../styles/controls.css";

// Onboarding: "Controls jason suggests from your documents" (docs/console/screens/onboarding.md, docs/console/screens/controls.md).
// One optional card in the Setup tab. It reads the suggestions (`GET /api/controls?state=suggested`) and offers two things:
// "Take these to the board", which puts each suggestion before the board one at a time (`POST /api/write/controls/<key>` with
// `{act: "propose"}`, the signer's name taken by the server) and reports each result, and "Not now", which is the browser's
// alone. It adopts, declines, and defers nothing, and no gate waits on it.

/** Where "Not now" is remembered: the day the suggestions were seen, in this browser only. A convenience, never a record. */
export const SEEN_KEY = "jason.onboarding.controls.seen";

const readSeen = (): string => { try { return localStorage.getItem(SEEN_KEY) ?? ""; } catch { return ""; } };
const keepSeen = (day: string) => {
  try {
    if (day) localStorage.setItem(SEEN_KEY, day);
    else localStorage.removeItem(SEEN_KEY);
  } catch { /* per-viewer convenience only */ }
};

/** One suggestion's result of being put before the board. */
export interface Outcome { key: string; title: string; state: "put" | "refreshed" | "refused" | "not tried"; item?: string; message?: string }

const STEP_URL = "/api/controls?state=suggested";
const TITLE = "Controls jason suggests from your documents";

function Results({ results }: { results: Outcome[] }) {
  if (!results.length) return null;
  return (
    <ul className="plain stack-sm" role="status" aria-label="Put before the board" data-testid="controls-results">
      {results.map((o) => (
        <li key={o.key}>
          <strong>{o.title}</strong>:{" "}
          {o.state === "put" && <>put before the board as <a href={boardHref(o.item ?? "")}>{o.item}</a>.</>}
          {o.state === "refreshed" && <>already before the board; <a href={boardHref(o.item ?? "")}>{o.item}</a> was refreshed.</>}
          {o.state === "refused" && <span className="notice notice-error">refused: {o.message}</span>}
          {o.state === "not tried" && <span className="muted">not tried: {o.message}</span>}
        </li>
      ))}
    </ul>
  );
}

function Suggestions({ onNotNow }: { onNotNow: () => void }) {
  const r = useControlsApi<ControlsPage>(STEP_URL);
  const viewer = useControlsViewer();
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<Outcome[]>([]);

  const d = r.status === "ready" ? r.data : null;
  const groups = (d?.families ?? []).filter((g) => g.controls.length);
  const rows: ControlRowData[] = groups.flatMap((g) => g.controls);
  const questions = d?.questions?.length ?? 0;

  /** One at a time, in the order shown; each result is reported as it comes. A refusal for the sign-in (401 or 403) stops the
   * rest, which would be refused the same way. Nothing is adopted. */
  const takeToBoard = async () => {
    setBusy(true);
    setResults([]);
    const out: Outcome[] = [];
    let stopped = "";
    for (const row of rows) {
      if (stopped) {
        out.push({ key: row.key, title: row.title, state: "not tried", message: stopped });
      } else {
        try {
          const a = await postJson<ProposeAnswer>(proposeUrl(row.key), { act: "propose" });
          out.push({ key: row.key, title: row.title, state: a.refreshed ? "refreshed" : "put", item: a.item });
        } catch (e) {
          const message = (e as Error).message;
          out.push({ key: row.key, title: row.title, state: "refused", message });
          if (e instanceof ApiError && (e.status === 401 || e.status === 403)) stopped = `the first refusal was the sign-in's (${message})`;
        }
      }
      setResults([...out]);
    }
    setBusy(false);
    r.reload();
  };

  const names = rows.map((x) => x.title).join(", ");
  const by = viewer.name || "the signed-in person";
  return (
    <Card title={TITLE}>
      <p className="muted">
        Optional, and no gate waits on it. jason read your governing documents' duties and limits and suggests these; the board adopts the
        ones it wants. A control only adds to what the documents and the law already require. Each row is a suggestion: not in force, and not a rule.
      </p>
      {r.status === "loading" && <Loading />}
      {r.status === "error" && (
        <p className="muted" data-testid="controls-unread">
          {r.code === 401 || r.code === 403 ? r.error : `The suggestions could not be read: ${r.error}.`} Nothing is shown as adopted.
        </p>
      )}
      {d && d.found === false && <p className="muted">{d.note ?? d.empty}</p>}
      {d && d.found !== false && d.empty && <p className="muted" data-testid="controls-empty">{d.empty}</p>}
      {d && d.found !== false && !d.empty && !rows.length && !results.length && (
        <p className="muted" data-testid="controls-none">jason read your documents and has no control to suggest.</p>
      )}
      {groups.map((g) => (
        <section key={g.family} className="stack-sm" aria-label={`${g.title} suggestions`}>
          <h3>{g.title}</h3>
          <ul className="control-list">
            {g.controls.map((c) => <ControlRow key={c.key} row={c} inStep />)}
          </ul>
        </section>
      ))}
      {questions > 0 && (
        <p className="muted">
          {questions} provision(s) read two ways are questions for the board or counsel, not suggestions: see <a href={CONTROLS_HREF}>Controls</a>.
        </p>
      )}
      <Results results={results} />
      {r.status !== "loading" && (
        <div className="row wrap">
          {rows.length > 0 && (viewer.actingAs ? (
            <p className="muted" role="note">Viewing as {viewer.actingAs} (admin view): go back to yourself first. A control is put before the board in a person's own name.</p>
          ) : (
            <Confirm busy={busy} label="Take these to the board" onConfirm={takeToBoard}
              summary={
                <p>
                  Put {rows.length === 1 ? "this suggestion" : `these ${rows.length} suggestions`} before the board ({names}) as {by}: one
                  board item for each, made one at a time, with its provision as the evidence. This adopts nothing and changes no rule; the board
                  decides at a meeting and the secretary records it.
                </p>
              }>
              Take these to the board
            </Confirm>
          ))}
          <button type="button" onClick={onNotNow} disabled={busy}>Not now</button>
        </div>
      )}
    </Card>
  );
}

/** The step in the Setup tab. "Not now" hides the suggestions in this browser and says they were seen, never that anything was
 * adopted; "Show them again" brings them back. */
export function OnboardingControlsStep() {
  const [seen, setSeen] = useState(readSeen);
  if (seen)
    return (
      <Card title={TITLE}>
        <p className="row wrap" data-testid="controls-seen">
          <Glyph name="shield-check" size="1em" />
          <span>Seen {seen}; nothing adopted.</span>
          <button type="button" onClick={() => { keepSeen(""); setSeen(""); }}>Show them again</button>
        </p>
      </Card>
    );
  return <Suggestions onNotNow={() => { const day = new Date().toISOString().slice(0, 10); keepSeen(day); setSeen(day); }} />;
}
