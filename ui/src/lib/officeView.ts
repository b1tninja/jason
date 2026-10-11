/** The office views' loader shape and the lens rules (`GET /api/office-view?office=ROLE`, docs/console/screens/office-views.md).
 * An office is an `OfficerRole` word; the lens lives in the URL's hash (`#/digest?as=treasurer`), never on the server. */

export const LENS_PARAM = "as";
export const OFFICE_WORDS = ["president", "vice president", "secretary", "treasurer", "director", "manager"] as const;

export const BANDS = ["waitingOnOffice", "needsAttention", "comingUp", "work"] as const;
export type BandKey = (typeof BANDS)[number];

export interface OfficeInfo { office: string; vacant: boolean; holders: number }

/** One row of a band: an office's counts, kinds, and titles of items, never a name. */
export interface OfficeRow {
  type: "letter" | "board-item" | "decision" | "duty" | "tasks" | "run" | string;
  text: string;
  office?: string;
  screen?: string;
  urgency?: string;
  due?: string | null;
  count?: number;
  overdue?: number;
  kind?: string;
  approver?: string;
  title?: string;
  label?: string;
  stepTitle?: string;
  standing?: string;
  basis?: string;
  shared?: boolean;
  backup?: boolean;
  id?: string;
  key?: string;
  /** A run row's workflow definition: with `id`, the run's address (`#/work/<definition>/<id>`). */
  definition?: string;
}

export interface NotComposed { band: string; what: string; why: string }

export interface OfficeViewData {
  found: boolean;
  asOf: string;
  /** The office asked for ("" is the viewer's own offices, the union). */
  office: string;
  reading: string[];
  title: string;
  ownOffice: boolean;
  vacant: boolean;
  offices: OfficeInfo[];
  mine: string[];
  bands: Record<BandKey, OfficeRow[]>;
  counts: Record<BandKey, number>;
  bandErrors: Partial<Record<string, string>>;
  notComposed: NotComposed[];
  caveats: string[];
  note?: string;
}

/** "the treasurer": an office as a sentence reads it. */
export const theOffice = (office: string): string => `the ${office}`;

/** A list of offices as words: "the secretary and the treasurer". */
export function officesText(offices: readonly string[]): string {
  const words = offices.map(theOffice);
  if (words.length <= 1) return words[0] ?? "";
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/** The office a hash names (`?as=treasurer`, `vice-president`, `vice+president`), or "" for the viewer's own offices. A word
 * that is no office is kept as typed, so the page can say so rather than quietly read something else. */
export function lensFromHash(hash: string): string {
  const q = hash.includes("?") ? hash.slice(hash.indexOf("?") + 1) : "";
  const raw = new URLSearchParams(q).get(LENS_PARAM) ?? "";
  return raw.replace(/[-_+]/g, " ").trim().toLowerCase().replace(/\s+/g, " ");
}

/** `hash` with the lens set to `office` ("" removes it), every other part of the hash kept as it was. */
export function hashWithLens(hash: string, office: string): string {
  const at = hash.indexOf("?");
  const route = (at < 0 ? hash : hash.slice(0, at)).replace(/^#\/?/, "");
  const params = new URLSearchParams(at < 0 ? "" : hash.slice(at + 1));
  if (office) params.set(LENS_PARAM, office);
  else params.delete(LENS_PARAM);
  const q = params.toString();
  return `/${route}${q ? `?${q}` : ""}`;
}

/** Whether the page reads the viewer's own offices (no lens, or a lens on an office they hold). */
export const isOwnLens = (d: Pick<OfficeViewData, "office" | "ownOffice">): boolean => !d.office || d.ownOffice;

/** A band's heading: the viewer's own say "you"; another office's names that office and never says "you" for it. */
export function bandTitle(band: BandKey, d: Pick<OfficeViewData, "office" | "ownOffice">): string {
  const own = isOwnLens(d);
  const who = theOffice(d.office);
  switch (band) {
    case "waitingOnOffice": return own ? "Waiting on you" : `Waiting on ${who}`;
    case "needsAttention": return own ? "Needs attention" : `Needs attention for ${who}`;
    case "comingUp": return own ? "Coming up" : `Coming up for ${who}`;
    case "work": return own ? "Your work" : `Work for ${who}`;
  }
}

/** Why a control is not live for the viewer: "Only the treasurer can sign this. You are the secretary." */
export function notYours(needs: string | readonly string[], mine: readonly string[], what = "do this"): string {
  const list = typeof needs === "string" ? [needs] : [...needs];
  const only = list.length === 1 ? `Only ${theOffice(list[0])} can ${what}.` : `Only ${officesText(list).replace(" and ", " or ")} can ${what}.`;
  return `${only} ${mine.length ? `You are ${officesText(mine)}.` : "You hold no office."}`;
}

/** Whether the viewer's offices include any of `needs`. */
export const holdsAny = (needs: string | readonly string[], mine: readonly string[]): boolean =>
  (typeof needs === "string" ? [needs] : needs).some((o) => mine.includes(o));
