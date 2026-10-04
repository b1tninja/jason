import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DOC_WORDS, Doc, DocList, type DocRef } from "../components";
import { resetServerSession } from "../lib/api";
import { HearingsView } from "./HearingsView";
import { MeetingsView } from "./MeetingsView";
import { MinutesReviewView } from "./MinutesReviewView";

/* The Meetings group's screens on `Doc` (docs/console/doc-component.md, "Adopting it on a screen"): Meetings and minutes'
 * records as rows, Minutes review's transcript inline beside the draft and its filled copy as a chip, and a hearing's
 * notice as cards at P3. Every reference here is made up. */

const transcript: DocRef = { address: "file:zoom/meetings/2099-10-20-abc1234567/transcript.txt", document: "text", name: "Zoom transcript, 2099-10-20",
  kind: "text", level: "P1", source: "File on disk", readAt: "2099-10-21T00:00:00+00:00", size: 4096 };
const filled: DocRef = { address: "file:board/minutes-2099-10-20.md", document: "text", name: "Filled minutes, 2099-10-20", kind: "text", level: "P1", source: "File on disk" };
const draftDoc: DocRef = { address: "file:board/minutes-draft-2099-10-20.md", document: "text", name: "Minutes draft, 2099-10-20", kind: "text", level: "P1", source: "File on disk" };
const noticeDoc: DocRef = { address: "drive:1ExampleHearingDoc01", document: "pdf", name: "Hearing notice, 2099-10-20 (Doc)", kind: "pdf", level: "P3", source: "Drive copy",
  original: { url: "https://docs.google.com/document/d/1ExampleHearingDoc01/edit", label: "Open in Google" } };
const noticeDraft: DocRef = { address: "file:zoom/hearings/2099-10-20-123-main-st-12.md", document: "text", name: "Hearing notice, 2099-10-20 (jason's draft)", kind: "text", level: "P3", source: "File on disk" };
const postedMinutes: DocRef = { address: "library:abc1234", document: "library:abc1234", name: "Minutes 2099-10-20.pdf", kind: "pdf", level: "P0", source: "Library copy", size: 90_000 };
const driveMinutes: DocRef = { address: "drive:1ExampleMinutesDoc1", document: "pdf", name: "Minutes 2099-10-20", kind: "pdf", level: "P2", source: "Drive copy" };
const agenda: DocRef = { address: "file:board/agenda-2099-10-20.md", document: "text", name: "agenda-2099-10-20.md", kind: "text", level: "P1", source: "File on disk" };
const shut = { open: false, mayOpen: true, minutes: [15, 30, 60], default: 30 };

type Route = (url: string, init?: RequestInit) => unknown;
const textView = (name: string) => ({ kind: "text", name, readAt: "", url: "", expires: "", text: "[7:02 PM] A Director: I call the meeting to order.", caveats: [] });

/** The server, made up: who is signed in, the view (`POST /api/evidence/view`, recorded), and the screen's loader. */
function server({ signedIn = true, refuse = "", loader }: { signedIn?: boolean; refuse?: string; loader: Route }) {
  const views: { address: string; document: string; by: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/session") {
      return new Response(JSON.stringify({ signedIn: signedIn ? { name: "Sam Secretary" } : null, signIn: { configured: true, start: "/auth/google" }, private: shut }), { status: 200 });
    }
    if (url === "/api/evidence/view") {
      const body = JSON.parse(String(init?.body));
      views.push(body);
      if (refuse) return new Response(JSON.stringify({ error: refuse }), { status: 403 });
      return new Response(JSON.stringify(textView(body.address)), { status: 200 });
    }
    const got = loader(url, init);
    return new Response(JSON.stringify(got ?? { error: `no route ${url}` }), { status: got ? 200 : 404 });
  }));
  return views;
}

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

/** The screen shows documents only through Doc: no /api/file link or image, no frame of an outside host, no absolute path. */
function noRawLinks(container: HTMLElement) {
  expect(container.querySelector('a[href*="/api/file"], img[src*="/api/file"], audio[src*="/api/file"]')).toBeNull();
  expect(container.querySelector('iframe[src*="google.com"], iframe[src*="zoom.us"]')).toBeNull();
  expect(container.innerHTML).not.toMatch(/[A-Za-z]:\\|"\/(?:Users|home)\//);
}

// --- the variants, from static references -------------------------------------------------------------------------------

describe("the meetings' references, each in its variant", () => {
  it("the transcript inline (P1): viewed on mount, in a region named for it", async () => {
    const onView = vi.fn(async () => ({ kind: "text" as const, name: transcript.name, readAt: "", url: "", expires: "", text: "I call the meeting to order.", caveats: [] }));
    render(<Doc doc={transcript} variant="inline" signedIn by="Sam Secretary" onView={onView} />);
    const region = screen.getByRole("region", { name: transcript.name });
    await waitFor(() => expect(onView).toHaveBeenCalledWith({ address: transcript.address, document: "text", by: "Sam Secretary" }));
    expect(await within(region).findByText("I call the meeting to order.")).toBeInTheDocument();
  });

  it("the filled minutes as a chip", () => {
    render(<Doc doc={filled} signedIn by="Sam Secretary" onView={vi.fn()} />);
    expect(screen.getByRole("button", { name: `Open ${filled.name}` })).toHaveAccessibleDescription("Text");
  });

  it("a hearing's notice as cards, held outside the private view", () => {
    render(<DocList docs={[noticeDoc, noticeDraft]} variant="card" title="" signedIn privateView={shut} by="Sam Secretary" evidence={null} />);
    expect(screen.getAllByRole("button", { name: "Open the private view" })).toHaveLength(2);    // one switch a card
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("a meeting's minutes as rows, the posted copy first", () => {
    render(<DocList docs={[postedMinutes, driveMinutes]} title="Minutes (2)" signedIn by="Sam Secretary" onView={vi.fn()} />);
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText("Library copy")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Drive copy")).toBeInTheDocument();
  });
});

// --- Minutes review --------------------------------------------------------------------------------------------------------

const UNKNOWN = "___ (not in the record)";
const draft = `# DRAFT Minutes of 10/20/99\n\n## Call to order\n\nThe president called the meeting to order at ${UNKNOWN}.\n`;
const review = { found: true, date: "2099-10-20", draft, markdown: draft, open: 1, privacy: [], namesFrom: "a conservative reading", sections: [], reviewedBy: "Sam Secretary",
  savedAt: "2099-10-22T00:00:00+00:00", history: [], minutesFile: "board/minutes-2099-10-20.md", draftDoc, minutesDoc: filled, transcriptDoc: transcript,
  blanks: [{ id: "b1", section: "Call to order", context: `The president called the meeting to order at ${UNKNOWN}.`, marker: UNKNOWN, value: "" }],
  command: "jason board --minutes 2099-10-20", commands: { redraft: "jason board --minutes 2099-10-20" }, caveats: [] };
const listing = { found: true, count: 1, caveats: [], drafts: [{ date: "2099-10-20", file: "board/minutes-draft-2099-10-20.md", blanks: 1, filled: 0, reviewed: true,
  reviewedBy: "Sam Secretary", savedAt: "", minutesFile: "board/minutes-2099-10-20.md", privacyFlags: 0, draftDoc, minutesDoc: filled, transcriptDoc: transcript }] };
const minutesLoader: Route = (url) => (url.startsWith("/api/minutes-review?date=") ? review : url === "/api/minutes-review" ? listing : null);

async function openDraft() {
  render(<MinutesReviewView />);
  expect(await screen.findByRole("button", { name: `Open ${filled.name}` })).toBeInTheDocument();      // the filled copy's chip in the list
  await userEvent.click(screen.getByRole("button", { name: "Review" }));
  return screen.findByRole("region", { name: transcript.name });
}

describe("Minutes review", () => {
  it("shows the Zoom transcript inline beside the draft, viewed once on mount (P1), and the filled copy as a chip", async () => {
    const views = server({ loader: minutesLoader });
    const region = await openDraft();
    expect(await within(region).findByText(/I call the meeting to order/)).toBeInTheDocument();
    expect(views).toEqual([{ address: transcript.address, document: "text", by: "Sam Secretary" }]);
    expect(screen.getByText("As it would read")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: `Open ${filled.name}` }));
    await waitFor(() => expect(views).toHaveLength(2));
    expect(views[1]).toEqual({ address: filled.address, document: "text", by: "Sam Secretary" });
    noRawLinks(document.body);
  });

  it("signed out: the transcript says to sign in, and nothing is viewed", async () => {
    const views = server({ signedIn: false, loader: minutesLoader });
    const region = await openDraft();
    expect(await within(region).findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(within(region).getByRole("link", { name: "Sign in with Google" })).toBeInTheDocument();
    expect(views).toEqual([]);
  });

  it("not allowed: the server's reason, in its words", async () => {
    server({ refuse: "The treasurer's office doesn't open this transcript.", loader: minutesLoader });
    const region = await openDraft();
    expect(await within(region).findByText(/The treasurer's office doesn't open this transcript/)).toBeInTheDocument();
  });

  it("no Zoom meeting that day: says so, with the sync command", async () => {
    server({ loader: (url) => (url.startsWith("/api/minutes-review?date=") ? { ...review, transcriptDoc: null } : url === "/api/minutes-review" ? listing : null) });
    render(<MinutesReviewView />);
    await userEvent.click(await screen.findByRole("button", { name: "Review" }));
    expect(await screen.findByText(/No board meeting on 2099-10-20 in the Zoom index/)).toBeInTheDocument();
    expect(screen.getByText("jason zoom --sync")).toBeInTheDocument();
  });
});

// --- Hearings ---------------------------------------------------------------------------------------------------------------

const hearing = { key: "2099-10-20|123-main-st-12", address: "123 Main St #12", start: "2099-10-20T18:00:00", noticeBy: "2099-10-10", decisionByIfHeld: "2099-11-03",
  standing: "notice by 2099-10-10", scheduled: false, problems: [], decision: null, notice: "hearings/2099-10-20-123-main-st-12.md",
  noticeDoc: { id: "1ExampleHearingDoc01", url: "https://docs.google.com/document/d/1ExampleHearingDoc01/edit" }, noticeRefs: [noticeDoc, noticeDraft],
  stages: [{ key: "noticeBy", label: "Notice delivered by", date: "2099-10-10" }, { key: "hearing", label: "Hearing", date: "2099-10-20" }] };
const hearingsLoader: Route = (url) => (url === "/api/hearings" ? { found: true, hearings: [hearing] } : null);

describe("Hearings", () => {
  it("shows the notice as two P3 cards that ask for the private view; nothing is viewed or framed", async () => {
    const views = server({ loader: hearingsLoader });
    const { container } = render(<HearingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    const card = screen.getByRole("heading", { name: "The hearing notice" }).closest("section")!;
    expect(await within(card).findAllByRole("button", { name: "Open the private view" })).toHaveLength(2);
    expect(within(card).getAllByText(/open the private view to see it/).length).toBeGreaterThanOrEqual(2);
    expect(within(card).getByText(noticeDoc.name)).toBeInTheDocument();
    expect(within(card).getByText(noticeDraft.name)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /Open in Google/ })).toHaveAttribute("rel", "noreferrer");
    expect(within(card).queryByRole("img")).toBeNull();                       // no thumbnail of a held document
    expect(views).toEqual([]);
    noRawLinks(container);
  });

  it("signed out: each card asks for a sign-in", async () => {
    server({ signedIn: false, loader: hearingsLoader });
    render(<HearingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    const card = screen.getByRole("heading", { name: "The hearing notice" }).closest("section")!;
    expect(await within(card).findAllByText("Sign in to see previews")).toHaveLength(2);
  });
});

// --- Meetings and minutes -----------------------------------------------------------------------------------------------------

const meetings = { found: true, caveats: [], scheduleGaps: [], meetings: [{ date: "2099-10-20", titles: ["Board"], has: { agenda: { Drive: 1 }, minutes: { "PayHOA library": 1, Drive: 1 } }, checks: [] }] };
const one = { found: true, date: "2099-10-20", docs: [{ kind: "agenda", docs: [agenda] }, { kind: "minutes", docs: [postedMinutes, driveMinutes] }] };
const meetingsLoader: Route = (url) => (url === "/api/meetings" ? meetings : url === "/api/meetings?date=2099-10-20" ? one : null);

describe("Meetings and minutes", () => {
  it("shows a meeting's records as rows by kind, and a View posts one view", async () => {
    const views = server({ loader: meetingsLoader });
    const { container } = render(<MeetingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Show the records of 2099-10-20" }));
    expect(await screen.findByRole("heading", { name: "Minutes (2)" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Agenda (1)" })).toBeInTheDocument();
    const view = screen.getByRole("button", { name: `View ${postedMinutes.name}` });
    await waitFor(() => expect(view).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(view);
    await waitFor(() => expect(views).toEqual([{ address: postedMinutes.address, document: postedMinutes.document, by: "Sam Secretary" }]));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    noRawLinks(container);
  });

  it("signed out: View is off and says why", async () => {
    server({ signedIn: false, loader: meetingsLoader });
    render(<MeetingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Show the records of 2099-10-20" }));
    expect(await screen.findAllByText("Sign in with Google to view it.")).toHaveLength(2);
    expect(screen.getByRole("button", { name: `View ${postedMinutes.name}` })).toHaveAttribute("aria-disabled", "true");
  });

  it("not allowed: the server's reason in the viewer", async () => {
    server({ refuse: "The treasurer's office doesn't open these minutes.", loader: meetingsLoader });
    render(<MeetingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Show the records of 2099-10-20" }));
    const view = await screen.findByRole("button", { name: `View ${driveMinutes.name}` });
    await waitFor(() => expect(view).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(view);
    expect(await screen.findByText(/The treasurer's office doesn't open these minutes/)).toBeInTheDocument();
  });
});
