import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConsoleShell, OWNER_BANNER, ScreenHeader, visibleScreens, type ConsoleScreen } from "./ConsoleShell";

const SCREENS: ConsoleScreen[] = [
  { id: "digest", label: "Board digest", ownerLabel: "Overview", group: "Overview", owner: true },
  { id: "approvals", label: "Approvals", group: "Overview", count: 2 },
  { id: "actions", label: "Board action items", group: "Governance" },
  { id: "meetings", label: "Meetings and minutes", group: "Governance", owner: true },
  { id: "liens", label: "Liens and delinquency", group: "Money" },
  { id: "records", label: "Records (CIV 5200)", group: "Records", owner: true },
];
const GROUPS = ["Overview", "Governance", "Money", "Records"];

function shell(over: Partial<Parameters<typeof ConsoleShell>[0]> = {}) {
  const onGo = vi.fn(), onAudience = vi.fn(), setMe = vi.fn();
  render(
    <ConsoleShell wordmark="Sample Commons" legal="Sample Commons Owners Association" groups={GROUPS} screens={SCREENS} current="digest" onGo={onGo} audience="board" onAudience={onAudience}
      session={{ me: "D. Okafor", setMe, people: [{ name: "D. Okafor", role: "president" }, { name: "R. Lind", role: "treasurer" }] }} dock={<span data-testid="dock">dock</span>} {...over}>
      <p>screen body</p>
    </ConsoleShell>,
  );
  return { onGo, onAudience, setMe };
}

describe("ConsoleShell", () => {
  it("groups the nav, marks the current screen, carries counts, and routes", async () => {
    const { onGo } = shell();
    const nav = screen.getByRole("navigation", { name: "Duties" });
    expect(within(nav).getAllByText(/^(Overview|Governance|Money|Records)$/).map((p) => p.textContent)).toEqual(GROUPS);
    expect(within(nav).getByRole("button", { name: "Board digest" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("button", { name: "Approvals (2)" })).toBeInTheDocument();
    await userEvent.click(within(nav).getByRole("button", { name: "Liens and delinquency" }));
    expect(onGo).toHaveBeenCalledWith("liens");
    expect(screen.getByText("Sample Commons Owners Association · jason")).toBeInTheDocument();
    expect(screen.getByTestId("dock")).toBeInTheDocument();
    expect(screen.queryByText(/Records as of/)).toBeNull(); // no loader gave a date: nothing is invented
  });

  it("lets the person pick who they are signed in as", async () => {
    const { setMe } = shell();
    const pick = screen.getByLabelText("Signed in as");
    expect(pick).toHaveValue("D. Okafor");
    await userEvent.selectOptions(pick, "R. Lind");
    expect(setMe).toHaveBeenCalledWith("R. Lind");
  });

  it("names the officer signed in with Google, with Sign out and no picker", async () => {
    const onSignOut = vi.fn();
    const people = [{ name: "D. Okafor", role: "president" }];
    shell({ session: { me: "D. Okafor", setMe: vi.fn(), people, account: { name: "D. Okafor", role: "president", email: "d@example.org" }, onSignOut, signInHref: "/auth/google" } });
    expect(screen.queryByLabelText("Signed in as")).toBeNull();
    expect(screen.getByText("D. Okafor, president")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Sign in with Google" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalled();
  });

  it("offers Sign in with Google beside the picker when the server has it, and says a refusal", () => {
    const people = [{ name: "D. Okafor", role: "president" }];
    shell({ session: { me: "", setMe: vi.fn(), people, signInHref: "/auth/google?next=%23%2Fdigest", signInError: "x@example.org is not an officer's account" } });
    expect(screen.getByRole("link", { name: "Sign in with Google" })).toHaveAttribute("href", "/auth/google?next=%23%2Fdigest");
    expect(screen.getByLabelText("Signed in as")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("not an officer's account");
  });

  it("hides board-only screens, the sign-in, and board drawers from owners, and shows the read-only banner", async () => {
    const { onAudience } = shell({ audience: "owner" });
    const nav = screen.getByRole("navigation", { name: "Duties" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent)).toEqual(["Overview", "Meetings and minutes", "Records (CIV 5200)"]);
    expect(within(nav).queryByText("Money")).toBeNull(); // an empty group is not shown
    expect(screen.queryByLabelText("Signed in as")).toBeNull();
    expect(screen.getByText(OWNER_BANNER)).toBeInTheDocument();
    const seg = screen.getByRole("radiogroup", { name: "View as" });
    expect(within(seg).getByRole("radio", { name: "Owner view" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(within(seg).getByRole("radio", { name: "Board" }));
    expect(onAudience).toHaveBeenCalledWith("board");
    expect(visibleScreens(SCREENS, "owner").map((s) => s.id)).toEqual(["digest", "meetings", "records"]);
  });

  it("becomes a Go to select under 720px", async () => {
    const saved = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { value: 600, configurable: true, writable: true });
    try {
      const { onGo } = shell();
      expect(screen.queryByRole("navigation", { name: "Duties" })).toBeNull();
      const pick = screen.getByLabelText("Go to");
      expect(within(pick).getByRole("option", { name: "Money · Liens and delinquency" })).toBeInTheDocument();
      await userEvent.selectOptions(pick, "records");
      expect(onGo).toHaveBeenCalledWith("records");
    } finally {
      Object.defineProperty(window, "innerWidth", { value: saved, configurable: true, writable: true });
    }
  });

  it("renders the screen header pattern", () => {
    render(<ScreenHeader title="Liens and delinquency" summary="Every lien in order." />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Liens and delinquency");
    expect(screen.getByText("Every lien in order.")).toHaveClass("muted");
  });
});
