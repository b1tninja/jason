import { Badge, Card, Caveats, DataTable, Doc, DueDate, Findings, Money, RemoteView, Stat, type Audience, type Column, type DocRef } from "../components";
import { useApi } from "../lib/useApi";
import type { Borrowing, Move, Reserves } from "./types";

/** One line of the 5515 record: met or not, and the library's document that shows it, as a `Doc` chip to open. */
function Tick({ ok, label, doc }: { ok: boolean; label: string; doc?: DocRef }) {
  return (
    <li className="tick">
      <Badge tone={ok ? "good" : "bad"}>{ok ? "✓" : "✗"}</Badge> {label}{doc && <> <Doc doc={doc} /></>}
    </li>
  );
}

/** One borrowing from the reserve and its Civil Code 5515 record. Whether the statute was met is the board's call. */
export function BorrowingCard({ b }: { b: Borrowing }) {
  const d = b.documents;
  return (
    <article className="item" data-priority={b.gaps.length ? "high" : "normal"}>
      <header className="row wrap">
        <strong>{b.day}</strong> <Money cents={b.cents} /> <span className="muted">from {b.account}</span>
        {b.number && <code className="chip">tx {b.number}</code>}
        <Badge tone={b.outstandingCents ? "warn" : "good"}>{b.outstandingCents ? "outstanding" : "restored"}</Badge>
      </header>
      {b.memo && <p className="muted">{b.memo}</p>}
      <div className="grid-2">
        <ul className="ticks">
          <Tick ok={!!d.notice} label="Notice of intent to borrow on an agenda (5515(a))" doc={d.notice?.doc} />
          <Tick ok={!!d.minutes && !d.minutes.draft} label={d.minutes?.draft ? "Minutes with the finding (5515(c)): DRAFT only" : "Minutes with the finding (5515(c))"} doc={d.minutes?.doc} />
          <Tick ok={!!d.resolution} label="Resolution authorizing it" doc={d.resolution?.doc} />
          <Tick ok={!b.outstandingCents} label="Restored to the reserve within a year (5515(d))" />
        </ul>
        <div className="stats">
          <Stat label="Restore by" value={<DueDate iso={b.deadline} />} />
          <Stat label="Repaid" value={<Money cents={b.repaidCents} />} hint={b.repaidOn ? `on ${b.repaidOn}${b.exactRepayment ? ", exact" : ""}` : "no transfer back"} />
          <Stat label="Outstanding" value={<Money cents={b.outstandingCents} />} />
        </div>
      </div>
      <Findings items={b.gaps} empty="the record is complete" />
    </article>
  );
}

const moveCols: Column<Move>[] = [
  { key: "day", header: "Date" },
  { key: "cents", header: "Amount", align: "right", render: (m) => <Money cents={m.cents} /> },
  { key: "account", header: "Account" },
  { key: "purpose", header: "Purpose", render: (m) => <Badge>{m.purpose}</Badge> },
  { key: "memo", header: "Memo", value: (m) => m.memo || m.description },
];

interface ReserveSummary {
  fiscalYear?: number | null; preparer?: string; prepared?: string | null; level?: string | null;
  beginningBalanceCents?: number | null; annualContributionCents?: number | null; requiredEndOfYearCents?: number | null;
  projectedEndOfYearCents?: number | null; percentFunded?: number | null; sufficientFor30Years?: boolean | null; components?: number;
}
export interface OwnerReservesData {
  found?: boolean; note?: string; summary: ReserveSummary | null;
  years: { fiscalYear?: number | null; percentFunded?: number | null; projectedEndOfYearCents?: number | null; requiredEndOfYearCents?: number | null }[];
  caveats?: string[];
}

const pct = (v?: number | null) => (v == null ? "—" : `${Math.round(v * 1000) / 10}%`);
const cents = (v?: number | null) => (v == null ? <span className="muted">—</span> : <Money cents={v} />);

/** The owner view of the reserves: the reserve funding summary members receive with the budget report (CIV 5565, 5570),
 * from the latest study (`GET /api/reserves?view=owner`). Not the ledger's transfers, borrowings, or memos: those are
 * the board's, and a member asks for the reserve records through the records request form. */
export function OwnerReserves() {
  const r = useApi<OwnerReservesData>("/api/reserves?view=owner");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          {d.summary && (
            <Card title={`Reserve funding summary${d.summary.fiscalYear ? `, fiscal year ${d.summary.fiscalYear}` : ""}`}>
              <div className="stats">
                <Stat label="Percent funded" value={pct(d.summary.percentFunded)} />
                <Stat label="Projected reserves, year end" value={cents(d.summary.projectedEndOfYearCents)} />
                <Stat label="Fully funded, year end" value={cents(d.summary.requiredEndOfYearCents)} />
                <Stat label="Annual contribution" value={cents(d.summary.annualContributionCents)} />
              </div>
              <p className="muted">{d.summary.preparer ? `Prepared by ${d.summary.preparer}` : "Preparer not read"}{d.summary.prepared ? ` on ${d.summary.prepared}` : ""}.</p>
            </Card>
          )}
          {d.years.length > 1 && (
            <Card title="Over the studies on file">
              <DataTable rows={d.years} searchable={false} rowKey={(y) => String(y.fiscalYear ?? "")} columns={[
                { key: "fiscalYear", header: "Fiscal year", value: (y) => y.fiscalYear ?? 0 },
                { key: "percentFunded", header: "Percent funded", align: "right", value: (y) => y.percentFunded ?? -1, render: (y) => pct(y.percentFunded) },
                { key: "projectedEndOfYearCents", header: "Projected", align: "right", value: (y) => y.projectedEndOfYearCents ?? -1, render: (y) => cents(y.projectedEndOfYearCents) },
                { key: "requiredEndOfYearCents", header: "Fully funded", align: "right", value: (y) => y.requiredEndOfYearCents ?? -1, render: (y) => cents(y.requiredEndOfYearCents) },
              ]} />
            </Card>
          )}
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

/** The reserves: each borrowing's 5515 record, contributions against the budget, and the movements nothing explains,
 * with the latest reserve study as a card. The owner view is `OwnerReserves`, the summary the budget report carries. */
export function ReservesView({ audience = "board" }: { audience?: Audience } = {}) {
  if (audience === "owner") return <OwnerReserves />;
  return <BoardReserves />;
}

function BoardReserves() {
  const r = useApi<Reserves>("/api/reserves");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          {d.study && (
            <Card title="The reserve study">
              <p className="muted">The latest study on disk, the one the funding plan is read from. Its figures are the preparer's estimates; the board adopts the plan.</p>
              <Doc doc={d.study} variant="card" />
            </Card>
          )}
          <Card title={`Borrowings from the reserve (${d.borrowings.length})`} actions={<span className="muted">ledger through {d.ledgerThrough}</span>}>
            <p className="muted">Each card is one loan's 5515 record as the library shows it. A match is a lead; only the board's resolution says which loan a payment restored.</p>
            {d.borrowings.length === 0 && <p className="muted">No borrowing in the ledger.</p>}
            {d.borrowings.map((b) => <BorrowingCard key={`${b.day}-${b.number}`} b={b} />)}
          </Card>
          <Card title="Reserve contributions against the budget">
            <DataTable rows={d.budgetYears} searchable={false} columns={[
              { key: "year", header: "Year" },
              { key: "contributionBudgetCents", header: "Budgeted", align: "right", render: (y) => <Money cents={y.contributionBudgetCents} /> },
              { key: "contributionPaidCents", header: "Paid", align: "right", render: (y) => <Money cents={y.contributionPaidCents} /> },
              { key: "short", header: "Short or late", value: (y) => (y.short?.length ?? 0) + (y.late?.length ?? 0),
                render: (y) => <Findings items={[...(y.short ?? []).map((m) => `${m}: short`), ...(y.late ?? []).map((l) => `${l.month}: ${l.daysLate}d late`)]} empty="on schedule" /> },
            ]} />
          </Card>
          {d.otherWithdrawals.length > 0 && <Card title={`Other withdrawals from the reserve (${d.otherWithdrawals.length})`}><DataTable rows={d.otherWithdrawals} columns={moveCols} /></Card>}
          {d.unappliedContributions.length > 0 && <Card title={`Transfers in that no schedule or loan explains (${d.unappliedContributions.length})`}><DataTable rows={d.unappliedContributions} columns={moveCols} /></Card>}
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
