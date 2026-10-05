import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { resetServerSession } from "../lib/api";

/** The console's roles end to end on the page's side: the server says what the signed-in person is (`roleClass`), the
 * nav follows it, a person with no route in the address lands where their role does, and the strip names their moves.
 * Every other source answers "not found", so each screen shows its own empty note. */

function serve(session: Record<string, unknown>, counts: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url);
    const body = path.startsWith("/api/session") ? session
      : path.startsWith("/api/dock?part=counts") ? { found: true, deadlines: 1, tasks: 2, approvals: 3, scope: "mine", who: "Mo Manager", ...counts }
      : { found: false, note: "not here" };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

const nav = () => screen.getByRole("navigation", { name: "Duties" });

beforeEach(() => { resetServerSession(); window.location.hash = ""; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

describe("the console by role", () => {
  it("hides Decisions from the manager, lands them on the duties, and shows their moves there", async () => {
    serve({ token: "t", header: "X-Jason-Token", signedIn: { name: "Mo Manager", role: "manager", email: "m@example.org" }, roleClass: "manager" });
    render(<App />);
    await waitFor(() => expect(window.location.hash).toBe("#/duties"));
    expect(within(nav()).queryByRole("button", { name: "Decisions" })).toBeNull();
    expect(within(nav()).getByRole("button", { name: /Duties by cadence/ })).toHaveAttribute("aria-current", "page");
    const strip = await screen.findByRole("region", { name: "Your moves" });
    expect(strip).toHaveTextContent("Mo Manager, manager: your moves");
    expect(within(strip).getByRole("button", { name: "2 of your tasks overdue" })).toBeInTheDocument();
  });

  it("lands an administrator on Status and keeps Decisions in their nav", async () => {
    serve({ token: "t", header: "X-Jason-Token", signedIn: { name: "Ana Admin", role: "admin", email: "a@example.org", admin: true }, roleClass: "administrator" },
      { who: "", scope: "everyone" });
    render(<App />);
    await waitFor(() => expect(window.location.hash).toBe("#/status"));
    expect(within(nav()).getByRole("button", { name: /^Status/ })).toHaveAttribute("aria-current", "page");
    expect(within(nav()).getByRole("button", { name: "Decisions" })).toBeInTheDocument();
  });

  it("never shows Status in the nav to anyone but one of jason's admins", async () => {
    serve({ token: "t", header: "X-Jason-Token", signedIn: { name: "Lee Officer", role: "president", email: "l@example.org" }, roleClass: "officer" });
    render(<App />);
    await screen.findByRole("navigation", { name: "Duties" });
    await waitFor(() => expect(window.location.hash).toBe("#/digest"));
    expect(within(nav()).queryByRole("button", { name: /^Status/ })).toBeNull();
  });

  it("keeps an explicit link, and filters nothing when no one is signed in", async () => {
    window.location.hash = "#/liens";
    serve({ token: "t", header: "X-Jason-Token", signedIn: null, roleClass: "" });
    render(<App />);
    await screen.findByRole("navigation", { name: "Duties" });
    expect(window.location.hash).toBe("#/liens");
    expect(within(nav()).getByRole("button", { name: "Decisions" })).toBeInTheDocument();
    expect(within(nav()).queryByRole("button", { name: /^Status/ })).toBeNull();   // no one signed in: no admin screen
    expect(screen.queryByRole("region", { name: "Your moves" })).toBeNull();
  });
});
