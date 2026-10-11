import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { bandTitle, hashWithLens, holdsAny, lensFromHash, notYours, officesText, todayCounts } from "../lib/officeView";
import type { OfficeViewData } from "../lib/officeView";
import { DisabledForOffice, OfficeBanner, OfficeBands, OfficeLens, OfficeToday } from "./OfficeLens";

/* Office views (docs/console/screens/office-views.md). Made-up offices and items only (plainly fake); the fixtures have the
   shape of `GET /api/office-view`. */

const OFFICES = ["president", "vice president", "secretary", "treasurer", "director", "manager"].map((office) => ({
  office, vacant: office === "vice president", holders: office === "vice president" ? 0 : 1,
}));

const BAND_ROWS = {
  waitingOnOffice: [
    { type: "letter", office: "treasurer", kind: "Sample notice", approver: "the treasurer", count: 2, screen: "approvals", text: "2 Sample notice waiting for the treasurer" },
    { type: "board-item", office: "treasurer", id: "i1", title: "A sample matter", priority: "normal", status: "proposed", due: null, shared: true, screen: "actions", text: "Board item: A sample matter" },
  ],
  signedWaiting: [] as unknown[],
  needsAttention: [
    { type: "duty", office: "treasurer", key: "books", title: "Review the sample reconciliations", due: "2099-09-05", standing: "overdue", urgency: "LEGAL", basis: "law", screen: "people", text: "Review the sample reconciliations, due 2099-09-05" },
  ],
  comingUp: [
    { type: "duty", office: "treasurer", key: "books", title: "Review the sample reconciliations", due: "2099-10-05", standing: "upcoming", urgency: "coming up", basis: "law", screen: "people", text: "Review the sample reconciliations, due 2099-10-05" },
  ],
  work: [
    { type: "run", office: "treasurer", id: "run-1", label: "Example cycle 2099", step: "example-cycle.2", stepTitle: "Approve the sample", due: "2099-10-23", screen: "", text: "Example cycle 2099: Approve the sample" },
  ],
};

function page(over: Partial<OfficeViewData> = {}): OfficeViewData {
  return {
    found: true, asOf: "2099-09-20", office: "treasurer", reading: ["treasurer"], title: "the treasurer", ownOffice: false, vacant: false,
    offices: OFFICES, mine: ["secretary"], bands: BAND_ROWS as never,
    counts: { waitingOnOffice: 2, signedWaiting: 0, needsAttention: 1, comingUp: 1, work: 1 }, bandErrors: {},
    notComposed: [{ band: "waitingOnOffice", what: "Plans in the approvals engine", why: "No office is attached to a plan." }],
    caveats: ["Reading another office's page is a lens, not that person's session."], ...over,
  };
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** A made-up server: `/api/office-view?office=X` answers by office (or `status`). Returns the urls asked. */
function serve(answers: Record<string, { status?: number; body: unknown }>) {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const u = String(url);
    urls.push(u);
    if (u.startsWith("/api/session")) return json(200, { token: "t", header: "X-Jason-Token", signedIn: { name: "A. Secretary", role: "secretary" } });
    if (u.startsWith("/api/office-view")) {
      const office = decodeURIComponent(u.split("office=")[1] ?? "");
      const a = answers[office] ?? { status: 404, body: { error: "no" } };
      return json(a.status ?? 200, a.body);
    }
    return json(404, { error: "not here" });
  }));
  return urls;
}

beforeEach(() => { resetServerSession(); window.location.hash = "#/digest"; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

describe("the lens in the URL", () => {
  it("reads the office a hash names, with a hyphen or a plus for a space, and none as my offices", () => {
    expect(lensFromHash("#/digest?as=treasurer")).toBe("treasurer");
    expect(lensFromHash("#/digest?as=vice-president")).toBe("vice president");
    expect(lensFromHash("#/digest?as=vice+president&view=board")).toBe("vice president");
    expect(lensFromHash("#/digest")).toBe("");
  });

  it("sets and clears the lens and keeps every other part of the hash", () => {
    expect(hashWithLens("#/digest", "vice president")).toBe("/digest?as=vice+president");
    expect(hashWithLens("#/digest?view=owner&as=secretary", "treasurer")).toBe("/digest?view=owner&as=treasurer");
    expect(hashWithLens("#/digest?as=secretary", "")).toBe("/digest");
    expect(hashWithLens("#/digest?as=secretary&x=1", "")).toBe("/digest?x=1");
  });
});

describe("words", () => {
  it("names the office in a band's heading when the lens is not the viewer's own, and says you when it is", () => {
    expect(bandTitle("work", { office: "treasurer", ownOffice: false })).toBe("Work for the treasurer");
    expect(bandTitle("work", { office: "", ownOffice: false })).toBe("Your work");
    expect(bandTitle("work", { office: "secretary", ownOffice: true })).toBe("Your work");
    expect(bandTitle("waitingOnOffice", { office: "treasurer", ownOffice: false })).toBe("Waiting on the treasurer");
    expect(bandTitle("needsAttention", { office: "manager", ownOffice: false })).toBe("Needs attention for the manager");
  });

  it("gives the reason a control is not live", () => {
    expect(notYours("treasurer", ["secretary"], "sign this")).toBe("Only the treasurer can sign this. You are the secretary.");
    expect(notYours(["president", "secretary"], ["treasurer"], "record this")).toBe("Only the president or the secretary can record this. You are the treasurer.");
    expect(notYours("treasurer", [])).toBe("Only the treasurer can do this. You hold no office.");
    expect(officesText(["secretary", "treasurer"])).toBe("the secretary and the treasurer");
    expect(holdsAny("treasurer", ["secretary", "treasurer"])).toBe(true);
    expect(holdsAny(["president"], ["treasurer"])).toBe(false);
  });
});

describe("OfficeLens and OfficeBanner", () => {
  it("lists My offices and each office, a vacant one marked, and reports a change", async () => {
    const onChange = vi.fn();
    render(<OfficeLens offices={OFFICES} mine={["secretary"]} value="" onChange={onChange} />);
    const select = screen.getByRole("combobox", { name: "Reading as" });
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "My offices (secretary)", "president", "vice president (vacant)", "secretary", "treasurer", "director", "manager",
    ]);
    await userEvent.selectOptions(select, "treasurer");
    expect(onChange).toHaveBeenCalledWith("treasurer");
  });

  it("offers no lens where the profile names no office", () => {
    const { container } = render(<OfficeLens offices={[]} mine={[]} value="" onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows Reading as the treasurer with a way back when the lens is not the viewer's own", async () => {
    const back = vi.fn();
    render(<OfficeBanner data={page()} onBack={back} />);
    expect(screen.getByText("Reading as the treasurer")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("you are the secretary");
    expect(screen.getByRole("status")).toHaveTextContent("shown but not live");
    await userEvent.click(screen.getByRole("button", { name: "Back to my offices" }));
    expect(back).toHaveBeenCalled();
  });

  it("shows no banner for the viewer's own offices, and says a vacant office is vacant", () => {
    const { rerender } = render(<OfficeBanner data={page({ office: "", ownOffice: false })} onBack={() => {}} />);
    expect(screen.queryByRole("status")).toBeNull();
    rerender(<OfficeBanner data={page({ office: "secretary", ownOffice: true })} onBack={() => {}} />);
    expect(screen.queryByRole("status")).toBeNull();
    rerender(<OfficeBanner data={page({ office: "vice president", vacant: true })} onBack={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Reading as the vice president");
    expect(screen.getByRole("status")).toHaveTextContent("vacant");
    expect(screen.getByRole("status")).toHaveTextContent("no one to do it");
  });
});

describe("DisabledForOffice", () => {
  it("renders the control as it is when the viewer holds the office", () => {
    render(<DisabledForOffice office="treasurer" mine={["secretary", "treasurer"]}><button>Sign</button></DisabledForOffice>);
    expect(screen.getByRole("button", { name: "Sign" })).toBeEnabled();
    expect(screen.queryByText(/Only the treasurer/)).toBeNull();
  });

  it("shows the control disabled, never hidden, with the reason beside it", () => {
    render(<DisabledForOffice office="treasurer" mine={["secretary"]} what="sign this"><button>Sign</button></DisabledForOffice>);
    expect(screen.getByRole("button", { name: "Sign" })).toBeDisabled();
    expect(screen.getByText("Only the treasurer can sign this. You are the secretary.")).toBeInTheDocument();
  });
});

describe("OfficeBands", () => {
  it("titles each band for the office and lists its rows with the screen that owns them", () => {
    render(<OfficeBands data={page()} />);
    for (const t of ["Waiting on the treasurer", "Needs attention for the treasurer", "Coming up for the treasurer", "Work for the treasurer"])
      expect(screen.getByRole("heading", { level: 2, name: t })).toBeInTheDocument();
    expect(screen.getByText("2 Sample notice waiting for the treasurer")).toBeInTheDocument();
    expect(screen.getByText("Example cycle 2099: Approve the sample")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "Open" }).map((a) => a.getAttribute("href"));
    expect(links).toEqual(["#/approvals", "#/actions", "#/people", "#/people"]);        // a run has no screen yet: no link
    expect(screen.getByText("legal")).toBeInTheDocument();                              // the urgency word, from the loader
    expect(screen.getByText("the board's")).toBeInTheDocument();
  });

  it("says you for the viewer's own offices and never for another's", () => {
    const { rerender } = render(<OfficeBands data={page({ office: "", ownOffice: false })} />);
    expect(screen.getByRole("heading", { level: 2, name: "Your work" })).toBeInTheDocument();
    rerender(<OfficeBands data={page()} />);
    expect(screen.queryByText(/\byour\b/i)).toBeNull();
    expect(screen.queryByText(/\byou are\b/i)).toBeNull();
  });

  it("says plainly that a band is empty, and why one could not be read", () => {
    const empty = page({
      bands: { waitingOnOffice: [], signedWaiting: [], needsAttention: [], comingUp: [], work: [] },
      counts: { waitingOnOffice: 0, signedWaiting: 0, needsAttention: 0, comingUp: 0, work: 0 },
      bandErrors: { needsAttention: "OSError: the schedule store is not readable" },
    });
    render(<OfficeBands data={empty} />);
    expect(screen.getByText("Nothing is waiting on the treasurer.")).toBeInTheDocument();
    expect(screen.getByText("No run is waiting on the treasurer.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("This band could not be read: OSError: the schedule store is not readable");
    expect(screen.queryByText("Nothing needs attention for the treasurer.")).toBeNull();     // a failed band is not "nothing"
  });

  it("lists what could not be composed and repeats the caveats", () => {
    render(<OfficeBands data={page()} />);
    expect(screen.getByRole("complementary", { name: "Not composed on this page" })).toHaveTextContent("Plans in the approvals engine");
    expect(screen.getByRole("complementary", { name: "Caveats" })).toHaveTextContent("a lens, not that person's session");
  });

  it("counts the rows a band holds beyond what it shows", () => {
    render(<OfficeBands data={page({ counts: { waitingOnOffice: 20, signedWaiting: 0, needsAttention: 1, comingUp: 1, work: 1 } })} />);
    expect(screen.getByText("18 more.")).toBeInTheDocument();
  });

  it("carries no person's name from a fixture that has none", () => {
    const { container } = render(<OfficeBands data={page()} />);
    expect(container.textContent).not.toMatch(/Pat Example|Lee President|@example\.org/);
  });
});

describe("OfficeToday", () => {
  it("reads my offices by default and the office the hash names, and goes back", async () => {
    const mine = page({ office: "", reading: ["secretary"], title: "the secretary", ownOffice: false });
    const urls = serve({ "": { body: mine }, treasurer: { body: page() } });
    render(<OfficeToday />);
    await screen.findByRole("heading", { level: 2, name: "My offices" });
    expect(screen.queryByText(/Reading as the/)).toBeNull();
    expect(screen.getByRole("heading", { level: 2, name: "Your work" })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Reading as" }), "treasurer");
    await screen.findByText("Reading as the treasurer");
    expect(window.location.hash).toBe("#/digest?as=treasurer");
    expect(screen.getByRole("heading", { level: 2, name: "Work for the treasurer" })).toBeInTheDocument();
    expect(urls.filter((u) => u.startsWith("/api/office-view"))).toEqual(["/api/office-view?office=", "/api/office-view?office=treasurer"]);

    await userEvent.click(screen.getByRole("button", { name: "Back to my offices" }));
    await waitFor(() => expect(screen.queryByText("Reading as the treasurer")).toBeNull());
    expect(window.location.hash).toBe("#/digest");
    expect(screen.getByRole("heading", { level: 2, name: "Your work" })).toBeInTheDocument();
  });

  it("opens on the office the URL names and keeps it across a reload", async () => {
    window.location.hash = "#/digest?as=vice-president";
    const urls = serve({ "vice president": { body: page({ office: "vice president", reading: ["vice president"], title: "the vice president", vacant: true }) } });
    render(<OfficeToday />);
    await screen.findByText("Reading as the vice president");
    expect(urls.filter((u) => u.startsWith("/api/office-view"))).toEqual(["/api/office-view?office=vice%20president"]);
    expect(screen.getByRole("combobox", { name: "Reading as" })).toHaveValue("vice president");
  });

  it("offers nothing where the loader refuses the viewer: Today as it was", async () => {
    serve({ "": { status: 403, body: { error: "Someone with no office doesn't open contact details and members' submissions (P2)." } } });
    const { container } = render(<OfficeToday />);
    await waitFor(() => expect(screen.queryByText(/Reading the office/)).toBeNull());
    expect(container).toBeEmptyDOMElement();
  });

  it("says so when the URL names a word that is no office, and offers the way back", async () => {
    window.location.hash = "#/digest?as=chairman";
    serve({ chairman: { status: 400, body: { error: "'chairman' is not an office. The offices are president, vice president." } } });
    render(<OfficeToday />);
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("is not an office");
    await userEvent.click(screen.getByRole("button", { name: "Back to my offices" }));
    expect(window.location.hash).toBe("#/digest");
  });
});

describe("the signed, waiting to be applied band", () => {
  const PLAN = { type: "plan-to-apply", id: "apr-20990101T000000-0001", kind: "owner-info-tags", title: "A sample plan", office: "", waitingHours: 75, stale: false, terminalOnly: false, needsSecond: false, note: "", screen: "approvals", text: "A sample plan: signed, waiting to be applied · 3 days" };
  const STALE = { ...PLAN, id: "apr-20990101T000000-0002", waitingHours: 120, stale: true, text: "A sample plan: signed 5 days ago; it will be planned again before it is applied" };
  const TERMINAL = { ...PLAN, id: "apr-20990101T000000-0003", terminalOnly: true, note: "Applied only at a terminal: jason sample --send --yes", text: "A sample letter plan: signed, waiting to be applied · 3 days" };
  const withPlans = (rows: unknown[]) => page({ bands: { ...BAND_ROWS, signedWaiting: rows } as never, counts: { waitingOnOffice: 2, signedWaiting: rows.length, needsAttention: 1, comingUp: 1, work: 1 } });

  it("is a band every office reads, titled in the same words for any lens", () => {
    const { container, rerender } = render(<OfficeBands data={withPlans([PLAN])} />);
    expect(screen.getByRole("heading", { level: 2, name: "Signed, waiting to be applied" })).toBeInTheDocument();
    rerender(<OfficeBands data={{ ...withPlans([PLAN]), office: "", ownOffice: false }} />);
    expect(screen.getByRole("heading", { level: 2, name: "Signed, waiting to be applied" })).toBeInTheDocument();
    expect(container.querySelector('[data-band="signedWaiting"]')).not.toBeNull();
  });

  it("lists each plan with how long it has waited and a link to the Approvals screen", () => {
    const { container } = render(<OfficeBands data={withPlans([PLAN])} />);
    const band = container.querySelector<HTMLElement>('[data-band="signedWaiting"]')!;
    expect(within(band).getByText("A sample plan: signed, waiting to be applied · 3 days")).toBeInTheDocument();
    expect(within(band).getByRole("link", { name: "Open" })).toHaveAttribute("href", "#/approvals");
  });

  it("says a plan older than its kind allows will be planned again before it is applied", () => {
    render(<OfficeBands data={withPlans([STALE])} />);
    expect(screen.getByText("A sample plan: signed 5 days ago; it will be planned again before it is applied")).toBeInTheDocument();
    expect(screen.getByText("will be planned again")).toBeInTheDocument();
  });

  it("notes a plan only a terminal applies, with its command", () => {
    render(<OfficeBands data={withPlans([TERMINAL])} />);
    expect(screen.getByText("applied at the terminal")).toBeInTheDocument();
    expect(screen.getByText("Applied only at a terminal: jason sample --send --yes")).toBeInTheDocument();
  });

  it("says plainly that nothing is signed and waiting, so an empty band is not mistaken for a failure", () => {
    render(<OfficeBands data={page()} />);
    expect(screen.getByText("No plan is signed and waiting to be applied.")).toBeInTheDocument();
  });

  it("carries no person's name from a fixture that has none", () => {
    const { container } = render(<OfficeBands data={withPlans([PLAN, STALE, TERMINAL])} />);
    expect(container.textContent).not.toMatch(/Pat Example|Lee President|@example\.org|Owner Example/);
  });

  it("is counted in the Today heading beside what waits on the office", async () => {
    expect(todayCounts(withPlans([PLAN, STALE]))).toBe("2 waiting on the treasurer · 2 plans signed, waiting to be applied · 1 needs attention");
    expect(todayCounts({ ...withPlans([PLAN]), office: "", ownOffice: false })).toBe("2 waiting on you · 1 plan signed, waiting to be applied · 1 needs attention");
    expect(todayCounts(page({ counts: { waitingOnOffice: 0, signedWaiting: 0, needsAttention: 0, comingUp: 3, work: 0 } }))).toBe("");
    serve({ treasurer: { body: withPlans([PLAN, STALE]) } });
    window.location.hash = "#/digest?as=treasurer";
    render(<OfficeToday />);
    expect(await screen.findByLabelText("Counts")).toHaveTextContent("2 plans signed, waiting to be applied");
  });
});
