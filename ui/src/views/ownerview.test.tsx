import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SCREENS, findScreen } from "../App";
import { DOCK_DRAWERS } from "../components";
import { forView } from "../lib/api";
import owned from "../ownerScreens.json";
import { roomData } from "./meetingroom.fixture";

/** The owner view's guard on the page's side (docs/console/security-and-privacy.md, the owner view). The server is the
 * guard (`jason.web.extra.owner_view`, tests/test_web_owner_view.py); here: every screen the owner nav shows reads only
 * the sources `ownerScreens.json` names for it, each with `view=owner`, and renders no board-only section even when an
 * answer carries board rows beside the owner's. */

// Made-up board-only facts: a delinquent owner, a lien, a hearing, an executive item.
const OWNER = "Pat Delinquent";
const UNIT = "Unit 99";
const LIEN = "2099-0000777";
const HEARING = "Hearing on the fine for Unit 99";
const EXEC = "Executive: collections strategy for Pat Delinquent";
const POISON = [OWNER, UNIT, LIEN, HEARING, EXEC];

const lifecycle = { opened: "2099-01-02", process: "assessment lien", number: LIEN, status: "recorded", closed: "", debtor: [OWNER] };
const board = {
  ownersInDefault: [{ owner: OWNER, unit: UNIT, pastDueCents: 123_456 }], liens: [lifecycle], placed: [lifecycle],
  hearings: [{ address: UNIT, statement: HEARING }], executive: [{ title: EXEC }],
};

const disclosure = { key: "annual-budget-report", name: "Annual budget report", authority: "CIV 5300", rule: "30 to 90 days before the end of the fiscal year",
  windowOpens: "2099-10-02", next: "2099-12-01", delivered: null, deliveredAs: "", carries: [] };

// What each source answers: the owner's shape, with the board's rows beside it (a server that leaked would send them).
const ANSWERS: Record<string, unknown> = {
  "owner-digest": { ...board, found: true, asOf: "2099-10-01",
    nextMeeting: { date: "2099-10-21", regular: true, agendaPosted: false, docs: [], time: "6:30 PM", place: "Clubhouse" },
    latestMinutes: null, disclosures: [disclosure],
    policies: { adopted: [], standards: [], note: "No board policy is recorded as adopted yet." },
    recordsRequest: { screen: "records-requests", steps: ["Pick the records."], clocks: [], produced: "Once owners have accounts." },
    caveats: ["This is the owner view."] },
  "meeting-room": { ...roomData({
    roster: { synced: "2099-10-01", count: 1, rows: [{ name: OWNER, unit: UNIT }], note: "" },
    items: [...roomData().items.slice(0, 3), { id: "exec", kind: "exec", label: "Executive session", title: EXEC, facts: [HEARING], motion: `Move to discuss ${EXEC}`,
      threshold: "majority", recused: [], allot: 2, packet: [], brief: null, session: "executive session", matters: [EXEC] }, roomData().items[3]],
  }, { log: [{ at: "", title: `Lien ${LIEN} discussed`, tone: "warn" }], admitted: [OWNER] }), ...board },
  meetings: { ...board, found: true, meetings: [{ date: "2099-09-15", titles: [HEARING], has: { minutes: { "PayHOA library": 1 } }, checks: [EXEC] }], scheduleGaps: [UNIT] },
  calendar: { ...board, found: true, asOf: "2099-10-01", disclosures: [disclosure], obligations: [{ name: HEARING }], caveats: [] },
  reserves: { ...board, found: true, summary: { fiscalYear: 2099, percentFunded: 0.5, projectedEndOfYearCents: 1, requiredEndOfYearCents: 2 }, years: [],
    borrowings: [{ memo: OWNER }], otherWithdrawals: [{ memo: OWNER }], caveats: [] },
  "records-requests": { ...board, found: true, count: 1, counts: {}, kinds: [{ record: "minutes", label: "Minutes", citation: "CIV 5200(a)(8)", meaning: "", retention: "" }],
    vias: [], caveats: [], requests: [{ id: "r1", unit: UNIT, purpose: OWNER, records: ["minutes"] }] },
  insurance: { ...board, found: true, asOf: "2099-10-01", policies: [{ kind: "master", carrier: "Example Carrier", termEnd: "2100-01-01", terms: [{ start: "2099-01-01", end: "2100-01-01" }],
    number: LIEN, notices: [{ kind: HEARING }] }], claims: [{ claimNumber: LIEN, dateOfLoss: OWNER }], caveats: [] },
  "community-profile": { ...board, found: true, slug: "sample", name: "Sample Commons", corporateName: "", wordmark: "Sample Commons", site: "", pages: [], mailing: [],
    contacts: [], calendarId: "", timeZone: "", records: { kinds: [], onFile: 0, total: 0, note: "" }, asOf: "2099-10-01", caveats: [] },
};

// What only the board sees, as a section heading or a label: none of it may render in the owner view.
const BOARD_ONLY = [/Liens the association placed/, /Borrowings from the reserve/, /Records requests \(/, /Receive a request/, /Notices in the mail/,
  /Claims the mail acknowledges/, /Scheduled days with no record/, /only with checks/, /The reserve study/, /Deadlines as of/, /Host panel/];

// What each owner screen shows of the owner's answer, so a screen that rendered nothing cannot pass.
const SHOWN: Record<string, string> = {
  digest: "Next open meeting", room: "Renew the landscape contract", meetings: "2099-09-15", disclosures: "Annual budget report",
  reserves: "Reserve funding summary", "records-requests": "Request a record", insurance: "Example Carrier", "owner-page": "Sample Commons",
};

const NOT_SOURCES =/^\/api\/(session|file|thumb|drive\/thumb|evidence|write\/)/;

function serve() {
  const reads: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (!init?.method || init.method === "GET") reads.push(url);
    if (url.startsWith("/api/session")) return new Response(JSON.stringify({}), { status: 200 });
    const name = url.replace(/^\/api\//, "").split("?")[0];
    const body = ANSWERS[name];
    return new Response(JSON.stringify(body ?? { error: `no route ${url}` }), { status: body ? 200 : 404 });
  }));
  return reads;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

describe("the owner view's screens", () => {
  it("are exactly the screens ownerScreens.json names, which the server test reads too", () => {
    expect(SCREENS.filter((s) => s.owner).map((s) => s.id).sort()).toEqual(Object.keys(owned.screens).sort());
  });

  it("leave out the board's records screen and the dock: an owner asks for records through the request form", () => {
    expect(SCREENS.find((s) => s.id === "records")?.owner).toBeFalsy();
    expect(findScreen("records", "owner")?.id).toBe("records-requests");
    expect(findScreen("records", "board")?.id).toBe("records");
    expect(DOCK_DRAWERS.filter((d) => d.owner)).toEqual([]);
  });

  it("every read in the owner view carries view=owner; the session does not", () => {
    window.location.hash = "/digest?view=owner";
    expect(forView("/api/meetings")).toBe("/api/meetings?view=owner");
    expect(forView("/api/meetings?date=2099-09-15")).toBe("/api/meetings?date=2099-09-15&view=owner");
    expect(forView("/api/reserves?view=owner")).toBe("/api/reserves?view=owner");
    expect(forView("/api/session")).toBe("/api/session");
    window.location.hash = "/digest";
    expect(forView("/api/meetings")).toBe("/api/meetings");
  });

  it("the check sees a leak: the board's digest, given the same answer, shows the delinquent owner", async () => {
    window.location.hash = "/digest";
    serve();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(board), { status: 200 })));
    const { container } = render(SCREENS.find((s) => s.id === "digest")!.view({ audience: "board" }));
    await waitFor(() => expect(container.textContent).toContain(OWNER));
  });

  for (const [id, sources] of Object.entries(owned.screens)) {
    it(`${id}: reads only ${sources.join(", ")} as the owner view, and renders nothing of the board's`, async () => {
      window.location.hash = `/${id}?view=owner`;
      const reads = serve();
      const def = SCREENS.find((s) => s.id === id)!;
      const { container } = render(def.view({ audience: "owner" }));
      await waitFor(() => expect(reads.length).toBeGreaterThan(0));
      await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
      await new Promise((r) => setTimeout(r, 0));
      expect(screen.queryByRole("alert")).toBeNull();                 // the screen rendered its answer, not an error
      const read = reads.filter((u) => !NOT_SOURCES.test(u));
      for (const u of read) {
        expect(u).toMatch(/[?&]view=owner(&|$)/);
        expect(sources).toContain(u.replace(/^\/api\//, "").split("?")[0]);
      }
      const text = container.textContent ?? "";
      expect(text).toContain(SHOWN[id]);                               // it rendered the owner's answer
      for (const p of POISON) expect(text).not.toContain(p);
      for (const b of BOARD_ONLY) expect(text).not.toMatch(b);
      expect(screen.queryByLabelText("Host panel")).toBeNull();
    });
  }
});
