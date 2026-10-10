import { WorkReader } from "jason-ui";

/* Harness glue: the reader loads `/api/reference-page?work=&page=`; there is no server in the capture. The fixtures are the
 * shape `jason.web.extra.citations.reference_page` returns, one per page. */
const BANNER = "An explanation, not the law and not the association's record.";
const CAVEAT = "It predates later amendments: read a section it cites from the current text on the authorities shelf before relying on it.";
const page = (n: number, text: string, extra: Record<string, unknown> = {}) => ({
  found: true, work: "A Guide to Understanding Residential Subdivisions in California", file: "ResidentialSubdivisionsGuide.pdf",
  author: "Alberto Esquivel and Jaime R. Alvayay", year: 2014, page: n, pages: 104, text, noText: !text, banner: BANNER, caveat: CAVEAT, ...extra,
});

const FIXTURES: Record<string, unknown> = {
  "/api/reference-page?work=ResidentialSubdivisionsGuide.pdf&page=60": page(60, [
    "48 A Guide to Understanding Residential Subdivisions in California",
    "In defining “subdivision” the SLA also explains that the Map Act is an “undivided interest” subdivision as defined in",
    "BPC Section 11001.1 of the SLA. Not all subdivisions subject to the Map Act are subject to the SLA.",
  ].join("\n")),
  "/api/reference-page?work=ResidentialSubdivisionsGuide.pdf&page=999": { found: false, work: "A Guide to Understanding Residential Subdivisions in California", pages: 104, note: "A Guide to Understanding Residential Subdivisions in California has 104 pages" },
  "/api/reference-page?work=Missing.pdf": { found: false, work: "A Missing Guide", note: "not on disk", command: "jason reference --fetch" },
};
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const key = Object.keys(FIXTURES).find((k) => url.startsWith(k));
  if (!key) return realFetch(input, init);
  return new Response(JSON.stringify(FIXTURES[key]), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

/** The reader loading one page of a work, the cited sentence marked, Previous and Next in the page's own bounds. */
export const LoadedPage = () => (
  <WorkReader work="ResidentialSubdivisionsGuide.pdf" page={60} sentence={"the Map Act is an “undivided interest” subdivision as defined in BPC Section 11001.1 of the SLA."} onPage={() => {}} />
);

/** A page past the end of the work: the loader's note, with no page. */
export const PastTheEnd = () => <WorkReader work="ResidentialSubdivisionsGuide.pdf" page={999} />;

/** A work not on disk: the note and the command that brings it. */
export const NotOnDisk = () => <WorkReader work="Missing.pdf" page={1} />;
