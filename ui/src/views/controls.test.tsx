import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findScreen, GROUPS, SCREENS } from "../App";
import { resetServerSession } from "../lib/api";
import {
  CONTRACT_AUTH, COUNTS, DELIVERY_CLASS, EMPTY_PAGE, MANAGER_LIMIT, MONTHLY_REVIEW, PAGE, PAYMENT_SIGNERS, PROPOSED_ANSWER, RESERVE, one,
} from "../lib/controls.fixtures";
import owned from "../ownerScreens.json";
import { ControlsView } from "./ControlsView";

interface Call { url: string; method: string; body?: unknown }
type Answer = { status?: number; body: unknown };
interface Served {
  list?: Answer[];
  /** One answer for a card, or a sequence (each read pops the next; the last repeats). */
  cards?: Record<string, Answer | Answer[]>;
  writes?: { status: number; body: unknown }[];
  session?: Record<string, unknown>;
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** A made-up server: the list (each read pops the next answer; the last repeats), the cards by key, the write, and the session. */
function serve(s: Served = {}) {
  const calls: Call[] = [];
  const list = [...(s.list ?? [{ body: PAGE }])];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const method = init?.method ?? "GET";
    if (u.startsWith("/api/session"))
      return json(200, { token: "t", header: "X-Jason-Token", signedIn: { name: "A. Secretary", role: "secretary" }, ...(s.session ?? {}) });
    if (method === "POST") {
      calls.push({ url: u, method, body: JSON.parse(String(init?.body)) });
      const w = (s.writes ?? []).shift() ?? { status: 200, body: PROPOSED_ANSWER };
      return json(w.status, w.body);
    }
    calls.push({ url: u, method });
    if (u.startsWith("/api/controls")) {
      const next = list.length > 1 ? list.shift()! : list[0];
      return json(next.status ?? 200, next.body);
    }
    if (u.startsWith("/api/control?key=")) {
      const key = decodeURIComponent(u.split("key=")[1]);
      const got = s.cards?.[key];
      const c = Array.isArray(got) ? (got.length > 1 ? got.shift() : got[0]) : got;
      return c ? json(c.status ?? 200, c.body) : json(200, { found: false, key, note: `no control ${key}` });
    }
    return json(404, { error: "not here" });
  }));
  return calls;
}

beforeEach(() => { resetServerSession(); window.location.hash = ""; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

const list = async () => {
  window.location.hash = "#/controls";
  render(<ControlsView />);
  await screen.findByRole("heading", { level: 2, name: "Money" });
};
const card = async (key: string) => {
  window.location.hash = `#/controls?key=${key}`;
  render(<ControlsView />);
  await screen.findByRole("heading", { level: 2, name: /The provision/ });
};
const rowOf = (key: string) => document.querySelector<HTMLElement>(`li.control-row[data-key="${key}"]`)!;
const head = () => document.querySelector<HTMLElement>(".screen-head")!;
const cardEl = () => document.querySelector<HTMLElement>(".control-card")!;

describe("Controls, the list", () => {
  it("groups the controls by family under the loader's heading counts, and draws no empty family", async () => {
    serve();
    await list();
    expect(screen.getByRole("heading", { level: 1, name: "Controls" })).toBeInTheDocument();
    expect(screen.getByText("jason suggests; the board adopts.")).toBeInTheDocument();
    expect(screen.getByText(PAGE.heading + ".")).toBeInTheDocument();
    const families = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(families).toEqual(["Money", "Contracts", "Reviews", "Notices", "Onboarding"]);       // no Meetings: it holds nothing
    const money = screen.getByRole("list", { name: "Money controls" });
    const titles = within(money).getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(["Payment signers", "Reserve withdrawals", "Manager spending limit", "Payment countersign", "Example Bylaws, 99.9(c)"]);
    expect(COUNTS.adopted).toBe(4);
  });

  it("links each row's title to its card at #/controls?key=KEY", async () => {
    serve();
    await list();
    expect(screen.getByRole("link", { name: "Payment signers" })).toHaveAttribute("href", "#/controls?key=payment-signers");
    expect(within(rowOf("payment-signers")).getByText("Example Bylaws, 99.9")).toBeInTheDocument();
    expect(within(rowOf("payment-signers")).getByText(/second signer above/)).toBeInTheDocument();
  });

  it("says each state in a word and a glyph, and tells 'takes effect DATE' from 'in force, the roster cannot satisfy it'", async () => {
    serve();
    await list();
    const inForce = rowOf("payment-signers");
    expect(inForce).toHaveTextContent("adopted, in force");
    expect(inForce.querySelector('[data-glyph="shield-check"]')).not.toBeNull();

    const ahead = rowOf("delivery-class");
    expect(ahead).toHaveTextContent("adopted, takes effect 2099-11-14");
    expect(ahead.querySelector('[data-glyph="calendar-clock"]')).not.toBeNull();
    expect(ahead).not.toHaveTextContent(/roster cannot satisfy/);
    expect(ahead).not.toHaveTextContent(/adopted, in force/);

    const lacking = rowOf("monthly-review");
    expect(lacking).toHaveTextContent("in force, the roster cannot satisfy it");
    expect(lacking.querySelector('[data-glyph="user-x"]')).not.toBeNull();
    expect(lacking).not.toHaveTextContent(/takes effect/);
    expect(lacking.getAttribute("data-standing")).not.toBe(ahead.getAttribute("data-standing"));

    expect(rowOf("manager-limit")).toHaveTextContent("declined");
    expect(rowOf("manager-limit")).toHaveTextContent("May be asked again after 2100-02-01 (the board's date)");
    expect(rowOf("manager-limit").querySelector('[data-glyph="circle-x"]')).not.toBeNull();
    expect(rowOf("recorder").querySelector('[data-glyph="circle-pause"]')).not.toBeNull();
    expect(rowOf("payment-countersign").querySelector('[data-glyph="archive"]')).not.toBeNull();
    expect(rowOf("contract-term")).toHaveTextContent("proposed to the board");
    expect(within(rowOf("contract-term")).getByRole("link", { name: "control-contract-term" })).toHaveAttribute("href", "#/actions?item=control-contract-term");
  });

  it("never says a suggestion, a proposal, a declined, deferred, or retired control is in force", async () => {
    serve();
    await list();
    for (const key of ["reserve-withdrawals", "second-person", "contract-term", "manager-limit", "recorder", "payment-countersign"])
      expect(rowOf(key).textContent).not.toMatch(/in force/i);
  });

  it("offers Propose only on a suggestion, and shows a provision jason cannot read as a question with its words", async () => {
    serve();
    await list();
    const proposes = screen.getAllByRole("button", { name: /^Propose .* to the board$/ });
    expect(proposes.map((b) => b.textContent)).toEqual(["Propose Reserve withdrawals to the board", "Propose Second person, other kinds to the board"]);
    const q = document.querySelector<HTMLElement>("li[data-kind='question']")!;
    expect(q).toHaveTextContent("question for the board or counsel");
    expect(q).toHaveTextContent("No suggestion: it reads two ways about who may sign for the reserve");
    expect(q.querySelector("figure.recitation blockquote")).toHaveTextContent("The reserve may be drawn on the signature of the officer");
    expect(within(q).queryByRole("button")).toBeNull();
  });

  it("keeps the headings in order: one h1, then h2 groups, then h3 rows", async () => {
    serve();
    await list();
    const levels = screen.getAllByRole("heading").map((h) => Number(h.tagName.slice(1)));
    expect(levels[0]).toBe(1);
    levels.slice(1).forEach((n, i) => expect(n).toBeLessThanOrEqual(levels[i] + 1));
    expect(levels.filter((n) => n === 1)).toHaveLength(1);
  });

  it("filters by family and state by asking the loader", async () => {
    const calls = serve();
    const user = userEvent.setup();
    await list();
    await user.selectOptions(screen.getByLabelText(/Family/), "money");
    await waitFor(() => expect(calls.some((c) => c.url === "/api/controls?family=money")).toBe(true));
    await user.selectOptions(screen.getByLabelText(/State/), "suggested");
    await waitFor(() => expect(calls.some((c) => c.url === "/api/controls?family=money&state=suggested")).toBe(true));
  });

  it("says 'jason has not read your governing documents' with the Onboarding link when nothing is read", async () => {
    serve({ list: [{ body: EMPTY_PAGE }] });
    window.location.hash = "#/controls";
    render(<ControlsView />);
    expect(await screen.findByText(/jason has not read your governing documents\. Ingest them from Onboarding\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Onboarding" })).toHaveAttribute("href", "#/onboarding");
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("says so with the reason when the loader fails, and shows nothing as adopted", async () => {
    serve({ list: [{ status: 500, body: { error: "the control store is unreadable" } }] });
    window.location.hash = "#/controls";
    render(<ControlsView />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The controls could not be read: the control store is unreadable. Nothing is shown as adopted.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText(/Payment signers/)).toBeNull();
  });

  it("shows a refusal in the server's own sentence (403), and a sign-in link for a 401", async () => {
    const sentence = "Controls are open to the board's offices and the manager; your office does not open them.";
    serve({ list: [{ status: 403, body: { error: sentence } }] });
    window.location.hash = "#/controls";
    render(<ControlsView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(sentence);
    expect(screen.queryByRole("link", { name: /Sign in/ })).toBeNull();
    cleanup();

    resetServerSession();
    serve({ list: [{ status: 401, body: { error: "Sign in to read the controls.", signIn: "/auth/google" } }] });
    render(<ControlsView />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Sign in to read the controls.");
    expect(within(alert).getByRole("link", { name: "Sign in with Google" }).getAttribute("href")).toMatch(/^\/auth\/google/);
  });

  it("puts a suggestion before the board only through Confirm, with {act: 'propose'} and nothing else", async () => {
    const proposed = { ...PAGE, families: PAGE.families.map((g) => ({ ...g, controls: g.controls.map((c) => (c.key === "reserve-withdrawals" ? PROPOSED_ANSWER.control : c)) })) };
    const calls = serve({ list: [{ body: PAGE }, { body: proposed }] });
    const user = userEvent.setup();
    await list();
    await user.click(screen.getByRole("button", { name: "Propose Reserve withdrawals to the board" }));
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);                          // the first click writes nothing
    const group = screen.getByRole("group", { name: "Propose" });
    await waitFor(() => expect(group).toHaveTextContent("as A. Secretary"));
    expect(group).toHaveTextContent("control-reserve-withdrawals");
    expect(group).toHaveTextContent("It adopts nothing and changes no rule");
    await user.click(within(group).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.url).toBe("/api/write/controls/reserve-withdrawals");
    expect(post.body).toEqual({ act: "propose" });
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Put before the board: control-reserve-withdrawals, as A. Secretary");
    expect(status).toHaveTextContent("It adopts nothing");
    await waitFor(() => expect(rowOf("reserve-withdrawals")).toHaveTextContent("proposed to the board"));      // the list read again
    expect(within(rowOf("reserve-withdrawals")).queryByRole("button")).toBeNull();
  });

  it("shows the server's sentence when a proposal is refused, and nothing changes", async () => {
    serve({ writes: [{ status: 400, body: { error: "reserve-withdrawals is already adopted; only a suggestion is put before the board" } }] });
    const user = userEvent.setup();
    await list();
    await user.click(screen.getByRole("button", { name: "Propose Reserve withdrawals to the board" }));
    await user.click(within(screen.getByRole("group", { name: "Propose" })).getByRole("button", { name: "Yes, do it" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("only a suggestion is put before the board");
    expect(rowOf("reserve-withdrawals")).toHaveTextContent("suggested");
  });

  it("replaces Propose with the admin-view sentence while an administrator views as someone else", async () => {
    serve({ session: { acting: { name: "A. Secretary", role: "secretary" } } });
    await list();
    await waitFor(() => expect(rowOf("reserve-withdrawals")).toHaveTextContent("Viewing as A. Secretary (admin view): go back to yourself first"));
    expect(screen.queryByRole("button", { name: /^Propose / })).toBeNull();
  });

  it("is registered in Governance for the board's offices, and never an owner screen", () => {
    const s = SCREENS.find((x) => x.id === "controls");
    expect(s?.group).toBe("Governance");
    expect(GROUPS).toContain(s?.group);
    expect(s?.owner).toBeFalsy();
    expect(s?.roles).toEqual(["officer", "manager", "administrator"]);
    expect(Object.keys(owned.screens)).not.toContain("controls");
    expect(findScreen("controls")?.id).toBe("controls");
    const ids = SCREENS.filter((x) => x.group === "Governance").map((x) => x.id);
    expect(ids.indexOf("controls")).toBe(ids.indexOf("decisions") + 1);                         // beside Decisions
  });
});

describe("Controls, one control", () => {
  it("opens a suggestion with the provision in a Recitation BEFORE jason's labeled reading, and bands 1, 2, 4, 5, 6", async () => {
    serve({ cards: { "reserve-withdrawals": { body: one(RESERVE) } } });
    await card("reserve-withdrawals");
    const bands = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(bands).toEqual(["1 The provision", "2 What jason suggested", "4 What it changes", "5 Can the roster satisfy it", "6 History"]);
    const recitation = cardEl().querySelector("figure.recitation")!;
    const reading = cardEl().querySelector("aside.reading")!;
    expect(recitation).toHaveTextContent("Withdrawals from the reserve account require the signatures of two board members.");
    expect(recitation.compareDocumentPosition(reading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(reading).toHaveTextContent("jason's reading");
    expect(reading).toHaveTextContent("jason's reading, not the provision");
    expect(reading).toHaveTextContent("The floor is two board members. jason suggests keeping it and naming which two.");
    expect(cardEl()).toHaveTextContent("The floor: Signers: 2. A control only adds.");
    expect(screen.getByRole("button", { name: "Propose to the board" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /What the board adopted/ })).toBeNull();
  });

  it("never says a suggestion is in force", async () => {
    serve({ cards: { "reserve-withdrawals": { body: one(RESERVE) } } });
    await card("reserve-withdrawals");
    expect(cardEl().textContent).not.toMatch(/in force/i);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Reserve withdrawals");
    expect(head()).not.toHaveTextContent(/in force/i);
  });

  it("proposes from the card through Confirm with {act: 'propose'} only", async () => {
    const calls = serve({ cards: { "reserve-withdrawals": [{ body: one(RESERVE) }, { body: one(PROPOSED_ANSWER.control) }] } });
    const user = userEvent.setup();
    await card("reserve-withdrawals");
    await user.click(screen.getByRole("button", { name: "Propose to the board" }));
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    await user.click(within(screen.getByRole("group", { name: "Propose" })).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ act: "propose" });
    expect(await screen.findByRole("heading", { level: 2, name: "3 What the board adopted" })).toBeInTheDocument();
    expect(screen.getByText(/The board has not decided/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("It adopts nothing and changes no rule");
  });

  it("shows an adopted control through all six bands: the stamp, the decision and its vote as counts, what it changes, the roster, the history", async () => {
    serve({ cards: { "payment-signers": { body: one(PAYMENT_SIGNERS) } } });
    await card("payment-signers");
    const bands = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(bands).toEqual(["1 The provision", "2 What jason suggested", "3 What the board adopted", "4 What it changes", "5 Can the roster satisfy it", "6 History"]);
    expect(head()).toHaveTextContent("Adopted 2099-09-05 · in force since 2099-09-20 (the board's date)");
    expect(within(cardEl()).getByRole("img", { name: /Adopted, 2099-09-05/ })).toBeInTheDocument();
    const three = document.getElementById("control-band-3")!;
    expect(three).toHaveTextContent("Decision 2099-09-05-4");
    expect(three).toHaveTextContent("vote as taken: 5 to 0");
    expect(three).toHaveTextContent("recorded by the secretary");
    expect(within(three).getByRole("link", { name: "Open the decision" })).toHaveAttribute("href", "#/decisions?decision=2099-09-05-4");
    expect(document.getElementById("control-band-4")).toHaveTextContent("Stricter than the kind's own rule (one person).");
    expect(document.getElementById("control-band-5")).toHaveTextContent("The roster can satisfy it.");
    const trail = within(document.getElementById("control-band-6")!).getByRole("list", { name: "History, newest first" });
    const items = within(trail).getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(items[0]).toMatch(/^2099-09-20.*in force/);
    expect(items[0]).toMatch(/\(current\)/);
    expect(items.at(-1)).toMatch(/^2099-09-01.*suggested by jason/);
    expect(items.join(" ")).toMatch(/proposed by A\. Secretary/);
  });

  it("tells 'adopted, takes effect DATE' from 'in force, the roster cannot satisfy it' at the top of the card", async () => {
    serve({ cards: { "delivery-class": { body: one(DELIVERY_CLASS) }, "monthly-review": { body: one(MONTHLY_REVIEW) } } });
    await card("delivery-class");
    const ahead = cardEl().querySelector(".control-top")!;
    expect(ahead).toHaveTextContent("Adopted, not yet in force. It takes effect 2099-11-14 (the board's date) and does not bind until then.");
    expect(ahead.querySelector('[data-glyph="calendar-clock"]')).not.toBeNull();
    expect(cardEl()).not.toHaveTextContent(/roster cannot satisfy/);
    expect(head()).toHaveTextContent("takes effect 2099-11-14 (the board's date)");
    cleanup();

    resetServerSession();
    serve({ cards: { "monthly-review": { body: one(MONTHLY_REVIEW) } } });
    await card("monthly-review");
    const lacking = cardEl().querySelector(".control-top")!;
    expect(lacking).toHaveTextContent("In force, and the roster cannot satisfy it. the roster has no vice president.");
    expect(lacking).toHaveTextContent("The acts it governs are refused, with this reason. A control never falls back to fewer.");
    expect(lacking.querySelector('[data-glyph="user-x"]')).not.toBeNull();
    expect(cardEl()).not.toHaveTextContent(/takes effect/);
    const five = document.getElementById("control-band-5")!;
    expect(five).toHaveTextContent("The roster cannot satisfy it.");
    expect(five).toHaveTextContent("vice president");
    expect(head()).toHaveTextContent("in force since 2099-10-10 (the board's date)");
  });

  it("shows a declined control's reason and the date it may be asked again, in band 3", async () => {
    serve({ cards: { "manager-limit": { body: one(MANAGER_LIMIT) } } });
    await card("manager-limit");
    const three = document.getElementById("control-band-3")!;
    expect(three).toHaveTextContent("Reason: the manager's limit lives in the management contract");
    expect(three).toHaveTextContent("May be asked again after 2100-02-01 (the board's date).");
    expect(within(three).getByRole("button", { name: "Propose again" })).toBeInTheDocument();
    expect(three.querySelector(".stamp")).toBeNull();                                           // a stamp has no declined word
  });

  it("shows a changed provision in a banner above band 1, the control unchanged, both versions recited", async () => {
    const changed = { ...PAYMENT_SIGNERS, changed: { was: "Old words of the bylaw.", now: "New words of the bylaw.", changedOn: "2099-10-01", basis: "the governing documents' date", citation: "Example Bylaws, 99.9" } };
    serve({ cards: { "payment-signers": { body: one(changed) } } });
    await card("payment-signers");
    const banner = screen.getByRole("region", { name: "A provision changed" });
    expect(banner).toHaveTextContent("Example Bylaws, 99.9 changed on 2099-10-01 (the governing documents' date). The control stays as the board adopted it. The board decides whether it still serves.");
    expect(banner.querySelectorAll("figure.recitation")).toHaveLength(2);
    expect(banner).toHaveTextContent("Old words of the bylaw.");
    expect(banner).toHaveTextContent("New words of the bylaw.");
    const first = document.getElementById("control-band-1")!;
    expect(banner.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(head()).toHaveTextContent("in force since 2099-09-20");          // the state is untouched
  });

  it("offers 'Open in Decisions' to the secretary on a proposed control, not to a director", async () => {
    const proposed = PROPOSED_ANSWER.control;
      serve({ cards: { "reserve-withdrawals": { body: one(proposed) } } });
    await card("reserve-withdrawals");
    await waitFor(() => expect(screen.getByRole("link", { name: "Open in Decisions" })).toHaveAttribute("href", "#/decisions"));
    cleanup();

    resetServerSession();
    serve({ cards: { "reserve-withdrawals": { body: one(proposed) } }, session: { signedIn: { name: "B. Director", role: "director" } } });
    await card("reserve-withdrawals");
    await screen.findByText(/The board has not decided/);
    expect(screen.queryByRole("link", { name: "Open in Decisions" })).toBeNull();
  });

  it("names no person for an office: the roster shows offices and counts, and a name only as an actor in the history", async () => {
    const leaky = { ...MONTHLY_REVIEW, roster: { ...MONTHLY_REVIEW.roster, seated: [{ office: "treasurer", count: 1, name: "A. Treasurer", email: "treasurer@example.org" }] } };
    serve({ cards: { "monthly-review": { body: one(leaky as unknown as typeof MONTHLY_REVIEW) } } });
    await card("monthly-review");
    const five = document.getElementById("control-band-5")!;
    expect(five).toHaveTextContent("treasurer: 1");
    expect(five.textContent).not.toMatch(/A\. Treasurer|treasurer@example\.org/);
    expect(document.body.textContent).not.toMatch(/A\. Treasurer|@example\.org/);
  });

  it("moves focus to the title when the card opens, and keeps six labeled regions", async () => {
    serve({ cards: { "contract-authorization": { body: one(CONTRACT_AUTH) } } });
    await card("contract-authorization");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1 }).firstElementChild));
    expect(document.activeElement).toHaveTextContent("Contract authorization");
    expect(screen.getAllByRole("region")).toHaveLength(6);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Controls");
    expect(within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole("link", { name: "Controls" })).toHaveAttribute("href", "#/controls");
  });

  it("says a key with no control has none, and shows the server's sentence for a refusal", async () => {
    serve();
    window.location.hash = "#/controls?key=nope";
    render(<ControlsView />);
    expect(await screen.findByText("no control nope")).toBeInTheDocument();
    cleanup();

    resetServerSession();
    serve({ cards: { nope: { status: 403, body: { error: "Controls are open to the board's offices." } } } });
    render(<ControlsView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Controls are open to the board's offices.");
  });
});
