import { useState } from "react";
import { Badge, Card, Caveats, Clock, Confirm, DataTable, DueDate, Findings, Money, Pill, RemoteView, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import type { Policy } from "./types";
import "./findings.css";

export interface RenewalDecision { number: string; decision: string; decidedOn: string; by: string; premiumCents: number | null; limitsChanged: boolean; memberNoticeNeeded: boolean; noticeAuthority: string; note: string; recorded: string; history: string[] }
type Row = Policy & { key: string; renewal: RenewalDecision | null; daysToTermEnd: number | null; renewalWindow: boolean; memberNoticeNeeded: boolean };
interface Renewals { found?: boolean; note?: string; asOf: string; today: string; windowDays: number; decisions: string[]; policies: Row[]; caveats?: string[] }

const label = (p: Policy) => <>{p.kind.replace(/_/g, " ")}{p.building != null && p.building !== "" ? <span className="muted"> bldg {String(p.building)}</span> : null}</>;

/** The recorded decision, as a person entered it: the board's words, who recorded them, and when. */
function Recorded({ d }: { d: RenewalDecision }) {
  return (
    <div className="recorded">
      <p><Pill word={d.decision} /> decided <strong>{d.decidedOn}</strong>{d.premiumCents != null && <> · premium <Money cents={d.premiumCents} /></>}{d.limitsChanged && <> · <Badge tone="warn">coverage changes</Badge></>}</p>
      {d.note && <blockquote>{d.note}</blockquote>}
      {d.memberNoticeNeeded && <p className="notice notice-warn">Individual notice to the members is needed as soon as reasonably practical ({d.noticeAuthority || "CIV 5810"}); the statute sets no date, and jason sends none.</p>}
      <p className="who">Recorded {d.recorded.slice(0, 10)} by {d.by}</p>
      {d.history.length > 1 && <ul className="history">{d.history.map((h, i) => <li key={i}>{h}</li>)}</ul>}
    </div>
  );
}

/** One policy opened: the term as the clock, then the board's decision entered once, behind a confirm. */
function RenewalPanel({ p, decisions, today, onSaved }: { p: Row; decisions: string[]; today: Date; onSaved: (next: Row) => void }) {
  const r = p.renewal;
  const [decision, setDecision] = useState(r?.decision ?? "");
  const [decidedOn, setDecidedOn] = useState(r?.decidedOn ?? today.toISOString().slice(0, 10));
  const [by, setBy] = useState(r?.by ?? "");
  const [premium, setPremium] = useState(r?.premiumCents != null ? (r.premiumCents / 100).toFixed(2) : "");
  const [limitsChanged, setLimitsChanged] = useState(r?.limitsChanged ?? false);
  const [note, setNote] = useState(r?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const premiumCents = premium.trim() ? Math.round(Number(premium) * 100) : null;
  const premiumOk = premiumCents == null || Number.isFinite(premiumCents);
  const save = async () => {
    setBusy(true); setError("");
    try {
      const saved = await postJson<RenewalDecision>(`/api/write/insurance-renewals/${encodeURIComponent(p.key)}`, { decision, decidedOn, by, premiumCents, limitsChanged, note });
      onSaved({ ...p, renewal: saved, memberNoticeNeeded: saved.memberNoticeNeeded });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const stages = [p.termEnd ? { key: "termEnd", label: "Term in force ends", date: p.termEnd } : null, r ? { key: "decided", label: `Board decided: ${r.decision}`, date: r.decidedOn, done: true } : null]
    .filter((s): s is NonNullable<typeof s> => s != null);
  const changed = !r || decision !== r.decision || decidedOn !== r.decidedOn || premiumCents !== r.premiumCents || limitsChanged !== r.limitsChanged || note !== r.note;
  return (
    <div className="stack">
      {stages.length > 0 && <Clock stages={stages} today={today} />}
      <div className="grid-2">
        <Card title={r ? "The board's decision" : "Record the board's decision"}>
          <p className="muted">What the board decided about the next term, with its agent. jason records the decision; it buys, renews, cancels, and claims nothing. A change in coverage calls for notice to the members (CIV 5810).</p>
          <div className="fields">
            <label>Decision <select value={decision} onChange={(e) => setDecision(e.target.value)}><option value="">—</option>{decisions.map((d) => <option key={d} value={d}>{d}</option>)}</select></label>
            <label>Decided on <input type="date" value={decidedOn} onChange={(e) => setDecidedOn(e.target.value)} /></label>
            <label>Premium quoted ($, optional) <input inputMode="decimal" value={premium} onChange={(e) => setPremium(e.target.value)} /></label>
            <label>Recorded by <input value={by} onChange={(e) => setBy(e.target.value)} /></label>
            <label className="check"><input type="checkbox" checked={limitsChanged} onChange={(e) => setLimitsChanged(e.target.checked)} /> Coverage changes (limits, deductible, or a lapse)</label>
            <label className="wide">Note <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          {decision && by.trim() && premiumOk && changed && (
            <Confirm busy={busy} onConfirm={save} summary={<p>Record for {label(p)} <code>{p.number}</code>: <strong>{decision}</strong>, decided {decidedOn}{premiumCents != null && <>, premium <Money cents={premiumCents} /></>}{limitsChanged && ", coverage changes (members to be notified, CIV 5810)"}, recorded by {by}. Nothing is bought or sent.</p>}>Record the decision</Confirm>
          )}
          {!premiumOk && <p className="notice notice-error">The premium is a dollar amount.</p>}
          {error && <p className="notice notice-error">{error}</p>}
        </Card>
        <Card title="On the record">
          {r ? <Recorded d={r} /> : <p className="muted">No decision recorded for this policy.</p>}
          <Findings items={p.findings} empty="the review flags nothing" />
        </Card>
      </div>
    </div>
  );
}

const cols: Column<Row>[] = [
  { key: "kind", header: "Policy", render: label },
  { key: "number", header: "Number" },
  { key: "carrier", header: "Carrier" },
  { key: "standing", header: "Standing", render: (r) => <Pill word={r.standing} /> },
  { key: "termEnd", header: "Term ends", render: (r) => <>{<DueDate iso={r.termEnd} />}{r.renewalWindow && <> <Badge tone="warn">renewal window</Badge></>}</>, value: (r) => r.termEnd ?? "9999" },
  { key: "decision", header: "Board's decision", value: (r) => r.renewal?.decision ?? "",
    render: (r) => r.renewal ? <><Pill word={r.renewal.decision} /> <span className="muted">{r.renewal.decidedOn}</span>{r.renewal.premiumCents != null && <> <Money cents={r.renewal.premiumCents} /></>}</> : <Badge tone={r.renewalWindow ? "warn" : "neutral"}>{r.renewalWindow ? "decision needed" : "none recorded"}</Badge> },
  { key: "notice", header: "Members", value: (r) => (r.memberNoticeNeeded ? 1 : 0), render: (r) => r.memberNoticeNeeded ? <Badge tone="warn">notice needed (5810)</Badge> : <span className="muted">—</span> },
];

/** Each policy as the review reads it, with the board's renewal decision recorded once beside it. */
export function InsuranceRenewalsView() {
  const r = useApi<Renewals>("/api/insurance-renewals");
  const [open, setOpen] = useState("");
  const [patched, setPatched] = useState<Record<string, Row>>({});
  const today = new Date();
  return (
    <RemoteView r={r}>
      {(d) => {
        const rows = d.policies.map((p) => patched[p.key] ?? p);
        const current = rows.find((p) => p.key === open);
        const inWindow = rows.filter((p) => p.renewalWindow && !p.renewal).length;
        return (
          <div className="stack">
            <Card title={`Policies as of ${d.asOf}`} actions={<span className="muted">{inWindow ? `${inWindow} in the ${d.windowDays}-day window without a decision` : "every term in the window has a decision"}</span>}>
              <DataTable rows={rows} searchable={false} columns={[...cols, { key: "open", header: "", render: (p) => <button className={open === p.key ? "" : "primary"} onClick={() => setOpen(open === p.key ? "" : p.key)}>{open === p.key ? "Close" : "Open"}</button> }]} />
            </Card>
            {current && <RenewalPanel key={current.key + (current.renewal?.recorded ?? "")} p={current} decisions={d.decisions} today={today} onSaved={(n) => setPatched((x) => ({ ...x, [n.key]: n }))} />}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
