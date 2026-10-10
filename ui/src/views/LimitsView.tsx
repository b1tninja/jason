import { Fragment, useEffect, useId, useRef, useState } from "react";
import { Badge, Caveats, RemoteView, ScreenHeader, type Tone } from "../components";
import type { GlyphName } from "../components/Glyph";
import { postJson } from "../lib/api";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import { stampText } from "./StatusView";
import "./limits.css";

/** The newest change in a layer's own trail (`limits_view._last`); `{}` when the layer never changed it. */
export interface LimitChange { kind?: "set" | "reset"; at?: string; by?: string; reason?: string; role?: string; from?: unknown; to?: unknown }

/** One limit as either screen shows it. Setup rows (`GET /api/limits`) carry `source`, `ceiling`, `clamped`; Instance rows
 * (`GET /api/instance-limits`) carry `top`, `communitiesMayGoUpTo`, and a `set` of who set the layer's value. */
export interface LimitRow {
  key: string; kind: string; unit: string; description: string;
  value: unknown; words: string;
  source?: "default" | "env" | "instance" | "community" | string; sourceWords?: string;
  default: unknown; defaultWords: string; minimum?: unknown; maximum?: unknown;
  ceiling?: unknown; ceilingWords: string; topWords?: string; communitiesMayGoUpTo?: unknown;
  rangeWords: string; scopes: string[];
  clamped?: boolean; note?: string; unreadable?: string[];
  set?: { by?: string; at?: string; reason?: string };
  lastChange: LimitChange; why: string; whenHit: string; restart?: boolean;
  override?: boolean; overrideMaxWords?: string;
  editable: boolean; readOnlyWhy: string;
}
export interface LimitGroup { kind: string; name: string; keys: string[]; open: boolean }
export interface LimitsPage {
  found?: boolean; note?: string; asOf: string; scope: "community" | "instance"; community?: string; canChange: boolean; role: string;
  limits: LimitRow[]; groups: LimitGroup[]; host: { drive: string; free: number | null; freeWords: string };
  unreadable?: string[]; caveats: string[];
}
interface PlannedChange { key: string; words: string; now?: unknown; to?: unknown }
interface WriteAnswer {
  ok: boolean; dryRun: boolean; note: string; recordedAs: { by: string; role: string }; changes: PlannedChange[]; caveats?: string[];
}

const SOURCES: Record<string, { tone: Tone; glyph: GlyphName; words: string }> = {
  default: { tone: "neutral", glyph: "circle-dashed", words: "built in" },
  env: { tone: "neutral", glyph: "settings-2", words: "this machine's setting" },
  instance: { tone: "neutral", glyph: "landmark", words: "the operator" },
  community: { tone: "good", glyph: "pencil", words: "this community" },
};

/** "set to 500 MB here..." style note for a stored value that was held to its range: the server's own words, with a glyph. */
function SourceBadge({ row, scope }: { row: LimitRow; scope: LimitsPage["scope"] }) {
  const key = scope === "instance" ? (row.value === null || row.value === undefined ? "default" : "instance") : row.source ?? "default";
  const s = SOURCES[key] ?? SOURCES.default;
  return <Badge tone={s.tone} glyph={s.glyph}>{row.sourceWords && scope === "community" ? row.sourceWords : s.words}</Badge>;
}

/** Whether a group opens by itself: a value someone changed, or a stored value held to its range. */
function startsOpen(rows: LimitRow[], scope: LimitsPage["scope"]): boolean {
  return rows.some((r) => r.clamped || (scope === "instance" ? r.value !== null && r.value !== undefined : r.source !== undefined && r.source !== "default"));
}

function lastChangeWords(c: LimitChange): string {
  if (!c.kind) return "never changed";
  const who = c.by || "someone";
  return `${c.kind === "reset" ? "Reset" : "Changed"} by ${who}, ${c.at ? stampText(c.at).slice(0, 10) : "date unknown"}`;
}

/** The nearest allowed value a refusal names ("... The nearest allowed value is 500 MB."), or "" when it names none. */
export function nearestIn(message: string): string {
  const m = /nearest allowed value is (.+?)\.(?:\s|$)/i.exec(message);
  return m ? m[1] : "";
}

type Mode = "set" | "reset";
interface Editing { key: string; mode: Mode }

/** The editor under a row: change (a value in the unit's own words and a required reason), then the dry run in the
 * server's words, then one confirm button labelled with the change. A reset takes the same two steps. A refusal shows
 * as the server said it, with the nearest allowed value offered as a one-click fill. */
function Editor({ row, mode, scope, by, onDone, onCancel }: {
  row: LimitRow; mode: Mode; scope: LimitsPage["scope"]; by: string; onDone: (key: string) => void; onCancel: () => void;
}) {
  const id = useId();
  const isSwitch = row.unit === "switch";
  const [value, setValue] = useState(isSwitch ? ((row.value ?? row.default) ? "on" : "off") : (row.value === null || row.value === undefined ? "" : row.words));
  const [ceiling, setCeiling] = useState("");
  const [reason, setReason] = useState("");
  const [plan, setPlan] = useState<WriteAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement | null>(null);
  const preview = useRef<HTMLDivElement | null>(null);
  useEffect(() => { first.current?.focus(); }, []);
  useEffect(() => { if (plan) preview.current?.focus(); }, [plan]);

  const body = (dry: boolean) => mode === "reset"
    ? { act: "reset", keys: [row.key], reason: reason.trim(), by: by || undefined, dryRun: dry }
    : { act: "set", changes: { [row.key]: isSwitch ? value === "on" : value.trim() }, ...(scope === "instance" && ceiling.trim() ? { ceiling: ceiling.trim() } : {}),
        reason: reason.trim(), by: by || undefined, dryRun: dry };
  const send = async (dry: boolean) => {
    setBusy(true); setError("");
    try {
      const out = await postJson<WriteAnswer>(`/api/write/limits/${scope}`, body(dry));
      if (dry) setPlan(out); else onDone(row.key);
    } catch (e) {
      setPlan(null); setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const edit = (f: () => void) => { f(); setPlan(null); setError(""); };
  const near = nearestIn(error);
  const target = mode === "reset"
    ? (scope === "instance" ? `the built-in ${row.defaultWords}` : "the layer above")
    : isSwitch ? value : value.trim();
  const confirmLabel = mode === "reset" ? `Reset ${row.description.toLowerCase()} to ${target}` : `Set ${row.description.toLowerCase()} to ${target || "the new value"}`;
  const needsReason = !reason.trim();

  return (
    <section className="limit-editor" aria-label={`${mode === "reset" ? "Reset" : "Change"} ${row.description}`}>
      <h3>{mode === "reset" ? "Reset to default" : "Change this limit"}</h3>
      <p className="muted" id={`${id}-range`}>Allowed: {row.rangeWords}.{row.restart ? " Takes effect after a restart." : ""}</p>
      {mode === "set" && (
        <div className="limit-field">
          <label htmlFor={`${id}-value`}>{isSwitch ? "Switch" : "New value"}</label>
          {isSwitch ? (
            <select id={`${id}-value`} value={value} onChange={(e) => edit(() => setValue(e.target.value))} aria-describedby={`${id}-range`}>
              <option value="on">On</option><option value="off">Off</option>
            </select>
          ) : (
            <input id={`${id}-value`} ref={first} value={value} onChange={(e) => edit(() => setValue(e.target.value))} aria-describedby={`${id}-range`} autoComplete="off" />
          )}
        </div>
      )}
      {mode === "set" && scope === "instance" && !isSwitch && (
        <div className="limit-field">
          <label htmlFor={`${id}-ceiling`}>Ceiling for communities (optional)</label>
          <input id={`${id}-ceiling`} value={ceiling} onChange={(e) => edit(() => setCeiling(e.target.value))} placeholder={row.ceilingWords || row.topWords} autoComplete="off" />
        </div>
      )}
      <div className="limit-field">
        <label htmlFor={`${id}-reason`}>Reason (required, kept in the record; no names)</label>
        <textarea id={`${id}-reason`} ref={mode === "reset" ? (first as never) : undefined} value={reason} rows={2} required aria-required="true" onChange={(e) => edit(() => setReason(e.target.value))} />
      </div>
      {error && (
        <div className="notice notice-error limit-refusal" role="alert">
          <span>{error}</span>
          {near && mode === "set" && <button type="button" onClick={() => edit(() => setValue(near))}>Use {near}</button>}
        </div>
      )}
      {plan && (
        <div className="limit-preview" tabIndex={-1} ref={preview} role="region" aria-label="What will change">
          <h4>What will change</h4>
          <ul>{plan.changes.map((c) => <li key={c.key}>{c.words}</li>)}</ul>
          <p>Recorded as <strong>{plan.recordedAs.by}</strong>, {plan.recordedAs.role}.</p>
          <p className="muted">{plan.note}</p>
        </div>
      )}
      <div className="row wrap limit-actions">
        {!plan ? (
          <button type="button" className="primary" disabled={busy || needsReason} onClick={() => send(true)}>Preview the change</button>
        ) : (
          <button type="button" className="primary" disabled={busy || needsReason} onClick={() => send(false)}>{confirmLabel}</button>
        )}
        <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
        {needsReason && <span className="muted">Write a reason to continue.</span>}
      </div>
    </section>
  );
}

function RowDetail({ row, scope }: { row: LimitRow; scope: LimitsPage["scope"] }) {
  return (
    <dl className="limit-detail">
      <dt>Why this limit exists</dt><dd>{row.why}</dd>
      <dt>What happens when it is reached</dt><dd>{row.whenHit}</dd>
      {row.lastChange.reason && (<><dt>Reason given for the last change</dt><dd>{row.lastChange.reason}</dd></>)}
      {scope === "community" && row.set && Object.keys(row.set).length > 0 && row.set.reason && row.set.reason !== row.lastChange.reason && (
        <><dt>Reason for the value in force</dt><dd>{row.set.reason}</dd></>
      )}
      {row.override && <><dt>Once-only override</dt><dd>An administrator may allow one act up to {row.overrideMaxWords}, with a reason.</dd></>}
    </dl>
  );
}

/** Instance > Limits (`#/instance/limits`; `GET /api/instance-limits`, one of jason's admins as themselves) and Setup > Limits
 * (`#/setup/limits`; `GET /api/limits`, officers, managers, and administrators read; the community's administrator changes).
 * One table of limits by kind; each row's value in words, where it comes from, its allowed range and ceiling, its last
 * change, and on expand why it exists and what happens when it is hit. A change is a dry run, then a confirm with a required
 * reason; a reset takes the same two steps. Writes are `POST /api/write/limits/<scope>`. */
export function LimitsView({ scope }: { scope: "community" | "instance" }) {
  const r = useApi<LimitsPage>(scope === "instance" ? "/api/instance-limits" : "/api/limits");
  const { account } = useSession([]);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [changed, setChanged] = useState<string>("");
  const toggle = (key: string) => setExpanded((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; });
  const done = (key: string) => { setEditing(null); setChanged(key); r.reload(); };
  const title = scope === "instance" ? "Instance limits" : "Limits";

  return (
    <div className="stack limits-view">
      <ScreenHeader
        title={title}
        summary={scope === "instance"
          ? "The instance layer: a value and a ceiling for every community. A community's own values and reasons are not shown here."
          : "What jason is held to for this community: how big, how many, how often. A limit applies to new acts and never removes what exists."}
      />
      <RemoteView r={r}>
        {(d) => {
          const byKey = new Map(d.limits.map((l) => [l.key, l]));
          return (
            <>
              <p className="muted limits-meta">
                {d.canChange
                  ? <>You can change these limits as <strong>{d.role}</strong>; each change is a preview first, then confirmed, with a reason.</>
                  : "You can read these limits. Only the community's administrator changes them."}
                {" "}As of {stampText(d.asOf)}.
              </p>
              {d.host.freeWords && <p className="limits-host" role="status">Room on the drive jason writes to ({d.host.drive || "this machine"}): <strong>{d.host.freeWords}</strong> free. A size limit never lifts the machine's own guard.</p>}
              {d.unreadable && d.unreadable.length > 0 && (
                <p className="notice notice-warn" role="alert">A limits file could not be read, so the built-in values apply there: {d.unreadable.join(", ")}. Fix or move the file, then reload.</p>
              )}
              {changed && byKey.get(changed) && <p className="limit-changed" role="status"><Badge tone="good" glyph="circle-check">Changed just now</Badge> {byKey.get(changed)?.description}: {byKey.get(changed)?.words || byKey.get(changed)?.defaultWords}.</p>}
              {d.groups.map((g) => {
                const rows = g.keys.map((k) => byKey.get(k)).filter((x): x is LimitRow => !!x);
                return (
                  <details key={g.kind} className="limit-group" open={g.open || startsOpen(rows, scope)}>
                    <summary><h2>{g.name}</h2> <span className="muted">{rows.length} {rows.length === 1 ? "limit" : "limits"}</span></summary>
                    <div className="limit-scroll">
                      <table className="limit-table">
                        <caption className="sr-only">{g.name} limits</caption>
                        <thead>
                          <tr><th scope="col">Limit</th><th scope="col">In effect</th><th scope="col">Where it comes from</th><th scope="col">Allowed range</th><th scope="col">Last changed</th><th scope="col">Actions</th></tr>
                        </thead>
                        <tbody>
                          {rows.map((row) => {
                            const open = expanded.has(row.key);
                            const edit = editing?.key === row.key ? editing : null;
                            const here = scope === "instance" ? row.value !== null && row.value !== undefined : row.source === "community";
                            const inEffect = scope === "instance" && (row.value === null || row.value === undefined)
                              ? `not set; communities use ${row.defaultWords}` : row.words;
                            return (
                              <Fragment key={row.key}>
                                <tr data-limit={row.key} data-changed={changed === row.key || undefined}>
                                  <th scope="row" data-label="Limit"><span>{row.description}</span><br /><code className="limit-key">{row.key}</code></th>
                                  <td data-label="In effect"><strong>{inEffect}</strong></td>
                                  <td data-label="Where it comes from">
                                    <SourceBadge row={row} scope={scope} />
                                    {row.clamped && <p className="limit-clamped" role="note">{row.note || "A stored value was held to the allowed range."}</p>}
                                  </td>
                                  <td data-label="Allowed range">{row.rangeWords}<br />
                                    <span className="muted">{scope === "instance" ? `Communities may go up to ${row.ceilingWords || row.topWords || ""}` : `Ceiling here: ${row.ceilingWords}`}</span></td>
                                  <td data-label="Last changed">{lastChangeWords(row.lastChange)}</td>
                                  <td data-label="Actions" className="limit-row-actions">
                                    <button type="button" aria-expanded={open} aria-label={`${open ? "Hide" : "Show"} why and when it is hit: ${row.description}`} onClick={() => toggle(row.key)}>{open ? "Hide why" : "Why"}</button>
                                    {row.editable && d.canChange ? (
                                      <>
                                        <button type="button" aria-label={`Change ${row.description}`} onClick={() => setEditing({ key: row.key, mode: "set" })}>Change</button>
                                        {here && <button type="button" aria-label={`Reset ${row.description} to default`} onClick={() => setEditing({ key: row.key, mode: "reset" })}>Reset</button>}
                                      </>
                                    ) : <span className="muted limit-readonly">{row.readOnlyWhy || (d.canChange ? "" : "Read only")}</span>}
                                  </td>
                                </tr>
                                {(open || edit) && (
                                  <tr className="limit-expand">
                                    <td colSpan={6}>
                                      {open && <RowDetail row={row} scope={scope} />}
                                      {edit && <Editor row={row} mode={edit.mode} scope={scope} by={account?.name ?? ""} onDone={done} onCancel={() => setEditing(null)} />}
                                    </td>
                                  </tr>
                                )}
                              </Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </details>
                );
              })}
              <Caveats items={d.caveats} />
            </>
          );
        }}
      </RemoteView>
    </div>
  );
}
