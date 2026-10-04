import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { CHANGED_IN_DRIVE, DrivePreview, ReadAllFromDrive, copyDay, driveIdOf, googleLink, type EvidenceAnswer } from "./index";

const ID = "1FakeDocId0001";
const today = new Date("2026-10-03T12:00:00");
const PNG = "data:image/png;base64,iVBORw0KGgo=";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const copy = (over: Partial<EvidenceAnswer> = {}): EvidenceAnswer => ({
  found: true, address: `drive:${ID}`, label: "Notice of Hearing", kind: "drive" as EvidenceAnswer["kind"],
  sources: [
    { name: "Copy from Drive", readAt: "2026-10-03T15:00:00+00:00", digest: "", fields: [], text: "", citation: "", caveat: "", note: "" },
    { name: "Drive catalog", readAt: "2026-10-02T08:00:00+00:00", digest: "", fields: [], text: "", citation: "", caveat: "", note: "" },
  ],
  changed: false, changedNote: "", link: `https://docs.google.com/document/d/${ID}/edit`,
  refresh: [], caveats: [], note: "", refreshable: { system: "Google Drive", what: "Export this file again from Drive" },
  documents: [{ id: "pdf", name: "Notice of Hearing.pdf", kind: "pdf", size: 2048, readAt: "2026-10-03T15:00:00+00:00", note: "" },
    { id: "text", name: "Notice of Hearing, its text", kind: "text", size: 20, readAt: "2026-10-03T15:00:00+00:00", note: "" }],
  ...over,
});
const noCopy = (): EvidenceAnswer => copy({ sources: [copy().sources[1]], documents: [], changed: null });

describe("DrivePreview", () => {
  it("shows the thumbnail like a sheet of paper, the copy's age, and Open in Google", () => {
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={copy()} signedIn thumb={PNG} today={today} />);
    const img = screen.getByRole("img", { name: "Notice of Hearing" });
    expect(img).toHaveAttribute("src", PNG);
    expect(img).toHaveAttribute("loading", "lazy");
    fireEvent.load(img);
    expect(screen.queryByText("No preview yet")).not.toBeInTheDocument();
    expect(screen.getByText(/copy from/)).toHaveTextContent("copy from Oct 3");
    const link = screen.getByRole("link", { name: /Open in Google/ });
    expect(link).toHaveAttribute("href", `https://docs.google.com/document/d/${ID}/edit`);
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.queryByText(CHANGED_IN_DRIVE)).not.toBeInTheDocument();
  });

  it("says No preview yet when jason keeps no copy, and never shows a broken image", () => {
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={noCopy()} signedIn today={today} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("No preview yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview Notice of Hearing" })).toHaveAttribute("aria-disabled", "true");
  });

  it("swaps a thumbnail that fails to load for the placeholder", () => {
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={copy()} signedIn thumb="/api/drive/thumb/x" today={today} />);
    fireEvent.error(screen.getByRole("img", { name: "Notice of Hearing" }));
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("No preview yet")).toBeInTheDocument();
  });

  it("signed out: the placeholder asks for a sign-in and the acts are off", () => {
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={copy()} signedIn={false} thumb={PNG} today={today} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in to see previews")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read Notice of Hearing from Drive" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Preview Notice of Hearing" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("link", { name: /Open in Google/ })).toBeInTheDocument();          // the original, always
  });

  it("says when Drive changed since the copy", () => {
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={copy({ changed: true })} signedIn thumb={PNG} today={today} />);
    expect(screen.getByText(CHANGED_IN_DRIVE)).toBeInTheDocument();
  });

  it("Preview opens the copy's PDF in the viewer, a logged view", async () => {
    const onView = vi.fn(async () => ({ kind: "pdf" as const, name: "Notice of Hearing.pdf", readAt: "2026-10-03T15:00:00+00:00", url: "/api/evidence/document/t", expires: "", caveats: ["Unmasked: shown because A Manager asked; this view is logged."] }));
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={copy()} signedIn thumb={PNG} today={today} by="A Manager" onView={onView} />);
    await userEvent.click(screen.getByRole("button", { name: "Preview Notice of Hearing" }));
    expect(onView).toHaveBeenCalledWith({ address: `drive:${ID}`, document: "pdf", by: "A Manager" });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Notice of Hearing.pdf" })).toBeInTheDocument();
  });

  it("Read from Drive asks the server for one read, and shows the fresh copy", async () => {
    const onRead = vi.fn(async () => copy({ changed: false, refreshed: { at: "2026-10-03T16:00:00+00:00", by: "A Manager", system: "Google Drive" } }));
    render(<DrivePreview driveId={ID} name="Notice of Hearing" evidence={noCopy()} signedIn today={today} by="A Manager" onRead={onRead} />);
    await userEvent.click(screen.getByRole("button", { name: "Read Notice of Hearing from Drive" }));
    expect(onRead).toHaveBeenCalledWith({ address: `drive:${ID}`, by: "A Manager" });
    expect(await screen.findByText("Read from Google Drive just now by A Manager.")).toBeInTheDocument();
  });

  it("fetches its evidence from jason, never Google, and posts a refresh through the server", async () => {
    const calls: [string, string][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push([init?.method ?? "GET", url]);
      const body = url.startsWith("/api/session") ? { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true } }
        : url === "/api/evidence/refresh" ? copy({ refreshed: { at: "x", by: "A Manager", system: "Google Drive" } })
        : noCopy();
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    render(<DrivePreview driveId={ID} name="Notice of Hearing" today={today} />);
    expect(await screen.findByText("No preview yet")).toBeInTheDocument();
    expect(calls).toContainEqual(["GET", `/api/evidence?address=drive%3A${ID}`]);
    const read = screen.getByRole("button", { name: "Read Notice of Hearing from Drive" });
    await waitFor(() => expect(read).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(read);
    await waitFor(() => expect(calls).toContainEqual(["POST", "/api/evidence/refresh"]));
    const img = await screen.findByRole("img", { name: "Notice of Hearing" });
    expect(img.getAttribute("src")).toMatch(new RegExp(`^/api/drive/thumb/${ID}\\?v=`));
    expect(calls.every(([, u]) => u.startsWith("/api/"))).toBe(true);                       // jason only
  });
});

describe("ReadAllFromDrive", () => {
  it("reads every file on one batch, signed in, and says what it read", async () => {
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") posts.push([url, JSON.parse(String(init.body))]);
      const body = url.startsWith("/api/session") ? { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true } }
        : { by: "A Manager", at: "x", refreshed: [`drive:${ID}`], failed: [{ address: "drive:1FakeSheet0002", error: "Budget is too large to export (Google exports up to 10 MB); open it in Google." }], skipped: 0 };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    const done = vi.fn();
    render(<ReadAllFromDrive driveIds={[ID, "1FakeSheet0002", ID, ""]} batch="templates" onDone={done} />);
    const button = await screen.findByRole("button", { name: "Read every template from Drive" });
    await waitFor(() => expect(button).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(button);
    expect(await screen.findByText(/Read 1 template from Google Drive just now by A Manager\. 1 could not be read: Budget is too large/)).toBeInTheDocument();
    expect(posts).toEqual([["/api/evidence/refresh-many", { addresses: [`drive:${ID}`, "drive:1FakeSheet0002"], by: "A Manager", batch: "templates" }]]);
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("signed out, it is off and says why", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ signIn: { configured: true, start: "/auth/google" } }), { status: 200 })));
    render(<ReadAllFromDrive driveIds={[ID]} />);
    expect(await screen.findByText("Sign in with Google to read them from Drive.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read every template from Drive" })).toHaveAttribute("aria-disabled", "true");
  });
});

describe("Drive links", () => {
  it("finds the id in a link and builds the editor's link by kind", () => {
    expect(driveIdOf(`https://docs.google.com/document/d/${ID}/edit`)).toBe(ID);
    expect(driveIdOf(`https://drive.google.com/open?id=${ID}`)).toBe(ID);
    expect(driveIdOf("https://example.com/x")).toBe("");
    expect(googleLink(ID, "sheet")).toBe(`https://docs.google.com/spreadsheets/d/${ID}/edit`);
    expect(copyDay("2025-12-30T12:00:00Z", today)).toBe("Dec 30, 2025");
  });
});
