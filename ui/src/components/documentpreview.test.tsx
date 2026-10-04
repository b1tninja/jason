import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { DRIVE_COPY_LABEL, DocumentPreview, RECORDED_COPY, attachedCopies, thumbUrl, type EvidenceAnswer } from "./index";

const ID = "1FakeDeclDoc0001";
const PATH = "artifacts/site-docs/governing_documents/Declaration.pdf";
const today = new Date("2026-10-03T12:00:00");
const PNG = "data:image/png;base64,iVBORw0KGgo=";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const driveCopy = (): EvidenceAnswer => ({
  found: true, address: `drive:${ID}`, label: "Declaration", kind: "drive",
  sources: [{ name: "Copy from Drive", readAt: "2026-10-03T15:00:00+00:00", digest: "", fields: [], text: "", citation: "", caveat: "", note: "" }],
  changed: false, changedNote: "", link: `https://docs.google.com/document/d/${ID}/edit`, refresh: [], caveats: [], note: "",
  refreshable: { system: "Google Drive", what: "Export this file again from Drive" },
  documents: [{ id: "pdf", name: "Declaration.pdf", kind: "pdf", size: 2048, readAt: "2026-10-03T15:00:00+00:00", note: "" }],
});
const recorded = (): EvidenceAnswer => ({
  found: true, address: `file:${PATH}`, label: "Declaration.pdf", kind: "file",
  sources: [{ name: "Recorded copy", readAt: "2026-01-01T00:00:00+00:00", digest: "", fields: [], text: "", citation: "", caveat: "", note: "" }],
  changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "", refreshable: null,
  documents: [{ id: "pdf", name: "Declaration.pdf", kind: "pdf", size: 4096, readAt: "2026-01-01T00:00:00+00:00", note: "Recorded copy" },
    { id: "text", name: "Declaration.pdf, its text", kind: "text", size: 40, readAt: "2026-01-01T00:00:00+00:00", note: "" }],
});

describe("DocumentPreview", () => {
  it("with a Drive id alone, it is DrivePreview as it was: no label, Read from Drive, Open in Google", () => {
    render(<DocumentPreview name="Declaration" driveId={ID} driveEvidence={driveCopy()} signedIn driveThumb={PNG} today={today} />);
    expect(screen.queryByText(DRIVE_COPY_LABEL)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview Declaration" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read Declaration from Drive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", `https://docs.google.com/document/d/${ID}/edit`);
  });

  it("with a recorded PDF on disk, it shows page 1 from jason and opens the file through file:<path>, a logged view", async () => {
    const onView = vi.fn(async () => ({ kind: "pdf" as const, name: "Declaration.pdf", readAt: "", url: "/api/evidence/document/t", expires: "", caveats: [] }));
    render(<DocumentPreview name="Declaration" path={PATH} recordedEvidence={recorded()} signedIn by="A Manager" onView={onView} today={today} />);
    const img = screen.getByRole("img", { name: "Declaration" });
    expect(img.getAttribute("src")).toBe(thumbUrl(PATH, "2026-01-01T00:00:00+00:00"));
    expect(img.getAttribute("src")).toMatch(/^\/api\/thumb\?path=artifacts%2Fsite-docs%2F/);
    fireEvent.load(img);
    expect(screen.getByText(RECORDED_COPY)).toBeInTheDocument();                          // a single local copy is named
    expect(screen.queryByRole("button", { name: /from Drive/ })).not.toBeInTheDocument();   // a recorded copy does not change
    await userEvent.click(screen.getByRole("button", { name: "Preview Declaration, recorded copy" }));
    expect(onView).toHaveBeenCalledWith({ address: `file:${PATH}`, document: "pdf", by: "A Manager" });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTitle("Declaration.pdf")).toHaveAttribute("src", "/api/evidence/document/t");
  });

  it("with both, the recorded copy first and the Drive copy beside it, each labelled", () => {
    render(<DocumentPreview name="Declaration" driveId={ID} path={PATH} driveEvidence={driveCopy()} recordedEvidence={recorded()} signedIn
      driveThumb={PNG} recordedThumb={PNG} today={today} />);
    const regions = screen.getAllByRole("region");
    expect(regions.map((r) => r.getAttribute("aria-label"))).toEqual([`${RECORDED_COPY}: Declaration`, `${DRIVE_COPY_LABEL}: Declaration`]);
    expect(within(regions[0]).getByRole("button", { name: "Preview Declaration, recorded copy" })).toBeInTheDocument();
    expect(within(regions[1]).getByRole("button", { name: "Read Declaration from Drive" })).toBeInTheDocument();
    expect(within(regions[1]).getByText(/copy from/)).toHaveTextContent("copy from Oct 3");
  });

  it("signed out: placeholders that ask for a sign-in, never an image, and Preview off", () => {
    render(<DocumentPreview name="Declaration" driveId={ID} path={PATH} driveEvidence={driveCopy()} recordedEvidence={recorded()} signedIn={false}
      driveThumb={PNG} recordedThumb={PNG} today={today} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getAllByText("Sign in to see previews")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Preview Declaration, recorded copy" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Preview Declaration" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("link", { name: /Open in Google/ })).toBeInTheDocument();
  });

  it("fetches the recorded copy's answer from jason only", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      calls.push(url);
      const body = url.startsWith("/api/session") ? { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true } } : recorded();
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    render(<DocumentPreview name="Declaration" path={PATH} today={today} />);
    const preview = await screen.findByRole("button", { name: "Preview Declaration, recorded copy" });
    await waitFor(() => expect(preview).not.toHaveAttribute("aria-disabled"));
    expect(calls).toContain(`/api/evidence?address=${encodeURIComponent(`file:${PATH}`)}`);
    expect(calls.every((u) => u.startsWith("/api/"))).toBe(true);
  });

  it("names no copy when there is none", () => {
    render(<DocumentPreview name="Sample" />);
    expect(screen.getByText("No copy")).toBeInTheDocument();
  });
});

describe("attachedCopies", () => {
  it("reads a Drive file's id from its id or its link, a path under data/, and nothing from a sample", () => {
    expect(attachedCopies({ id: ID, kind: "doc", url: "" })).toEqual({ driveId: ID, path: "", kind: "doc" });
    expect(attachedCopies({ id: "x", kind: "pdf", url: `https://drive.google.com/file/d/${ID}/view` })).toEqual({ driveId: ID, path: "", kind: "pdf" });
    expect(attachedCopies({ name: "Bid", ref: "data/board/packet.pdf", real: true } as never)).toEqual({ driveId: "", path: "board/packet.pdf", kind: "pdf" });
    expect(attachedCopies({ id: "f1", kind: "pdf" })).toEqual({ driveId: "", path: "", kind: "pdf" });
  });
});
