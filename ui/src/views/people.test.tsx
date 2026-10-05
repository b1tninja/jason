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

  it("shows terms on file with their election records, an ended one as due, and the questions that record them", async () => {
    const q = (item: string, id: string, form: string) => ({
      item, id, words: `The sample ${item} question.`, form,
      commands: [`jason onboard --answer ${id} "${form}" --by "YOUR NAME"`, `jason onboard --confirm ${id} --by "SECOND PERSON"`, "jason onboard --apply"],
    });
    await show({
      ...PEOPLE,
      terms: {
        onFile: true, note: "Each term as its election record gives it.", ended: 1,
        rows: [
          { person: "Lee Sample", seat: "director", office: "", start: "2096-03-01", end: "2098-02-28", endNote: "2098-02-28",
            source: "Sample inspector's report, 2096", provision: "Bylaws 9.1", ended: true, status: "term ended; election due" },
          { person: "Tess Sample", seat: "officer", office: "secretary", start: "2098-03-09", end: null, endNote: "at the pleasure of the board",
            source: "Sample minutes, 2098-03-09", provision: "Bylaws 9.2", ended: false, status: "" },
        ],
        question: q("election-status", "t0000000001", "SEAT; PERSON; START; END; RECORD; PROVISION"),
      },
      change: { ...PEOPLE.change, built: true, gap: "", question: q("board-roster", "c0000000001", "OFFICE; PERSON (or vacant); YYYY-MM-DD; MINUTES"),
                commands: q("board-roster", "c0000000001", "OFFICE; PERSON (or vacant); YYYY-MM-DD; MINUTES").commands },
    });
    expect(screen.queryByText("Terms: not on file.")).not.toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Terms on file" });
    const [lee, tess] = within(list).getAllByRole("listitem");
    expect(lee.textContent).toMatch(/term ended; election due/);
    expect(within(lee).getByText("Sample inspector's report, 2096")).toBeInTheDocument();
    expect(tess.textContent).toMatch(/at the pleasure of the board/);
    expect(tess.textContent).not.toMatch(/election due/);
    expect(within(tess).getByText("Sample minutes, 2098-03-09")).toBeInTheDocument();
    expect(screen.getByText("The sample board-roster question.")).toBeInTheDocument();
    expect(screen.getByText(/jason onboard --answer c0000000001/)).toBeInTheDocument();
    expect(screen.getByText(/jason onboard --answer t0000000001/)).toBeInTheDocument();
    expect(screen.queryByText("The board-roster question is not built yet.")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("is a board screen only", () => {
    const people = SCREENS.find((s) => s.id === "people");
    expect(people?.owner).toBeFalsy();
    expect(Object.keys(owned.screens)).not.toContain("people");
  });
});
