import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { KeyDocuments, type KeyDocumentsData } from "./KeyDocuments";
import { ApiError } from "../lib/api";
import { DOC_WORDS, Doc, type DocRef, type DocumentView } from "./index";

const data: KeyDocumentsData = {
  found: true,
  association: "Example Village HOA",
  counts: { held: 1, located: 1, linked: 1, expected: 1 },
  statuses: [{ value: "held", meaning: "a copy is held" }],
  limits: { maxUploadBytes: 1024, suffixes: [".pdf"] },
  groups: [
    {
      item: "declaration", title: "The declaration (CC&Rs), the recorded copy", why: "CIV 4135", entries: [
        { key: "declaration", item: "declaration", title: "The declaration (CC&Rs), the recorded copy", number: "2001-0000020", recorded: "2001-03-08",
          status: "held", statusWhy: "specification pin", copies: [{ kind: "drive", ref: "1ExampleDriveFile01", name: "CC&Rs.pdf", source: "specification pin", url: "https://drive.google.com/open?id=1ExampleDriveFile01",
            doc: { address: "drive:1ExampleDriveFile01", name: "CC&Rs.pdf", kind: "pdf", level: "P0", source: "Drive copy", original: { url: "https://drive.google.com/open?id=1ExampleDriveFile01", label: "Open in Google" } } },
            { kind: "disk", ref: "governing/Declaration 2001-0000020.pdf", name: "Declaration 2001-0000020.pdf", source: "recorded copy on disk",
              doc: { address: "file:governing/Declaration 2001-0000020.pdf", document: "pdf", name: "Declaration 2001-0000020.pdf", kind: "pdf", level: "P0", source: "Recorded copy" } }],
          links: [], leads: [{ number: "2001-0000020", filing: "AMENDED RESTRICTION", tie: "names the association" }], notes: [] },
        { key: "declaration/2001-0000010", item: "declaration", title: "Declaration (rescinded)", number: "2001-0000010", recorded: "2001-03-01",
          status: "located", supersededBy: "2001-0000020", copies: [], links: [], leads: [], notes: ["recital F"] },
      ],
    },
    {
      item: "amendments", title: "Each amendment to the declaration", entries: [
        { key: "amendments/2010-0000100", item: "amendments", title: "First Amendment", number: "2010-0000100", recorded: "2010-02-01", status: "linked",
          copies: [], links: [{ id: "l-1", kind: "upload", ref: "key-documents/x/files/a/First.pdf", name: "First.pdf", by: "Jane Example", at: "2026-10-03T10:00:00+00:00",
            doc: { address: "file:key-documents/x/files/a/First.pdf", document: "pdf", name: "First.pdf", kind: "pdf", level: "P0", source: "Recorded copy" } }],
          leads: [], notes: [] },
      ],
    },
    { item: "maps", title: "Subdivision and parcel maps", entries: [
      { key: "maps", item: "maps", title: "Subdivision and parcel maps", number: "", recorded: "", status: "expected", copies: [], links: [], leads: [], notes: [] },
    ] },
  ],
  caveats: ["A located recording number is a lead, not a pin."],
};

describe("KeyDocuments", () => {
  it("shows each document's number, status word, copies, leads as leads, and the caveats", () => {
    render(<KeyDocuments data={data} by="Jane Example" />);
    const decl = screen.getByRole("listitem", { name: "The declaration (CC&Rs), the recorded copy (2001-0000020)" });
    expect(within(decl).getByText("held")).toBeInTheDocument();
    expect(within(decl).getByText("Mar 8, 2001").closest("time")).toHaveAttribute("datetime", "2001-03-08");
    expect(within(decl).getByRole("button", { name: "Open CC&Rs.pdf" })).toBeInTheDocument();
    expect(within(decl).getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", "https://drive.google.com/open?id=1ExampleDriveFile01");
    expect(within(decl).getByText("· Recorded copy")).toBeInTheDocument();
    expect(within(decl).getByText("· Drive copy (specification pin)")).toBeInTheDocument();
    expect(within(decl).getByText(/Lead from the county index, not a pin/)).toBeInTheDocument();
    expect(screen.getByText(/Rescinded and superseded by/)).toBeInTheDocument();
    expect(screen.getByText("A located recording number is a lead, not a pin.")).toBeInTheDocument();
    expect(screen.getByText("Writing as Jane Example")).toBeInTheDocument();
  });

  it("links a Drive copy only after the Confirm, in the person's name", async () => {
    const post = vi.fn(async () => ({ ok: true }));
    const changed = vi.fn();
    const user = userEvent.setup();
    render(<KeyDocuments data={data} by="Jane Example" post={post} onChanged={changed} />);
    const maps = screen.getByRole("listitem", { name: "Subdivision and parcel maps" });
    await user.click(within(maps).getByRole("button", { name: "Link or upload a copy" }));
    await user.type(within(maps).getByLabelText("Drive link or id"), "https://drive.google.com/file/d/1AbCdEfGhIjK/view");
    await user.click(within(maps).getByRole("button", { name: "Link this copy" }));
    expect(post).not.toHaveBeenCalled();
    expect(within(maps).getByRole("group", { name: "Link" })).toHaveTextContent("as Jane Example");
    await user.click(within(maps).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith("/api/write/key-documents/maps", { action: "link", kind: "drive", ref: "https://drive.google.com/file/d/1AbCdEfGhIjK/view", note: "", by: "Jane Example" });
    expect(await within(maps).findByRole("status")).toHaveTextContent("Linked");
    expect(changed).toHaveBeenCalled();
  });

  it("unlinks behind a Confirm and says the file stays", async () => {
    const post = vi.fn(async () => ({ ok: true }));
    const user = userEvent.setup();
    render(<KeyDocuments data={data} by="Jane Example" post={post} />);
    const first = screen.getByRole("listitem", { name: "First Amendment (2010-0000100)" });
    await user.click(within(first).getByRole("button", { name: "Unlink" }));
    expect(within(first).getByRole("group", { name: "Unlink" })).toHaveTextContent("The file is not deleted");
    await user.click(within(first).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/write/key-documents/amendments/2010-0000100", { action: "unlink", link: "l-1", by: "Jane Example" }));
    expect(await within(first).findByRole("status")).toHaveTextContent("The file stays where it is");
  });

  it("asks what was looked for before recording missing, and shows a refusal as an alert", async () => {
    const post = vi.fn(async () => { throw new Error("say what was looked for"); });
    const user = userEvent.setup();
    render(<KeyDocuments data={data} by="Jane Example" post={post} />);
    const maps = screen.getByRole("listitem", { name: "Subdivision and parcel maps" });
    await user.click(within(maps).getByRole("button", { name: "Record a status" }));
    expect(within(maps).queryByRole("button", { name: "Record missing" })).toBeNull();
    await user.type(within(maps).getByLabelText("What was looked for, and where"), "the prior manager's files");
    await user.click(within(maps).getByRole("button", { name: "Record missing" }));
    await user.click(within(maps).getByRole("button", { name: "Yes, do it" }));
    expect(await within(maps).findByRole("alert")).toHaveTextContent("Nothing was written.");
  });

  it("refuses an upload over the size limit before anything is sent", async () => {
    const post = vi.fn();
    const user = userEvent.setup();
    render(<KeyDocuments data={data} by="Jane Example" post={post} />);
    const maps = screen.getByRole("listitem", { name: "Subdivision and parcel maps" });
    await user.click(within(maps).getByRole("button", { name: "Link or upload a copy" }));
    await user.click(within(maps).getByLabelText("Upload a file"));
    await user.upload(within(maps).getByLabelText("File to upload"), new File(["x".repeat(2048)], "Map.pdf", { type: "application/pdf" }));
    expect(within(maps).getByRole("alert")).toHaveTextContent("Put it on Drive and link it there.");
    expect(within(maps).queryByRole("button", { name: "Upload and link" })).toBeNull();
  });

  it("filters to the documents not yet held or linked, and asks for a name when no one is signed in", async () => {
    const user = userEvent.setup();
    render(<KeyDocuments data={data} />);
    expect(screen.getByLabelText("Your name")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Show"), "open");
    expect(screen.queryByRole("listitem", { name: "First Amendment (2010-0000100)" })).toBeNull();
    expect(screen.getByRole("listitem", { name: "Subdivision and parcel maps" })).toBeInTheDocument();
  });
});

describe("KeyDocuments: each copy is a Doc", () => {
  const recorded: DocRef = { address: "file:governing/Declaration 2001-0000020.pdf", document: "pdf", name: "Declaration 2001-0000020.pdf",
    kind: "pdf", level: "P0", source: "Recorded copy" };
  const view: DocumentView = { kind: "pdf", name: "Declaration 2001-0000020.pdf", readAt: "", url: "/api/evidence/document/t", expires: "", caveats: [] };

  it("the chip renders from a static reference, and opening it posts one view", async () => {
    const onView = vi.fn(async () => view);
    render(<KeyDocuments data={data} by="Jane Example" docProps={{ signedIn: true, by: "Jane Example", onView }} />);
    const decl = screen.getByRole("listitem", { name: "The declaration (CC&Rs), the recorded copy (2001-0000020)" });
    expect(onView).not.toHaveBeenCalled();
    await userEvent.click(within(decl).getByRole("button", { name: "Open Declaration 2001-0000020.pdf" }));
    expect(onView).toHaveBeenCalledWith({ address: recorded.address, document: "pdf", by: "Jane Example" });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("signed out and not allowed say their words", async () => {
    const { unmount } = render(<Doc doc={recorded} signedIn={false} onView={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Open Declaration 2001-0000020.pdf" }));
    expect(screen.getByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    unmount();
    const refuse = vi.fn(async () => { throw new ApiError("The office doesn't open this.", 403); });
    render(<KeyDocuments data={data} by="Jane Example" docProps={{ signedIn: true, by: "Jane Example", onView: refuse }} />);
    await userEvent.click(screen.getByRole("button", { name: "Open First.pdf" }));
    expect(await screen.findByText(/The office doesn't open this/)).toBeInTheDocument();
  });

  it("renders no /api/file href, no outside frame, and no absolute path", () => {
    const { container } = render(<KeyDocuments data={data} by="Jane Example" docProps={{ signedIn: true, by: "Jane Example", onView: vi.fn() }} />);
    expect(container.querySelector('a[href*="/api/file"], img[src*="/api/file"]')).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.innerHTML).not.toMatch(/[A-Za-z]:\|"\/(?:Users|home)\//);
  });
});
