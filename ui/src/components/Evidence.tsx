import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { ApiError, getJson } from "../lib/api";
import { when, type EvidenceRef } from "../lib/approvals";
import { Caveats } from "./Caveats";
import { daysUntil } from "./DueDate";
import { Recitation } from "./Recitation";

export type EvidenceKind = "payhoa_submission" | "citation" | "board_item" | "command" | "unknown";

/** One field a source holds; a masked value is the server's mask, never the value itself. */
export interface EvidenceField { name: string; value: string; masked: boolean }

/** One stored copy an address resolves to: when jason read it, its digest, its fields, and, for a citation, its words. */
export interface EvidenceSource {
  name: string; readAt: string; digest: string; fields: EvidenceField[];
  text: string; citation: string; caveat: string; note: string;
}

/** A command that reads the source again. `live` reads an outside system, named by `system` ("PayHOA"); the page never
 * runs it. */
export interface EvidenceRefresh { command: string; live: boolean; what: string; system?: string }

/** `GET /api/evidence?address=…&approval=…`: what jason stored for one evidence address, and whether it changed since the
 * plan was read (`null` when jason cannot tell). */
export interface EvidenceAnswer {
  found: boolean; address: string; label: string; kind: EvidenceKind;
  sources: EvidenceSource[]; changed: boolean | null; changedNote: string; link: string;
  refresh: EvidenceRefresh[]; caveats: string[]; note: string;
}

/** The loader's URL: the address, and the approval whose plan it was read for (when there is one). */
export function evidenceUrl(address: string, approval?: string): string {
  const q = [`address=${encodeURIComponent(address)}`];
  if (approval) q.push(`approval=${encodeURIComponent(approval)}`);
  return `/api/evidence?${q.join("&")}`;
}

function ago(iso: string, today?: Date): string {
  const days = -daysUntil(iso.slice(0, 10), today);
  if (Number.isNaN(days) || days < 0) return "";
  return days === 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`;
}

function Heading({ level, id, children }: { level: 3 | 4 | 5 | 6; id: string; children: string }) {
  const H = `h${level}` as "h3";
  return <H id={id} className="evidence-panel-title">{children}</H>;
}

function RefreshCommand({ r }: { r: EvidenceRefresh }) {
  const [copied, setCopied] = useState(false);
  const id = useId();
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(r.command);
      setCopied(true);
    } catch {
      /* no clipboard: the text is selectable */
    }
  };
  return (
    <li className="evidence-refresh">
      <div className="row wrap">
        <code id={id}>{r.command}</code>
        <button type="button" onClick={copy} aria-describedby={id}>{copied ? "Copied" : "Copy"}</button>
        <span className="visually-hidden" role="status">{copied ? "Copied the command." : ""}</span>
      </div>
      <span className="muted">
        {r.what}{r.what && !/[.!?]$/.test(r.what) ? "." : ""}{r.live ? ` It reads ${r.system || "outside jason"}; run it in a terminal.` : " Run it in a terminal."}
      </span>
    </li>
  );
}

function Source({ s, today }: { s: EvidenceSource; today?: Date }) {
  const fields = s.fields ?? [];
  const since = s.readAt ? ago(s.readAt, today) : "";
  const empty = !fields.length && !s.text && !s.citation && !s.note;
  return (
    <div className="evidence-source">
      <div className="evidence-source-head">
        <strong>{s.name}</strong>
        {s.readAt && (
          <span className="muted"> · read <time dateTime={s.readAt}>{when(s.readAt)}</time>{since ? ` (${since})` : ""}</span>
        )}
        {s.digest && <span className="muted"> · digest <code>{s.digest.slice(0, 12)}</code></span>}
      </div>
      {fields.length > 0 && (
        <dl className="kv evidence-fields">
          {fields.map((f, i) => (
            <div key={i} className="evidence-field">
              <dt>{f.name}</dt>
              <dd>
                {f.value || <span className="muted">(none)</span>}
                {f.masked && <> <span className="badge badge-neutral">masked</span><span className="visually-hidden"> (the server masks this value)</span></>}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {s.text && s.citation && <Recitation citation={{ found: true, citation: s.citation, text: s.text, caveat: s.caveat }} />}
      {s.text && !s.citation && (
        <figure className="recitation">
          <div className="recitation-label">Stored words</div>
          <blockquote className="recitation-words">{s.text}</blockquote>
          {s.caveat && <p className="recitation-caveat">{s.caveat}</p>}
        </figure>
      )}
      {!s.text && s.citation && (
        <p className="muted"><cite>{s.citation}</cite>: no stored words to recite.{s.caveat ? ` ${s.caveat}` : ""}</p>
      )}
      {s.note && <p className="muted evidence-note">{s.note}</p>}
      {empty && <p className="muted evidence-note">Nothing stored for this source beyond its name.</p>}
    </div>
  );
}

/** What jason stored for one evidence address, fetched when it opens (`GET /api/evidence`), or `data` rendered as given
 * (previews, tests). The stored words are recited, then cited; nothing is paraphrased. A miss shows the note and the
 * command that fills it, never an empty box. Commands are shown to copy; the page never runs one. */
export function EvidencePanel({ address, label, approval, data, today, level = 4, id, onClose }: {
  address: string; label?: string; approval?: string; data?: EvidenceAnswer | null; today?: Date;
  level?: 3 | 4 | 5 | 6; id?: string; onClose?: () => void;
}) {
  const [answer, setAnswer] = useState<EvidenceAnswer | null>(data ?? null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!data);
  const titleId = useId();

  useEffect(() => {
    if (data) {
      setAnswer(data);
      setLoading(false);
      return;
    }
    const ctl = new AbortController();
    setAnswer(null);
    setError("");
    setLoading(true);
    getJson<EvidenceAnswer>(evidenceUrl(address, approval), ctl.signal).then(
      (a) => { setAnswer(a); setLoading(false); },
      (e: unknown) => {
        if (ctl.signal.aborted) return;
        // A miss the server answered with a 404 and the contract's body is still a miss to show, not a failure.
        const body = e instanceof ApiError ? (e.body as Partial<EvidenceAnswer> | null) : null;
        if (body && typeof body === "object" && body.found === false && typeof body.address === "string") setAnswer(body as EvidenceAnswer);
        else setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      },
    );
    return () => ctl.abort();
  }, [address, approval, data]);

  const a = answer;
  const title = a?.label || label || address;
  const sources = a?.sources ?? [];
  const refresh = a?.refresh ?? [];
  const miss = !!a && !a.found;
  return (
    <div className="evidence-panel" id={id} role="group" aria-labelledby={titleId}>
      <div className="evidence-panel-head">
        <Heading level={level} id={titleId}>{title}</Heading>
        {onClose && <button type="button" className="link" onClick={onClose}>Close</button>}
      </div>
      <p className="muted evidence-address">Address <code>{a?.address || address}</code></p>
      <div aria-live="polite" className="evidence-panel-status">
        {loading && <p className="muted">Reading what jason stored for this address.</p>}
        {error && <p className="notice notice-error">jason-web did not answer: {error}</p>}
      </div>
      {a && (
        <>
          {a.changed === true && (
            <p className="notice notice-warn evidence-changed">Changed since this plan was read.{a.changedNote ? ` ${a.changedNote}` : ""}</p>
          )}
          {a.changed === false && (
            <p className="evidence-unchanged">Unchanged since this plan was read.{a.changedNote ? <span className="muted"> {a.changedNote}</span> : null}</p>
          )}
          {a.changed == null && a.changedNote && <p className="muted">{a.changedNote}</p>}
          {miss && <p className="evidence-miss">{a.note || "None on record for this address. None on record is not none given."}</p>}
          {sources.map((s, i) => <Source key={i} s={s} today={today} />)}
          {!miss && !sources.length && <p className="muted evidence-note">{a.note || "jason holds no stored copy for this address."}</p>}
          {a.link && (
            <p>
              <a href={a.link} target="_blank" rel="noreferrer">
                {a.kind === "payhoa_submission" ? "Open the unit's requests in PayHOA" : "Open the original"}
                <span className="visually-hidden"> (opens in a new tab)</span>
              </a>
            </p>
          )}
          {refresh.length > 0 && (
            <div className="evidence-refreshes">
              <p className="muted">{miss ? "The command that fills it" : "To read it again"} (the page never runs a command):</p>
              <ul>{refresh.map((r, i) => <RefreshCommand key={i} r={r} />)}</ul>
            </div>
          )}
          <Caveats items={a.caveats} />
          {!miss && sources.length > 0 && a.note && <p className="muted evidence-note">{a.note}</p>}
        </>
      )}
    </div>
  );
}

const openable = (e: string | EvidenceRef): e is EvidenceRef & { address: string } => typeof e !== "string" && !!e.address;

/** Records, commands, paths, and links a row cites. A string, or a ref with no address, is a plain chip. A ref with an
 * address is a chip that opens what jason stored for it below the chips (one at a time; Escape closes it and returns to
 * the chip). A command is shown as code so it can be copied, never run from here. */
export function Evidence({ items, label = "Evidence", approval, level }: {
  items?: readonly (string | EvidenceRef)[] | null; label?: string; approval?: string; level?: 3 | 4 | 5 | 6;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const chips = useRef<(HTMLButtonElement | null)[]>([]);
  const panelId = useId();
  if (!items?.length) return null;
  const close = () => {
    const at = open;
    setOpen(null);
    if (at != null) chips.current[at]?.focus();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Escape" || open == null) return;
    e.stopPropagation();
    close();
  };
  const shown = open != null ? items[open] : undefined;
  return (
    <div className="evidence" onKeyDown={onKeyDown}>
      {label && <span className="muted">{label}: </span>}
      {items.map((e, i) =>
        openable(e) ? (
          <button key={i} type="button" className="chip chip-open" ref={(el) => { chips.current[i] = el; }}
            aria-expanded={open === i} aria-controls={panelId} onClick={() => setOpen(open === i ? null : i)}>
            <span className="evidence-caret" aria-hidden="true">{open === i ? "▾" : "▸"}</span>{e.label}
          </button>
        ) : (
          <code key={i} className="chip">{typeof e === "string" ? e : e.label}</code>
        ),
      )}
      {shown && openable(shown) && (
        <EvidencePanel key={`${open}:${shown.address}`} id={panelId} address={shown.address} label={shown.label}
          approval={approval} level={level} onClose={close} />
      )}
    </div>
  );
}
