import { useMemo, useState } from "react";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { Caveats } from "./Caveats";
import { Checklist } from "./Checklist";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import type { Brief } from "./DecisionBrief";
import { DriveAttach, type DriveFile } from "./DriveAttach";
import { Pill } from "./Pill";

export type MeetingFormat = "" | "in person" | "hybrid" | "teleconference";
export type AgendaKind = "consent" | "discussion" | "action" | "executive";
export interface PlanBasics { date: string; start: string; format: MeetingFormat; location: string; join: string; dialIn: string; help: string }
export interface PlanZoom { topic: string; joinUrl: string; dialIn: string; command?: string | null; note?: string }
export interface ReadinessCheck { label: string; ok: boolean; why?: string }
export interface AgendaCandidate {
  id: string; title: string; ask: string; session: string; authority?: string; priority?: string; evidence?: string[];
  kind: AgendaKind; include: boolean; motion: string; allot: number; order: number; packet: DriveFile[]; brief?: Brief | null;
  readiness: { ready: boolean; checks: ReadinessCheck[] }; suggestion: string;
}
export interface NoticeLine { label: string; ready: boolean; detail?: string }
export interface AgendaPlan {
  found?: boolean; note?: string; date: string; today: string; noticeBy: string; executiveNoticeBy: string;
  directors: string[]; decisions: unknown[]; basics: PlanBasics; zoom: PlanZoom; candidates: AgendaCandidate[];
  kinds: AgendaKind[]; formats: MeetingFormat[]; rules: string[]; notice: { by: string; executiveBy: string; required: NoticeLine[] };
  steps: string[]; commands: { agendaDoc: string; packetDoc: string; minutesDraft: string; notice: string; onAgenda: string[] };
  updated: string; history: string[]; agendaMarkdown?: string; caveats?: string[];
}
export interface ItemDraft { include: boolean; kind: AgendaKind; motion: string; allot: number; order: number; packet: DriveFile[] }
/** What a save sends: `by` and only the parts that changed. */
export interface PlanBody { by: string; basics?: Partial<Omit<PlanBasics, "date">>; items?: Record<string, Partial<ItemDraft>>; zoom?: Partial<Pick<PlanZoom, "topic" | "joinUrl" | "dialIn">> }

const EXEC = "executive session";
const FORMATS: { id: MeetingFormat; label: string; hint: string }[] = [
  { id: "in person", label: "In person", hint: "A physical location only." },
  { id: "hybrid", label: "Hybrid", hint: "A physical location plus teleconference (CIV 4090(b))." },
  { id: "teleconference", label: "Entirely by teleconference", hint: "No physical location (CIV 4926). Every director vote is a roll call." },
];
const BASIC_LABELS: Record<keyof Omit<PlanBasics, "date">, string> = { start: "Start", format: "Format", location: "Location", join: "Join instructions", dialIn: "Telephone option", help: "Help contact" };
const ZOOM_LABELS: Record<"topic" | "joinUrl" | "dialIn", string> = { topic: "Zoom topic", joinUrl: "Zoom join link", dialIn: "Zoom dial-in" };
const ITEM_LABELS: Record<keyof ItemDraft, string> = { include: "on the agenda", kind: "kind", motion: "motion", allot: "minutes", order: "order", packet: "packet" };

const TIME = /^(\d{1,2}):(\d{2})$/;
export function addMinutes(hhmm: string, m: number): string {
  const found = TIME.exec(hhmm);
  if (!found) return "";
  const t = Number(found[1]) * 60 + Number(found[2]) + m;
  return `${String(Math.floor(t / 60) % 24).padStart(2, "0")}:${String(((t % 60) + 60) % 60).padStart(2, "0")}`;
}
export function clock(hhmm: string): string {
  const found = TIME.exec(hhmm);
  if (!found) return "—";
  const h = Number(found[1]), mm = Number(found[2]);
  return `${((h + 11) % 12) + 1}:${String(mm).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
}

/** One candidate on the Ready to act step: include, title, readiness Pill, the checks inline, jason's one line. */
export function ReadinessRow({ candidate, onToggle }: { candidate: AgendaCandidate; onToggle?: (include: boolean) => void }) {
  const c = candidate;
  return (
    <article className="readiness">
      <input type="checkbox" checked={c.include} onChange={(e) => onToggle?.(e.target.checked)} aria-label={`Put ${c.title} on the agenda`} />
      <div className="readiness-body">
        <div className="row wrap">
          <strong>{c.title}</strong>
          <Pill word={c.readiness.ready ? "ready" : "needs work"} />
          {c.session === EXEC && <Badge tone="warn">executive session</Badge>}
        </div>
        <ul className="readiness-checks">
          {c.readiness.checks.map((k) => (
            <li key={k.label} className={k.ok ? "check-ok" : "check-bad"} title={k.why}>{k.ok ? "✓" : "✗"} {k.label}</li>
          ))}
        </ul>
        {c.suggestion && <p className="readiness-say">jason: {c.suggestion}</p>}
      </div>
    </article>
  );
}

interface Row { id: string; title: string; start: string; allot: number; fixed: boolean; note?: string; cand?: AgendaCandidate; draft?: ItemDraft }

function draftsOf(plan: AgendaPlan): Record<string, ItemDraft> {
  const out: Record<string, ItemDraft> = {};
  for (const c of plan.candidates) out[c.id] = { include: c.include, kind: c.kind, motion: c.motion, allot: c.allot, order: c.order, packet: c.packet ?? [] };
  return out;
}

/** The four-step planner. Every save is a `Confirm` that lists the changed fields; nothing here puts an item on the
 * agenda or sends the notice: those are the terminal commands on the Notice step and a letter a person drafts. */
export function AgendaWizard({ plan, onSave, busy }: { plan: AgendaPlan; onSave: (body: PlanBody) => void | Promise<void>; busy?: boolean }) {
  const [step, setStep] = useState(1);
  const [by, setBy] = useState("");
  const [basics, setBasics] = useState<PlanBasics>({ ...plan.basics });
  const [zoom, setZoom] = useState({ topic: plan.zoom.topic ?? "", joinUrl: plan.zoom.joinUrl ?? "", dialIn: plan.zoom.dialIn ?? "" });
  const [items, setItems] = useState<Record<string, ItemDraft>>(() => draftsOf(plan));
  const cands = useMemo(() => Object.fromEntries(plan.candidates.map((c) => [c.id, c])), [plan]);
  const steps = plan.steps?.length === 4 ? plan.steps : ["Meeting", "Ready to act", "Order and motions", "Notice"];
  const fmt = basics.format;
  const remote = fmt === "hybrid" || fmt === "teleconference";

  // What changed since the plan was loaded: the Confirm summary lists it and the body carries only it.
  const { changes, body } = useMemo(() => {
    const changes: string[] = [];
    const out: PlanBody = { by };
    for (const k of Object.keys(BASIC_LABELS) as (keyof typeof BASIC_LABELS)[]) {
      if ((basics[k] ?? "") !== (plan.basics[k] ?? "")) { changes.push(`${BASIC_LABELS[k]}: ${plan.basics[k] || "—"} → ${basics[k] || "—"}`); (out.basics ??= {})[k] = basics[k] as never; }
    }
    for (const k of Object.keys(ZOOM_LABELS) as (keyof typeof ZOOM_LABELS)[]) {
      if ((zoom[k] ?? "") !== (plan.zoom[k] ?? "")) { changes.push(`${ZOOM_LABELS[k]}: ${plan.zoom[k] || "—"} → ${zoom[k] || "—"}`); (out.zoom ??= {})[k] = zoom[k]; }
    }
    const base = draftsOf(plan);
    for (const [id, d] of Object.entries(items)) {
      const b = base[id]; if (!b) continue;
      for (const k of Object.keys(ITEM_LABELS) as (keyof ItemDraft)[]) {
        const same = k === "packet" ? JSON.stringify(d.packet) === JSON.stringify(b.packet) : d[k] === b[k];
        if (same) continue;
        const show = (v: unknown) => (k === "packet" ? `${(v as DriveFile[]).length} file(s)` : k === "include" ? (v ? "yes" : "no") : String(v ?? "—") || "—");
        changes.push(`${cands[id]?.title ?? id}, ${ITEM_LABELS[k]}: ${show(b[k])} → ${show(d[k])}`);
        ((out.items ??= {})[id] ??= {})[k] = d[k] as never;
      }
    }
    return { changes, body: out };
  }, [basics, zoom, items, plan, by, cands]);

  const setItem = (id: string, patch: Partial<ItemDraft>) => setItems((s) => ({ ...s, [id]: { ...s[id], ...patch } }));
  const openOrdered = plan.candidates.filter((c) => c.session !== EXEC && items[c.id]?.include).sort((a, b) => items[a.id].order - items[b.id].order || a.order - b.order);
  const execIncluded = plan.candidates.filter((c) => c.session === EXEC && items[c.id]?.include);
  const move = (id: string, d: number) => {
    const ids = openOrdered.map((c) => c.id);
    const i = ids.indexOf(id), j = i + d;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    setItems((s) => { const n = { ...s }; ids.forEach((k, idx) => { n[k] = { ...n[k], order: idx }; }); return n; });
  };

  // The run of the meeting with start times from the basics and the allotments.
  const rows: Row[] = [];
  let t = basics.start;
  const push = (r: Omit<Row, "start">) => { rows.push({ ...r, start: t ? clock(t) : "—" }); t = t ? addMinutes(t, r.allot) : t; };
  push({ id: "call", title: "Call to order; roll call and quorum", allot: 3, fixed: true });
  openOrdered.forEach((c) => push({ id: c.id, title: c.title, allot: items[c.id].allot, fixed: false, cand: c, draft: items[c.id] }));
  push({ id: "forum", title: "Member comment (CIV 4925)", allot: 15, fixed: true, note: "a time limit the board sets" });
  if (execIncluded.length) push({ id: "exec", title: "Adjourn to executive session (CIV 4935)", allot: execIncluded.reduce((s, c) => s + (items[c.id].allot || 0), 0), fixed: true, note: execIncluded.map((c) => c.title).join("; ") + " (by title only; noted generally in the next open minutes, 4935(e))" });
  push({ id: "adjourn", title: "Adjournment", allot: 1, fixed: true });
  const total = rows.reduce((s, r) => s + r.allot, 0);
  const readyCount = plan.candidates.filter((c) => c.readiness.ready && c.session !== EXEC).length;
  const workCount = plan.candidates.filter((c) => !c.readiness.ready && c.session !== EXEC).length;
  const execCount = plan.candidates.filter((c) => c.session === EXEC).length;
  const included = plan.candidates.filter((c) => items[c.id]?.include);

  const field = (label: string, value: string, set: (v: string) => void, type = "text") => (
    <label className="wfield">{label}<input type={type} value={value} onChange={(e) => set(e.target.value)} /></label>
  );
  const saveBlock = changes.length > 0 && (
    <div className="wizard-save">
      <label className="wfield">Saved by<input value={by} onChange={(e) => setBy(e.target.value)} placeholder="your name" /></label>
      {by.trim() ? (
        <Confirm busy={busy} onConfirm={() => onSave(body)} summary={<div><p>Save to the plan for {plan.date} ({changes.length} change{changes.length === 1 ? "" : "s"}). Nothing goes on the noticed agenda and nothing is sent; the commands on the Notice step do that.</p><ul>{changes.map((c) => <li key={c}>{c}</li>)}</ul></div>}>
          Save the plan
        </Confirm>
      ) : <span className="muted">Enter your name to save {changes.length} change{changes.length === 1 ? "" : "s"}.</span>}
    </div>
  );

  return (
    <div className="wizard">
      <ol className="wizard-steps">
        {steps.map((label, i) => (
          <li key={label}>
            <button className={step === i + 1 ? "step-on" : "step-off"} aria-current={step === i + 1 ? "step" : undefined} onClick={() => setStep(i + 1)}>
              <span className="step-n">{i + 1}</span>{label}
            </button>
          </li>
        ))}
      </ol>

      {step === 1 && (
        <div className="grid-2 wizard-grid">
          <Card title="Meeting">
            <div className="stack wizard-stack">
              <div className="wizard-fields">
                <label className="wfield">Date<input type="date" value={plan.date} readOnly aria-readonly="true" title="The plan is kept by its meeting date; pick another date above." /></label>
                {field("Start", basics.start, (v) => setBasics({ ...basics, start: v }), "time")}
              </div>
              <fieldset className="wizard-formats"><legend>Format</legend>
                {FORMATS.map((f) => (
                  <label key={f.id}><input type="radio" name="format" checked={fmt === f.id} onChange={() => setBasics({ ...basics, format: f.id })} /><span><strong>{f.label}</strong><span className="muted">{f.hint}</span></span></label>
                ))}
              </fieldset>
              {fmt !== "teleconference" && field("Physical location", basics.location, (v) => setBasics({ ...basics, location: v }))}
              {remote && field("Join instructions or link (CIV 4926(a)(1))", basics.join, (v) => setBasics({ ...basics, join: v }))}
              {remote && field("Telephone option (CIV 4926(a)(4))", basics.dialIn, (v) => setBasics({ ...basics, dialIn: v }))}
              {remote && field("Who can help before and during, phone and email (CIV 4926(a)(1))", basics.help, (v) => setBasics({ ...basics, help: v }))}
            </div>
          </Card>
          <Card title="What this format requires">
            <ul className="wizard-rules">{plan.rules.map((r) => <li key={r}>{r}</li>)}</ul>
            <p>Notice and the agenda to members by <strong className="num">{plan.noticeBy}</strong>, four days ahead (CIV 4920); by <strong className="num">{plan.executiveNoticeBy}</strong> for a meeting held solely in executive session.</p>
            {fmt !== plan.basics.format && <p className="muted">The list follows the saved format; save the plan to see what {fmt || "the new format"} requires.</p>}
          </Card>
        </div>
      )}

      {step === 2 && (
        <div className="stack wizard-stack">
          <div className="row wrap"><Badge tone="good">{`${readyCount} ready`}</Badge><Badge tone="warn">{`${workCount} need work`}</Badge><Badge>{`${execCount} executive session`}</Badge><span className="muted">{included.length} on the agenda</span></div>
          {plan.candidates.length === 0 && <p className="muted">No board item is proposed or on the agenda for {plan.date}. Propose one with jason board.</p>}
          <div className="stack wizard-stack">
            {plan.candidates.map((c) => <ReadinessRow key={c.id} candidate={{ ...c, include: items[c.id]?.include ?? c.include }} onToggle={(v) => setItem(c.id, { include: v })} />)}
          </div>
        </div>
      )}

      {step === 3 && (
        <Card title="Order and motions">
          <p className="muted">Runs about {total} minutes{basics.start ? `, ${clock(basics.start)} to ${clock(t)}` : "; set a start time on the Meeting step for the clock"}.</p>
          <ol className="order-list">
            {rows.map((r, i) => (
              <li key={r.id} className="order-row">
                <span className="order-start num">{r.start}</span>
                <div className="order-body">
                  <span><span className="muted num">{i + 1}. </span><strong>{r.title}</strong></span>
                  {r.fixed ? <span className="muted order-fixed">{r.allot} min{r.note ? ` · ${r.note}` : ""}</span> : r.cand && r.draft && (
                    <>
                      <span className="order-controls">
                        <select value={r.draft.kind} aria-label={`Kind of ${r.title}`} onChange={(e) => setItem(r.id, { kind: e.target.value as AgendaKind })}>
                          {(plan.kinds ?? ["consent", "discussion", "action", "executive"]).map((k) => <option key={k} value={k}>{k}</option>)}
                        </select>
                        <input type="number" min={1} max={120} value={r.draft.allot} aria-label={`Minutes for ${r.title}`} onChange={(e) => setItem(r.id, { allot: Number(e.target.value) })} />
                        <span className="muted">min</span>
                        <button onClick={() => move(r.id, -1)} aria-label={`Move ${r.title} up`}>↑</button>
                        <button onClick={() => move(r.id, 1)} aria-label={`Move ${r.title} down`}>↓</button>
                        {r.cand.authority && <span className="muted">{r.cand.authority}</span>}
                      </span>
                      <label className="wfield">Proposed motion<textarea rows={2} value={r.draft.motion} onChange={(e) => setItem(r.id, { motion: e.target.value })} /></label>
                      <div className="wfield-block"><span className="muted">Packet</span><DriveAttach files={r.draft.packet} onChange={(packet) => setItem(r.id, { packet })} /></div>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {step === 4 && (
        <div className="stack wizard-stack">
          {remote && (
            <Card title="Zoom meeting">
              <p className="muted">{plan.zoom.note ?? "The notice needs the join link and the telephone option."}</p>
              {plan.zoom.command ? <Command cmd={plan.zoom.command} note="Creates the meeting on the association's account; a person runs it." /> : null}
              <div className="wizard-fields">
                {field("Topic", zoom.topic, (v) => setZoom({ ...zoom, topic: v }))}
                {field("Join link", zoom.joinUrl, (v) => setZoom({ ...zoom, joinUrl: v }))}
                {field("Dial-in", zoom.dialIn, (v) => setZoom({ ...zoom, dialIn: v }))}
              </div>
            </Card>
          )}
          <Card title="Notice checks">
            <Checklist title="What the notice must carry (CIV 4920, 4926)" items={plan.notice.required} />
            <p className="muted">The notice is a letter a person drafts, approves, and sends. <a href="#/approvals">Draft it in Approvals</a>; nothing on this page sends it.</p>
          </Card>
          <Card title="Put the items on the noticed agenda">
            <p className="muted">Each command sets the board's status and meeting on one item; the agenda Doc is written from the items so marked. Run them in a terminal; the page never runs a command and never changes an item.</p>
            {plan.commands.onAgenda.length === 0 && <p className="notice notice-warn">No item is marked to include; save the plan with items included and the commands appear here.</p>}
            {plan.commands.onAgenda.map((cmd) => <Command key={cmd} cmd={cmd} note="Sets the board's status and meeting on the item; nothing else changes." />)}
            <Command cmd={plan.commands.agendaDoc} note="Writes the agenda Doc from last month's (its id) with the items on the agenda; a Drive write a person confirms." />
            <Command cmd={plan.commands.packetDoc} note="Writes the packet as a confidential Doc, private until shared; a Drive write a person confirms." />
          </Card>
        </div>
      )}

      {saveBlock}
      <div className="wizard-nav">
        {step > 1 ? <button onClick={() => setStep(step - 1)}>Back</button> : <span />}
        {step < 4 && <button className="primary" onClick={() => setStep(step + 1)}>{step === 3 ? "Review the notice" : "Next"}</button>}
      </div>
      <Caveats items={plan.caveats} />
    </div>
  );
}
