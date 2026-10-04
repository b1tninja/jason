import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssociationPicker } from "./AssociationPicker";
import { evidenceText, yearsText } from "../lib/discovery";

afterEach(() => vi.unstubAllGlobals());

const row = (key: string, name: string, extra: Record<string, unknown> = {}) => ({
  key, name, kind: "homeowners", standing: "confirmed", first: "2004-03-01", last: "2025-11-20",
  spellings: [name, `${name.replace("HOMEOWNERS ASSOCIATION", "HOA")}`], evidence: { "assessment lien": 386, declaration: 15 },
  governing: 12, links: 0, score: 9, ...extra,
});

const directory = {
  county: "placer", surveyed: true,
  summary: { byStanding: { confirmed: 2, likely: 1, named: 0 } },
  results: [
    row("example-village", "EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION"),
    row("example-oaks", "EXAMPLE OAKS OWNERS ASSN", { standing: "likely", kind: "maintenance", evidence: { property: 1, business: 3 }, spellings: ["EXAMPLE OAKS OWNERS ASSN"] }),
  ],
  caveats: ["The directory is read from the public index; a row is not a membership."],
};

function stub(answer: (url: string) => unknown) {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return new Response(JSON.stringify(answer(url)), { status: 200 }); }));
  return urls;
}

describe("discovery words", () => {
  it("puts evidence and years in words", () => {
    expect(evidenceText({ "assessment lien": 386, declaration: 15, property: 0 })).toBe("386 assessment liens · 15 declaration filings");
    expect(evidenceText({ "sale notice": 1, property: 2 })).toBe("2 property filings · 1 sale notice");
    expect(yearsText("2004-03-01", "2025-11-20")).toBe("recorded from 2004 through 2025");
    expect(yearsText("2004-03-01", "2004-05-01")).toBe("recorded in 2004");
  });
});

describe("AssociationPicker", () => {
  it("searches as a combobox, moves with the arrows, and chooses with Enter without writing", async () => {
    const urls = stub(() => directory);
    const onPick = vi.fn();
    render(<AssociationPicker counties={["placer", "sacramento"]} onPick={onPick} debounceMs={0} />);
    const box = screen.getByRole("combobox", { name: "Association's name" });
    expect(await screen.findByText("EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION")).toBeInTheDocument();
    expect(screen.getByText(/The Placer directory holds 3 associations: 2 confirmed · 1 likely/)).toBeInTheDocument();
    expect(screen.getAllByText("386 assessment liens · 15 declaration filings")).toHaveLength(1);
    expect(screen.getByText("3 business filings · 1 property filing")).toBeInTheDocument();
    expect(screen.getAllByText("recorded from 2004 through 2025").length).toBeGreaterThan(0);
    expect(screen.getByText("A directory row is a lead, not a pin.")).toBeInTheDocument();
    expect(screen.getByText(directory.caveats[0])).toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(box, "oaks");
    await waitFor(() => expect(urls.some((u) => u.includes("q=oaks") && u.includes("county=placer") && u.includes("limit=25"))).toBe(true));
    expect(box).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{ArrowDown}{ArrowDown}");
    const options = within(screen.getByRole("listbox")).getAllByRole("option");
    expect(box).toHaveAttribute("aria-activedescendant", options[1].id);
    expect(options[1]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowUp}");
    expect(box).toHaveAttribute("aria-activedescendant", options[0].id);
    await user.keyboard("{Enter}");
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ key: "example-village", name: "EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION", county: "placer" }));
    expect(urls.every((u) => !u.includes("/write/"))).toBe(true);

    // The chosen row: its spellings behind a disclosure, and a way back to the search.
    await user.click(screen.getByText("2 spellings in the index"));
    expect(screen.getByText("EXAMPLE VILLAGE HOA")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Choose another" }));
    expect(await screen.findByRole("combobox", { name: "Association's name" })).toHaveFocus();
  });

  it("closes the list with Escape and chooses with a click", async () => {
    stub(() => directory);
    const onPick = vi.fn();
    render(<AssociationPicker onPick={onPick} debounceMs={0} />);
    const box = screen.getByRole("combobox");
    await screen.findByText("EXAMPLE OAKS OWNERS ASSN");
    const user = userEvent.setup();
    await user.click(box);
    await user.keyboard("{Escape}");
    expect(box).toHaveAttribute("aria-expanded", "false");
    await user.keyboard("{ArrowDown}");
    expect(box).toHaveAttribute("aria-expanded", "true");
    await user.click(screen.getByText("EXAMPLE OAKS OWNERS ASSN"));
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ key: "example-oaks" }));
    expect(screen.getByText("Chosen from the Placer directory")).toBeInTheDocument();
  });

  it("says a search matched nothing, and shows the command for a county with no directory", async () => {
    stub((url) => url.includes("sacramento")
      ? { county: "sacramento", surveyed: false, results: [], caveats: [], command: "python -m asspy.associations_cli sacramento --survey 2001-01 YYYY-MM" }
      : { ...directory, results: [] });
    render(<AssociationPicker counties={["placer", "sacramento"]} onPick={() => {}} debounceMs={0} />);
    const user = userEvent.setup();
    await user.type(screen.getByRole("combobox", { name: "Association's name" }), "nothing");
    expect(await screen.findByText('No association in the Placer directory matches "nothing".')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("County"), "sacramento");
    expect(await screen.findByText("python -m asspy.associations_cli sacramento --survey 2001-01 YYYY-MM")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("The Sacramento directory is not built yet.");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
