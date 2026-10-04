import { Badge, Card, Caveats, DataTable, DocList, DueDate, Findings, Money, Pill, RemoteView, Timeline, type Audience, type Column, type DocRef } from "../components";
import { useApi } from "../lib/useApi";
import type { Insurance, Policy } from "./types";

/** The scans of these letters, each once, in order (a letter that prints two policies' numbers is one scan). */
export function scansOf(letters: readonly { scan?: DocRef | null }[]): DocRef[] {
  const seen = new Set<string>();
  return letters.flatMap((l) => (l.scan && !seen.has(l.scan.address) ? (seen.add(l.scan.address), [l.scan]) : []));
}

/** The letters held in place of a scan (one that carries a credential opens in no screen), each once, in order. */
export function heldOf<T extends { scan?: DocRef | null; held?: string; mailId?: string; received?: string }>(letters: readonly T[]): T[] {
  const seen = new Set<string>();
  return letters.filter((l) => !l.scan && !!l.held && !seen.has(l.mailId ?? l.received ?? "") && (seen.add(l.mailId ?? l.received ?? ""), true));
}

/** "Held" lines for the letters a list leaves out: when each came, and why it opens in no screen. */
export function HeldLetters({ letters }: { letters: readonly { held?: string; received?: string }[] }) {
  if (!letters.length) return null;
  return <ul className="mail-held-list">{letters.map((l, i) => <li key={i} className="muted mail-held">{l.received ? `${l.received}: ` : ""}{l.held}</li>)}</ul>;
}

const lettersCol: Column<Policy> = { key: "notices", header: "Letters", value: (r) => r.notices.length, render: (r) => <span className="row wrap">{r.notices.map((n, i) => <span key={i} title={n.received}><Badge tone={/cancel|non-?renew/i.test(n.kind) ? "bad" : "neutral"}>{n.kind}</Badge></span>)}</span> };

const cols: Column<Policy>[] = [
  { key: "kind", header: "Policy", render: (r) => <>{r.kind.replace(/_/g, " ")}{r.building != null && r.building !== "" ? <span className="muted"> bldg {String(r.building)}</span> : null}</> },
  { key: "number", header: "Number" },
  { key: "carrier", header: "Carrier" },
  { key: "standing", header: "Standing", render: (r) => <Pill word={r.standing} /> },
  { key: "termEnd", header: "Term ends", render: (r) => <DueDate iso={r.termEnd} />, value: (r) => r.termEnd ?? "9999" },
  { key: "paid", header: "Next term paid", align: "right", value: (r) => r.nextTermPayments.reduce((s, p) => s + p.amountCents, 0),
    render: (r) => r.nextTermPayments.length ? <Money cents={r.nextTermPayments.reduce((s, p) => s + p.amountCents, 0)} /> : <span className="muted">—</span> },
  lettersCol,
  { key: "findings", header: "Findings", render: (r) => <Findings items={r.findings} empty="none" />, value: (r) => r.findings.length },
];

/** A policy as the owner loader sends it (`jason.web.extra.owner_view.owner_insurance`): the summary CIV 5300(b)(9) asks for. */
interface OwnerPolicy { kind: string; building?: string | number | null; carrier: string; termEnd: string | null; terms: { start?: string; end?: string }[]; deductibleCents?: number | null }

const ownerCols: Column<OwnerPolicy>[] = [
  { key: "kind", header: "Policy", render: (r) => <>{r.kind.replace(/_/g, " ")}{r.building != null && r.building !== "" ? <span className="muted"> bldg {String(r.building)}</span> : null}</> },
  { key: "carrier", header: "Carrier" },
  { key: "termEnd", header: "Term ends", value: (r) => r.termEnd ?? "9999", render: (r) => r.termEnd ?? <span className="muted">—</span> },
  { key: "deductibleCents", header: "Deductible", align: "right", value: (r) => r.deductibleCents ?? -1,
    render: (r) => (r.deductibleCents != null ? <Money cents={r.deductibleCents} /> : <span className="muted">—</span>) },
];

/** The owner view of insurance: the insurance summary the budget report carries (CIV 5300(b)(9)), from
 * `GET /api/insurance?view=owner`. The server sends each policy's kind, carrier, term, and deductible, and nothing of the
 * policy numbers, premiums, standings, findings, the association's mail, or the claims. */
function OwnerInsurance() {
  const r = useApi<{ found?: boolean; note?: string; asOf: string; policies: OwnerPolicy[]; caveats?: string[] }>("/api/insurance?view=owner");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={`Policies as of ${d.asOf}`}>
            <DataTable rows={d.policies} columns={ownerCols} searchable={false} rowKey={(p) => `${p.kind}-${p.building ?? ""}`} />
          </Card>
          <Card title="Terms">
            <Timeline events={d.policies.flatMap((p) => p.terms.filter((t) => t.start).map((t, i) => ({
              id: `${p.kind}-${p.building ?? ""}-${i}`, date: t.start!, title: <>{p.kind.replace(/_/g, " ")}</>,
              detail: <>{t.start} to {t.end ?? "?"}</>, tone: "neutral" as const,
            })))} />
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

/** The policy register against what PayHOA paid and what the mail says, with the notices' and claim letters' scans as
 * rows (P2: each View is one logged view). jason buys, renews, cancels, and claims nothing.
 *
 * The owner view (`audience="owner"`) is `OwnerInsurance`, the policy summary alone, from the owner loader. */
export function InsuranceView({ audience = "board" }: { audience?: Audience } = {}) {
  if (audience === "owner") return <OwnerInsurance />;
  return <BoardInsurance />;
}

function BoardInsurance() {
  const r = useApi<Insurance>("/api/insurance");
  return (
    <RemoteView r={r}>
      {(d) => {
        const letters = d.policies.flatMap((p) => p.notices);
        const notices = scansOf(letters);
        const claimLetters = scansOf(d.claims);
        return (
          <div className="stack">
            <Card title={`Policies as of ${d.asOf}`}>
              <DataTable rows={d.policies} columns={cols} searchable={false} />
              {notices.length > 0 && <DocList docs={notices} variant="row" title="Notices in the mail" />}
              <HeldLetters letters={heldOf(letters)} />
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
                {claimLetters.length > 0 && <DocList docs={claimLetters} variant="row" title="Claim letters" />}
                <HeldLetters letters={heldOf(d.claims)} />
              </Card>
            )}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
