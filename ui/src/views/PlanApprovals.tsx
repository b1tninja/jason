import { useEffect, useState } from "react";
import { DataTable, Pill, PlanReview, RemoteView, type Column } from "../components";
import { postJson, serverSession, type ApiError, type ServerSession } from "../lib/api";
import { useApi } from "../lib/useApi";
import { STATUS_MEANING, when, type Approval, type AuditEntry, type ChainCheck, type KindFacts, type Recheck } from "../lib/approvals";
import type { Citation } from "../components/Recitation";
import { boardItemHref } from "./BoardItemsView";

/** An approval as a list carries it: the engine's record, or (from `GET /api/approvals`) its summary, where `items` is
 * a count and `byClass` counts the items by class. */
type Listed = Omit<Partial<Approval>, "items"> & Pick<Approval, "id" | "kind" | "title" | "status"> & {
  items?: Approval["items"] | number;
  byClass?: Record<string, number>;
};

/** The engine approvals in `/api/approvals` (`approvals`, or `plans`), told apart from the letters by their `apr-` ids. */
export function engineApprovals(page: unknown): Listed[] {
  const p = (page ?? {}) as { approvals?: unknown; plans?: unknown };
  const rows = Array.isArray(p.approvals) ? p.approvals : Array.isArray(p.plans) ? p.plans : [];
  return rows.filter((r): r is Listed => !!r && typeof r === "object" && typeof (r as Listed).id === "string" && (r as Listed).id.startsWith("apr-"));
}

/** `/api/approvals/<id>`: the engine's approval as the body, or wrapped beside its audit lines, chain check, and re-plan;
 * with the kind's declared facts (`kindFacts`, null for a kind the checkout no longer has), whether a second person must
 * sign (`needsSecond`), and each item's rule recited (`recitations`). */
interface Detail {
  found?: boolean; note?: string; approval?: Approval; audit?: AuditEntry[]; chain?: ChainCheck | null; recheck?: Recheck | null; check?: Recheck | null;
  kindFacts?: KindFacts | null; needsSecond?: boolean | null; recitations?: Record<string, Citation>;
}

export function approvalOf(d: Detail & Partial<Approval>): Approval | null {
  if (d.approval && Array.isArray(d.approval.items)) return d.approval;
  return typeof d.id === "string" && Array.isArray(d.items) ? (d as Approval) : null;
}

const OPEN = ["planned", "in_review", "approved", "partially_approved", "applying", "failed"];

function counts(a: Listed): string {
  const items = a.items;
  const n = Array.isArray(items)
    ? (cls: string) => items.filter((i) => i.class === cls).length
    : a.byClass
      ? (cls: string) => a.byClass?.[cls] ?? 0
      : null;
  if (!n) return "";
  const parts = [`${n("approvable")} to decide`, n("held_for_board") ? `${n("held_for_board")} held` : "", n("for_a_person") ? `${n("for_a_person")} for a person` : ""];
  return parts.filter(Boolean).join(" · ");
}

/** `GET /api/approvals/audit?approval=&verify=1`: the approval's audit lines and the chain check, in whichever of the
 * plain shapes the route answers. */
export function auditOf(d: unknown): { entries: AuditEntry[]; chain: ChainCheck | null } {
  if (Array.isArray(d)) return { entries: d as AuditEntry[], chain: null };
  const o = (d ?? {}) as Record<string, unknown>;
  const entries = (["entries", "audit", "lines", "events"].map((k) => o[k]).find(Array.isArray) as AuditEntry[] | undefined) ?? [];
  const v = (o.verify ?? o.chain) as ChainCheck | undefined;
  const chain = v && typeof v === "object" && typeof v.ok === "boolean" ? v : typeof o.ok === "boolean" ? { ok: o.ok, line: o.line as number | undefined, why: o.why as string | undefined } : null;
  return { entries, chain };
}

/** `POST /api/approvals/<id>/check`: the re-plan compared, `engine.Recheck` as JSON. */
function recheckOf(d: unknown): Recheck | null {
  const o = (d ?? {}) as Partial<Recheck> & { recheck?: Recheck };
  if (o.recheck && Array.isArray(o.recheck.changed)) return o.recheck;
  return Array.isArray(o.changed) ? (o as Recheck) : null;
}

/** One plan, loaded from `/api/approvals/<id>` and reviewed with `PlanReview`, its history from
 * `/api/approvals/audit?approval=<id>&verify=1`. Each step posts to `/api/approvals/<id>/<step>` in the signed-in
 * person's name, with the server's write token: `decide` `{items, decision, by, reason}`, `submit` and `confirm`
 * `{by}`, `decline` and `withdraw` `{by, reason}`, `check` (re-plan live, writing nothing), and `apply` `{by, confirm:
 * fingerprint}`, offered only when the server allows it (`applyEnabled`). A stale apply answers 409 with the plan that
 * superseded it, which opens. `onLoaded` passes each loaded approval up, so the list's row follows. */
export function PlanPanel({ id, me, onOpen, onLoaded }: { id: string; me: string; onOpen: (id: string) => void; onLoaded?: (a: Approval) => void }) {
  const base = `/api/approvals/${encodeURIComponent(id)}`;
  const r = useApi<Detail & Partial<Approval>>(base);
  const log = useApi<unknown>(`/api/approvals/audit?approval=${encodeURIComponent(id)}&verify=1`);
  const [server, setServer] = useState<ServerSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recheck, setRecheck] = useState<Recheck | null>(null);
  const loaded = r.status === "ready" ? approvalOf(r.data) : null;
  useEffect(() => { if (loaded) onLoaded?.(loaded); }, [loaded, onLoaded]);
  useEffect(() => { let on = true; serverSession().then((s) => on && setServer(s)); return () => { on = false; }; }, []);
  const step = (name: string, pick: (b: Record<string, unknown>) => Record<string, unknown>) => async (body?: object) => {
    setBusy(true); setError("");
    try {
      const out = await postJson<unknown>(`${base}/${name}`, pick((body ?? {}) as Record<string, unknown>));
      if (name === "check") { setRecheck(recheckOf(out)); return; }
      setRecheck(null);
      r.reload(); log.reload();
    } catch (e) {
      const err = e as ApiError;
      const body = (err.body ?? {}) as { supersededBy?: string; changed?: Recheck["changed"] };
      if (err.status === 409 && body.supersededBy) {
        setError(`${err.message}. Nothing was written; the plan was superseded by ${body.supersededBy}, opened now.`);
        onOpen(body.supersededBy);
      } else setError(err.message);
      throw e;
    } finally {
      setBusy(false);
    }
  };
  const { entries, chain } = log.status === "ready" ? auditOf(log.data) : { entries: [], chain: null };
  const applyBlocked = !server ? "" : server.applyEnabled ? "" : "the server was started without --allow-apply.";
  return (
    <RemoteView r={r}>
      {(d) => {
        const a = approvalOf(d);
        if (!a) throw new Error("not an approval");
        return (
          <PlanReview approval={a} me={me} audit={entries.length ? entries : d.audit} chain={chain ?? d.chain} recheck={recheck ?? d.recheck ?? d.check}
            kind={d.kindFacts ?? undefined} twoPerson={!!d.kindFacts?.twoPerson}
            maxAgeHours={d.kindFacts?.maxAgeHours} recitations={d.recitations} boardHref={boardItemHref}
            busy={busy} error={error} onOpen={onOpen}
            onDecide={step("decide", ({ items, decision, by, reason }) => ({ items, decision, by, reason }))}
            onSubmit={step("submit", ({ by }) => ({ by }))}
            onConfirmSecond={step("confirm", ({ by }) => ({ by }))}
            onDecline={step("decline", ({ by, reason }) => ({ by, reason }))}
            onWithdraw={step("withdraw", ({ by, reason }) => ({ by, reason }))}
            onCheck={server?.liveChecks === false ? undefined : () => step("check", () => ({}))()}
            onApply={step("apply", ({ by, confirm }) => ({ by, confirm }))} applyBlocked={applyBlocked} />
        );
      }}
    </RemoteView>
  );
}

/** The approvals engine's plans of writes outside jason, open ones first, beside the letters; one opens to its review
 * (`open`, kept by the screen so a reload of the letters keeps it). */
export function PlanApprovals({ page, me, open, onOpen }: { page: unknown; me: string; open: string; onOpen: (id: string) => void }) {
  const [fresh, setFresh] = useState<Record<string, Approval>>({});
  const listed = engineApprovals(page);
  const rows: Listed[] = [
    ...Object.values(fresh).filter((a) => !listed.some((l) => l.id === a.id)),
    ...listed.map((l) => fresh[l.id] ?? l),
  ].sort((x, y) => Number(!OPEN.includes(x.status)) - Number(!OPEN.includes(y.status)) || String(y.requestedAt ?? "").localeCompare(String(x.requestedAt ?? "")));
  const [onLoaded] = useState(() => (a: Approval) => setFresh((f) => (f[a.id] === a ? f : { ...f, [a.id]: a })));
  const columns: Column<Listed>[] = [
    { key: "title", header: "Plan", render: (a) => <><strong>{a.title}</strong><br /><span className="muted">{a.kind} · {a.id}</span></> },
    { key: "status", header: "Status", render: (a) => <Pill word={a.status} meaning={STATUS_MEANING[a.status]} /> },
    { key: "items", header: "Items", value: (a) => counts(a) },
    { key: "requestedBy", header: "Asked by", value: (a) => a.requestedBy ?? "" },
    { key: "readAt", header: "Read live", kind: "date", value: (a) => when(a.readAt) },
  ];
  return (
    <section className="approvals-group" aria-label="Plans of writes">
      <h2>Plans of writes</h2>
      <p className="muted">Changes jason planned outside itself (PayHOA tags, request completions), each decided item by item by a named person. jason plans; it never approves.</p>
      {rows.length === 0 ? (
        <p className="muted">No plan of writes on disk. <code className="chip">jason approvals plan owner-info-tags --by NAME</code> makes one.</p>
      ) : (
        <DataTable rows={rows} columns={columns} rowKey={(a) => a.id} selectedKey={open} onSelect={(a) => onOpen(a.id)} caption="Plans of writes, open first" />
      )}
      {open && (
        <section className="approvals-open" aria-label="Open plan">
          <div className="row wrap"><strong>{open}</strong><button className="link" onClick={() => onOpen("")}>Close</button></div>
          <PlanPanel key={open} id={open} me={me} onOpen={onOpen} onLoaded={onLoaded} />
        </section>
      )}
    </section>
  );
}
