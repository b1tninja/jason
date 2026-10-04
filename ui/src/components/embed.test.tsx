import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, resetServerSession } from "../lib/api";
import { EMBED_HOSTS, Embed, attachmentDocRef, embedUrls, frameRule } from "./Embed";
import { DOC_WORDS, type DocumentView } from "./index";

const ID = "1AbCdEfGhIjKlMnOpQ";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

/** A server whose `/api/session` answers `body`, and whose `/api/file` answers `file` (a refusal, as JSON). */
function session(body: unknown, file?: { status: number; body: unknown }) {
  const f = vi.fn(async (url: string) => {
    if (url === "/api/session") return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    if (url.startsWith("/api/file") && file) return new Response(JSON.stringify(file.body), { status: file.status, headers: { "Content-Type": "application/json" } });
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", f);
  return f;
}

const noOutside = (root: HTMLElement) => {
  expect(root.querySelector('a[href*="/api/file"], img[src*="/api/file"], iframe[src*="/api/file"]')).toBeNull();
  expect(root.querySelector('iframe[src*="docs.google.com/document"], iframe[src*="drive.google.com"]')).toBeNull();
  expect(root.innerHTML).not.toMatch(/[A-Za-z]:\\|"\/(?:Users|home)\//);
};

describe("Embed: a private Google file is a Doc card on drive:<id>, never a frame", () => {
  it("a Doc by its link: jason's copy with Open in Google, no iframe", () => {
    const { container } = render(<Embed a={{ kind: "doc", ref: `https://docs.google.com/document/d/${ID}/edit`, title: "Minutes" }}
      docProps={{ signedIn: true, evidence: null, by: "A Manager" }} />);
    expect(container.querySelector("iframe")).toBeNull();
    expect(screen.getByText("Minutes")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", `https://docs.google.com/document/d/${ID}/edit`);
    expect(screen.getByRole("button", { name: "Preview Minutes" })).toBeInTheDocument();
    noOutside(container);
  });

  it("each private kind, and a chart by its Sheet id, is a drive: reference", () => {
    for (const kind of ["doc", "sheet", "slides", "form", "drive", "chart"] as const) {
      expect(attachmentDocRef({ kind, ref: ID, title: "X" })?.address).toBe(`drive:${ID}`);
    }
    expect(attachmentDocRef({ kind: "doc", ref: "https://docs.google.com/document/d/e/2PACX-example/pub" })).toBeNull();
  });

  it("Preview posts one view; signed out says so", async () => {
    const view: DocumentView = { kind: "pdf", name: "Minutes", readAt: "", url: "/api/evidence/document/t", expires: "", caveats: [] };
    const onView = vi.fn(async () => view);
    const evidence = { found: true, address: `drive:${ID}`, label: "Minutes", kind: "drive" as const, sources: [], changed: null, changedNote: "", link: "",
      refresh: [], caveats: [], note: "", refreshable: null, documents: [{ id: "pdf", name: "Minutes.pdf", kind: "pdf" as const, size: 1, readAt: "", note: "" }] };
    const { unmount } = render(<Embed a={{ kind: "doc", ref: ID, title: "Minutes" }} docProps={{ signedIn: true, evidence, by: "A Manager", onView }} />);
    await userEvent.click(screen.getByRole("button", { name: "Preview Minutes" }));
    expect(onView).toHaveBeenCalledWith({ address: `drive:${ID}`, document: "pdf", by: "A Manager" });
    unmount();
    render(<Embed a={{ kind: "doc", ref: ID, title: "Minutes" }} docProps={{ signedIn: false, evidence }} />);
    expect(screen.getByText("Sign in to see previews")).toBeInTheDocument();
  });
});

describe("Embed: a photo or PDF under data/ is a Doc on file:<path>", () => {
  it("a photo is inline: Show the document, then one logged view", async () => {
    const view: DocumentView = { kind: "image", name: "East bed", readAt: "", url: "/api/evidence/document/p", expires: "", caveats: [] };
    const onView = vi.fn(async () => view);
    const { container } = render(<Embed a={{ kind: "image", ref: "photos/east-bed.jpg", title: "East bed" }}
      docProps={{ signedIn: true, by: "A Manager", onView, evidence: { found: true, address: "file:photos/east-bed.jpg", label: "East bed", kind: "file",
        sources: [], changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "", refreshable: null,
        documents: [{ id: "image", name: "east-bed.jpg", kind: "image", size: 3, readAt: "", note: "" }] } }} />);
    expect(screen.getByRole("region", { name: "East bed" })).toBeInTheDocument();
    expect(onView).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: DOC_WORDS.show }));
    expect(onView).toHaveBeenCalledWith({ address: "file:photos/east-bed.jpg", document: "image", by: "A Manager" });
    noOutside(container);
  });

  it("a PDF is a card; signed out asks for a sign-in; not allowed says the server's reason", async () => {
    const { container, unmount } = render(<Embed a={{ kind: "pdf", ref: "drafts/notice.pdf", title: "Notice" }} docProps={{ signedIn: false, evidence: null }} />);
    expect(screen.getByText("Sign in to see previews")).toBeInTheDocument();
    expect(container.querySelector("iframe")).toBeNull();
    noOutside(container);
    unmount();
    const refuse = vi.fn(async () => { throw new ApiError("The treasurer's office doesn't open executive-session and other restricted material (P3).", 403); });
    render(<Embed a={{ kind: "pdf", ref: "drafts/notice.pdf", title: "Notice" }} docProps={{ signedIn: true, by: "Pat Example", onView: refuse,
      evidence: { found: true, address: "file:drafts/notice.pdf", label: "Notice", kind: "file", sources: [], changed: null, changedNote: "", link: "",
        refresh: [], caveats: [], note: "", refreshable: null, documents: [{ id: "pdf", name: "notice.pdf", kind: "pdf", size: 1, readAt: "", note: "" }] } }} />);
    await userEvent.click(screen.getByRole("button", { name: /^Preview Notice/ }));
    expect(await screen.findByText(/The treasurer's office doesn't open/)).toBeInTheDocument();
  });

  it("an absolute path is refused in words", () => {
    render(<Embed a={{ kind: "pdf", ref: "C:\\elsewhere\\x.pdf", title: "Elsewhere" }} />);
    expect(screen.getByText(/Not a path under the data folder/)).toBeInTheDocument();
  });
});

describe("Embed: audio under data/ stays the player, signed in", () => {
  it("shows a card with Sign in with Google, and asks the server for no file, when no one is signed in", async () => {
    const f = session({ signedIn: null, signIn: { configured: true, start: "/auth/google" } });
    render(<Embed a={{ kind: "audio", ref: "meetings/a.mp3", title: "Board meeting" }} />);
    expect(await screen.findByText("Sign in with Google to see this file.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with Google" })).toHaveAttribute("href", "/auth/google");
    expect(f.mock.calls.every(([url]) => url === "/api/session")).toBe(true);
  });

  it("renders the <audio> player for a signed-in person, not a frame", async () => {
    session({ signedIn: { name: "A Manager" }, signIn: { configured: true } });
    render(<Embed a={{ kind: "audio", ref: "meetings/a.mp3", title: "Board meeting" }} />);
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    expect(document.querySelector("audio")).toHaveAttribute("controls");
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("shows the server's 401 with its sign-in link (signed out meanwhile)", async () => {
    session({ signedIn: { name: "A Manager" }, signIn: { configured: true } },
      { status: 401, body: { error: "Sign in with Google to open this.", signIn: "/auth/google" } });
    render(<Embed a={{ kind: "audio", ref: "zoom/meetings/x/audio.m4a", title: "Board meeting" }} />);
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.error(document.querySelector("audio")!);
    expect(await screen.findByText("Sign in with Google to open this.")).toBeInTheDocument();
  });
});

describe("Embed: frames only on the kind's hosts, sandboxed, on a click", () => {
  it("the calendar waits for a click, then frames with sandbox, no referrer, and a title", async () => {
    const f = session({});
    render(<Embed a={{ kind: "calendar", ref: "c_abc@group.calendar.google.com", title: "Association calendar" }} />);
    expect(document.querySelector("iframe")).toBeNull();
    expect(screen.getByText("calendar.google.com")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Load Association calendar from calendar.google.com" }));
    const frame = screen.getByTitle("Association calendar") as HTMLIFrameElement;
    expect(frame.src).toContain("https://calendar.google.com/calendar/embed?src=c_abc%40group.calendar.google.com");
    expect(frame.getAttribute("sandbox")).toBe(EMBED_HOSTS.calendar!.sandbox);
    expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(f).not.toHaveBeenCalled();
  });

  it("load=mount frames a public frame at once (the screen's subject)", () => {
    render(<Embed a={{ kind: "calendar", ref: "c_abc@group.calendar.google.com", title: "Association calendar" }} load="mount" />);
    expect(screen.getByTitle("Association calendar")).toHaveAttribute("sandbox", EMBED_HOSTS.calendar!.sandbox);
  });

  it("a Zoom share page off zoom.us, a web page, and a remote PDF are link cards", () => {
    const { container } = render(<>
      <Embed a={{ kind: "zoom", ref: "https://zoom.example/rec/share/abc", title: "Fake Zoom" }} load="mount" />
      <Embed a={{ kind: "url", ref: "https://x.example/page", title: "Some page" }} load="mount" />
      <Embed a={{ kind: "pdf", ref: "https://h.example/x.pdf", title: "Remote PDF" }} load="mount" />
    </>);
    expect(container.querySelector("iframe")).toBeNull();
    expect(screen.getByText(/jason frames a zoom only from zoom.us, .zoom.us/)).toBeInTheDocument();
    expect(screen.getByText("x.example")).toBeInTheDocument();
  });

  it("frameRule: the hosts and paths per kind", () => {
    expect(frameRule("zoom", "https://us02web.zoom.us/rec/share/abc")).not.toBeNull();
    expect(frameRule("zoom", "https://evil.example/rec/share/abc")).toBeNull();
    expect(frameRule("zoom", "http://zoom.us/rec/share/abc")).toBeNull();
    expect(frameRule("map", embedUrls({ kind: "map", ref: "123 Main St" }).frame)).not.toBeNull();
    expect(frameRule("chart", "https://docs.google.com/spreadsheets/d/e/2PACX-abc/pubchart?oid=1")).not.toBeNull();
    expect(frameRule("chart", `https://docs.google.com/spreadsheets/d/${ID}/preview`)).toBeNull();
    expect(frameRule("doc", "https://docs.google.com/document/d/e/2PACX-abc/pub")).not.toBeNull();
    expect(frameRule("doc", `https://docs.google.com/document/d/${ID}/preview`)).toBeNull();
    expect(frameRule("url", "https://x.example/")).toBeNull();
  });

  it("a remote photo loads on a click, with no referrer", async () => {
    const f = session({ signedIn: null });
    render(<Embed a={{ kind: "image", ref: "https://h.example/a.png", title: "Remote" }} />);
    expect(screen.queryByRole("img")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Load Remote from h.example" }));
    expect(screen.getByRole("img", { name: "Remote" })).toHaveAttribute("src", "https://h.example/a.png");
    expect(screen.getByRole("img", { name: "Remote" })).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(f).not.toHaveBeenCalled();
  });

  it("a blob or data image is local: shown at once", () => {
    render(<Embed a={{ kind: "image", ref: "data:image/png;base64,AAAA", title: "Pasted" }} />);
    expect(screen.getByRole("img", { name: "Pasted" })).toHaveAttribute("src", "data:image/png;base64,AAAA");
  });

  it("swaps a frame that never loads for a link card", async () => {
    render(<Embed a={{ kind: "zoom", ref: "https://zoom.us/rec/share/abc", title: "Recording" }} load="mount" timeoutMs={10} />);
    expect(document.querySelector("iframe")).not.toBeNull();
    await waitFor(() => expect(screen.getByText("This page does not allow embedding.")).toBeInTheDocument());
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("renders a thread as a link card with an open-in-Gmail link, never an iframe", () => {
    render(<Embed a={{ kind: "thread", ref: "18f0a1b2c3d4e5f6", title: "Re: pool heater" }} />);
    expect(document.querySelector("iframe")).toBeNull();
    expect(screen.getByRole("link", { name: "open in Gmail" })).toHaveAttribute("href", "https://mail.google.com/mail/u/0/#all/18f0a1b2c3d4e5f6");
  });
});

describe("embedUrls (kept for links)", () => {
  it("calendar: id with the agenda default, and with mode, dates, and tz", () => {
    const plain = embedUrls({ kind: "calendar", ref: "c_abc@group.calendar.google.com" });
    expect(plain.frame).toBe("https://calendar.google.com/calendar/embed?src=c_abc%40group.calendar.google.com&mode=AGENDA");
    expect(plain.open).toBe("https://calendar.google.com/calendar/u/0/r?cid=c_abc%40group.calendar.google.com");
    const full = embedUrls({ kind: "calendar", ref: "c_abc@group.calendar.google.com", opts: { mode: "MONTH", dates: "20261001/20261031", tz: "America/Los_Angeles" } });
    expect(full.frame).toBe("https://calendar.google.com/calendar/embed?src=c_abc%40group.calendar.google.com&mode=MONTH&ctz=America%2FLos_Angeles&dates=20261001%2F20261031");
  });
  it("calendar: takes the id out of a full embed URL", () => {
    const u = embedUrls({ kind: "calendar", ref: "https://calendar.google.com/calendar/embed?src=c_abc%40group.calendar.google.com&ctz=UTC" });
    expect(u.frame).toContain("src=c_abc%40group.calendar.google.com");
  });
  it("map: an address and a lat,lng", () => {
    expect(embedUrls({ kind: "map", ref: "123 Main St, Sacramento CA" }).frame).toBe("https://maps.google.com/maps?q=123%20Main%20St%2C%20Sacramento%20CA&output=embed");
    expect(embedUrls({ kind: "map", ref: "38.58,-121.49" }).open).toBe("https://maps.google.com/maps?q=38.58%2C-121.49");
  });
  it("chart: a bare Sheet id with gid and range, and a pubchart URL passed through", () => {
    expect(embedUrls({ kind: "chart", ref: ID, opts: { gid: "42", range: "A1:D20" } }).frame).toBe(`https://docs.google.com/spreadsheets/d/${ID}/preview?gid=42&range=A1%3AD20`);
    const pub = `https://docs.google.com/spreadsheets/d/e/2PACX-abc/pubchart?oid=1&format=interactive`;
    expect(embedUrls({ kind: "chart", ref: pub })).toEqual({ frame: pub, open: pub });
  });
  it("thread: a bare id becomes a Gmail URL; a Gmail URL stays", () => {
    const g = "https://mail.google.com/mail/u/0/#inbox/18f0a1b2c3d4e5f6";
    expect(embedUrls({ kind: "thread", ref: g }).open).toBe(g);
  });
});
