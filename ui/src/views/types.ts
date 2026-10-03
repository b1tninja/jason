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
