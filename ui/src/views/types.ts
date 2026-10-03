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
  letters: unknown[]; letterCount?: number; notices: { kind: string; received: string; subject?: string }[]; findings: string[];
}
export interface Insurance { found?: boolean; note?: string; asOf: string; paymentsSynced?: string; policies: Policy[]; unplacedFloodPayments: unknown[]; claims: { received: string; claimNumber?: string; dateOfLoss?: string; kind?: string }[]; caveats?: string[] }

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
export interface Payment {
  key: string; date: string; amountCents: number; payee: string; description: string; categories: string[];
  documents: { filename: string; kind?: string }[]; findings: string[]; ok: boolean;
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
  documents: { notice: { path?: string; cites?: string } | null; minutes: { path?: string; draft?: boolean } | null; resolution: { path?: string } | null };
  gaps: string[];
}
export interface Reserves {
  found?: boolean; note?: string; ledgerThrough: string; reserveAccounts: string[]; borrowings: Borrowing[];
  budgetYears: { year: number; through?: string; contributionBudgetCents: number; contributionPaidCents: number; repaymentBudgetCents?: number; repaymentPaidCents?: number; short?: string[]; late?: { month: string; daysLate: number }[] }[];
  otherWithdrawals: Move[]; unappliedContributions: Move[]; catchUps: Move[]; investments: Move[]; caveats?: string[];
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
  requestsPending: { id?: string | number; form?: string; unit?: string; title?: string; created?: string; status?: string }[];
  emailedRequests?: unknown[];
  deadlines: { name: string; next: string | null; daysLeft: number | null; standing: string; note?: string }[];
  insurance: { policy: string; standing: string; finding: string }[];
  mailNotScanned: { mailId?: string; received: string; from?: string; kind?: string }[];
  lettersToAct: { received: string; from: string; kind: string; deadlines: string[]; mailId?: string }[];
  lienNotices: { received?: string; from?: string; kind?: string; amountCents?: number; subject?: string }[];
  caveats?: string[];
}
