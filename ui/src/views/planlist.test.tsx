/// <reference types="vite/client" />
/** The plans-of-writes list: opening a plan moves focus to its heading and brings it into view, a plan that is over has nothing "to
 * decide", the plan's header says what the list says, and the table says that it scrolls. */
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import appliedJson from "../../../tests/fixtures/approvals/example-village-applied.json";
import { PlanApprovals } from "./PlanApprovals";
import { ApproveBar } from "../components/ApproveBar";
import { resetServerSession } from "../lib/api";
import type { Approval } from "../lib/approvals";

const ID = "apr-20261003T183801-4f5b";
const planned = () => structuredClone(plannedJson) as unknown as Approval;
const applied = () => structuredClone(appliedJson) as unknown as Approval;
const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });

function serve(detail: object) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/session") return json({ token: "t", header: "X-Jason-Token", applyEnabled: false, liveChecks: true });
    if (url.startsWith("/api/approvals/audit")) return json({ entries: [], verify: { ok: true } });
    if (url.startsWith("/api/control-notices")) return json({ found: false });
    if (url === `/api/approvals/${ID}`) return json(detail);
    return json({ error: "no route" }, 404);
  }));
}
const page = (...approvals: object[]) => ({ approvals });

let scrolled: { block?: string; behavior?: string }[] = [];
const matchMedia = (reduce: boolean) => vi.fn((q: string) => ({ matches: reduce && q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }));

beforeEach(() => {
  scrolled = [];
  Element.prototype.scrollIntoView = function (arg?: boolean | ScrollIntoViewOptions) { scrolled.push((arg ?? {}) as { block?: string; behavior?: string }); };
  vi.stubGlobal("matchMedia", matchMedia(false));
});
afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

describe("choosing a plan", () => {
  it("moves focus to the plan's heading and scrolls it into view, smoothly", async () => {
    serve(planned());
    const { rerender } = render(<PlanApprovals page={page(planned())} me="A Manager" open="" onOpen={() => {}} />);
    expect(scrolled).toHaveLength(0);
    rerender(<PlanApprovals page={page(planned())} me="A Manager" open={ID} onOpen={() => {}} />);
    const heading = await screen.findByRole("heading", { level: 3, name: ID });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(scrolled.at(-1)).toMatchObject({ block: "start", behavior: "smooth" });
    expect(heading).toHaveAttribute("tabindex", "-1");
  });

  it("does not animate the scroll for a person who asked for less motion", async () => {
    vi.stubGlobal("matchMedia", matchMedia(true));
    serve(planned());
    render(<PlanApprovals page={page(planned())} me="A Manager" open={ID} onOpen={() => {}} />);
    await waitFor(() => expect(scrolled.length).toBeGreaterThan(0));
    expect(scrolled.at(-1)).toMatchObject({ block: "start", behavior: "auto" });
  });

  it("moves again when another plan is chosen", async () => {
    serve(planned());
    const { rerender } = render(<PlanApprovals page={page(planned())} me="A Manager" open={ID} onOpen={() => {}} />);
    await waitFor(() => expect(scrolled).toHaveLength(1));
    rerender(<PlanApprovals page={page(planned())} me="A Manager" open="" onOpen={() => {}} />);
    expect(screen.queryByRole("region", { name: "Open plan" })).toBeNull();
    rerender(<PlanApprovals page={page(planned())} me="A Manager" open={ID} onOpen={() => {}} />);
    await waitFor(() => expect(scrolled).toHaveLength(2));
  });
});

describe("the list", () => {
  it("says a sideways-scrolling table scrolls, in words, for a phone", () => {
    serve(planned());
    render(<PlanApprovals page={page(planned())} me="A Manager" open="" onOpen={() => {}} />);
    const plans = screen.getByRole("region", { name: "Plans of writes" });
    expect(within(plans).getByText(/The table scrolls sideways/)).toBeInTheDocument();
    expect(plans.querySelector(".table-scroll-cue .table-wrap")).not.toBeNull();
  });

  it("says 'to decide' of an open plan and not of an applied one", () => {
    serve(planned());
    const open = { ...planned(), id: "apr-open", title: "An open plan" };
    const closed = { ...applied(), id: "apr-closed", title: "A closed plan" };
    render(<PlanApprovals page={page(open, closed)} me="A Manager" open="" onOpen={() => {}} />);
    const rows = screen.getAllByRole("row");
    const openRow = rows.find((r) => within(r).queryByText("An open plan"))!;
    const closedRow = rows.find((r) => within(r).queryByText("A closed plan"))!;
    expect(openRow).toHaveTextContent(/\d+ to decide/);
    expect(closedRow).not.toHaveTextContent(/to decide/);
    expect(closedRow).toHaveTextContent("7 applied");
  });

  it("gives the list row and the open plan's header the same sentence for a plan in its pause", async () => {
    const signed = (() => {
      const a = planned();
      for (const i of a.items) if (i.class === "approvable") Object.assign(i, { decision: "approved", decidedBy: "A Manager", decidedAt: "2026-10-03T19:00:00+00:00" });
      return { ...a, status: "approved" as const, first: { name: "A Manager", at: "2026-10-03T19:00:00+00:00", fingerprint: a.fingerprint } };
    })();
    const waiting = { waitingToApply: true, waitingHours: 0, waitingStale: false, pausing: true };
    serve({ approval: signed, ...waiting });
    render(<PlanApprovals page={page({ ...signed, ...waiting })} me="A Manager" open={ID} onOpen={() => {}} />);
    const open = await screen.findByRole("region", { name: "Open plan" });
    await waitFor(() => expect(open.querySelector(".plan-state")).not.toBeNull());
    const sentence = "Signed, waiting to be applied · less than an hour · held by the board's pause";
    expect(open.querySelector(".plan-state")).toHaveTextContent(sentence);
    expect(screen.getByRole("table")).toHaveTextContent(sentence);
  });
});

describe("the approve bar", () => {
  it("keeps its explanations behind 'How this works' and its count of what is not part of the approval in view", () => {
    const a = planned();
    render(<ApproveBar approval={a} selected={[]} me="A Manager" />);
    const help = screen.getByText("How this works").closest("details")!;
    expect(help).not.toHaveAttribute("open");
    expect(within(help).getByText(/Signing does not make the changes/)).toBeInTheDocument();
    expect(within(help).getByText(/are recorded\. jason plans; only a named person decides and signs\./)).toBeInTheDocument();
    const held = document.querySelector(".approve-note-held");
    expect(held).not.toBeNull();                                  // the example plan has flagged and for-a-person items
    expect(help.contains(held)).toBe(false);
  });
});
