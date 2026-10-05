import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adminSession, SCREENS } from "../App";
import owned from "../ownerScreens.json";
import { ageWords, StatusView, type Status } from "./StatusView";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const source = (over: Partial<Status["sources"][number]>): Status["sources"][number] => ({
  key: "drive", name: "Google Drive", what: "every file, read-only", store: "drive/files.json (syncedAt)",
  lastRead: "2099-10-03T06:10:00+00:00", ageSeconds: 3 * 86400 + 60, standing: "", note: "", fix: "jason drive --sync",
  staleAfterDays: null, staleSource: "", lastJob: null, signIn: "google", ...over,
});

// Made-up sources, sign-ins, gates, and failures.
const STATUS: Status = {
  found: true, asOf: "2099-10-04T12:00:00+00:00",
  sources: [
    source({}),
    source({ key: "zoom", name: "Zoom", what: "meetings", lastRead: "", ageSeconds: null, standing: "not signed in",
             note: "KeeperAuthRequired: sign in at a terminal", fix: "jason login", signIn: "keeper",
             lastJob: { id: 7, command: "jason zoom", status: "failed", at: "2099-10-02T03:00:00+00:00", summary: "", note: "" } }),
    source({ key: "county-tax", name: "County tax bills", what: "each parcel's tax bill", standing: "never read", lastRead: "", ageSeconds: null,
             note: "Its store holds no last read.", fix: "jason sync-tax", signIn: "" }),
  ],
  counts: { "no threshold": 1, "not signed in": 1, "never read": 1 },
  signIns: [{ at: "2099-10-04T08:12:00+00:00", event: "signed in", name: "Ada Sample", role: "admin", provider: "community" },
            { at: "2099-10-03T08:00:00+00:00", event: "refused", name: "", why: "[email] is not on the roster" }],
  gates: { found: true, stage: "ingest", command: "jason onboard", setup: "#/onboarding", gates: [
    { stage: "start", title: "Sign-in and sources", open: true },
    { stage: "ingest", title: "The documents read", open: false, opensWhen: "the library is read" },
  ] },
  failures: [{ kind: "job", source: "zoom", name: "Zoom", at: "2099-10-02T03:00:00+00:00", title: "Job 7: jason zoom failed",
               detail: "KeeperAuthRequired", fix: "jason jobs", job: 7 }],
  caveats: ["Read from disk only."],
};

function serve(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const answer = String(url).startsWith("/api/health") ? { ok: true, sources: ["status", "jobs"], writes: ["dock"] } : body;
    return new Response(JSON.stringify(answer), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

describe("StatusView", () => {
  it("renders each source with its last read, its standing only where given, and its fix", async () => {
    serve(STATUS);
    render(<StatusView />);
    const list = await screen.findByRole("list", { name: "Sources" });
    const drive = within(list).getByRole("listitem", { name: "Google Drive" });
    expect(drive).toHaveTextContent("2099-10-03 06:10 UTC");
    expect(drive).toHaveTextContent("(3 days ago)");
    expect(drive).toHaveTextContent("no threshold declared");                 // no word invented
    expect(drive.querySelector("details code")).toHaveTextContent("jason drive --sync");
    const zoom = within(list).getByRole("listitem", { name: "Zoom" });
    expect(zoom).toHaveTextContent("not signed in");
    expect(zoom).toHaveTextContent("no last read in its store");
    expect(within(zoom).getByText("jason login", { selector: "code" })).toBeVisible();
    expect(zoom).toHaveTextContent("Last queued run: job 7, failed");
    expect(within(list).getByRole("listitem", { name: "County tax bills" })).toHaveTextContent("never read");
  });

  it("renders the gates, the sign-ins, and the failures, with no control but copying a command", async () => {
    serve(STATUS);
    render(<StatusView />);
    const gates = await screen.findByRole("list", { name: "Setup's gates" });
    expect(within(gates).getAllByRole("listitem")).toHaveLength(2);
    expect(within(gates).getByText("The documents read").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("link", { name: "Open setup" })).toHaveAttribute("href", "#/onboarding");
    const signIns = screen.getByRole("list", { name: "Sign-ins" });
    expect(signIns).toHaveTextContent("signed in: Ada Sample, admin");
    expect(signIns).toHaveTextContent("[email] is not on the roster");
    expect(screen.getByRole("list", { name: "Failures" })).toHaveTextContent("Job 7: jason zoom failed");
    expect(await screen.findByText("Writes on: dock")).toBeInTheDocument();
    const buttons = screen.getAllByRole("button").map((b) => b.getAttribute("aria-label"));
    expect(new Set(buttons)).toEqual(new Set(["Copy command"]));
  });

  it("says when nothing failed", async () => {
    serve({ ...STATUS, failures: [] });
    render(<StatusView />);
    expect(await screen.findByText("No failed job, refresh, or sync on record.")).toBeInTheDocument();
  });
});

describe("Status in the nav", () => {
  it("is an admin-only screen, and no owner screen", () => {
    const status = SCREENS.find((s) => s.id === "status");
    expect(status?.admin).toBe(true);
    expect(status?.owner).toBeFalsy();
    expect(Object.keys(owned.screens)).not.toContain("status");
  });

  it("shows only to one of jason's admins as themselves", () => {
    expect(adminSession({ account: { admin: true } }, "administrator", "board")).toBe(true);
    expect(adminSession({ account: { admin: true } }, "officer", "board")).toBe(true);           // an admin who holds an office
    expect(adminSession({ account: { admin: false } }, "officer", "board")).toBe(false);
    expect(adminSession({ account: null }, undefined, "board")).toBe(false);
    expect(adminSession({ account: { admin: true }, acting: { name: "Pat", role: "treasurer" } }, "officer", "board")).toBe(false);
    expect(adminSession({ account: { admin: true } }, "administrator", "owner")).toBe(false);
  });
});

describe("ageWords", () => {
  it("words the server's seconds", () => {
    expect(ageWords(null)).toBe("");
    expect(ageWords(30)).toBe("under a minute");
    expect(ageWords(120)).toBe("2 minutes");
    expect(ageWords(3600)).toBe("1 hour");
    expect(ageWords(2 * 86400 + 5)).toBe("2 days");
  });
});
