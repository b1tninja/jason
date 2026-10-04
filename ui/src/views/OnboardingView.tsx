import { useEffect, useMemo, useState } from "react";
import { Badge, Card, Caveats, Command, DataTable, Findings, InstrumentGraph, KeyDocuments, Markdown, Pill, RemoteView, Stat, Tabs, type Column, type InstrumentGraphData, type KeyDocumentsData } from "../components";
import { AssociationPicker } from "../components/AssociationPicker";
import { DocumentLocator } from "../components/DocumentLocator";
import { OwnerNames } from "../components/InstrumentGraph";
import { postJson } from "../lib/api";
import type { AssociationChoice } from "../lib/discovery";
import { readMe } from "../lib/session";
import { useApi } from "../lib/useApi";
import "./discovery.css";

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

interface LibraryRow { id: string; path: string; kind: string; records: string[]; period: string; method: string; evidence: string; confidential: boolean }

/** Find the file jason classified for this item: by its kinds and record first, then by words. A pick fills "filed where". */
function FindInLibrary({ it, onPick }: { it: Item; onPick: (row: LibraryRow) => void }) {
  const [words, setWords] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => { const h = setTimeout(() => setDebounced(words), 300); return () => clearTimeout(h); }, [words]);
  const q = new URLSearchParams({ limit: "8" });
  if (debounced.trim()) q.set("words", debounced.trim());
  else if (it.kinds[0]) q.set("kind", it.kinds[0]);
  else if (it.record) q.set("record", it.record);
  const r = useApi<{ found: boolean; note?: string; count?: number; heldBackConfidential?: number; rows?: LibraryRow[] }>(`/api/library?${q}`);
  return (
    <details className="picker" open>
      <summary>Find in the library{it.kinds[0] ? <span className="muted"> (kind {it.kinds[0].replace(/_/g, " ")})</span> : null}</summary>
      <input className="search" aria-label="Words in the file" placeholder="words in the file…" value={words} onChange={(e) => setWords(e.target.value)} />
      {r.status === "ready" && r.data.found === false && <p className="muted">{r.data.note ?? "nothing classified yet"}</p>}
      {r.status === "ready" && r.data.found !== false && (
        <ul className="picks">
          {(r.data.rows ?? []).map((row) => <li key={row.id}><button className="link" onClick={() => onPick(row)}>{row.path}</button> <span className="muted">{row.period} · {row.method}</span></li>)}
          {!!r.data.heldBackConfidential && <li className="muted">{r.data.heldBackConfidential} confidential held back</li>}
        </ul>
      )}
    </details>
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
      <div className="wide"><FindInLibrary it={it} onPick={(row) => setD({ ...d, filed: `${row.path} (library ${row.id})`, status: d.status === "not asked" || d.status === "asked" ? "received" : d.status })} /></div>
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

/** The counties whose recorder's index jason reads; a county with no directory says how to build one. */
export const DIRECTORY_COUNTIES = ["placer", "sacramento"] as const;

/** The first step: choose the association from the county's directory, locate its recorded documents, and ask the
 * board about each through the onboarding questions. Choosing writes nothing; locating is a read job a person queues. */
export function FindAssociation({ counties = DIRECTORY_COUNTIES, me = readMe(), pollMs }: { counties?: readonly string[]; me?: string; pollMs?: number }) {
  const [choice, setChoice] = useState<AssociationChoice | null>(null);
  return (
    <div className="stack">
      <Card title="1. Choose the association">
        <p className="muted">From the county's association directory, built from the county recorder's public index. Choosing one writes nothing; it shows the next step.</p>
        <AssociationPicker counties={counties} onPick={setChoice} onClear={() => setChoice(null)} picked={choice} />
      </Card>
      <Card title={choice ? `2. Locate the recorded documents of ${choice.name}` : "2. Locate the active community's recorded documents"}>
        {choice ? (
          <div className="stack-sm">
            <p className="muted">The documents below are read for the association chosen above. If it is not the active community, a person starts its profile in a terminal; the console never writes a profile.</p>
            <Command cmd={`jason onboard --new ${choice.key} --name "${choice.name}" --county ${choice.county} --locate`} note="Writes a new profile package and its empty private facts, never over an existing one, and keeps what it locates as onboarding questions." />
          </div>
        ) : (
          <p className="muted">The active community's, as last located. Choose an association above to read another's.</p>
        )}
        <DocumentLocator county={choice?.county} name={choice?.name} me={me} pollMs={pollMs} />
      </Card>
      <Card title="3. Ask the board about each">
        <p className="muted">
          Each checklist item located becomes a FACT question in the onboarding session: which is the declaration, which
          amendments are in force, and whether the association holds a copy of each. The answers are given there, with the
          name of the person who gives them; a second person confirms the declaration and the amendments. The board's list
          above is the same questions on paper.
        </p>
        <Command cmd="jason onboard --questions" note="Lists the open questions by priority; answer one with jason onboard --answer ID TEXT --by NAME." />
      </Card>
    </div>
  );
}

/** The key documents: each expected document, the copies held or linked, and a person's link, upload, or unlink. */
export function KeyDocumentsTab({ me = readMe() }: { me?: string }) {
  const r = useApi<KeyDocumentsData>("/api/key-documents");
  return <RemoteView r={r}>{(d) => <KeyDocuments data={d} by={me} onChanged={r.reload} />}</RemoteView>;
}

/** The recorded instruments as a graph: the association's chain, closings, governing documents, and loans, each edge
 * with the rule that made it. Read from jason's stores; nothing is fetched from the county. Owners are masked by
 * default; "Show owners' names" reads the graph again with the names (`names=1&by=`), which the server logs as a
 * reveal, and "Hide names" returns to the masked view. */
export function InstrumentGraphTab({ me = readMe() }: { me?: string }) {
  const masked = useApi<InstrumentGraphData>("/api/instrument-graph?scope=association");
  const [named, setNamed] = useState<InstrumentGraphData | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState("");
  // The person's name goes in a POST body, never a URL; the server logs the reveal. A refused reveal stays masked.
  const show = async (who: string) => {
    setRefused("");
    setBusy(true);
    try {
      setNamed(await postJson<InstrumentGraphData>("/api/write/instrument-graph/reveal", { by: who, scope: "association" }));
    } catch (e) {
      setRefused(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const shown = !!named?.names;
  return (
    <div className="stack">
      <OwnerNames shown={shown} me={me} reveal={shown ? named?.reveal : undefined} busy={busy}
        onShow={show} onHide={() => setNamed(null)} />
      {refused && <p className="notice notice-error" role="alert">jason did not show the names: {refused}. The graph stays masked.</p>}
      {named ? <InstrumentGraph data={named} /> : <RemoteView r={masked}>{(d) => <InstrumentGraph data={d} />}</RemoteView>}
    </div>
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
              { id: "find", label: "Find the association", content: <FindAssociation /> },
              { id: "key-documents", label: "Key documents", content: <KeyDocumentsTab /> },
              { id: "instruments", label: "Recorded instruments", content: <InstrumentGraphTab /> },
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
