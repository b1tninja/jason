import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CitationChip, CitationGaps, CitedSections, IngestCitations, ReferencePage, ReferenceShelf, StandingPill, StandingStrip, WorkCard,
  citationsPerFile, markCitedSentence,
  type CitationRow, type CitationsData, type GapsData, type ReferencePageData, type ReferenceWork, type WorksData,
} from "../components";
import { ReferenceShelfView } from "./ReferenceShelfView";

const CAVEATS = ["Citations are read by a grammar: a range is read as its two ends, a citation the grammar misses stays missed."];

const row = (citation: string, standing: CitationRow["standing"], extra: Partial<CitationRow> = {}): CitationRow => ({
  citation, standing, meaning: "", mentions: 1, citedBy: ["Example Guide"], page: "", subdivisions: [], quote: `See ${citation}.`, ...extra,
});

const sections: CitationRow[] = [
  row("CIV 5650", "ON_SHELF"),
  row("GOV 66427", "NOT_EXPORTED", { mentions: 2, page: "2", subdivisions: ["(b)"], quote: "Compliance follows Government Code Section 66427 for a condominium plan, and more." }),
  row("BPC 11001.1", "NOT_FOUND", { page: "3" }),
  row("CIV 1351", "RENUMBERED", { page: "1" }),
];

const cites: CitationsData = {
  found: true, source: "Example Guide", made: "2099-10-03", lawChecked: true,
  counts: { ON_SHELF: 1, NOT_EXPORTED: 1, NOT_FOUND: 1, RENUMBERED: 1 }, total: 4, shown: 4, sections, proposal: "GOV 66427", notes: [], caveats: CAVEATS,
};

const gaps: GapsData = {
  found: true, surveys: [{ name: "Example Guide", kind: "reference", made: "2099-10-03", lawChecked: true }],
  total: 3, shown: 3, gaps: sections.filter((s) => s.standing !== "ON_SHELF"), proposal: "GOV 66427", unchecked: 2, caveats: CAVEATS,
};

const work: ReferenceWork = {
  title: "Example Guide", file: "ExampleGuide.pdf", author: "A. Author", publisher: "An Agency", year: 2014, url: "https://example.test/guide.pdf",
  covers: "how a subdivision is made", caveat: "It predates later amendments: read a cited section from the shelf.", topics: [],
  onDisk: true, pages: 3, surveyed: "2099-10-03", lawChecked: true, counts: { ON_SHELF: 1, NOT_EXPORTED: 1 }, command: null,
};

const page: ReferencePageData = {
  found: true, work: "Example Guide", file: "ExampleGuide.pdf", page: 2, pages: 3, noText: false,
  text: "Compliance follows Government Code Section 66427\nfor a condominium plan, and more.",
  banner: "An explanation, not the law and not the association's record.", caveat: work.caveat,
};

afterEach(() => vi.unstubAllGlobals());

function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    return new Response(JSON.stringify(key ? routes[key] : { error: `no route ${url}` }), { status: key ? 200 : 404 });
  }));
}

describe("StandingPill and StandingStrip", () => {
  it("says each standing in its word, with the meaning as the title; an unknown code stays neutral", () => {
    render(<><StandingPill standing="NOT_EXPORTED" /><StandingPill standing="ON_SHELF" /><StandingPill standing="SOMETHING_NEW" /></>);
    expect(screen.getByText("not exported").closest("span[title]")).toHaveAttribute("title", expect.stringContaining("lawlibrary holds the section"));
    expect(screen.getByText("not exported").className).toContain("badge-warn");      // a gap is a lead: never bad
    expect(screen.getByText("on the shelf").className).toContain("badge-good");
    expect(screen.getByText("something new").className).toContain("badge-neutral");
  });

  it("lists every count in words beside the bar and says so when nothing is cited", () => {
    const { rerender } = render(<StandingStrip counts={{ ON_SHELF: 48, NOT_EXPORTED: 29 }} />);
    const group = screen.getByRole("group", { name: "Sections by standing" });
    expect(within(group).getByText("not exported")).toBeInTheDocument();
    expect(within(group).getByText("48")).toBeInTheDocument();
    expect(within(group).getByText("77 in all")).toBeInTheDocument();
    rerender(<StandingStrip counts={{}} />);
    expect(screen.getByText("No section cited.")).toBeInTheDocument();
  });
});

describe("CitedSections", () => {
  it("lists the gaps first, says how it was made, and offers the proposal as a string to copy", () => {
    render(<CitedSections data={cites} />);
    const order = screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);
    expect(order.map((o) => o?.replace(/\s.*/, ""))).toEqual(["BPC", "GOV", "CIV", "CIV"]);
    expect(order[0]).toContain("BPC 11001.1");
    expect(order[3]).toContain("CIV 5650");                                          // on the shelf last
    expect(screen.getByText(/Looked up in lawlibrary 2099-10-03/)).toBeInTheDocument();
    expect(screen.getByText(/Each section is placed against the shelf as it is now/)).toBeInTheDocument();
    const proposal = screen.getByRole("group", { name: "Sections to add to the shelf" });
    expect(within(proposal).getByText("GOV 66427")).toBeInTheDocument();
    expect(within(proposal).getByText(/jason adds nothing/)).toBeInTheDocument();
    expect(within(proposal).queryByRole("button", { name: /add/i })).toBeNull();     // there is no Add button
    expect(screen.getByLabelText("Caveats")).toHaveTextContent(CAVEATS[0]);
  });

  it("says when lawlibrary was not asked, filters to the gaps, and opens a page from the page button", async () => {
    const onOpenPage = vi.fn();
    render(<CitedSections data={{ ...cites, lawChecked: false, made: null }} onOpenPage={onOpenPage} />);
    expect(screen.getByText(/Not looked up in lawlibrary/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("4 of 4 sections");
    await userEvent.selectOptions(screen.getByLabelText("Show"), "gaps");
    expect(screen.getByRole("status")).toHaveTextContent("3 of 4 sections");
    expect(screen.queryByText("CIV 5650")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Open page 2 for GOV 66427" }));
    expect(onOpenPage).toHaveBeenCalledWith(2, expect.objectContaining({ citation: "GOV 66427" }));
  });

  it("shows the page as text when nothing opens it, and a count when the tool capped the list", () => {
    render(<CitedSections data={{ ...cites, total: 90, shown: 4 }} />);
    expect(screen.queryByRole("button", { name: /Open page/ })).toBeNull();
    expect(screen.getByText("4 of 90 shown: the rest are in the tool.")).toBeInTheDocument();
  });
});

describe("CitationGaps", () => {
  it("counts the gaps and the unchecked, says how to ask lawlibrary, and names the surveys behind the list", () => {
    render(<CitationGaps data={gaps} />);
    expect(screen.getByText("Gaps").closest(".stat")).toHaveTextContent("3");
    expect(screen.getByText("Unchecked").closest(".stat")).toHaveTextContent("2");
    expect(screen.getByText(/2 sections are off the shelf and were not asked of lawlibrary/)).toBeInTheDocument();
    expect(screen.getByText("jason reference --cites WORK")).toBeInTheDocument();
    expect(screen.getByText("GOV 66427", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText("1 surveys behind this list")).toBeInTheDocument();
  });

  it("says plainly when there is no gap, and lets a person open the work that cites a section", async () => {
    const onOpenWork = vi.fn();
    const { rerender } = render(<CitationGaps data={gaps} onOpenWork={onOpenWork} />);
    await userEvent.click(screen.getAllByRole("button", { name: "Example Guide" })[0]);
    expect(onOpenWork).toHaveBeenCalledWith("Example Guide");
    rerender(<CitationGaps data={{ ...gaps, total: 0, shown: 0, gaps: [], proposal: "", unchecked: 0 }} />);
    expect(screen.getByText(/No gap: every section/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Sections to add to the shelf" })).toBeNull();
  });
});

describe("ReferenceShelf", () => {
  it("keeps a work's trust caveat open and says whether it is surveyed", () => {
    render(<WorkCard work={work} />);
    const card = screen.getByRole("listitem", { name: "Example Guide" });
    expect(card).toHaveTextContent("How far to trust it. It predates later amendments");
    expect(card).toHaveTextContent("Citations surveyed 2099-10-03; lawlibrary asked.");
    expect(within(card).getByRole("link", { name: "Open the original" })).toHaveAttribute("href", "https://example.test/guide.pdf");
  });

  it("gives the fetch command for a work not on disk and the survey command for one not surveyed", () => {
    const data: WorksData = { works: [
      { ...work, file: "a.pdf", title: "Missing Guide", onDisk: false, pages: 0, surveyed: null, counts: null, command: "jason reference --cites a.pdf" },
      { ...work, file: "b.pdf", title: "Unsurveyed Guide", surveyed: null, counts: null, command: "jason reference --cites b.pdf" },
    ], caveats: CAVEATS };
    render(<ReferenceShelf data={data} />);
    const missing = screen.getByRole("listitem", { name: "Missing Guide" });
    expect(within(missing).getByText("jason reference --fetch")).toBeInTheDocument();
    expect(within(missing).queryByRole("button", { name: /Read the citations/ })).toBeNull();
    const unsurveyed = screen.getByRole("listitem", { name: "Unsurveyed Guide" });
    expect(unsurveyed).toHaveTextContent("Citations not surveyed yet.");
    expect(within(unsurveyed).getByText("jason reference --cites b.pdf")).toBeInTheDocument();
  });
});

describe("ReferencePage", () => {
  it("carries the banner and the work's caveat on every page, and marks the sentence across a line break", () => {
    render(<ReferencePage data={page} sentence="Government Code Section 66427 for a condominium plan" />);
    expect(screen.getByRole("note")).toHaveTextContent("An explanation, not the law and not the association's record.");
    expect(screen.getByRole("note")).toHaveTextContent("It predates later amendments");
    expect(screen.getByRole("region", { name: "Example Guide, page 2" })).toBeInTheDocument();
    expect(document.querySelector("mark")?.textContent).toBe("Government Code Section 66427\nfor a condominium plan");
  });

  it("walks the pages within their bounds and says a page has no text layer", async () => {
    const onPage = vi.fn();
    const { rerender } = render(<ReferencePage data={{ ...page, page: 1 }} onPage={onPage} />);
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPage).toHaveBeenCalledWith(2);
    rerender(<ReferencePage data={{ ...page, page: 3, noText: true, text: "" }} onPage={onPage} />);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    expect(screen.getByText(/no text layer/)).toBeInTheDocument();
  });

  it("marks only a sentence the page holds", () => {
    expect(markCitedSentence("one two", "absent words")).toBe("one two");
    expect(markCitedSentence("one two", undefined)).toBe("one two");
  });
});

describe("the ingest's citations", () => {
  const ingest: CitationsData = { ...cites, source: "ingest", report: "ingest-2099-10-03.json", sections: [
    row("GOV 66427", "NOT_EXPORTED", { citedBy: ["notice-example.pdf", "letter-example.pdf"] }),
    row("CIV 5650", "ON_SHELF", { citedBy: ["notice-example.pdf"] }),
  ] };

  it("counts each file's sections and gaps, and says the list is private", () => {
    expect(citationsPerFile(ingest.sections)).toEqual([
      { file: "letter-example.pdf", sections: 1, gaps: 1 }, { file: "notice-example.pdf", sections: 2, gaps: 1 },
    ]);
    render(<IngestCitations data={ingest} />);
    expect(screen.getByText(/names the association's files: it is private/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Sections cited by each file" });
    expect(within(table).getByText("notice-example.pdf")).toBeInTheDocument();
  });

  it("is a chip a sentence can carry", () => {
    render(<p>Fees follow <CitationChip citation="CIV 5650" standing="ON_SHELF" /> and <CitationChip citation="CIV 1351" standing="RENUMBERED" />.</p>);
    expect(screen.getByText("CIV 1351").parentElement).toHaveTextContent("renumbered");
  });
});

describe("ReferenceShelfView", () => {
  it("with no survey, says so and shows the commands that make one", async () => {
    mockFetch({ "/api/citation-gaps": { found: false, note: "no citation survey; run jason reference --cites WORK, or jason ingest SOURCE" } });
    render(<ReferenceShelfView />);
    expect(await screen.findByText(/no citation survey/)).toBeInTheDocument();
    expect(screen.getByText("jason ingest SOURCE")).toBeInTheDocument();
  });

  it("walks from a work to its citations to the page with the sentence marked", async () => {
    mockFetch({
      "/api/citation-gaps": gaps,
      "/api/reference-works": { works: [work], caveats: CAVEATS },
      "/api/citations?source=ExampleGuide.pdf": cites,
      "/api/reference-page?work=ExampleGuide.pdf&page=2": page,
    });
    render(<ReferenceShelfView />);
    expect(await screen.findByText("Sections cited and not on the shelf", { selector: "caption" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Reference works" }));
    await userEvent.click(await screen.findByRole("button", { name: "Read the citations in Example Guide" }));
    await userEvent.click(await screen.findByRole("button", { name: "Open page 2 for GOV 66427" }));
    await waitFor(() => expect(screen.getByRole("note")).toHaveTextContent("An explanation, not the law"));
    expect(document.querySelector("mark")?.textContent).toBe(page.text);        // the whole sentence, across its line break
    await userEvent.click(screen.getByRole("button", { name: "Close the page" }));
    expect(screen.queryByRole("note")).toBeNull();
  });
});
