import { useEffect, useRef, type ReactNode } from "react";
import { SupplyItems } from "jason-ui";

// Made-up run and ids. "Check the list" asks the server for a dry run that writes nothing; there is no server in the capture, so the
// cells that press it answer from the stub below (shape `SupplyDry`). The ids are opaque handles, never names or addresses.
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  if (url.startsWith("/api/session")) return json({ token: "", header: "X-Jason-Token" });
  if (url.startsWith("/api/write/work/")) {
    const body = JSON.parse(String(init?.body ?? "{}"));
    const items: string[] = body.items ?? [];
    if (items.some((i) => /\s|@/.test(i))) return json({ error: "An item id is an opaque handle: no spaces and no @. Item 2 is neither." }, 400);
    const there = items.filter((i) => i === "req-1002");
    return json({
      ok: true, act: "supply-items", dryRun: true, set: body.set, wouldAdd: items.filter((i) => !there.includes(i)), alreadyThere: there,
      withDates: [], text: "", record: body.record ?? "", n: 9,
    });
  }
  return realFetch(input, init);
}) as typeof fetch;

const STEP = { n: 3, title: "Answer each request" };
const RUN = { definition: "respond-batch", id: "run-0a1b2c3d4e" };
const VIEWER = { known: true, name: "A. Manager", actingAs: "" };
const acts = (over: object = {}): any => ({ busy: false, said: null, send: async () => true, clear: () => {}, ...over });
const frame = { maxWidth: 640 } as const;

/** Type into the real form, then press "Check the list", the way a person would. */
function Doing({ text, children }: { text: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = box.current;
    if (!root) return;
    const t = setTimeout(() => {
      const area = root.querySelector("textarea");
      if (!area) return;
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set?.call(area, text);
      area.dispatchEvent(new Event("input", { bubbles: true }));
      setTimeout(() => root.querySelector<HTMLButtonElement>("button:not([disabled])")?.click(), 60);
    }, 30);
    return () => clearTimeout(t);
  }, []);
  return <div ref={box}>{children}</div>;
}

/** The form at rest: the ids one to a line, an optional record, and "Check the list" waiting for at least one id. */
export const Empty = () => (
  <div style={frame}><SupplyItems step={STEP} run={RUN} viewer={VIEWER} acts={acts()} setName="requests" /></div>
);

/** A step over the run's own items (the set named ""): the label says so rather than naming a set. */
export const RunsOwnItems = () => (
  <div style={frame}><SupplyItems step={STEP} run={RUN} viewer={VIEWER} acts={acts()} setName="" /></div>
);

/** Checked and passing: one id is already in the set, so three would be added, and a Confirm waits before anything is recorded. */
export const CheckedPassing = () => (
  <div style={frame}>
    <Doing text={"req-1001\nreq-1002\nreq-1003\nreq-1004"}>
      <SupplyItems step={STEP} run={RUN} viewer={VIEWER} acts={acts()} setName="requests" />
    </Doing>
  </div>
);

/** Checked and refused: the server's own sentence shows, since an id may not be a name or an address. */
export const CheckedRefused = () => (
  <div style={frame}>
    <Doing text={"req-1001\nA. Owner"}>
      <SupplyItems step={STEP} run={RUN} viewer={VIEWER} acts={acts()} setName="requests" />
    </Doing>
  </div>
);
