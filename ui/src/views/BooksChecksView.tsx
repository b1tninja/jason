import { useState, type ReactNode } from "react";
import { Badge, Card, Caveats, DataTable, Doc, Findings, Money, RemoteView, Stat, Tabs, type Column, type DocRef } from "../components";
import { useApi } from "../lib/useApi";
import "./books-checks.css";

/** An attachment as the utility audit gives it (`jason utilities --payments`): its filename, what it was read as, and
 * `doc`, the reference to jason's copy when it keeps one. */
interface UtilityAttachment { id?: number; filename: string; kind?: string; doc?: DocRef }
/** One utility payment as the audit gives it: the provider, its rows' categories, and its attachments. */
interface UtilityPayment {
  key: string | number;
  date: string;
  amountCents: number;
  provider: string;
  rows?: { txId?: number; category: string; amountCents?: number }[];
  attachments?: UtilityAttachment[];
  split?: string;
  findings: string[];
  ok: boolean;
}
interface UtilityPayments {
  found: boolean;
  note?: string;
  transactionsSyncedAt?: string;
  summary?: Record<string, number>;
  payments?: UtilityPayment[];
  caveats?: string[];
}

/** A treasurer's report run: its library copies by path, and `libraryDocs`, each copy's reference. */
interface LedgerRun { id: string | number; name: string; period: string; completedAt?: string | null; pages?: number | null; libraryCopies: string[]; libraryDocs?: DocRef[]; notes?: string[] | string | null }
interface RunMissing { name: string; period: string }
/** A checklist row names its library copy by path, with `doc`, its reference. */
interface LibraryCopy { path: string; period: string; doc?: DocRef }
interface BalanceChange { period: string; periodFrom: string; path: string; account: string; printedCents: number; ledgerCents: number; asOf: string; matchesPeriods?: string[]; doc?: DocRef }
interface DroppedAccount { period: string; account: string; printedCents: number; path: string; doc?: DocRef }
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
const categoriesOf = (p: UtilityPayment) => [...new Set((p.rows ?? []).map((r) => r.category).filter(Boolean))];

/** A document the loader names: its reference as a `Doc` chip (opening it is a logged view), else the name it gives,
 * with why nothing opens. */
function DocOrName({ doc, name, why }: { doc?: DocRef; name: string; why: string }) {
  return doc ? <Doc doc={doc} /> : <code className="chip" title={why}>{name}</code>;
}

/** A checklist row's library copy. */
function CopyChip({ x }: { x: { path: string; doc?: DocRef } }) {
  return <DocOrName doc={x.doc} name={baseName(x.path)} why="The library no longer holds this copy" />;
}

function UtilityPaymentsView() {
  const r = useApi<UtilityPayments>("/api/utility-payments");
  const cols: Column<UtilityPayment>[] = [
    { key: "date", header: "Date" },
    { key: "provider", header: "Utility", render: (p) => <Badge>{p.provider}</Badge> },
    { key: "amountCents", header: "Amount", align: "right", render: (p) => <Money cents={p.amountCents} /> },
    { key: "categories", header: "Category", value: (p) => categoriesOf(p).join(", ") },
    { key: "attachments", header: "Attached", value: (p) => (p.attachments ?? []).length, render: (p) => (p.attachments ?? []).length
      ? <span className="row wrap books-chips">{(p.attachments ?? []).map((x, i) => <DocOrName key={i} doc={x.doc} name={x.filename} why={`${x.kind ? `${x.kind}; ` : ""}no copy on disk to open`} />)}</span>
      : <Badge tone="bad">none</Badge> },
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
    { key: "libraryCopies", header: "Library copies", value: (x) => (x.libraryCopies ?? []).length, render: (x) => (x.libraryCopies ?? []).length ? <span className="row wrap books-chips">{x.libraryCopies.map((p, i) => <DocOrName key={i} doc={x.libraryDocs?.length === x.libraryCopies.length ? x.libraryDocs[i] : undefined} name={baseName(p)} why="The library no longer holds this copy" />)}</span> : <Badge tone="bad">none</Badge> },
    { key: "notes", header: "Notes", value: (x) => notesOf(x.notes).join("; "), render: (x) => <Findings items={notesOf(x.notes)} empty="—" /> },
  ];
  const changeCols: Column<BalanceChange>[] = [
    { key: "period", header: "Period", render: (x) => <>{x.period} <span className="muted">from {x.periodFrom}</span></> },
    { key: "account", header: "Account" },
    { key: "printedCents", header: "Printed", align: "right", render: (x) => <Money cents={x.printedCents} /> },
    { key: "ledgerCents", header: "Ledger today", align: "right", render: (x) => <Money cents={x.ledgerCents} /> },
    { key: "difference", header: "Difference", align: "right", value: (x) => x.ledgerCents - x.printedCents, render: (x) => <Money cents={x.ledgerCents - x.printedCents} /> },
    { key: "asOf", header: "As of" },
    { key: "path", header: "Copy", value: (x) => baseName(x.path), render: (x) => <CopyChip x={x} /> },
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
    { key: "path", header: "Copy", value: (x) => baseName(x.path), render: (x) => <CopyChip x={x} /> },
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
              <DataTable rows={altered} columns={[{ key: "period", header: "Period" }, { key: "path", header: "Copy", value: (x) => baseName(x.path), render: (x) => <CopyChip x={x} /> }]} />
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
