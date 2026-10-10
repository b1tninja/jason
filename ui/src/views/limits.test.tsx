import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { findScreen, SCREENS } from "../App";
import owned from "../ownerScreens.json";
import { LimitsView, nearestIn, type LimitRow, type LimitsPage } from "./LimitsView";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

// Made-up limits in the shape limits_view.py returns; no real service is called.
const row = (over: Partial<LimitRow>): LimitRow => ({
  key: "upload.max_bytes", kind: "size", unit: "bytes", description: "Largest file you can upload", value: 100e6, words: "100 MB",
  source: "default", sourceWords: "built in", default: 100e6, defaultWords: "100 MB", minimum: 1e6, maximum: 500e6, ceiling: 200e6,
  ceilingWords: "200 MB", rangeWords: "1 MB to 200 MB; built in 100 MB", scopes: ["instance", "community"], clamped: false, note: "",
  unreadable: [], set: {}, lastChange: {}, why: "Large uploads fill the disk.", whenHit: "The file is not saved; you are told its size.",
  editable: true, readOnlyWhy: "", ...over,
});
const PAGE: LimitsPage = {
  found: true, asOf: "2099-10-04T12:00:00+00:00", scope: "community", community: "example", canChange: true, role: "community administrator",
  limits: [
    row({}),
    row({ key: "fetch.max_bytes", description: "Largest page jason fetches", source: "community", sourceWords: "this community", value: 50e6, words: "50 MB",
          lastChange: { kind: "set", by: "Ada Admin", at: "2099-10-01T08:00:00+00:00", reason: "Small disk" }, clamped: true,
          note: "Set to 500 MB here; the operator's limit is 200 MB." }),
    row({ key: "split.auto_read", kind: "switch", unit: "switch", description: "Read each new part automatically", value: true, words: "on",
          default: true, defaultWords: "on", rangeWords: "on or off", editable: false, readOnlyWhy: "Only the operator sets this." }),
  ],
  groups: [{ kind: "size", name: "Size", keys: ["upload.max_bytes", "fetch.max_bytes"], open: true },
           { kind: "switch", name: "Switches", keys: ["split.auto_read"], open: false }],
  host: { drive: "D:", free: 5e10, freeWords: "46.6 GB" }, unreadable: [], caveats: ["A limit applies to new acts."],
};

interface Call { url: string; method: string; body?: Record<string, unknown> }
function serve(page: unknown, writes: Array<{ status: number; body: unknown }> = []) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const u = String(url);
    if (u.startsWith("/api/session")) return new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn: { name: "Ada Admin", role: "administrator" } }), { status: 200 });
    if (method === "POST") {
      calls.push({ url: u, method, body: JSON.parse(String(init?.body)) });
      const w = writes.shift() ?? { status: 200, body: {} };
      return new Response(JSON.stringify(w.body), { status: w.status, headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify(page), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
const PLAN = { ok: true, dryRun: true, note: "A dry run: nothing was written. Confirm to apply it.", recordedAs: { by: "Ada Admin", role: "community administrator" },
  changes: [{ key: "upload.max_bytes", words: "upload.max_bytes: 100 MB (default) -> 50 MB (community); a limit never removes or hides what exists." }] };

describe("LimitsView, Setup", () => {
  it("shows each limit in words with its source, range, ceiling, last change, and the host's free space", async () => {
    serve(PAGE);
    render(<LimitsView scope="community" />);
    const size = (await screen.findByRole("table", { name: "Size limits" }));
    const fetchRow = within(size).getByText("Largest page jason fetches").closest("tr")!;
    expect(fetchRow).toHaveTextContent("50 MB");
    expect(fetchRow).toHaveTextContent("this community");
    expect(fetchRow).toHaveTextContent("Ceiling here: 200 MB");
    expect(fetchRow).toHaveTextContent("Changed by Ada Admin, 2099-10-01");
    expect(within(fetchRow).getByRole("note")).toHaveTextContent("the operator's limit is 200 MB");   // the clamped note
    expect(screen.getByRole("status")).toHaveTextContent("46.6 GB");
    expect(screen.getByText("A limit applies to new acts.")).toBeInTheDocument();
  });

  it("opens why and when it is hit on demand, and says why a row cannot be edited", async () => {
    serve(PAGE);
    const user = userEvent.setup();
    render(<LimitsView scope="community" />);
    await user.click(await screen.findByRole("button", { name: /Show why and when it is hit: Largest file you can upload/ }));
    expect(screen.getByText("Large uploads fill the disk.")).toBeVisible();
    expect(screen.getByText("The file is not saved; you are told its size.")).toBeVisible();
    const sw = screen.getByText("Read each new part automatically").closest("tr")!;
    expect(sw).toHaveTextContent("Only the operator sets this.");
    expect(within(sw).queryByRole("button", { name: /^Change/ })).toBeNull();
  });

  it("previews a change as a dry run, then confirms it with a reason", async () => {
    const calls = serve(PAGE, [{ status: 200, body: PLAN }, { status: 200, body: { ...PLAN, dryRun: false, note: "Applied." } }]);
    const user = userEvent.setup();
    render(<LimitsView scope="community" />);
    await user.click(await screen.findByRole("button", { name: "Change Largest file you can upload" }));
    const value = screen.getByLabelText("New value");
    expect(value).toHaveFocus();
    await user.clear(value); await user.type(value, "50 MB");
    const preview = screen.getByRole("button", { name: "Preview the change" });
    expect(preview).toBeDisabled();                                                         // a reason is required
    await user.type(screen.getByLabelText(/Reason \(required/), "The disk is small");
    await user.click(preview);
    expect(calls[0].body).toMatchObject({ act: "set", changes: { "upload.max_bytes": "50 MB" }, reason: "The disk is small", dryRun: true });
    expect(calls[0].url).toBe("/api/write/limits/community");
    const region = await screen.findByRole("region", { name: "What will change" });
    expect(region).toHaveTextContent("100 MB (default) -> 50 MB (community)");
    expect(region).toHaveTextContent("Recorded as Ada Admin, community administrator");
    await user.click(screen.getByRole("button", { name: "Set largest file you can upload to 50 MB" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1].body).toMatchObject({ dryRun: false, reason: "The disk is small" });
    expect(await screen.findByText("Changed just now")).toBeInTheDocument();
    expect(screen.queryByLabelText("New value")).toBeNull();
  });

  it("shows a refusal in the server's words and offers the nearest allowed value", async () => {
    const said = "Refused: upload.max_bytes: 9 GB is above 200 MB, the highest allowed. The nearest allowed value is 200 MB. Nothing was changed.";
    serve(PAGE, [{ status: 400, body: { error: said } }]);
    const user = userEvent.setup();
    render(<LimitsView scope="community" />);
    await user.click(await screen.findByRole("button", { name: "Change Largest file you can upload" }));
    await user.clear(screen.getByLabelText("New value")); await user.type(screen.getByLabelText("New value"), "9 GB");
    await user.type(screen.getByLabelText(/Reason \(required/), "More room");
    await user.click(screen.getByRole("button", { name: "Preview the change" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(said);
    await user.click(screen.getByRole("button", { name: "Use 200 MB" }));
    expect(screen.getByLabelText("New value")).toHaveValue("200 MB");
    expect(screen.queryByRole("region", { name: "What will change" })).toBeNull();
  });

  it("resets to default with the same preview and confirm", async () => {
    const calls = serve(PAGE, [{ status: 200, body: { ...PLAN, changes: [{ key: "fetch.max_bytes", words: "fetch.max_bytes: 50 MB (community) -> back to the layer above" }] } }, { status: 200, body: {} }]);
    const user = userEvent.setup();
    render(<LimitsView scope="community" />);
    await user.click(await screen.findByRole("button", { name: "Reset Largest page jason fetches to default" }));
    await user.type(screen.getByLabelText(/Reason \(required/), "Back to normal");
    await user.click(screen.getByRole("button", { name: "Preview the change" }));
    expect(calls[0].body).toMatchObject({ act: "reset", keys: ["fetch.max_bytes"], dryRun: true });
    expect(await screen.findByRole("region", { name: "What will change" })).toHaveTextContent("back to the layer above");
    await user.click(screen.getByRole("button", { name: /^Reset largest page jason fetches/ }));
    await waitFor(() => expect(calls[1].body).toMatchObject({ act: "reset", dryRun: false }));
  });

  it("is read only for an officer: no Change or Reset button anywhere", async () => {
    serve({ ...PAGE, canChange: false, role: "", limits: PAGE.limits.map((l) => ({ ...l, editable: false, readOnlyWhy: "Only the community's administrator changes a limit." })) });
    render(<LimitsView scope="community" />);
    await screen.findByRole("table", { name: "Size limits" });
    expect(screen.queryByRole("button", { name: /^(Change|Reset)/ })).toBeNull();
    expect(screen.getByText(/Only the community's administrator changes them/)).toBeInTheDocument();
    expect(screen.getAllByText("Only the community's administrator changes a limit.").length).toBeGreaterThan(0);
  });

  it("warns when a limits file could not be read", async () => {
    serve({ ...PAGE, unreadable: ["instance limits.json"] });
    render(<LimitsView scope="community" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("instance limits.json");
  });
});

describe("LimitsView, Instance", () => {
  const INSTANCE: LimitsPage = {
    ...PAGE, scope: "instance", role: "instance operator",
    limits: [row({ value: null, words: "", ceiling: null, ceilingWords: "", topWords: "500 MB", communitiesMayGoUpTo: 500e6, rangeWords: "1 MB to 500 MB; built in 100 MB", source: undefined }),
             row({ key: "fetch.max_bytes", description: "Largest page jason fetches", value: 50e6, words: "50 MB", ceiling: 100e6, ceilingWords: "100 MB", topWords: "500 MB",
                   set: { by: "Opal Operator", at: "2099-10-02T00:00:00+00:00", reason: "Small host" } })],
    groups: [{ kind: "size", name: "Size", keys: ["upload.max_bytes", "fetch.max_bytes"], open: true }],
  };

  it("says an unset value uses the built-in one, and sends a ceiling with a set", async () => {
    const calls = serve(INSTANCE, [{ status: 200, body: PLAN }]);
    const user = userEvent.setup();
    render(<LimitsView scope="instance" />);
    const unset = (await screen.findByText("Largest file you can upload")).closest("tr")!;
    expect(unset).toHaveTextContent("not set; communities use 100 MB");
    expect(unset).toHaveTextContent("Communities may go up to 500 MB");
    await user.click(within(unset).getByRole("button", { name: "Change Largest file you can upload" }));
    await user.type(screen.getByLabelText("New value"), "80 MB");
    await user.type(screen.getByLabelText(/Ceiling for communities/), "200 MB");
    await user.type(screen.getByLabelText(/Reason \(required/), "Small host");
    await user.click(screen.getByRole("button", { name: "Preview the change" }));
    expect(calls[0].url).toBe("/api/write/limits/instance");
    expect(calls[0].body).toMatchObject({ act: "set", ceiling: "200 MB", dryRun: true });
  });
});

describe("Limits in the console", () => {
  it("has the two routes, Setup for the board's roles and Instance for admins only, and neither is an owner screen", () => {
    const setup = SCREENS.find((s) => s.id === "setup/limits");
    const instance = SCREENS.find((s) => s.id === "instance/limits");
    expect(setup?.roles).toEqual(["officer", "manager", "administrator"]);
    expect(instance?.admin).toBe(true);
    for (const s of [setup, instance]) expect(s?.owner).toBeFalsy();
    expect(Object.keys(owned.screens)).not.toContain("setup/limits");
    expect(findScreen("setup/limits")?.id).toBe("setup/limits");
    expect(findScreen("instance/limits")?.id).toBe("instance/limits");
    expect(findScreen("actions/anything")?.id).toBe("actions");                              // a deeper path still lands on its screen
  });

  it("reads the nearest allowed value out of a refusal", () => {
    expect(nearestIn("x is above 500 MB. The nearest allowed value is 500 MB. Nothing was changed.")).toBe("500 MB");
    expect(nearestIn("There is no nearest value.")).toBe("");
  });
});
