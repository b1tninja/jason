import { AssociationPicker } from "jason-ui";

/* Harness glue: the picker searches `/api/associations?county=&q=&limit=` (asspy's directory, through
 * `jason.web.extra.discovery`); there is no server in the capture. Each cell opens a different county, so the stub
 * answers by URL and the cells cannot race. Every association is made up. */
const row = (key: string, name: string, extra: Record<string, unknown> = {}) => ({
  key, name, kind: "homeowners", standing: "confirmed", first: "2004-03-01", last: "2025-11-20",
  spellings: [name, name.replace("HOMEOWNERS ASSOCIATION", "HOA")], evidence: { "assessment lien": 386, declaration: 15 },
  governing: 12, links: 2, score: 9, ...extra,
});
const placer = {
  county: "placer", surveyed: true,
  summary: { byStanding: { confirmed: 1577, likely: 1317, named: 0 } },
  results: [
    row("example-village", "EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION"),
    row("example-oaks", "EXAMPLE OAKS OWNERS ASSN", { standing: "likely", kind: "maintenance", first: "2009-06-02", last: "2012-01-30",
      evidence: { property: 1, business: 3 }, spellings: ["EXAMPLE OAKS OWNERS ASSN"], governing: 0, links: 0 }),
    row("sample-ridge", "SAMPLE RIDGE COMMUNITY ASSOCIATION", { first: "1998-02-11", last: "2026-06-25", evidence: { "assessment lien": 100, "sale notice": 4, declaration: 2 } }),
    row("example-center", "EXAMPLE CENTER OWNERS ASSOCIATION", { kind: "commercial", evidence: { declaration: 1, business: 2 }, first: "2015-09-14", last: "2015-09-14" }),
  ],
  caveats: ["The directory is read from the public index; a row is a lead, not a membership."],
};
const ANSWERS: Record<string, unknown> = {
  placer,
  sacramento: { county: "sacramento", surveyed: false, results: [], command: "python -m asspy.associations_cli sacramento --survey 2001-01 2026-09" },
  "el-dorado": { county: "el-dorado", surveyed: true, summary: { byStanding: { confirmed: 0, likely: 0, named: 0 } }, results: [] },
};

const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  if (!url.includes("/api/associations")) return realFetch(input, init);
  const county = new URL(url, "http://x").searchParams.get("county") ?? "placer";
  return new Response(JSON.stringify(ANSWERS[county] ?? placer), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

const choice = { key: "example-village", name: "EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION", county: "placer", row: placer.results[0] };

/** The search as a combobox: the county's directory in words (how many, by standing), each row's kind, standing, evidence, and years, and the lead-not-pin caveat. */
export const Searching = () => <AssociationPicker counties={["placer", "sacramento", "el-dorado"]} defaultCounty="placer" onPick={() => {}} debounceMs={0} />;

/** A choice made: the chosen association with its spellings behind a disclosure and a way back to the search. Choosing writes nothing. */
export const Chosen = () => <AssociationPicker counties={["placer"]} picked={choice} onPick={() => {}} onClear={() => {}} debounceMs={0} />;

/** A county whose directory is not built yet: the note and the command that builds it. */
export const NotSurveyed = () => <AssociationPicker counties={["sacramento", "placer"]} defaultCounty="sacramento" onPick={() => {}} debounceMs={0} />;

/** A surveyed county with no association in its directory. */
export const NoAssociations = () => <AssociationPicker counties={["el-dorado", "placer"]} defaultCounty="el-dorado" onPick={() => {}} debounceMs={0} />;
