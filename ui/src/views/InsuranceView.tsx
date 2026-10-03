import { Badge, Card, Caveats, DataTable, DueDate, Findings, Money, Pill, RemoteView, Timeline, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { Insurance, Policy } from "./types";

const cols: Column<Policy>[] = [
  { key: "kind", header: "Policy", render: (r) => <>{r.kind.replace(/_/g, " ")}{r.building != null && r.building !== "" ? <span className="muted"> bldg {String(r.building)}</span> : null}</> },
  { key: "number", header: "Number" },
  { key: "carrier", header: "Carrier" },
  { key: "standing", header: "Standing", render: (r) => <Pill word={r.standing} /> },
  { key: "termEnd", header: "Term ends", render: (r) => <DueDate iso={r.termEnd} />, value: (r) => r.termEnd ?? "9999" },
  { key: "paid", header: "Next term paid", align: "right", value: (r) => r.nextTermPayments.reduce((s, p) => s + p.amountCents, 0),
    render: (r) => r.nextTermPayments.length ? <Money cents={r.nextTermPayments.reduce((s, p) => s + p.amountCents, 0)} /> : <span className="muted">—</span> },
  { key: "notices", header: "Letters", value: (r) => r.notices.length, render: (r) => <span className="row wrap">{r.notices.map((n, i) => <span key={i} title={n.received}><Badge tone={/cancel|non-?renew/i.test(n.kind) ? "bad" : "neutral"}>{n.kind}</Badge></span>)}</span> },
  { key: "findings", header: "Findings", render: (r) => <Findings items={r.findings} empty="none" />, value: (r) => r.findings.length },
];

/** The policy register against what PayHOA paid and what the mail says. jason buys, renews, cancels, and claims nothing. */
export function InsuranceView() {
  const r = useApi<Insurance>("/api/insurance");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={`Policies as of ${d.asOf}`}>
            <DataTable rows={d.policies} columns={cols} searchable={false} />
          </Card>
          <Card title="Terms">
            <Timeline events={d.policies.flatMap((p) => p.terms.filter((t) => t.start).map((t, i) => ({
              id: `${p.number}-${i}`, date: t.start!, title: <>{p.kind.replace(/_/g, " ")} <span className="muted">{p.number}</span></>,
              detail: <>{t.start} to {t.end ?? "?"}{t.paidCents != null && <> · <Money cents={t.paidCents} /></>}</>, tone: t.paidCents ? "good" : "warn",
            })))} />
          </Card>
          {d.claims.length > 0 && (
            <Card title={`Claims the mail acknowledges (${d.claims.length})`}>
              <DataTable rows={d.claims} columns={[{ key: "received", header: "Received" }, { key: "claimNumber", header: "Claim" }, { key: "dateOfLoss", header: "Date of loss" }, { key: "kind", header: "Letter" }]} />
            </Card>
          )}
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
