import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, resetServerSession, type PrivateView } from "../lib/api";
import { DOC_WORDS, Doc, DocList, type DocRef, type DocumentView, type EvidenceAnswer } from "./index";

// Made-up references; nothing here names a real document.
const today = new Date("2099-10-03T12:00:00");
const PNG = "data:image/png;base64,iVBORw0KGgo=";
const minutes: DocRef = { address: "file:board/minutes-draft-2099-10-01.md", document: "text", name: "Minutes draft, Oct 1",
  kind: "text", level: "P1", source: "File on disk", readAt: "2099-10-02T00:00:00+00:00", size: 2048 };
const letter: DocRef = { address: "file:mail/100/contents.pdf", document: "pdf", name: "Letter from a vendor", kind: "pdf",
  level: "P2", source: "Scan", readAt: "2099-10-01T15:00:00+00:00", size: 90_000, thumb: true };
const hearing: DocRef = { address: "file:zoom/hearings/Notice.pdf", document: "pdf", name: "Notice of hearing", kind: "pdf",
  level: "P3", source: "File on disk" };
const shut: PrivateView = { open: false, mayOpen: true, minutes: [15, 30, 60], default: 30 };
const pdfView = (name = "Letter from a vendor"): DocumentView => ({ kind: "pdf", name, readAt: "", url: "/api/evidence/document/t", expires: "", caveats: ["Unmasked: shown because A Manager asked; this view is logged."] });
const textView: DocumentView = { kind: "text", name: "Minutes draft, Oct 1", readAt: "", url: "", expires: "", text: "# Minutes\n\nThe board met.", caveats: [] };
const answer = (over: Partial<EvidenceAnswer> = {}): EvidenceAnswer => ({
  found: true, address: letter.address, label: letter.name, kind: "file", sources: [], changed: null, changedNote: "", link: "",
  refresh: [], caveats: [], note: "", refreshable: null,
  documents: [{ id: "pdf", name: "contents.pdf", kind: "pdf", size: 90_000, readAt: "", note: "" }], ...over,
});

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

describe("Doc chip", () => {
  it("names the document with its kind and opens it as one logged view", async () => {
    const onView = vi.fn(async () => pdfView());
    render(<Doc doc={letter} signedIn by="A Manager" onView={onView} today={today} />);
    const chip = screen.getByRole("button", { name: "Open Letter from a vendor" });
    expect(chip).toHaveAccessibleDescription("PDF");
    expect(onView).not.toHaveBeenCalled();                        // nothing is viewed on load
    await userEvent.click(chip);
    expect(onView).toHaveBeenCalledWith({ address: letter.address, document: "pdf", by: "A Manager" });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTitle("Letter from a vendor")).toHaveAttribute("src", "/api/evidence/document/t");
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(chip).toHaveFocus();                                   // focus returns to the opener
  });

  it("signed out: says to sign in, with the link, and posts nothing", async () => {
    const onView = vi.fn(async () => pdfView());
    render(<Doc doc={letter} signedIn={false} onView={onView} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Letter from a vendor" }));
    expect(screen.getByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with Google" })).toBeInTheDocument();
    expect(onView).not.toHaveBeenCalled();
  });

  it("not allowed: the server's reason, in words", async () => {
    const onView = vi.fn(async () => { throw new ApiError("The treasurer's office doesn't open executive-session and other restricted material (P3).", 403); });
    render(<Doc doc={letter} signedIn by="Pat Example" onView={onView} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Letter from a vendor" }));
    expect(await screen.findByText(/The treasurer's office doesn't open/)).toBeInTheDocument();
  });

  it("P3 marks the chip and needs the private view, with the switch's action when the person may open it", async () => {
    const onView = vi.fn(async () => pdfView());
    const onOpenPrivate = vi.fn();
    render(<Doc doc={hearing} signedIn by="Sam Secretary" privateView={shut} onView={onView} onOpenPrivate={onOpenPrivate} />);
    const chip = screen.getByRole("button", { name: "Open Notice of hearing" });
    expect(chip).toHaveAccessibleDescription("PDF, confidential");
    await userEvent.click(chip);
    expect(screen.getByText(/open the private view to see it/)).toBeInTheDocument();
    expect(onView).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Open the private view" }));
    expect(screen.getByRole("group", { name: "Open the private view" })).toBeInTheDocument();
  });

  it("no copy: says Not on disk with the command that fills it", async () => {
    const empty = answer({ documents: [], refresh: [{ command: "jason mail --sync", live: false, what: "" }] });
    render(<Doc doc={{ ...letter, document: undefined }} evidence={empty} signedIn by="A Manager" onView={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Letter from a vendor" }));
    expect(screen.getByText(DOC_WORDS.missing, { exact: false })).toBeInTheDocument();
    expect(screen.getByText("jason mail --sync")).toBeInTheDocument();
  });

  it("an error from the server is its sentence", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "The evidence store could not be read." }), { status: 500 })));
    render(<Doc doc={{ ...letter, document: undefined }} signedIn by="A Manager" onView={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Letter from a vendor" }));
    expect(await screen.findByText(/The evidence store could not be read/)).toBeInTheDocument();
  });
});

describe("Doc row and DocList", () => {
  it("lists each document with its kind and size, View, and its source; a view posts", async () => {
    const onView = vi.fn(async () => pdfView());
    render(<DocList docs={[letter, minutes]} signedIn by="A Manager" onView={onView} today={today} />);
    expect(screen.getByRole("heading", { name: "Documents" })).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText(/PDF · 88 KB/)).toHaveTextContent("copy from Oct 1");
    expect(within(rows[0]).getByText("Scan")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View Letter from a vendor" }));
    expect(onView).toHaveBeenCalledWith({ address: letter.address, document: "pdf", by: "A Manager" });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("signed out: View is off, and says why", () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ signedIn: null, signIn: { configured: true, start: "/auth/google" } }), { status: 200 })));
    render(<DocList docs={[letter]} by="A Manager" />);
    return waitFor(() => {
      expect(screen.getByText("Sign in with Google to view it.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "View Letter from a vendor" })).toHaveAttribute("aria-disabled", "true");
    });
  });

  it("a single row is a Doc too", () => {
    render(<Doc doc={minutes} variant="row" signedIn by="A Manager" onView={vi.fn()} today={today} />);
    expect(screen.getByRole("button", { name: "View Minutes draft, Oct 1" })).toBeInTheDocument();
  });
});

describe("Doc card", () => {
  it("is a sheet of paper with its name, source age, and Preview", async () => {
    const onView = vi.fn(async () => pdfView());
    render(<Doc doc={letter} variant="card" evidence={answer()} signedIn thumb={PNG} by="A Manager" onView={onView} today={today} />);
    expect(screen.getByRole("img", { name: "Letter from a vendor" })).toHaveAttribute("src", PNG);
    expect(screen.getByText(/copy from/)).toHaveTextContent("copy from Oct 1");
    await userEvent.click(screen.getByRole("button", { name: "Preview Letter from a vendor, scan" }));
    expect(onView).toHaveBeenCalledWith({ address: letter.address, document: "pdf", by: "A Manager" });
  });

  it("signed out: the placeholder asks for a sign-in, never a broken image", () => {
    render(<Doc doc={letter} variant="card" evidence={answer()} signedIn={false} thumb={PNG} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in to see previews")).toBeInTheDocument();
  });

  it("P3 outside the private view: held, with the switch's action", () => {
    render(<Doc doc={hearing} variant="card" evidence={answer({ documents: [] })} signedIn privateView={shut} thumb={PNG} by="Sam Secretary" />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText(/open the private view to see it/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open the private view" })).toBeInTheDocument();
  });

  it("a Drive card says No copy yet and Changed in Drive, from the reference", () => {
    const drive: DocRef = { address: "drive:1ExampleDriveFile01", name: "Example rules", kind: "pdf", source: "Drive copy",
      stale: "Changed in Drive since this copy", refreshable: { system: "Google Drive", what: "Export this file again from Drive" } };
    const none = answer({ address: drive.address, kind: "drive", documents: [], changed: true,
      refreshable: { system: "Google Drive", what: "Export this file again from Drive" } });
    render(<Doc doc={drive} variant="card" evidence={none} signedIn by="A Manager" onRead={vi.fn()} today={today} />);
    expect(screen.getByText("Changed in Drive since this copy")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview Example rules" })).toHaveAttribute("title", "No copy yet: read it from Drive first.");
    expect(screen.getByRole("button", { name: "Read Example rules from Drive" })).not.toHaveAttribute("aria-disabled");
  });
});

describe("Doc inline", () => {
  it("P0 or P1: the screen's subject, viewed on mount, in a region labelled by its name", async () => {
    const onView = vi.fn(async () => textView);
    render(<Doc doc={minutes} variant="inline" signedIn by="A Manager" onView={onView} today={today} />);
    const region = screen.getByRole("region", { name: "Minutes draft, Oct 1" });
    await waitFor(() => expect(onView).toHaveBeenCalledTimes(1));
    expect(await within(region).findByText("The board met.")).toBeInTheDocument();
    await userEvent.click(within(region).getByRole("button", { name: "Open in viewer" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onView).toHaveBeenCalledTimes(1);                       // the viewer shows the same view; no second POST
  });

  it("P2 or P3: Show the document first; the view posts on the click", async () => {
    const onView = vi.fn(async () => pdfView());
    render(<Doc doc={letter} variant="inline" signedIn by="A Manager" onView={onView} />);
    expect(onView).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: DOC_WORDS.show }));
    expect(onView).toHaveBeenCalledWith({ address: letter.address, document: "pdf", by: "A Manager" });
    expect(await screen.findByTitle("Letter from a vendor")).toBeInTheDocument();
    expect(screen.getByText(/^Unmasked:/)).toBeInTheDocument();
  });

  it("loading: Opening…, busy, while the sign-in is checked", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<Doc doc={minutes} variant="inline" />);
    expect(screen.getByText(DOC_WORDS.loading)).toBeInTheDocument();
  });

  it("missing: Not on disk with the command that fills it", () => {
    const empty = answer({ address: minutes.address, documents: [], refresh: [{ command: "jason board --minutes 2099-10-01", live: false, what: "" }] });
    render(<Doc doc={{ ...minutes, document: undefined }} variant="inline" evidence={empty} signedIn by="A Manager" onView={vi.fn()} />);
    expect(screen.getByText("jason board --minutes 2099-10-01")).toBeInTheDocument();
  });

  it("renders no /api/file link, no outside frame, and no absolute path", async () => {
    const { container } = render(<>
      <Doc doc={letter} signedIn by="A" onView={vi.fn()} />
      <Doc doc={letter} variant="card" evidence={answer()} signedIn thumb={PNG} />
      <DocList docs={[letter, minutes]} signedIn by="A" onView={vi.fn()} />
    </>);
    expect(container.querySelector('a[href*="/api/file"], img[src*="/api/file"]')).toBeNull();
    expect(container.querySelector('iframe[src*="google.com"]')).toBeNull();
    expect(container.innerHTML).not.toMatch(/[A-Za-z]:\\|"\/(?:Users|home)\//);
  });
});
