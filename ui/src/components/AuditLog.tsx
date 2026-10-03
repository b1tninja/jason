import { Timeline, type TimelineEvent } from "./Timeline";
import { personName, plural, short, type AuditEntry, type ChainCheck } from "../lib/approvals";

const TONE: Partial<Record<AuditEntry["event"], TimelineEvent["tone"]>> = {
  "item.applied": "good", "approval.applied": "good", "cli.applied": "good", "approval.confirmed": "good",
  "item.failed": "bad", "approval.failed": "bad", "plan.failed": "bad", "apply.refused": "bad",
  "item.uncertain": "warn", "item.blocked": "warn", "approval.superseded": "warn", "approval.declined": "warn",
};

function count(result: unknown): number {
  return result && typeof result === "object" ? Object.values(result as Record<string, unknown>).reduce<number>((n, v) => n + (typeof v === "number" ? v : 0), 0) : 0;
}

function counts(result: unknown): string {
  return result && typeof result === "object"
    ? Object.entries(result as Record<string, unknown>).filter(([, v]) => typeof v === "number").map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ")
    : "";
}

/** What the log says happened, in its own words. jason appears only as the planner; every other act names its person. */
export function auditWords(e: AuditEntry): string {
  const who = personName(e.actor);
  const n = e.items?.length ?? 0;
  const what = e.label ? `${e.label}: ${e.op ?? ""} ${e.value ?? ""}`.trim() : e.item ?? "";
  switch (e.event) {
    case "plan.created": return `Planned by jason: ${plural(count(e.result), "item", "items")} (asked by ${who})`;
    case "plan.failed": return `Planning failed (asked by ${who})`;
    case "item.decided": return `${who} ${String(e.result ?? "decided")} ${plural(n, "change", "changes")}`;
    case "approval.submitted": return `${who} signed: ${String(e.result ?? "").replace(/_/g, " ")}${n ? `, ${plural(n, "change", "changes")} approved` : ""}`;
    case "approval.confirmed": return `${who} confirmed as the second person`;
    case "approval.declined": return `${who} declined and sent it back to review`;
    case "apply.started": return `${who} started the apply (${plural(n, "approved change", "approved changes")})`;
    case "apply.refused": return `Apply refused (${who} asked)`;
    case "item.applying": return `Writing ${what}`;
    case "item.applied": return `Applied ${what}`;
    case "item.failed": return `Failed ${what}`;
    case "item.uncertain": return `Uncertain ${what}`;
    case "item.blocked": return `Blocked ${what}`;
    case "item.not_applied": return `Not applied ${what}`;
    case "approval.applied": return `Applied: ${counts(e.result)} (${who} applied)`;
    case "approval.failed": return `Apply failed: ${counts(e.result)} (${who} applied)`;
    case "approval.superseded": return `Superseded`;
    case "approval.withdrawn": return `${who} withdrew it`;
    case "cli.applied": return `${who} applied it from a terminal`;
    default: return String(e.event);
  }
}

/** Whether each shown line names the hash of the line before (only for a contiguous run of the whole log). The hashes
 * themselves are checked by `jason approvals audit --verify` (`chain`). */
function links(entries: readonly AuditEntry[]): { ok: boolean; at?: number } | null {
  if (entries.length < 2 || entries.some((e, n) => n > 0 && e.seq !== entries[n - 1].seq + 1)) return null;
  for (let n = 1; n < entries.length; n++) if (entries[n].prev !== entries[n - 1].hash) return { ok: false, at: entries[n].seq };
  return { ok: true };
}

/** An approval's history (or the whole log's), oldest first, as a `Timeline`: the time (UTC, as logged), who, the event in
 * the log's words, the fingerprint it was taken on, and the detail. `approval` narrows to one approval; `compact` leaves
 * out the intent lines (`item.applying`). `chain` is the server's check of the hash chain. */
export function AuditLog({ entries, approval, compact = false, chain }: {
  entries: readonly AuditEntry[]; approval?: string; compact?: boolean; chain?: ChainCheck | null;
}) {
  const shown = entries.filter((e) => (!approval || e.approval === approval) && !(compact && e.event === "item.applying"));
  const linked = approval || compact ? null : links(shown);
  const events: TimelineEvent[] = shown.map((e) => ({
    id: String(e.seq),
    date: `${e.at.slice(0, 16).replace("T", " ")}`,
    title: auditWords(e),
    tone: TONE[e.event] ?? "neutral",
    detail: [e.detail, e.fingerprint ? `fingerprint ${short(e.fingerprint)}` : "", `line ${e.seq}`, e.via ? `via ${e.via}` : ""].filter(Boolean).join(" · "),
  }));
  return (
    <section className="audit-log" aria-label="History">
      <Timeline events={events} />
      {compact && entries.some((e) => e.event === "item.applying" && (!approval || e.approval === approval)) && (
        <p className="muted">Each write's intent line (item.applying) is in the full log.</p>
      )}
      {chain && (
        <p className={chain.ok ? "audit-chain" : "audit-chain audit-broken"} role={chain.ok ? undefined : "alert"}>
          {chain.ok ? `Chain verified${chain.why ? `: ${chain.why}` : ""}.` : `Chain broken at line ${chain.line ?? "?"}${chain.why ? `: ${chain.why}` : ""}.`}
        </p>
      )}
      {!chain && linked && (
        <p className={linked.ok ? "muted" : "audit-chain audit-broken"} role={linked.ok ? undefined : "alert"}>
          {linked.ok
            ? `Each of these ${shown.length} lines names the line before it; jason approvals audit --verify checks the hashes.`
            : `Line ${linked.at} does not name the line before it: run jason approvals audit --verify.`}
        </p>
      )}
      <p className="muted">Times are UTC, as logged.</p>
    </section>
  );
}
