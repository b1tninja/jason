import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Badge } from "../components";
import { getJson, postJson } from "../lib/api";
import { STATE_LOOK, sizeWords, words, type JobState, type Plan, type ReadPlan } from "./recordTypes";

/** The state of a slot or a pick, as the server's word with a glyph and a tone that only repeat it. */
export function SlotWord({ state, word }: { state: string; word?: string }) {
  const look = STATE_LOOK[state] ?? STATE_LOOK.empty;
  return <Badge tone={look.tone} glyph={look.glyph}>{word || words(state)}</Badge>;
}

/** The write route of a slot: its key is in the path (slashes and all), never a file's name or id. */
export const writePath = (slot: string) => `/api/write/records/${slot.split("/").map(encodeURIComponent).join("/")}`;

/** A file read in the browser for an upload: its name, size, and bytes as base64. Nothing is sent until an act is previewed. */
export function useFileBytes() {
  const [file, setFile] = useState<{ name: string; size: number; base64: string } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const choose = useCallback((f: File | null | undefined) => {
    setFile(null); setError("");
    if (!f) return;
    setBusy(true);
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result ?? "");
      setFile({ name: f.name, size: f.size, base64: url.slice(url.indexOf(",") + 1) });
      setBusy(false);
    };
    reader.onerror = () => { setError("The browser could not read that file."); setBusy(false); };
    reader.readAsDataURL(f);
  }, []);
  return { file, error, busy, choose };
}

/** The largest upload the community allows, from the limits table (`upload.max_bytes`), or nothing when it cannot be read: the
 * server states the limit in its own words either way. */
export function useUploadCap(): { bytes: number | null; words: string } {
  const [cap, setCap] = useState<{ bytes: number | null; words: string }>({ bytes: null, words: "" });
  useEffect(() => {
    let on = true;
    getJson<{ limits?: { key: string; value: unknown; words: string }[] }>("/api/limits").then(
      (d) => {
        const row = d.limits?.find((l) => l.key === "upload.max_bytes");
        if (on && row) setCap({ bytes: typeof row.value === "number" ? row.value : null, words: row.words });
      },
      () => undefined,
    );
    return () => { on = false; };
  }, []);
  return cap;
}

const TERMINAL = new Set(["done", "failed", "cancelled"]);

/** A queued job, polled until it ends: a reading is never run in the page, so the page says where it stands. */
export function JobWatch({ id, command, onFinished, every = 3000 }: { id: number; command?: string; onFinished?: (status: string) => void; every?: number }) {
  const [state, setState] = useState<JobState | null>(null);
  const [lost, setLost] = useState("");
  const done = useRef(onFinished);
  done.current = onFinished;
  useEffect(() => {
    let on = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const s = await getJson<JobState>(`/api/jobs?job=${id}`);
        if (!on) return;
        setState(s); setLost("");
        const status = s.job?.status ?? "";
        if (TERMINAL.has(status)) { done.current?.(status); return; }
      } catch (e) {
        if (!on) return;
        setLost((e as Error).message);
      }
      timer = setTimeout(poll, every);
    };
    void poll();
    return () => { on = false; if (timer) clearTimeout(timer); };
  }, [id, every]);
  const status = state?.job?.status ?? "queued";
  const ended = TERMINAL.has(status);
  return (
    <div className={`record-job${status === "failed" ? " record-job-bad" : ""}`} role="status">
      <Badge tone={status === "failed" ? "bad" : status === "done" ? "good" : "neutral"} glyph={status === "failed" ? "triangle-alert" : status === "done" ? "circle-check" : "clock"}>{`job ${id}: ${status}`}</Badge>{" "}
      {ended
        ? (status === "done" ? "The reading is finished; the slot is up to date." : status === "failed" ? "The reading failed. Read its log in the job queue; the pick stands." : "The reading was cancelled.")
        : "jason's worker is fetching the file into its store and reading it. This page does not wait on it."}
      {state?.job?.summary && <> {state.job.summary}</>}
      {lost && <span className="muted"> (could not ask the queue: {lost})</span>}
      {" "}<a href="#/jobs">Open the job queue</a>
      {command && <span className="muted"> · {command}</span>}
    </div>
  );
}

/** What a dry run says, in the server's own words: the note, the facts it would write, both halves of a replace, each part of a
 * split with its collisions, a proposed rule's text, and how big a reading is. Nothing here is a claim of the page's. */
export function PlanPreview({ plan, by, innerRef }: { plan: Plan; by: string; innerRef?: React.Ref<HTMLDivElement> }) {
  const facts = (would?: Record<string, unknown>) => Object.entries(would ?? {}).filter(([, v]) => v !== null && v !== "" && v !== false && typeof v !== "object" || Array.isArray(v) && v.length > 0 && v.every((x) => typeof x !== "object"));
  const show = (k: string, v: unknown) => k === "size" && typeof v === "number" ? `${sizeWords(v)} (${v} bytes)` : Array.isArray(v) ? v.join(", ") : String(v);
  const list = (would?: Record<string, unknown>) => (
    <dl className="record-facts">
      {facts(would).map(([k, v]) => (<div key={k}><dt>{words(k)}</dt><dd>{show(k, v)}</dd></div>))}
    </dl>
  );
  const proposal = plan.proposal && !Array.isArray(plan.proposal) ? plan.proposal : null;
  return (
    <div className="record-preview" tabIndex={-1} ref={innerRef} role="region" aria-label="What will be recorded">
      <h4>What will be recorded</h4>
      <p>Recorded as <strong>{by}</strong>. Nothing in Drive, PayHOA, or the county is touched, and no file is changed.</p>
      {plan.note && <p className="muted">{plan.note}</p>}
      {plan.already && <p className="notice notice-warn" role="note">The same file is already pinned here; nothing new would be kept.</p>}
      {plan.alsoIn && plan.alsoIn.length > 0 && <p role="note">The same bytes are also pinned for: {plan.alsoIn.join(", ")}.</p>}
      {plan.reads?.map((r: ReadPlan) => (
        <div key={r.pin} className="record-read-plan">
          <p><strong>{r.plan?.name ?? "The pinned file"}</strong>{r.plan ? <>, {sizeWords(r.plan.size)}{r.plan.export ? `, read as ${r.plan.export}` : ""}. {r.plan.willFetch ? "It would be fetched into jason's store." : "It is unchanged since the last read."}</> : null}</p>
          {r.reads && <p className="muted">{r.reads}</p>}
          {r.note && <p className="muted">{r.note}</p>}
          {r.problem && <p className="notice notice-warn" role="alert">{r.problem}</p>}
        </div>
      ))}
      {plan.would && list(plan.would)}
      {plan.first && (<><h5>First</h5>{plan.first.note && <p className="muted">{plan.first.note}</p>}{list(plan.first.would)}</>)}
      {plan.then && (<><h5>Then</h5>{plan.then.note && <p className="muted">{plan.then.note}</p>}{list(plan.then.would)}</>)}
      {plan.parts && plan.parts.length > 0 && (
        <ul className="record-parts">
          {plan.parts.map((p) => (
            <li key={p.segment} className={p.action === "collision" ? "record-collision" : undefined}>
              <strong>Pages {p.pages[0]} to {p.pages[1]}</strong> into <code>{p.slot}</code>{p.period ? ` (${p.period})` : ""}:{" "}
              {p.action === "collision" ? <>a collision, so this part is <strong>not written</strong>. {p.why} {p.kept}</> : "would be filled as a new file of just those pages."}
              {p.action !== "collision" && p.fits === false && " jason's reading does not put this part there; you chose it."}
            </li>
          ))}
        </ul>
      )}
      {proposal?.text && (
        <>
          <p>{proposal.note ?? "A proposal for a person to apply to the profile."} <strong>Nothing is applied here.</strong></p>
          <pre className="record-rule"><code>{proposal.text}</code></pre>
        </>
      )}
    </div>
  );
}

/** One act: its fields, a preview (the dry run), then one confirm button spelled with the act. Changing any field discards the
 * preview, so what is confirmed is what was previewed. A refusal is shown in the server's words with nothing written. */
export function ActPanel({ slot, title, by, body, ready, confirmLabel, previewLabel = "Preview", children, watch, onDone, onCancel, whyNot }: {
  slot: string; title: string; by: string; body: () => Record<string, unknown>; ready: boolean; confirmLabel: string; previewLabel?: string;
  children?: ReactNode; watch: unknown[]; onDone: (out: Plan) => void; onCancel: () => void; whyNot?: string;
}) {
  const id = useId();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const head = useRef<HTMLHeadingElement | null>(null);
  const preview = useRef<HTMLDivElement | null>(null);
  useEffect(() => { head.current?.focus(); }, []);
  useEffect(() => { if (plan) preview.current?.focus(); }, [plan]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setPlan(null); setError(""); }, watch);
  const signedIn = !!by;
  const send = async (dry: boolean) => {
    setBusy(true); setError("");
    try {
      const out = await postJson<Plan>(writePath(slot), { ...body(), by, dryRun: dry });
      if (dry) setPlan(out); else onDone(out);
    } catch (e) {
      setPlan(null); setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const blocked = !ready || !signedIn;
  return (
    <section className="record-act" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} tabIndex={-1} ref={head}>{title}</h3>
      {children}
      {error && <p className="notice notice-error record-refusal" role="alert">{error}</p>}
      {plan && <PlanPreview plan={plan} by={by} innerRef={preview} />}
      <div className="row wrap record-act-buttons">
        {!plan
          ? <button type="button" className="primary" disabled={busy || blocked} onClick={() => send(true)}>{previewLabel}</button>
          : <button type="button" className="primary" disabled={busy || blocked || plan.ok === false} onClick={() => send(false)}>{confirmLabel}</button>}
        <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
        {!signedIn && <span className="muted">Sign in so this goes on the record under your name.</span>}
        {signedIn && !ready && <span className="muted">{whyNot ?? "Fill in the fields above to continue."}</span>}
      </div>
    </section>
  );
}
