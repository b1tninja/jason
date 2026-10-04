import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentLocator } from "./DocumentLocator";
import { resetServerSession } from "../lib/api";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const LOCATED = {
  association: "Example Village HOA", county: "placer", located_at: "2026-10-02T15:04:00", searches: 42, liens: 386,
  spellings: ["EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION", "EXAMPLE VILLAGE HOA"],
  items: [
    { item: "declaration", title: "The declaration (CC&Rs), the recorded copy", question: "Which is the association's declaration (the CC&Rs later amendments amend)?", stakes: true,
      located: [
        { number: "2004-0012345", recorded: "2004-03-01", filing: "DECLARATION", tie: "NAMED", tie_label: "names the association", strong: true, via: "", parties: ["EXAMPLE HOMES INC", "EXAMPLE VILLAGE HOA"], people: [{ name: "SAMPLE PAT Q", side: "E" }] },
      ] },
    { item: "annexations", title: "Annexations", question: "Which of these annex a phase into the association (or take one out)?", stakes: false,
      located: [
        { number: "2005-0020001", recorded: "2005-06-10", filing: "DECLARATION OF ANNEXATION", tie: "BESIDE", tie_label: "recorded with the association's documents", strong: true, via: "2005-0020000", parties: ["EXAMPLE HOMES INC"] },
        { number: "2007-0030003", recorded: "2007-01-15", filing: "DECLARATION OF ANNEXATION", tie: "DECLARANT", tie_label: "the builder's filing", strong: false, via: "EXAMPLE HOMES INC", parties: ["EXAMPLE HOMES INC"] },
      ] },
  ],
  not_located: [{ item: "maps", title: "The subdivision maps", ask: "None in the index under the association's names; ask the board or the prior manager for the recording number." }],
  notes: ["The index before 1999 is not searchable by name."],
  caveats: ["A located document is a lead, not a pin: the recorded copy is read before it is pinned.", "Only business and association parties are kept."],
};

const MISSING = { missing: true, command: 'jason onboard --locate --county placer --name "Example Village HOA"', note: "No documents located for Example Village HOA yet." };

describe("DocumentLocator", () => {
  it("shows a cached result grouped by checklist item, with ties in words, and the board's list", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(LOCATED), { status: 200 })));
    render(<DocumentLocator questionHref={(item) => `#/onboarding?question=${item}`} />);
    expect(await screen.findByRole("heading", { name: "Recorded documents located for Example Village HOA" })).toBeInTheDocument();
    expect(screen.getByText(/42 searches/)).toBeInTheDocument();
    expect(screen.getByText(/386 of the association's own assessment liens and releases, counted, not listed/)).toBeInTheDocument();
    expect(screen.getByText("Oct 2, 2026")).toHaveAttribute("datetime", "2026-10-02");

    const decl = screen.getByRole("region", { name: "The declaration (CC&Rs), the recorded copy" });
    expect(within(decl).getByText("a second person confirms")).toBeInTheDocument();
    expect(within(decl).getByText("SAMPLE PAT Q (E)")).toBeInTheDocument();          // owners are P1: shown
    expect(within(decl).getByText(/Which is the association's declaration.*Do you hold a copy of each\?/)).toBeInTheDocument();
    expect(within(decl).getByText("names the association")).toBeInTheDocument();
    expect(within(decl).getByRole("link", { name: "Answer it" })).toHaveAttribute("href", "#/onboarding?question=declaration");
    expect(within(decl).getByText("fact:lookup:located-declaration")).toBeInTheDocument();

    const annex = screen.getByRole("region", { name: "Annexations" });
    expect(within(annex).getByText("2 located: 1 strong tie · 1 the builder's filing")).toBeInTheDocument();
    const weak = within(annex).getByText("2007-0030003").closest("tr")!;
    expect(within(weak).getByText("the builder's filing")).toBeInTheDocument();
    expect(within(weak).getByText("may be another community's")).toBeInTheDocument();
    expect(within(annex).queryByText("a second person confirms")).not.toBeInTheDocument();

    expect(screen.getByRole("region", { name: "Not located" })).toHaveTextContent("The subdivision maps.");
    expect(screen.getByText("The index before 1999 is not searchable by name.")).toBeInTheDocument();
    expect(screen.getAllByText("A located document is a lead, not a pin: the recorded copy is read before it is pinned.")).toHaveLength(1);

    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: "The board's list" }));
    expect(screen.getByRole("button", { name: "Print the board's list" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader", { name: "We hold a copy" })).toHaveLength(2);
    expect(screen.getAllByRole("columnheader", { name: "Order a copy" })).toHaveLength(2);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    const print = vi.fn();
    vi.stubGlobal("print", print);
    await user.click(screen.getByRole("button", { name: "Print the board's list" }));
    expect(print).toHaveBeenCalled();
  });

  it("queues the locate as a named person, shows the job, and polls until the result arrives", async () => {
    const posts: unknown[] = [];
    let stage: "missing" | "queued" | "done" = "missing";
    let running = 0;
    const gets: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/session") return new Response(JSON.stringify({}), { status: 200 });
      if (init?.method === "POST") {
        posts.push([url, JSON.parse(String(init.body))]);
        stage = "queued";
        return new Response(JSON.stringify({ job: { id: 7, status: "queued" }, command: MISSING.command }), { status: 200 });
      }
      gets.push(url);
      if (stage === "missing") return new Response(JSON.stringify(MISSING), { status: 200 });
      if (stage === "queued") { if (++running >= 4) stage = "done"; return new Response(JSON.stringify({ ...MISSING, job: { id: 7, status: "running" } }), { status: 200 }); }
      return new Response(JSON.stringify({ ...LOCATED, job: { id: 7, status: "done" } }), { status: 200 });
    }));
    render(<DocumentLocator county="placer" name="Example Village HOA" pollMs={20} />);
    expect(await screen.findByText("No documents located for Example Village HOA yet.")).toBeInTheDocument();
    expect(screen.getAllByText(MISSING.command).length).toBeGreaterThan(0);
    expect(gets[0]).toBe("/api/documents-located?county=placer&name=Example+Village+HOA");

    const user = userEvent.setup();
    const by = screen.getByLabelText("Queued by");
    await user.type(by, "jason");
    expect(screen.getByText("jason never signs: give a person's full name.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Locate documents" }));
    expect(posts).toHaveLength(0);
    await user.clear(by);
    await user.type(by, "Jane Example");
    await user.click(screen.getByRole("button", { name: "Locate documents" }));
    expect(screen.getByRole("group", { name: "Queue" })).toHaveTextContent("as Jane Example");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toEqual(["/api/write/documents-located/locate", { county: "placer", name: "Example Village HOA", by: "Jane Example" }]);
    expect(await screen.findByText(/Running: job/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Recorded documents located for Example Village HOA" }, { timeout: 2000 })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 80));
    const after = gets.length;
    await new Promise((r) => setTimeout(r, 80));
    expect(gets.length).toBe(after);
  });

  it("shows the command when writes are off", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/session") return new Response(JSON.stringify({}), { status: 200 });
      if (init?.method === "POST") return new Response(JSON.stringify({ error: "writes are off" }), { status: 405 });
      return new Response(JSON.stringify(MISSING), { status: 200 });
    }));
    render(<DocumentLocator me="Jane Example" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Locate documents" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(await screen.findByText(/Writes are off in this console/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Locate documents" })).not.toBeInTheDocument();
    expect(screen.getAllByText(MISSING.command).length).toBeGreaterThan(0);
  });

  it("names a failed job and offers the locate again", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...MISSING, job: { id: 9, status: "failed" } }), { status: 200 })));
    render(<DocumentLocator me="Jane Example" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("failed. Nothing was located.");
    expect(screen.getByRole("link", { name: "Read its log in the job queue" })).toHaveAttribute("href", "#/jobs");
    expect(screen.getByRole("button", { name: "Locate documents" })).toBeInTheDocument();
  });
});
