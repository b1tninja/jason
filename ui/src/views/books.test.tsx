import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BooksChecksView } from "./BooksChecksView";

function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    return new Response(JSON.stringify(key ? routes[key] : { error: `no route ${url}` }), { status: key ? 200 : 404 });
  }));
}
afterEach(() => vi.unstubAllGlobals());

describe("BooksChecksView", () => {
  it("lists utility payments with their questions, then the ledger checklist", async () => {
    mockFetch({
      "/api/utility-payments": { found: true, transactionsSyncedAt: "2026-10-01", summary: { "no attachment": 1, water: 2 }, payments: [
        { key: "a", date: "2026-09-02", amountCents: 6120, payee: "City Water", description: "water", categories: ["Utilities: Water"], documents: [{ filename: "bill-sep.pdf", kind: "bill" }], findings: [], ok: true, utility: "water" },
        { key: "b", date: "2026-09-05", amountCents: 12000, payee: "Power Co", description: "power", categories: ["Utilities: Electric"], documents: [], findings: ["no attachment"], ok: false, utility: "electric" },
      ], caveats: ["A finding is a question, not a verdict."] },
      "/api/ledger-validation": { found: true, balancesChecked: 3, latestSheet: { period: "2026-09", asOf: "2026-09-30", accounts: [] },
        runs: [{ id: 1, name: "Treasurer Packet 2026-08", period: "2026-08", completedAt: "2026-09-02", pages: 12, libraryCopies: ["Finance/2026-08 report.pdf"], notes: [] },
               { id: 2, name: "Treasurer Packet 2026-09", period: "2026-09", completedAt: "2026-10-01", pages: 11, libraryCopies: [], notes: ["period read from the name"] }],
        runsMissingFromLibrary: [{ name: "Treasurer Packet 2026-09", period: "2026-09" }],
        libraryCopiesNotFromARun: [],
        balanceChanges: [{ period: "2026-08", periodFrom: "run", path: "Finance/2026-08 report.pdf", account: "Operating (Bank)", printedCents: 100000, ledgerCents: 125050, asOf: "2026-08-31" }],
        accountsTheLedgerDropped: [],
        caveats: ["The report the board saw is the record of what it was told."] },
    });
    render(<BooksChecksView />);
    expect(await screen.findByText("City Water")).toBeInTheDocument();
    expect(screen.getByText("bill-sep.pdf")).toBeInTheDocument();
    expect(screen.getByText("none")).toBeInTheDocument();
    expect(screen.getByText("$61.20")).toBeInTheDocument();
    expect(screen.getAllByText("no attachment").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/jason changes nothing in PayHOA\./)).toBeInTheDocument();
    expect(screen.getByText("A finding is a question, not a verdict.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Ledger validation" }));
    expect(await screen.findByText("Runs with no identical copy in the library (1)")).toBeInTheDocument();
    expect(screen.getByText("Printed balances that differ from the ledger today (1)")).toBeInTheDocument();
    expect(screen.getByText("$1,000.00")).toBeInTheDocument();
    expect(screen.getByText("$1,250.50")).toBeInTheDocument();
    expect(screen.getByText("$250.50")).toBeInTheDocument();
    // Empty categories read "none", including the one the response left out.
    expect(screen.getByText("Library copies that are not a run as generated (0)")).toBeInTheDocument();
    expect(screen.getByText("Copies filed under another month (0)")).toBeInTheDocument();
    expect(screen.getAllByText("none").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("The report the board saw is the record of what it was told.")).toBeInTheDocument();
  });

  it("shows the tool's note when nothing is on disk", async () => {
    mockFetch({ "/api/utility-payments": { found: false, note: "no utility payments on disk" } });
    render(<BooksChecksView />);
    expect(await screen.findByText("no utility payments on disk")).toBeInTheDocument();
  });
});
