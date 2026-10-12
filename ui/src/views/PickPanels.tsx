import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Badge, type Tone } from "../components";
import type { GlyphName } from "../components/Glyph";
import type { PickReturn, PickRow } from "../lib/pick";
import { useApi } from "../lib/useApi";
import { PickFields, type ChooserSlot } from "./DriveChooser";
import { ActPanel } from "./RecordActs";
import { sizeWords, type Plan } from "./recordTypes";
import type { OpenAnswer, SplitBackend } from "./splitApi";
import { sizeText, splitRoute } from "./splitModel";

/** Choosing from a person's own Google Drive with Google's Picker (docs/google-picker.md, "The UI contract"): the button and what
 * it does in words, the list of what came back, a held copy opened as a draft or pinned to a slot, and the copies jason holds. */

const REASONS: Record<string, string> = {
  folder: "A folder", not_pdf: "Not a PDF", too_large: "Too large", too_many_pages: "Too many pages", no_access: "No access",
  not_readable: "Cannot be read", no_room: "No room", bad_id: "Skipped", duplicate: "Picked twice",
};

function look(row: PickRow): { tone: Tone; glyph: GlyphName; label: string } {
  if (row.outcome === "held") return { tone: "good", glyph: "circle-check", label: "Kept" };
  if (row.outcome === "already held") return { tone: "neutral", glyph: "circle-check", label: "Already kept" };
  if (row.outcome === "would hold") return { tone: "neutral", glyph: "clock", label: "Would be kept" };
  return { tone: "warn", glyph: "triangle-alert", label: `Refused: ${REASONS[row.reason]?.toLowerCase() ?? "not kept"}` };
}

/** What a pick came to, in a sentence, from the server's counts. */
export function pickSummary(rows: PickRow[]): string {
  const kept = rows.filter((r) => r.heldId).length;
  const refused = rows.length - kept;
  const noun = (n: number) => (n === 1 ? "file" : "files");
  if (rows.length === 0) return "Nothing was picked.";
  if (refused === 0) return `${kept} ${noun(kept)} kept.`;
  if (kept === 0) return `No file was kept. ${refused} ${noun(refused)} refused; each says why.`;
  return `${kept} of ${rows.length} files kept. ${refused} ${noun(refused)} refused; each says why. The ones kept are listed with them.`;
}

/** A list of what came back from Google. `action` draws the button of a kept file (open it as a draft, pin it to a slot); a refused row
 * has none. The heading takes the focus when the list appears, and one polite status line says how it went. */
export function PickOutcome({ value, onClose, action, again, level = 3 }: {
  value: PickReturn; onClose: () => void; action?: (row: PickRow, n: number) => ReactNode; again?: ReactNode;
  /** The heading level, so the list sits in the page's outline: 2 straight under the screen's title, 3 inside a section. */
  level?: 2 | 3;
}) {
  const Heading = `h${level}` as "h2" | "h3";
  const id = useId();
  const head = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => { head.current?.focus(); }, [value]);
  let title = "What you picked from Google Drive";
  let said: ReactNode = null;
  let rows: PickRow[] = [];
  let link: ReactNode = null;
  if (value.kind === "gone") {
    title = "That pick is over";
    said = "That pick was already read, or it has expired. Choose again.";
  } else if (value.kind === "signin") {
    title = "Sign in to see what you picked";
    said = <>{value.message} Files jason already read are held; they are listed under Picked from Drive on the splitter's start page.</>;
    link = <a href={value.href}>Sign in with Google</a>;
  } else if (value.kind === "error") {
    title = "The result of the pick could not be read";
    said = `${value.message} Choose again.`;
  } else if (value.result.report) {
    rows = value.result.report.rows;
    said = pickSummary(rows);
  } else {
    title = "Nothing was kept";
    said = value.result.error || "Nothing was picked.";
  }
  const bad = value.kind !== "result" || !value.result.report || rows.some((r) => !r.heldId);
  return (
    <section className="pick-outcome" aria-labelledby={`${id}-h`} data-pick={value.kind === "result" ? "result" : value.kind}>
      <Heading id={`${id}-h`} tabIndex={-1} ref={head}>{title}</Heading>
      <p className={bad ? "notice notice-warn" : "notice notice-good"} role="status">{said}</p>
      {link && <p>{link}</p>}
      {rows.length > 0 && (
        <ul className="pick-rows" aria-label="Files you picked">
          {rows.map((row, i) => {
            const l = look(row);
            return (
              <li key={`${row.heldId || "x"}-${i}`} data-outcome={row.outcome} data-reason={row.reason || undefined}>
                <p className="pick-row-head"><strong>File {i + 1}{row.name ? <>: <span className="pick-row-name">{row.name}</span></> : null}</strong> <Badge tone={l.tone} glyph={l.glyph}>{l.label}</Badge></p>
                <p>{row.words}</p>
                {row.heldId && <p className="muted">{row.pages} {row.pages === 1 ? "page" : "pages"}, {sizeWords(row.size)}.</p>}
                {row.heldId && action?.(row, i + 1)}
              </li>
            );
          })}
        </ul>
      )}
      <div className="row wrap">
        <button type="button" onClick={onClose}>Close this list</button>
        {again}
      </div>
    </section>
  );
}

/** A held copy opened as a split draft (`words` are the two buttons' own: the held-copies list words them differently from a fresh result, so a screen with both has no two buttons of one name): check it (a dry run, in the server's words), then open it. The same bytes resume the same draft. */
export function OpenHeld({ backend, by, heldId, label, words = { check: "Check the file", open: "Open it for splitting" } }: {
  backend: SplitBackend; by: string; heldId: string; label: string; words?: { check: string; open: string };
}) {
  const [checked, setChecked] = useState<OpenAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async (dry: boolean) => {
    setBusy(true); setError("");
    try {
      const a = await backend.open({ kind: "held", id: heldId }, dry, by);
      if (dry) setChecked(a);
      else if (a.session) window.location.hash = splitRoute(a.session.id).slice(1);
    } catch (e) { setChecked(null); setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="pick-open">
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {checked?.dryRun && checked.would && (
        <div className="split-preview" role="region" aria-label={`What opening ${label} will do`}>
          <p>{checked.would.pages !== null ? `${checked.would.pages} pages, ` : ""}{sizeText(checked.would.size ?? 0)}. It keeps {checked.would.keeps}. {checked.note}</p>
        </div>
      )}
      {!checked?.dryRun
        ? <button type="button" disabled={busy || !by} aria-label={`${words.check}: ${label}`} onClick={() => go(true)}>{words.check}</button>
        : <button type="button" className="primary" disabled={busy} aria-label={`${words.open}: ${label}`} onClick={() => go(false)}>{words.open}</button>}
      {!by && <span className="muted"> Sign in to open it.</span>}
    </div>
  );
}

/** A held copy pinned to a record slot: the server hands the copy to the slot's upload, so this page never holds the file. It is kept
 * in jason's store like any upload; it is not pinned as a Drive file, because jason's own Drive account cannot see it. */
export function HeldPanel({ slot, row, n, by, onDone, onBack }: { slot: ChooserSlot; row: PickRow; n: number; by: string; onDone: (p: Plan) => void; onBack: () => void }) {
  const [period, setPeriod] = useState("");
  const [entry, setEntry] = useState("");
  const [note, setNote] = useState("");
  return (
    <ActPanel
      slot={slot.key} by={by} onDone={onDone} onCancel={onBack}
      title={`Pin file ${n} from your Drive to ${slot.title}`}
      body={() => ({ act: "upload", heldId: row.heldId, name: row.name || undefined, period, entry, note })}
      ready={slot.cardinality !== "series" || !!period.trim()} whyNot="Name the period this file is for."
      previewLabel="Preview the pin" confirmLabel={`Keep file ${n} and pin it to ${slot.title}`}
      watch={[row.heldId, period, entry, note]}
    >
      <p className="muted">jason already holds a copy it read once from your Drive. The copy is kept in jason's own store and pinned here as an upload. Nothing is written to Drive.</p>
      <PickFields slot={slot} period={period} setPeriod={setPeriod} entry={entry} setEntry={setEntry} note={note} setNote={setNote} />
    </ActPanel>
  );
}

interface HeldList { found?: boolean; copies: { n: number; id: string; size: number | null; pages: number | null; day: string; confidential: boolean; held: boolean }[]; total: number; note?: string }

/** "Picked from Drive": the copies jason holds from earlier picks, by number and size (no name, no Drive id), each openable as a draft.
 * Nothing is drawn when there are none, or when the list cannot be read. */
export function HeldCopies({ backend, by }: { backend: SplitBackend; by: string }) {
  const r = useApi<HeldList>("/api/drive-held");
  const id = useId();
  if (r.status !== "ready" || r.data.copies.length === 0) return null;
  const d = r.data;
  return (
    <section className="pick-held" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>Picked from Drive</h2>
      <p className="muted">{d.note ?? "Copies jason read once from files you picked in your own Drive."}{d.total > d.copies.length ? ` The latest ${d.copies.length} of ${d.total} are shown.` : ""}</p>
      <ul className="pick-held-list" aria-label="Copies held from Drive">
        {d.copies.map((c) => (
          <li key={c.n}>
            <p><strong>Copy {c.n}</strong>{" "}
              {c.held ? <span className="muted">a confidential file; its size and pages are held back{c.day ? `, picked ${c.day}` : ""}</span>
                : <span className="muted">{c.pages} {c.pages === 1 ? "page" : "pages"}, {sizeWords(c.size)}{c.day ? `, picked ${c.day}` : ""}</span>}</p>
            {c.held
              ? <p className="muted">Open the private view to open it as a draft.</p>
              : <OpenHeld backend={backend} by={by} heldId={c.id} label={`copy ${c.n}`} words={{ check: "Check this copy", open: "Open as a draft" }} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
