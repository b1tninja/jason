import { useState } from "react";
import { Badge, Card, Caveats, DataTable, Money, Pill, RemoteView, Stat, Tabs, Timeline, type Column, type TimelineEvent } from "../components";
import { useApi } from "../lib/useApi";
import "./legal.css";

// Shapes of GET /api/legal-cases (mcp.county.legal_cases) and GET /api/audit-chains (mcp.county.audit_chains).

export interface CaseEvent { day: string; step: string; source?: string }
export interface CaseDuty { statute: string; requirement: string; met: boolean | null; due?: string | null; applies?: boolean; evidence?: string }
export interface SettledItem { section: string; title: string; scope: string; hard_cents?: number | null; standing?: string; work?: string }
export interface LegalCase {
  key: string;
  title: string;
  forum: string;
  role: string;
  status: string;
  court?: string;
  case_number?: string;
  opposing?: string[];
  counsel?: string[];
  insurer_claims?: string[];
  buildings?: number[];
  events: CaseEvent[];
  gross_cents?: number | null;
  fees_cents?: number | null;
  net_cents?: number | null;
  proceeds_account?: string;
  duties: CaseDuty[];
  board_item?: string;
  confidential?: boolean;
  settled_items?: SettledItem[];
  settled_source?: string;
}
export interface OpenDuty { case: string; statute: string; requirement: string; met: boolean | null }
export interface LegalCases { found: boolean; cases: LegalCase[]; openDuties: OpenDuty[]; caveats?: string[]; note?: string }

export interface ChainFinding { check: string; detail: string; number?: string | null; year?: number | null }
export interface Parcel { apn: string; phase?: number | string | null; steps: number; reassessing?: Record<string, string | number>; findings: ChainFinding[] }
export interface AuditChains { found?: boolean; checked: number; clean: number; restorationYears?: number[]; parcels: Parcel[]; note?: string }

/** Whether the record shows a duty met. `null` is "not shown": the record is silent, not a failure. */
export function MetPill({ met }: { met: boolean | null | undefined }) {
  if (met === true) return <Pill word="met" meaning="the record shows it done" />;
  if (met === false) return <Pill word="not met" meaning="the record shows it was not done" />;
  return <Pill word="not shown" meaning="the record does not show it either way; it may be met in records jason does not hold" />;
}

const openDutyCols: Column<OpenDuty>[] = [
  { key: "case", header: "Case" },
  { key: "statute", header: "Statute" },
  { key: "requirement", header: "Requirement" },
  { key: "met", header: "Met", render: (d) => <MetPill met={d.met} />, value: (d) => d.met === true ? "met" : d.met === false ? "not met" : "not shown" },
];

const dutyCols: Column<CaseDuty>[] = [
  { key: "statute", header: "Statute" },
  { key: "requirement", header: "Requirement" },
  { key: "due", header: "Due", value: (d) => d.due ?? "" },
  { key: "met", header: "Met", render: (d) => <MetPill met={d.met} />, value: (d) => d.met === true ? "met" : d.met === false ? "not met" : "not shown" },
];

/** One matter: its forum, standing, money, events, and the duties that apply to it. Names only what the JSON gives. */
export function CaseCard({ c }: { c: LegalCase }) {
  const duties = c.duties.filter((d) => d.applies !== false);
  const events: TimelineEvent[] = c.events.map((e, i) => ({ id: `${c.key}-${i}`, date: e.day, title: e.step, detail: e.source || undefined }));
  const hasMoney = c.gross_cents != null || c.fees_cents != null || c.net_cents != null;
  return (
    <Card title={c.title} actions={<span className="row wrap"><Pill word={c.status} />{c.confidential !== false && <Badge tone="warn">confidential</Badge>}</span>}>
      <article className="legal-case" data-case={c.key}>
        <dl className="kv">
          <dt>Forum</dt><dd>{c.forum}</dd>
          <dt>Role</dt><dd>{c.role}</dd>
          {c.court && <><dt>Court</dt><dd>{c.court}</dd></>}
          {c.case_number && <><dt>Number</dt><dd><code className="chip">{c.case_number}</code></dd></>}
          {!!c.opposing?.length && <><dt>Opposing</dt><dd>{c.opposing.join("; ")}</dd></>}
          {!!c.counsel?.length && <><dt>Counsel</dt><dd>{c.counsel.join("; ")}</dd></>}
          {!!c.insurer_claims?.length && <><dt>Insurer claims</dt><dd>{c.insurer_claims.join("; ")}</dd></>}
          {!!c.buildings?.length && <><dt>Buildings</dt><dd>{c.buildings.join(", ")}</dd></>}
          {c.board_item && <><dt>Board item</dt><dd><code className="chip">{c.board_item}</code></dd></>}
        </dl>
        {hasMoney && (
          <div className="stats">
            {c.gross_cents != null && <Stat label="Gross" value={<Money cents={c.gross_cents} />} />}
            {c.fees_cents != null && <Stat label="Fees" value={<Money cents={c.fees_cents} />} />}
            {c.net_cents != null && <Stat label="Net" value={<Money cents={c.net_cents} />} hint={c.proceeds_account ? `to ${c.proceeds_account}` : undefined} />}
          </div>
        )}
        <h4>Events</h4>
        <Timeline events={events} />
        <h4>Duties</h4>
        {duties.length ? <DataTable rows={duties} columns={dutyCols} searchable={false} /> : <p className="muted">No statutory duty applies.</p>}
        {!!c.settled_items?.length && (
          <>
            <h4>Settled items</h4>
            <DataTable rows={c.settled_items} searchable={false} columns={[
              { key: "section", header: "Section" },
              { key: "title", header: "Item" },
              { key: "hard_cents", header: "Priced", align: "right", value: (i) => i.hard_cents ?? -1, render: (i) => i.hard_cents != null ? <Money cents={i.hard_cents} /> : <span className="muted">not priced</span> },
              { key: "standing", header: "Standing", render: (i) => <Pill word={i.standing} /> },
              { key: "scope", header: "Scope", value: (i) => i.scope },
            ]} />
            {c.settled_source && <p className="muted">{c.settled_source}</p>}
          </>
        )}
      </article>
    </Card>
  );
}

function LegalMatters() {
  const r = useApi<LegalCases>("/api/legal-cases");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <p className="notice notice-warn">CONFIDENTIAL: litigation is an executive session matter (CIV 4935(a)). For directors and counsel only. A private person appears by role only; jason decides nothing about a matter.</p>
          <Card title={`Open duties (${d.openDuties.length})`}>
            <p className="muted">Each statutory duty the record does not yet show met. "Not shown" means the record is silent, not that the duty was missed.</p>
            <DataTable rows={d.openDuties} columns={openDutyCols} searchable={false} />
          </Card>
          {d.cases.map((c) => <CaseCard key={c.key} c={c} />)}
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

function ParcelRow({ p }: { p: Parcel }) {
  const n = p.findings.length;
  return (
    <details className="legal-chain">
      <summary className={n ? undefined : "muted"}>{n ? `${n} finding${n === 1 ? "" : "s"}` : "clean"}</summary>
      {n > 0 && (
        <ul className="legal-findings">
          {p.findings.map((f, i) => (
            <li key={i}>
              <Badge tone="warn">{f.check}</Badge> {f.detail}
              {f.number && <> <code className="chip">{f.number}</code></>}
              {f.year != null && <span className="muted"> {f.year}</span>}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

const parcelCols: Column<Parcel>[] = [
  { key: "apn", header: "APN" },
  { key: "phase", header: "Phase", value: (p) => p.phase ?? "" },
  { key: "steps", header: "Steps", align: "right" },
  { key: "reassessing", header: "Reassessing years", value: (p) => Object.keys(p.reassessing ?? {}).join(" "),
    render: (p) => <>{Object.entries(p.reassessing ?? {}).map(([y, num]) => <code key={y} className="chip" title={`instrument ${num}`}>{y}</code>)}</> },
  { key: "findings", header: "Findings", value: (p) => p.findings.length, render: (p) => <ParcelRow p={p} /> },
];

function DeedChains() {
  const r = useApi<AuditChains>("/api/audit-chains");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <div className="stats">
            <Stat label="Chains checked" value={d.checked} />
            <Stat label="Clean" value={d.clean} hint={d.checked ? `${d.checked - d.clean} with findings` : undefined} />
            {!!d.restorationYears?.length && <Stat label="Restoration years" value={d.restorationYears.join(", ")} hint="most parcels rose with no deed behind it" />}
          </div>
          <Card title={`Parcels (${d.parcels.length})`}>
            <p className="muted">Each chain is checked for recording order, a pinned developer's grant in the phase window, a reassessing deed behind each bill year off the 2% track, and a declared price near the next base. A finding names the next record to read; it is a lead, not a determination.</p>
            <DataTable rows={d.parcels} columns={parcelCols} />
          </Card>
        </div>
      )}
    </RemoteView>
  );
}

/** The association's legal matters (confidential; directors and counsel) and the deed chain audit. jason decides nothing. */
export function LegalView() {
  const [tab, setTab] = useState("matters");
  return (
    <Tabs active={tab} onChange={setTab} tabs={[
      { id: "matters", label: "Legal matters", content: <LegalMatters /> },
      { id: "chains", label: "Deed chains", content: <DeedChains /> },
    ]} />
  );
}
