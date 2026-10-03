import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MinutesReviewView, fillDraft } from "./MinutesReviewView";

afterEach(() => vi.unstubAllGlobals());

const UNKNOWN = "___ (not in the record)";
const draft = `# DRAFT Minutes of 10/20/26\n\n_"${UNKNOWN}" marks what the record does not show._\n\n## Call to order\n\nThe president called the meeting to order at ${UNKNOWN}.\n\n## Business\n\n### 2. Collections\n\nPat Example is delinquent on assessments.\n\n## Adjournment\n\nThe meeting adjourned at ${UNKNOWN}.\n`;
const blanks = [
  { id: "b1", section: "Call to order", context: `The president called the meeting to order at ${UNKNOWN}.`, marker: UNKNOWN, value: "" },
  { id: "b2", section: "Adjournment", context: `The meeting adjourned at ${UNKNOWN}.`, marker: UNKNOWN, value: "" },
];
const flag = { line: 13, text: "Pat Example is delinquent on assessments.", member: "Pat Example", replacement: "", why: "\"Pat Example\" reads as a person's name beside \"delinquent\"" };
const review = { found: true, date: "2026-10-20", draft, markdown: draft, blanks, open: 2, privacy: [flag], namesFrom: "a conservative reading", sections: [], reviewedBy: "", savedAt: "", history: [],
  minutesFile: "", command: "jason board --minutes 2026-10-20", commands: { redraft: "jason board --minutes 2026-10-20", privacy: "jason minutes-privacy --correct" }, caveats: ["The Secretary approves the text; the board adopts the minutes at its next meeting (CIV 4950)."] };
const listing = { found: true, count: 1, drafts: [{ date: "2026-10-20", file: "data/board/minutes-draft-2026-10-20.md", blanks: 2, filled: 0, reviewed: false, reviewedBy: "", savedAt: "", minutesFile: "", privacyFlags: 1 }], caveats: review.caveats };

describe("fillDraft", () => {
  it("replaces blanks in order, skips headings and the quoted preamble marker, and keeps an empty one", () => {
    const out = fillDraft(draft, { b1: "7:04 PM", b2: " " });
    expect(out).toContain("order at 7:04 PM.");
    expect(out).toContain(`adjourned at ${UNKNOWN}.`);
    expect(out).toContain(`_"${UNKNOWN}" marks`);
    expect(fillDraft("## {Heading}\n\n{a}", { b1: "x" })).toBe("## {Heading}\n\nx");
  });
});

describe("MinutesReviewView", () => {
  it("lists drafts, renders the blanks and privacy flags, updates the preview as you type, and saves values and by", async () => {
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify({ ...review, reviewedBy: "Secretary", minutesFile: "data/board/minutes-2026-10-20.md" }), { status: 200 }); }
      if (url.includes("date=")) return new Response(JSON.stringify(review), { status: 200 });
      return new Response(JSON.stringify(listing), { status: 200 });
    }));
    render(<MinutesReviewView />);
    expect(await screen.findByText("2026-10-20")).toBeInTheDocument();
    expect(screen.getByText("0/2 filled")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(await screen.findByText("Blanks (2)")).toBeInTheDocument();
    expect(screen.getByText("2 blanks open")).toBeInTheDocument();
    expect(screen.getByText(/line 13: "Pat Example is delinquent on assessments\."/)).toBeInTheDocument();
    expect(screen.getByText("jason minutes-privacy --correct")).toBeInTheDocument();
    expect(screen.getByText(/the board adopts the minutes at its next meeting/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("b1 in Call to order"), "7:04 PM");
    await waitFor(() => expect(screen.getByText(/called the meeting to order at 7:04 PM\./)).toBeInTheDocument());
    expect(screen.getByText("1 blank open")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Reviewed by"), "Secretary");
    await userEvent.click(screen.getByRole("button", { name: "Save review" }));
    expect(screen.getByText(/Saves 1 answer beside the draft/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toEqual(["/api/write/minutes-review/2026-10-20", { values: { b1: "7:04 PM" }, by: "Secretary" }]);
    expect(await screen.findByText(/saved: data\/board\/minutes-2026-10-20\.md/)).toBeInTheDocument();
  });

  it("says when there is no draft", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ found: false, count: 0, drafts: [], note: "no minutes draft under data/board; run jason board --minutes DATE" }), { status: 200 })));
    render(<MinutesReviewView />);
    expect(await screen.findByText(/no minutes draft under data\/board; run jason board --minutes DATE/)).toBeInTheDocument();
  });
});
