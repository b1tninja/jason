import { useEffect, useRef, type ReactNode } from "react";
import { EvidencePanel, type EvidenceAnswer } from "jason-ui";

/* Harness glue: a panel with no `data` loads `GET /api/evidence?address=…`; there is no server in the capture. The stub
 * answers by address, so cells that render at once each get their own reply. A reply that never settles holds the
 * loading state; a 500 with an `error` shows the failure notice. */
const today = new Date("2026-10-03T12:00:00");
const STORED = "A stored copy is what jason read then, not the record now.";

const request = (n: number, over: Partial<EvidenceAnswer> = {}): EvidenceAnswer => ({
  found: true, address: `payhoa:submission:${n}`, label: `PayHOA request ${n}`, kind: "payhoa_submission",
  changed: false, changedNote: "",
  sources: [{
    name: "PayHOA request export", readAt: "2026-09-30T18:38:00+00:00", digest: "3f9a02c1d4e7aa51", text: "", citation: "", caveat: "", note: "",
    fields: [
      { name: "Owner", value: "Jane Example", masked: false },
      { name: "Mailing address", value: "123 Main St, Example City, CA 90000", masked: false },
      { name: "Email", value: "j***@example.com", masked: true },
      { name: "Rents the unit", value: "No", masked: false },
    ],
  }],
  link: `https://app.payhoa.example/requests/${n}`,
  refresh: [{ command: "jason sync-catalog --requests", live: true, what: "Reads the requests again", system: "PayHOA" }],
  refreshable: { system: "PayHOA", what: "Reads this request from PayHOA again" },
  caveats: [STORED], note: "",
  ...over,
});

type Reply = { status: number; body: unknown } | "pending";
const GETS: Record<string, Reply> = {
  "payhoa:submission:1201": { status: 200, body: request(1201) },
  "payhoa:submission:1202": "pending",
  "payhoa:submission:1203": { status: 500, body: { error: "evidence store is locked by another job; try again in a minute" } },
};

const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  if (url.startsWith("/api/session")) return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  if (!url.startsWith("/api/evidence?")) return realFetch(input, init);
  const address = new URLSearchParams(url.split("?")[1]).get("address") ?? "";
  const reply = GETS[address] ?? { status: 404, body: { error: `no evidence ${address}` } };
  if (reply === "pending") return new Promise<Response>(() => {});
  return new Response(JSON.stringify(reply.body), { status: reply.status, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

/** Clicks the first element matching `selector` once after mount: the panel's read-again state has no prop. */
function ClickOnce({ selector, children }: { selector: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    ref.current?.querySelector<HTMLElement>(selector)?.click();
  }, [selector]);
  return <div ref={ref} style={{ maxWidth: 560 }}>{children}</div>;
}

const frame = { maxWidth: 560 };

/** Fetched from the loader: an unchanged PayHOA request with its fields (the email masked), the read-again icon and Close, the PayHOA link, the command, and the caveat. */
export const Fetched = () => (
  <div style={frame}>
    <EvidencePanel address="payhoa:submission:1201" approval="owner-info-tags-0001" today={today} by="Jane Example" onClose={() => {}} />
  </div>
);

/** After a person clicked read-again: the fresh read replaced the answer in place, changed since the plan was read, and the status says who read it and when. */
export const ReadAgain = () => (
  <ClickOnce selector="button.evidence-reread">
    <EvidencePanel
      address="payhoa:submission:1204"
      approval="owner-info-tags-0001"
      today={today}
      by="Jane Example"
      onClose={() => {}}
      data={request(1204)}
      onRefresh={async () => request(1204, {
        changed: true, changedNote: "The mailing address answer differs from the one the plan read.",
        sources: [{
          ...request(1204).sources[0], readAt: "2026-10-03T19:02:00+00:00", digest: "9a0c11e2bb4f7d03",
          fields: [
            { name: "Owner", value: "Jane Example", masked: false },
            { name: "Mailing address", value: "456 Oak Ave, Example City, CA 90000", masked: false },
            { name: "Email", value: "j***@example.com", masked: true },
            { name: "Rents the unit", value: "No", masked: false },
          ],
        }],
        refreshed: { at: "2026-10-03T19:02:00+00:00", by: "Jane Example", system: "PayHOA" },
      })}
    />
  </ClickOnce>
);

/** The request's documents: a submission, a PDF with its size and note, a photo, each with a View button (viewing is a logged, named act). */
export const WithDocuments = () => (
  <div style={frame}>
    <EvidencePanel
      address="payhoa:submission:1205"
      today={today}
      by="Jane Example"
      data={request(1205, {
        refreshable: null,
        documents: [
          { id: "sub-1205", name: "Owner information, Unit 12", kind: "submission", size: 0, readAt: "2026-09-30T18:38:00+00:00", note: "" },
          { id: "pdf-7", name: "Lease addendum.pdf", kind: "pdf", size: 2_200_000, readAt: "2026-09-30T18:38:00+00:00", note: "Attached to the request." },
          { id: "img-2", name: "Fence photo.jpg", kind: "image", size: 48 * 1024, readAt: "2026-09-30T18:38:00+00:00", note: "" },
        ],
      })}
      onView={() => new Promise(() => {})}
    />
  </div>
);

/** No one named: the read-again icon is dashed (disabled) and, once tried, says to sign in or pick a name. */
export const NoNameToReadAs = () => (
  <ClickOnce selector="button.evidence-reread">
    <EvidencePanel
      address="payhoa:submission:1206"
      today={today}
      by=""
      onClose={() => {}}
      data={request(1206, { changed: null, changedNote: "jason cannot tell whether it changed: the plan kept no digest." })}
      onRefresh={async () => request(1206)}
    />
  </ClickOnce>
);

/** Still loading: the loader has not answered, so the panel says it is reading what jason stored. */
export const StillReading = () => (
  <div style={frame}>
    <EvidencePanel address="payhoa:submission:1202" label="PayHOA request 1202" onClose={() => {}} />
  </div>
);

/** The loader failed: the server's words in the error tone, under the address, never an empty box. */
export const LoaderFailed = () => (
  <div style={frame}>
    <EvidencePanel address="payhoa:submission:1203" label="PayHOA request 1203" onClose={() => {}} />
  </div>
);
