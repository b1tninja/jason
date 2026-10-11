import { maskContact, safeAddress, type HistoryEvent } from "../lib/work";

const stamp = (at: string) => (at ? `${at.slice(0, 10)} ${at.slice(11, 16)}`.trim() : "");

/** The evidence addresses an event kept, and the differences it found: only addresses and hashes, never contents. */
function evidenceOf(e: HistoryEvent): { address: string; note: string }[] {
  const out: { address: string; note: string }[] = [];
  const kept = e.detail?.evidence;
  if (Array.isArray(kept)) for (const x of kept as { address?: unknown; hash?: unknown }[]) out.push({ address: safeAddress(String(x.address ?? "")), note: x.hash ? String(x.hash).slice(0, 12) : "" });
  const diff = e.detail?.differences;
  if (Array.isArray(diff)) for (const x of diff as { address?: unknown; was?: unknown; now?: unknown }[])
    out.push({ address: safeAddress(String(x.address ?? "")), note: `was ${String(x.was ?? "nothing").slice(0, 12)}, now ${String(x.now ?? "nothing").slice(0, 12)}` });
  return out;
}

/** The event log, newest first, with who and when. A correction is a later entry, never an edit. An event a read of the run
 * found but nobody has recorded yet is marked as such. Text is the server's sentence, with any contact detail masked once
 * more here. With `print`, the same events oldest first for the board's record, with each event's evidence addresses. */
export function RunHistory({ events, print = false }: { events: readonly HistoryEvent[]; print?: boolean }) {
  if (!events.length) return <p className="muted">No events yet.</p>;
  const sorted = [...events].sort((a, b) => (print ? a.n - b.n : b.n - a.n));
  return (
    <ol className={`work-history${print ? " work-history-print" : ""}`}>
      {sorted.map((e) => {
        const ev = print ? evidenceOf(e) : [];
        return (
          <li key={`${e.n}-${e.kind}`} className={e.pending ? "work-history-pending" : undefined}>
            <time dateTime={e.at} className="work-history-at">{stamp(e.at)}</time>{" "}
            <span className="work-history-text">{maskContact(e.text)}</span>
            {e.pending && <span className="badge badge-neutral work-history-flag">found by this read, not yet recorded</span>}
            {print && <span className="muted"> (event {e.n}, {maskContact(e.by || "?")})</span>}
            {ev.length > 0 && (
              <ul className="work-history-evidence">
                {ev.map((x, i) => <li key={i}><code className="chip">{x.address}</code>{x.note && <span className="muted"> {x.note}</span>}</li>)}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}
