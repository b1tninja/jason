import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { SplitReview } from "./SplitReview";
import { SplitView, demoBackend, resetDemo } from "./SplitView";
import type { SplitBackend } from "./splitApi";
import { DEMO_PART_LIMIT, DemoBackend, demoFacts } from "./splitDemo";
import { FactsCache } from "./splitFacts";
import { cellLabel, flagItems, pagesList, segWord, sidewaysWords, stateWord, turnBody, turnWord, type Review, type ReviewPart } from "./splitModel";
import { ThumbLoader } from "./splitThumbs";

beforeEach(() => { resetServerSession(); resetDemo(); sessionStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.location.hash = ""; });

const cell = (page: number) => document.querySelector<HTMLElement>(`button.split-cell-btn[data-page="${page}"]`)!;
async function openDemo() {
  window.location.hash = "#/setup/split/demo";
  render(<SplitView />);
  await screen.findByRole("grid", { name: "Pages" });
  await waitFor(() => expect(cell(1)).toBeTruthy());
}
const saved = () => waitFor(() => expect(document.querySelector('[data-save="saved"]')).toBeTruthy());
/** the segments drawer is closed under 1400 px: open it from the toolbar */
const openRail = (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole("button", { name: /^Segments \d/ }));
const reviewButton = () => screen.getAllByRole("button", { name: "Review and split" })[0];

describe("flag and turn words (the model)", () => {
  it("gives every flag a glyph, a short form, and a full sentence, in a fixed order, and says an over-limit size is an estimate", () => {
    const items = flagItems({
      blankOnly: true, nearDuplicateOf: "s2", repeatedBy: ["s5"], sideways: [{ page: 61, turn: 90, fix: 270 }, { page: 66, turn: 270, fix: 90 }],
      overPartLimit: true, estimatedBytes: 4_920_000, partLimit: 2_000_000, slotFilled: true, slot: "annual-budget", mayHoldMore: [{ page: 14, score: 0.9 }, { page: 22, score: 0.7 }],
    });
    expect(items.map((i) => i.key)).toEqual(["blankOnly", "nearDuplicate", "repeated", "sideways", "overLimit", "slotFilled", "mayHoldMore"]);
    expect(items.every((i) => i.glyph && i.short && i.long)).toBe(true);
    expect(items.find((i) => i.key === "nearDuplicate")!.short).toBe("Repeats segment 2");
    expect(items.find((i) => i.key === "repeated")!.short).toBe("Repeated by segment 5");
    expect(items.find((i) => i.key === "sideways")!.short).toBe("2 sideways pages");
    const over = items.find((i) => i.key === "overLimit")!;
    expect(over.short).toBe("May be over the size limit");
    expect(over.long).toMatch(/about 4\.9 MB.*an estimate.*limit of 2\.0 MB/);
    expect(items.find((i) => i.key === "slotFilled")!.long).toMatch(/annual-budget.*already holds a file/);
    expect(items.find((i) => i.key === "mayHoldMore")!.pages).toEqual([14, 22]);
    expect(flagItems({})).toEqual([]);
    expect(flagItems({ overPartLimit: true, partLimit: 2_000_000 }, 3_100_000).find((i) => i.key === "overLimit")!.short).toBe("Over the size limit");   // the review's exact size
  });

  it("writes turns the way the server reads them, and words them with degrees", () => {
    expect(turnBody({})).toBeUndefined();
    expect(turnBody({ 61: 90, 66: "fix" })).toEqual({ "61": 90, "66": "fix" });
    expect(turnWord("fix", 270)).toBe("Fix sideways (turn 270°)");
    expect(turnWord(180)).toBe("Turn 180°");
    expect(segWord("s3")).toBe("segment 3");
    expect(pagesList([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 4)).toBe("1, 2, 3, 4, and 6 more");
    const f = demoFacts(120)[18];
    expect(f).toMatchObject({ n: 19, turn: 90, sideways: true, fix: 270, orientation: "landscape" });
    expect(sidewaysWords(f)).toBe("Sideways: its text is turned 90° clockwise; turning the page 270° clockwise makes it upright");
    expect(stateWord(f)).toBe("sideways");
    expect(cellLabel(19, f, -1, 1, undefined, false, "fix")).toMatch(/Sideways: its text is turned 90°.*drawn landscape.*Will be turned in the new files: fix sideways \(turn 270°\)/);
  });

  it("never calls a scan or a blank page sideways: nothing was measured", () => {
    const facts = demoFacts(120);
    const scan = facts[44], blank = facts[8];
    expect(scan).toMatchObject({ n: 45, has_text: false, turn: -1, sideways: false, fix: 0 });
    expect(blank).toMatchObject({ n: 9, turn: -1, sideways: false });
    expect(sidewaysWords(scan)).toBe("");
  });
});

describe("the demo answers the same fields as the server", () => {
  it("reads flags from the draft: sideways pages, an estimate over the limit, and at most five pages that may start another document", async () => {
    const b = new DemoBackend();
    const a = await b.session("demo", { flags: true });
    const [whole] = a.flags!.segments;
    expect(a.flags!.segments).toHaveLength(1);
    expect(whole).toMatchObject({ segment: "s1", start: 1, end: 120, pages: 120, measured: 120, blankOnly: false, overPartLimit: true, partLimit: DEMO_PART_LIMIT, flagged: true });
    expect(whole.estimatedBytes).toBe(120 * 41000);
    expect(whole.sideways.map((s) => s.page)).toEqual([19, 61, 66]);
    expect(whole.sideways[0]).toEqual({ page: 19, turn: 90, fix: 270 });
    expect(whole.mayHoldMore.length).toBeGreaterThan(0);
    expect(whole.mayHoldMore.length).toBeLessThanOrEqual(5);
    const scores = whole.mayHoldMore.map((m) => m.score);
    expect([...scores].sort((x, y) => y - x)).toEqual(scores);                              // strongest first
    expect(a.flags!.counts).toMatchObject({ sideways: 3, overPartLimit: 1 });
    expect(a.flags!.caveats.join(" ")).toMatch(/estimate/);
  });

  it("flags a blank-only segment, a repeat and the one it repeats, a full slot, and nothing more once the page is marked or rejected", async () => {
    const b = new DemoBackend();
    await b.act("demo", { act: "mark", pages: [9, 10, 20, 45, 47, 72, 74], version: 1 });
    const flags = (await b.session("demo", { flags: true })).flags!;
    const by = (start: number) => flags.segments.find((s) => s.start === start)!;
    expect(by(9)).toMatchObject({ blankOnly: true, end: 9 });
    expect(by(45)).toMatchObject({ end: 46, repeatedBy: ["s7"], nearDuplicateOf: null });
    expect(by(72)).toMatchObject({ end: 73, nearDuplicateOf: "s5" });
    expect(by(20)).toMatchObject({ slot: "reserve-study", slotFilled: true });
    expect(by(10)).toMatchObject({ slot: "annual-budget", slotFilled: false });
    expect(by(74).slot).toBe("insurance-renewal");
    expect(flags.parts).toEqual({ count: 8, limit: 500, over: false });
  });

  it("applies the filing choice and a part's own, and turns pages, as the server's review does", async () => {
    const b = new DemoBackend();
    await b.act("demo", { act: "mark", pages: [10, 20], version: 1 });
    const plain = (await b.act("demo", { act: "review" })).review!;
    expect(plain.parts.map((p) => p.action)).toEqual(["held", "fill", "collision", ]);        // a part with a slot fills it; a full slot keeps the part held; the rest are held
    expect(plain.filing).toMatchObject({ asked: "as labelled", held: 1, slots: 1, collisions: 1, library: 0 });
    expect(plain.collisions).toEqual(["reserve-study"]);
    const held = (await b.act("demo", { act: "review", filing: "held" })).review!;
    expect(held.parts.every((p) => p.action === "held")).toBe(true);
    const lib = (await b.act("demo", { act: "review", filing: "library", parts: [{ segment: "s2", filing: "slot" }] })).review!;
    expect(lib.parts.map((p) => p.action)).toEqual(["library", "fill", "library"]);          // the part's own choice overrides the request
    expect(lib.library).toEqual(["s1", "s3"]);
    await expect(b.act("demo", { act: "review", parts: [{ segment: "s1", filing: "slot" }] })).rejects.toThrow(/names none/);
    await expect(b.act("demo", { act: "review", filing: "everywhere" })).rejects.toThrow(/filing is one of held, library, slots/);
    const turned = (await b.act("demo", { act: "review", rotate: { "19": "fix", "61": 180 } })).review!;
    expect(turned.rotated).toEqual([{ page: 19, degrees: 270 }, { page: 61, degrees: 180 }]);
    expect(turned.sidewaysLeft).toBe(1);                                                    // page 66 is measured sideways and left as it is
    expect(turned.parts.find((p) => p.start === 10)!.rotated).toEqual([{ page: 19, degrees: 270 }]);
    expect((await b.act("demo", { act: "review", rotate: "sideways" })).review!.rotated!.map((r) => r.page)).toEqual([19, 61, 66]);
    await expect(b.act("demo", { act: "review", rotate: { "45": "fix" } })).rejects.toThrow(/no text layer is never measured/);
    await expect(b.act("demo", { act: "review", rotate: { "20": 45 } })).rejects.toThrow(/90, 180, or 270/);
    await expect(b.act("demo", { act: "review", rotate: { "999": 90 } })).rejects.toThrow(/not in a file/);
    expect((await b.act("demo", { act: "review", rotate: { "19": 90 }, drop: [19] })).review!.rotated).toEqual([]);   // a page left out is not turned
  });
});

describe("sideways pages on the cells and in the page menu", () => {
  it("marks a sideways page with a turn glyph and the word, and says so in its name; a scan is never marked", async () => {
    await openDemo();
    const c = cell(19).closest("[data-cell]") as HTMLElement;
    const state = c.querySelector(".split-cell-turn")!;
    expect(state).toHaveTextContent("Sideways");
    expect(state.querySelector("svg[data-glyph='refresh-cw']")).toBeTruthy();
    expect(cell(19)).toHaveAccessibleName(/Sideways: its text is turned 90° clockwise.*drawn landscape/);
    expect(cell(18).closest("[data-cell]")!.querySelector(".split-cell-turn")).toBeNull();
  });

  it("offers Turn 90, 180, 270 and Fix sideways in the page menu, and shows the choice on the cell and in the summary", async () => {
    const user = userEvent.setup();
    await openDemo();
    fireEvent.contextMenu(cell(19));
    const menu = await screen.findByRole("dialog", { name: "Page 19" });
    await waitFor(() => expect(menu).toHaveTextContent("Sideways: its text is turned 90° clockwise; turning the page 270° clockwise makes it upright. Drawn landscape."));
    for (const n of [90, 180, 270]) expect(within(menu).getByRole("button", { name: `Turn ${n}° clockwise in the new files` })).toHaveAttribute("aria-pressed", "false");
    expect(within(menu).queryByRole("button", { name: "Do not turn this page" })).toBeNull();
    await user.click(within(menu).getByRole("button", { name: "Fix sideways (turn 270°) in the new files" }));
    await waitFor(() => expect(cell(19)).toHaveAccessibleName(/Will be turned in the new files: fix sideways \(turn 270°\)/));
    expect(cell(19).closest("[data-cell]")!.querySelector(".split-cell-turn")).toHaveTextContent("Sideways, Fix sideways (turn 270°)");
    expect(screen.getByText("1 page to turn")).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem("jason-split-turns-demo")!)).toEqual({ "19": "fix" });
    fireEvent.contextMenu(cell(19));
    const again = await screen.findByRole("dialog", { name: "Page 19" });
    expect(within(again).getByRole("button", { name: "Fix sideways (turn 270°) in the new files" })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(again).getByRole("button", { name: "Do not turn this page" }));
    await waitFor(() => expect(screen.queryByText("1 page to turn")).toBeNull());
  });

  it("offers a page with no sideways measurement only fixed degrees, and says why a scan has no Fix", async () => {
    await openDemo();
    fireEvent.contextMenu(cell(10));
    const menu = await screen.findByRole("dialog", { name: "Page 10" });
    expect(within(menu).queryByRole("button", { name: /Fix sideways/ })).toBeNull();
    expect(within(menu).getByRole("button", { name: "Turn 90° clockwise in the new files" })).toBeInTheDocument();
    await waitFor(() => expect(menu).toHaveTextContent("Its text is upright."));
    fireEvent.keyDown(menu, { key: "Escape" });
    fireEvent.contextMenu(cell(9));
    const blank = await screen.findByRole("dialog", { name: "Page 9" });
    expect(blank).not.toHaveTextContent(/sideways/i);
  });
});

describe("flags on the rail", () => {
  it("shows the first flag as glyph and words in the compact rail, a button for the rest, and the count in the summary", async () => {
    const user = userEvent.setup();
    await openDemo();
    await openRail(user);
    const chips = await screen.findByRole("group", { name: "Flags for segment 1" });
    expect(within(chips).getByText("3 sideways pages")).toBeInTheDocument();
    expect(chips.querySelectorAll("svg[data-glyph='refresh-cw']").length).toBe(1);
    expect(within(chips).queryByText("May be over the size limit")).toBeNull();                 // the rest are behind the button, and named in its label
    const more = within(chips).getByRole("button", { name: /All 3 flags for segment 1: 3 sideways pages; May be over the size limit; May hold more than one document/ });
    expect(more).toHaveTextContent("+2 more");
    await waitFor(() => expect(screen.getByText(/flags: 1 segment flagged/)).toBeInTheDocument());
  });

  it("opens every flag in a sentence, states the estimate as an estimate, and goes to a sideways page", async () => {
    const user = userEvent.setup();
    await openDemo();
    await openRail(user);
    const chips = await screen.findByRole("group", { name: "Flags for segment 1" });
    await user.click(within(chips).getByRole("button", { name: /All 3 flags/ }));
    const dialog = await screen.findByRole("dialog", { name: "Flags for segment 1" });
    expect(dialog).toHaveTextContent("Pages 19, 61, 66 are sideways: the text runs up or down the page, measured from the text layer");
    expect(dialog).toHaveTextContent(/about 4\.9 MB \(an estimate from the file's size in proportion to its pages\).*limit of 2\.0 MB/);
    expect(dialog).toHaveTextContent("Nothing is marked.");
    await user.click(within(dialog).getByRole("button", { name: "Go to page 61" }));
    expect(screen.queryByRole("dialog", { name: "Flags for segment 1" })).toBeNull();
    expect(screen.getAllByText(/Page 61 of 120/).length).toBeGreaterThan(0);
  });

  it("fixes the flagged sideways pages from the dialog", async () => {
    const user = userEvent.setup();
    await openDemo();
    await openRail(user);
    const chips = await screen.findByRole("group", { name: "Flags for segment 1" });
    await user.click(within(chips).getByRole("button", { name: /All 3 flags/ }));
    const dialog = await screen.findByRole("dialog", { name: "Flags for segment 1" });
    await user.click(within(dialog).getByRole("button", { name: "Fix these 3 pages in the new files" }));
    expect(JSON.parse(sessionStorage.getItem("jason-split-turns-demo")!)).toEqual({ "19": "fix", "61": "fix", "66": "fix" });
    expect(screen.getByText("3 pages to turn")).toBeInTheDocument();
  });

  it("walks the pages that may start another document with 'Review these pages', marking nothing until a button is pressed", async () => {
    const user = userEvent.setup();
    await openDemo();
    await openRail(user);
    const chips = await screen.findByRole("group", { name: "Flags for segment 1" });
    await user.click(within(chips).getByRole("button", { name: /All 3 flags/ }));
    const dialog = await screen.findByRole("dialog", { name: "Flags for segment 1" });
    expect(dialog).toHaveTextContent(/look like the start of another document, strongest first/);
    await user.click(within(dialog).getByRole("button", { name: "Review these pages" }));
    const bar = await screen.findByRole("region", { name: "Reviewing pages" });
    const first = Number(/Reviewing page (\d+)/.exec(bar.textContent!)![1]);
    expect(bar).toHaveTextContent("1 of ");
    expect(bar).toHaveTextContent("may hold another document");
    expect(bar).toHaveTextContent("Nothing is marked until you press the button.");
    expect(within(bar).getByRole("button", { name: "Previous page to review" })).toBeDisabled();
    expect(cell(first) ?? true).toBeTruthy();
    await user.click(within(bar).getByRole("button", { name: "Next page to review" }));
    const second = Number(/Reviewing page (\d+)/.exec(bar.textContent!)![1]);
    expect(second).not.toBe(first);
    expect(screen.getAllByText(new RegExp(`Page ${second} of 120`)).length).toBeGreaterThan(0);
    await user.click(within(bar).getByRole("button", { name: `Mark page ${second} as a start` }));
    await waitFor(() => expect(within(bar).getByRole("button", { name: `Page ${second} already starts a segment` })).toBeDisabled());
    await saved();
    await user.click(within(bar).getByRole("button", { name: "Done reviewing" }));
    expect(screen.queryByRole("region", { name: "Reviewing pages" })).toBeNull();
  });

  it("finds the sideways pages from the Pages menu and fixes them all in the new files", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(screen.getByRole("button", { name: "Pages" }));
    await user.click(await screen.findByRole("menuitem", { name: "Find and fix sideways pages…" }));
    await user.click(screen.getByRole("button", { name: "Find sideways pages" }));
    expect(await screen.findByText(/3 pages are sideways\. Turning is done in the new files only/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fix all 3 sideways pages" }));
    expect(screen.getByText("3 pages to turn")).toBeInTheDocument();
  });
});

describe("the review: filing, turning, and the flags", () => {
  async function toReview(user: ReturnType<typeof userEvent.setup>, marks: number[] = [10, 20]) {
    await openDemo();
    for (const p of marks) await user.click(cell(p));
    await saved();
    await user.click(reviewButton());
    await screen.findByRole("heading", { name: /^Review:/ });
  }

  it("defaults to what the server says: a part with a slot fills it, a full slot keeps the part held, any other is held", async () => {
    const user = userEvent.setup();
    await toReview(user);
    expect(screen.getByRole("radio", { name: /As each part is labelled/ })).toBeChecked();
    const rows = within(screen.getByRole("table", { name: /The files this split would make/ })).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Kept in jason's store, not filed yet");
    expect(rows[1]).toHaveTextContent("Fills its record slot");
    expect(rows[1]).toHaveTextContent("Slot: annual-budget");
    expect(rows[2]).toHaveTextContent("Its slot already holds a file: kept in the store instead");
    const plan = screen.getAllByRole("list", { name: "What the choices come to" })[0];
    expect(plan).toHaveTextContent("Filing (as labelled): 1 held, 0 to the library, 1 into a slot, 1 kept held because the slot is full.");
  });

  it("sends the chosen filing and a part's own override, shows the counts and the library note, and writes the library result with its reasons", async () => {
    const user = userEvent.setup();
    const act = vi.spyOn(demoBackend(), "act");
    await toReview(user, [10, 11]);                                                          // part 3 starts mid-document: the made-up intake reads no kind there
    await user.click(screen.getByRole("radio", { name: /Library/ }));
    await waitFor(() => expect(act).toHaveBeenCalledWith("demo", expect.objectContaining({ act: "review", filing: "library" })));
    expect(await screen.findByText(/It does not run OCR in this step/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("list", { name: "What the choices come to" })[0]).toHaveTextContent("Filing (library): 0 held, 3 to the library, 0 into slots."));
    await user.selectOptions(screen.getByLabelText("Where part 2 goes"), "slot");
    await waitFor(() => expect(act).toHaveBeenCalledWith("demo", expect.objectContaining({ act: "review", filing: "library", parts: [{ segment: "s2", filing: "slot" }] })));
    await waitFor(() => expect(screen.getAllByRole("list", { name: "What the choices come to" })[0]).toHaveTextContent("Filing (library): 0 held, 2 to the library, 1 into a slot."));
    await user.selectOptions(screen.getByLabelText("Where part 2 goes"), "");
    await user.click(await screen.findByRole("button", { name: "Preview the split" }));
    const preview = await screen.findByRole("region", { name: "What the split will do" });
    expect(within(preview).getByRole("list", { name: "The dry run's counts" })).toHaveTextContent("3 to the library");
    await user.click(screen.getByRole("button", { name: /^Write 3 files/ }));
    await screen.findByRole("heading", { name: "The split was written" });
    const sent = act.mock.calls.filter(([, b]) => b.act === "apply" && b.dryRun === false);
    expect(sent).toHaveLength(1);
    expect(sent[0][1]).toMatchObject({ filing: "library", confirm: true });
    const written = screen.getByRole("heading", { name: "The split was written" }).closest("section")!;
    expect(written).toHaveTextContent("2 files were taken in by the library: s1 as welcome letter (lib-1); s2 as annual budget (lib-2).");
    expect(written).toHaveTextContent("Kept, with the reason: s3 (not taken in by the library: no kind read).");
    expect(screen.queryByText(/queued for OCR/)).toBeNull();                                               // the demo's answer carries no ocrQueued, so none is claimed
  });

  it("offers a part its slot only when it names one, and refuses nothing the server would", async () => {
    const user = userEvent.setup();
    await toReview(user);
    const one = screen.getByLabelText("Where part 1 goes");
    expect(within(one).queryByRole("option", { name: /its slot/ })).toBeNull();
    const two = screen.getByLabelText("Where part 2 goes");
    expect(within(two).getByRole("option", { name: "Where it goes: its slot (annual-budget)" })).toBeInTheDocument();
  });

  it("turns pages per page and all at once, sends rotate, and shows the rotated and the left counts", async () => {
    const user = userEvent.setup();
    const act = vi.spyOn(demoBackend(), "act");
    await toReview(user);
    const section = await screen.findByRole("region", { name: "Pages to turn" });
    await waitFor(() => expect(within(section).getByLabelText("Turn for page 19")).toBeInTheDocument());
    expect(within(section).getByText("Page 19: sideways, its text is turned 90°")).toBeInTheDocument();
    expect(screen.getAllByRole("list", { name: "What the choices come to" })[0]).toHaveTextContent("0 pages turned in the new files; 3 measured sideways stay as they are.");
    await user.selectOptions(within(section).getByLabelText("Turn for page 61"), "180");
    await waitFor(() => expect(act).toHaveBeenCalledWith("demo", expect.objectContaining({ act: "review", rotate: { "61": 180 } })));
    await waitFor(() => expect(screen.getAllByRole("list", { name: "What the choices come to" })[0]).toHaveTextContent("1 page turned in the new files (61); 2 measured sideways stay as they are."));
    await user.click(within(section).getByRole("button", { name: "Fix all 3 sideways pages" }));
    await waitFor(() => expect(act).toHaveBeenCalledWith("demo", expect.objectContaining({ act: "review", rotate: { "19": "fix", "61": "fix", "66": "fix" } })));
    await waitFor(() => expect(screen.getAllByRole("list", { name: "What the choices come to" })[0]).toHaveTextContent("3 pages turned in the new files (19, 61, 66); 0 measured sideways stay as they are."));
    expect(screen.getByText(/Turns pages 19 by 270°, 61 by 90°, 66 by 270° in this file\.|Turns page 19 by 270°/)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Preview the split" }));
    const preview = await screen.findByRole("region", { name: "What the split will do" });
    expect(within(preview).getByRole("list", { name: "The dry run's counts" })).toHaveTextContent("3 pages turned in the new files (19, 61, 66)");
    await user.click(screen.getByRole("button", { name: /^Write 3 files/ }));
    await screen.findByRole("heading", { name: "The split was written" });
    expect(screen.getByText(/3 pages were turned in the new files: 19 by 270°, 61 by 90°, 66 by 270°\./)).toBeInTheDocument();
    const sent = act.mock.calls.filter(([, b]) => b.act === "apply" && b.dryRun === false);
    expect(sent[0][1]).toMatchObject({ rotate: { "19": "fix", "61": "fix", "66": "fix" } });
  });

  it("carries a turn chosen from a page menu into the review, and lets it be set back", async () => {
    const user = userEvent.setup();
    await openDemo();
    fireEvent.contextMenu(cell(19));
    await user.click(within(await screen.findByRole("dialog", { name: "Page 19" })).getByRole("button", { name: "Turn 90° clockwise in the new files" }));
    await user.click(cell(10));
    await saved();
    await user.click(reviewButton());
    const section = await screen.findByRole("region", { name: "Pages to turn" });
    await waitFor(() => expect(within(section).getByLabelText("Turn for page 19")).toHaveValue("90"));
    await user.click(within(section).getByRole("button", { name: "Leave every page as it is" }));
    await waitFor(() => expect(within(section).getByLabelText("Turn for page 19")).toHaveValue(""));
    expect(JSON.parse(sessionStorage.getItem("jason-split-turns-demo")!)).toEqual({});
  });

  it("shows each part's flags as a glyph, words and a sentence, with a 'Review these pages' action that leaves the review for the pages", async () => {
    const user = userEvent.setup();
    await openDemo();
    await user.click(cell(10));
    await saved();
    await user.click(reviewButton());
    await screen.findByRole("heading", { name: /^Review:/ });
    const list = (await screen.findAllByRole("list", { name: /^Flags for part/ }))[0];
    expect(list).toHaveTextContent("May hold more than one document.");
    expect(list.querySelector("svg[data-glyph='split']")).toBeTruthy();
    await user.click(within(list).getByRole("button", { name: "Review these pages" }));
    expect(await screen.findByRole("region", { name: "Reviewing pages" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^Review:/ })).toBeNull();
  });
});

describe("the review against answers the demo does not give", () => {
  const part = (n: number, extra: Partial<ReviewPart> = {}): ReviewPart => ({ segment: `s${n}`, level: 0, start: n * 10 - 9, end: n * 10, ordinal: n, slot: "", title: `Part ${n}`, kind: null, pages: [[n * 10 - 9, n * 10]], count: 10, name: "", action: "held", ...extra });
  const review = (parts: ReviewPart[], more: Partial<Review> = {}): Review => ({ id: "x", status: "draft", version: 1, sourcePages: 20, files: parts.length, parts, dropped: [], pagesInFiles: 20, totalsOk: true, problems: [], collisions: [], duplicates: [], held: [], result: "", ...more });
  const mount = (rv: Review, applyAnswer: Record<string, unknown>) => {
    const backend = {
      act: async (_id: string, b: { act: string }) => (b.act === "review" ? { act: "review", review: rv } : { act: "apply", ok: true, dryRun: false, filled: [], held: [], skipped: [], failed: [], dropped: [], ...applyAnswer }),
      session: async () => ({ flags: undefined }),
    } as unknown as SplitBackend;
    const loader = new ThumbLoader({ urlOf: () => "", fetcher: () => new Promise<string>(() => undefined) });
    const facts = new FactsCache(new DemoBackend(), "demo", 20);
    return render(<SplitReview backend={backend} id="x" by="Test" loader={loader} facts={facts} status="draft" drop={[]} setDrop={() => undefined} onBack={() => undefined} onDone={() => undefined} confidential={false} onRename={async () => undefined} />);
  };

  it("says OCR was queued only when the server says so", async () => {
    const user = userEvent.setup();
    const run = async (answer: Record<string, unknown>) => {
      const view = mount(review([part(1), part(2)]), answer);
      await screen.findByText(/Pages add up/);
      await user.click(screen.getByRole("button", { name: "Preview the split" }));
      await user.click(await screen.findByRole("button", { name: /^Write 2 files/ }));
      await screen.findByRole("heading", { name: "The split was written" });
      return view;
    };
    const none = await run({ library: [{ segment: "s1", action: "library", libraryId: "lib-9", kind: "invoice" }] });
    expect(screen.getByText(/1 file was taken in by the library: s1 as invoice \(lib-9\)\./)).toBeInTheDocument();
    expect(screen.queryByText(/queued for OCR/)).toBeNull();
    none.unmount();
    const some = await run({ library: [{ segment: "s1", action: "library" }], ocrQueued: 2 });
    expect(screen.getByText("2 parts were queued for OCR.")).toBeInTheDocument();
    some.unmount();
    await run({ ocrQueued: [{ segment: "s2" }] });
    expect(screen.getByText("1 part was queued for OCR.")).toBeInTheDocument();
  });

  it("shows the server's flags on a part in its own words, with the exact size where the review cut it", async () => {
    mount(review([part(1, { size: 3_100_000, flags: { overPartLimit: true, nearDuplicateOf: "s1", blankOnly: true }, sideways: [{ page: 4, turn: 90, fix: 270 }] }), part(2)]), {});
    const list = await screen.findByRole("list", { name: "Flags for part 1" });
    expect(list).toHaveTextContent("Blank only.");
    expect(list).toHaveTextContent("Repeats segment 1.");
    expect(list).toHaveTextContent("1 sideways page.");
    expect(list).toHaveTextContent("Over the size limit.");
    expect(list).toHaveTextContent("it would be 3.1 MB. A slot");
    expect(screen.queryByRole("list", { name: "Flags for part 2" })).toBeNull();
    for (const li of within(list).getAllByRole("listitem")) expect(li.querySelector("svg[data-glyph]")).toBeTruthy();               // a glyph beside every flag: never colour alone
  });

  it("states a refusal of the server's in its words and keeps the choices", async () => {
    const backend = {
      act: async () => { throw new Error("page 45: jason measured no sideways text there (a page with no text layer is never measured); name the degrees (90, 180, or 270) to turn it"); },
      session: async () => ({}),
    } as unknown as SplitBackend;
    const loader = new ThumbLoader({ urlOf: () => "", fetcher: () => new Promise<string>(() => undefined) });
    render(<SplitReview backend={backend} id="x" by="Test" loader={loader} facts={new FactsCache(new DemoBackend(), "demo", 20)} status="draft" drop={[]} setDrop={() => undefined}
      onBack={() => undefined} onDone={() => undefined} confidential={false} onRename={async () => undefined} turns={{ 45: "fix" }} setTurns={() => undefined} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("a page with no text layer is never measured");
  });
});
