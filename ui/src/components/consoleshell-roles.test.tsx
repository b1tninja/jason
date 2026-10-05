import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConsoleShell, ScreenHeader, DEFAULT_LANDING, landingScreen, visibleScreens, type ConsoleScreen, type Move, type Role } from "./ConsoleShell";
import { DockToolbar } from "./Dock";

const SCREENS: ConsoleScreen[] = [
  { id: "digest", label: "Board digest", ownerLabel: "Overview", group: "Overview", owner: true, glyph: "house" },
  { id: "approvals", label: "Approvals", group: "Overview", roles: ["officer", "administrator"], count: 2 },
  { id: "duties", label: "Duties by cadence", group: "Overview", roles: ["officer", "manager", "administrator"] },
  { id: "decisions", label: "Decisions", group: "Governance", roles: ["officer", "administrator"] },
  { id: "meetings", label: "Meetings and minutes", group: "Governance", owner: true },
  { id: "records", label: "Records (CIV 5200)", group: "Records", roles: ["officer", "manager", "administrator", "owner"] },
];
const GROUPS = ["Overview", "Governance", "Records"];
const ids = (role: Role | undefined, audience: "board" | "owner" = "board") => visibleScreens(SCREENS, audience, role).map((s) => s.id);

describe("visibleScreens by role", () => {
  it("filters a screen that declares roles, and follows the audience for one that does not", () => {
    expect(ids("manager")).toEqual(["digest", "duties", "meetings", "records"]);          // no Decisions, no Approvals
    expect(ids("officer")).toEqual(["digest", "approvals", "duties", "decisions", "meetings", "records"]);
    expect(ids("administrator")).toEqual(["digest", "approvals", "duties", "decisions", "meetings", "records"]);
    expect(ids(undefined)).toEqual(SCREENS.map((s) => s.id));                              // no role given: as before
  });

  it("an owner audience is the owner role, whatever role it is given", () => {
    expect(ids("officer", "owner")).toEqual(["digest", "meetings", "records"]);
    expect(ids(undefined, "owner")).toEqual(["digest", "meetings", "records"]);
  });
});

describe("landingScreen", () => {
  it("is the role's own screen unless the shell names another", () => {
    expect(DEFAULT_LANDING).toEqual({ officer: "digest", manager: "duties", administrator: "approvals", owner: "digest" });
    expect(landingScreen("manager")).toBe("duties");
    expect(landingScreen("manager", { manager: "approvals" })).toBe("approvals");
    expect(landingScreen(undefined)).toBeUndefined();
  });
});

describe("ConsoleShell roles", () => {
  const go = vi.fn();
  const moves: Move[] = [{ n: 2, label: "waiting for your approval", go }, { n: 0, label: "of your tasks overdue", go: vi.fn() }];
  function shell(over: Partial<Parameters<typeof ConsoleShell>[0]> = {}) {
    return render(
      <ConsoleShell wordmark="Sample Commons" legal="Sample Commons Owners Association" groups={GROUPS} screens={SCREENS} current="digest" onGo={vi.fn()} audience="board" onAudience={vi.fn()}
        role="officer" moves={moves} session={{ me: "D. Okafor", setMe: vi.fn(), people: [{ name: "D. Okafor", role: "president" }] }} {...over}>
        <p>screen body</p>
      </ConsoleShell>,
    );
  }

  it("shows the role strip only on the role's landing screen, naming the person and the office", async () => {
    const { rerender } = shell();
    const strip = screen.getByRole("region", { name: "Your moves" });
    expect(strip).toHaveTextContent("D. Okafor, president: your moves");
    const first = within(strip).getByRole("button", { name: "2 waiting for your approval" });
    await userEvent.click(first);
    expect(go).toHaveBeenCalled();
    expect(within(strip).getByRole("button", { name: "0 of your tasks overdue" })).toHaveClass("quiet"); // muted at zero
    rerender(
      <ConsoleShell wordmark="W" legal="L" groups={GROUPS} screens={SCREENS} current="approvals" onGo={vi.fn()} audience="board" onAudience={vi.fn()} role="officer" moves={moves}>
        <p>elsewhere</p>
      </ConsoleShell>,
    );
    expect(screen.queryByRole("region", { name: "Your moves" })).toBeNull();
  });

  it("lands each role where the spec says, and a shell's landing overrides it", () => {
    shell({ role: "manager", current: "duties" });
    expect(screen.getByRole("region", { name: "Your moves" })).toBeInTheDocument();
    cleanupAndRender({ role: "manager", current: "digest" }); // the manager's landing is duties, not the digest
    expect(screen.queryByRole("region", { name: "Your moves" })).toBeNull();
    cleanupAndRender({ role: "manager", current: "digest", landing: { manager: "digest" } });
    expect(screen.getByRole("region", { name: "Your moves" })).toBeInTheDocument();
  });

  it("shows no strip without a role or without moves, and an owner's is the owner's landing", () => {
    shell({ role: undefined });
    expect(screen.queryByRole("region", { name: "Your moves" })).toBeNull();
    cleanupAndRender({ moves: [] });
    expect(screen.queryByRole("region", { name: "Your moves" })).toBeNull();
    cleanupAndRender({ audience: "owner", role: "officer" }); // the owner audience is the owner role, which lands on the digest
    expect(screen.getByRole("region", { name: "Your moves" })).toBeInTheDocument();
  });

  it("an admin viewing as another role sees that role's screens", () => {
    const { rerender } = shell({ role: "administrator" });
    expect(within(screen.getByRole("navigation", { name: "Duties" })).queryByRole("button", { name: "Decisions" })).toBeInTheDocument();
    rerender(
      <ConsoleShell wordmark="W" legal="L" groups={GROUPS} screens={SCREENS} current="digest" onGo={vi.fn()} audience="board" onAudience={vi.fn()} role="manager">
        <p>x</p>
      </ConsoleShell>,
    );
    expect(within(screen.getByRole("navigation", { name: "Duties" })).queryByRole("button", { name: "Decisions" })).toBeNull();
  });

  it("puts a glyph beside a nav label, on the dock pills, and on the screen header", () => {
    shell();
    expect(screen.getByRole("button", { name: "Board digest" }).querySelector("svg[data-glyph='house']")).not.toBeNull();
    const { container } = render(<DockToolbar open={null} onToggle={vi.fn()} counts={{ deadlines: 0, tasks: 0 }} audience="board" />);
    expect(Array.from(container.querySelectorAll("svg[data-glyph]")).map((g) => g.getAttribute("data-glyph"))).toEqual(
      ["calendar-clock", "list-checks", "notebook", "message-circle-question-mark"]);
    const head = render(<ScreenHeader title="Approvals" glyph="stamp" />);
    expect(head.container.querySelector(".screen-glyph svg[data-glyph='stamp']")).not.toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Approvals" })).toBeInTheDocument();
  });

  function cleanupAndRender(over: Partial<Parameters<typeof ConsoleShell>[0]>) {
    document.body.innerHTML = "";
    shell(over);
  }
});
