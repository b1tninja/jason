import { useState } from "react";
import { Badge, Card, Caveats, Clock, Confirm, DataTable, DueDate, Findings, Money, Pill, RemoteView, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import type { Borrowing } from "./types";
import "./findings.css";

export interface ReserveFinding { key: string; finding: string; kind: string; authority: string; madeOn: string; by: string; meeting: string; recorded: string; history: string[] }
type Row = Borrowing & { key: string; finding: ReserveFinding | null; findingNeeded: boolean };
interface Findings_ { found?: boolean; note?: string; ledgerThrough: string; kinds: string[]; needed: number; borrowings: Row[]; caveats?: string[] }

function Doc({ ok, label, hint }: { ok: boolean; label: string; hint?: string }) {
  return <li className="tick" title={hint}><Badge tone={ok ? "good" : "bad"}>{ok ? "✓" : "✗"}</Badge> {label}</li>;
}

/** The recorded finding, as a person entered it: the board's words, the meeting, who recorded them, and when. */
function Recorded({ f }: { f: ReserveFinding }) {
  return (
    <div className="recorded">
      <p><Pill word={f.kind} /> <span className="muted">{f.authority}</span> · meeting of <strong>{f.meeting}</strong></p>
      <blockquote>{f.finding}</blockquote>
      <p className="who">Made {f.madeOn}; recorded {f.recorded.slice(0, 10)} by {f.by}</p>
      {f.history.length > 1 && <ul className="history">{f.history.map((h, i) => <li key={i}>{h}</li>)}</ul>}
    </div>
  );
}

/** One borrowing opened: its 5515 clock and documents, then the board's finding entered once, behind a confirm. */
function FindingPanel({ b, kinds, today, onSaved }: { b: Row; kinds: string[]; today: Date; onSaved: (next: Row) => void }) {
  const f = b.finding;
  const late = !!b.outstandingCents && b.deadline < today.toISOString().slice(0, 10);
  const [finding, setFinding] = useState(f?.finding ?? "");
  const [kind, setKind] = useState(f?.kind ?? (late ? kinds[1] ?? "" : kinds[0] ?? ""));
  const [meeting, setMeeting] = useState(f?.meeting ?? "");
  const [madeOn, setMadeOn] = useState(f?.madeOn ?? today.toISOString().slice(0, 10));
  const [by, setBy] = useState(f?.by ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true); setError("");
    try {
      const saved = await postJson<ReserveFinding>(`/api/write/reserve-findings/${encodeURIComponent(b.key)}`, { finding, kind, madeOn, by, meeting });
      onSaved({ ...b, finding: saved, findingNeeded: false });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const d = b.documents;
  const stages = [
    { key: "borrowed", label: "Borrowed from the reserve", date: b.day, done: true },
    { key: "deadline", label: "Restore by (one year)", date: b.deadline, authority: "CIV 5515(d)", done: !b.outstandingCents },
    ...(f ? [{ key: "finding", label: `Finding in the minutes: ${f.kind}`, date: f.meeting, authority: f.authority, done: true }] : []),
  ];
  const changed = !f || finding !== f.finding || kind !== f.kind || meeting !== f.meeting || madeOn !== f.madeOn;
  return (
    <div className="stack">
      <Clock stages={stages} today={today} />
      <div className="grid-2">
        <Card title={f ? "The board's finding" : "Record the board's finding"}>
          <p className="muted">The written finding in the board's words: at the borrowing, why the transfer is needed and when and how it is repaid (5515(c)); for a late restoration, that the delay is in the association's best interest (5515(d)). jason records it and decides nothing.</p>
          <div className="fields">
            <label className="wide">Finding, as the minutes record it <textarea rows={4} value={finding} onChange={(e) => setFinding(e.target.value)} /></label>
            <label>Which finding <select value={kind} onChange={(e) => setKind(e.target.value)}>{kinds.map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
            <label>Meeting that made it <input type="date" value={meeting} onChange={(e) => setMeeting(e.target.value)} /></label>
            <label>Made on <input type="date" value={madeOn} onChange={(e) => setMadeOn(e.target.value)} /></label>
            <label>Recorded by <input value={by} onChange={(e) => setBy(e.target.value)} /></label>
          </div>
          {finding.trim() && by.trim() && meeting && kind && changed && (
            <Confirm busy={busy} onConfirm={save} summary={<p>Record the {kind} of the meeting of {meeting} on the borrowing of {b.day} (<Money cents={b.cents} />): "{finding.slice(0, 160)}{finding.length > 160 ? "…" : ""}", recorded by {by}. Nothing in PayHOA changes.</p>}>Record the finding</Confirm>
          )}
          {error && <p className="notice notice-error">{error}</p>}
        </Card>
        <Card title="The record as the library shows it">
          <ul className="ticks">
            <Doc ok={!!d.notice} label="Notice of intent to borrow on an agenda (5515(a))" hint={d.notice?.path} />
            <Doc ok={!!d.minutes && !d.minutes.draft} label={d.minutes?.draft ? "Minutes with the finding (5515(c)): DRAFT only" : "Minutes with the finding (5515(c))"} hint={d.minutes?.path} />
            <Doc ok={!!d.resolution} label="Resolution authorizing it" hint={d.resolution?.path} />
            <Doc ok={!b.outstandingCents} label="Restored to the reserve within a year (5515(d))" />
          </ul>
          <Findings items={b.gaps} empty="the record is complete" />
          {f ? <Recorded f={f} /> : <p className="muted">No finding recorded here.</p>}
        </Card>
      </div>
    </div>
  );
}

const cols: Column<Row>[] = [
  { key: "day", header: "Borrowed" },
  { key: "cents", header: "Amount", align: "right", render: (b) => <Money cents={b.cents} /> },
  { key: "account", header: "From", render: (b) => <>{b.account}{b.number && <> <code className="chip">tx {b.number}</code></>}</> },
  { key: "deadline", header: "Restore by", render: (b) => b.outstandingCents ? <DueDate iso={b.deadline} /> : <><time dateTime={b.deadline}>{b.deadline}</time> <Badge tone="good">restored</Badge></> },
  { key: "outstandingCents", header: "Outstanding", align: "right", render: (b) => <Money cents={b.outstandingCents} /> },
  { key: "gaps", header: "Gaps", value: (b) => b.gaps.length, render: (b) => <Findings items={b.gaps} empty="complete" /> },
  { key: "finding", header: "Board's finding", value: (b) => (b.finding ? 2 : b.findingNeeded ? 1 : 0),
    render: (b) => b.finding ? <><Pill word={b.finding.kind} /> <span className="muted">meeting {b.finding.meeting}</span></> : b.findingNeeded ? <Badge tone="warn">finding needed</Badge> : <span className="muted">none recorded</span> },
];

/** Each borrowing from the reserve as the ledger and library show it, with the board's 5515 finding recorded once beside it. */
export function ReserveFindingsView() {
  const r = useApi<Findings_>("/api/reserve-findings");
  const [open, setOpen] = useState("");
  const [patched, setPatched] = useState<Record<string, Row>>({});
  const today = new Date();
  return (
    <RemoteView r={r}>
      {(d) => {
        const rows = [...d.borrowings].map((b) => patched[b.key] ?? b).sort((a, b) => b.day.localeCompare(a.day));
        const current = rows.find((b) => b.key === open);
        const needed = rows.filter((b) => b.findingNeeded).length;
        return (
          <div className="stack">
            <Card title={`Borrowings from the reserve (${rows.length})`} actions={<span className="muted">ledger through {d.ledgerThrough}{needed ? ` · ${needed} finding${needed === 1 ? "" : "s"} needed` : ""}</span>}>
              <p className="muted">A borrowing whose library record lacks the finding, with none recorded here, is flagged. The flag is a lead; the board's minutes are the record.</p>
              {rows.length === 0 && <p className="muted">No borrowing in the ledger.</p>}
              <DataTable rows={rows} searchable={false} columns={[...cols, { key: "open", header: "", render: (b) => <button className={open === b.key ? "" : "primary"} onClick={() => setOpen(open === b.key ? "" : b.key)}>{open === b.key ? "Close" : "Open"}</button> }]} />
            </Card>
            {current && <FindingPanel key={current.key + (current.finding?.recorded ?? "")} b={current} kinds={d.kinds} today={today} onSaved={(n) => setPatched((x) => ({ ...x, [n.key]: n }))} />}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
