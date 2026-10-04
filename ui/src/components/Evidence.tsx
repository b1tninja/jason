import { createContext, useContext, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { ApiError, getJson, postJson, signInRefusal } from "../lib/api";
import { when, type EvidenceRef } from "../lib/approvals";
import { useAccount, useMe } from "../lib/session";
import { Caveats } from "./Caveats";
import { DocumentViewer, documentKindWord, humanSize, viewDocument, type DocumentView, type DocumentViewRequest, type EvidenceDocument } from "./DocumentViewer";
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

/** Whether the page may read this address again from an outside system (`system`, "PayHOA"), and what that read does. */
export interface EvidenceRefreshable { system: string; what: string }

/** Who read it again from the page, from which system, and when (`POST /api/evidence/refresh`'s answer). */
export interface EvidenceRefreshed { at: string; by: string; system: string }

/** `GET /api/evidence?address=…&approval=…`: what jason stored for one evidence address, and whether it changed since the
 * plan was read (`null` when jason cannot tell). `refreshable` is set when a person may read it again from the page.
 * `documents` are the documents it holds, each opened unmasked only by a view (an older server leaves it out). */
export interface EvidenceAnswer {
  found: boolean; address: string; label: string; kind: EvidenceKind;
  sources: EvidenceSource[]; changed: boolean | null; changedNote: string; link: string;
  refresh: EvidenceRefresh[]; caveats: string[]; note: string;
  refreshable?: EvidenceRefreshable | null; refreshed?: EvidenceRefreshed | null;
  documents?: EvidenceDocument[];
}

/** The body of a read again: the address, the approval whose plan it was read for, and the person reading. */
export interface EvidenceRefreshRequest { address: string; approval?: string; by: string }

/** `POST /api/evidence/refresh`: one live read, as a person's act, through the write guard. The answer is the fresh
 * `EvidenceAnswer` with `refreshed`; a 409 or 403 carries the server's `error`, said as it is. */
export function refreshEvidence(req: EvidenceRefreshRequest): Promise<EvidenceAnswer> {
  return postJson<EvidenceAnswer>("/api/evidence/refresh", req);
}

/** `POST /api/evidence/refresh-all`'s answer: which addresses of the plan were read again, which could not be (and why),
 * and how many the server does not read again. The answers themselves are not returned: open panels refetch. */
export interface EvidenceRefreshAll {
  approval: string; by: string; at: string; refreshed: string[]; failed: { address: string; error: string }[]; skipped: number;
}

/** Every request of one plan read again from PayHOA on one sign-in, as a named person's act, through the write guard. */
export function refreshAllEvidence(req: { approval: string; by: string }): Promise<EvidenceRefreshAll> {
  return postJson<EvidenceRefreshAll>("/api/evidence/refresh-all", req);
}

/** A counter a plan bumps after a batch read: every open `EvidencePanel` under it fetches its answer again, in place.
 * A closed panel fetches when it opens anyway. */
export const EvidenceVersion = createContext(0);

/** Two arrows in a circle, at the text's color: the read-again icon, here and in the plan's "Read every request again". */
export function RereadIcon() {
  return (
    <svg className="evidence-reread-icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13.5 6.5A5.5 5.5 0 0 0 3.2 4.6" />
      <path d="M3 2v3h3" />
      <path d="M2.5 9.5a5.5 5.5 0 0 0 10.3 1.9" />
      <path d="M13 14v-3h-3" />
    </svg>
  );
}

const sentence = (s: string) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);

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

const VIEW_REFUSALS = [400, 403, 404, 409];

/** What the server's own calls need before a click: a person signed in with Google (`jason.web.access`); a picked name
 * is not enough. `live` is false for a panel whose calls are passed in (previews, tests). */
interface Gate { live: boolean; known: boolean; signedIn: boolean; href: string }

/** Why a server call is off until someone signs in ("" when it is on): checking, or "Sign in with Google to …". */
function signInWhy(gate: Gate, what: string): string {
  if (!gate.live) return "";
  if (!gate.known) return "Checking your sign-in…";
  return gate.signedIn ? "" : `Sign in with Google to ${what}.`;
}

/** "Sign in with Google", beside a sentence that asks for it. */
function SignInLink({ href }: { href: string }) {
  return <> <a className="evidence-sign-in" href={href}>Sign in with Google</a></>;
}

/** The documents an address holds, each with a View button. A view is a signed-in person's act, logged by the server:
 * one click, one POST, one at a time, never on open; Previous and Next in the viewer are each a view of their own. */
function Documents({ docs, level, address, approval, who, viewer, gate, today }: {
  docs: EvidenceDocument[]; level: 3 | 4 | 5 | 6; address: string; approval?: string; who: string;
  viewer: ((req: DocumentViewRequest) => Promise<DocumentView>) | null; gate: Gate; today?: Date;
}) {
  const [viewing, setViewing] = useState<{ index: number; data: DocumentView | null; busy: boolean; error: string; signIn?: string } | null>(null);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const opener = useRef(0);
  const inFlight = useRef(false);
  const seq = useRef(0);
  const alive = useRef(true);
  const titleId = useId();
  const whyId = useId();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const needsSignIn = signInWhy(gate, "view it");
  const why = !viewer
    ? "This copy is shown as given; the page does not open its documents."
    : needsSignIn || (!who ? "Sign in or pick your name to view it." : "");

  const open = async (i: number) => {
    const d = docs[i];
    if (!d || why || !viewer || inFlight.current) return;
    inFlight.current = true;
    const mine = ++seq.current;
    setViewing({ index: i, data: null, busy: true, error: "" });
    try {
      const v = await viewer({ address, ...(approval ? { approval } : {}), document: d.id, by: who });
      if (alive.current && seq.current === mine) setViewing({ index: i, data: v, busy: false, error: "" });
    } catch (e: unknown) {
      if (!alive.current || seq.current !== mine) return;
      const status = e instanceof ApiError ? e.status : undefined;
      const message = e instanceof Error ? e.message : String(e);
      const asked = signInRefusal(e);
      const text = asked || (status && VIEW_REFUSALS.includes(status)) ? message : `jason-web did not answer: ${message}`;
      setViewing({ index: i, data: null, busy: false, error: text, signIn: asked?.href });
    } finally {
      inFlight.current = false;
    }
  };
  const view = (i: number) => {
    if (why || viewing) return;
    opener.current = i;
    void open(i);
  };
  const close = () => {
    seq.current += 1;
    setViewing(null);
    buttons.current[opener.current]?.focus();
  };

  const H = `h${Math.min(level + 1, 6)}` as "h5";
  return (
    <section className="evidence-documents" aria-labelledby={titleId}>
      <H id={titleId} className="evidence-documents-title">Documents</H>
      <p className="muted">Viewing shows the document unmasked, under your name, and is logged.</p>
      {why && <p className="muted evidence-documents-why"><span id={whyId}>{why}</span>{needsSignIn && gate.known && <SignInLink href={gate.href} />}</p>}
      <ul>
        {docs.map((d, i) => {
          const size = d.kind === "submission" ? "" : humanSize(d.size);
          return (
            <li key={d.id || i} className="evidence-document">
              <span className="evidence-document-name">{d.name}</span>
              <span className="muted evidence-document-kind">{documentKindWord(d.kind)}{size ? ` · ${size}` : ""}</span>
              <button type="button" ref={(el) => { buttons.current[i] = el; }} aria-label={`View ${d.name}`}
                aria-disabled={why || (viewing && viewing.busy) ? true : undefined} aria-describedby={why ? whyId : undefined}
                onClick={() => view(i)}>
                View
              </button>
              {d.note && <span className="muted evidence-document-note">{d.note}</span>}
            </li>
          );
        })}
      </ul>
      {viewing && (
        <DocumentViewer data={viewing.data} document={docs[viewing.index]} documents={docs} busy={viewing.busy} error={viewing.error} signIn={viewing.signIn}
          position={{ index: viewing.index, count: docs.length }} onGo={(i) => void open(i)} onClose={close} today={today} />
      )}
    </section>
  );
}

/** What jason stored for one evidence address, fetched when it opens (`GET /api/evidence`), or `data` rendered as given
 * (previews, tests). The stored words are recited, then cited; nothing is paraphrased. A miss shows the note and the
 * command that fills it, never an empty box. Commands are shown to copy; the page never runs one.
 *
 * When the answer is `refreshable`, a button beside Close reads it again from the outside system now
 * (`POST /api/evidence/refresh`), as a named person's act: one click, one read, never on open, a timer, or focus. It
 * writes nothing outside jason, so there is no Confirm. `by` is that person (omitted: the session's signed-in, acting, or
 * picked name). A `data` panel reads again only through `onRefresh`; `refreshing` forces the reading state (previews).
 *
 * The answer's `documents` are listed with a View button each. A view opens the document unmasked in `DocumentViewer`
 * (`POST /api/evidence/view`), under the same person, and the server logs it; nothing is viewed on open. A `data` panel
 * views only through `onView`. */
export function EvidencePanel({ address, label, approval, data, today, level = 4, id, onClose, by, onRefresh, refreshing = false, onView }: {
  address: string; label?: string; approval?: string; data?: EvidenceAnswer | null; today?: Date;
  level?: 3 | 4 | 5 | 6; id?: string; onClose?: () => void;
  by?: string; onRefresh?: (req: EvidenceRefreshRequest) => Promise<EvidenceAnswer>; refreshing?: boolean;
  onView?: (req: DocumentViewRequest) => Promise<DocumentView>;
}) {
  const [answer, setAnswer] = useState<EvidenceAnswer | null>(data ?? null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!data);
  const [rereading, setRereading] = useState(false);
  const [reread, setReread] = useState<{ tone: "status" | "error"; text: string; signIn?: string } | null>(null);
  const [showWhy, setShowWhy] = useState(false);
  const inFlight = useRef(false);
  const alive = useRef(true);
  const rereadRef = useRef<HTMLButtonElement | null>(null);
  const titleId = useId();
  const whyId = useId();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const refreshable = answer?.refreshable ?? null;
  const refresher = onRefresh ?? (data ? null : refreshEvidence);
  const documents = answer?.documents ?? [];
  const viewer = onView ?? (data ? null : viewDocument);
  const sessionMe = useMe(by === undefined && ((!!refreshable && !!refresher) || (documents.length > 0 && !!viewer)));
  const who = (by ?? sessionMe).trim();
  // The server's own calls need a Google sign-in; passed-in calls (previews, tests) take the name as given.
  const liveRefresh = !onRefresh && !!refresher;
  const liveView = !onView && !!viewer;
  const account = useAccount((liveRefresh && !!refreshable) || (liveView && documents.length > 0));
  const gateFor = (live: boolean): Gate => ({ live, known: account.known, signedIn: !!account.account, href: account.href });
  const system = refreshable?.system || "the outside system";
  const busy = rereading || refreshing;
  const needsSignIn = signInWhy(gateFor(liveRefresh), "read it again");
  const why = !refresher
    ? "This copy is shown as given; the page does not read it again."
    : needsSignIn || (!who ? "Sign in or pick your name to read it again." : "");

  const readAgain = async () => {
    if (busy || inFlight.current || !refreshable) return;
    if (why || !refresher) { setShowWhy(true); return; }
    inFlight.current = true;
    setRereading(true);
    setReread({ tone: "status", text: `Reading from ${system}…` });
    try {
      const fresh = await refresher({ address, ...(approval ? { approval } : {}), by: who });
      if (!alive.current) return;
      setAnswer(fresh);
      setError("");
      const r = fresh.refreshed;
      setReread({ tone: "status", text: `Read from ${r?.system || system} just now by ${r?.by || who}.` });
    } catch (e: unknown) {
      if (!alive.current) return;
      const status = e instanceof ApiError ? e.status : undefined;
      const message = e instanceof Error ? e.message : String(e);
      const asked = signInRefusal(e);
      const text = asked ? message
        : status === 400 ? "This evidence can't be read again from the page."
        : status === 409 || status === 403 || status === 405 ? message
        : `jason-web did not answer: ${message}`;
      setReread({ tone: "error", text, signIn: asked?.href });
    } finally {
      inFlight.current = false;
      if (alive.current) {
        setRereading(false);
        // Focus stays on the button; if a re-render lost it to the page, put it back.
        if (typeof document !== "undefined" && (!document.activeElement || document.activeElement === document.body)) rereadRef.current?.focus();
      }
    }
  };

  const version = useContext(EvidenceVersion);
  const fetched = useRef("");
  useEffect(() => {
    if (data) {
      setAnswer(data);
      setLoading(false);
      return;
    }
    const ctl = new AbortController();
    const key = `${address}\n${approval ?? ""}`;
    // The same record fetched again (a batch read it): the answer stays shown until the new one replaces it.
    if (fetched.current !== key) {
      setAnswer(null);
      setLoading(true);
    }
    fetched.current = key;
    setError("");
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
  }, [address, approval, data, version]);

  const a = answer;
  const title = a?.label || label || address;
  const sources = a?.sources ?? [];
  const refresh = a?.refresh ?? [];
  const miss = !!a && !a.found;
  return (
    <div className="evidence-panel" id={id} role="group" aria-labelledby={titleId}>
      <div className="evidence-panel-head">
        <Heading level={level} id={titleId}>{title}</Heading>
        {(refreshable || onClose) && (
          <span className="evidence-panel-actions">
            {refreshable && (
              <button type="button" ref={rereadRef} className="evidence-reread"
                aria-label={`Read again from ${system}`}
                title={`${sentence(refreshable.what)}${refreshable.what ? " " : ""}Reads ${system} now, under your name; writes nothing to ${system}.`}
                aria-disabled={busy || !!why ? true : undefined} aria-busy={busy ? true : undefined}
                aria-describedby={why ? whyId : undefined}
                onClick={readAgain} onFocus={() => why && setShowWhy(true)} onBlur={() => setShowWhy(false)}>
                <RereadIcon />
              </button>
            )}
            {onClose && <button type="button" className="link" onClick={onClose}>Close</button>}
          </span>
        )}
      </div>
      {refreshable && why && (
        <p className={showWhy ? "muted evidence-reread-why" : "visually-hidden"}>
          <span id={whyId}>{why}</span>{needsSignIn && account.known && showWhy && <SignInLink href={account.href} />}
        </p>
      )}
      <p className="muted evidence-address">Address <code>{a?.address || address}</code></p>
      <div aria-live="polite" className="evidence-panel-status">
        {loading && <p className="muted">Reading what jason stored for this address.</p>}
        {error && <p className="notice notice-error">jason-web did not answer: {error}</p>}
        {(refreshing && !rereading) ? <p className="muted">{`Reading from ${system}…`}</p>
          : reread && <p className={reread.tone === "error" ? "notice notice-error" : "muted"}>{reread.text}{reread.signIn && <SignInLink href={reread.signIn} />}</p>}
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
          {documents.length > 0 && (
            <Documents docs={documents} level={level} address={address} approval={approval} who={who}
              viewer={viewer} gate={gateFor(liveView)} today={today} />
          )}
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

const PAYHOA = "payhoa:";
const requests = (n: number) => `${n} ${n === 1 ? "request" : "requests"}`;

/** "Read every request again": the plan's PayHOA requests read again now (`POST /api/evidence/refresh-all`), as a named
 * person's act. Offered only when `refs` name a `payhoa:` address (the server decides what it reads); one click, one
 * batch, never on load. `by` is that person (omitted: the session's signed-in, acting, or picked name). `onDone` runs
 * after a batch the server answered, so the plan's open panels fetch again. */
export function RefreshAllEvidence({ approval, refs, by, onDone }: {
  approval: string; refs: readonly (string | EvidenceRef)[]; by?: string; onDone?: (r: EvidenceRefreshAll) => void;
}) {
  const count = new Set(refs.filter(openable).map((e) => e.address).filter((x) => x.startsWith(PAYHOA))).size;
  const sessionMe = useMe(by === undefined && count > 0);
  const who = (by ?? sessionMe).trim();
  const account = useAccount(count > 0);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<{ tone: "status" | "warn" | "error"; text: string; signIn?: string } | null>(null);
  const inFlight = useRef(false);
  const alive = useRef(true);
  const button = useRef<HTMLButtonElement | null>(null);
  const whyId = useId();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  if (!count) return null;
  const needsSignIn = signInWhy({ live: true, known: account.known, signedIn: !!account.account, href: account.href },
    "read them again");
  const why = needsSignIn || (who ? "" : "Sign in or pick your name to read them again.");

  const readAll = async () => {
    if (busy || inFlight.current || why) return;
    inFlight.current = true;
    setBusy(true);
    setSaid({ tone: "status", text: `Reading ${requests(count)} from PayHOA…` });
    try {
      const r = await refreshAllEvidence({ approval, by: who });
      if (!alive.current) return;
      const failed = r.failed ?? [];
      const done = `Read ${requests((r.refreshed ?? []).length)} from PayHOA just now by ${r.by || who}.`;
      const missed = failed.length
        ? ` ${failed.length} could not be read: ${failed.map((f) => `${f.address}: ${f.error}`).join("; ")}`
        : "";
      setSaid({ tone: failed.length ? "warn" : "status", text: sentence(done + missed) });
      onDone?.(r);
    } catch (e: unknown) {
      if (!alive.current) return;
      const status = e instanceof ApiError ? e.status : undefined;
      const message = e instanceof Error ? e.message : String(e);
      const asked = signInRefusal(e);
      setSaid({ tone: "error", text: asked || (status && [400, 403, 405, 409].includes(status)) ? message : `jason-web did not answer: ${message}`, signIn: asked?.href });
    } finally {
      inFlight.current = false;
      if (alive.current) {
        setBusy(false);
        if (typeof document !== "undefined" && (!document.activeElement || document.activeElement === document.body)) button.current?.focus();
      }
    }
  };

  return (
    <div className="evidence-reread-all-row">
      <button type="button" ref={button} className="evidence-reread-all"
        title="Reads each request in this plan from PayHOA now, under your name; writes nothing to PayHOA."
        aria-disabled={busy || !!why ? true : undefined} aria-busy={busy ? true : undefined}
        aria-describedby={why ? whyId : undefined} onClick={readAll}>
        <RereadIcon />Read every request again
      </button>
      {why && <span className="muted evidence-reread-all-why"><span id={whyId}>{why}</span>{needsSignIn && account.known && <SignInLink href={account.href} />}</span>}
      <span aria-live="polite" className="evidence-reread-all-status">
        {said && <span className={said.tone === "error" ? "notice notice-error" : said.tone === "warn" ? "notice notice-warn" : "muted"}>{said.text}{said.signIn && <SignInLink href={said.signIn} />}</span>}
      </span>
    </div>
  );
}

function openable(e: string | EvidenceRef): e is EvidenceRef & { address: string } {
  return typeof e !== "string" && !!e.address;
}

/** Records, commands, paths, and links a row cites. A string, or a ref with no address, is a plain chip. A ref with an
 * address is a chip that opens what jason stored for it below the chips (one at a time; Escape closes it and returns to
 * the chip). A command is shown as code so it can be copied, never run from here. `by` is who reads a panel again
 * (omitted: the session's name). */
export function Evidence({ items, label = "Evidence", approval, level, by }: {
  items?: readonly (string | EvidenceRef)[] | null; label?: string; approval?: string; level?: 3 | 4 | 5 | 6; by?: string;
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
          approval={approval} level={level} by={by} onClose={close} />
      )}
    </div>
  );
}
