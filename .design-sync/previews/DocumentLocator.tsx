import { DocumentLocator } from "jason-ui";

/* Harness glue: the locator reads `/api/documents-located?county=&name=` and polls while a job is queued; there is no
 * server in the capture. Each cell asks for a different made-up association, so the stub answers by URL and the
 * cells cannot race. Shapes are `jason.web.extra.discovery`'s. */
const located = {
  association: "Example Village HOA", county: "placer", located_at: "2026-10-02T15:04:00", searches: 42, liens: 386,
  spellings: ["EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION", "EXAMPLE VILLAGE HOA"],
  items: [
    { item: "declaration", title: "The declaration (CC&Rs), the recorded copy", question: "Which is the association's declaration (the CC&Rs later amendments amend)?", stakes: true,
      located: [{ number: "2001-0000020", recorded: "2001-03-08", filing: "AMENDED RESTRICTION", tie: "NAMED", tie_label: "names the association", strong: true, via: "",
        parties: ["EXAMPLE HOMES INC", "EXAMPLE VILLAGE HOA"] }] },
    { item: "annexations", title: "Annexations", question: "Which of these annex a phase into the association (or take one out)?", stakes: false,
      located: [
        { number: "2003-0000050", recorded: "2003-06-01", filing: "DECLARATION OF ANNEXATION", tie: "BESIDE", tie_label: "recorded with the association's documents", strong: true, via: "2003-0000049", parties: ["EXAMPLE HOMES INC"] },
        { number: "2007-0030003", recorded: "2007-01-15", filing: "DECLARATION OF ANNEXATION", tie: "DECLARANT", tie_label: "the builder's filing", strong: false, via: "EXAMPLE HOMES INC", parties: ["EXAMPLE HOMES INC"] },
      ] },
  ],
  not_located: [{ item: "maps", title: "The subdivision maps", ask: "None in the index under the association's names; ask the board or the prior manager for the recording number." }],
  notes: [], caveats: ["A located document is a lead, not a pin: the recorded copy is read before it is pinned."],
};
const missing = (name: string, job: unknown = null) => ({
  missing: true, job, note: `No documents located for ${name} yet.`,
  command: `jason onboard --locate --county placer --name "${name}"`,
});

const ANSWERS: Record<string, unknown> = {
  "Example Village HOA": located,
  "Sample Oaks Owners Association": missing("Sample Oaks Owners Association"),
  "Example Ridge Community Association": missing("Example Ridge Community Association", { id: 41, status: "running" }),
  "Sample Creek HOA": missing("Sample Creek HOA", { id: 39, status: "failed" }),
};

const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  if (!url.includes("/api/documents-located")) return realFetch(input, init);
  const name = new URL(url, "http://x").searchParams.get("name") ?? "";
  return new Response(JSON.stringify(ANSWERS[name] ?? located), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

/** Located: the result grouped by checklist item, with "Locate documents again" behind Confirm. */
export const Located = () => <DocumentLocator county="placer" name="Example Village HOA" me="Jane Example" />;

/** Nothing located yet: the note, the command, and "Locate documents" (a read job a named person queues). */
export const NotYet = () => <DocumentLocator county="placer" name="Sample Oaks Owners Association" me="Jane Example" />;

/** A locate job running: the job line in place of the button while the page reads again. */
export const JobRunning = () => <DocumentLocator county="placer" name="Example Ridge Community Association" me="Jane Example" />;

/** The last locate job failed: the job line says so and the button is back. */
export const JobFailed = () => <DocumentLocator county="placer" name="Sample Creek HOA" me="Jane Example" />;
