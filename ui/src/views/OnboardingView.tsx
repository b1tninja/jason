import { useMemo, useState } from "react";
import { Badge, Card, Caveats, Command, DataTable, Findings, Markdown, Pill, RemoteView, Stat, Tabs, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";

interface Account { service: string; set: boolean | null; how: string; note?: string }
interface Fact { name: string; supplied: boolean | null }
interface Item {
  key: string; group: string; title: string; authority: string; holders: string[]; record: string; delivery: string; kinds: string[]; why: string;
  status: string; askedOf: string; askedOn: string; chasedOn: string; receivedOn: string; filed: string; reason: string; note: string; history: string[]; storeSays: string;
}
interface Summary { factsSupplied: number; factsTotal: number; accountsSet: number; accountsTotal: number; recordsHeld: number; recordsTotal: number; deliveriesFound: number; deliveriesTotal: number; requests: Record<string, number>; gaps: number }
interface Onboarding { found?: boolean; note?: string; summary: Summary; accounts: Account[]; facts: { duty: string; facts: Fact[] }[]; items: Item[]; gaps: string[]; statuses: string[]; holders: string[]; groups: string[]; caveats?: string[] }

export function SummaryStats({ s }: { s: Summary }) {
  return (
    <div className="stats">
      <Stat label="Accounts connected" value={`${s.accountsSet} of ${s.accountsTotal}`} />
      <Stat label="Facts supplied" value={`${s.factsSupplied} of ${s.factsTotal}`} hint="Community methods that return something" />
      <Stat label="5200 records with a holder" value={`${s.recordsHeld} of ${s.recordsTotal}`} />
      <Stat label="Developer deliveries found" value={`${s.deliveriesFound} of ${s.deliveriesTotal}`} />
      <Stat label="Requests received or pinned" value={(s.requests["received"] ?? 0) + (s.requests["pinned"] ?? 0)} hint={`${s.requests["asked"] ?? 0} asked · ${s.requests["gap"] ?? 0} gaps`} />
    </div>
  );
}

/** One request-list row's editor: what a person did about it. */
function Mark({ it, holders, statuses, onSaved }: { it: Item; holders: string[]; statuses: string[]; onSaved: (next: Item) => void }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState({ status: it.status, asked_of: it.askedOf, asked_on: it.askedOn, chased_on: it.chasedOn, received_on: it.receivedOn, filed: it.filed, reason: it.reason, note: it.note });
  const [error, setError] = useState("");
  const save = async () => {
    try {
      const r = await postJson<Record<string, string>>(`/api/onboarding/${it.key}`, d);
      onSaved({ ...it, status: r.status, askedOf: r.asked_of, askedOn: r.asked_on, chasedOn: r.chased_on, receivedOn: r.received_on, filed: r.filed, reason: r.reason, note: r.note, history: (r.history as unknown as string[]) ?? it.history });
      setOpen(false);
    } catch (e) { setError((e as Error).message); }
  };
  if (!open) return <button className="link" onClick={() => setOpen(true)}>mark</button>;
  return (
    <div className="fields mark">
      <label>Status <select value={d.status} onChange={(e) => setD({ ...d, status: e.target.value })}>{statuses.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label>Asked of <input list="holders" value={d.asked_of} onChange={(e) => setD({ ...d, asked_of: e.target.value })} /></label>
      <datalist id="holders">{holders.map((h) => <option key={h} value={h} />)}</datalist>
      <label>Asked on <input type="date" value={d.asked_on} onChange={(e) => setD({ ...d, asked_on: e.target.value })} /></label>
      <label>Chased on <input type="date" value={d.chased_on} onChange={(e) => setD({ ...d, chased_on: e.target.value })} /></label>
      <label>Received on <input type="date" value={d.received_on} onChange={(e) => setD({ ...d, received_on: e.target.value })} /></label>
      <label>Filed where <input value={d.filed} onChange={(e) => setD({ ...d, filed: e.target.value })} placeholder="PayHOA folder, Drive path, or library id" /></label>
      {d.status === "not applicable" && <label className="wide">Why it does not apply <input value={d.reason} onChange={(e) => setD({ ...d, reason: e.target.value })} /></label>}
      <label className="wide">Note <input value={d.note} onChange={(e) => setD({ ...d, note: e.target.value })} /></label>
      <div className="row"><button className="primary" onClick={save}>Save</button><button onClick={() => setOpen(false)}>Cancel</button>{error && <span className="notice notice-error">{error}</span>}</div>
    </div>
  );
}

function RequestList({ d, onSaved }: { d: Onboarding; onSaved: (next: Item) => void }) {
  const [group, setGroup] = useState("");
  const [status, setStatus] = useState("");
  const rows = d.items.filter((i) => (!group || i.group === group) && (!status || i.status === status));
  const cols: Column<Item>[] = [
    { key: "status", header: "Status", render: (i) => <Pill word={i.status} meaning={i.reason || undefined} /> },
    { key: "title", header: "Item", render: (i) => <><strong>{i.title}</strong>{i.authority && <span className="muted"> {i.authority}</span>}{i.why && <div className="muted">{i.why}</div>}</> },
    { key: "holders", header: "Usually held by", value: (i) => i.holders.join(", ") },
    { key: "record", header: "Files as", value: (i) => [i.record, i.delivery].filter(Boolean).join(" · "), render: (i) => <span className="row wrap">{i.record && <Badge>{i.record.replace(/_/g, " ")}</Badge>}{i.delivery && <Badge tone="neutral">{`delivery: ${i.delivery.replace(/_/g, " ")}`}</Badge>}</span> },
    { key: "askedOn", header: "Asked", value: (i) => i.askedOn, render: (i) => i.askedOn ? <>{i.askedOn}{i.askedOf && <span className="muted"> of {i.askedOf}</span>}{i.chasedOn && <span className="muted">, chased {i.chasedOn}</span>}</> : <span className="muted">—</span> },
    { key: "receivedOn", header: "Received", value: (i) => i.receivedOn, render: (i) => i.receivedOn ? <>{i.receivedOn}{i.filed && <div className="muted">{i.filed}</div>}</> : <span className="muted">—</span> },
    { key: "storeSays", header: "The stores show", render: (i) => i.storeSays ? <Findings items={[i.storeSays]} /> : <span className="muted">—</span>, value: (i) => i.storeSays },
    { key: "mark", header: "", render: (i) => <Mark it={i} holders={d.holders} statuses={d.statuses} onSaved={onSaved} /> },
  ];
  return (
    <Card title={`Request list (${rows.length} of ${d.items.length})`} actions={<span className="row wrap">
      <select aria-label="Group" value={group} onChange={(e) => setGroup(e.target.value)}><option value="">every group</option>{d.groups.map((g) => <option key={g}>{g}</option>)}</select>
      <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">any status</option>{d.statuses.map((s) => <option key={s}>{s}</option>)}</select>
    </span>}>
      <p className="muted">In plain words, with the statute beside each and who usually has it. Mark what you asked, of whom, when; what came back and where it was filed; or why an item does not apply.</p>
      <DataTable rows={rows} columns={cols} searchable />
    </Card>
  );
}

function Letter() {
  const [to, setTo] = useState("the board");
  const r = useApi<{ found: boolean; count: number; markdown: string }>(`/api/request-letter?to=${encodeURIComponent(to)}`);
  return (
    <Card title="The request letter" actions={<label>To <input value={to} onChange={(e) => setTo(e.target.value)} /></label>}>
      <p className="muted">Built from the items marked <em>asked</em>, grouped, in plain words. Copy it into the email you send; the page sends nothing.</p>
      <RemoteView r={r}>{(d) => d.count === 0 ? <p className="muted">Mark items as asked and the letter appears here.</p> : <><div className="preview"><Markdown text={d.markdown} /></div><Command cmd={d.markdown} note="The letter as Markdown, to paste." /></>}</RemoteView>
    </Card>
  );
}

/** Onboarding the active community: accounts, facts, the request list and its letter, what arrived, and the gaps. */
export function OnboardingView() {
  const r = useApi<Onboarding>("/api/onboarding");
  const [tab, setTab] = useState("requests");
  const [patched, setPatched] = useState<Record<string, Item>>({});
  return (
    <RemoteView r={r}>
      {(raw) => {
        const d = { ...raw, items: raw.items.map((i) => patched[i.key] ?? i) };
        return (
          <div className="stack">
            <SummaryStats s={d.summary} />
            <Tabs active={tab} onChange={setTab} tabs={[
              { id: "accounts", label: "Accounts", content: (
                <Card title="Services the community uses">
                  <p className="muted">Set or not set, never the value. Connecting is a person's step; the page shows how.</p>
                  <DataTable rows={d.accounts} searchable={false} columns={[
                    { key: "service", header: "Service" },
                    { key: "set", header: "Connected", value: (a) => a.set === null ? "unknown" : a.set ? "yes" : "no", render: (a) => a.set === null ? <Badge>unknown</Badge> : a.set ? <Badge tone="good">set</Badge> : <Badge tone="warn">not set</Badge> },
                    { key: "how", header: "How", render: (a) => <code className="chip">{a.how}</code> },
                  ]} />
                  {d.accounts.some((a) => a.note) && <p className="muted">{d.accounts.find((a) => a.note)?.note}</p>}
                </Card>
              ) },
              { id: "facts", label: "Facts", content: (
                <Card title="The profile's facts, by duty">
                  <p className="muted">A fact is a Community method; supplied when it returns something. The profile sets it in Python; this is the map of what is left.</p>
                  {d.facts.map((duty) => (
                    <div key={duty.duty} className="factrow"><strong>{duty.duty}</strong> <span className="row wrap">{duty.facts.map((f) => <Badge key={f.name} tone={f.supplied === null ? "neutral" : f.supplied ? "good" : "warn"}>{f.name}</Badge>)}</span></div>
                  ))}
                </Card>
              ) },
              { id: "requests", label: "Request list", content: <RequestList d={d} onSaved={(n) => setPatched((p) => ({ ...p, [n.key]: n }))} /> },
              { id: "letter", label: "The letter", content: <Letter /> },
              { id: "gaps", label: `Gaps (${d.gaps.length + d.items.filter((i) => i.status === "gap").length})`, content: (
                <Card title="What is still missing">
                  <Findings items={[...d.gaps, ...d.items.filter((i) => i.status === "gap").map((i) => `${i.title}: asked ${i.askedOn || "?"}${i.chasedOn ? `, chased ${i.chasedOn}` : ""}, not received`)]} empty="no gaps" />
                  <p className="muted">The inventory's gaps (a record with no holder) and the requests asked and not received. The standing agenda item until it is empty. Ingestion itself is on <a href="#/ingestion">Document ingestion</a> and <a href="#/leads">Leads</a>.</p>
                </Card>
              ) },
            ]} />
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}

export function CommunitiesView() {
  const r = useApi<{ found: boolean; count: number; communities: { name: string; where: string; active: boolean; progress?: Summary }[] }>("/api/communities");
  const go = useMemo(() => (h: string) => { window.location.hash = `/${h}`; }, []);
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <p className="muted">Every community this checkout can serve. One is active at a time (the server's profile); the others are listed from where they were found.</p>
          <div className="grid-2">
            {d.communities.map((c) => (
              <Card key={c.name} title={c.name} actions={c.active ? <Badge tone="good">active</Badge> : <Badge>not active</Badge>}>
                <p className="muted"><code className="chip">{c.where}</code></p>
                {c.progress ? <><SummaryStats s={c.progress} /><button className="primary" onClick={() => go("onboarding")}>Open onboarding</button></> : <p className="muted">Set <code className="chip">JASON_PROFILE={c.name}</code> and restart to work on it.</p>}
              </Card>
            ))}
          </div>
        </div>
      )}
    </RemoteView>
  );
}
