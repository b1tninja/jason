import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { SESSION_KEY } from "../lib/session";
import plannedJson from "../../../tests/fixtures/approvals/example-village-planned.json";
import type { Approval } from "../lib/approvals";
import { Evidence, EvidencePanel, evidenceUrl, RefreshAllEvidence, type EvidenceAnswer, type EvidenceRefreshAll } from "./index";
import { PlanReview } from "./PlanReview";

afterEach(() => vi.unstubAllGlobals());

function mockFetch(answer: (url: string) => { status?: number; body: unknown }) {
  const f = vi.fn(async (url: string) => {
    const { status = 200, body } = answer(url);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", f);
  return f;
}

const answer = (over: Partial<EvidenceAnswer> = {}): EvidenceAnswer => ({
  found: true, address: "payhoa:submission:1234", label: "PayHOA request 1234", kind: "payhoa_submission",
  sources: [{
    name: "PayHOA request export", readAt: "2026-09-30T18:38:00+00:00", digest: "3f9a02c1d4e7aa", text: "", citation: "", caveat: "", note: "",
    fields: [{ name: "Owner", value: "Jane Doe", masked: false }, { name: "Email", value: "j***@example.com", masked: true }],
  }],
  changed: null, changedNote: "", link: "https://app.payhoa.example/requests/1234",
  refresh: [{ command: "jason sync-catalog --requests", live: true, what: "Reads the requests again" }],
  caveats: ["A stored copy is what jason read then, not the record now."], note: "",
  ...over,
});

const refs = [
  "jason books-check --month 2026-09",
  { label: "Unit 12 ledger" },
  { label: "PayHOA request 1234", address: "payhoa:submission:1234" },
  { label: "Declaration § 7.3", address: "jason://decl/7.3" },
];

describe("Evidence", () => {
  it("keeps plain strings and refs with no address as chips", () => {
    render(<Evidence items={["instrument 2023-000123", "jason calendar"]} label="Read from" />);
    expect(screen.getByText("Read from:")).toBeInTheDocument();
    expect(screen.getByText("instrument 2023-000123").tagName).toBe("CODE");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("makes a ref with an address a disclosure button showing the label, not the address", () => {
    render(<Evidence items={refs} />);
    expect(screen.getByText("Unit 12 ledger").tagName).toBe("CODE");
    const chip = screen.getByRole("button", { name: "PayHOA request 1234" });
    expect(chip).toHaveAttribute("aria-expanded", "false");
    expect(chip).toHaveAttribute("aria-controls");
    expect(screen.queryByText(/payhoa:submission:1234/)).not.toBeInTheDocument();
  });

  it("fetches on open with the address and the approval encoded, and shows the stored source", async () => {
    const f = mockFetch(() => ({ body: answer() }));
    render(<Evidence items={refs} approval="owner-info tags/1" />);
    expect(f).not.toHaveBeenCalled();
    const chip = screen.getByRole("button", { name: "PayHOA request 1234" });
    await userEvent.click(chip);
    expect(chip).toHaveAttribute("aria-expanded", "true");
    expect(f).toHaveBeenCalledWith("/api/evidence?address=payhoa%3Asubmission%3A1234&approval=owner-info%20tags%2F1", expect.anything());
    const panel = await screen.findByRole("group", { name: "PayHOA request 1234" });
    expect(panel.id).toBe(chip.getAttribute("aria-controls"));
    expect(within(panel).getByText("payhoa:submission:1234")).toBeInTheDocument();
    expect(within(panel).getByText("PayHOA request export")).toBeInTheDocument();
    expect(within(panel).getByText("Jane Doe")).toBeInTheDocument();
    const link = within(panel).getByRole("link", { name: /Open the unit.s requests in PayHOA/ });
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
    expect(within(panel).getByText("A stored copy is what jason read then, not the record now.")).toBeInTheDocument();
  });

  it("opens one panel at a time", async () => {
    mockFetch((url) => ({ body: url.includes("decl") ? answer({ address: "jason://decl/7.3", label: "Declaration § 7.3", kind: "citation", link: "" }) : answer() }));
    render(<Evidence items={refs} />);
    const a = screen.getByRole("button", { name: "PayHOA request 1234" });
    const b = screen.getByRole("button", { name: "Declaration § 7.3" });
    await userEvent.click(a);
    await screen.findByRole("group", { name: "PayHOA request 1234" });
    await userEvent.click(b);
    expect(a).toHaveAttribute("aria-expanded", "false");
    expect(b).toHaveAttribute("aria-expanded", "true");
    await screen.findByRole("group", { name: "Declaration § 7.3" });
    expect(screen.getAllByRole("group")).toHaveLength(1);
    await userEvent.click(b);
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the chip", async () => {
    mockFetch(() => ({ body: answer() }));
    render(<Evidence items={refs} />);
    const chip = screen.getByRole("button", { name: "PayHOA request 1234" });
    await userEvent.click(chip);
    const panel = await screen.findByRole("group", { name: "PayHOA request 1234" });
    within(panel).getByRole("button", { name: "Copy" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(chip).toHaveAttribute("aria-expanded", "false");
    expect(chip).toHaveFocus();
  });

  it("opens and closes from the keyboard", async () => {
    mockFetch(() => ({ body: answer() }));
    render(<Evidence items={refs} />);
    const chip = screen.getByRole("button", { name: "PayHOA request 1234" });
    chip.focus();
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("group", { name: "PayHOA request 1234" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(chip).toHaveFocus();
  });

  it("says jason-web did not answer when the fetch fails", async () => {
    mockFetch(() => ({ status: 404, body: { error: "no route /api/evidence" } }));
    render(<Evidence items={refs} />);
    await userEvent.click(screen.getByRole("button", { name: "PayHOA request 1234" }));
    expect(await screen.findByText("jason-web did not answer: no route /api/evidence")).toBeInTheDocument();
  });

  it("announces loading politely", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<Evidence items={refs} />);
    await userEvent.click(screen.getByRole("button", { name: "PayHOA request 1234" }));
    const status = screen.getByText("Reading what jason stored for this address.");
    expect(status.closest("[aria-live='polite']")).not.toBeNull();
  });
});

describe("EvidencePanel", () => {
  const today = new Date("2026-10-03T12:00:00");

  it("renders given data without fetching, with the read date and how long ago", () => {
    const f = mockFetch(() => ({ body: {} }));
    render(<EvidencePanel address="payhoa:submission:1234" data={answer()} today={today} />);
    expect(f).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "PayHOA request 1234" })).toBeInTheDocument();
    expect(screen.getByText(/\(3 days ago\)/)).toBeInTheDocument();
    expect(screen.getByText("2026-09-30 18:38 UTC").tagName).toBe("TIME");
  });

  it("says when the source changed, is unchanged, or cannot tell", () => {
    const { rerender } = render(<EvidencePanel address="a" data={answer({ changed: true, changedNote: "The answer to question 3 differs." })} />);
    const warn = screen.getByText(/Changed since this plan was read\./);
    expect(warn).toHaveClass("notice-warn");
    expect(warn).toHaveTextContent("The answer to question 3 differs.");
    rerender(<EvidencePanel address="a" data={answer({ changed: false })} />);
    expect(screen.getByText("Unchanged since this plan was read.")).toBeInTheDocument();
    expect(screen.queryByText(/Changed since/)).not.toBeInTheDocument();
    rerender(<EvidencePanel address="a" data={answer({ changed: null, changedNote: "jason has no digest from the plan to compare." })} />);
    expect(screen.queryByText(/since this plan was read/)).not.toBeInTheDocument();
    expect(screen.getByText("jason has no digest from the plan to compare.")).toBeInTheDocument();
  });

  it("marks a masked field as masked", () => {
    render(<EvidencePanel address="a" data={answer()} />);
    const email = screen.getByText("Email").nextElementSibling as HTMLElement;
    expect(email).toHaveTextContent("j***@example.com");
    expect(within(email).getByText("masked")).toBeInTheDocument();
    const owner = screen.getByText("Owner").nextElementSibling as HTMLElement;
    expect(within(owner).queryByText("masked")).not.toBeInTheDocument();
  });

  it("recites a citation's words as a quotation, then its citation and caveat", () => {
    const words = "No owner shall keep more than two pets in a unit.";
    render(<EvidencePanel address="jason://decl/7.3" data={answer({
      kind: "citation", label: "Declaration § 7.3", link: "",
      sources: [{ name: "Declaration", readAt: "", digest: "", fields: [], text: words, citation: "Declaration § 7.3", caveat: "jason's consolidated text, not an official restatement.", note: "" }],
    })} />);
    const quote = screen.getByText(words).closest("blockquote");
    expect(quote).not.toBeNull();
    const cite = screen.getByText("Declaration § 7.3", { selector: "cite" });
    expect(quote!.compareDocumentPosition(cite) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("jason's consolidated text, not an official restatement.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows the original's link for a kind other than PayHOA", () => {
    render(<EvidencePanel address="board:12" data={answer({ kind: "board_item", link: "https://example.com/item/12" })} />);
    expect(screen.getByRole("link", { name: /Open the original/ })).toHaveAttribute("href", "https://example.com/item/12");
  });

  it("copies a refresh command and says a live one reads PayHOA, never running it", async () => {
    const f = mockFetch(() => ({ body: {} }));
    const writeText = vi.fn(async () => {});
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(<EvidencePanel address="a" data={answer({
      refresh: [
        { command: "jason sync-catalog --requests", live: true, what: "Reads the requests again", system: "PayHOA" },
        { command: "jason cite jason://decl/7.3", live: false, what: "Recites the stored words" },
      ],
    })} />);
    expect(screen.getByText("jason sync-catalog --requests").tagName).toBe("CODE");
    expect(screen.getByText(/Reads the requests again\. It reads PayHOA; run it in a terminal\./)).toBeInTheDocument();
    expect(screen.getByText(/Recites the stored words\. Run it in a terminal\./)).toBeInTheDocument();
    const [first] = screen.getAllByRole("button", { name: "Copy" });
    await userEvent.click(first);
    expect(writeText).toHaveBeenCalledWith("jason sync-catalog --requests");
    expect(await screen.findByText("Copied the command.")).toBeInTheDocument();
    expect(f).not.toHaveBeenCalled();
  });

  it("shows a miss's note and the command that fills it, never an empty box", () => {
    render(<EvidencePanel address="payhoa:submission:9999" data={answer({
      found: false, label: "PayHOA request 9999", sources: [], link: "", caveats: [],
      note: "No PayHOA request 9999 on disk.", refresh: [{ command: "jason sync-catalog --requests", live: true, what: "Reads the requests" }],
    })} />);
    expect(screen.getByText("No PayHOA request 9999 on disk.")).toBeInTheDocument();
    expect(screen.getByText(/The command that fills it/)).toBeInTheDocument();
    expect(screen.getByText("jason sync-catalog --requests")).toBeInTheDocument();
  });

  it("shows a source's own note", () => {
    render(<EvidencePanel address="a" data={answer({
      sources: [{ name: "PayHOA request export", readAt: "", digest: "", fields: [], text: "", citation: "", caveat: "", note: "The export holds no answers yet." }],
    })} />);
    expect(screen.getByText("The export holds no answers yet.")).toBeInTheDocument();
  });

  it("shows a 404 that carries the contract's miss as a miss", async () => {
    mockFetch(() => ({ status: 404, body: { ...answer({ found: false, sources: [], note: "Nothing stored at this address." }) } }));
    render(<EvidencePanel address="payhoa:submission:1234" />);
    expect(await screen.findByText("Nothing stored at this address.")).toBeInTheDocument();
    expect(screen.queryByText(/did not answer/)).not.toBeInTheDocument();
  });

  it("builds the loader URL, leaving out an empty approval", async () => {
    expect(evidenceUrl("a b&c")).toBe("/api/evidence?address=a%20b%26c");
    const f = mockFetch(() => ({ body: answer() }));
    render(<EvidencePanel address="payhoa:submission:1234" />);
    await waitFor(() => expect(f).toHaveBeenCalledWith("/api/evidence?address=payhoa%3Asubmission%3A1234", expect.anything()));
  });
});

describe("EvidencePanel's read again", () => {
  const refreshable = { system: "PayHOA", what: "Reads this request from PayHOA again" };
  const REFRESH = "/api/evidence/refresh";
  const KEEPER = "Keeper is not signed in; run `jason login` in a terminal, then refresh again.";

  afterEach(() => {
    resetServerSession();
    document.head.querySelector('meta[name="jason-token"]')?.remove();
    localStorage.clear();
  });

  function withToken(token = "tok-9") {
    const meta = document.createElement("meta");
    meta.name = "jason-token";
    meta.content = token;
    document.head.append(meta);
  }

  type Reply = { status?: number; body: unknown };
  /** A server: `/api/session` answers `session`, the refresh answers `post()`, and every other GET the stored answer. */
  function server(post: () => Reply | Promise<Reply>, session: unknown = {}) {
    const json = ({ status = 200, body }: Reply) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    const f = vi.fn(async (url: string, _init?: RequestInit) => {
      if (url === "/api/session") return json({ body: session });
      if (url === REFRESH) return json(await post());
      return json({ body: answer({ refreshable }) });
    });
    vi.stubGlobal("fetch", f);
    const posts = () => f.mock.calls.filter(([url]) => url === REFRESH);
    return { f, posts };
  }

  const fresh = (over: Partial<EvidenceAnswer> = {}): EvidenceAnswer => answer({
    refreshable, changed: true, changedNote: "The mailing address answer differs.",
    sources: [{
      name: "PayHOA request (live)", readAt: "2026-10-03T19:02:00+00:00", digest: "9a0c11e2bb", text: "", citation: "", caveat: "", note: "",
      fields: [{ name: "Owner", value: "Owner B", masked: false }],
    }],
    refreshed: { at: "2026-10-03T19:02:00+00:00", by: "Jane Example", system: "PayHOA" },
    ...over,
  });

  it("shows the button only when the answer is refreshable", () => {
    const { rerender } = render(<EvidencePanel address="a" data={answer()} by="Jane Example" onRefresh={vi.fn()} onClose={() => {}} />);
    expect(screen.queryByRole("button", { name: /Read again/ })).not.toBeInTheDocument();
    rerender(<EvidencePanel address="a" data={answer({ refreshable: null })} by="Jane Example" onRefresh={vi.fn()} onClose={() => {}} />);
    expect(screen.queryByRole("button", { name: /Read again/ })).not.toBeInTheDocument();
    rerender(<EvidencePanel address="a" data={answer({ refreshable })} by="Jane Example" onRefresh={vi.fn()} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: "Read again from PayHOA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("takes its name from the system and says in its title what the read does", () => {
    render(<EvidencePanel address="a" data={answer({ refreshable: { system: "Example Portal", what: "Reads the request again" } })} by="Jane Example" onRefresh={vi.fn()} />);
    const button = screen.getByRole("button", { name: "Read again from Example Portal" });
    expect(button).toHaveAttribute("title", "Reads the request again. Reads Example Portal now, under your name; writes nothing to Example Portal.");
    expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(button).not.toHaveAttribute("aria-disabled");
  });

  it("POSTs the address, the approval, and the person, with the write token", async () => {
    withToken("tok-9");
    const { posts } = server(() => ({ body: fresh() }));
    render(<EvidencePanel address="payhoa:submission:1234" approval="owner-info tags/1" by="Jane Example" />);
    await userEvent.click(await screen.findByRole("button", { name: "Read again from PayHOA" }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [url, init] = posts()[0];
    expect(url).toBe(REFRESH);
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)["X-Jason-Token"]).toBe("tok-9");
    expect(JSON.parse(String(init?.body))).toEqual({ address: "payhoa:submission:1234", approval: "owner-info tags/1", by: "Jane Example" });
  });

  it("spins with aria-busy while the read runs, and a second click sends nothing", async () => {
    withToken();
    let finish: (r: Reply) => void = () => {};
    const { posts } = server(() => new Promise<Reply>((ok) => { finish = ok; }));
    render(<EvidencePanel address="payhoa:submission:1234" by="Jane Example" />);
    const button = await screen.findByRole("button", { name: "Read again from PayHOA" });
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("aria-disabled", "true");
    const status = screen.getByText("Reading from PayHOA…");
    expect(status.closest("[aria-live='polite']")).not.toBeNull();
    await userEvent.click(button);
    await userEvent.click(button);
    await waitFor(() => expect(posts()).toHaveLength(1));
    finish({ body: fresh() });
    await waitFor(() => expect(button).not.toHaveAttribute("aria-busy"));
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(posts()).toHaveLength(1);
  });

  it("replaces the answer in place, keeps the panel open, and keeps focus on the button", async () => {
    withToken();
    server(() => ({ body: fresh() }));
    render(<EvidencePanel address="payhoa:submission:1234" by="Jane Example" onClose={() => {}} />);
    const panel = await screen.findByRole("group", { name: "PayHOA request 1234" });
    expect(await within(panel).findByText("Jane Doe")).toBeInTheDocument();
    const button = within(panel).getByRole("button", { name: "Read again from PayHOA" });
    await userEvent.click(button);
    expect(await within(panel).findByText("Read from PayHOA just now by Jane Example.")).toBeInTheDocument();
    expect(within(panel).getByText("Owner B")).toBeInTheDocument();
    expect(within(panel).queryByText("Jane Doe")).not.toBeInTheDocument();
    expect(within(panel).getByText(/Changed since this plan was read\./)).toHaveTextContent("The mailing address answer differs.");
    expect(within(panel).getByText("2026-10-03 19:02 UTC").tagName).toBe("TIME");
    expect(screen.getByRole("group", { name: "PayHOA request 1234" })).toBe(panel);
    expect(button).toHaveFocus();
  });

  it("says the server's 409 or 403 as it is and keeps the old answer; a 400 says it cannot be read again", async () => {
    withToken();
    let reply: Reply = { status: 409, body: { error: KEEPER } };
    server(() => reply);
    render(<EvidencePanel address="payhoa:submission:1234" by="Jane Example" />);
    const button = await screen.findByRole("button", { name: "Read again from PayHOA" });
    expect(await screen.findByText("Jane Doe")).toBeInTheDocument();
    await userEvent.click(button);
    const message = await screen.findByText(KEEPER);
    expect(message).toHaveClass("notice-error");
    expect(message.closest("[aria-live='polite']")).not.toBeNull();
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.queryByText(/just now/)).not.toBeInTheDocument();
    reply = { status: 403, body: { error: "Writes are refused while an admin views the console as someone else." } };
    await userEvent.click(button);
    expect(await screen.findByText("Writes are refused while an admin views the console as someone else.")).toHaveClass("notice-error");
    reply = { status: 400, body: { error: "not a refreshable kind" } };
    await userEvent.click(button);
    expect(await screen.findByText("This evidence can't be read again from the page.")).toHaveClass("notice-error");
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(button).toHaveFocus();
  });

  it("is disabled with the reason when no one is named, and sends nothing", async () => {
    withToken();
    const { posts } = server(() => ({ body: fresh() }), { signedIn: null });
    render(<EvidencePanel address="payhoa:submission:1234" />);
    const button = await screen.findByRole("button", { name: "Read again from PayHOA" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    const why = screen.getByText("Sign in or pick your name to read it again.");
    expect(button).toHaveAccessibleDescription("Sign in or pick your name to read it again.");
    expect(why).toHaveClass("visually-hidden");
    await userEvent.click(button);
    expect(why).not.toHaveClass("visually-hidden");
    expect(why).toHaveClass("muted");
    expect(posts()).toHaveLength(0);
  });

  it("reads under the signed-in name, or the name picked in this browser", async () => {
    withToken();
    const { posts } = server(() => ({ body: fresh() }), { signedIn: { name: "Casey Sample" } });
    const { unmount } = render(<EvidencePanel address="payhoa:submission:1234" />);
    const button = await screen.findByRole("button", { name: "Read again from PayHOA" });
    await waitFor(() => expect(button).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(button);
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(JSON.parse(String(posts()[0][1]?.body)).by).toBe("Casey Sample");
    unmount();
    resetServerSession();
    localStorage.setItem(SESSION_KEY, "Jordan Example");
    const second = server(() => ({ body: fresh() }), {});
    render(<EvidencePanel address="payhoa:submission:1234" />);
    await userEvent.click(await screen.findByRole("button", { name: "Read again from PayHOA" }));
    await waitFor(() => expect(second.posts()).toHaveLength(1));
    expect(JSON.parse(String(second.posts()[0][1]?.body)).by).toBe("Jordan Example");
  });

  it("never reads again on open or on focus", async () => {
    withToken();
    const { f, posts } = server(() => ({ body: fresh() }));
    render(<Evidence items={refs} by="Jane Example" />);
    await userEvent.click(screen.getByRole("button", { name: "PayHOA request 1234" }));
    const button = await screen.findByRole("button", { name: "Read again from PayHOA" });
    button.focus();
    await userEvent.tab();
    await userEvent.tab({ shift: true });
    expect(button).toHaveFocus();
    expect(f).toHaveBeenCalled();
    expect(posts()).toHaveLength(0);
  });

  it("reads a data panel again only through onRefresh, and shows a forced reading state", async () => {
    const onRefresh = vi.fn(async () => fresh());
    const f = mockFetch(() => ({ body: {} }));
    const { rerender } = render(<EvidencePanel address="a" approval="p/1" data={answer({ refreshable })} by="Jane Example" onRefresh={onRefresh} />);
    await userEvent.click(screen.getByRole("button", { name: "Read again from PayHOA" }));
    expect(onRefresh).toHaveBeenCalledWith({ address: "a", approval: "p/1", by: "Jane Example" });
    expect(await screen.findByText("Owner B")).toBeInTheDocument();
    rerender(<EvidencePanel address="a" data={answer({ refreshable })} by="Jane Example" refreshing />);
    expect(screen.getByRole("button", { name: "Read again from PayHOA" })).toHaveAttribute("aria-busy", "true");
    expect(f).not.toHaveBeenCalled();
  });
});

describe("Read every request again", () => {
  const ALL = "/api/evidence/refresh-all";
  const NAME = "Read every request again";
  const planned = () => structuredClone(plannedJson) as unknown as Approval;
  const payhoaRefs = [
    { label: "Civil Code 4041", address: "CIV 4041" },
    { label: "PayHOA request 501", address: "payhoa:submission:501" },
    { label: "PayHOA request 501", address: "payhoa:submission:501" },
    { label: "PayHOA request 502", address: "payhoa:submission:502" },
  ];

  afterEach(() => {
    resetServerSession();
    document.head.querySelector('meta[name="jason-token"]')?.remove();
    localStorage.clear();
  });

  function withToken(token = "tok-7") {
    const meta = document.createElement("meta");
    meta.name = "jason-token";
    meta.content = token;
    document.head.append(meta);
  }

  type Reply = { status?: number; body: unknown };
  /** A server: `/api/session` answers `session`, the batch answers `post()`, and `/api/evidence` answers `get(n)` on
   * its n-th read (from 1). */
  function server(post: () => Reply | Promise<Reply>, session: unknown = {}, get: (n: number) => EvidenceAnswer = () => answer()) {
    const json = ({ status = 200, body }: Reply) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    let reads = 0;
    const f = vi.fn(async (url: string, _init?: RequestInit) => {
      if (url === "/api/session") return json({ body: session });
      if (url === ALL) return json(await post());
      if (url.startsWith("/api/evidence?")) return json({ body: get(++reads) });
      return json({ status: 404, body: { error: `no route ${url}` } });
    });
    vi.stubGlobal("fetch", f);
    const posts = () => f.mock.calls.filter(([url]) => url === ALL);
    const gets = () => f.mock.calls.filter(([url]) => String(url).startsWith("/api/evidence?"));
    return { f, posts, gets };
  }

  const summary = (over: Partial<EvidenceRefreshAll> = {}): EvidenceRefreshAll => ({
    approval: "apr-1", by: "Jane Example", at: "2026-10-03T19:02:00+00:00",
    refreshed: ["payhoa:submission:501", "payhoa:submission:502", "payhoa:submission:503", "payhoa:submission:504"],
    failed: [], skipped: 3, ...over,
  });

  it("is offered only when the plan names a PayHOA request", () => {
    const { rerender } = render(<RefreshAllEvidence approval="apr-1" refs={[{ label: "Civil Code 4041", address: "CIV 4041" }, "jason calendar", { label: "no address" }]} by="Jane Example" />);
    expect(screen.queryByRole("button", { name: NAME })).not.toBeInTheDocument();
    rerender(<RefreshAllEvidence approval="apr-1" refs={payhoaRefs} by="Jane Example" />);
    const button = screen.getByRole("button", { name: NAME });
    expect(button).toHaveAttribute("title", "Reads each request in this plan from PayHOA now, under your name; writes nothing to PayHOA.");
    expect(button.querySelector("svg.evidence-reread-icon")).toHaveAttribute("aria-hidden", "true");
    expect(button).not.toHaveAttribute("aria-disabled");
  });

  it("sits in the plan's header beside Read from, and nothing is read on load", async () => {
    withToken();
    const { f } = server(() => ({ body: summary() }));
    render(<PlanReview approval={planned()} me="Jane Example" now="2026-10-03T19:00:00+00:00" />);
    const header = screen.getByRole("heading", { level: 2 }).closest("header")!;
    expect(within(header).getByText("Read from:")).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: NAME })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 20));
    expect(f).not.toHaveBeenCalled();
  });

  it("POSTs the approval and the person with the write token, busy until it answers, and a second click sends nothing", async () => {
    withToken("tok-7");
    let finish: (r: Reply) => void = () => {};
    const { posts } = server(() => new Promise<Reply>((ok) => { finish = ok; }));
    render(<RefreshAllEvidence approval="apr-1" refs={payhoaRefs} by="Jane Example" />);
    const button = screen.getByRole("button", { name: NAME });
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("aria-disabled", "true");
    const status = screen.getByText("Reading 2 requests from PayHOA…");
    expect(status.closest("[aria-live='polite']")).not.toBeNull();
    await userEvent.click(button);
    await userEvent.click(button);
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [url, init] = posts()[0];
    expect(url).toBe(ALL);
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)["X-Jason-Token"]).toBe("tok-7");
    expect(JSON.parse(String(init?.body))).toEqual({ approval: "apr-1", by: "Jane Example" });
    finish({ body: summary() });
    expect(await screen.findByText("Read 4 requests from PayHOA just now by Jane Example.")).toBeInTheDocument();
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).toHaveFocus();
    expect(posts()).toHaveLength(1);
  });

  it("says what could not be read beside what was", async () => {
    withToken();
    server(() => ({ body: summary({ refreshed: ["payhoa:submission:501", "payhoa:submission:502"], failed: [{ address: "payhoa:submission:503", error: "PayHOA could not be read: HTTPError: 502" }] }) }));
    render(<RefreshAllEvidence approval="apr-1" refs={payhoaRefs} by="Jane Example" />);
    await userEvent.click(screen.getByRole("button", { name: NAME }));
    const said = await screen.findByText("Read 2 requests from PayHOA just now by Jane Example. 1 could not be read: payhoa:submission:503: PayHOA could not be read: HTTPError: 502.");
    expect(said.closest("[aria-live='polite']")).not.toBeNull();
  });

  it("says the server's 409 or 403 as it is, in the error tone", async () => {
    withToken();
    const KEEPER = "Keeper is not signed in; run `jason login` in a terminal, then refresh again.";
    let reply: Reply = { status: 409, body: { error: KEEPER } };
    const onDone = vi.fn();
    server(() => reply);
    render(<RefreshAllEvidence approval="apr-1" refs={payhoaRefs} by="Jane Example" onDone={onDone} />);
    const button = screen.getByRole("button", { name: NAME });
    await userEvent.click(button);
    expect(await screen.findByText(KEEPER)).toHaveClass("notice-error");
    reply = { status: 403, body: { error: "viewing as A Director (admin view): writes are refused." } };
    await userEvent.click(button);
    expect(await screen.findByText("viewing as A Director (admin view): writes are refused.")).toHaveClass("notice-error");
    expect(onDone).not.toHaveBeenCalled();
    expect(button).toHaveFocus();
  });

  it("is disabled with the reason shown when no one is named, and sends nothing", async () => {
    withToken();
    const { posts } = server(() => ({ body: summary() }), { signedIn: null });
    render(<RefreshAllEvidence approval="apr-1" refs={payhoaRefs} />);
    const button = screen.getByRole("button", { name: NAME });
    expect(button).toHaveAttribute("aria-disabled", "true");
    const why = screen.getByText("Sign in or pick your name to read them again.");
    expect(why).not.toHaveClass("visually-hidden");
    expect(button).toHaveAccessibleDescription("Sign in or pick your name to read them again.");
    await userEvent.click(button);
    expect(posts()).toHaveLength(0);
  });

  it("reads under the session's name when none is passed", async () => {
    withToken();
    const { posts } = server(() => ({ body: summary({ by: "Casey Sample" }) }), { signedIn: { name: "Casey Sample" } });
    render(<RefreshAllEvidence approval="apr-1" refs={payhoaRefs} />);
    const button = screen.getByRole("button", { name: NAME });
    await waitFor(() => expect(button).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(button);
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(JSON.parse(String(posts()[0][1]?.body)).by).toBe("Casey Sample");
  });

  it("has every open panel in the plan fetch its answer again after the batch, in place", async () => {
    withToken();
    const read = (n: number) => answer({
      address: "payhoa:submission:502", label: "PayHOA request 502",
      changed: n > 1 ? true : null, changedNote: n > 1 ? "The last read from PayHOA differs from the plan's read: status complete." : "",
      sources: [{
        name: "Last read from PayHOA", readAt: n > 1 ? "2026-10-03T19:02:00+00:00" : "2026-09-30T18:38:00+00:00", digest: "", text: "", citation: "", caveat: "", note: "",
        fields: [{ name: "Status", value: n > 1 ? "complete" : "pending", masked: false }],
      }],
    });
    const { posts, gets } = server(() => ({ body: summary() }), {}, read);
    render(<PlanReview approval={planned()} me="Jane Example" now="2026-10-03T19:00:00+00:00" />);
    await userEvent.click(screen.getAllByRole("button", { name: "PayHOA request 502" })[0]);
    const panel = await screen.findByRole("group", { name: "PayHOA request 502" });
    expect(await within(panel).findByText("pending")).toBeInTheDocument();
    expect(gets()).toHaveLength(1);
    const button = screen.getByRole("button", { name: NAME });
    await userEvent.click(button);
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(JSON.parse(String(posts()[0][1]?.body))).toEqual({ approval: "apr-20261003T183801-4f5b", by: "Jane Example" });
    expect(await within(panel).findByText("complete")).toBeInTheDocument();
    expect(gets()).toHaveLength(2);
    expect(within(panel).getByText("2026-10-03 19:02 UTC").tagName).toBe("TIME");
    expect(within(panel).getByText(/Changed since this plan was read\./)).toHaveTextContent("status complete");
    expect(screen.getByRole("group", { name: "PayHOA request 502" })).toBe(panel);
    expect(button).toHaveFocus();
  });
});
