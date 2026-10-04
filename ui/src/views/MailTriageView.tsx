import { useState } from "react";
import { Badge, Card, Caveats, Confirm, Doc, DueDate, EmptyState, Pill, RemoteView, Tabs, type DocRef } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import "./choices.css";

export interface TriageChoice { mailId: string; choice: string; by: string; on: string; note: string; history: string[] }
export interface Letter {
  mailId: string | number; received: string; sender: string; from?: string | null; kind: string; urgency: string; evidence?: string[];
  deadlines?: { date: string; label: string }[]; status?: string; folder?: string; scanned?: boolean; summary?: string[]; choice: TriageChoice | null;
  /** The letter's document (docs/console/doc-component.md): the scan, `mail/<id>/contents.pdf`, else the envelope (P2). */
  scan?: DocRef | null;
  /** In place of `scan` for a letter that carries a credential (P4): "Held: … it opens in no screen". */
  held?: string;
}
export interface MailTriage {
  found?: boolean; note?: string; since?: string; items?: number; byKind?: Record<string, number>;
  act: Letter[]; review: Letter[]; unscanned: Letter[]; choices: string[]; chosen: number; caveats?: string[];
}

const LABELS: Record<string, string> = { scan: "Scan", forward: "Forward", shred: "Shred", discard: "Discard", keep: "Keep at the service" };

/** One letter: what the brief knows about it, its scan (or envelope) as a row, the choice recorded, and the five choices
 * each behind a confirm. Read opens the letter inline beside the choices, so a person reads it before choosing; the
 * scan is P2, so it shows only on "Show the document", one logged view. */
function LetterRow({ l, who, onSaved, reading, onRead }: { l: Letter; who: string; onSaved: (c: TriageChoice) => void; reading: boolean; onRead: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const id = String(l.mailId);
  const choose = async (choice: string) => {
    setBusy(true); setError("");
    try { onSaved(await postJson<TriageChoice>(`/api/write/mail-triage/${encodeURIComponent(id)}`, { choice, by: who, note: "" })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const sender = l.from || l.sender;
  return (
    <article className="choice-letter" aria-label={`letter ${id}`}>
      <div className="meta">
        <strong>{sender}</strong>
        <span className="muted">received {l.received}</span>
        <Badge>{l.kind}</Badge>
        <Pill word={l.urgency} />
        {l.scanned === false && <Badge tone="warn">not scanned</Badge>}
        {l.choice && <span className="choice-recorded"><Badge tone="good">{l.choice.choice}</Badge> <span className="muted">by {l.choice.by} on {l.choice.on.slice(0, 10)}</span></span>}
      </div>
      {!!l.deadlines?.length && <div className="meta">{l.deadlines.map((d, i) => <span key={i}>{d.label} <DueDate iso={d.date} /></span>)}</div>}
      {!!l.evidence?.length && <p className="muted">{l.evidence.join("; ")}</p>}
      {!!l.summary?.length && <ul className="choice-steps">{l.summary.map((s, i) => <li key={i}>{s}</li>)}</ul>}
      {!l.scan && l.held && <p className="notice notice-warn mail-held">{l.held}</p>}
      {l.scan && (
        <>
          <Doc doc={l.scan} variant="row" />
          <p><button type="button" className="link" aria-pressed={reading} onClick={onRead}>{reading ? "Close the letter" : "Read it beside the choices"}</button></p>
        </>
      )}
      <div className={reading && l.scan ? "grid-2" : undefined}>
        {reading && l.scan && <Doc doc={l.scan} variant="inline" headingLevel={4} />}
        <div>
          {who.trim() ? (
            <div className="choice-buttons" role="group" aria-label={`Choices for letter ${id}`}>
              {["scan", "forward", "shred", "discard", "keep"].map((c) => (
                <Confirm key={c} busy={busy} onConfirm={() => choose(c)} summary={<p>Record "{c}" for the letter from {sender} ({l.received}), chosen by {who.trim()}. jason records the choice; a person carries it out at the mail service.</p>}>{LABELS[c]}</Confirm>
              ))}
            </div>
          ) : <p className="muted">Enter your name above to record a choice.</p>}
          {error && <p className="notice notice-error">{error}</p>}
        </div>
      </div>
    </article>
  );
}

function Lane({ rows, who, onSaved, reading, setReading }: { rows: Letter[]; who: string; onSaved: (c: TriageChoice) => void; reading: string; setReading: (id: string) => void }) {
  if (!rows.length) return <EmptyState>Nothing in this lane.</EmptyState>;
  return (
    <div>
      {rows.map((l) => {
        const id = String(l.mailId);
        return <LetterRow key={id} l={l} who={who} onSaved={onSaved} reading={reading === id} onRead={() => setReading(reading === id ? "" : id)} />;
      })}
    </div>
  );
}

/** The mail brief's lanes with a person's choice recorded beside each letter. jason scans, forwards, shreds, and discards nothing. */
export function MailTriageView() {
  const [days, setDays] = useState(30);
  const r = useApi<MailTriage>(`/api/mail-triage?days=${days}`);
  const [tab, setTab] = useState("act");
  const [who, setWho] = useState("");
  const [patched, setPatched] = useState<Record<string, TriageChoice>>({});
  const [reading, setReading] = useState("");
  const onSaved = (c: TriageChoice) => setPatched((p) => ({ ...p, [c.mailId]: c }));
  const overlay = (rows: Letter[]) => rows.map((l) => ({ ...l, choice: patched[String(l.mailId)] ?? l.choice }));
  return (
    <RemoteView r={r}>
      {(d) => {
        const act = overlay(d.act), review = overlay(d.review), unscanned = overlay(d.unscanned);
        return (
          <div className="stack">
            <p className="notice notice-warn">jason scans, forwards, shreds, and discards nothing. The choice is recorded here for the person who acts on it at the mail service, which may bill for a scan or a forward.</p>
            <Card title="Mail to triage" actions={<label>last <input type="number" min={1} value={days} onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 30))} style={{ width: "4rem" }} /> days</label>}>
              <div className="fields">
                <label>Your name <input placeholder="your name" value={who} onChange={(e) => setWho(e.target.value)} /></label>
              </div>
              {d.byKind && <p className="row wrap">{Object.entries(d.byKind).map(([k, n]) => <span key={k}><Badge>{k}</Badge> {n}</span>)}</p>}
            </Card>
            <Tabs active={tab} onChange={setTab} tabs={[
              { id: "act", label: `Act (${act.length})`, content: <Lane rows={act} who={who} onSaved={onSaved} reading={reading} setReading={setReading} /> },
              { id: "review", label: `Review (${review.length})`, content: <Lane rows={review} who={who} onSaved={onSaved} reading={reading} setReading={setReading} /> },
              { id: "unscanned", label: `Not scanned (${unscanned.length})`, content: <Lane rows={unscanned} who={who} onSaved={onSaved} reading={reading} setReading={setReading} /> },
            ]} />
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
