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

/** `{label, address}`: a record, a citation `jason cite` resolves, or a command; `readAt` and `digest` say when jason read
 * it for the plan and what it read (`GET /api/evidence` compares them with the stored copy now). */
export interface EvidenceRef { label: string; address?: string; readAt?: string; digest?: string }

/** What an item changes: a value added to or removed from a field, or a field set from one value to another. */
export interface Change { op: "add" | "remove" | "set"; field: string; value?: string; before?: string; after?: string; text?: string }

/** One decision made under a finding, from the exceptions log (`data/approvals/exceptions.jsonl`, append only): who, when,
 * why, the second person who signed the plan it was in, and whether the write was made. */
export interface ExceptionRow {
  at: string; approval: string; item: string; finding: string; boardItem?: string; by: string; secondBy?: string;
  decision: DecisionWord; reason?: string; applied?: boolean; kind?: string;
}

/** One change in an approval (plan-item.schema.json). An item of class `held_for_board` is **flagged for review**: it is
 * in no ordinary approval, and a person decides it on its own as a one-off exception (`exception: true` once decided).
 * `exceptions` and `exceptionCount` are the server's, beside a flagged item: what was decided under its finding. */
export interface PlanItem {
  id: string; op: string; target: string; label: string; value: string; why: string; group?: string;
  change?: Change | null; rule?: string; evidence?: EvidenceRef[]; basis: string; class: ItemClass; boardItem?: string;
  dependsOn?: string[]; highStakes?: boolean; costCents?: number; decision: ItemDecision; decidedBy?: string;
  decidedAt?: string; reason?: string; result: ItemResult; resultDetail?: string;
  exception?: boolean; exceptions?: ExceptionRow[]; exceptionCount?: number;
}

/** One decision as a named person made it (decision.schema.json). */
export interface DecisionRecord { by: string; at: string; items: string[]; decision: DecisionWord; reason?: string; fingerprint: string; via?: Via }

/** A person's signature on a plan fingerprint (decision.schema.json#/$defs/signature). */
export interface Signature { name: string; at: string; fingerprint: string; role?: string; via?: Via }

export interface ApprovalClock { what?: string; due?: string; daysLeft?: number }

/** The plan's flagged items counted by the server, and the count of exceptions at which the plan suggests a rule. */
export interface FlaggedCounts { flagged: number; decidedByException: number; nudge: number }

/** How many exceptions under one finding before the plan says the board may want to write a rule (the server sends the
 * number it uses as `flagged.nudge`; this is its default). */
export const EXCEPTION_NUDGE = 2;

/** One plan of writes outside jason (approval.schema.json). */
export interface Approval {
  id: string; kind: string; title: string; status: ApprovalStatus; scope?: Record<string, unknown>; profile?: string;
  fingerprint: string; readAt: string; requestedBy: string; requestedAt: string; requestedVia?: Via; evidence?: EvidenceRef[];
  items: PlanItem[]; decisions: DecisionRecord[]; first?: Signature | null; second?: Signature | null;
  costCents?: number | null; clock?: ApprovalClock | null; summary?: Record<string, unknown>; result?: Record<string, unknown>;
  supersedes?: string; supersededBy?: string; notes?: string[]; flagged?: FlaggedCounts;
  /** Beside the plan from the server (a list row, `/api/approvals/<id>`): whether a second person must sign, controls included. */
  needsSecond?: boolean | null;
  /** Signed by everyone the plan needs and not yet applied (the server's `waiting_row`): hours since the last signature,
   * whether the plan is older than its kind allows (it is planned again before apply), and a terminal-only kind. */
  waitingToApply?: boolean; waitingHours?: number | null; waitingStale?: boolean; signedAt?: string; terminalOnly?: boolean;
  /** The board's apply preferences, beside the plan (`jason.controls.apply_prefs`): a reminder is due (it only surfaces; nothing
   * is sent), the hours it was set to (null: none), and a pause after the last signature with when it ends. */
  reminderDue?: boolean; reminderHours?: number | null; pausing?: boolean; pauseEndsAt?: string;
}

/** One of the five apply settings in plain words, with where it comes from: the default, or the board's adoption. */
export interface ApplyPrefRow {
  setting: "where" | "who" | "pause" | "typed" | "reminder"; title: string; words: string; default: boolean; source: string; controls: string[];
}

/** The apply preferences that hold for a plan's kind (`applyPrefs` in `/api/approvals/<id>`). `consoleAllowed` is whether the
 * preferences let the console apply this kind; the server's `--allow-apply` is asked on its own. `consoleFloored`: the board chose
 * the console and the floors closed it (a kind that is terminal-only, costs money, or sends mail or email). */
export interface ApplyPrefs {
  kind: string; where: "terminal" | "console"; who: string; pauseMinutes: number; pauseUntilNextDay: boolean;
  typedCountOver: number | null; reminderHours: number | null; consoleFloor: string; consoleFloored: boolean; consoleAllowed: boolean;
  clash: string; rows: ApplyPrefRow[]; waiting: { control: string; setting: string; why: string }[];
}

/** A pause after the last signature that has not ended (`applyHold`): when it ends, the seconds left when the page loaded. */
export interface ApplyHold { endsAt: string; secondsLeft: number; words: string }

/** Whether apply asks the person to type the number of changes, and that number (`typedCount`). */
export interface TypedCount { needed: boolean; over: number | null; changes: number }

export type AuditEvent =
  | "plan.created" | "plan.failed" | "item.decided" | "approval.submitted" | "approval.confirmed" | "approval.declined"
  | "apply.started" | "apply.refused" | "item.applying" | "item.applied" | "item.failed" | "item.uncertain" | "item.blocked"
  | "item.not_applied" | "approval.applied" | "approval.failed" | "approval.superseded" | "approval.withdrawn" | "cli.applied"
  | "item.referred";

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

/** What an action kind declares (`jason approvals kinds`; `kindFacts` beside a plan in `/api/approvals/<id>`): its risk,
 * who approves, how it is undone, how long a plan stays current before apply refuses it, and its cost. The screen shows
 * these as the server sends them and never works them out. */
export interface KindFacts {
  key: string; title: string; cli?: string; system?: string; risk: string; riskWords: string; approver: string;
  twoPerson: boolean; reversible: string; maxAgeHours: number; cost?: string; clock?: string; rule?: string;
  /** Only a person at a terminal applies this kind (the server refuses jason-web's apply); `cli` names the command. */
  terminalOnly?: boolean;
  /** What the kind sends to people when it is applied ("" none): the console never applies a kind that sends. */
  sends?: string;
}

/** `engine.Recheck`: a re-plan compared with the approval (what `jason approvals apply ID` prints without --yes). */
export interface Recheck { changed: ChangedItem[]; new?: PlanItem[] | number; then?: string; now?: string; problems?: string[] }

/** A body a decision, signature, or re-plan posts. `by` is a named person; jason never signs. */
export interface DecideBody { items: string[]; decision: DecisionWord; reason: string; by: string; fingerprint: string; via: Via; exception?: boolean }
/** Put a flagged item's finding before the board (`POST /api/approvals/<id>/refer`). It decides nothing. */
export interface ReferBody { item: string; by: string; fingerprint: string; via: Via }
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
  { cls: "held_for_board", title: "Flagged for review", note: "In no ordinary approval: no rule the board adopted answers these. Each is decided on its own, as a one-off exception." },
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

/** Flagged for review: held for the board by jason's policy finding (the engine's `held_for_board` class). */
export function isFlagged(i: PlanItem): boolean {
  return i.class === "held_for_board";
}

/** Approved, and so written at apply: an approvable item approved, or a flagged item approved as a one-off exception. */
export function takesEffect(i: PlanItem): boolean {
  return i.decision === "approved" && (isApprovable(i) || (isFlagged(i) && !!i.exception));
}

/** The flagged items counted: how many, and how many were approved as exceptions. */
export function flaggedCounts(a: Pick<Approval, "items">): { flagged: number; decidedByException: number } {
  const rows = a.items.filter(isFlagged);
  return { flagged: rows.length, decidedByException: rows.filter((i) => i.exception && i.decision === "approved").length };
}

/** Whether an item's finding has been decided by exception often enough that the plan suggests the board write a rule. */
export function nudged(i: PlanItem, threshold: number = EXCEPTION_NUDGE): boolean {
  return isFlagged(i) && (i.exceptionCount ?? 0) >= threshold;
}

/** Why a decision on a flagged item is refused before it is sent, or "" (the engine's `decide` with `exception`): an
 * approval gives a reason in words; a rejection or a flag kept gives a note. */
export function exceptionProblem(decision: DecisionWord, reason: string): string {
  const text = reason.trim();
  if (decision === "approved") return text.split(/\s+/).filter(Boolean).length >= 2 ? "" : "Give a reason in words (a few, not \"ok\") for the exception.";
  if (!text) return decision === "held" ? "Add a note of a few words for the next reviewer." : "Give a reason of a few words for rejecting this change.";
  return "";
}

/** Items a person may still decide: approvable, while the plan is planned or in review. */
export function decidable(a: Approval): boolean {
  return a.status === "planned" || a.status === "in_review";
}

/** `exceptions` are flagged items approved as one-off exceptions: they are written like an approved change, but are not
 * among the `approvable` ones the ordinary approval counts. */
export interface Tally { approvable: number; approved: number; rejected: number; held: number; undecided: number; exceptions: number }

export function tally(a: Pick<Approval, "items">): Tally {
  const rows = a.items.filter(isApprovable);
  const n = (d: ItemDecision) => rows.filter((i) => i.decision === d).length;
  return {
    approvable: rows.length, approved: n("approved"), rejected: n("rejected"), held: n("held"), undecided: n("undecided"),
    exceptions: a.items.filter((i) => isFlagged(i) && takesEffect(i)).length,
  };
}

/** A second, distinct person signs: a two-person kind (`twoPerson`, from the kind's registry row), or an approved item
 * that is high stakes (the engine's `needs_second`): a flagged item approved as an exception always is. */
export function needsSecond(a: Pick<Approval, "items">, twoPerson = false): boolean {
  return twoPerson || a.items.some((i) => takesEffect(i) && !!i.highStakes);
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
  if (never.some((i) => i && isFlagged(i)))
    return `${never.length} selected ${never.length === 1 ? "item is" : "items are"} flagged for review, never approvable here: decide each on its own, as a one-off exception.`;
  if (never.length) return `${never.length} selected ${never.length === 1 ? "item is" : "items are"} never approvable.`;
  if (decision !== "approved" && !reason.trim())
    return decision === "held" ? "Give a reason of a few words for holding these changes for the board." : "Give a reason of a few words for rejecting these changes.";
  if (decision === "approved") {
    for (const id of ids) {
      const item = by.get(id)!;
      const waits = waitsOn(item, a, ids);
      if (waits.length) return `${item.op} (${item.label}) waits on ${waits.length} ${waits.length === 1 ? "change" : "changes"} not approved: mark ${waits.length === 1 ? "it" : "them"} approved first.`;
    }
  }
  return "";
}

/** The statuses after which a plan is not decided, signed, or applied again: it is closed (a superseded plan is closed too, by a newer one). */
export const CLOSED_STATUSES: readonly ApprovalStatus[] = ["applied", "failed", "withdrawn", "superseded"];
/** Closed, but not replaced: nothing is stale about it, it is simply over. */
const ENDED: readonly ApprovalStatus[] = ["applied", "failed", "withdrawn"];

/** Whether a plan is over: applied, failed, withdrawn, or superseded. What is "to decide", "blocked", or "changed since review"
 * is not said of one. */
export function isClosed(status: ApprovalStatus): boolean {
  return CLOSED_STATUSES.includes(status);
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
  // A plan that is over (applied, failed, withdrawn) is not "changed since it was reviewed": nothing more is decided or signed
  // on it, so there is nothing to block. Its changed items are told in the apply result. A superseded plan keeps its own banner.
  const ended = ENDED.includes(a.status);
  const changed = ended ? [] : opts.recheck?.changed?.length ? opts.recheck.changed : fromItems;
  const superseded = a.status === "superseded";
  const read = Date.parse(a.readAt), now = Date.parse(opts.now ?? new Date().toISOString());
  const ageHours = Number.isFinite(read) && Number.isFinite(now) ? (now - read) / 3_600_000 : null;
  const open = ["planned", "in_review", "approved", "partially_approved"].includes(a.status);
  const tooOld = open && ageHours !== null && ageHours > (opts.maxAgeHours ?? 24);
  return { blocked: superseded || changed.length > 0, superseded, changed, tooOld, ageHours };
}

/** Counts by result over the approved items, and over everything not applied. */
export function results(a: Pick<Approval, "items">) {
  const approved = a.items.filter(takesEffect);
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

// --- where a plan stands, in words (docs/console/approval-clarity.md) --------------------------------------------------

/** The outside system a kind writes to, as a reader names it: the registry's `system` key ("payhoa"), or "" for a kind
 * that names none or only `local`. */
export function systemWord(kind?: Pick<KindFacts, "system"> | null): string {
  const key = String(kind?.system ?? "").trim().toLowerCase();
  if (!key || key === "local") return "";
  return ({ payhoa: "PayHOA", google: "Google", zoom: "Zoom" } as Record<string, string>)[key] ?? key;
}

/** "to PayHOA", or "outside jason" when the kind names no system: the place a plan's writes go. */
export function writtenTo(kind?: Pick<KindFacts, "system"> | null): string {
  const w = systemWord(kind);
  return w ? `to ${w}` : "outside jason";
}

/** What applying will do, counted from the approved items (those that take effect): the changes, the records they fall on
 * (an item's `group`), and the changes by the field each sets (`change.field`, else the item's `op`). */
export function applyCounts(a: Pick<Approval, "items">): { changes: number; records: number; byField: { name: string; n: number }[] } {
  const rows = a.items.filter(takesEffect);
  const by = new Map<string, number>();
  for (const i of rows) { const k = i.change?.field || i.op; by.set(k, (by.get(k) ?? 0) + 1); }
  return { changes: rows.length, records: new Set(rows.map((i) => i.group || i.label)).size, byField: [...by].map(([name, n]) => ({ name, n })) };
}

/** "Applying will make 7 changes on 2 records: member tags (5), request status (2).", or that none is marked approved. */
export function applyCountsWords(a: Pick<Approval, "items">): string {
  const c = applyCounts(a);
  if (!c.changes) return "No change is marked approved yet.";
  return `Applying will make ${plural(c.changes, "change", "changes")} on ${plural(c.records, "record", "records")}: ${c.byField.map((f) => `${f.name} (${f.n})`).join(", ")}.`;
}

/** What did not go through, each apart: "1 failed, 1 changed since review, 1 uncertain". A count of none is left out, except that a
 * plan with nothing wrong says "0 failed" when `always` (the sentence for an applied plan names failures even when there are none). */
export function applyOutcomeWords(c: { failed: number; changed: number; uncertain: number }, always = false): string {
  const parts = [
    c.failed || always ? `${c.failed} failed` : "",
    c.changed ? `${c.changed} changed since review` : "",
    c.uncertain ? `${c.uncertain} uncertain` : "",
  ].filter(Boolean);
  return parts.join(", ");
}

/** A plan as a list row or the full record carries it: the full `Approval`, or `GET /api/approvals`'s summary, where
 * `items` is a count and the counts come by class, decision, and result (`engine.counts`), and the signers are names. */
export interface PlanLike {
  status: ApprovalStatus;
  items?: PlanItem[] | number;
  byClass?: Record<string, number>; byDecision?: Record<string, number>; byResult?: Record<string, number>;
  first?: Signature | string | null; second?: Signature | string | null;
  needsSecond?: boolean | null; approved?: number; result?: Record<string, unknown>;
  waitingToApply?: boolean; waitingHours?: number | null; waitingStale?: boolean; terminalOnly?: boolean; reminderDue?: boolean;
  /** The board's pause after the last signature has not ended: the plan is signed and held, not ready to apply. */
  pausing?: boolean;
}

const signerOf = (s: Signature | string | null | undefined): string => (typeof s === "string" ? s : s?.name ?? "");

/** One of the six sentences a plan's state is always shown in (the engine's status words stay in the JSON). `me` is the
 * signed-in person: "needs your signature" is said only to a person who may sign. `opts.needsSecond` or `opts.twoPerson`
 * say whether a second person must sign when the record itself does not (a full plan with a two-person kind). */
export function planState(a: PlanLike, me = "", opts: { needsSecond?: boolean | null; twoPerson?: boolean } = {}): string {
  const rows = Array.isArray(a.items) ? (a.items as PlanItem[]) : null;
  const t = rows ? tally({ items: rows }) : null;
  const r = rows ? results({ items: rows }) : null;
  const total = t ? t.approvable : a.byClass?.approvable ?? 0;
  const marked = t ? t.approvable - t.undecided : ["approved", "rejected", "held"].reduce((n, k) => n + (a.byDecision?.[k] ?? 0), 0);
  const approved = r ? r.approved.length : a.approved ?? a.byDecision?.approved ?? 0;
  const res = a.byResult ?? {};
  const applied = r ? r.applied.length : Number(res.applied ?? a.result?.applied ?? 0);
  // Failed, changed since review, and uncertain are three different things for a person to look at: said apart, never lumped.
  const failed = r ? r.failed.length : Number(res.failed ?? 0);
  const changed = r ? r.changed.length : Number(res.changed ?? 0);
  const uncertain = r ? r.uncertain.length : Number(res.uncertain ?? 0);
  switch (a.status) {
    case "planned":
    case "in_review":
      if (total > 0 && marked >= total) return signerProblem(me) ? "Marked, needs a signature." : "Marked, needs your signature.";
      return `Needs review: ${marked} of ${total} marked.`;
    case "approved":
    case "partially_approved": {
      const second = opts.needsSecond ?? a.needsSecond ?? (rows ? needsSecond({ items: rows }, opts.twoPerson) : false);
      if (second && !signerOf(a.second)) {
        const first = signerOf(a.first);
        return `Waiting for a second signature${first ? ` (someone other than ${first})` : ""}.`;
      }
      return "Signed, not applied yet. Nothing has been written.";
    }
    case "applying": return `Applying: ${applied} of ${plural(approved, "change", "changes")} written.`;
    case "applied": return `Applied: ${plural(applied, "change", "changes")} made, ${applyOutcomeWords({ failed, changed, uncertain }, true)}.`;
    case "failed": {
      const not = Math.max(approved - applied, failed + changed + uncertain);
      const kinds = [failed, changed, uncertain].filter(Boolean).length;
      return `Failed: ${plural(not, "change was", "changes were")} not made${kinds > 1 ? ` (${applyOutcomeWords({ failed, changed, uncertain })})` : ""}`;
    }
    case "superseded": return "Replaced by a newer plan";
    case "withdrawn": return "Withdrawn";
  }
}

// --- signed, waiting to be applied (docs/console/approval-clarity.md, section 4) ---------------------------------------------

/** How long, in words, as the server says it (`engine.ago`): "less than an hour", "5 hours", "3 days". */
export function agoWords(hours: number | null | undefined): string {
  const h = Number(hours ?? 0);
  if (!(h >= 1)) return "less than an hour";
  if (h < 48) { const n = Math.floor(h); return `${n} ${n === 1 ? "hour" : "hours"}`; }
  return `${Math.floor(h / 24)} days`;
}

/** "Signed, waiting to be applied · 3 days", or for a plan read longer ago than its kind allows, "Signed 5 days ago; it will
 * be planned again before it is applied". "" for a plan that is not signed and waiting. The server decides which plan
 * waits (`waitingToApply`) and for how long; this only says it. A terminal-only kind adds where it is applied. */
export function waitingWords(a: Pick<PlanLike, "waitingToApply" | "waitingHours" | "waitingStale" | "terminalOnly" | "reminderDue" | "pausing">): string {
  if (!a.waitingToApply) return "";
  const waited = agoWords(a.waitingHours);
  const base = a.waitingStale ? `Signed ${waited} ago; it will be planned again before it is applied` : `Signed, waiting to be applied · ${waited}`;
  const held = a.pausing ? `${base} · held by the board's pause` : base;
  const where = a.terminalOnly ? `${held} · applied at the terminal` : held;
  return a.reminderDue ? `${where} · reminder due` : where;
}

/** The one sentence a plan's state is told in, wherever it is told: the waiting words for a signed plan the server says is waiting
 * (the list's "Where it stands"), else the plan's state. The plan's header and its row in the list both use it, so they never
 * say two things of one plan. */
export function stateSentence(a: PlanLike, me = "", opts: { needsSecond?: boolean | null; twoPerson?: boolean } = {}): string {
  return waitingWords(a) || planState(a, me, opts);
}

/** The list's "Where it stands" (see `stateSentence`). */
export function listState(a: PlanLike, me = ""): string {
  return stateSentence(a, me);
}

// --- the board's apply preferences (docs/console/approval-clarity.md, section 5) -----------------------------------------------

/** The time left in a pause, as a clock: "29:41", or "1:02:09" past an hour. */
export function holdClock(seconds: number): string {
  const t = Math.max(0, Math.floor(seconds));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  const two = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${two(m)}:${two(sec)}` : `${two(m)}:${two(sec)}`;
}

/** Why the typed count is not the plan's, or "" when none is asked or it is right (the server asks again: `typed_problem`). */
export function typedCountProblem(tc: TypedCount | null | undefined, typed: string): string {
  if (!tc?.needed) return "";
  const t = typed.trim();
  if (!t) return `Type the number of changes this plan makes (${tc.changes}) to apply it.`;
  if (!/^\d+$/.test(t) || Number(t) !== tc.changes) return `${t} is not the number of changes this plan makes.`;
  return "";
}
