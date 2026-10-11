import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { lookOf, paramWords, voteCounts, focusedControl, controlHref } from "../lib/controls";
import { KIND_NOTICES, PAYMENT_SIGNERS, QUESTION, RESERVE, SECOND_PERSON, CONTRACT_TERM, TODAY } from "../lib/controls.fixtures";
import { ControlChangedBanner } from "./ControlCard";
import { ControlNotice, ControlNoticeFor } from "./ControlNotice";
import { ControlProposeConfirm } from "./ControlProposeConfirm";
import { ControlQuestionRow, ControlRow, RefusedRow } from "./ControlRow";
import { ControlStateWord } from "./ControlStateWord";
import { RosterCheck } from "./RosterCheck";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetServerSession(); });

describe("ControlStateWord", () => {
  const cases: [string, string, string, string?][] = [
    ["suggested", "suggested", "proposal"],
    ["proposed", "proposed to the board", "paperclip"],
    ["in-force", "adopted, in force", "shield-check"],
    ["in-force-roster-lacks", "in force, the roster cannot satisfy it", "user-x"],
    ["adopted-not-in-force", "adopted, takes effect 2099-11-14", "calendar-clock", "2099-11-14"],
    ["declined", "declined", "circle-x"],
    ["deferred", "deferred", "circle-pause"],
    ["retired", "retired", "archive"],
  ];
  it.each(cases)("%s is a word and a glyph", (standing, word, glyph, effective) => {
    const { container } = render(<ControlStateWord standing={standing} effective={effective} />);
    expect(container).toHaveTextContent(word);
    expect(container.querySelector(`[data-glyph="${glyph}"]`)).not.toBeNull();
  });

  it("gives the date-ahead and roster-lacks cases different words and glyphs", () => {
    const a = lookOf("adopted-not-in-force", "2099-11-14")!;
    const b = lookOf("in-force-roster-lacks")!;
    expect(a.word).not.toBe(b.word);
    expect(a.glyph).not.toBe(b.glyph);
    expect(lookOf("adopted-not-in-force")!.word).toBe("adopted, not in force");           // no date set
  });

  it("shows the loader's sentence beside the word when asked, and an unknown standing plainly", () => {
    const { container, rerender } = render(<ControlStateWord standing="in-force" word="adopted, in force since 2099-09-20" detail />);
    expect(container).toHaveTextContent("adopted, in force since 2099-09-20");
    rerender(<ControlStateWord standing="paused-by-aliens" word="Paused" />);
    expect(container).toHaveTextContent("paused");
    expect(container.querySelector("[data-glyph]")).toBeNull();
  });

  it("never says a suggestion is in force", () => {
    for (const s of ["suggested", "proposed", "declined", "deferred", "retired"]) {
      const { container, unmount } = render(<ControlStateWord standing={s} word={s} detail />);
      expect(container.textContent).not.toMatch(/in force/i);
      unmount();
    }
  });
});

describe("RosterCheck", () => {
  it("shows offices and counts: needs, seated, and satisfied", () => {
    render(<RosterCheck roster={PAYMENT_SIGNERS.roster} />);
    expect(screen.getByText("treasurer: 1; director: 1")).toBeInTheDocument();
    expect(screen.getByText(/president: 1; secretary: 1/)).toBeInTheDocument();
    expect(screen.getByText("The roster can satisfy it.")).toBeInTheDocument();
  });

  it("says exactly which office is missing, by office", () => {
    render(<RosterCheck roster={{ read: true, needs: [{ office: "vice president", count: 1 }], seated: [{ office: "president", count: 1 }], missing: [{ office: "vice president" }], lacks: "the roster has no vice president" }} />);
    expect(screen.getByText("Missing")).toBeInTheDocument();
    expect(screen.getByText("The roster cannot satisfy it.")).toBeInTheDocument();
    expect(screen.getByText(/the roster has no vice president/)).toBeInTheDocument();
  });

  it("counts one person who holds two offices in each office, and names none", () => {
    const { container } = render(<RosterCheck roster={{ read: true, needs: [{ office: "secretary", count: 1 }, { office: "treasurer", count: 1 }], seated: [{ office: "secretary", count: 1 }, { office: "treasurer", count: 1 }], missing: [], lacks: "" }} />);
    expect(container).toHaveTextContent("secretary: 1; treasurer: 1");
  });

  it("renders only offices and counts: a name, email, or phone a loader sent by mistake is not shown", () => {
    const roster = { read: true, needs: [{ office: "treasurer", count: 1, name: "A. Treasurer" }], seated: [{ office: "treasurer", count: 1, name: "A. Treasurer", email: "t@example.org", phone: "555-0100" }],
      missing: [{ office: "vice president", name: "B. Nobody" }], lacks: "the roster has no vice president" };
    const { container } = render(<RosterCheck roster={roster as never} />);
    expect(container.textContent).not.toMatch(/A\. Treasurer|B\. Nobody|example\.org|555-0100/);
  });

  it("says when the roster could not be read, and assumes nothing", () => {
    render(<RosterCheck roster={{ read: false, needs: [], seated: [], missing: [], lacks: "" }} />);
    expect(screen.getByText(/could not be read, so this check was skipped/)).toBeInTheDocument();
    expect(screen.queryByText(/can satisfy/)).toBeNull();
  });
});

describe("ControlNotice", () => {
  it("is one line a control: 'a control the board adopted on DATE', the title linking to the card, the effective rule", () => {
    render(<ControlNotice data={KIND_NOTICES} />);
    const line = screen.getByText(/Required by a control the board adopted on 2099-09-05:/).closest("p")!;
    expect(line).toHaveTextContent("Two signers are required above $2,500.00.");
    expect(within(line).getByRole("link", { name: "Payment signers" })).toHaveAttribute("href", "#/controls?key=payment-signers");
    expect(screen.getByText("The kind's own rule is one person.")).toBeInTheDocument();
  });

  it("shows a control not yet effective in the muted form, never as required, and a refusal in the server's words", () => {
    const { container } = render(<ControlNotice data={KIND_NOTICES} />);
    const waiting = container.querySelector(".control-notice-waiting")!;
    expect(waiting).toHaveTextContent("Takes effect 2099-11-14; not yet required: Delivery class, a control the board adopted on 2099-10-03.");
    expect(waiting.className).toContain("muted");
    expect(waiting.textContent).not.toMatch(/Required by/);
    expect(waiting.querySelector('[data-glyph="calendar-clock"]')).not.toBeNull();
    const refused = container.querySelector(".control-notice-refused")!;
    expect(refused).toHaveTextContent("Refused: Monthly review requires a treasurer and a vice president; the roster has no vice president. A control never falls back to fewer.");
    expect(refused.querySelector('[data-glyph="ban"]')).not.toBeNull();
  });

  it("is built for a step or a send too, and draws nothing when no control touches the subject", () => {
    const send = { ...KIND_NOTICES, subjectKind: "step or send", subject: "mailroom", builtin: undefined, why: undefined, stricter: undefined, waiting: [], refusals: [] };
    const { container, rerender } = render(<ControlNotice data={send} />);
    expect(container).toHaveTextContent("Required by a control the board adopted on 2099-09-05: Payment signers.");
    rerender(<ControlNotice data={{ ...send, controls: [], waiting: [], refusals: [] }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ControlNotice data={null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ControlNotice data={{ ...send, found: false }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("reads its data from /api/control-notices, and shows nothing when the loader refuses", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (u: string) => { urls.push(String(u)); return new Response(JSON.stringify(KIND_NOTICES), { status: 200 }); }));
    render(<ControlNoticeFor subject="payhoa-attach-bills" amountCents={300000} />);
    expect(await screen.findByText(/Required by a control the board adopted/)).toBeInTheDocument();
    expect(urls).toEqual(["/api/control-notices?subject=payhoa-attach-bills&amount=300000"]);
    cleanup();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "Controls are for the board." }), { status: 403 })));
    const { container } = render(<ControlNoticeFor subject="payhoa-attach-bills" />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

describe("ControlProposeConfirm", () => {
  it("writes nothing on the first click, then posts {act: 'propose'} and nothing else", async () => {
    const post = vi.fn(async () => ({ key: "reserve-withdrawals", item: "control-reserve-withdrawals" }));
    const done = vi.fn();
    const user = userEvent.setup();
    render(<ControlProposeConfirm controlKey="reserve-withdrawals" title="Reserve withdrawals" by="A. Secretary" onProposed={done} post={post as never} />);
    await user.click(screen.getByRole("button", { name: "Propose to the board" }));
    expect(post).not.toHaveBeenCalled();
    const group = screen.getByRole("group", { name: "Propose" });
    expect(group).toHaveTextContent("Create a board item, control-reserve-withdrawals, with this provision as its evidence, as A. Secretary. It adopts nothing and changes no rule");
    await user.click(within(group).getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(done).toHaveBeenCalledOnce());
    expect(post).toHaveBeenCalledWith("/api/write/controls/reserve-withdrawals", { act: "propose" });
  });

  it("cancels without writing, and shows a refusal in the server's sentence", async () => {
    const post = vi.fn(async () => { throw new Error("a declined control may be asked again after 2100-02-01"); });
    const user = userEvent.setup();
    render(<ControlProposeConfirm controlKey="k" title="K" post={post as never} />);
    await user.click(screen.getByRole("button", { name: "Propose to the board" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(post).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Propose to the board" }));
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("a declined control may be asked again after 2100-02-01");
  });

  it("is replaced by the admin-view sentence while an administrator views as someone else", () => {
    render(<ControlProposeConfirm controlKey="k" title="K" actingAs="A. Secretary" />);
    expect(screen.getByText(/Viewing as A\. Secretary \(admin view\): go back to yourself first\./)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ControlRow", () => {
  it("is a link to the card, with the citation and a line of what it requires; Propose only on a suggestion", () => {
    const { container, rerender } = render(<ul><ControlRow row={RESERVE} /></ul>);
    expect(screen.getByRole("link", { name: "Reserve withdrawals" })).toHaveAttribute("href", controlHref("reserve-withdrawals"));
    expect(container).toHaveTextContent("Example Bylaws, 99.9(b)");
    expect(screen.getByRole("button", { name: "Propose Reserve withdrawals to the board" })).toHaveTextContent("Propose");
    rerender(<ul><ControlRow row={CONTRACT_TERM} /></ul>);
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<ul><ControlRow row={PAYMENT_SIGNERS} /></ul>);
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<ul><ControlRow row={SECOND_PERSON} /></ul>);
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("draws a question with its words recited and no suggestion, and a refusal with the floor and no Propose", () => {
    const { container } = render(<ul><ControlQuestionRow q={QUESTION} /><RefusedRow r={{ title: "One signer for reserve withdrawals", why: "The floor is two board members (Example Bylaws, 99.9(b)).", floor: { citation: "Example Bylaws, 99.9(b)", words: "Withdrawals from the reserve account require the signatures of two board members." } }} /></ul>);
    const [q, r] = Array.from(container.querySelectorAll("li"));
    expect(q).toHaveTextContent("No suggestion: it reads two ways");
    expect(q.querySelector('[data-glyph="circle-question-mark"]')).not.toBeNull();
    expect(r).toHaveTextContent("Refused: The floor is two board members (Example Bylaws, 99.9(b)). A control only adds.");
    expect(r.querySelector('[data-glyph="ban"]')).not.toBeNull();
    expect(r.querySelector("figure.recitation")).toHaveTextContent("require the signatures of two board members");
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ControlChangedBanner", () => {
  it("shows both versions recited and leaves the control as adopted", () => {
    const { container } = render(<ControlChangedBanner changed={{ wasWords: "Old.", words: "New.", changedOn: "2099-10-01" }} citation="Example Bylaws, 99.9" itemId="control-payment-signers" />);
    expect(container.querySelectorAll("figure.recitation")).toHaveLength(2);
    expect(container).toHaveTextContent("The control stays as the board adopted it.");
    expect(screen.getByRole("link", { name: "Open the board item" })).toHaveAttribute("href", "#/actions?item=control-payment-signers");
  });
});

describe("lib/controls", () => {
  it("reads the card's key from the hash, and writes the vote as counts", () => {
    expect(focusedControl("#/controls?key=payment-signers")).toBe("payment-signers");
    expect(focusedControl("#/controls")).toBe("");
    expect(voteCounts({ yes: 5, no: 0, abstain: 0 })).toBe("5 to 0");
    expect(voteCounts({ yes: 3, no: 1, abstain: 1 })).toBe("3 to 1, 1 abstain");
    expect(paramWords({ signers: 2, secondAboveCents: 250000, roles: ["treasurer", "director"] })).toBe("Signers: 2; Second Above: $2,500.00; Roles: treasurer, director");
    expect(TODAY).toBe("2099-10-12");
  });
});
