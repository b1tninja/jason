import { useEffect, useRef, type ReactNode } from "react";
import { RefreshAllEvidence } from "jason-ui";

/* Harness glue: a click POSTs `/api/evidence/refresh-all` with the plan's approval; there is no server in the capture.
 * The stub answers by approval, so cells that render at once each get their own reply. A cell past idle clicks the
 * button once after mount, since the status has no prop. */
const refs = [
  { label: "Civil Code 4041", address: "CIV 4041" },
  { label: "PayHOA request 501", address: "payhoa:submission:501" },
  { label: "PayHOA request 502", address: "payhoa:submission:502" },
  { label: "PayHOA request 503", address: "payhoa:submission:503" },
  "jason owner-info --apply --payhoa",
];

type Reply = { status: number; body: unknown } | "pending";
const summary = (refreshed: string[], failed: { address: string; error: string }[] = []) => ({
  approval: "", by: "Jane Example", at: "2026-10-03T19:02:00+00:00", refreshed, failed, skipped: 1,
});
const POSTS: Record<string, Reply> = {
  "owner-info-done": { status: 200, body: summary(["payhoa:submission:501", "payhoa:submission:502", "payhoa:submission:503"]) },
  "owner-info-partial": {
    status: 200,
    body: summary(["payhoa:submission:501", "payhoa:submission:502"], [{ address: "payhoa:submission:503", error: "PayHOA could not be read: HTTPError: 502" }]),
  },
  "owner-info-refused": { status: 409, body: { error: "Keeper is not signed in; run `jason login` in a terminal, then read them again." } },
  "owner-info-busy": "pending",
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  if (url.startsWith("/api/session")) return json(200, {});
  if (url !== "/api/evidence/refresh-all") return realFetch(input, init);
  const approval = (JSON.parse(String(init?.body ?? "{}")) as { approval?: string }).approval ?? "";
  const reply = POSTS[approval] ?? { status: 404, body: { error: `no plan ${approval}` } };
  if (reply === "pending") return new Promise<Response>(() => {});
  return json(reply.status, reply.body);
}) as typeof fetch;

/** Clicks the button once after mount, so the cell shows what the click leaves behind. */
function Clicked({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    ref.current?.querySelector<HTMLButtonElement>("button.evidence-reread-all")?.click();
  }, []);
  return <div ref={ref}>{children}</div>;
}

/** Idle: the plan names three PayHOA requests, so the button is offered; nothing is read until a person clicks. */
export const Idle = () => <RefreshAllEvidence approval="owner-info-idle" refs={refs} by="Jane Example" />;

/** Reading: the batch is in flight, the icon spins, the button is busy, and the status counts the requests. */
export const Reading = () => (
  <Clicked><RefreshAllEvidence approval="owner-info-busy" refs={refs} by="Jane Example" /></Clicked>
);

/** Done: every request read again, said with who read them and when. */
export const AllRead = () => (
  <Clicked><RefreshAllEvidence approval="owner-info-done" refs={refs} by="Jane Example" /></Clicked>
);

/** Partly read: two requests read, the third named with PayHOA's error, in the warning tone. */
export const OneFailed = () => (
  <Clicked><RefreshAllEvidence approval="owner-info-partial" refs={refs} by="Jane Example" /></Clicked>
);

/** Refused: the server's 409 said as it is, in the error tone. */
export const Refused = () => (
  <Clicked><RefreshAllEvidence approval="owner-info-refused" refs={refs} by="Jane Example" /></Clicked>
);

/** No one named: the button is dashed and disabled, with the reason beside it. */
export const NoName = () => <RefreshAllEvidence approval="owner-info-idle" refs={refs} by="" />;
