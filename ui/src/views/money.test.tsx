import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DOC_WORDS, Doc, type DocRef } from "../components";
import { resetServerSession } from "../lib/api";
import { BooksChecksView } from "./BooksChecksView";
import { MoneyView } from "./MoneyView";
import { ReserveFindingsView } from "./ReserveFindingsView";
import { ReservesView } from "./ReservesView";

/* The Money screens on `Doc` (docs/console/doc-component.md, "Adopting it on a screen"): invoices' and utility bills'
 * attachments, the treasurer's reports the ledger validation names, each borrowing's 5515 documents, and the reserve
 * study. Every reference here is made up. */

const invoice: DocRef = { address: "file:transactions/2099/01/invoices/501-Invoice 77.pdf", document: "pdf", name: "Invoice 77.pdf",
  kind: "pdf", level: "P2", source: "File on disk", size: 19_000, thumb: true };
const bill: DocRef = { address: "file:transactions/2099/02/invoices/601-Water bill.pdf", document: "pdf", name: "Water bill.pdf",
  kind: "pdf", level: "P2", source: "File on disk" };
const report: DocRef = { address: "library:tr0826", document: "library:tr0826", name: "2099-08 report.pdf", kind: "pdf", level: "P0", source: "Library copy" };
const notice: DocRef = { address: "library:ag0215", document: "library:ag0215", name: "2099-02-15 agenda.pdf", kind: "pdf", level: "P0", source: "Library copy" };
const minutes: DocRef = { address: "library:mn0215", document: "library:mn0215", name: "2099-02-15 minutes.pdf", kind: "pdf", level: "P0", source: "Library copy" };
const study: DocRef = { address: "file:reserve-studies/Study 2099.pdf", document: "pdf", name: "Reserve study, fiscal year 2099", kind: "pdf",
  level: "P1", source: "File on disk", readAt: "2099-01-02T00:00:00+00:00", size: 900_000, thumb: true };

const IN = { token: "t", signedIn: { name: "A Treasurer" }, signIn: { configured: true, start: "/auth/google" } };
const OUT = { token: "t", signedIn: null, signIn: { configured: true, start: "/auth/google" } };
const REFUSED = "The treasurer's office doesn't open this document.";
const view = (name: string) => ({ kind: "pdf", name, readAt: "", url: "/api/evidence/document/tok", expires: "", caveats: [] });
const answer = (ref: DocRef) => ({ found: true, address: ref.address, label: ref.name, kind: "file", sources: [{ name: "Recorded copy", readAt: ref.readAt ?? "" }],
  changed: null, changedNote: "", link: "", refresh: [], caveats: [], note: "", refreshable: null,
  documents: [{ id: ref.document ?? "pdf", name: ref.name, kind: "pdf", size: 1, readAt: "", note: "" }] });

const borrowing = {
  kind: "withdrawal", purpose: "borrowing", description: "", exactRepayment: false, repayments: [], day: "2099-03-01", cents: 1_000_000,
  account: "Reserve", number: "77", memo: "roof", deadline: "2100-03-01", repaidCents: 0, outstandingCents: 1_000_000, repaidOn: null,
  documents: { notice: { id: "ag0215", name: notice.name, meeting: "2099-02-15", cites: "", doc: notice },
               minutes: { id: "mn0215", name: minutes.name, draft: false, doc: minutes }, resolution: null },
  gaps: ["no resolution in the library authorizes it"],
};

const ROUTES: Record<string, unknown> = {
  "/api/invoices": { found: true, summary: { "amount not on the attachment": 1 }, caveats: [], payments: [
    { key: "500", date: "2099-01-05", amountCents: 6120, payee: "Example Vendor", description: "", categories: ["Repairs"], ok: false,
      findings: ["no attachment prints the payment's $61.20"],
      documents: [{ id: 9001, filename: "Invoice 77.pdf", kind: "invoice", doc: invoice }, { id: 9002, filename: "Never downloaded.pdf", kind: "" }] },
  ] },
  "/api/utility-payments": { found: true, summary: {}, caveats: [], payments: [
    { key: 601, provider: "water", date: "2099-02-03", amountCents: 6120, rows: [{ txId: 601, category: "Utilities: Water", amountCents: 6120 }],
      attachments: [{ id: 9101, filename: "Water bill.pdf", kind: "utility_bill", doc: bill }], findings: [], ok: true },
  ] },
  "/api/ledger-validation": { found: true, balancesChecked: 1, latestSheet: null, runsMissingFromLibrary: [], libraryCopiesNotFromARun: [],
    copiesUnderAnotherMonth: [], accountsTheLedgerDropped: [], caveats: [],
    runs: [{ id: 1, name: "Treasurer's Report 2099-08", period: "2099-08", libraryCopies: ["Finance/2099-08 report.pdf"], libraryDocs: [report], notes: [] }],
    balanceChanges: [{ period: "2099-08", periodFrom: "run", path: "Finance/2099-08 report.pdf", account: "Operating", printedCents: 100_000, ledgerCents: 125_050, asOf: "2099-08-31", doc: report }] },
  "/api/reserve-findings": { found: true, ledgerThrough: "2099-09-30", kinds: ["finding at borrowing"], needed: 0, budgetYears: [], caveats: [],
    borrowings: [{ ...borrowing, key: "2099-03-01|77", finding: null, findingNeeded: false }] },
  "/api/reserves": { found: true, ledgerThrough: "2099-09-30", reserveAccounts: ["Reserve"], borrowings: [borrowing], budgetYears: [],
    otherWithdrawals: [], unappliedContributions: [], catchUps: [], investments: [], caveats: [], study },
};

/** The server: the screens' loaders, the session, the evidence answer, and the view (`refuse`: a 403 in its words). */
function serve(session: object, { refuse = false } = {}) {
  const posts: [string, unknown][] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as { address: string };
      posts.push([url, body]);
      if (refuse) return new Response(JSON.stringify({ error: REFUSED }), { status: 403 });
      return new Response(JSON.stringify(view(body.address)), { status: 200 });
    }
    if (url.startsWith("/api/session")) return new Response(JSON.stringify(session), { status: 200 });
    if (url.startsWith("/api/evidence?")) return new Response(JSON.stringify(answer(study)), { status: 200 });
    const key = Object.keys(ROUTES).find((k) => url.startsWith(k));
    return new Response(JSON.stringify(key ? ROUTES[key] : { error: `no route ${url}` }), { status: key ? 200 : 404 });
  }));
  return posts;
}

/** No `/api/file` link, no outside frame, and no absolute path in what the screen renders. */
function clean(container: HTMLElement) {
  expect(container.querySelector('a[href*="/api/file"]')).toBeNull();
  expect(container.querySelector("iframe")).toBeNull();
  expect(container.innerHTML).not.toMatch(/[A-Za-z]:[\\/]|\/(?:home|Users)\//);
}

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

describe("Doc chips from the Money loaders' references", () => {
  it.each([["an invoice", invoice], ["a utility bill", bill], ["a treasurer's report", report], ["a borrowing's notice", notice]])(
    "%s renders as a chip from a static reference", (_what, ref) => {
      render(<Doc doc={ref} signedIn by="A Treasurer" onView={vi.fn()} />);
      expect(screen.getByRole("button", { name: `Open ${ref.name}` })).toHaveAccessibleDescription("PDF");
    });

  it("the reserve study renders as a card from a static reference", () => {
    render(<Doc doc={study} variant="card" evidence={answer(study) as never} signedIn by="A Treasurer" onView={vi.fn()} />);
    expect(screen.getByText("Reserve study, fiscal year 2099")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Preview Reserve study, fiscal year 2099/ })).toBeInTheDocument();
  });
});

describe("Invoice review", () => {
  async function invoices() {
    const r = render(<MoneyView />);
    await userEvent.click(screen.getByRole("tab", { name: "Invoice review" }));
    return r;
  }

  it("shows each attachment jason keeps as a chip, and opening it posts one view", async () => {
    const posts = serve(IN);
    const { container } = await invoices();
    const chip = await screen.findByRole("button", { name: "Open Invoice 77.pdf" });
    expect(screen.getByText("Never downloaded.pdf")).toHaveAttribute("title", "No copy on disk");   // no copy: the name only
    expect(posts).toEqual([]);                                                                       // nothing viewed on load
    await userEvent.click(chip);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: invoice.address, document: "pdf", by: "A Treasurer" }]]));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    clean(container);
  });

  it("signed out: says to sign in, with the link, and posts nothing", async () => {
    const posts = serve(OUT);
    await invoices();
    await userEvent.click(await screen.findByRole("button", { name: "Open Invoice 77.pdf" }));
    expect(await screen.findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with Google" })).toBeInTheDocument();
    expect(posts).toEqual([]);
  });

  it("not allowed: the server's reason, in words", async () => {
    serve(IN, { refuse: true });
    await invoices();
    await userEvent.click(await screen.findByRole("button", { name: "Open Invoice 77.pdf" }));
    expect(await screen.findByText(REFUSED)).toBeInTheDocument();
  });
});

describe("Books checks", () => {
  it("shows the utility bills and the treasurer's reports as chips; opening one posts a view", async () => {
    const posts = serve(IN);
    const { container } = render(<BooksChecksView />);
    expect(await screen.findByRole("button", { name: "Open Water bill.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Utilities: Water")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open Water bill.pdf" }));
    await waitFor(() => expect(posts[0]).toEqual(["/api/evidence/view", { address: bill.address, document: "pdf", by: "A Treasurer" }]));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Close" }));
    clean(container);

    await userEvent.click(screen.getByRole("tab", { name: "Ledger validation" }));
    const chips = await screen.findAllByRole("button", { name: "Open 2099-08 report.pdf" });
    expect(chips).toHaveLength(2);                    // the run's copy, and the copy whose printed balance differs
    await userEvent.click(chips[0]);
    await waitFor(() => expect(posts[1]).toEqual(["/api/evidence/view", { address: report.address, document: report.document, by: "A Treasurer" }]));
    clean(container);
  });
});

describe("Reserve findings", () => {
  it("shows the documents that satisfy the record as chips, not an empty hint", async () => {
    const posts = serve(IN);
    const { container } = render(<ReserveFindingsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    const record = screen.getByText("The record as the library shows it").closest("section") as HTMLElement;
    expect(within(record).getByRole("button", { name: `Open ${notice.name}` })).toBeInTheDocument();
    expect(within(record).getByRole("button", { name: `Open ${minutes.name}` })).toBeInTheDocument();
    expect(container.querySelector("li.tick[title]")).toBeNull();
    await userEvent.click(within(record).getByRole("button", { name: `Open ${minutes.name}` }));
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: minutes.address, document: minutes.document, by: "A Treasurer" }]]));
    clean(container);
  });
});

describe("Reserves", () => {
  it("shows the reserve study as a card and each borrowing's documents as chips", async () => {
    const posts = serve(IN);
    const { container } = render(<ReservesView />);
    expect(await screen.findByText("The reserve study")).toBeInTheDocument();
    expect(screen.getByText("Reserve study, fiscal year 2099")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `Open ${notice.name}` })).toBeInTheDocument();
    const preview = screen.getByRole("button", { name: /^Preview Reserve study, fiscal year 2099/ });
    await waitFor(() => expect(preview).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(preview);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: study.address, document: "pdf", by: "A Treasurer" }]]));
    clean(container);
  });

  it("signed out: the study's card asks for a sign-in, never a broken image", async () => {
    serve(OUT);
    render(<ReservesView />);
    expect(await screen.findByText("Sign in to see previews")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("the owner view is the reserve funding summary from the owner loader: no borrowings, no study card", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url);
      return new Response(JSON.stringify({ found: true, note: "", caveats: ["The figures are the preparer's estimates."],
        summary: { fiscalYear: 2099, preparer: "Example Reserve Co", prepared: "2098-09-01", percentFunded: 0.452, projectedEndOfYearCents: 45_200_00, requiredEndOfYearCents: 100_000_00, annualContributionCents: 12_000_00 },
        years: [{ fiscalYear: 2098, percentFunded: 0.41 }, { fiscalYear: 2099, percentFunded: 0.452 }] }), { status: 200 });
    }));
    render(<ReservesView audience="owner" />);
    expect(await screen.findByText("Reserve funding summary, fiscal year 2099")).toBeInTheDocument();
    expect(urls).toEqual(["/api/reserves?view=owner"]);
    expect(screen.getAllByText("45.2%").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Borrowings from the reserve/)).toBeNull();
    expect(screen.queryByText("The reserve study")).toBeNull();
    expect(screen.queryByRole("button", { name: `Open ${notice.name}` })).toBeNull();
  });
});
