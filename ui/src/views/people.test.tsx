import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SCREENS } from "../App";
import owned from "../ownerScreens.json";
import { PeopleView, type People } from "./PeopleView";

afterEach(() => vi.unstubAllGlobals());

const duty = (key: string, title: string, role: string, name = "") => ({
  key, title, adoption: "proposed", owners: name ? [{ role, name, adoption: "proposed" }] : [], assigned: !!name,
  routing: name ? `routed to the ${role} (assignment ${key}, proposed)` : `unassigned: waiting for a person to take it (no one holds the office of ${role})`,
  backup: "",
});

// Made-up people: one holds secretary and treasurer; no one holds vice president.
const PEOPLE: People = {
  found: true, asOf: "2099-10-01",
  offices: [
    { office: "president", holders: [{ name: "Lee Sample", approves: ["the president"], recordsBoard: true, canSignIn: true }], vacant: false, vacancy: "", provision: null, provisionNote: "", duties: [] },
    { office: "vice president", holders: [], vacant: true, vacancy: "No one holds the office of vice president.", provision: null,
      provisionNote: "The governing documents' vacancy provision is not on file.", duties: [duty("vp-review", "Review the sample policy", "vice president")] },
    { office: "secretary", holders: [{ name: "Tess Sample", approves: ["the secretary"], recordsBoard: true, canSignIn: true }], vacant: false, vacancy: "", provision: null, provisionNote: "", duties: [] },
    { office: "treasurer", holders: [{ name: "Tess Sample", approves: ["the treasurer"], recordsBoard: false, canSignIn: true }], vacant: false, vacancy: "", provision: null, provisionNote: "",
      duties: [duty("books", "Review the sample reconciliations", "treasurer", "Tess Sample")] },
  ],
  directors: { holders: [{ name: "Dana Sample", approves: [], recordsBoard: false, canSignIn: false }], seats: null },
  management: { holders: [], note: "Management, not an office of the board.", vacant: true, vacancy: "No one holds the manager's role.", duties: [] },
  admins: [{ name: "Ada Sample", holds: [], canSignIn: true, note: "Not an office; approves nothing." }],
  people: [
    { name: "Ada Sample", offices: [], approves: [], recordsBoard: false, canSignIn: true, admin: true, email: "[email]" },
    { name: "Lee Sample", offices: ["president"], approves: ["the president"], recordsBoard: true, canSignIn: true, admin: false, email: "[email]" },
    { name: "Tess Sample", offices: ["secretary", "treasurer"], approves: ["the secretary", "the treasurer"], recordsBoard: true, canSignIn: true, admin: false, email: "[email]" },
  ],
  vacant: ["vice president"],
  terms: { onFile: false, note: "Terms: not on file." },
  change: { note: "A change of office is the board's act, recorded in the minutes; then the board-roster question records it (a second person confirms).",
            onboardingItem: "board-roster", screen: "onboarding", built: false, commands: ["jason onboard --apply"], gap: "The board-roster question is not built yet." },
  emailsShown: false, emailsNote: "Email addresses are masked.",
  caveats: ["A vacant office's duties are unassigned."],
};

async function show(data: People = PEOPLE) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(data), { status: 200 })));
  render(<PeopleView />);
  await screen.findByRole("heading", { name: "People and offices" });
}

describe("PeopleView", () => {
  it("has no edit controls: the only buttons copy a command or sort the table, and there is no field", async () => {
    await show();
    const buttons = screen.getAllByRole("button");
    const other = buttons.filter((b) => b.getAttribute("aria-label") !== "Copy command" && !b.closest("th"));
    expect(other.map((b) => b.textContent)).toEqual([]);
    expect(buttons.some((b) => /edit|add|remove|retire|change|save|assign/i.test(`${b.textContent} ${b.getAttribute("aria-label") ?? ""}`))).toBe(false);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText(/A change of office is the board's act, recorded in the minutes/)).toBeInTheDocument();
    expect(screen.getByText("jason onboard --apply")).toBeInTheDocument();
  });

  it("says a vacant office is held by no one, with the provision's absence, and routes it nowhere", async () => {
    await show();
    const vp = screen.getByRole("region", { name: "vice president" });
    expect(within(vp).getByText(/No one holds the office of vice president\./)).toBeInTheDocument();
    expect(within(vp).getByText("The governing documents' vacancy provision is not on file.")).toBeInTheDocument();
    expect(vp.textContent).not.toMatch(/the president ·|routed to the president/);
  });

  it("shows a vacant office's duties as unassigned, and a held office's routed to it", async () => {
    await show();
    const vp = screen.getByRole("region", { name: "vice president" });
    expect(within(vp).getByText("Review the sample policy", { exact: false })).toBeInTheDocument();
    expect(vp.querySelector(".routing-unassigned")).not.toBeNull();
    const treasurer = screen.getByRole("region", { name: "treasurer" });
    expect(treasurer.querySelector(".routing-unassigned")).toBeNull();
    expect(within(treasurer).getAllByText(/Tess Sample/).length).toBeGreaterThan(0);
  });

  it("lists one person under both offices, the admin as no office, and terms as not on file", async () => {
    await show();
    expect(within(screen.getByRole("region", { name: "secretary" })).getByText(/Tess Sample/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "treasurer" })).getAllByText(/Tess Sample/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Ada Sample: Not an office; approves nothing\./)).toBeInTheDocument();
    expect(screen.getByText("Terms: not on file.")).toBeInTheDocument();
    expect(screen.getAllByText("[email]").length).toBe(3);
  });

  it("is a board screen only", () => {
    const people = SCREENS.find((s) => s.id === "people");
    expect(people?.owner).toBeFalsy();
    expect(Object.keys(owned.screens)).not.toContain("people");
  });
});
