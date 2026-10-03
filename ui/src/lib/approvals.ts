/** The approvals engine's JSON (`src/jason/approvals/schemas/*.schema.json`, `jason approvals show ID --json`), typed as
 * the engine writes it, and the small pure rules the screen applies before the server does. The server enforces every
 * rule; these say so sooner. Field names are the engine's, so a view passes the body through with no mapping. */

export type ApprovalStatus =
  | "planned" | "in_review" | "approved" | "partially_approved" | "applying" | "applied" | "failed" | "superseded" | "withdrawn";
export type ItemClass = "approvable" | "held_for_board" | "for_a_person" | "confirm_with_owner" | "informational";
export type ItemDecision = "undecided" | "approved" | "rejected" | "held";
export type DecisionWord = Exclude<ItemDecision, "undecided">;
export type ItemResult = "pending" | "applied" | "not_applied" | "changed" | "blocked" | "failed" | "uncertain";
export type Via = "cli" | "console";

/** `{label, address}`: a record, a citation `jason cite` resolves, or a command. */
export interface EvidenceRef { label: string; address?: string }

/** What an item changes: a value added to or removed from a field, or a field set from one value to another. */
export interface Change { op: "add" | "remove" | "set"; field: string; value?: string; before?: string; after?: string; text?: string }

/** One change in an approval (plan-item.schema.json). */
export interface PlanItem {
  id: string; op: string; target: string; label: string; value: string; why: string; group?: string;
  change?: Change | null; rule?: string; evidence?: EvidenceRef[]; basis: string; class: ItemClass; boardItem?: string;
  dependsOn?: string[]; highStakes?: boolean; costCents?: number; decision: ItemDecision; decidedBy?: string;
  decidedAt?: string; reason?: string; result: ItemResult; resultDetail?: string;
}

/** One decision as a named person made it (decision.schema.json). */
export interface DecisionRecord { by: string; at: string; items: string[]; decision: DecisionWord; reason?: string; fingerprint: string; via?: Via }

/** A person's signature on a plan fingerprint (decision.schema.json#/$defs/signature). */
export interface Signature { name: string; at: string; fingerprint: string; role?: string; via?: Via }

export interface ApprovalClock { what?: string; due?: string; daysLeft?: number }

/** One plan of writes outside jason (approval.schema.json). */
export interface Approval {
  id: string; kind: string; title: string; status: ApprovalStatus; scope?: Record<string, unknown>; profile?: string;
  fingerprint: string; readAt: string; requestedBy: string; requestedAt: string; requestedVia?: Via; evidence?: EvidenceRef[];
  items: PlanItem[]; decisions: DecisionRecord[]; first?: Signature | null; second?: Signature | null;
  costCents?: number | null; clock?: ApprovalClock | null; summary?: Record<string, unknown>; result?: Record<string, unknown>;
  supersedes?: string; supersededBy?: string; notes?: string[];
}

export type AuditEvent =
  | "plan.created" | "plan.failed" | "item.decided" | "approval.submitted" | "approval.confirmed" | "approval.declined"
  | "apply.started" | "apply.refused" | "item.applying" | "item.applied" | "item.failed" | "item.uncertain" | "item.blocked"
  | "item.not_applied" | "approval.applied" | "approval.failed" | "approval.superseded" | "approval.withdrawn" | "cli.applied";

/** One line of approvals/audit.jsonl (audit-entry.schema.json). */
export interface AuditEntry {
  seq: number; at: string; event: AuditEvent; os_user: string; approval?: string; kind?: string; actor?: string; via?: Via;
  role?: string; fingerprint?: string; item?: string; items?: string[]; op?: string; target?: string; label?: string;
  value?: string; basis?: string; result?: unknown; detail?: string; prev: string; hash: string;
}

/** `audit.verify`: whether the hash chain is whole, and where it broke. */
export interface ChainCheck { ok: boolean; line?: number; why?: string }

/** `engine.Changed`: an approved item whose basis moved, is gone, or is now held, found by a re-plan. */
export interface ChangedItem { id: string; op: string; label: string; then: string; now: string; why: string }

/** `engine.Recheck`: a re-plan compared with the approval (what `jason approvals apply ID` prints without --yes). */
export interface Recheck { changed: ChangedItem[]; new?: PlanItem[] | number; then?: string; now?: string; problems?: string[] }

/** A body a decision, signature, or re-plan posts. `by` is a named person; jason never signs. */
export interface DecideBody { items: string[]; decision: DecisionWord; reason: string; by: string; fingerprint: string; via: Via }
export interface SignBody { by: string; fingerprint: string; via: Via; reason?: string }

// --- names --------------------------------------------------------------------------------------------------------------

/** A name as typed, trimmed with inner spaces collapsed. */
export function cleanName(name: string | null | undefined): string {
  return String(name ?? "").replace(/\s+/g, " ").trim();
}

/** The same person: compared case-blind with spacing ignored (the engine's `same_person`, plus collapsed inner spaces). */
export function sameName(a: string | null | undefined, b: string | null | undefined): boolean {
  const x = cleanName(a).toLocaleLowerCase(), y = cleanName(b).toLocaleLowerCase();
  return !!x && !!y && x === y;
}

/** jason plans; it never decides, signs, confirms, or applies. */
export function isJason(name: string | null | undefined): boolean {
  return sameName(name, "jason");
}

/** Why a signer's name is refused, or "" when it may sign. `refused` are the names that may not (the first signer, the
 * requester). */
export function signerProblem(name: string, refused: readonly (string | null | undefined)[] = []): string {
  const who = cleanName(name);
  if (!who) return "Enter your full name to sign.";
  if (isJason(who)) return "jason never signs: give a person's full name.";
  const same = refused.find((r) => sameName(r, who));
  return same ? `${same} already signed or asked for this plan: a second, distinct person confirms.` : "";
}

/** An actor as the audit log names it: a person, `os:<user>` when none was named, or nothing. Never jason as a signer. */
export function personName(actor: string | null | undefined): string {
  const who = cleanName(actor);
  if (!who || isJason(who)) return "(no person named)";
  if (who.startsWith("os:")) return `${who.slice(3)} (operating-system user; no name given)`;
  return who;
}

// --- reading the plan ---------------------------------------------------------------------------------------------------

export const short = (fingerprint: string | null | undefined): string => String(fingerprint ?? "").slice(0, 12);

/** When, as a reader sees it: "2026-10-03 18:38 UTC". */
export function when(iso: string | null | undefined): string {
  const s = String(iso ?? "");
  if (!s) return "";
  const utc = /(\+00:00|Z)$/.test(s);
  return s.slice(0, 16).replace("T", " ") + (utc ? " UTC" : "");
}

export const SECTIONS: { cls: ItemClass; title: string; note: string }[] = [
  { cls: "approvable", title: "To decide", note: "" },
  { cls: "held_for_board", title: "Held for the board", note: "Never approvable: the board decides first." },
  { cls: "for_a_person", title: "For a person", note: "Never approvable: a person does these in the system itself." },
  { cls: "confirm_with_owner", title: "Confirm with the owner first", note: "Never approvable: ask the owner first." },
  { cls: "informational", title: "What follows", note: "Nothing to decide: what happens, or stays open, and why." },
];

export const STATUS_MEANING: Record<ApprovalStatus, string> = {
  planned: "jason made the plan; nobody has decided an item",
  in_review: "at least one item decided, not yet signed",
  approved: "signed: every approvable item approved",
  partially_approved: "signed: some approved, the rest rejected or held",
  applying: "the re-plan matched; writes under way",
  applied: "every approved item applied",
  failed: "one or more approved items failed; waits for a person",
  superseded: "the live state changed, or a newer plan replaced it",
  withdrawn: "withdrawn before apply, or nothing was approved",
};

export const RESULT_WORDS: Record<ItemResult, string> = {
  pending: "pending", applied: "applied", not_applied: "not applied", changed: "changed since review",
  blocked: "blocked", failed: "failed", uncertain: "uncertain",
};

/** Items by `group` (one owner), in plan order. */
export function groupItems(items: readonly PlanItem[]): { group: string; items: PlanItem[] }[] {
  const out = new Map<string, PlanItem[]>();
  for (const i of items) {
    const g = i.group || i.label;
    out.set(g, [...(out.get(g) ?? []), i]);
  }
  return [...out].map(([group, rows]) => ({ group, items: rows }));
}

export function isApprovable(i: PlanItem): boolean {
  return i.class === "approvable";
}

/** Items a person may still decide: approvable, while the plan is planned or in review. */
export function decidable(a: Approval): boolean {
  return a.status === "planned" || a.status === "in_review";
}

export interface Tally { approvable: number; approved: number; rejected: number; held: number; undecided: number }

export function tally(a: Pick<Approval, "items">): Tally {
  const rows = a.items.filter(isApprovable);
  const n = (d: ItemDecision) => rows.filter((i) => i.decision === d).length;
  return { approvable: rows.length, approved: n("approved"), rejected: n("rejected"), held: n("held"), undecided: n("undecided") };
}

/** A second, distinct person signs: a two-person kind (`twoPerson`, from the kind's registry row), or an approved item
 * that is high stakes (the engine's `needs_second`). */
export function needsSecond(a: Pick<Approval, "items">, twoPerson = false): boolean {
  return twoPerson || a.items.some((i) => isApprovable(i) && i.decision === "approved" && !!i.highStakes);
}

/** The items `item` waits on that are neither approved nor among `chosen`: approving it is refused until they are. */
export function waitsOn(item: PlanItem, a: Pick<Approval, "items">, chosen: readonly string[] = []): PlanItem[] {
  const by = new Map(a.items.map((i) => [i.id, i]));
  return (item.dependsOn ?? [])
    .filter((d) => !chosen.includes(d) && by.get(d)?.decision !== "approved")
    .map((d) => by.get(d) ?? ({ id: d, op: "", target: "", label: d, value: d, why: "", basis: "", class: "approvable", decision: "undecided", result: "pending" } as PlanItem));
}

/** Why a decision on `ids` is refused before it is sent, or "" (the engine's `decide` rules). */
export function decisionProblem(a: Approval, ids: readonly string[], decision: DecisionWord, reason: string): string {
  if (!decidable(a)) return `This plan is ${a.status.replace(/_/g, " ")}: items are decided before it is signed.`;
  if (!ids.length) return "Select changes in the list first.";
  const by = new Map(a.items.map((i) => [i.id, i]));
  const never = ids.map((id) => by.get(id)).filter((i) => !i || !isApprovable(i));
  if (never.length) return `${never.length} selected ${never.length === 1 ? "item is" : "items are"} never approvable.`;
  if (decision !== "approved" && !reason.trim())
    return decision === "held" ? "Give a reason of a few words for holding these changes for the board." : "Give a reason of a few words for rejecting these changes.";
  if (decision === "approved") {
    for (const id of ids) {
      const item = by.get(id)!;
      const waits = waitsOn(item, a, ids);
      if (waits.length) return `${item.op} (${item.label}) waits on ${waits.length} ${waits.length === 1 ? "change" : "changes"} not approved: approve ${waits.length === 1 ? "it" : "them"} first.`;
    }
  }
  return "";
}

export interface Staleness {
  /** The plan cannot be decided or signed: it changed since review, or it was superseded. */
  blocked: boolean;
  superseded: boolean;
  changed: ChangedItem[];
  /** Read longer ago than the kind allows: decisions stand, but apply re-plans first. */
  tooOld: boolean;
  ageHours: number | null;
}

/** Whether the plan in hand is stale: superseded, a re-plan that differs (`recheck`), items the apply marked changed, or
 * a live read older than `maxAgeHours` (the kind's `max_age_hours`, 24 by default). */
export function staleness(a: Approval, opts: { recheck?: Recheck | null; now?: string; maxAgeHours?: number } = {}): Staleness {
  const fromItems: ChangedItem[] = a.items
    .filter((i) => i.result === "changed")
    .map((i) => ({ id: i.id, op: i.op, label: i.label, then: i.basis, now: "", why: i.resultDetail || "changed since review" }));
  const changed = opts.recheck?.changed?.length ? opts.recheck.changed : fromItems;
  const superseded = a.status === "superseded";
  const read = Date.parse(a.readAt), now = Date.parse(opts.now ?? new Date().toISOString());
  const ageHours = Number.isFinite(read) && Number.isFinite(now) ? (now - read) / 3_600_000 : null;
  const open = ["planned", "in_review", "approved", "partially_approved"].includes(a.status);
  const tooOld = open && ageHours !== null && ageHours > (opts.maxAgeHours ?? 24);
  return { blocked: superseded || changed.length > 0, superseded, changed, tooOld, ageHours };
}

/** Counts by result over the approved items, and over everything not applied. */
export function results(a: Pick<Approval, "items">) {
  const approved = a.items.filter((i) => isApprovable(i) && i.decision === "approved");
  const by = (r: ItemResult) => a.items.filter((i) => i.result === r);
  return {
    approved, applied: by("applied"), failed: by("failed"), uncertain: by("uncertain"), changed: by("changed"),
    blocked: by("blocked"), notApplied: by("not_applied"), pending: approved.filter((i) => i.result === "pending"),
  };
}

/** The change in words: "+ Notices by Mail (member tags)". */
export function changeText(i: PlanItem): string {
  const c = i.change;
  if (!c) return i.value;
  if (c.text) return c.text;
  if (c.op === "set") return `${c.field}: ${c.before || "(none)"} -> ${c.after ?? ""}`;
  return `${c.op === "add" ? "+" : "-"} ${c.value ?? i.value} (${c.field})`;
}

/** The evidence as `Evidence` chips show it: the label, and the address when it adds something. */
export function evidenceText(e: EvidenceRef): string {
  return e.address && e.address !== e.label ? `${e.label} (${e.address})` : e.label;
}

/** The terminal commands beside each step (`jason approvals`). */
export const commands = {
  show: (id: string) => `jason approvals show ${id}`,
  plan: (kind: string, by: string) => `jason approvals plan ${kind} --by "${cleanName(by) || "NAME"}"`,
  apply: (id: string, by: string) => `jason approvals apply ${id} --yes --by "${cleanName(by) || "NAME"}"`,
  check: (id: string) => `jason approvals apply ${id}`,
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
export { plural };
