import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DOC_WORDS, rowRegionName, type DocRef } from "../components";
import { resetServerSession } from "../lib/api";
import { MailTriageView } from "./MailTriageView";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

// Made-up letters; the scans are references the loader builds (`jason.tasks.mail.scan_ref`), never a URL or a path.
const summons: DocRef = { address: "file:mail/9001/contents.pdf", document: "pdf", name: "Letter from Superior Court, 2026-10-01", kind: "pdf",
  level: "P2", source: "Scan", readAt: "2026-10-01T15:00:00+00:00", size: 90_000, thumb: true };
const statement: DocRef = { address: "file:mail/9002/contents.pdf", document: "pdf", name: "Letter from A Bank, 2026-09-28", kind: "pdf",
  level: "P2", source: "Scan", size: 40_000, thumb: true };
const envelope: DocRef = { address: "file:mail/9003/cover.jpg", document: "image", name: "Envelope from Ad Co, 2026-09-30", kind: "image",
  level: "P2", source: "Scan", size: 12_000 };

const data = {
  found: true, since: "2026-09-03", items: 3, byKind: { legal: 1, bank: 1, ad: 1 }, choices: ["scan", "forward", "shred", "discard", "keep"], chosen: 1,
  act: [{ mailId: "9001", received: "2026-10-01", sender: "Superior Court", kind: "legal", urgency: "act", evidence: ["summons"], deadlines: [{ date: "2099-10-31", label: "respond by" }], scanned: true, summary: ["A summons in a civil case."], choice: null, scan: summons }],
  review: [{ mailId: "9002", received: "2026-09-28", sender: "A Bank", kind: "bank", urgency: "review", evidence: [], deadlines: [], scanned: true, summary: [], choice: null, scan: statement }],
  unscanned: [{ mailId: "9003", received: "2026-09-30", sender: "Ad Co", kind: "ad", urgency: "file", evidence: [], deadlines: [], scanned: false, summary: [], choice: { mailId: "9003", choice: "discard", by: "Secretary", on: "2026-10-02T10:00:00+00:00", note: "", history: [] }, scan: envelope }],
  caveats: ["jason scans, forwards, shreds, and discards nothing."],
};

const IN = { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true, start: "/auth/google" } };
const OUT = { token: "t", signIn: { configured: true, start: "/auth/google" } };
const pdfView = { kind: "pdf", name: "contents.pdf", readAt: "", url: "/api/evidence/document/tok", expires: "", caveats: ["Unmasked: shown because A Manager asked; this view is logged."] };

/** The inline document of that name in the letter: the one region labelled by its name (the row beside it is
 * "<name> (in the list)"). */
const inlineOf = (letter: HTMLElement, name: string) => {
  const found = within(letter).queryAllByRole("region", { name });
  expect(found.length).toBeLessThanOrEqual(1);
  return found.find((el) => el.classList.contains("doc-inline"));
};

/** The page's data, the session, and the view: `view` answers `POST /api/evidence/view` (a status and body). */
function serve(session: object, view: { status: number; body: object } = { status: 200, body: pdfView }) {
  const posts: [string, unknown][] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push([url, JSON.parse(String(init.body))]);
    if (url === "/api/evidence/view") return new Response(JSON.stringify(view.body), { status: view.status, headers: { "Content-Type": "application/json" } });
    const body = url.startsWith("/api/session") ? session : data;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return posts;
}

describe("MailTriageView", () => {
  it("renders the lanes with each letter's facts and the recorded choice", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return new Response(JSON.stringify(data), { status: 200 }); }));
    render(<MailTriageView />);
    expect(await screen.findByText("Superior Court")).toBeInTheDocument();
    expect(urls[0]).toBe("/api/mail-triage?days=30");
    expect(screen.getByText(/jason scans, forwards, shreds, and discards nothing\. The choice/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Act (1)" })).toBeInTheDocument();
    const first = screen.getByRole("article", { name: "letter 9001" });
    expect(within(first).getByText("legal")).toBeInTheDocument();
    expect(within(first).getByText("act")).toBeInTheDocument();
    expect(within(first).getByText("2099-10-31")).toBeInTheDocument();
    expect(within(first).getByText("summons")).toBeInTheDocument();
    expect(within(first).getByText("Enter your name above to record a choice.")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: "Not scanned (1)" }));
    const letter = screen.getByRole("article", { name: "letter 9003" });
    expect(within(letter).getByText("discard")).toBeInTheDocument();
    expect(within(letter).getByText(/by Secretary on 2026-10-02/)).toBeInTheDocument();
    expect(within(letter).getByText("not scanned")).toBeInTheDocument();
  });

  it("records a choice through a confirm, posting to the mail id", async () => {
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify({ mailId: "9001", choice: "forward", by: "Treasurer", on: "2026-10-03T10:00:00+00:00", note: "", history: [] }), { status: 200 }); }
      return new Response(JSON.stringify(data), { status: 200 });
    }));
    render(<MailTriageView />);
    await screen.findByText("Superior Court");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("your name"), "Treasurer");
    const letter = screen.getByRole("article", { name: "letter 9001" });
    expect(within(screen.getByRole("group", { name: "Choices for letter 9001" })).getAllByRole("button")).toHaveLength(5);
    await user.click(within(letter).getByRole("button", { name: "Forward" }));
    expect(within(letter).getByRole("group", { name: "Confirm" })).toHaveTextContent('Record "forward" for the letter from Superior Court');
    await user.click(within(letter).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/write/mail-triage/9001");
    expect((posts[0] as unknown[])[1]).toEqual({ choice: "forward", by: "Treasurer", note: "" });
    expect(await within(letter).findByText("forward")).toBeInTheDocument();
    expect(within(letter).getByText(/by Treasurer on 2026-10-03/)).toBeInTheDocument();
  });

  it("cancels a choice without posting", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MailTriageView />);
    await screen.findByText("Superior Court");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("your name"), "T");
    const letter = screen.getByRole("article", { name: "letter 9001" });
    await user.click(within(letter).getByRole("button", { name: "Shred" }));
    await user.click(within(letter).getByRole("button", { name: "Cancel" }));
    expect(within(letter).queryByRole("group", { name: "Confirm" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.every((c) => (c as unknown[])[1] === undefined || ((c as unknown[])[1] as RequestInit).method !== "POST")).toBe(true);
  });
});

describe("MailTriageView: each letter's document (Doc)", () => {
  it("shows the scan as a row, and the envelope for a letter not scanned", async () => {
    serve(IN);
    render(<MailTriageView />);
    const letter = await screen.findByRole("article", { name: "letter 9001" });
    expect(within(letter).getByRole("heading", { name: summons.name })).toBeInTheDocument();
    expect(within(letter).getByText("Scan")).toBeInTheDocument();
    expect(within(letter).getByText(/^PDF · \d/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Not scanned (1)" }));
    const unscanned = screen.getByRole("article", { name: "letter 9003" });
    expect(within(unscanned).getByRole("button", { name: `View ${envelope.name}` })).toBeInTheDocument();
    expect(within(unscanned).getByText(/^Image/)).toBeInTheDocument();
  });

  it("View posts one logged view of the scan and opens the viewer", async () => {
    const posts = serve(IN);
    render(<MailTriageView />);
    const view = await screen.findByRole("button", { name: `View ${summons.name}` });
    await waitFor(() => expect(view).not.toHaveAttribute("aria-disabled"));
    expect(posts).toEqual([]);                                             // nothing is viewed on load
    await userEvent.click(view);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(posts).toEqual([["/api/evidence/view", { address: summons.address, document: "pdf", by: "A Manager" }]]);
  });

  it("Read opens the letter inline beside the choices; the P2 scan shows only on Show the document", async () => {
    const posts = serve(IN);
    render(<MailTriageView />);
    const letter = await screen.findByRole("article", { name: "letter 9001" });
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("your name"), "Treasurer");
    await user.click(within(letter).getByRole("button", { name: "Read it beside the choices" }));
    const region = inlineOf(letter, summons.name)!;
    expect(region).toBeTruthy();
    expect(within(letter).getByRole("region", { name: rowRegionName(summons.name) })).toHaveClass("doc-list-row");   // the row: its own name
    expect(within(letter).getByRole("group", { name: "Choices for letter 9001" })).toBeInTheDocument();
    const show = await within(region).findByRole("button", { name: DOC_WORDS.show });
    expect(posts).toEqual([]);                                             // P2: not viewed on mount
    await user.click(show);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: summons.address, document: "pdf", by: "A Manager" }]]));
    expect(await within(region).findByTitle("contents.pdf")).toHaveAttribute("src", "/api/evidence/document/tok");
    await user.click(within(letter).getByRole("button", { name: "Close the letter" }));
    expect(inlineOf(letter, summons.name)).toBeUndefined();
  });

  it("signed out: the row and the inline letter say to sign in, and nothing is viewed", async () => {
    const posts = serve(OUT);
    render(<MailTriageView />);
    const letter = await screen.findByRole("article", { name: "letter 9001" });
    expect(await within(letter).findByText("Sign in with Google to view it.")).toBeInTheDocument();
    await userEvent.click(within(letter).getByRole("button", { name: "Read it beside the choices" }));
    expect(await within(letter).findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(within(letter).queryByRole("button", { name: DOC_WORDS.show })).not.toBeInTheDocument();
    expect(posts).toEqual([]);
  });

  it("not allowed: the server's reason, in words", async () => {
    serve(IN, { status: 403, body: { error: "The treasurer's office doesn't open this letter." } });
    render(<MailTriageView />);
    const letter = await screen.findByRole("article", { name: "letter 9001" });
    await userEvent.click(within(letter).getByRole("button", { name: "Read it beside the choices" }));
    await userEvent.click(await within(letter).findByRole("button", { name: DOC_WORDS.show }));
    expect(await within(letter).findByText(/The treasurer's office doesn't open this letter\./)).toBeInTheDocument();
  });

  it("a letter that holds a credential has no document: Held, in words, and nothing to view", async () => {
    const HELD = "Held: this letter holds a credential; it opens in no screen.";
    const held = { mailId: "9004", received: "2026-10-02", sender: "Example County", kind: "government", urgency: "review", evidence: [], deadlines: [], scanned: true, summary: [], choice: null, scan: null, held: HELD };
    const posts: [string, unknown][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") posts.push([url, JSON.parse(String(init.body))]);
      const body = url.startsWith("/api/session") ? IN : { ...data, review: [...data.review, held] };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    render(<MailTriageView />);
    await screen.findByText("Superior Court");
    await userEvent.click(screen.getByRole("tab", { name: "Review (2)" }));
    const letter = screen.getByRole("article", { name: "letter 9004" });
    expect(within(letter).getByText(HELD)).toBeInTheDocument();
    expect(within(letter).queryByRole("button", { name: /^View / })).not.toBeInTheDocument();
    expect(within(letter).queryByRole("button", { name: "Read it beside the choices" })).not.toBeInTheDocument();
    expect(posts).toEqual([]);
  });

  it("renders no /api/file link, no outside frame, and no absolute path", async () => {
    serve(IN);
    const { container } = render(<MailTriageView />);
    const letter = await screen.findByRole("article", { name: "letter 9001" });
    await userEvent.click(within(letter).getByRole("button", { name: "Read it beside the choices" }));
    await userEvent.click(await within(letter).findByRole("button", { name: DOC_WORDS.show }));
    await within(letter).findByTitle("contents.pdf");
    const html = container.innerHTML;
    expect(html).not.toContain("/api/file");
    expect(html).not.toMatch(/(?<![A-Za-z])[A-Za-z]:[\\/]|\/home\/|\/Users\//);
    for (const frame of Array.from(container.querySelectorAll("iframe"))) expect(frame.getAttribute("src") ?? "").toMatch(/^\/api\/evidence\/document\//);
  });
});
