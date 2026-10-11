/// <reference types="vite/client" />
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import auditRaw from "../../../tests/fixtures/approvals/example-village-audit.jsonl?raw";
import { ApprovalsView } from "./ApprovalsView";
import { PlanPanel, approvalOf, auditOf, engineApprovals } from "./PlanApprovals";
import { KIND_NOTICES } from "../lib/controls.fixtures";
import { postJson, resetServerSession } from "../lib/api";
import type { Approval } from "../lib/approvals";

const ID = "apr-20261003T183801-4f5b";
const people = [{ name: "A Manager", role: "manager", approves: ["the manager"], canApproveBoard: false }];
const page = { found: true, letters: [], groups: { requested: [], approved: [], sent: [], drafts: [] }, pending: 0, people, stages: [], caveats: [], approvals: [plannedJson], approvalsOpen: 1 };
const entries = auditRaw.trim().split("\n").map((l) => JSON.parse(l));

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); document.head.querySelector('meta[name="jason-token"]')?.remove(); });

function stub(session: object) {
  const posted: { url: string; body: unknown; headers: Record<string, string> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });
    if (init?.method === "POST") {
      posted.push({ url, body: JSON.parse(String(init.body)), headers: init.headers as Record<string, string> });
      return json({ ...plannedJson, status: "in_review" });
    }
    if (url === "/api/session") return json(session);
    if (url.startsWith("/api/approvals/audit")) return json({ entries: entries.filter((e) => e.approval === ID), verify: { ok: true, why: "whole" } });
    if (url === `/api/approvals/${ID}`) return json(plannedJson);
    if (url === "/api/approvals") return json(page);
    return json({ error: "no route" }, 404);
  }));
  return posted;
}

describe("the Approvals screen's plans", () => {
  it("reads the engine list beside the letters and the engine's approval as the body", () => {
    expect(engineApprovals(page).map((a) => a.id)).toEqual([ID]);
    expect(engineApprovals({ letters: [{ key: "Drive/x.docx" }] })).toEqual([]);
    expect(approvalOf(plannedJson as never)?.id).toBe(ID);
    expect(approvalOf({ approval: plannedJson } as never)?.id).toBe(ID);
    expect(auditOf({ entries, verify: { ok: false, line: 3, why: "hash" } }).chain).toEqual({ ok: false, line: 3, why: "hash" });
    expect(auditOf(entries).entries).toHaveLength(22);
  });

  it("lists the server's summary rows, where items is a count and byClass counts them by class", async () => {
    const full = plannedJson as unknown as { items: { class: string }[] };
    const byClass: Record<string, number> = {};
    for (const i of full.items) byClass[i.class] = (byClass[i.class] ?? 0) + 1;
    const summary = { ...plannedJson, items: full.items.length, byClass, byDecision: {}, byResult: {}, approved: 0 };
    stub({ token: "tok-1", header: "X-Jason-Token", applyEnabled: false, liveChecks: true });
    vi.mocked(fetch).mockImplementation(async (url) =>
      new Response(JSON.stringify(url === "/api/approvals" ? { ...page, approvals: [summary] } : { error: "no route" }), { status: url === "/api/approvals" ? 200 : 404 }));
    render(<ApprovalsView />);
    const plans = await screen.findByRole("region", { name: "Plans of writes" });
    expect(within(plans).getByText(`${byClass.approvable} to decide`, { exact: false })).toBeInTheDocument();
  });

  it("opens a plan, decides an item as the signed-in person, and posts it with the write token", async () => {
    const posted = stub({ token: "tok-1", header: "X-Jason-Token", applyEnabled: false, liveChecks: true });
    const user = userEvent.setup();
    render(<ApprovalsView />);
    const plans = await screen.findByRole("region", { name: "Plans of writes" });
    await user.click(within(plans).getByText("Owner information: PayHOA tags and request completions"));
    const open = await screen.findByRole("region", { name: "Open plan" });
    expect(await within(open).findByRole("heading", { name: "To decide (12)" })).toBeInTheDocument();
    expect(await within(open).findByText(/Planned by jason: 17 items \(asked by A Manager\)/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Signed in as"), "A Manager");
    const first = open.querySelector<HTMLInputElement>("input[data-plan-check]")!;
    await user.click(first);
    await user.click(within(open).getByRole("button", { name: "Approve 1 selected" }));
    await user.click(within(open).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].url).toBe(`/api/approvals/${ID}/decide`);
    expect(posted[0].body).toEqual({ items: ["7344a0e1a0d1efa6"], decision: "approved", by: "A Manager", reason: "" });
    expect(posted[0].headers["X-Jason-Token"]).toBe("tok-1");
  });

  it("shows the kind's declared facts, recites an item's rule, links a held item's board item, and refuses an old plan's apply", async () => {
    const kindFacts = { key: "owner-info-tags", title: "Owner information tags", risk: "R2", riskWords: "member-facing record",
      approver: "one person", twoPerson: false, reversible: "a tag removed again", maxAgeHours: 24, cost: "" };
    const recitations = { "owner_info.FOR_A_PERSON": { found: true, citation: "owner_info.FOR_A_PERSON", text: "Test words recited whole." } };
    stub({ token: "tok-1", header: "X-Jason-Token", applyEnabled: false, liveChecks: true });
    const base = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (url, init) =>
      url === `/api/approvals/${ID}` ? new Response(JSON.stringify({ ...plannedJson, kindFacts, needsSecond: false, recitations }), { status: 200 }) : base(url, init));
    const user = userEvent.setup();
    render(<ApprovalsView />);
    const plans = await screen.findByRole("region", { name: "Plans of writes" });
    await user.click(within(plans).getByText("Owner information: PayHOA tags and request completions"));
    const open = await screen.findByRole("region", { name: "Open plan" });
    expect(await within(open).findByText(/risk member-facing record \(R2\)/)).toBeInTheDocument();
    expect(within(open).getByText(/planned again after 24 hours/)).toBeInTheDocument();
    expect(within(open).getAllByText("Rule: owner_info.FOR_A_PERSON").length).toBeGreaterThan(0);
    expect(within(open).getAllByRole("link", { name: "rental-approvals-4-15" })[0]).toHaveAttribute("href", "#/actions?item=rental-approvals-4-15");
    // The fixture was read live long ago: the engine refuses its apply, so the page says so and offers no apply.
    expect(within(open).getByText(/apply refuses it until it is planned again/)).toBeInTheDocument();
    expect(within(open).queryByText(/ready to apply/)).not.toBeInTheDocument();
  });

  it("reads the token from the page's meta tag first", async () => {
    const posted = stub({});
    const meta = document.createElement("meta");
    meta.name = "jason-token"; meta.content = "from-meta";
    document.head.appendChild(meta);
    await postJson(`/api/approvals/${ID}/submit`, { by: "A Manager" });
    expect(posted[0].headers["X-Jason-Token"]).toBe("from-meta");
  });
});

describe("a control's notice on an open plan", () => {
  const kind = (plannedJson as { kind: string }).kind;
  const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });
  /** The plan stubbed as stub() has it, with the notices route answered by `notices` (a status and body). */
  function withNotices(notices: { status: number; body: unknown }, plan: object = plannedJson) {
    stub({ token: "tok-1", header: "X-Jason-Token", applyEnabled: false, liveChecks: true });
    const base = vi.mocked(fetch).getMockImplementation()!;
    const asked: string[] = [];
    vi.mocked(fetch).mockImplementation(async (url, init) => {
      if (String(url).startsWith("/api/control-notices")) { asked.push(String(url)); return json(notices.body, notices.status); }
      if (url === `/api/approvals/${ID}` && !init?.method) return json(plan);
      return base(url, init);
    });
    return asked;
  }

  it("asks the loader for the plan's kind and shows the line at the top of the plan", async () => {
    const asked = withNotices({ status: 200, body: KIND_NOTICES });
    render(<PlanPanel id={ID} me="A Manager" onOpen={() => {}} />);
    expect(await screen.findByText(/Required by a control the board adopted on 2099-09-05:/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Payment signers" })).toHaveAttribute("href", "#/controls?key=payment-signers");
    expect(screen.getByText(/Takes effect 2099-11-14; not yet required/)).toBeInTheDocument();
    expect(asked[0]).toBe(`/api/control-notices?subject=${encodeURIComponent(kind)}`);
  });

  it("shows no line, and no error, when the loader refuses the viewer or fails", async () => {
    for (const status of [401, 403, 404, 500]) {
      const asked = withNotices({ status, body: { error: "Controls are for the board." } });
      const { container, unmount } = render(<PlanPanel id={ID} me="A Manager" onOpen={() => {}} />);
      expect(await screen.findByRole("heading", { name: "To decide (12)" })).toBeInTheDocument();
      await waitFor(() => expect(asked).toHaveLength(1));
      await new Promise((r) => setTimeout(r, 0));
      expect(container.querySelector(".control-notice")).toBeNull();
      expect(screen.queryByText(/Controls are for the board/)).toBeNull();
      unmount();
    }
  });

  it("shows the control's reason when a second signature is refused, and names who may sign", async () => {
    const why = "a control the board adopted on 2099-09-05 allows only the treasurer or the director to sign; B Director does not hold one of those offices";
    const plan = structuredClone(plannedJson) as unknown as Approval;
    for (const i of plan.items) if (i.class === "approvable") Object.assign(i, { decision: "approved", decidedBy: "A Manager" });
    plan.items.find((i) => i.class === "approvable")!.highStakes = true;
    const signed = { ...plan, status: "approved", first: { name: "A Manager", at: "2026-10-03T19:00:00+00:00", fingerprint: plan.fingerprint, role: "manager", via: "console" } };
    const posted = stub({ token: "tok-1", header: "X-Jason-Token", applyEnabled: false, liveChecks: true });
    const base = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (url, init) => {
      if (String(url).startsWith("/api/control-notices")) return json({ ...KIND_NOTICES, refusals: [] });
      if (url === `/api/approvals/${ID}` && !init?.method) return json(signed);
      if (url === `/api/approvals/${ID}/confirm`) { posted.push({ url: String(url), body: JSON.parse(String(init?.body)), headers: {} }); return json({ error: why }, 400); }
      return base(url, init);
    });
    const user = userEvent.setup();
    render(<PlanPanel id={ID} me="" onOpen={() => {}} />);
    expect(await screen.findByLabelText("Who may sign, by a control")).toHaveTextContent("Only the treasurer or the director may sign.");
    await user.type(screen.getByLabelText(/Your full name/), "B Director");
    await user.click(screen.getByRole("button", { name: "Confirm as B Director" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(screen.getAllByRole("alert").some((e) => e.textContent === why)).toBe(true));
    expect(posted.at(-1)?.body).toMatchObject({ by: "B Director" });
  });
});
