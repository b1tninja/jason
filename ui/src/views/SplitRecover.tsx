import { useRef, useState } from "react";
import { Badge, Confirm } from "../components";
import { Glyph } from "../components/Glyph";
import { busyOf, planChangedOf, type AnyAnswer, type Busy, type SplitBackend } from "./splitApi";
import type { UnfinishedApply } from "./splitModel";
import { BusyNotice } from "./splitNotices";

/** An apply that did not finish (docs/pdf-splitter.md, section 6.7). The server wrote part of it and stopped (a kill, a full disk, a part that
 * failed); what it wrote is kept, and nothing more is written until a person chooses: finish it with the choices it began with, or roll it back.
 * Either is a person's act behind a confirm, as the signed-in person, and nothing is deleted. */

export const UNFINISHED_SENTENCE = "An earlier apply did not finish";

const stamp = (t: string): string => (t ? t.slice(0, 16).replace("T", " ") : "");

/** The state in words: who began it, when, and how far it got. No file name, no page text. */
export function unfinishedWords(u: UnfinishedApply): string {
  const who = u.by ? ` by ${u.by}` : "";
  const when = u.at ? ` at ${stamp(u.at)}` : "";
  const how = u.of > 0 ? `${u.written} of ${u.of} files ${u.written === 1 ? "was" : "were"} written` : "no files were written";
  const hurt = u.failed > 0 ? `; ${u.failed} ${u.failed === 1 ? "part" : "parts"} could not be written` : "";
  return `It was started${who}${when}: ${how}${hurt}.`;
}

/** The draft list's mark for an unfinished apply: words and a glyph, and how far it got. */
export function UnfinishedBadge({ u }: { u: UnfinishedApply }) {
  return (
    <>
      <Badge tone="warn" glyph="triangle-alert">{UNFINISHED_SENTENCE}</Badge>
      <span className="muted split-unfinished-how"> {u.of > 0 ? `${u.written} of ${u.of} files written` : "nothing written"}</span>
    </>
  );
}

type Mode = "finish" | "rollback";

/** The draft's header panel. It stays on screen after the person acts, with what was done in words, and goes only when they leave. `u` is the
 * server's description (`unfinishedApply`), or null once nothing is left to do. `onSettled` reads the draft again. */
export function RecoverPanel({ backend, id, u, by, onSettled }: { backend: SplitBackend; id: string; u: UnfinishedApply | null; by: string; onSettled(): void }) {
  const [working, setWorking] = useState<Mode | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<{ note: Busy; mode: Mode; n: number } | null>(null);
  const [done, setDone] = useState<{ mode: Mode; words: string } | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const last = useRef<UnfinishedApply | null>(u);
  if (u) last.current = u;
  const shown = u ?? last.current;

  const run = async (mode: Mode) => {
    setWorking(mode); setError(""); setBusy(null);
    try {
      const a: AnyAnswer = await backend.act(id, { act: "recover", mode, dryRun: false, confirm: true, by: by || undefined });
      const words = mode === "rollback"
        ? (a as { note?: string }).note || "The apply was rolled back: its pins are unpinned and the draft is as it was. Nothing was deleted."
        : "The apply was finished with the choices it began with.";
      setDone({ mode, words });
      onSettled();
      requestAnimationFrame(() => heading.current?.focus());
    } catch (e) {
      const b = busyOf(e);
      const changed = planChangedOf(e);
      if (b) setBusy((was) => ({ note: b, mode, n: (was?.n ?? 0) + 1 }));
      else setError(changed ? changed.message : (e as Error).message);
    } finally { setWorking(null); }
  };

  if (!shown && !done) return null;
  return (
    <section className="split-note split-unfinished" data-note="unfinished" aria-labelledby="split-unfinished-h">
      <h2 id="split-unfinished-h" tabIndex={-1} ref={heading}>
        <Glyph name={done ? "circle-check" : "triangle-alert"} size={14} /> {done ? (done.mode === "finish" ? "The earlier apply was finished" : "The earlier apply was rolled back") : UNFINISHED_SENTENCE}
      </h2>
      {done ? <p role="status">{done.words}</p> : shown && (
        <>
          <p>{unfinishedWords(shown)} What it wrote is kept. Nothing more is written, and nothing is undone, until you choose and confirm.</p>
          {error && <p className="notice notice-error" role="alert"><span>{error}</span></p>}
          {busy && <BusyNotice busy={busy.note} again={busy.n} working={working !== null} onRetry={() => void run(busy.mode)} />}
          <div className="row wrap split-recover-acts">
            <Confirm label="Finish it" busy={working !== null}
              summary={<p>Finish the earlier apply with the choices it began with{by ? `, as ${by}` : ""}. It writes the {Math.max(0, shown.of - shown.written)} files that are left; files already written are kept and none is written twice.</p>}
              onConfirm={() => void run("finish")}>Finish it</Confirm>
            <Confirm label="Roll it back" busy={working !== null}
              summary={<p>Roll the earlier apply back{by ? `, as ${by}` : ""}: the files it pinned are unpinned and the draft is put back as it was. The files it wrote stay where they are, held; nothing is deleted. A part the library already took in stays in the library.</p>}
              onConfirm={() => void run("rollback")}>Roll it back</Confirm>
          </div>
        </>
      )}
    </section>
  );
}
