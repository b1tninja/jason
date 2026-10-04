import { Badge, Card, Caveats, DataTable, DocList, RemoteView, type Column, type DocRef } from "../components";
import { useApi } from "../lib/useApi";

interface DocGroup { kind: string; docs: DocRef[] }
interface NextMeeting { date: string; regular: boolean; agendaPosted: boolean; docs: DocGroup[]; time?: string; place?: string }
interface Minutes { date: string; docs: DocGroup[] }
export interface Disclosure {
  key: string; name: string; authority: string; rule: string; windowOpens: string | null; next: string | null;
  delivered: string | null; deliveredAs: string; carries: { key: string; name: string; authority: string }[];
}
interface Standard { kind: string; days: number; businessDays: boolean; authority: string; source: string }
interface Clock { key: string; records: string; authority: string; clock: string }
export interface OwnerDigest {
  found?: boolean; note?: string; asOf: string;
  nextMeeting: NextMeeting | null; latestMinutes: Minutes | null; disclosures: Disclosure[];
  policies: { adopted: { title: string; adopted: string }[]; standards: Standard[]; note: string };
  recordsRequest: { screen: string; steps: string[]; clocks: Clock[]; produced: string };
  caveats: string[];
}

const heading = (kind: string) => kind.charAt(0).toUpperCase() + kind.slice(1);

function Groups({ groups }: { groups: DocGroup[] }) {
  return <>{groups.map((g) => <DocList key={g.kind} docs={g.docs} variant="row" level={3} title={`${heading(g.kind)} (${g.docs.length})`} />)}</>;
}

/** When a disclosure goes out, and the day the delivery ledger shows it went. */
export const disclosureCols: Column<Disclosure>[] = [
  { key: "name", header: "Disclosure", render: (d) => (
    <span className="stack-tight">
      <strong>{d.name}</strong>
      {d.carries.length > 0 && <span className="muted"> with {d.carries.map((c) => c.name.toLowerCase()).join("; ")}</span>}
    </span>
  ) },
  { key: "authority", header: "Civil Code" },
  { key: "next", header: "Due", value: (d) => d.next ?? "9999", render: (d) => (d.next ? <>{d.windowOpens ? `${d.windowOpens} to ` : "by "}{d.next}</> : <span className="muted">{d.rule}</span>) },
  { key: "delivered", header: "Went out", value: (d) => d.delivered ?? "", render: (d) => (d.delivered ? <Badge tone="good">{`${d.deliveredAs} ${d.delivered}`}</Badge> : <span className="muted">not shown yet</span>) },
];

/** The owner's Overview (`GET /api/owner-digest`): the next open meeting and its agenda when posted, the latest approved
 * minutes, the annual disclosures, the community's adopted standards, and how to ask for a record. It is not the board's
 * digest: nothing about any owner, unit, balance, lien, hearing, or executive session is sent to it. */
export function OwnerDigestView() {
  const r = useApi<OwnerDigest>("/api/owner-digest?view=owner");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <div className="grid-2">
            <Card title="Next open meeting">
              {d.nextMeeting ? (
                <div className="stack">
                  <p><strong>{d.nextMeeting.date}</strong>{d.nextMeeting.time ? ` at ${d.nextMeeting.time}` : ""}{d.nextMeeting.place ? `, ${d.nextMeeting.place}` : ""}</p>
                  {d.nextMeeting.agendaPosted
                    ? <Groups groups={d.nextMeeting.docs} />
                    : <p className="muted">The agenda is posted with the meeting's notice, at least four days before the meeting (CIV 4920).</p>}
                </div>
              ) : <p className="muted">No meeting is scheduled on file.</p>}
            </Card>
            <Card title="Latest minutes">
              {d.latestMinutes ? (
                <div className="stack">
                  <p>Approved minutes of <strong>{d.latestMinutes.date}</strong></p>
                  <Groups groups={d.latestMinutes.docs} />
                </div>
              ) : <p className="muted">No approved minutes are on file yet.</p>}
            </Card>
          </div>
          <Card title="Annual disclosures">
            <p className="muted">What every member receives each year, when it is due, and when the association's delivery ledger shows it went out.</p>
            <DataTable rows={d.disclosures} columns={disclosureCols} rowKey={(x) => x.key} searchable={false} />
          </Card>
          <Card title="Standards and policies">
            {d.policies.adopted.length === 0 && d.policies.standards.length === 0 && <p className="muted">{d.policies.note}</p>}
            {d.policies.standards.length > 0 && (
              <>
                <p className="muted">{d.policies.note}</p>
                <ul>{d.policies.standards.map((s) => <li key={s.kind}>{heading(s.kind)}: within {s.days} {s.businessDays ? "business " : ""}days <span className="muted">({s.authority})</span></li>)}</ul>
              </>
            )}
          </Card>
          <Card title="Ask for a record">
            <ol>{d.recordsRequest.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            {d.recordsRequest.clocks.length > 0 && (
              <ul className="muted">{d.recordsRequest.clocks.map((c) => <li key={c.key}>{c.records}: {c.clock} ({c.authority})</li>)}</ul>
            )}
            <p><a href={`#/${d.recordsRequest.screen}?view=owner`}>Open the records request form</a></p>
            <p className="muted">{d.recordsRequest.produced}</p>
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
