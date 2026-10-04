import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DriveAttach } from "../components/DriveAttach";
import { resetServerSession } from "../lib/api";
import { GoverningDocumentsList } from "./AssociationRecordsView";
import { PacketFiles } from "./MeetingView";
import type { GoverningDocuments } from "./types";

const DOC = "1FakeDeclDoc0001";
const SHEET = "1FakeBudget00002";
const PATH = "artifacts/site-docs/governing_documents/Declaration.pdf";

/** jason-web, signed in as a manager: the session, an evidence answer with no copy, and a batch read. */
function mockFetch() {
  const calls: [string, string, unknown][] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push([init?.method ?? "GET", url, init?.body ? JSON.parse(String(init.body)) : null]);
    const body = url.startsWith("/api/session") ? { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true } }
      : url === "/api/evidence/refresh-many" ? { by: "A Manager", at: "x", refreshed: [`drive:${DOC}`], failed: [], skipped: 0 }
      : { found: true, address: "", label: "", kind: "drive", sources: [], changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "", documents: [] };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const governing = (over: Partial<GoverningDocuments> = {}): GoverningDocuments => ({
  found: true, count: 3, heldBack: 0, folders: ["governing"], caveats: ["A recorded instrument's PDF is the copy that governs."],
  rows: [
    { key: "decl", title: "Declaration", kind: "declaration", kindWord: "declaration", recorded: "2001-02-03", adopted: "", written: "", number: "2001-000123",
      driveKind: "doc", level: "P0", confidential: false,
      recordedCopy: { address: `file:${PATH}`, document: "pdf", name: "Declaration.pdf", kind: "pdf", level: "P0", source: "Recorded copy", thumb: true },
      driveCopy: { address: `drive:${DOC}`, name: "Declaration", kind: "pdf", level: "P0", source: "Drive copy", thumb: false,
        original: { url: `https://docs.google.com/document/d/${DOC}/edit`, label: "Open in Google" } } },
    { key: "rules", title: "Rules", kind: "operating_rules", kindWord: "operating rules", recorded: "", adopted: "2024-05-01", written: "", number: "",
      driveKind: "sheet", level: "P0", confidential: false, recordedCopy: null,
      driveCopy: { address: `drive:${SHEET}`, name: "Rules", kind: "pdf", level: "P0", source: "Drive copy" } },
    { key: "file-articles", title: "Articles", kind: "", kindWord: "", recorded: "", adopted: "", written: "", number: "", driveKind: "", level: "P0", confidential: false,
      recordedCopy: { address: "file:governing/Articles.pdf", document: "pdf", name: "Articles.pdf", kind: "pdf", level: "P0", source: "Recorded copy", thumb: true },
      driveCopy: null },
  ],
  ...over,
});

describe("Governing documents on the records screen", () => {
  it("lists each document with its recorded copy first and its Drive copy, and reads every Drive file on one click", async () => {
    const calls = mockFetch();
    render(<GoverningDocumentsList data={governing()} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    const decl = within(rows[0]);
    expect(decl.getByText("Declaration", { selector: "strong" })).toBeInTheDocument();
    expect(decl.getByText("recorded 2001-02-03")).toBeInTheDocument();
    expect(decl.getAllByRole("region").map((r) => r.getAttribute("aria-label"))).toEqual(["Recorded copy: Declaration", "Drive copy: Declaration"]);
    expect(within(rows[1]).getByText("adopted 2024-05-01")).toBeInTheDocument();
    expect(within(rows[1]).getByRole("region", { name: "Drive copy: Rules" })).toBeInTheDocument();       // labelled even alone
    expect(within(rows[2]).queryByRole("button", { name: /from Drive/ })).not.toBeInTheDocument();
    expect(screen.getByText("A recorded instrument's PDF is the copy that governs.")).toBeInTheDocument();
    const all = await screen.findByRole("button", { name: "Read every governing document from Drive" });
    await waitFor(() => expect(all).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(all);
    await waitFor(() => expect(calls.find(([m]) => m === "POST")).toEqual(
      ["POST", "/api/evidence/refresh-many", { addresses: [`drive:${DOC}`, `drive:${SHEET}`], by: "A Manager", batch: "governing" }]));
    const img = await within(rows[0]).findByRole("img", { name: "Declaration" });
    expect(img.getAttribute("src")).toMatch(/^\/api\/thumb\?path=artifacts%2Fsite-docs/);
    expect(document.querySelector("iframe")).toBeNull();
    expect(document.querySelector('a[href^="/api/file"]')).toBeNull();
  });

  it("says how many it held back", () => {
    mockFetch();
    render(<GoverningDocumentsList data={governing({ heldBack: 2, note: "2 held back (confidential); open the private view to see them." })} />);
    expect(screen.getByText("2 held back (confidential); open the private view to see them.")).toBeInTheDocument();
  });
});

describe("Packet files", () => {
  const items = [
    { id: "landscape", title: "Renew the landscape contract", include: true, packet: [
      { id: DOC, name: "Vendor A bid", kind: "doc", url: `https://docs.google.com/document/d/${DOC}/edit` },
      { id: "f2", name: "Sample.pdf", kind: "drive", url: "" }] },
    { id: "loan", title: "Reserve loan", include: false, packet: [{ id: SHEET, name: "Budget", kind: "sheet", url: "" }] },
    { id: "empty", title: "Nothing attached", include: true, packet: [] },
  ];

  it("in the meeting view: each file on the agenda as jason's copy, and Read every packet file from Drive", async () => {
    const calls = mockFetch();
    render(<PacketFiles items={items} />);
    expect(screen.getByRole("region", { name: "Packet files for Renew the landscape contract" })).toBeInTheDocument();
    expect(screen.queryByText("Reserve loan")).not.toBeInTheDocument();                       // not on the agenda
    expect(screen.queryByText("Nothing attached")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview Vendor A bid" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read Vendor A bid from Drive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", `https://docs.google.com/document/d/${DOC}/edit`);
    expect(screen.getByText("No copy")).toBeInTheDocument();                                   // the sample has none
    const all = await screen.findByRole("button", { name: "Read every packet file from Drive" });
    await waitFor(() => expect(all).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(all);
    await waitFor(() => expect(calls.find(([m]) => m === "POST")?.[2]).toEqual({ addresses: [`drive:${DOC}`], by: "A Manager", batch: "packet" }));
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("in the agenda wizard: each attached file gets its preview in place of the bare link", async () => {
    mockFetch();
    render(<DriveAttach files={items[0].packet} onChange={() => {}} previews />);
    expect(screen.getByRole("button", { name: "Preview Vendor A bid" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read Vendor A bid from Drive" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2);
    expect(await screen.findByText("No preview yet")).toBeInTheDocument();                   // jason keeps no copy yet
  });
});
