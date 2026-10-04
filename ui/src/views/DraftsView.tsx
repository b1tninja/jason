import { useState } from "react";
import { Badge, Card, Caveats, Command, DataTable, Doc, EmptyState, Pill, RemoteView, Stat, type Column, type DocRef } from "../components";
import { useApi } from "../lib/useApi";

export interface RequestDraft {
  threadId: string; unit: string; unitId?: number | null; first: string; last: string; status: string; topics: string[];
  form: string | null; formId?: number | null; title: string; link?: string; message: string;
}
export interface LinkedRequest {
  id: number | string; form: string; unit: string; status: string; created: string; title: string; topics: string[];
  notices: { threadId: string; at: string; subject: string; how: string }[];
  /** The request's submission as a document reference (`payhoa:submission:<id>`, named by its title), from the loader. */
  doc?: DocRef;
  ownerThreads: { threadId: string; first: string; last: string; subject: string; status: string; score: number; how: string; link?: string }[];
}
export interface RequestLinks {
  found?: boolean; note?: string; requests: number; withNotice: number; withOwnerThread: number; emailedWithoutRequest: number;
  rows: LinkedRequest[]; drafts: RequestDraft[]; caveats?: string[];
}

/** One emailed request PayHOA does not have: what jason would enter, and the command a person runs to enter it. */
export function DraftCard({ d }: { d: RequestDraft }) {
  const cmd = `jason request-links --create ${d.threadId} --yes`;
  return (
    <article className="item" data-priority={d.form ? "normal" : "high"}>
      <header className="row wrap">
        <Badge>{d.unit || "unit?"}</Badge>
        {d.form ? <Badge tone="good">{d.form}</Badge> : <Badge tone="bad">no form matches</Badge>}
        {d.topics.map((t) => <Badge key={t}>{t}</Badge>)}
        <Pill word={d.status} />
        <span className="muted">first {d.first} · last {d.last}</span>
      </header>
      <h4>{d.link ? <a href={d.link} target="_blank" rel="noreferrer">{d.title}</a> : d.title}</h4>
      <p className="draft-message">{d.message}</p>
      <Command cmd={cmd} note="Enters the request in PayHOA; it is never approved, denied, or assigned. Add --message to replace the text, --notify-owner to tell the owner." />
    </article>
  );
}

const cols: Column<LinkedRequest>[] = [
  { key: "created", header: "Created" },
  { key: "unit", header: "Unit" },
  { key: "form", header: "Form" },
  // The request's submission as a Doc chip: one logged view of jason's kept read, the form the owner filled in.
  { key: "title", header: "Request", render: (r) => r.doc ? <Doc doc={r.doc} variant="chip" /> : r.title },
  { key: "status", header: "Status", render: (r) => <Pill word={r.status} /> },
  { key: "notices", header: "PayHOA notices", align: "right", value: (r) => r.notices.length },
  { key: "ownerThreads", header: "Owner's email", value: (r) => r.ownerThreads.length,
    render: (r) => r.ownerThreads.length ? <ul className="findings">{r.ownerThreads.slice(0, 3).map((t) => <li key={t.threadId} title={t.how}>{t.link ? <a href={t.link} target="_blank" rel="noreferrer">{t.subject}</a> : t.subject} <span className="muted">score {t.score}</span></li>)}</ul> : <span className="muted">none</span> },
];

/** Emailed requests PayHOA does not have, as drafts a person enters; and each request beside the email about it. */
export function DraftsView() {
  const [unit, setUnit] = useState("");
  const r = useApi<RequestLinks>(`/api/request-links?unit=${encodeURIComponent(unit)}`);
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <div className="stats">
            <Stat label="Requests in PayHOA" value={d.requests} />
            <Stat label="With PayHOA notices" value={d.withNotice} />
            <Stat label="With the owner's email" value={d.withOwnerThread} />
            <Stat label="Emailed, no request" value={d.emailedWithoutRequest} hint="drafts below" />
          </div>
          <Card title={`Drafts: emailed requests PayHOA does not have (${d.drafts.length})`} actions={<input className="search" aria-label="Unit" placeholder="Unit…" value={unit} onChange={(e) => setUnit(e.target.value)} />}>
            <p className="muted">A draft is what jason would enter from the thread. A person reads the thread, then runs the command; the page enters nothing.</p>
            {d.drafts.length ? d.drafts.map((x) => <DraftCard key={x.threadId} d={x} />) : <EmptyState>Every emailed request has a PayHOA request.</EmptyState>}
          </Card>
          <Card title={`Requests beside their email (${d.rows.length})`}>
            <DataTable rows={d.rows} columns={cols} />
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
