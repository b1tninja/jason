import { useState } from "react";
import { Badge, Card, Caveats, Confirm, DataTable, Findings, Money, Pill, RemoteView, Stat, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import type { CollectionRow } from "./types";
import "./choices.css";

export interface CollectionStep { step: string; decidedOn: string; by: string; vote: string; note: string; recorded: string; history: string[] }
export type DelinquentAccount = CollectionRow & { steps: CollectionStep[]; latestStep: CollectionStep | null };
export interface Delinquency {
  found?: boolean; note?: string; counts: Record<string, number>; rows: DelinquentAccount[]; pastDueCents: number;
  recordedOnly?: { apn: string; steps: CollectionStep[]; latestStep: CollectionStep }[]; steps: string[]; lienStep: string; rollCall: string; caveats?: string[];
}
interface Account { apn: string; steps: CollectionStep[]; latest: CollectionStep | null }

const today = () => new Date().toISOString().slice(0, 10);

/** One account opened: the steps the board recorded on it, and the form that records the next one. */
function StepPanel({ row, steps, lienStep, rollCall, onSaved }: { row: DelinquentAccount; steps: string[]; lienStep: string; rollCall: string; onSaved: (apn: string, a: Account) => void }) {
  const [step, setStep] = useState(steps[0] ?? "");
  const [decidedOn, setDecidedOn] = useState(today());
  const [by, setBy] = useState("");
  const [vote, setVote] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true); setError("");
    try { onSaved(row.apn, await postJson<Account>(`/api/write/delinquency/${encodeURIComponent(row.apn)}`, { step, decidedOn, by, vote, note })); setNote(""); setVote(""); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const ready = step && by.trim() && decidedOn && (!vote.trim() || /^\d+-\d+$/.test(vote.trim()));
  return (
    <div className="grid-2">
      <Card title={`Steps recorded on ${row.address}`}>
        <p className="muted">The statute's next step, from the ledger and the liens: <strong>{row.nextStep || "none"}</strong>.</p>
        {row.steps.length === 0 ? <p className="muted">No step recorded yet.</p> : (
          <ol className="choice-steps" aria-label="recorded steps">
            {row.steps.map((s, i) => <li key={i}><strong>{s.step}</strong> on {s.decidedOn}{s.vote && <> · vote {s.vote}</>} · by {s.by}{s.note && <> · {s.note}</>}</li>)}
          </ol>
        )}
      </Card>
      <Card title="Record the board's step">
        <p className="muted">jason records the step the board took; it submits, records, and forecloses nothing.</p>
        <div className="fields">
          <label className="wide">Step <select value={step} onChange={(e) => setStep(e.target.value)}>{steps.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <label>Decided on <input type="date" value={decidedOn} onChange={(e) => setDecidedOn(e.target.value)} /></label>
          <label>Recorded by <input value={by} onChange={(e) => setBy(e.target.value)} /></label>
          <label>Vote (ayes-noes) <input value={vote} placeholder="3-0" onChange={(e) => setVote(e.target.value)} /></label>
          <label className="wide">Note <input value={note} onChange={(e) => setNote(e.target.value)} /></label>
        </div>
        {step === lienStep && <p className="notice notice-warn">{rollCall}</p>}
        {ready && (
          <Confirm busy={busy} onConfirm={save} summary={<p>Record "{step}" on {row.address}, decided {decidedOn}{vote.trim() ? `, vote ${vote.trim()}` : ""}, recorded by {by.trim()}. jason records it and does nothing else.</p>}>Record the step</Confirm>
        )}
        {error && <p className="notice notice-error">{error}</p>}
      </Card>
    </div>
  );
}

/** The delinquent accounts with the board's recorded steps beside the statute's next step; a step is recorded once, through a confirm. */
export function DelinquencyView() {
  const r = useApi<Delinquency>("/api/delinquency");
  const [open, setOpen] = useState("");
  const [patched, setPatched] = useState<Record<string, Account>>({});
  const cols: Column<DelinquentAccount>[] = [
    { key: "address", header: "Unit" },
    { key: "standing", header: "Standing", render: (x) => <Pill word={x.standing} meaning={x.meaning} /> },
    { key: "pastDueCents", header: "Past due", align: "right", render: (x) => <Money cents={x.pastDueCents} /> },
    { key: "lien", header: "Lien", value: (x) => x.lien ?? "", render: (x) => x.lien ? <>{x.lien} <span className="muted">{x.lienStatus} {x.lienDays != null && `· ${x.lienDays}d`}</span></> : <span className="muted">—</span> },
    { key: "nextStep", header: "Next step (the statute's)" },
    { key: "latestStep", header: "Latest recorded step", value: (x) => x.latestStep?.decidedOn ?? "", render: (x) => x.latestStep ? <><Badge tone="good">{x.latestStep.step}</Badge> <span className="muted">{x.latestStep.decidedOn}</span></> : <span className="muted">none</span> },
    { key: "open", header: "", render: (x) => <button className={open === x.apn ? "" : "primary"} onClick={() => setOpen(open === x.apn ? "" : x.apn)}>{open === x.apn ? "Close" : "Open"}</button> },
  ];
  return (
    <RemoteView r={r}>
      {(d) => {
        const rows = d.rows.map((x) => { const p = patched[x.apn]; return p ? { ...x, steps: p.steps, latestStep: p.latest } : x; });
        const current = rows.find((x) => x.apn === open);
        return (
          <div className="stack">
            <p className="notice notice-warn">Executive session (CIV 4935): for directors. jason records the board's step; it never submits an account to a collection agency, records a lien, or starts a foreclosure.</p>
            <Card title={`Delinquent accounts (${rows.length})`} actions={<Stat label="past due" value={<Money cents={d.pastDueCents} />} />}>
              <DataTable rows={rows} columns={cols} />
              {rows.some((x) => x.floorQuestion) && <Findings items={rows.filter((x) => x.floorQuestion).map((x) => `${x.address}: ${x.floorQuestion}`)} />}
            </Card>
            {current && <StepPanel key={current.apn} row={current} steps={d.steps} lienStep={d.lienStep} rollCall={d.rollCall} onSaved={(apn, a) => setPatched((p) => ({ ...p, [apn]: a }))} />}
            {d.recordedOnly && d.recordedOnly.length > 0 && <Card title="Steps recorded on accounts no longer in the ledger's rows"><ul className="choice-steps">{d.recordedOnly.map((o) => <li key={o.apn}>{o.apn}: {o.latestStep.step} on {o.latestStep.decidedOn}</li>)}</ul></Card>}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
