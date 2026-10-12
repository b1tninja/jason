import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, resetServerSession, retryAfterOf } from "../lib/api";
import { SplitEditor } from "./SplitEditor";
import { SplitReview } from "./SplitReview";
import { RecoverPanel, UNFINISHED_SENTENCE, unfinishedWords } from "./SplitRecover";
import { SplitView, resetDemo } from "./SplitView";
import { busyOf, planChangedOf, type ActBody, type SplitBackend } from "./splitApi";
import { DemoBackend } from "./splitDemo";
import { FactsCache } from "./splitFacts";
import type { Review, ReviewPart, SessionAnswer, UnfinishedApply } from "./splitModel";
import { BUSY_SENTENCE, BusyNotice, CHANGED_SENTENCE, ConfidentialNotice, DUPLICATES_SKIPPED_SENTENCE, HELD_SENTENCE, useCountdown } from "./splitNotices";
import { LoadError, ThumbLoader, fetchPicture } from "./splitThumbs";

// The console's wiring for the backend hardening (docs/pdf-splitter.md 6.7 and 8.1; docs/console/screens/split.md): a confidential file's withheld
// text, a library that could not be read, the plan fingerprint, and an apply that did not finish. The browser run is e2e/tests/split-hardening.spec.ts.

beforeEach(() => { resetServerSession(); resetDemo(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); window.location.hash = ""; document.title = ""; });

const part = (n: number): ReviewPart => ({ segment: `s${n}`, level: 0, start: n * 10 - 9, end: n * 10, ordinal: n, slot: "", title: `Part ${n}`, kind: null, pages: [[n * 10 - 9, n * 10]], count: 10, name: "", action: "held" });
const reviewOf = (files: number, fingerprint: string, extra: Partial<Review> = {}): Review => ({
  id: "demo", status: "draft", version: 1, sourcePages: files * 10, files, parts: Array.from({ length: files }, (_, i) => part(i + 1)), dropped: [], pagesInFiles: files * 10,
  totalsOk: true, problems: [], collisions: [], duplicates: [], held: [], result: "", planFingerprint: fingerprint, duplicateCheck: { checked: true, skipped: "" }, ...extra,
});
const FP1 = "a".repeat(32);
const FP2 = "b".repeat(32);
const busyError = (after = 0) => new ApiError("The library could not be read just now (it may be busy). Nothing was changed. Try again in a moment.", 503, { busy: true, retryAfter: after }, after);

interface Harness { calls: ActBody[]; backend: SplitBackend }
function harness(handler: (body: ActBody, n: number) => unknown | Promise<unknown>): Harness {
  const calls: ActBody[] = [];
  const backend = {
    act: async (_id: string, body: ActBody) => { calls.push(body); return handler(body, calls.length); },
    session: async () => ({}),
  } as unknown as SplitBackend;
  return { calls, backend };
}

function showReview(h: Harness, over: Partial<React.ComponentProps<typeof SplitReview>> = {}) {
  const loader = new ThumbLoader({ urlOf: () => "", fetcher: () => new Promise<string>(() => undefined) });
  const facts = new FactsCache(new DemoBackend(), "demo", 30);
  return render(<SplitReview backend={h.backend} id="demo" by="Test" loader={loader} facts={facts} status="draft" drop={[]} setDrop={() => undefined}
    onBack={() => undefined} onDone={() => undefined} confidential={false} onRename={async () => undefined} {...over} />);
}
const applies = (h: Harness) => h.calls.filter((c) => c.act === "apply");

describe("the words for a busy library and a changed plan", () => {
  it("reads Retry-After from the header, and says a 503 is busy only when the server says so", () => {
    expect(retryAfterOf(new Response("", { headers: { "Retry-After": "7" } }))).toBe(7);
    expect(retryAfterOf(new Response("", {}))).toBeUndefined();
    expect(retryAfterOf(new Response("", { headers: { "Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT" } }))).toBeUndefined();
    expect(busyOf(busyError(5))).toEqual({ retryAfter: 5, message: expect.stringContaining("could not be read") });
    expect(busyOf(new ApiError("down", 503, { error: "down" }))).toBeNull();                       // a 503 that is not the library's
    expect(busyOf(new ApiError("no", 500, { busy: true }))).toBeNull();
    expect(busyOf(new ApiError("x", 503, null, 9))?.retryAfter).toBe(9);                             // the header alone is enough
    expect(planChangedOf(new ApiError("moved", 409, { planChanged: true, review: reviewOf(2, FP2) }))?.review.planFingerprint).toBe(FP2);
    expect(planChangedOf(new ApiError("moved", 409, { conflict: true, current: {} }))).toBeNull();     // a stale save is the store's, not an apply's
  });

  it("carries a picture's Retry-After in the load error, so the editor can say the library is busy", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "The library could not be read just now." }), { status: 503, headers: { "Retry-After": "5", "Content-Type": "application/json" } })));
    await expect(fetchPicture("/api/split/thumb?id=x&page=1&size=96", new AbortController().signal)).rejects.toMatchObject({ status: 503, retryAfter: 5 });
    const seen: number[] = [];
    let recovered = 0;
    const loader = new ThumbLoader({
      urlOf: (p) => `u${p}`, onBusy: (after) => seen.push(after), onRecovered: () => { recovered += 1; },
      fetcher: async (url) => { if (url === "u1" || url === "u2") throw new LoadError(503, "busy", 5); return "blob:ok"; },
    });
    const el = document.createElement("img");
    loader.attach(el, 1, ["tiny"]);
    loader.attach(document.createElement("img"), 2, ["tiny"]);
    await waitFor(() => expect(seen).toEqual([5]));                                                  // said once for two pages
    loader.attach(document.createElement("img"), 3, ["tiny"]);
    await waitFor(() => expect(recovered).toBe(1));
  });
});

describe("BusyNotice: the wait in words, and one polite line when it is over", () => {
  it("disables Try again while it counts down in words, enables it at zero, and says so once", async () => {
    vi.useFakeTimers();
    const onRetry = vi.fn();
    render(<BusyNotice busy={{ retryAfter: 3, message: "" }} onRetry={onRetry} />);
    expect(screen.getByText(BUSY_SENTENCE)).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Try again in 3 seconds" });
    expect(button).toBeDisabled();
    expect(screen.queryByRole("alert")).toBeNull();                                                   // not a generic error
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole("button", { name: "Try again in 2 seconds" })).toBeDisabled();
    act(() => { vi.advanceTimersByTime(2000); });
    const ready = screen.getByRole("button", { name: "Try again" });
    expect(ready).toBeEnabled();
    expect(document.querySelector("[data-ready]")).toHaveTextContent("You can try again now.");
    fireEvent.click(ready);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not put the countdown in a live region, and counts down again when the same failure comes back", () => {
    vi.useFakeTimers();
    const { rerender } = render(<BusyNotice busy={{ retryAfter: 2, message: "" }} again={1} onRetry={() => undefined} />);
    for (const live of document.querySelectorAll("[role=status]")) expect(live.textContent ?? "").not.toMatch(/Try again in/);
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    rerender(<BusyNotice busy={{ retryAfter: 2, message: "" }} again={2} onRetry={() => undefined} />);
    expect(screen.getByRole("button", { name: "Try again in 2 seconds" })).toBeDisabled();
  });

  it("shows the server's own sentence below, verbatim, when it says more", () => {
    render(<BusyNotice busy={{ retryAfter: 0, message: "Nothing was written. Try again in a moment." }} onRetry={() => undefined} />);
    expect(document.querySelector("[data-detail]")).toHaveTextContent("Nothing was written. Try again in a moment.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();                          // Retry-After 0: no wait
  });

  it("useCountdown stops at zero", () => {
    vi.useFakeTimers();
    function Probe() { return <p data-testid="n">{useCountdown(2, 0)}</p>; }
    render(<Probe />);
    act(() => { vi.advanceTimersByTime(10_000); });
    expect(screen.getByTestId("n")).toHaveTextContent("0");
  });
});

describe("a confidential file's notice", () => {
  const session = (private_: unknown) => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn: { name: "Ada Admin" }, private: private_ }), { status: 200 })));

  it("says in words that page text, titles and reasons are hidden, with a glyph, and offers the private view to a person whose office opens it", async () => {
    session({ open: false, mayOpen: true, minutes: [15, 30, 60], default: 30 });
    const user = userEvent.setup();
    render(<ConfidentialNotice by="Ada Admin" />);
    const note = screen.getByRole("note", { name: "This file is confidential" });
    expect(note).toHaveTextContent(HELD_SENTENCE);
    expect(note.querySelector("svg")).not.toBeNull();                                                   // a glyph beside the words, not colour alone
    await user.click(await screen.findByRole("button", { name: "Open the private view…" }));
    expect(screen.getByRole("group", { name: "Open the private view" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Why" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Open the private view…" })).toHaveFocus();               // focus returns to where it was
  });

  it("gives the server's reason to a person whose office does not open it, and offers nothing to press", async () => {
    session({ open: false, mayOpen: false, why: "Only the board's officers open it." });
    render(<ConfidentialNotice />);
    expect(await screen.findByText(/Only the board's officers open it\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Open the private view/ })).toBeNull();
  });

  it("when the library could not be asked, says so in the server's words and checks again on request", async () => {
    session({ open: false, mayOpen: true });
    const again = vi.fn();
    render(<ConfidentialNotice known={false} why="The library could not be read just now (it may be busy), so this file is treated as confidential until it can be." onCheckAgain={again} />);
    expect(screen.getByText(/treated as confidential until it can be/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(again).toHaveBeenCalled();
  });
});

describe("the review keeps the plan it showed, and every apply names it", () => {
  const happy = (body: ActBody) => {
    if (body.act === "review") return { act: "review", review: reviewOf(2, FP1) };
    if (body.dryRun) return { dryRun: true, would: { act: "apply", id: "demo", by: "Test", files: 2 }, review: reviewOf(2, FP1), planFingerprint: FP1, note: "A dry run: nothing was written." };
    return { ok: true, held: [], filled: [] };
  };

  it("sends planFingerprint as expect with the dry run and with the confirmed apply", async () => {
    const h = harness(happy);
    showReview(h);
    await screen.findByText(/Pages add up/);
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));
    fireEvent.click(await screen.findByRole("button", { name: "Write 2 files as Test" }));
    await screen.findByText("The split was written");
    expect(applies(h).map((c) => [c.dryRun, c.confirm, c.expect])).toEqual([[true, false, FP1], [false, true, FP1]]);
  });

  it("when the draft moved: replaces the review with the returned one, says what changed in words, and needs a fresh preview and confirm", async () => {
    let n = 0;
    const h = harness((body) => {
      if (body.act === "review") return { act: "review", review: reviewOf(2, FP1) };
      if (body.dryRun) return { dryRun: true, would: { act: "apply", id: "demo", by: "Test", files: 2 }, review: reviewOf(2, n === 0 ? FP1 : FP2), planFingerprint: n === 0 ? FP1 : FP2, note: "A dry run." };
      n += 1;
      throw new ApiError("The draft or the way it would be filed changed after you reviewed it. Nothing was written. Review again.", 409, { conflict: true, planChanged: true, review: reviewOf(3, FP2) });
    });
    showReview(h);
    await screen.findByText(/Pages add up/);
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));
    fireEvent.click(await screen.findByRole("button", { name: /^Write 2 files/ }));
    const note = await screen.findByRole("group", { name: new RegExp(CHANGED_SENTENCE.slice(0, 30)) });
    expect(note).toHaveTextContent(CHANGED_SENTENCE);
    expect(note.querySelector("[data-detail]")).toHaveTextContent("Nothing was written. Review again.");   // the server's sentence, verbatim
    expect(screen.getByRole("heading", { name: /^Review: 3 documents from 30 pages/ })).toBeInTheDocument();  // the returned review replaced the shown one
    expect(screen.queryByRole("button", { name: /^Write / })).toBeNull();                                       // a fresh confirm is required
    await waitFor(() => expect(screen.getByRole("heading", { name: CHANGED_SENTENCE })).toHaveFocus());
    expect(screen.queryByRole("alert")).toBeNull();                                                              // one announcement, not an error as well
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));
    await screen.findByRole("button", { name: /^Write 3 files/ });
    expect(applies(h).at(-1)).toMatchObject({ dryRun: true, expect: FP2 });                                      // the new fingerprint is the one carried
  });

  it("treats a preview that comes back with another fingerprint as a change too, and writes nothing", async () => {
    const h = harness((body) => body.act === "review" ? { act: "review", review: reviewOf(2, FP1) }
      : { dryRun: true, would: { act: "apply", id: "demo", by: "Test", files: 3 }, review: reviewOf(3, FP2), planFingerprint: FP2 });
    showReview(h);
    await screen.findByText(/Pages add up/);
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));
    await screen.findByRole("group", { name: new RegExp(CHANGED_SENTENCE.slice(0, 30)) });
    expect(applies(h).filter((c) => c.confirm).length).toBe(0);
  });

  it("shows the server's refusal words verbatim, as the alert, and not as a changed plan", async () => {
    const words = "signed in as Test: a step goes on the record under the signed-in name, not Someone";
    const h = harness((body) => {
      if (body.act === "review") return { act: "review", review: reviewOf(2, FP1) };
      if (body.dryRun) return happy(body);
      throw new ApiError(words, 403, { error: words });
    });
    showReview(h);
    await screen.findByText(/Pages add up/);
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));
    fireEvent.click(await screen.findByRole("button", { name: /^Write 2 files/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(words);
    expect(screen.queryByRole("group", { name: /changed/ })).toBeNull();
  });
});

describe("a library that could not be read, in the review", () => {
  it("shows the calm notice with Try again for a review the library could not answer, not a generic error", async () => {
    let n = 0;
    const h = harness((body) => {
      if (body.act === "review") { n += 1; if (n === 1) throw busyError(0); return { act: "review", review: reviewOf(2, FP1) }; }
      return {};
    });
    showReview(h);
    expect(await screen.findByText(BUSY_SENTENCE)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText(/Pages add up/);
    expect(screen.queryByText(BUSY_SENTENCE)).toBeNull();
  });

  it("shows the same notice for a confirmed apply the library refused, and Try again sends the same apply with the same fingerprint", async () => {
    let tries = 0;
    const h = harness((body) => {
      if (body.act === "review") return { act: "review", review: reviewOf(2, FP1) };
      if (body.dryRun) return { dryRun: true, would: { act: "apply", id: "demo", by: "Test", files: 2 }, review: reviewOf(2, FP1), planFingerprint: FP1 };
      tries += 1;
      if (tries === 1) throw busyError(0);
      return { ok: true, held: [], filled: [] };
    });
    showReview(h);
    await screen.findByText(/Pages add up/);
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));
    fireEvent.click(await screen.findByRole("button", { name: /^Write 2 files/ }));
    await screen.findByText(BUSY_SENTENCE);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("The split was written");
    expect(applies(h).filter((c) => c.confirm).map((c) => c.expect)).toEqual([FP1, FP1]);
  });

  it("says the duplicate check was skipped, blocks the write, and explains why in words the button points to", async () => {
    const skipped = "The library could not be read just now (it may be busy), so these parts were not checked against the files it already holds. Try again in a moment before applying.";
    let n = 0;
    const h = harness((body) => {
      if (body.act === "review") { n += 1; return { act: "review", review: reviewOf(2, FP1, { duplicateCheck: n === 1 ? { checked: false, skipped } : { checked: true, skipped: "" } }) }; }
      return { dryRun: true, would: { act: "apply", id: "demo", by: "Test", files: 2 }, review: reviewOf(2, FP1, { duplicateCheck: { checked: false, skipped } }), planFingerprint: FP1 };
    });
    showReview(h);
    const note = await screen.findByRole("group", { name: "The duplicate check was skipped" });
    expect(note).toHaveTextContent(DUPLICATES_SKIPPED_SENTENCE);
    expect(note.querySelector("[data-detail]")).toHaveTextContent(skipped);                            // the server's sentence, verbatim
    fireEvent.click(screen.getByRole("button", { name: "Preview the split" }));                         // a preview may still be read
    const write = await screen.findByRole("button", { name: /^Write 2 files/ });
    expect(write).toBeDisabled();
    const why = document.getElementById(write.getAttribute("aria-describedby") ?? "none");
    expect(why).toHaveTextContent(/Writing is blocked: the duplicate check has not run/);
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));                               // reads the review again
    await waitFor(() => expect(screen.queryByRole("group", { name: "The duplicate check was skipped" })).toBeNull());
  });

  it("does not call a check that was not asked for (keep a copy) skipped", async () => {
    const h = harness(() => ({ act: "review", review: reviewOf(2, FP1, { duplicateCheck: { checked: false, skipped: "not asked for" } }) }));
    showReview(h);
    await screen.findByText(/Pages add up/);
    expect(screen.queryByRole("group", { name: "The duplicate check was skipped" })).toBeNull();
  });
});

describe("a confidential file in the review", () => {
  it("shows the compact notice, no title or kind, and keeps the numbers and the states", async () => {
    const h = harness(() => ({ act: "review", review: reviewOf(2, FP1) }));
    showReview(h, { confidential: true, withheld: { why: "", known: true } });
    await screen.findByText(/Pages add up/);
    expect(screen.getByRole("note", { name: "This file is confidential" })).toHaveTextContent(HELD_SENTENCE);
    expect(screen.queryByRole("button", { name: /Open the private view/ })).toBeNull();                 // the compact form points to the header's switch only
    expect(screen.getAllByText("hidden").length).toBeGreaterThan(0);
    expect(screen.queryByDisplayValue("Part 1")).toBeNull();
    expect(screen.getByRole("heading", { name: /Review: 2 documents from 20 pages/ })).toBeInTheDocument();
  });
});

describe("an apply that did not finish", () => {
  const U: UnfinishedApply = { apply: "a-1", by: "Ada Admin", at: "2099-10-04T10:42:00+00:00", written: 2, of: 5, visible: true, failed: 0, choices: ["finish", "rollback"] };

  it("tells the state in words, with no file name", () => {
    expect(unfinishedWords(U)).toBe("It was started by Ada Admin at 2099-10-04 10:42: 2 of 5 files were written.");
    expect(unfinishedWords({ ...U, written: 1, failed: 1 })).toContain("1 of 5 files was written; 1 part could not be written");
  });

  it("says nothing is written until the person confirms, and finishes only after Finish it and Yes", async () => {
    const onSettled = vi.fn();
    const h = harness(() => ({ ok: true, act: "recover", dryRun: false }));
    render(<RecoverPanel backend={h.backend} id="demo" u={U} by="Ada Admin" onSettled={onSettled} />);
    const region = screen.getByRole("region", { name: UNFINISHED_SENTENCE });
    expect(region).toHaveTextContent("2 of 5 files were written");
    expect(region).toHaveTextContent(/Nothing more is written, and nothing is undone, until you choose and confirm/);
    expect(h.calls).toHaveLength(0);
    fireEvent.click(within(region).getByRole("button", { name: "Finish it" }));
    expect(h.calls).toHaveLength(0);                                                                    // the stamp explains first
    expect(within(region).getByRole("group", { name: "Finish it" })).toHaveTextContent(/writes the 3 files that are left/);
    fireEvent.click(within(region).getByRole("button", { name: "Yes, do it" }));
    await screen.findByRole("heading", { name: "The earlier apply was finished" });
    expect(h.calls).toEqual([{ act: "recover", mode: "finish", dryRun: false, confirm: true, by: "Ada Admin" }]);
    expect(onSettled).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByRole("heading", { name: "The earlier apply was finished" })).toHaveFocus());
  });

  it("rolls back only after Roll it back and Yes, and shows the server's note verbatim", async () => {
    const note = "The apply was rolled back: its pins are unpinned and the draft is as it was. The files it wrote stay where they are, held; nothing was deleted.";
    const h = harness(() => ({ ok: true, act: "recover", dryRun: false, rolledBack: true, note }));
    render(<RecoverPanel backend={h.backend} id="demo" u={U} by="Ada Admin" onSettled={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Roll it back" }));
    expect(screen.getByRole("group", { name: "Roll it back" })).toHaveTextContent(/nothing is deleted/);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(h.calls).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Roll it back" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    await screen.findByRole("heading", { name: "The earlier apply was rolled back" });
    expect(h.calls[0]).toMatchObject({ act: "recover", mode: "rollback", dryRun: false, confirm: true });
    expect(screen.getByRole("status")).toHaveTextContent(note);
  });

  it("shows a refusal verbatim and a busy library as the calm notice, and writes nothing more", async () => {
    let n = 0;
    const h = harness(() => { n += 1; if (n === 1) throw busyError(0); throw new ApiError("this split has no unfinished apply", 400, { error: "this split has no unfinished apply" }); });
    render(<RecoverPanel backend={h.backend} id="demo" u={U} by="Ada Admin" onSettled={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Finish it" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    await screen.findByText(BUSY_SENTENCE);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("this split has no unfinished apply");
    expect(screen.getByRole("heading", { name: UNFINISHED_SENTENCE })).toBeInTheDocument();
  });

  it("renders nothing for a draft with no unfinished apply", () => {
    const { container } = render(<RecoverPanel backend={harness(() => ({})).backend} id="demo" u={null} by="x" onSettled={() => undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("the draft list and the editor", () => {
  const U: UnfinishedApply = { apply: "a-1", by: "Ada Admin", at: "2099-10-04T10:42:00+00:00", written: 2, of: 5, visible: true, failed: 0, choices: ["finish", "rollback"] };

  it("marks a draft whose apply did not finish, in words, with how far it got", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => String(url).startsWith("/api/session")
      ? new Response(JSON.stringify({ token: "t", header: "X-Jason-Token", signedIn: { name: "Ada Admin" } }), { status: 200 })
      : String(url).startsWith("/api/limits") ? new Response(JSON.stringify({ limits: [] }), { status: 200 })
      : String(url).startsWith("/api/drive-held") ? new Response(JSON.stringify({ found: true, total: 0, copies: [] }), { status: 200 })
      : new Response(JSON.stringify({ sessions: [
        { id: "a1b2c3d4", status: "confirmed", pages: 40, segments: 5, suggestionsOpen: 0, updated: "2099-10-04T10:42:00", by: "Ada Admin", confidential: false, kind: "upload", label: "40 pages, 5f3a9c01", unfinishedApply: U },
        { id: "e5f6a7b8", status: "draft", pages: 12, segments: 1, suggestionsOpen: 0, updated: "2099-10-01T08:00:00", by: "Ada Admin", confidential: false, kind: "upload", label: "12 pages, 77aa11bb" }],
      limits: { maxPages: 3000, suggestEnabled: true, draftDays: 60, maxParts: 500 } }), { status: 200 })));
    window.location.hash = "#/setup/split";
    render(<SplitView />);
    const table = await screen.findByRole("table", { name: "Split drafts, newest first" });
    const row = within(table).getByRole("link", { name: /^Open the draft 40 pages, 5f3a9c01\. An earlier apply did not finish/ }).closest("tr")!;
    expect(row).toHaveTextContent(UNFINISHED_SENTENCE);
    expect(row).toHaveTextContent("2 of 5 files written");
    expect(within(table).getAllByText(UNFINISHED_SENTENCE)).toHaveLength(1);                            // only the draft that has one
  });

  class Wrapped extends DemoBackend {
    constructor(private extra: Partial<SessionAnswer>) { super({ pages: 20 }); }
    async session(id: string, q: { facts?: [number, number]; review?: boolean; flags?: boolean } = {}): Promise<SessionAnswer> {
      const a = await super.session(id, q);
      return { ...a, ...this.extra, source: { ...a.source, ...(this.extra.source ?? {}) } };
    }
  }

  it("shows the confidential notice and no file name or size in the title for a draft whose text is withheld", async () => {
    const backend = new Wrapped({ confidential: true, source: { sha256: "", size: 123456, pages: 20, kind: "library", ref: "", confidential: true },
      masked: { text: "withheld", why: HELD_SENTENCE, known: true } });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ token: "t", signedIn: { name: "Ada Admin" }, private: { open: false, mayOpen: true } }), { status: 200 })));
    render(<SplitEditor backend={backend} id="demo" />);
    expect(await screen.findByRole("note", { name: "This file is confidential" })).toHaveTextContent(HELD_SENTENCE);
    expect(screen.getByText("A confidential file")).toBeInTheDocument();
    expect(document.title).toBe("Split document: Draft - jason");                                       // no page count, no name
    expect(screen.getByRole("button", { name: "Open the private view…" })).toBeInTheDocument();
  });

  it("says the file is treated as confidential when the library could not be asked, and Check again reads the draft again", async () => {
    const backend = new Wrapped({ confidential: true, source: { sha256: "", size: 1, pages: 20, kind: "library", ref: "", confidential: true },
      masked: { text: "withheld", why: "The library could not be read just now (it may be busy), so this file is treated as confidential until it can be.", known: false }, retry: true,
      confidentialWhy: "The library could not be read just now (it may be busy), so this file is treated as confidential until it can be." });
    const spy = vi.spyOn(backend, "session");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ token: "t", signedIn: { name: "Ada Admin" } }), { status: 200 })));
    render(<SplitEditor backend={backend} id="demo" />);
    await screen.findByText(/treated as confidential until it can be/);
    const before = spy.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(before));
  });

  it("shows the unfinished apply in the draft's header and keeps it there through an edit's answer", async () => {
    const backend = new Wrapped({ unfinishedApply: U });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ token: "t", signedIn: { name: "Ada Admin" } }), { status: 200 })));
    render(<SplitEditor backend={backend} id="demo" />);
    const region = await screen.findByRole("region", { name: UNFINISHED_SENTENCE });
    expect(within(region).getByRole("button", { name: "Finish it" })).toBeInTheDocument();
    expect(within(region).getByRole("button", { name: "Roll it back" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Suggest splits|Undo/ }));                        // any answer that carries no unfinishedApply
    expect(screen.getByRole("region", { name: UNFINISHED_SENTENCE })).toBeInTheDocument();
  });

  it("shows the busy notice, not a generic error, when the library could not be read opening the draft, and Try again opens it", async () => {
    let n = 0;
    class Busy extends DemoBackend {
      async session(id: string, q: { facts?: [number, number]; review?: boolean; flags?: boolean } = {}): Promise<SessionAnswer> {
        n += 1;
        if (n === 1) throw busyError(0);
        return super.session(id, q);
      }
    }
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ token: "t", signedIn: { name: "Ada Admin" } }), { status: 200 })));
    render(<SplitEditor backend={new Busy({ pages: 20 })} id="demo" />);
    expect(await screen.findByText(BUSY_SENTENCE)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("grid", { name: "Pages" });
  });
});
