import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { closePrivate, openPrivate, resetServerSession, type PrivateView } from "../lib/api";
import { ConsoleShell, type ConsoleScreen } from "./ConsoleShell";
import { CONFIDENTIAL_LINE, DocumentViewer, type EvidenceDocument } from "./DocumentViewer";
import { EvidencePanel, type EvidenceAnswer } from "./Evidence";
import { clockTime, minutesLeft, PrivateBand, PrivateSwitch } from "./PrivateSwitch";

const NOW = new Date("2026-10-03T20:03:00Z");
const OFF: PrivateView = { open: false, mayOpen: true, why: "", minutes: [15, 30, 60], default: 30 };
const ON: PrivateView = { open: true, mayOpen: true, id: "a1b2c3d4", reason: "executive session prep", until: "2026-10-03T20:15:00Z" };
const TREASURER = "The treasurer's office doesn't open executive-session and other restricted material (P3).";
const SCREENS: ConsoleScreen[] = [{ id: "digest", label: "Board digest", ownerLabel: "Overview", group: "Overview", owner: true }];

function withToken(token = "tok-123") {
  const meta = document.createElement("meta");
  meta.name = "jason-token";
  meta.content = token;
  document.head.append(meta);
  return () => meta.remove();
}

function fetchReplying(body: unknown, status = 200) {
  const f = vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", f);
  return f;
}

function shell(over: { audience?: "board" | "owner"; account?: boolean; view?: PrivateView } = {}) {
  const onOpen = vi.fn(), onClose = vi.fn();
  const { audience = "board", account = true, view = OFF } = over;
  render(
    <ConsoleShell wordmark="Sample Commons" legal="Sample Commons Owners Association" groups={["Overview"]} screens={SCREENS} current="digest"
      onGo={vi.fn()} audience={audience} onAudience={vi.fn()}
      session={{ me: "D. Okafor", setMe: vi.fn(), people: [{ name: "D. Okafor", role: "president" }],
        account: account ? { name: "D. Okafor", role: "president" } : null,
        privateView: { view, onOpen, onClose } }}>
      <p>screen body</p>
    </ConsoleShell>,
  );
  return { onOpen, onClose };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  resetServerSession();
});

describe("PrivateSwitch", () => {
  it("is hidden when no one is signed in", () => {
    shell({ account: false });
    expect(screen.queryByRole("button", { name: /Private view/ })).toBeNull();
    expect(screen.queryByRole("region", { name: "Private view" })).toBeNull();
  });

  it("shows disabled with the reason, never blank, for an office that does not open it", () => {
    shell({ view: { open: false, mayOpen: false, why: TREASURER } });
    const button = screen.getByRole("button", { name: "Private view: off" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(TREASURER);
    expect(screen.getByText(TREASURER)).toBeVisible();
    render(<PrivateSwitch view={{ open: false, mayOpen: false }} name="A" onOpen={vi.fn()} />);
    expect(screen.getByText("Your office doesn't open restricted material.")).toBeInTheDocument();   // no why: still words
  });

  it("asks why and for how long, and posts {reason, minutes} with the token", async () => {
    const cleanup = withToken("tok-123");
    const f = fetchReplying({ private: { ...ON, until: "2026-10-03T20:18:00Z" } });
    try {
      const opened = vi.fn();
      render(<PrivateSwitch view={OFF} name="D. Okafor" onOpen={async (b) => { await openPrivate(b); opened(); }} />);
      await userEvent.click(screen.getByRole("button", { name: "Private view: off" }));
      const form = screen.getByRole("group", { name: "Open the private view" });
      const why = within(form).getByLabelText("Why");
      expect(why).toHaveFocus();
      expect(why).toHaveAccessibleDescription("A short phrase, e.g. executive session prep. It's logged.");
      expect(within(form).getByRole("radio", { name: "30 minutes" })).toBeChecked();
      await userEvent.click(within(form).getByRole("button", { name: "Open the private view as D. Okafor for 30 minutes" }));
      expect(within(form).getByRole("alert")).toHaveTextContent("Say why you open it");
      expect(f).not.toHaveBeenCalled();
      await userEvent.type(why, "  executive   session prep ");
      await userEvent.click(within(form).getByRole("radio", { name: "15 minutes" }));
      await userEvent.click(within(form).getByRole("button", { name: "Open the private view as D. Okafor for 15 minutes" }));
      expect(f).toHaveBeenCalledTimes(1);
      const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
      expect(url).toBe("/api/private");
      expect(init.method).toBe("POST");
      expect((init.headers as Record<string, string>)["X-Jason-Token"]).toBe("tok-123");
      expect(JSON.parse(String(init.body))).toEqual({ reason: "executive session prep", minutes: 15 });
      expect(opened).toHaveBeenCalled();
    } finally {
      cleanup();
    }
  });

  it("says the server's refusal in the form", async () => {
    const cleanup = withToken();
    fetchReplying({ error: "That reason looks like a secret (it gives a PIN or code with its digits): nothing was opened or kept." }, 400);
    try {
      render(<PrivateSwitch view={OFF} name="D. Okafor" onOpen={async (b) => { await openPrivate(b); }} />);
      await userEvent.click(screen.getByRole("button", { name: "Private view: off" }));
      await userEvent.type(screen.getByLabelText("Why"), "the PIN is 4321");
      await userEvent.click(screen.getByRole("button", { name: /^Open the private view as/ }));
      expect(await screen.findByRole("alert")).toHaveTextContent("looks like a secret");
    } finally {
      cleanup();
    }
  });

  it("closes the ask on Escape and gives focus back to the switch", async () => {
    render(<PrivateSwitch view={OFF} name="D. Okafor" onOpen={vi.fn()} />);
    const button = screen.getByRole("button", { name: "Private view: off" });
    await userEvent.click(button);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("group", { name: "Open the private view" })).toBeNull();
    expect(button).toHaveFocus();
  });
});

describe("PrivateBand", () => {
  it("shows the reason and the time left, under the header, and the switch says on", () => {
    vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval", "setTimeout", "clearTimeout"] });
    vi.setSystemTime(NOW);
    shell({ view: ON });
    const band = screen.getByRole("region", { name: "Private view" });
    const heading = within(band).getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent(
      `Private view — restricted material is shown — for executive session prep — until ${clockTime(ON.until)} (12 min left)`);
    expect(band.closest("header")).not.toBeNull();                                       // in the sticky bar
    expect(screen.getByText("Private view: on")).toBeInTheDocument();
  });

  it("counts down each minute, says five minutes once, and says when it closes", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout"] });
    let at = new Date("2026-10-03T20:08:30Z");
    const onExpired = vi.fn();
    render(<PrivateBand view={ON} onClose={vi.fn()} onExpired={onExpired} now={() => at} />);
    const band = screen.getByRole("region", { name: "Private view" });
    const live = band.querySelector("[aria-live='polite']")!;
    expect(band).toHaveTextContent("(7 min left)");
    expect(live).toHaveTextContent("");
    at = new Date("2026-10-03T20:10:30Z");
    await act(async () => { vi.advanceTimersByTime(10_000); });
    expect(band).toHaveTextContent("(5 min left)");
    expect(live).toHaveTextContent("The private view closes in 5 minutes.");
    at = new Date("2026-10-03T20:11:30Z");
    await act(async () => { vi.advanceTimersByTime(10_000); });
    expect(band).toHaveTextContent("(4 min left)");
    expect(live).toHaveTextContent("The private view closes in 5 minutes.");          // not every minute
    at = new Date("2026-10-03T20:15:00Z");
    await act(async () => { vi.advanceTimersByTime(10_000); });
    expect(live).toHaveTextContent("The private view has closed.");
    expect(onExpired).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(2_000); });
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it("takes focus on its heading right after it opens", () => {
    render(<PrivateBand view={ON} onClose={vi.fn()} focus now={() => NOW} />);
    expect(screen.getByRole("heading", { level: 2 })).toHaveFocus();
  });

  it("Close sends DELETE with the token", async () => {
    const cleanup = withToken("tok-9");
    const f = fetchReplying({ private: { open: false, mayOpen: true } });
    try {
      render(<PrivateBand view={ON} onClose={async () => { await closePrivate(); }} now={() => NOW} />);
      await userEvent.click(screen.getByRole("button", { name: "Close private view" }));
      const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
      expect(url).toBe("/api/private");
      expect(init.method).toBe("DELETE");
      expect((init.headers as Record<string, string>)["X-Jason-Token"]).toBe("tok-9");
    } finally {
      cleanup();
    }
  });

  it("reads minutes and clock times", () => {
    expect(minutesLeft("2026-10-03T20:15:00Z", NOW)).toBe(12);
    expect(minutesLeft("2026-10-03T20:03:01Z", NOW)).toBe(1);
    expect(minutesLeft("2026-10-03T20:00:00Z", NOW)).toBe(0);
    expect(minutesLeft("", NOW)).toBe(0);
    expect(clockTime("not a time")).toBe("");
    expect(clockTime(ON.until)).toMatch(/^\d\d:\d\d$/);
  });
});

describe("the owner view", () => {
  it("shows neither the switch nor the band", () => {
    shell({ audience: "owner", view: ON });
    expect(screen.queryByText("Private view: on")).toBeNull();
    expect(screen.queryByRole("button", { name: /Private view/ })).toBeNull();
    expect(screen.queryByRole("region", { name: "Private view" })).toBeNull();
  });
});

describe("confidential documents", () => {
  const docs: EvidenceDocument[] = [
    { id: "library:d1", name: "Declaration.pdf", kind: "pdf", size: 2048, readAt: "", note: "" },
    { id: "library:d2", name: "Private.pdf", kind: "pdf", size: 2048, readAt: "", note: "Confidential: shown in the private view", level: "P3" },
  ];
  const answer: EvidenceAnswer = {
    found: true, address: "decl#6.2", label: "Declaration § 6.2", kind: "citation", sources: [], changed: null, changedNote: "",
    link: "", refresh: [], refreshable: null, documents: docs, caveats: [], note: "",
  } as unknown as EvidenceAnswer;

  it("carry a Confidential chip in the Documents list", () => {
    render(<EvidencePanel address="decl#6.2" data={answer} by="Jane Example" onView={vi.fn()} />);
    const items = within(screen.getByRole("region", { name: "Documents" })).getAllByRole("listitem");
    expect(within(items[0]).queryByText("Confidential")).toBeNull();
    expect(within(items[1]).getByText("Confidential")).toHaveClass("private-chip");
  });

  it("say so in the viewer's header", () => {
    render(<DocumentViewer inline document={docs[1]} data={{ kind: "pdf", name: "Private.pdf", readAt: "", url: "", expires: "", caveats: [], level: "P3" }} />);
    expect(screen.getByText(CONFIDENTIAL_LINE)).toBeInTheDocument();
    expect(CONFIDENTIAL_LINE).toBe("Confidential: shown in the private view; this view is logged.");
  });

  it("an open document's viewer has no such line", () => {
    render(<DocumentViewer inline document={docs[0]} data={{ kind: "pdf", name: "Declaration.pdf", readAt: "", url: "", expires: "", caveats: [] }} />);
    expect(screen.queryByText(CONFIDENTIAL_LINE)).toBeNull();
  });
});
