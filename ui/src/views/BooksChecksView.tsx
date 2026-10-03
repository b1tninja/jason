import { useState, type ReactNode } from "react";
import { Badge, Card, Caveats, DataTable, Findings, Money, RemoteView, Stat, Tabs, type Column } from "../components";
import { useApi } from "../lib/useApi";
import "./books-checks.css";

interface UtilityDocument { filename: string; kind?: string }
interface UtilityPayment {
  key: string;
  date: string;
  amountCents: number;
  payee: string;
  description: string;
  categories: string[];
  documents: UtilityDocument[];
  findings: string[];
  ok: boolean;
  utility?: string;
}
interface UtilityPayments {
  found: boolean;
  note?: string;
  transactionsSyncedAt?: string;
  summary?: Record<string, number>;
  payments?: UtilityPayment[];
  caveats?: string[];
}

interface LedgerRun { id: string | number; name: string; period: string; completedAt?: string | null; pages?: number | null; libraryCopies: string[]; notes?: string[] | string | null }
interface RunMissing { name: string; period: string }
interface LibraryCopy { path: string; period: string }
interface BalanceChange { period: string; periodFrom: string; path: string; account: string; printedCents: number; ledgerCents: number; asOf: string; matchesPeriods?: string[] }
interface DroppedAccount { period: string; account: string; printedCents: number; path: string }
interface LatestSheet { period: string; asOf?: string; lastUpdated?: string | null; accounts?: { label: string; section: string; cents: number }[] }
interface LedgerValidation {
  found: boolean;
  note?: string;
  runs?: LedgerRun[];
  runsMissingFromLibrary?: RunMissing[];
  libraryCopiesNotFromARun?: LibraryCopy[];
  balanceChanges?: BalanceChange[];
  copiesUnderAnotherMonth?: BalanceChange[];
  accountsTheLedgerDropped?: DroppedAccount[];
  balancesChecked?: number;
  latestSheet?: LatestSheet | null;
  caveats?: string[];
}

const notesOf = (n: LedgerRun["notes"]): string[] => (Array.isArray(n) ? n : n ? [n] : []);
const baseName = (p: string) => p.split("/").pop() ?? p;

function UtilityPaymentsView() {
  const r = useApi<UtilityPayments>("/api/utility-payments");
  const cols: Column<UtilityPayment>[] = [
    { key: "date", header: "Date" },
    { key: "payee", header: "Payee", value: (p) => `${p.payee} ${p.utility ?? ""}`, render: (p) => <>{p.payee}{p.utility && <> <Badge>{p.utility}</Badge></>}</> },
    { key: "amountCents", header: "Amount", align: "right", render: (p) => <Money cents={p.amountCents} /> },
    { key: "categories", header: "Category", value: (p) => (p.categories ?? []).join(", ") },
    { key: "documents", header: "Attached", value: (p) => (p.documents ?? []).length, render: (p) => (p.documents ?? []).length ? <span className="row wrap books-chips">{p.documents.map((x, i) => <code key={i} className="chip" title={x.kind}>{x.filename}</code>)}</span> : <Badge tone="bad">none</Badge> },
    { key: "findings", header: "Questions", render: (p) => <Findings items={p.findings} ok={p.ok} />, value: (p) => (p.findings ?? []).length },
  ];
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title="Utility payments" actions={<span className="row wrap">{Object.entries(d.summary ?? {}).map(([k, n]) => <span key={k}><Badge tone="warn">{k}</Badge> {n}</span>)}</span>}>
            <p className="muted">Each finding is a question for the treasurer: re-attach the bill, re-categorize, or ask the utility. jason changes nothing in PayHOA.{d.transactionsSyncedAt && <> Transactions as synced {d.transactionsSyncedAt}.</>}</p>
            <DataTable rows={d.payments ?? []} columns={cols} />
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

/** One checklist item: its count in the title, green "none" when empty, the table otherwise. */
function Check({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <Card title={`${title} (${count})`} actions={count === 0 ? <Badge tone="good">none</Badge> : <span className="books-count books-count-bad">{count}</span>}>
      {count === 0 ? <p className="muted books-none">Nothing to check here.</p> : children}
    </Card>
  );
}

function LedgerValidationView() {
  const r = useApi<LedgerValidation>("/api/ledger-validation");
  const runCols: Column<LedgerRun>[] = [
    { key: "period", header: "Period" },
    { key: "name", header: "Run" },
    { key: "completedAt", header: "Completed", value: (x) => x.completedAt ?? "" },
    { key: "pages", header: "Pages", align: "right", value: (x) => x.pages ?? 0 },
    { key: "libraryCopies", header: "Library copies", value: (x) => (x.libraryCopies ?? []).length, render: (x) => (x.libraryCopies ?? []).length ? <span className="row wrap books-chips">{x.libraryCopies.map((p, i) => <code key={i} className="chip" title={p}>{baseName(p)}</code>)}</span> : <Badge tone="bad">none</Badge> },
    { key: "notes", header: "Notes", value: (x) => notesOf(x.notes).join("; "), render: (x) => <Findings items={notesOf(x.notes)} empty="—" /> },
  ];
  const changeCols: Column<BalanceChange>[] = [
    { key: "period", header: "Period", render: (x) => <>{x.period} <span className="muted">from {x.periodFrom}</span></> },
    { key: "account", header: "Account" },
    { key: "printedCents", header: "Printed", align: "right", render: (x) => <Money cents={x.printedCents} /> },
    { key: "ledgerCents", header: "Ledger today", align: "right", render: (x) => <Money cents={x.ledgerCents} /> },
    { key: "difference", header: "Difference", align: "right", value: (x) => x.ledgerCents - x.printedCents, render: (x) => <Money cents={x.ledgerCents - x.printedCents} /> },
    { key: "asOf", header: "As of" },
    { key: "path", header: "Copy", render: (x) => <code className="chip" title={x.path}>{baseName(x.path)}</code> },
  ];
  const misfiledCols: Column<BalanceChange>[] = [
    ...changeCols.slice(0, 4),
    { key: "matchesPeriods", header: "Balance matches", value: (x) => (x.matchesPeriods ?? []).join(", "), render: (x) => <span className="row wrap">{(x.matchesPeriods ?? []).map((p) => <Badge key={p} tone="warn">{p}</Badge>)}</span> },
    changeCols[6],
  ];
  const droppedCols: Column<DroppedAccount>[] = [
    { key: "period", header: "Period" },
    { key: "account", header: "Account" },
    { key: "printedCents", header: "Printed", align: "right", render: (x) => <Money cents={x.printedCents} /> },
    { key: "path", header: "Copy", render: (x) => <code className="chip" title={x.path}>{baseName(x.path)}</code> },
  ];
  return (
    <RemoteView r={r}>
      {(d) => {
        const runs = d.runs ?? [], missing = d.runsMissingFromLibrary ?? [], altered = d.libraryCopiesNotFromARun ?? [];
        const changes = d.balanceChanges ?? [], misfiled = d.copiesUnderAnotherMonth ?? [], dropped = d.accountsTheLedgerDropped ?? [];
        const latest = d.latestSheet;
        return (
          <div className="stack books-checklist">
            <div className="stats">
              <Stat label="Treasurer's runs" value={runs.length} />
              <Stat label="Balances checked" value={d.balancesChecked ?? 0} hint="printed against the ledger as of the same month end" />
              {latest && <Stat label="Latest balance sheet" value={latest.period} hint={latest.asOf ? `as of ${latest.asOf}` : undefined} />}
            </div>
            <p className="muted">A checklist for the treasurer. Each card is a question the library and the ledger raise together; jason changes nothing in PayHOA or the library.</p>
            <Check title="Runs with no identical copy in the library" count={missing.length}>
              <DataTable rows={missing} columns={[{ key: "period", header: "Period" }, { key: "name", header: "Run" }]} searchable={false} />
            </Check>
            <Check title="Library copies that are not a run as generated" count={altered.length}>
              <DataTable rows={altered} columns={[{ key: "period", header: "Period" }, { key: "path", header: "Copy", render: (x) => <code className="chip" title={x.path}>{baseName(x.path)}</code> }]} />
            </Check>
            <Check title="Printed balances that differ from the ledger today" count={changes.length}>
              <DataTable rows={changes} columns={changeCols} />
            </Check>
            <Check title="Copies filed under another month" count={misfiled.length}>
              <DataTable rows={misfiled} columns={misfiledCols} />
            </Check>
            <Check title="Accounts a report printed that the ledger dropped" count={dropped.length}>
              <DataTable rows={dropped} columns={droppedCols} />
            </Check>
            <Card title={`Treasurer's report runs (${runs.length})`}>
              <DataTable rows={runs} columns={runCols} />
            </Card>
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}

/** The books checks: utility payments with their questions, and the library's treasurer's reports against PayHOA's runs and today's ledger. */
export function BooksChecksView() {
  const [tab, setTab] = useState("utilities");
  return (
    <Tabs active={tab} onChange={setTab} tabs={[
      { id: "utilities", label: "Utility payments", content: <UtilityPaymentsView /> },
      { id: "ledger", label: "Ledger validation", content: <LedgerValidationView /> },
    ]} />
  );
}
