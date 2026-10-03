import { useState } from "react";
import { Badge, Card, Caveats, Clock, Confirm, DataTable, DueDate, Findings, Pill, RemoteView, RequestForm, type ClockStage, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import "./recordsrequests.css";

interface Withheld { record: string; reason: string }
interface Decisions { purposeAdequate: boolean | null; withheld: Withheld[]; producedOn: string; inspectedOrCopies: "inspection" | "copies" | ""; feeCents: number; note: string }
interface Req {
  id: string; receivedOn: string; unit: string; via: string; records: string[]; purpose: string; membershipList: boolean; years: number[];
  decisions: Decisions; by: string; recorded: string; updated: string; history: string[]; stages: ClockStage[]; dueBy: string; standing: string; citations: Record<string, string>;
}
interface Kind { record: string; label: string; citation: string; meaning: string; retention: string; files: number | null; gap: string }
interface Source { found?: boolean; count: number; counts: Record<string, number>; requests: Req[]; kinds: Kind[]; vias: string[]; note?: string; caveats: string[] }

const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const label = (kinds: Kind[], record: string) => kinds.find((k) => k.record === record)?.label ?? record.replace(/_/g, " ");

/** Receive a request: the day, the unit (never the member's name), how it came, the record kinds, and the purpose in the member's words. */
function ReceiveForm({ kinds, vias, onSaved }: { kinds: Kind[]; vias: string[]; onSaved: (r: Req) => void }) {
  const [receivedOn, setReceivedOn] = useState(new Date().toISOString().slice(0, 10));
  const [unit, setUnit] = useState("");
  const [via, setVia] = useState(vias[0] ?? "email");
  const [records, setRecords] = useState<string[]>([]);
  const [purpose, setPurpose] = useState("");
  const [years, setYears] = useState("");
  const [by, setBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toggle = (r: string) => setRecords((xs) => (xs.includes(r) ? xs.filter((x) => x !== r) : [...xs, r]));
  const yearList = years.split(/[,\s]+/).map((y) => parseInt(y, 10)).filter((y) => !Number.isNaN(y));
  const save = async () => {
    setBusy(true); setError("");
    try { onSaved(await postJson<Req>("/api/write/records-requests/new", { receivedOn, unit, via, records, purpose, years: yearList, by })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const list = records.includes("membership_list");
  return (
    <Card title="Receive a request">
      <p className="muted">The request as it came in. The purpose is the member's own words, quoted as given; it is read against CIV 5225 only when the membership list is asked, and by a person.</p>
      <div className="fields">
        <label>Received on <input type="date" value={receivedOn} onChange={(e) => setReceivedOn(e.target.value)} /></label>
        <label>Unit <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Unit 12" /></label>
        <label>Via <select value={via} onChange={(e) => setVia(e.target.value)}>{vias.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
        <label>Fiscal years asked for (blank: the current year) <input value={years} onChange={(e) => setYears(e.target.value)} placeholder="2026, 2025" /></label>
        <fieldset className="wide rr-kinds"><legend>Records requested (CIV 5200)</legend>
          {kinds.map((k) => (
            <label key={k.record} title={k.meaning || undefined}><input type="checkbox" checked={records.includes(k.record)} onChange={() => toggle(k.record)} /> {k.label} <span className="muted">{k.citation}{k.files != null ? `, ${k.files} on the shelf` : ""}</span></label>
          ))}
        </fieldset>
        <label className="wide">Purpose, as the member stated it <textarea rows={3} value={purpose} onChange={(e) => setPurpose(e.target.value)} /></label>
        <label>Received by <input value={by} onChange={(e) => setBy(e.target.value)} /></label>
      </div>
      {list && !purpose.trim() && <p className="notice notice-warn">The membership list is asked and no purpose is given. Section 5225 asks the member to state one; record it as given, or note that none was stated.</p>}
      {receivedOn && unit.trim() && records.length > 0 && (
        <Confirm busy={busy} onConfirm={save} summary={<p>Open a request received {receivedOn} from {unit} via {via} for {records.map((r) => label(kinds, r)).join(", ")}{list ? ", including the membership list" : ""}. The clock starts from the day received.</p>}>Open the request</Confirm>
      )}
      {error && <p className="notice notice-error">{error}</p>}
    </Card>
  );
}

/** One request opened: its clock, then the decisions a person records on it. */
function RequestPanel({ r, kinds, today, onSaved }: { r: Req; kinds: Kind[]; today: Date; onSaved: (r: Req) => void }) {
  const d = r.decisions;
  const [purposeAdequate, setPurposeAdequate] = useState<boolean | null>(d.purposeAdequate);
  const [withheld, setWithheld] = useState<Withheld[]>(d.withheld);
  const [producedOn, setProducedOn] = useState(d.producedOn);
  const [how, setHow] = useState<Decisions["inspectedOrCopies"]>(d.inspectedOrCopies);
  const [fee, setFee] = useState((d.feeCents / 100).toFixed(2));
  const [note, setNote] = useState(d.note);
  const [by, setBy] = useState(r.by);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const feeCents = Math.round(parseFloat(fee || "0") * 100);
  const changes: Partial<Decisions> & { by: string } = { by };
  if (r.membershipList && purposeAdequate !== d.purposeAdequate) changes.purposeAdequate = purposeAdequate;
  if (JSON.stringify(withheld) !== JSON.stringify(d.withheld)) changes.withheld = withheld;
  if (producedOn !== d.producedOn) changes.producedOn = producedOn;
  if (how !== d.inspectedOrCopies) changes.inspectedOrCopies = how;
  if (!Number.isNaN(feeCents) && feeCents !== d.feeCents) changes.feeCents = feeCents;
  if (note !== d.note) changes.note = note;
  const changed = Object.keys(changes).length > 1 || by !== r.by;
  const complete = withheld.every((w) => w.record && w.reason.trim());
  const save = async () => {
    setBusy(true); setError("");
    try { onSaved(await postJson<Req>(`/api/write/records-requests/${encodeURIComponent(r.id)}`, changes)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const summary: string[] = [];
  if ("purposeAdequate" in changes) summary.push(`purpose ${purposeAdequate === null ? "undecided" : purposeAdequate ? "adequate" : "not adequate"} under 5225`);
  if ("withheld" in changes) summary.push(`${withheld.length} record kind(s) withheld under 5215`);
  if ("producedOn" in changes) summary.push(producedOn ? `produced ${producedOn}` : "production cleared");
  if ("inspectedOrCopies" in changes) summary.push(how ? `by ${how}` : "how produced cleared");
  if ("feeCents" in changes) summary.push(`fee ${dollars(feeCents)}`);
  if ("note" in changes) summary.push("note");
  return (
    <div className="stack">
      <Clock stages={r.stages} today={today} />
      <div className="grid-2">
        <Card title={`The request from ${r.unit}`}>
          <dl className="rr-facts">
            <dt>Received</dt><dd>{r.receivedOn} via {r.via}{r.years.length > 0 && <> for fiscal {r.years.join(", ")}</>}</dd>
            <dt>Records</dt><dd><ul className="rr-list">{r.records.map((k) => <li key={k}>{label(kinds, k)} <span className="muted">{r.citations[k]}</span></li>)}</ul></dd>
            <dt>Purpose, as stated</dt><dd>{r.purpose ? <blockquote className="rr-quote">{r.purpose}</blockquote> : <span className="muted">none stated</span>}</dd>
            <dt>Standing</dt><dd><Pill word={r.standing} /> {r.dueBy && !d.producedOn && <DueDate iso={r.dueBy} today={today} />}</dd>
          </dl>
          {r.history.length > 0 && <details><summary>History</summary><ul className="rr-list">{r.history.map((h, i) => <li key={i}>{h}</li>)}</ul></details>}
        </Card>
        <Card title="Decisions">
          <p className="muted">What a person decided, recorded here in the person's words. jason decides nothing and does not hand out the list.</p>
          <div className="fields">
            {r.membershipList && (
              <label className="wide">Purpose adequate for the membership list (CIV 5225)
                <select value={purposeAdequate === null ? "" : purposeAdequate ? "yes" : "no"} onChange={(e) => setPurposeAdequate(e.target.value === "" ? null : e.target.value === "yes")}>
                  <option value="">undecided</option><option value="yes">yes, reasonably related to the member's interest</option><option value="no">no</option>
                </select>
              </label>
            )}
            <label>Produced on <input type="date" value={producedOn} onChange={(e) => setProducedOn(e.target.value)} /></label>
            <label>Inspection or copies (CIV 5205) <select value={how} onChange={(e) => setHow(e.target.value as Decisions["inspectedOrCopies"])}><option value="">not yet</option><option value="inspection">inspection</option><option value="copies">copies</option></select></label>
            <label>Fee the member agreed to, in dollars <input inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} /></label>
            <label>Decided by <input value={by} onChange={(e) => setBy(e.target.value)} /></label>
            <label className="wide">Note <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          <div className="rr-withheld">
            <strong>Withheld or redacted (CIV 5215)</strong>
            {withheld.length === 0 && <p className="muted">nothing withheld</p>}
            {withheld.map((w, i) => (
              <div className="fields" key={i}>
                <label>Record <select aria-label={`Withheld record ${i + 1}`} value={w.record} onChange={(e) => setWithheld((xs) => xs.map((x, j) => (j === i ? { ...x, record: e.target.value } : x)))}>
                  {r.records.map((k) => <option key={k} value={k}>{label(kinds, k)}</option>)}
                </select></label>
                <label>Basis, as the person states it <input aria-label={`Withheld reason ${i + 1}`} value={w.reason} onChange={(e) => setWithheld((xs) => xs.map((x, j) => (j === i ? { ...x, reason: e.target.value } : x)))} /></label>
                <button className="wide" onClick={() => setWithheld((xs) => xs.filter((_, j) => j !== i))}>Remove</button>
              </div>
            ))}
            <button onClick={() => setWithheld((xs) => [...xs, { record: r.records[0] ?? "", reason: "" }])}>Withhold a record</button>
          </div>
          {changed && complete && by.trim() && (
            <Confirm busy={busy} onConfirm={save} summary={<p>Record on {r.unit}'s request of {r.receivedOn}: {summary.join("; ") || "the person deciding"}; decided by {by}.</p>}>Record the decisions</Confirm>
          )}
          {withheld.length > 0 && !complete && <p className="notice notice-warn">Each withheld record needs the basis stated; a member may ask for it in writing (CIV 5215(d)).</p>}
          {error && <p className="notice notice-error">{error}</p>}
          {d.producedOn && <p className="muted">Produced {d.producedOn}{d.inspectedOrCopies && <> by {d.inspectedOrCopies}</>}{d.feeCents > 0 && <>, fee {dollars(d.feeCents)}</>}.</p>}
        </Card>
      </div>
    </div>
  );
}

/** Whether the page is in the owner view: the prop, else `?view=owner` in the hash. */
function ownerFromHash(): boolean {
  if (typeof window === "undefined") return false;
  const q = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(q).get("view") === "owner";
}

const OWNER_CAVEATS = [
  "The membership list is shared only for purposes related to membership (CIV 5230).",
  "A request recorded here is received by the association; a person answers it. jason produces nothing on its own.",
];

/** The owner view: the records members may inspect, and a form that records a request for any of them. */
function OwnerRecords({ raw }: { raw: Source }) {
  const cols: Column<Kind>[] = [
    { key: "label", header: "Record" },
    { key: "citation", header: "Civil Code" },
    { key: "files", header: "On the shelf", value: (k) => k.files ?? -1, render: (k) => (k.files == null ? <span className="muted">—</span> : <Badge tone={k.files > 0 ? "good" : "neutral"}>{k.files > 0 ? `${k.files} on file` : "not on file"}</Badge>) },
  ];
  return (
    <div className="stack">
      <Caveats items={OWNER_CAVEATS} />
      <Card title="Request a record">
        <p className="muted">The records members may inspect or copy (CIV 5205). Pick what you need and how you'd like it; the association's clock under CIV 5210 starts when the request is received.</p>
        <RequestForm kinds={raw.kinds} />
      </Card>
      <Card title="Record kinds">
        <DataTable rows={raw.kinds} columns={cols} rowKey={(k) => k.record} searchable={false} />
      </Card>
    </div>
  );
}

/** Members' requests for association records (CIV 5200-5240), against the 5210 clocks, with the decisions a person recorded.
 * In the owner view (`audience="owner"` or `?view=owner`) it is the request form and the record kinds, nothing of other members' requests. */
export function RecordsRequestsView({ audience }: { audience?: "board" | "owner" } = {}) {
  const r = useApi<Source>("/api/records-requests");
  const [open, setOpen] = useState("");
  const [patched, setPatched] = useState<Record<string, Req>>({});
  const [added, setAdded] = useState<Req[]>([]);
  const today = new Date();
  const owner = audience ? audience === "owner" : ownerFromHash();
  return (
    <RemoteView r={r}>
      {(raw) => {
        if (owner) return <OwnerRecords raw={raw} />;
        const rows = [...added, ...raw.requests].map((x) => patched[x.id] ?? x).sort((a, b) => b.receivedOn.localeCompare(a.receivedOn));
        const current = rows.find((x) => x.id === open);
        const cols: Column<Req>[] = [
          { key: "receivedOn", header: "Received", kind: "date" },
          { key: "unit", header: "Unit" },
          { key: "via", header: "Via", render: (x) => <Badge>{x.via}</Badge> },
          { key: "records", header: "Records", render: (x) => <>{x.records.map((k) => label(raw.kinds, k)).join(", ")}{x.membershipList && <> <Badge tone="warn">list</Badge></>}</>, value: (x) => x.records.length },
          { key: "dueBy", header: "Due by (5210)", render: (x) => x.decisions.producedOn ? <Badge tone="good">{`produced ${x.decisions.producedOn}`}</Badge> : <DueDate iso={x.dueBy} today={today} /> },
          { key: "standing", header: "Standing", render: (x) => <Pill word={x.standing} /> },
          { key: "withheld", header: "Withheld", render: (x) => <Findings items={x.decisions.withheld.map((w) => `${label(raw.kinds, w.record)}: ${w.reason}`)} empty="none" />, value: (x) => x.decisions.withheld.length },
          { key: "open", header: "", render: (x) => <button className="link" onClick={(e) => { e.stopPropagation(); setOpen(open === x.id ? "" : x.id); }}>{open === x.id ? "Close" : "Open"}</button> },
        ];
        return (
          <div className="stack">
            <Caveats items={raw.caveats} />
            {raw.note && <p className="notice notice-warn">{raw.note}</p>}
            <Card title={`Records requests (${rows.length})`}>
              {rows.length === 0 ? <p className="muted">No request recorded yet.</p> : <DataTable rows={rows} columns={cols} searchable={false} rowKey={(x) => x.id} selectedKey={open} onSelect={(x) => setOpen(open === x.id ? "" : x.id)} />}
            </Card>
            {current && <RequestPanel key={current.id + current.updated} r={current} kinds={raw.kinds} today={today} onSaved={(n) => setPatched((p) => ({ ...p, [n.id]: n }))} />}
            <ReceiveForm kinds={raw.kinds} vias={raw.vias ?? ["email", "mail", "form"]} onSaved={(n) => { setAdded((xs) => [n, ...xs]); setOpen(n.id); }} />
          </div>
        );
      }}
    </RemoteView>
  );
}
