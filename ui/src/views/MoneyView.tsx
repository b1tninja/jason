import { useState } from "react";
import { Badge, Card, Caveats, DataTable, Doc, Findings, Money, Pill, RemoteView, Stat, Tabs, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { Account, Budget, CollectionRow, Collections, Invoices, Payment, PaymentDocument, Reconciliations, Side } from "./types";

const side = (v: Side | number | undefined) => (typeof v === "object" && v ? v : undefined);

function BudgetView() {
  const r = useApi<Budget>("/api/budget");
  const gapCols: Column<Budget["expenseGaps"][number]>[] = [
    { key: "name", header: "Category" },
    { key: "budgeted", header: "Budget", align: "right", render: (x) => <Money cents={x.budgeted} /> },
    { key: "actual", header: "Actual", align: "right", render: (x) => <Money cents={x.actual} /> },
    { key: "gap", header: "Gap", align: "right", render: (x) => <Money cents={x.gap} />, value: (x) => Math.abs(x.gap) },
  ];
  return (
    <RemoteView r={r}>
      {(d) => {
        const rev = side(d.yearToDate.revenue), exp = side(d.yearToDate.expense), net = side(d.yearToDate.net);
        return (
          <div className="stack">
            <div className="stats">
              {rev && <Stat label="Revenue YTD" value={<Money cents={rev.actual ?? 0} />} hint={`budget ${((rev.budget ?? rev.budgeted ?? 0) / 100).toLocaleString("en-US", { style: "currency", currency: "USD" })}`} />}
              {exp && <Stat label="Expense YTD" value={<Money cents={exp.actual ?? 0} />} hint={`budget ${((exp.budget ?? exp.budgeted ?? 0) / 100).toLocaleString("en-US", { style: "currency", currency: "USD" })}`} />}
              {net && <Stat label="Net YTD" value={<Money cents={net.actual ?? 0} />} />}
              {d.reserveTotalCents != null && <Stat label="Reserves" value={<Money cents={d.reserveTotalCents} />} hint="Plaid balance; can lag the bank" />}
            </div>
            <div className="grid-2">
              <Card title="Expense furthest from budget"><DataTable rows={d.expenseGaps} columns={gapCols} searchable={false} /></Card>
              <Card title="Revenue furthest from budget"><DataTable rows={d.revenueGaps} columns={gapCols} searchable={false} /></Card>
            </div>
            <Card title={`Accounts (${d.year}${d.throughMonth ? ` through ${d.throughMonth}` : ""})`}>
              <DataTable rows={d.accounts} columns={[
                { key: "label", header: "Account", value: (a) => a.label ?? a.name ?? "" },
                { key: "purpose", header: "Purpose", render: (a) => <Badge>{a.purpose ?? ""}</Badge> },
                { key: "balance_cents", header: "Balance", align: "right", render: (a) => a.balance_cents == null ? <span className="muted">n/a</span> : <Money cents={a.balance_cents} /> },
              ]} searchable={false} />
            </Card>
            <Caveats items={[d.note ?? ""].filter(Boolean)} />
          </div>
        );
      }}
    </RemoteView>
  );
}

function ReconciliationsView() {
  const r = useApi<Reconciliations>("/api/reconciliations");
  const itemCols: Column<Account["openItems"][number]>[] = [
    { key: "date", header: "Date" },
    { key: "kind", header: "Kind" },
    { key: "description", header: "Description" },
    { key: "amount", header: "Amount", align: "right", value: (x) => x.lineCents ?? x.amount ?? 0, render: (x) => <Money cents={x.lineCents ?? x.amount ?? 0} /> },
    { key: "ageDays", header: "Age (days)", align: "right" },
    { key: "reason", header: "Likely reason (a lead)", render: (x) => x.reason ? <Badge tone="warn">{x.reason}</Badge> : <span className="muted">—</span> },
  ];
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          {d.accounts.map((a) => (
            <Card key={a.account} title={`${a.account}${a.last4 ? ` …${a.last4}` : ""}`} actions={<span className="muted">reconciled through {a.latest ?? a.reconciled ?? "?"}</span>}>
              <div className="stats">
                {a.latestEndingCents != null && <Stat label="Statement ending" value={<Money cents={a.latestEndingCents} />} />}
                {a.registerBalanceCents != null && <Stat label="Register" value={<Money cents={a.registerBalanceCents} />} />}
                <Stat label="Open items" value={a.openItems.length} />
                <Stat label="Months with no reconciliation" value={a.gaps.length} hint={a.gaps.slice(0, 6).join(", ")} />
              </div>
              {a.ledgerMismatches.length > 0 && (
                <Findings items={a.ledgerMismatches.filter((m) => !m.explained).map((m) => `${m.end}: statement differs from ledger by ${(m.differenceCents / 100).toFixed(2)}`)} empty="statement and ledger agree" />
              )}
              <DataTable rows={a.openItems} columns={itemCols} />
            </Card>
          ))}
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

/** One attachment: jason's copy as a `Doc` chip (opening it is a logged view), else its filename as PayHOA gives it
 * (no copy on disk to open). */
function Attachment({ x }: { x: PaymentDocument }) {
  return x.doc ? <Doc doc={x.doc} /> : <code className="chip" title="No copy on disk">{x.filename}</code>;
}

function InvoicesView() {
  const r = useApi<Invoices>("/api/invoices");
  const cols: Column<Payment>[] = [
    { key: "date", header: "Date" },
    { key: "payee", header: "Payee" },
    { key: "amountCents", header: "Amount", align: "right", render: (p) => <Money cents={p.amountCents} /> },
    { key: "categories", header: "Category", value: (p) => p.categories.join(", ") },
    { key: "documents", header: "Attached", value: (p) => p.documents.length, render: (p) => p.documents.length ? <span className="row wrap">{p.documents.map((x, i) => <Attachment key={i} x={x} />)}</span> : <Badge tone="bad">none</Badge> },
    { key: "findings", header: "Questions", render: (p) => <Findings items={p.findings} ok={p.ok} />, value: (p) => p.findings.length },
  ];
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title="Payments with questions" actions={<span className="row wrap">{Object.entries(d.summary).map(([k, n]) => <span key={k}><Badge tone="warn">{k}</Badge> {n}</span>)}</span>}>
            <p className="muted">Each finding is a question for the treasurer: re-attach, re-categorize, or recover. "Paid twice" is confirmed only by a next-bill credit or two debits at the bank.</p>
            <DataTable rows={d.payments} columns={cols} />
            {d.more && <p className="muted">{d.more}</p>}
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

function CollectionsView() {
  const r = useApi<Collections>("/api/collections");
  const cols: Column<CollectionRow>[] = [
    { key: "standing", header: "Standing", render: (x) => <Pill word={x.standing} meaning={x.meaning} /> },
    { key: "address", header: "Unit" },
    { key: "pastDueCents", header: "Past due", align: "right", render: (x) => <Money cents={x.pastDueCents} /> },
    { key: "balanceCents", header: "Balance", align: "right", render: (x) => <Money cents={x.balanceCents} /> },
    { key: "lien", header: "Lien", value: (x) => x.lien ?? "", render: (x) => x.lien ? <>{x.lien} <span className="muted">{x.lienStatus} {x.lienDays != null && `· ${x.lienDays}d`}</span></> : <span className="muted">—</span> },
    { key: "nextStep", header: "Next step (the board's)" },
  ];
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title="Delinquent accounts" actions={<Stat label="past due" value={<Money cents={d.pastDueCents} />} />}>
            <p className="notice notice-warn">Executive session (CIV 4935). jason records nothing here and never submits an account to a collection agency, records a lien, or starts a foreclosure.</p>
            <DataTable rows={d.rows} columns={cols} />
            {d.rows.some((x) => x.floorQuestion) && <Findings items={d.rows.filter((x) => x.floorQuestion).map((x) => `${x.address}: ${x.floorQuestion}`)} />}
          </Card>
          <Caveats items={[d.note ?? ""].filter(Boolean)} />
        </div>
      )}
    </RemoteView>
  );
}

/** The monthly review (CIV 5500): budget against actual, the bank reconciliations, the payments with questions, and the delinquencies. */
export function MoneyView() {
  const [tab, setTab] = useState("budget");
  return (
    <Tabs active={tab} onChange={setTab} tabs={[
      { id: "budget", label: "Budget vs actual", content: <BudgetView /> },
      { id: "reconciliations", label: "Reconciliations", content: <ReconciliationsView /> },
      { id: "invoices", label: "Invoice review", content: <InvoicesView /> },
      { id: "collections", label: "Collections", content: <CollectionsView /> },
    ]} />
  );
}
