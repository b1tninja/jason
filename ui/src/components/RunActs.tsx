import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Confirm } from "./Confirm";
import { postAct, refusalOf, type ActBody, type Run } from "../lib/work";

/** What an act said back: the event recorded, or the server's refusal in its own words. */
export interface ActSaid { tone: "status" | "error"; text: string; signIn?: string; stale?: boolean }

export interface Acts {
  busy: boolean;
  said: ActSaid | null;
  /** Post an act on the run (the signed-in person's name goes on the record on the server; the body names no one). */
  send: (body: Omit<ActBody, "expect">) => Promise<boolean>;
  clear: () => void;
}

/** The writes of one run: each act is one POST to `/api/write/work/<definition>/<id>` carrying the `n` the page last read
 * (`expect`), so a run that moved on is refused and not overwritten. A refusal is shown as the server gave it; an act that
 * is recorded reads the run again. */
export function useActs(run: Pick<Run, "definition" | "id" | "n">, reload: () => void): Acts {
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<ActSaid | null>(null);
  const n = useRef(run.n);
  n.current = run.n;
  const send = useCallback(async (body: Omit<ActBody, "expect">) => {
    setBusy(true);
    setSaid(null);
    try {
      const out = await postAct(run.definition, run.id, { ...body, expect: n.current });
      setSaid({ tone: "status", text: out.event?.text ? `Recorded: ${out.event.text}.` : "Recorded." });
      reload();
      return true;
    } catch (e) {
      const r = refusalOf(e);
      setSaid({ tone: "error", text: r.text, signIn: r.signIn, stale: r.status === 409 });
      return false;
    } finally {
      setBusy(false);
    }
  }, [run.definition, run.id, reload]);
  return { busy, said, send, clear: () => setSaid(null) };
}

/** The result of the last act, where it was taken: recorded (a status) or refused (an alert, with the way on). */
export function ActStatus({ said, onReload }: { said: ActSaid | null; onReload?: () => void }) {
  if (!said) return null;
  if (said.tone === "status") return <p role="status" className="notice notice-good work-said">{said.text}</p>;
  return (
    <div role="alert" className="notice notice-error work-said">
      <span>{said.text}{said.signIn && <> <a href={said.signIn}>Sign in with Google</a></>}</span>
      {said.stale && onReload && <button type="button" onClick={onReload}>Read the run again</button>}
    </div>
  );
}

/** A write that asks for a few words first (a reason, a record, a note) and then goes through `Confirm`: the first button is
 * off until the words are given when they are required, and says why. Nothing is sent by a single click. */
export function TextConfirm({ trigger, field, hint, required = true, rows = 2, summary, onConfirm, busy, label, single = false }: {
  trigger: string; field: string; hint?: string; required?: boolean; rows?: number; single?: boolean;
  summary: (text: string) => ReactNode; onConfirm: (text: string) => void; busy?: boolean; label?: string;
}) {
  const [text, setText] = useState("");
  const id = useId();
  const need = required && !text.trim();
  return (
    <div className="work-text-confirm stack-sm">
      <label htmlFor={id}>{field}{required ? "" : " (optional)"}</label>
      {single
        ? <input id={id} type="text" value={text} aria-required={required || undefined} aria-describedby={`${id}-hint`} onChange={(e) => setText(e.target.value)} />
        : <textarea id={id} rows={rows} value={text} aria-required={required || undefined} aria-describedby={`${id}-hint`} onChange={(e) => setText(e.target.value)} />}
      <p id={`${id}-hint`} className="muted">{need ? `${field} is required.` : ""}{hint ? ` ${hint}` : ""}</p>
      <Confirm busy={busy || need} label={label} summary={summary(text.trim())} onConfirm={() => onConfirm(text.trim())}>{trigger}</Confirm>
    </div>
  );
}

/** A small dialog (a native `<dialog>`, modal): focus moves into it when it opens and back to the button that opened it when
 * it closes; Escape closes it. */
export function ActDialog({ title, open, onClose, children }: { title: string; open: boolean; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", ""); }
    if (!open && d.open) d.close();
  }, [open]);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    const on = () => onClose();
    d.addEventListener("close", on);
    return () => d.removeEventListener("close", on);
  }, [onClose]);
  return (
    <dialog ref={ref} className="work-dialog" aria-labelledby={heading}>
      {open && (
        <div className="stack-sm">
          <h2 id={heading}>{title}</h2>
          {children}
          <div className="row"><button type="button" onClick={onClose}>Close</button></div>
        </div>
      )}
    </dialog>
  );
}
