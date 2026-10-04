import type { DocRef } from "../lib/docref";

export interface BoardItem {
  id: string; title: string; summary: string; ask: string; category: string; priority: string; status: string;
  authority: string; evidence: string[]; session: string | null; special_notice: string; due: string | null; opened: string | null;
  owner: string; meeting: string; notes: string; source: string; history: string[];
}
export const BOARD_STATUSES = ["open", "proposed", "on agenda", "in progress", "deferred", "closed"] as const;

export interface Governing {
  number: string; recorded: string; filing: string; role: string; phase: string; delivery: string; recordedBy: string;
  parties: string[]; cites: string[]; status: string; supersededBy: string;
}
/** One copy of a governing document as `GET /api/governing-documents` gives it, in the shape docs/console/doc-component.md
 * calls a `DocRef`: an evidence address (`file:<path under data/>` or `drive:<id>`), never a URL into data/. */
export interface GoverningCopy {
  address: string; document?: string; name: string; kind: string; level?: string; source: string; readAt?: string; size?: number;
  thumb?: boolean; original?: { url: string; label: string }; refreshable?: { system: string; what: string }; stale?: string;
}
/** One of the association's governing documents: what it is, when it was recorded or adopted, and its copies: the recorded
 * PDF (the copy that governs) and the Drive file (a working copy). */
export interface GoverningDocumentRow {
  key: string; title: string; kind: string; kindWord: string; recorded: string; adopted: string; written: string; number: string;
  driveKind: string; recordedCopy: GoverningCopy | null; driveCopy: GoverningCopy | null; level: string; confidential: boolean;
}
export interface GoverningDocuments { found?: boolean; note?: string; count: number; rows: GoverningDocumentRow[]; heldBack: number; folders: string[]; caveats: string[] }
export interface Lifecycle { process?: string; status?: string; opened?: string; closed?: string; number?: string; [k: string]: unknown }
export interface AssociationRecords {
  found?: boolean; note?: string;
  governing: Governing[];
  deliveries: { delivery: string; found: string[]; missing: string[] }[];
  placed: Lifecycle[]; against: Lifecycle[];
  notices: { number: string; recorded: string; filing: string }[];
  unplaced: { number: string; recorded: string; filing: string; recordedBy: string }[];
}
export interface InventoryRecord {
  record: string; citation: string; meaning: string; retention: string; folders: string[]; files: number; rules: string[];
  documents: number; classified: number; newest: string; notes: string[]; gap: string;
}
export interface Inventory { found?: boolean; note?: string; count: number; gaps: string[]; records: InventoryRecord[] }

export interface LibraryStatus {
  found?: boolean; note?: string; files: number; distinctFiles: number; byMethod: Record<string, number>; byKind: Record<string, number>;
  byRecord: Record<string, { files: number; newest: string; newestPeriod: string }>; unclassified: string[];
}
export interface Readings {
  found?: boolean; note?: string; count: number; recordedCopies: Record<string, string>;
  supersessions: { number: string; supersededBy: string; phase: string; source: string; pinned: boolean }[];
  readings: { path: string; kind: string; title: string; number: string; recorded: string; pages: number; phase: string; unsigned: boolean; unrecordedCopy: boolean }[];
  unreadable: string[];
}
export interface Lead { source: string; kind: string; title: string; detail: string; next: string; authority?: string }
export interface Leads { found?: boolean; note?: string; count: number; counts: Record<string, number>; rows: Lead[]; notes: string[]; caveats: string[] }

export interface Duty {
  anchor: string; keepsStraight: string; sections: string; artifact: string; cadence: string; when: string;
  records: string[]; produce: string; limit: string;
}
export interface Duties { found?: boolean; note?: string; count: number; duties: Duty[] }
export interface DutyBrief extends Duty {
  found?: boolean; note?: string;
  passages: Record<string, { shelf: string; file: string; passage: number; score: number; text: string }[]>;
}

export interface Obligation {
  name: string; authority: string; rule: string; note: string; standing: string; next: string | null; daysLeft: number | null;
  lastDone: string | null; history: { deadline?: string; standing?: string; daysLate?: number; date?: string; amountCents?: number; evidence?: string[] }[];
}
export interface Calendar { found?: boolean; note?: string; asOf: string; obligations: Obligation[]; lateOrMissed?: Obligation[]; caveats?: string[] }

export interface Meeting { date: string; titles: string[]; has: Record<string, Record<string, number>>; checks: string[] }
export interface Meetings { found?: boolean; note?: string; builtAt?: string; count?: number; meetings: Meeting[]; scheduleGaps?: string[]; unplaced?: unknown[]; caveats?: string[] }

export interface Policy {
  kind: string; building?: string | number | null; number: string; priorNumbers: string[]; carrier: string; program: string; agent: string;
  standing: string; termEnd: string | null; terms: { start?: string; end?: string; paidCents?: number }[]; nextTermPayments: { date: string; amountCents: number }[];
  letters: unknown[]; letterCount?: number; notices: InsuranceLetter[]; findings: string[];
}
/** A letter the insurance review reads (a notice or a claim), with its scan as a `DocRef` (`mail/<id>/contents.pdf`, P2);
 * `held` stands in place of `scan` for a letter that carries a credential (P4: it opens in no screen). */
export interface InsuranceLetter { kind: string; received: string; subject?: string; mailId?: string; from?: string | null; scan?: import("../lib/docref").DocRef | null; held?: string }
export interface InsuranceClaim { received: string; claimNumber?: string; dateOfLoss?: string; kind?: string; mailId?: string; from?: string | null; scan?: import("../lib/docref").DocRef | null; held?: string }
export interface Insurance { found?: boolean; note?: string; asOf: string; paymentsSynced?: string; policies: Policy[]; unplacedFloodPayments: unknown[]; claims: InsuranceClaim[]; caveats?: string[] }

export interface Side { budget?: number; actual?: number; variance?: number; budgeted?: number }
export interface Budget {
  found?: boolean; note?: string; year: number; throughMonth?: string; syncedAt?: string;
  yearToDate: Record<string, Side | number>; fullYear?: Record<string, Side | number>;
  months: { month: string; incomeBudget: number; incomeActual: number; expenseBudget: number; expenseActual: number }[];
  expenseGaps: { name: string; budgeted: number; actual: number; gap: number }[]; revenueGaps: { name: string; budgeted: number; actual: number; gap: number }[];
  accounts: { name?: string; label?: string; last4?: string; purpose?: string; balance_cents?: number | null }[]; reserveTotalCents: number | null;
}
export interface Account {
  account: string; last4?: string; reconciled?: string; latest?: string; latestEndingCents?: number; registerBalanceCents?: number; gaps: string[];
  openItems: { kind: string; date: string; amount?: number; lineCents?: number; description: string; ageDays: number; reason: string }[];
  ledgerMismatches: { end: string; statementCents: number; ledgerCents: number; differenceCents: number; explained: boolean }[];
}
export interface Reconciliations { found?: boolean; note?: string; accounts: Account[]; openTransfers: unknown[]; caveats?: string[] }
/** An attachment as the invoice review gives it: its filename, and `doc`, the reference to jason's copy when it keeps one. */
export interface PaymentDocument { id?: number; filename: string; kind?: string; doc?: DocRef }
export interface Payment {
  key: string; date: string; amountCents: number; payee: string; description: string; categories: string[];
  documents: PaymentDocument[]; findings: string[]; ok: boolean;
}
export interface Invoices { found?: boolean; note?: string; summary: Record<string, number>; payments: Payment[]; more?: string; caveats?: string[] }
export interface CollectionRow {
  apn: string; address: string; owners: string[]; standing: string; meaning: string; balanceCents: number; pastDueCents: number;
  lien?: string; lienRecorded?: string; lienStatus?: string; lienDays?: number; floorQuestion?: string; nextStep: string;
}
export interface Collections { found?: boolean; note?: string; counts: Record<string, number>; rows: CollectionRow[]; pastDueCents: number; note2?: string }

export interface Move { day: string; cents: number; account: string; kind: string; purpose: string; number: string; memo: string; description: string; matched?: boolean }
export interface Borrowing extends Move {
  deadline: string; repaidCents: number; outstandingCents: number; repaidOn: string | null; exactRepayment: boolean; repayments: Move[];
  /** The 5515 record the library holds, each with `doc`, its reference. */
  documents: {
    notice: { id?: string; name?: string; meeting?: string; cites?: string; doc?: DocRef } | null;
    minutes: { id?: string; name?: string; draft?: boolean; mentionsBorrowing?: boolean; doc?: DocRef } | null;
    resolution: { id?: string; name?: string; doc?: DocRef } | null;
  };
  gaps: string[];
}
export interface Reserves {
  found?: boolean; note?: string; ledgerThrough: string; reserveAccounts: string[]; borrowings: Borrowing[];
  budgetYears: { year: number; through?: string; contributionBudgetCents: number; contributionPaidCents: number; repaymentBudgetCents?: number; repaymentPaidCents?: number; short?: string[]; late?: { month: string; daysLate: number }[] }[];
  otherWithdrawals: Move[]; unappliedContributions: Move[]; catchUps: Move[]; investments: Move[]; caveats?: string[];
  /** The latest reserve study's reference, when one is on disk. */
  study?: DocRef;
}
export interface Hearing {
  address: string; building?: string | number; start: string; noticeBy: string; noticeOn?: string; decisionByIfHeld: string; statement?: string;
  standing: string; scheduled: boolean; zoom?: { id?: string; joinUrl?: string } | null; notice?: string; problems?: string[];
}
export interface Hearings { found?: boolean; note?: string; hearings: Hearing[] }
export interface TitleRow {
  apn: string; address: string; building: string | number; owner: string; currentOwners: string[]; process: string; number: string; recorded: string;
  claimant: string[]; status: string; standing: string; meaning: string; presumedPaidAt: string; namesakeRisk: boolean; enforceableUntil: string; sharedWith: string[]; latestStep: string; taxBillYear?: number | string;
}
export interface TitleWatch { found?: boolean; note?: string; counts: Record<string, number>; rows: TitleRow[] }
export interface OpenItems {
  found?: boolean; note?: string; counts: Record<string, number>;
  threadsAwaitingUs: { threadId?: string; last: string; ageDays: number; who: string; subject: string; topics: string[]; link?: string; likelyNeedsResponse?: boolean; pastUsualTime?: boolean; replyRate?: number }[];
  requestsPending: { id?: string | number; form?: string; unit?: string; title?: string; created?: string; status?: string; doc?: import("../lib/docref").DocRef | null }[];
  emailedRequests?: unknown[];
  deadlines: { name: string; next: string | null; daysLeft: number | null; standing: string; note?: string }[];
  insurance: { policy: string; standing: string; finding: string }[];
  mailNotScanned: { mailId?: string; received: string; from?: string; kind?: string }[];
  lettersToAct: { received: string; from: string; kind: string; deadlines: string[]; mailId?: string; scan?: import("../lib/docref").DocRef | null; held?: string }[];
  lienNotices: { received?: string; from?: string; kind?: string; amountCents?: number; subject?: string }[];
  caveats?: string[];
}
