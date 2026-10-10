import type { Tone } from "../components/Badge";

/** What a cited section's standing is against the authorities shelf, as `jason.tasks.citation_coverage.Standing` names it.
 * The codes are the server's; the words are what a person reads (docs/console/handoff-citations.md). */
export type Standing = "ON_SHELF" | "NOT_EXPORTED" | "NOT_FOUND" | "RENUMBERED" | "REGULATION" | "OTHER_CODE" | "UNCHECKED";

export interface StandingWord {
  word: string;
  meaning: string;
  tone: Tone;
  /** A gap: a lead for a person, listed first. Never a bad tone, never "error": a lead is not a finding. */
  gap: boolean;
}

export const STANDINGS: Record<Standing, StandingWord> = {
  NOT_FOUND: { word: "not found", meaning: "the current publication has no such section: read the sentence, the document or the reading may be wrong", tone: "warn", gap: true },
  NOT_EXPORTED: { word: "not exported", meaning: "lawlibrary holds the section and the authorities shelf does not: a lead to add it", tone: "warn", gap: true },
  RENUMBERED: { word: "renumbered", meaning: "a pre-2014 Davis-Stirling number (1350 to 1378): read its successor", tone: "warn", gap: true },
  REGULATION: { word: "regulation", meaning: "a regulation the shelf does not hold: the Department publishes it", tone: "neutral", gap: false },
  OTHER_CODE: { word: "other code", meaning: "a code lawlibrary does not hold (a fire, building, or city code)", tone: "neutral", gap: false },
  UNCHECKED: { word: "unchecked", meaning: "not on the shelf, and lawlibrary was not asked", tone: "neutral", gap: false },
  ON_SHELF: { word: "on the shelf", meaning: "a page under the authorities shelf holds this section", tone: "good", gap: false },
};

/** The order a list reads in: the gaps first, then what is unknown, then what is held. */
export const STANDING_ORDER: Standing[] = ["NOT_FOUND", "NOT_EXPORTED", "RENUMBERED", "REGULATION", "OTHER_CODE", "UNCHECKED", "ON_SHELF"];

export const isStanding = (s: string): s is Standing => s in STANDINGS;
export const rank = (s: Standing) => STANDING_ORDER.indexOf(s);

export type StandingCounts = Partial<Record<Standing, number>>;

export interface CitationRow {
  citation: string;
  standing: Standing;
  meaning: string;
  mentions: number;
  citedBy: string[];
  /** The first PDF page it is on, for a reference work; empty for an ingest. */
  page: string;
  subdivisions: string[];
  quote: string;
}

/** `GET /api/citations?source=` for a reference work or `ingest`. With no `source` it is `CitationSources`. */
export interface CitationsData {
  found?: boolean;
  note?: string;
  source?: string;
  made?: string | null;
  report?: string;
  file?: string;
  lawChecked: boolean;
  counts: StandingCounts;
  total: number;
  shown: number;
  sections: CitationRow[];
  proposal: string;
  notes: string[];
  caveats: string[];
}

/** `GET /api/citation-gaps`. */
export interface GapsData {
  found?: boolean;
  note?: string;
  surveys: { name: string; kind: string; made: string | null; lawChecked: boolean }[];
  total: number;
  shown: number;
  gaps: CitationRow[];
  proposal: string;
  unchecked: number;
  caveats: string[];
}

export interface ReferenceWork {
  title: string;
  file: string;
  author: string;
  publisher: string;
  year: number;
  url: string;
  covers: string;
  caveat: string;
  topics: string[];
  onDisk: boolean;
  pages: number;
  surveyed: string | null;
  lawChecked: boolean;
  counts: StandingCounts | null;
  /** The survey command while none is kept. */
  command: string | null;
}

/** `GET /api/reference-works`. */
export interface WorksData {
  found?: boolean;
  note?: string;
  works: ReferenceWork[];
  caveats: string[];
}

/** `GET /api/reference-page?work=&page=`. */
export interface ReferencePageData {
  found?: boolean;
  note?: string;
  command?: string;
  work?: string;
  file?: string;
  author?: string;
  year?: number;
  page?: number;
  pages?: number;
  text?: string;
  noText?: boolean;
  banner?: string;
  caveat?: string;
}

/** A file's cited sections and gaps, from an ingest's rows (each row names the files that cite it). */
export function perFile(rows: readonly CitationRow[]): { file: string; sections: number; gaps: number }[] {
  const by = new Map<string, { file: string; sections: number; gaps: number }>();
  for (const r of rows) {
    for (const f of r.citedBy) {
      const e = by.get(f) ?? { file: f, sections: 0, gaps: 0 };
      e.sections += 1;
      if (STANDINGS[r.standing]?.gap) e.gaps += 1;
      by.set(f, e);
    }
  }
  return [...by.values()].sort((a, b) => b.gaps - a.gaps || a.file.localeCompare(b.file));
}
