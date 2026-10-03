import { useState } from "react";
import { Badge, Card, Caveats, DataTable, DueDate, Findings, Money, Pill, RemoteView, Tabs } from "../components";
import { useApi } from "../lib/useApi";
import type { OpenItems } from "./types";

/** What is waiting on the association, from every store at once. jason answers, pays, and files nothing. */
export function InboxView() {
  const [days, setDays] = useState(30);
  const r = useApi<OpenItems>(`/api/open-items?days=${days}`);
  const [tab, setTab] = useState("threads");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title="Waiting on the association" actions={<label>last <input type="number" min={1} value={days} onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 30))} style={{ width: "4rem" }} /> days</label>}>
            <p className="row wrap">{Object.entries(d.counts).map(([k, n]) => <span key={k}><Badge tone={n ? "warn" : "neutral"}>{k}</Badge> {n}</span>)}</p>
          </Card>
          <Tabs active={tab} onChange={setTab} tabs={[
            { id: "threads", label: `Email awaiting us (${d.threadsAwaitingUs.length})`, content: (
              <DataTable rows={d.threadsAwaitingUs} columns={[
                { key: "last", header: "Last" },
                { key: "ageDays", header: "Age (days)", align: "right" },
                { key: "who", header: "Who" },
                { key: "subject", header: "Subject", render: (t) => t.link ? <a href={t.link} target="_blank" rel="noreferrer">{t.subject}</a> : t.subject },
                { key: "topics", header: "Topics", value: (t) => t.topics.join(", ") },
                { key: "likely", header: "Reply?", value: (t) => (t.likelyNeedsResponse ? 1 : 0),
                  render: (t) => <>{t.likelyNeedsResponse && <Badge tone="warn">likely</Badge>} {t.pastUsualTime && <Badge tone="bad">past usual time</Badge>} {t.replyRate != null && <span className="muted">{Math.round(t.replyRate * 100)}% replied before</span>}</> },
              ]} /> ) },
            { id: "requests", label: `Requests pending (${d.requestsPending.length})`, content: (
              <DataTable rows={d.requestsPending} columns={[{ key: "created", header: "Created", value: (x) => x.created ?? "" }, { key: "form", header: "Form", value: (x) => x.form ?? "" }, { key: "unit", header: "Unit", value: (x) => x.unit ?? "" }, { key: "title", header: "Title", value: (x) => x.title ?? "" }, { key: "status", header: "Status", render: (x) => <Pill word={x.status} />, value: (x) => x.status ?? "" }]} /> ) },
            { id: "deadlines", label: `Deadlines (${d.deadlines.length})`, content: (
              <DataTable rows={d.deadlines} columns={[{ key: "standing", header: "Standing", render: (x) => <Pill word={x.standing} meaning={x.note} /> }, { key: "name", header: "Obligation" }, { key: "next", header: "Next", render: (x) => <DueDate iso={x.next} />, value: (x) => x.next ?? "9999" }]} searchable={false} /> ) },
            { id: "insurance", label: `Insurance (${d.insurance.length})`, content: (
              <DataTable rows={d.insurance} columns={[{ key: "policy", header: "Policy" }, { key: "standing", header: "Standing", render: (x) => <Pill word={x.standing} /> }, { key: "finding", header: "Finding", render: (x) => <Findings items={[x.finding]} /> }]} searchable={false} /> ) },
            { id: "letters", label: `Letters to act on (${d.lettersToAct.length})`, content: (
              <DataTable rows={d.lettersToAct} columns={[{ key: "received", header: "Received" }, { key: "from", header: "From" }, { key: "kind", header: "Kind", render: (x) => <Badge>{x.kind}</Badge> }, { key: "deadlines", header: "Deadlines it states", render: (x) => <Findings items={x.deadlines} empty="none" />, value: (x) => x.deadlines.length }]} /> ) },
            { id: "mail", label: `Mail not scanned (${d.mailNotScanned.length})`, content: (
              <DataTable rows={d.mailNotScanned} columns={[{ key: "received", header: "Received" }, { key: "from", header: "From", value: (x) => x.from ?? "" }, { key: "kind", header: "Kind", value: (x) => x.kind ?? "" }]} /> ) },
            { id: "liens", label: `Lien notices (${d.lienNotices.length})`, content: (
              <DataTable rows={d.lienNotices} columns={[{ key: "received", header: "Received", value: (x) => x.received ?? "" }, { key: "from", header: "Claimant", value: (x) => x.from ?? "" }, { key: "kind", header: "Kind", value: (x) => x.kind ?? "" }, { key: "amountCents", header: "Amount", align: "right", value: (x) => x.amountCents ?? 0, render: (x) => x.amountCents != null ? <Money cents={x.amountCents} /> : <span className="muted">—</span> }]} /> ) },
          ]} />
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
