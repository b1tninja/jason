import { useState } from "react";
import { Confirm } from "./Confirm";
import { postJson } from "../lib/api";

/** A record kind a member may ask for, as `/api/records-requests` lists them (`kinds`). */
export interface RequestKind { record: string; label: string; citation?: string; meaning?: string }

/** What the write answers: the request as recorded, with its section 5210 clock. */
export interface RecordedRequest {
  id: string;
  receivedOn: string;
  unit: string;
  records: string[];
  dueBy: string;
  stages: { key: string; label: string; date?: string; done?: boolean }[];
}

export const DELIVERIES = ["By email", "Inspect in person", "Mailed copies"] as const;
export type Delivery = (typeof DELIVERIES)[number];

const MEMBERSHIP_LIST = "membership_list";
const VIA = "form"; // how the request came: through the owner view
const BY = "the member, through the owner view";

/** An owner's request for association records (CIV 5200): pick the records, say how to deliver them, then `Confirm`.
 * Send stays disabled until a record is picked (and the unit is given, which the store needs). The request posts to
 * `/api/write/records-requests/new`; the notice afterwards repeats the CIV 5210 deadline the association now owes. */
export function RequestForm({ kinds, email, today, onSent }: {
  kinds: readonly RequestKind[];
  /** Where a written request would otherwise go; named in the summary when known. */
  email?: string;
  /** The day received; defaults to today. */
  today?: string;
  onSent?: (req: RecordedRequest) => void;
}) {
  const day = today ?? new Date().toISOString().slice(0, 10);
  const [picked, setPicked] = useState<string[]>([]);
  const [delivery, setDelivery] = useState<Delivery>(DELIVERIES[0]);
  const [unit, setUnit] = useState("");
  const [purpose, setPurpose] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<RecordedRequest | null>(null);

  const toggle = (r: string) => { setSent(null); setPicked((xs) => (xs.includes(r) ? xs.filter((x) => x !== r) : [...xs, r])); };
  const labelOf = (r: string) => kinds.find((k) => k.record === r)?.label ?? r.replace(/_/g, " ");
  const list = picked.includes(MEMBERSHIP_LIST);
  const needsPurpose = list && !purpose.trim();
  const canSend = picked.length > 0 && unit.trim().length > 0 && !needsPurpose;

  const send = async () => {
    setBusy(true);
    setError("");
    try {
      const req = await postJson<RecordedRequest>("/api/write/records-requests/new", {
        receivedOn: day, unit: unit.trim(), via: VIA, records: picked, purpose: purpose.trim(), years: [], by: BY, delivery,
      });
      setSent(req);
      setPicked([]);
      onSent?.(req);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const summary = `Record a written request${email ? ` to ${email}` : ""} from ${unit.trim()} for ${picked.length} ${picked.length === 1 ? "record" : "records"} (${picked.map(labelOf).join(", ")}), ${delivery.toLowerCase()}. The association's clock under CIV 5210 starts from today, ${day}.`;

  return (
    <div className="request-form stack">
      <fieldset className="rf-set">
        <legend>Which records</legend>
        <div className="rf-picks">
          {kinds.map((k) => (
            <label key={k.record} title={k.meaning || undefined}>
              <input type="checkbox" checked={picked.includes(k.record)} onChange={() => toggle(k.record)} />
              <span>{k.label}{k.citation && <span className="muted"> {k.citation}</span>}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="rf-set">
        <legend>How you'd like them</legend>
        <div className="row wrap rf-deliveries">
          {DELIVERIES.map((d) => (
            <label key={d}>
              <input type="radio" name="delivery" checked={delivery === d} onChange={() => { setDelivery(d); setSent(null); }} />
              <span>{d}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="fields">
        <label>Your unit <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Unit 12" /></label>
        <label className="wide">
          {list ? "Purpose, in your words (the membership list asks for one, CIV 5225)" : "Purpose, in your words (optional)"}
          <textarea rows={2} value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        </label>
      </div>
      <div className="row wrap">
        {canSend ? (
          <Confirm busy={busy} onConfirm={send} summary={<p>{summary}</p>}>Send request</Confirm>
        ) : (
          <>
            <button className="primary" disabled>Send request</button>
            <span className="muted">
              {picked.length === 0 ? "Pick at least one record." : !unit.trim() ? "Give your unit." : "The membership list asks for a stated purpose."}
            </span>
          </>
        )}
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      {sent && (
        <p className="notice notice-good" role="status">
          Request recorded {sent.receivedOn} for {sent.unit}{sent.records.length ? ` (${sent.records.map(labelOf).join(", ")})` : ""}.
          {sent.dueBy ? ` The association has until ${sent.dueBy} to produce the records (CIV 5210).` : " The association's deadline under CIV 5210 runs from today."}
          {sent.stages.filter((s) => s.date && !s.done).length > 0 && (
            <> Due dates: {sent.stages.filter((s) => s.date && !s.done).map((s) => `${s.label} by ${s.date}`).join("; ")}.</>
          )}
        </p>
      )}
    </div>
  );
}
