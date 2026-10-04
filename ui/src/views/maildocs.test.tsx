import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DOC_WORDS, type DocRef } from "../components";
import { resetServerSession } from "../lib/api";
import { InboxView } from "./InboxView";
import { InsuranceRenewalsView } from "./InsuranceRenewalsView";
import { InsuranceView, heldOf, scansOf } from "./InsuranceView";

/* The mail group's screens on `Doc` (docs/console/doc-component.md): the Inbox's letters and pending requests as chips,
 * insurance notices and claim letters as rows. Made-up references; nothing here names a real document. */

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const letter: DocRef = { address: "file:mail/9101/contents.pdf", document: "pdf", name: "Letter from Example County, 2099-09-30", kind: "pdf",
  level: "P2", source: "Scan", size: 50_000, thumb: true };
const request: DocRef = { address: "payhoa:submission:42", document: "submission", name: "Example Form (request 42)", kind: "submission",
  level: "P2", source: "PayHOA", original: { url: "https://app.example.test/units/1/requests", label: "Open in PayHOA" } };
const notice: DocRef = { address: "file:mail/9201/contents.pdf", document: "pdf", name: "Letter from Example Insurer, 2099-08-01", kind: "pdf",
  level: "P2", source: "Scan", size: 30_000 };
const claim: DocRef = { address: "file:mail/9202/contents.pdf", document: "pdf", name: "Letter from Example Adjuster, 2099-08-15", kind: "pdf",
  level: "P2", source: "Scan", size: 20_000 };

const inbox = { found: true, counts: { threadsAwaitingUs: 1, requestsPending: 1, lettersToAct: 1 }, caveats: ["Jason answers, pays, and files nothing."],
  threadsAwaitingUs: [{ last: "2099-10-01", ageDays: 2, who: "a vendor", subject: "Invoice 42", topics: ["invoice"], link: "https://mail.google.com/mail/u/0/#all/abc123", likelyNeedsResponse: true, replyRate: 0.8 }],
  requestsPending: [{ id: 42, form: "Example Form", unit: "123 MAIN ST #1", created: "2099-09-01", status: "Pending", doc: request }],
  deadlines: [], insurance: [], mailNotScanned: [], lienNotices: [],
  lettersToAct: [{ received: "2099-09-30", from: "Example County", kind: "tax", deadlines: ["2099-12-10"], mailId: "9101", scan: letter }] };

const base = { priorNumbers: [], program: "", agent: "Agent", terms: [], nextTermPayments: [], letters: [], findings: [] };
const policy = { ...base, kind: "master", building: null, number: "EX-1", carrier: "Example Carrier", standing: "in term", termEnd: "2099-12-01",
  notices: [{ kind: "insurance", received: "2099-08-01", mailId: "9201", scan: notice }, { kind: "insurance", received: "2099-08-15", mailId: "9202", scan: claim }] };
const flood = { ...base, kind: "flood", building: 5, number: "EX-5", carrier: "Example Flood", standing: "in term", termEnd: "2099-06-01",
  notices: [{ kind: "insurance", received: "2099-08-01", mailId: "9201", scan: notice }] };            // one letter printing both numbers
const insurance = { found: true, asOf: "2099-10-03", policies: [policy, flood], unplacedFloodPayments: [],
  claims: [{ received: "2099-08-15", claimNumber: "CL-12345", dateOfLoss: "1/2/2099", mailId: "9202", scan: claim }], caveats: ["Jason buys, renews, and cancels nothing."] };
const renewals = { found: true, asOf: "2099-10-03", today: "2099-10-03", windowDays: 90, decisions: ["renew as quoted"], caveats: [],
  policies: [{ ...policy, key: "EX-1", renewal: null, daysToTermEnd: 59, renewalWindow: true, memberNoticeNeeded: false }] };

const IN = { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true, start: "/auth/google" } };
const OUT = { token: "t", signIn: { configured: true, start: "/auth/google" } };
const pdfView = { kind: "pdf", name: "contents.pdf", readAt: "", url: "/api/evidence/document/tok", expires: "", caveats: [] };

function serve(session: object, view: { status: number; body: object } = { status: 200, body: pdfView }) {
  const posts: [string, unknown][] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") posts.push([url, JSON.parse(String(init.body))]);
    const [status, body] = url === "/api/evidence/view" ? [view.status, view.body]
      : url.startsWith("/api/session") ? [200, session]
      : url.startsWith("/api/open-items") ? [200, inbox]
      : url.startsWith("/api/insurance-renewals") ? [200, renewals]
      : url.startsWith("/api/insurance") ? [200, insurance]
      : [404, { error: `no route ${url}` }];
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }));
  return posts;
}

function clean(container: HTMLElement) {
  const html = container.innerHTML;
  expect(html).not.toContain("/api/file");
  expect(html).not.toMatch(/(?<![A-Za-z])[A-Za-z]:[\\/]|\/home\/|\/Users\//);      // a drive letter, not "https:/"
  for (const frame of Array.from(container.querySelectorAll("iframe"))) expect(frame.getAttribute("src") ?? "").toMatch(/^\/api\/evidence\/document\//);
}

describe("InboxView: letters and requests (Doc chips)", () => {
  it("a letter's chip opens its scan as one logged view", async () => {
    const posts = serve(IN);
    const { container } = render(<InboxView />);
    await screen.findByText("Invoice 42");
    await userEvent.click(screen.getByRole("tab", { name: "Letters to act on (1)" }));
    const chip = screen.getByRole("button", { name: `Open ${letter.name}` });
    expect(chip).toHaveAccessibleDescription("PDF");
    expect(posts).toEqual([]);
    await userEvent.click(chip);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: letter.address, document: "pdf", by: "A Manager" }]]));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    clean(container);
  });

  it("a pending request's chip is its PayHOA submission, the same evidence the plans use", async () => {
    const posts = serve(IN);
    render(<InboxView />);
    await screen.findByText("Invoice 42");
    await userEvent.click(screen.getByRole("tab", { name: "Requests pending (1)" }));
    const chip = screen.getByRole("button", { name: `Open ${request.name}` });
    expect(chip).toHaveAccessibleDescription("Form submission");
    await userEvent.click(chip);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: "payhoa:submission:42", document: "submission", by: "A Manager" }]]));
  });

  it("signed out: the chip says to sign in and posts nothing", async () => {
    const posts = serve(OUT);
    render(<InboxView />);
    await screen.findByText("Invoice 42");
    await userEvent.click(screen.getByRole("tab", { name: "Letters to act on (1)" }));
    await userEvent.click(screen.getByRole("button", { name: `Open ${letter.name}` }));
    expect(await screen.findByText(new RegExp(DOC_WORDS.signedOut))).toBeInTheDocument();
    expect(posts).toEqual([]);
  });

  it("not allowed: the server's reason, in words", async () => {
    serve(IN, { status: 403, body: { error: "The treasurer's office doesn't open this letter." } });
    render(<InboxView />);
    await screen.findByText("Invoice 42");
    await userEvent.click(screen.getByRole("tab", { name: "Letters to act on (1)" }));
    await userEvent.click(screen.getByRole("button", { name: `Open ${letter.name}` }));
    expect(await screen.findByText(/The treasurer's office doesn't open this letter\./)).toBeInTheDocument();
  });

  it("a Gmail thread stays a link, said as Open in Gmail; the subject is text", async () => {
    serve(IN);
    const { container } = render(<InboxView />);
    const link = await screen.findByRole("link", { name: "Open in Gmail: Invoice 42 (opens in a new tab)" });
    expect(link).toHaveTextContent("Open in Gmail");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("Invoice 42").closest("a")).toBeNull();
    clean(container);
  });
});

describe("InsuranceView: notices and claim letters (Doc rows)", () => {
  it("lists each notice's scan once and each claim letter, as rows", async () => {
    serve(IN);
    const { container } = render(<InsuranceView />);
    const notices = await screen.findByRole("region", { name: "Notices in the mail" });
    expect(within(notices).getAllByRole("button", { name: /^View / }).map((b) => b.getAttribute("aria-label"))).toEqual([`View ${notice.name}`, `View ${claim.name}`]);
    const claims = screen.getByRole("region", { name: "Claim letters" });
    expect(within(claims).getByRole("button", { name: `View ${claim.name}` })).toBeInTheDocument();
    expect(within(claims).getByText("Scan")).toBeInTheDocument();
    clean(container);
  });

  it("View posts one logged view", async () => {
    const posts = serve(IN);
    render(<InsuranceView />);
    const claims = await screen.findByRole("region", { name: "Claim letters" });
    const view = within(claims).getByRole("button", { name: `View ${claim.name}` });
    await waitFor(() => expect(view).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(view);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: claim.address, document: "pdf", by: "A Manager" }]]));
  });

  it("signed out: View is off and says why", async () => {
    const posts = serve(OUT);
    render(<InsuranceView />);
    const claims = await screen.findByRole("region", { name: "Claim letters" });
    expect(await within(claims).findByText("Sign in with Google to view it.")).toBeInTheDocument();
    expect(within(claims).getByRole("button", { name: `View ${claim.name}` })).toHaveAttribute("aria-disabled", "true");
    expect(posts).toEqual([]);
  });

  it("not allowed: the server's reason, in words", async () => {
    serve(IN, { status: 403, body: { error: "The treasurer's office doesn't open this letter." } });
    render(<InsuranceView />);
    const claims = await screen.findByRole("region", { name: "Claim letters" });
    const view = within(claims).getByRole("button", { name: `View ${claim.name}` });
    await waitFor(() => expect(view).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(view);
    expect(await screen.findByText(/The treasurer's office doesn't open this letter\./)).toBeInTheDocument();
  });

  it("scansOf keeps each scan once, in order, and skips a letter without one", () => {
    expect(scansOf([{ scan: notice }, { scan: null }, { scan: claim }, { scan: notice }, {}])).toEqual([notice, claim]);
  });

  it("a letter that holds a credential is said as held, never listed as a document", async () => {
    const HELD = "Held: this letter holds a credential; it opens in no screen.";
    const held = { kind: "insurance", received: "2099-08-20", mailId: "9203", scan: null, held: HELD };
    expect(heldOf([held, { ...held }, { scan: notice, mailId: "9201" }])).toEqual([held]);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(
      url.startsWith("/api/session") ? IN : { ...insurance, policies: [{ ...policy, notices: [...policy.notices, held] }] }), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<InsuranceView />);
    const notices = await screen.findByRole("region", { name: "Notices in the mail" });
    expect(within(notices).getAllByRole("button", { name: /^View / })).toHaveLength(2);
    expect(screen.getByText(`2099-08-20: ${HELD}`)).toBeInTheDocument();
  });
});

describe("Insurance in the owner view: the policy summary, not the association's mail", () => {
  it("InsuranceView leaves out the letters, the notices, and the claims entirely", async () => {
    serve(IN);
    const { container } = render(<InsuranceView audience="owner" />);
    expect(await screen.findByText("Policies as of 2099-10-03")).toBeInTheDocument();
    expect(screen.getByText("Example Carrier")).toBeInTheDocument();                      // the policy summary stays
    expect(screen.queryByRole("region", { name: "Notices in the mail" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Claim letters" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Claims the mail acknowledges/)).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Letters/ })).not.toBeInTheDocument();
    expect(screen.queryByText(notice.name)).not.toBeInTheDocument();
    expect(screen.queryByText("CL-12345")).not.toBeInTheDocument();
    clean(container);
  });

  it("the board view keeps them", async () => {
    serve(IN);
    render(<InsuranceView audience="board" />);
    expect(await screen.findByRole("region", { name: "Notices in the mail" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Letters/ })).toBeInTheDocument();
  });

  it("InsuranceRenewalsView shows an opened policy without its notices", async () => {
    serve(IN);
    render(<InsuranceRenewalsView audience="owner" />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(screen.getByText("On the record")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Notices in the mail" })).not.toBeInTheDocument();
    expect(screen.queryByText(notice.name)).not.toBeInTheDocument();
  });
});

describe("InsuranceRenewalsView: the opened policy's notices", () => {
  it("shows the notices as rows on the record, and View posts", async () => {
    const posts = serve(IN);
    const { container } = render(<InsuranceRenewalsView />);
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    const notices = screen.getByRole("region", { name: "Notices in the mail" });
    const view = within(notices).getByRole("button", { name: `View ${notice.name}` });
    await waitFor(() => expect(view).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(view);
    await waitFor(() => expect(posts).toEqual([["/api/evidence/view", { address: notice.address, document: "pdf", by: "A Manager" }]]));
    clean(container);
  });
});
