import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Embed, embedUrls } from "./Embed";

const ID = "1AbCdEfGhIjKlMnOpQ";

afterEach(() => vi.unstubAllGlobals());

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

describe("Embed: a file under data/ needs a signed-in person", () => {
  it("shows a card with Sign in with Google, and asks the server for no file, when no one is signed in", async () => {
    const f = session({ signedIn: null, signIn: { configured: true, start: "/auth/google" } });
    render(<Embed a={{ kind: "image", ref: "photos/a.jpg", title: "East bed" }} />);
    expect(await screen.findByText("Sign in with Google to see this file.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with Google" })).toHaveAttribute("href", "/auth/google");
    expect(screen.queryByRole("img")).toBeNull();
    expect(f.mock.calls.every(([url]) => url === "/api/session")).toBe(true);
  });

  it("says so when sign-in is not set up on this jason-web", async () => {
    session({ signedIn: null, signIn: { configured: false } });
    render(<Embed a={{ kind: "pdf", ref: "drafts/notice.pdf", title: "Notice" }} />);
    expect(await screen.findByText(/Console sign-in isn't set up on this jason-web/)).toBeInTheDocument();
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("shows the server's reason on a card when it refuses an image (an <img> cannot read the status)", async () => {
    session({ signedIn: { name: "Pat Example" }, signIn: { configured: true } },
      { status: 403, body: { error: "The treasurer's office doesn't open executive-session and other restricted material (P3)." } });
    render(<Embed a={{ kind: "image", ref: "library/files/x.png", title: "Scan" }} />);
    const img = await screen.findByRole("img", { name: "Scan" });
    fireEvent.error(img);
    expect(await screen.findByText("The treasurer's office doesn't open executive-session and other restricted material (P3).")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("shows the server's 401 with its sign-in link (signed out meanwhile)", async () => {
    session({ signedIn: { name: "A Manager" }, signIn: { configured: true } },
      { status: 401, body: { error: "Sign in with Google to open this.", signIn: "/auth/google" } });
    render(<Embed a={{ kind: "audio", ref: "zoom/meetings/x/audio.m4a", title: "Board meeting" }} />);
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.error(document.querySelector("audio")!);
    expect(await screen.findByText("Sign in with Google to open this.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with Google" })).toHaveAttribute("href", "/auth/google");
  });

  it("leaves a URL alone: no sign-in asked for", () => {
    const f = session({ signedIn: null });
    render(<Embed a={{ kind: "image", ref: "https://h.example/a.png", title: "Remote" }} />);
    expect(screen.getByRole("img", { name: "Remote" })).toHaveAttribute("src", "https://h.example/a.png");
    expect(f).not.toHaveBeenCalled();
  });
});

describe("embedUrls (new kinds)", () => {
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
    expect(u.open).toBe("https://calendar.google.com/calendar/u/0/r?cid=c_abc%40group.calendar.google.com");
  });
  it("zoom: the share URL as it is", () => {
    const u = embedUrls({ kind: "zoom", ref: "https://us02web.zoom.us/rec/share/abc" });
    expect(u).toEqual({ frame: "https://us02web.zoom.us/rec/share/abc", open: "https://us02web.zoom.us/rec/share/abc" });
  });
  it("map: an address and a lat,lng", () => {
    expect(embedUrls({ kind: "map", ref: "123 Main St, Sacramento CA" }).frame).toBe("https://maps.google.com/maps?q=123%20Main%20St%2C%20Sacramento%20CA&output=embed");
    expect(embedUrls({ kind: "map", ref: "38.58,-121.49" }).open).toBe("https://maps.google.com/maps?q=38.58%2C-121.49");
  });
  it("chart: a bare Sheet id with gid and range, and a pubchart URL passed through", () => {
    expect(embedUrls({ kind: "chart", ref: ID }).frame).toBe(`https://docs.google.com/spreadsheets/d/${ID}/preview`);
    expect(embedUrls({ kind: "chart", ref: ID, opts: { gid: "42", range: "A1:D20" } }).frame).toBe(`https://docs.google.com/spreadsheets/d/${ID}/preview?gid=42&range=A1%3AD20`);
    const pub = `https://docs.google.com/spreadsheets/d/e/2PACX-abc/pubchart?oid=1&format=interactive`;
    expect(embedUrls({ kind: "chart", ref: pub })).toEqual({ frame: pub, open: pub });
  });
  it("thread: a bare id becomes a Gmail URL; a Gmail URL stays", () => {
    expect(embedUrls({ kind: "thread", ref: "18f0a1b2c3d4e5f6" }).open).toBe("https://mail.google.com/mail/u/0/#all/18f0a1b2c3d4e5f6");
    const g = "https://mail.google.com/mail/u/0/#inbox/18f0a1b2c3d4e5f6";
    expect(embedUrls({ kind: "thread", ref: g }).open).toBe(g);
  });
  it("audio: a path under data/ goes through /api/file; a URL stays", () => {
    expect(embedUrls({ kind: "audio", ref: "meetings/2026-09 board.mp3" }).frame).toBe("/api/file?path=meetings%2F2026-09%20board.mp3");
    expect(embedUrls({ kind: "audio", ref: "https://h/a.mp3" }).frame).toBe("https://h/a.mp3");
  });
});

describe("Embed (new kinds)", () => {
  it("renders audio as an <audio> player, not a frame", async () => {
    session({ signedIn: { name: "A Manager" }, signIn: { configured: true } });
    render(<Embed a={{ kind: "audio", ref: "meetings/a.mp3", title: "Board meeting" }} />);
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    const audio = document.querySelector("audio");
    expect(audio).toHaveAttribute("src", "/api/file?path=meetings%2Fa.mp3");
    expect(audio).toHaveAttribute("controls");
    expect(document.querySelector("iframe")).toBeNull();
  });
  it("renders a thread as a link card with an open-in-Gmail link, never an iframe", () => {
    render(<Embed a={{ kind: "thread", ref: "18f0a1b2c3d4e5f6", title: "Re: pool heater" }} />);
    expect(document.querySelector("iframe")).toBeNull();
    expect(document.querySelector(".embed-link")).not.toBeNull();
    expect(screen.getByRole("link", { name: "open in Gmail" })).toHaveAttribute("href", "https://mail.google.com/mail/u/0/#all/18f0a1b2c3d4e5f6");
    expect(screen.getByText("mail.google.com")).toBeInTheDocument();
  });
  it("swaps a frame that never loads for a link card", async () => {
    render(<Embed a={{ kind: "url", ref: "https://x.example/page", title: "Some page" }} timeoutMs={10} />);
    expect(document.querySelector("iframe")).not.toBeNull();
    await waitFor(() => expect(document.querySelector(".embed-link")).not.toBeNull());
    expect(document.querySelector("iframe")).toBeNull();
    expect(screen.getByText("This page does not allow embedding.")).toBeInTheDocument();
    expect(screen.getByText("x.example")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "open" })[0]).toHaveAttribute("href", "https://x.example/page");
  });
});
