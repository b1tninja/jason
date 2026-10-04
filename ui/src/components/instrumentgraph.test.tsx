import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { InstrumentGraph, OwnerNames, layout, type InstrumentGraphData } from "./InstrumentGraph";

const data: InstrumentGraphData = {
  found: true,
  view: "shared",
  nodes: [
    { id: "parcel:1", type: "parcel", label: "000-0000-000-0001", apn: "000-0000-000-0001", unit: "12" },
    { id: "inst:example:2001-0000010", type: "instrument", label: "2001-0000010", number: "2001-0000010", recorded: "2001-03-01", role: "declaration", supersededBy: "2001-0000020" },
    { id: "inst:example:2001-0000020", type: "instrument", label: "2001-0000020", number: "2001-0000020", recorded: "2001-03-08", role: "restated declaration" },
    { id: "inst:example:2003-0000050", type: "instrument", label: "2003-0000050", number: "2003-0000050", recorded: "2003-06-01", role: "annexation", phase: 2 },
    { id: "party:association", type: "party", label: "the association", partyKind: "association" },
  ],
  edges: [
    { id: "e0", kind: "supersedes", family: "governing", source: "inst:example:2001-0000020", target: "inst:example:2001-0000010", lead: false,
      meaning: "rescinded and superseded this instrument", provenance: { rule: "spec.supersession", store: "specification", lead: false, note: "recital F" } },
    { id: "e1", kind: "annexes", family: "governing", source: "inst:example:2003-0000050", target: "inst:example:2001-0000020", lead: true,
      meaning: "annexes property under this declaration", provenance: { rule: "governing.role", store: "association record", lead: true, note: "by its role" } },
    { id: "e2", kind: "covers", family: "governing", source: "inst:example:2003-0000050", target: "parcel:1", lead: true,
      provenance: { rule: "spec.phase", store: "public reports", lead: true } },
  ],
  cycles: [{ family: "citation", kind: "cites", source: "inst:example:2001-0000010", target: "inst:example:2001-0000020", rule: "index.cross-reference", path: [] }],
  notes: ["2 private person(s) left out of the shared view, with their edges"],
  caveats: ["A dotted edge is a lead."],
  mermaid: "flowchart LR\n  a --> b",
};

describe("InstrumentGraph", () => {
  it("lays parcels, years, and parties out in columns", () => {
    const at = layout(data.nodes);
    expect(at.get("parcel:1")!.x).toBeLessThan(at.get("inst:example:2001-0000010")!.x);
    expect(at.get("inst:example:2001-0000010")!.x).toBe(at.get("inst:example:2001-0000020")!.x);   // one year, one column
    expect(at.get("inst:example:2003-0000050")!.x).toBeGreaterThan(at.get("inst:example:2001-0000020")!.x);
    expect(at.get("party:association")!.x).toBeGreaterThan(at.get("inst:example:2003-0000050")!.x);
  });

  it("lists every node for the keyboard and shows an edge's provenance on focus", async () => {
    const user = userEvent.setup();
    render(<InstrumentGraph data={data} />);
    const list = screen.getByRole("navigation", { name: "Nodes" });
    await user.click(within(list).getByRole("button", { name: "2001-0000020" }));
    const chosen = screen.getByRole("region", { name: "Chosen node" });
    const supersedes = within(chosen).getByRole("button", { name: "supersedes → 2001-0000010" });
    supersedes.focus();
    const provenance = await within(chosen).findByRole("status");
    expect(provenance).toHaveTextContent("spec.supersession from specification: recital F");
    expect(provenance).toHaveTextContent("firm");
    within(chosen).getByRole("button", { name: "2003-0000050 annexes → this" }).focus();
    expect(await within(chosen).findByRole("status")).toHaveTextContent("lead");
  });

  it("filters by family, reports the cycles left out, and says what the view holds", async () => {
    const user = userEvent.setup();
    render(<InstrumentGraph data={data} />);
    expect(screen.getByText("Shared view: no private person")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("1 edge left out");
    expect(screen.getByRole("img")).toHaveAccessibleName("5 nodes and 3 edges");
    await user.click(screen.getByLabelText("governing"));
    expect(screen.getByRole("img")).toHaveAccessibleName("5 nodes and 0 edges");
    expect(screen.getByText("A dotted edge is a lead.")).toBeInTheDocument();
  });

  it("shows a private person by role when masked, and by name only when the names were asked for", () => {
    const owner = { id: "person:abc", type: "party" as const, label: "owner, unit 12", partyKind: "private" };
    const { unmount } = render(<InstrumentGraph data={{ ...data, view: "private", nodes: [...data.nodes, owner] }} />);
    expect(screen.getByText("Private view: owners labeled by role and parcel")).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Nodes" })).getByRole("button", { name: "owner, unit 12" })).toBeInTheDocument();
    unmount();
    render(<InstrumentGraph data={{ ...data, view: "private", names: true, nodes: [...data.nodes, { ...owner, names: ["EXAMPLE OWNER A"] }] }} />);
    expect(screen.getByText("Private view: owners' names shown")).toBeInTheDocument();
    const list = screen.getByRole("navigation", { name: "Nodes" });
    expect(within(list).getByRole("button", { name: "EXAMPLE OWNER A" })).toBeInTheDocument();
    expect(within(list).getByText("owner, unit 12 · private")).toBeInTheDocument();
  });

  it("asks for a person's name before showing owners' names, and says the reveal was logged", async () => {
    const user = userEvent.setup();
    const shows: string[] = [];
    let hidden = 0;
    const { rerender } = render(<OwnerNames shown={false} me="" onShow={(by) => shows.push(by)} onHide={() => { hidden += 1; }} />);
    await user.click(screen.getByRole("button", { name: "Show owners' names" }));
    const form = screen.getByRole("form", { name: "Show owners' names" });
    await user.click(within(form).getByRole("button", { name: "Show names" }));
    expect(shows).toEqual([]);
    expect(within(form).getByText("Enter your name: each reveal is logged with it.")).toBeInTheDocument();
    await user.type(within(form).getByLabelText("Your name"), "jason");
    await user.click(within(form).getByRole("button", { name: "Show names" }));
    expect(shows).toEqual([]);
    await user.clear(within(form).getByLabelText("Your name"));
    await user.type(within(form).getByLabelText("Your name"), "  Jane   Example ");
    await user.click(within(form).getByRole("button", { name: "Show names" }));
    expect(shows).toEqual(["Jane Example"]);
    rerender(<OwnerNames shown me="" reveal={{ at: "2026-10-03T12:00:00+00:00", by: "Jane Example", named: 2, log: "console/reveals.jsonl" }}
      onShow={(by) => shows.push(by)} onHide={() => { hidden += 1; }} />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Owners' names are shown, asked by Jane Example");
    expect(status).toHaveTextContent("The reveal was logged in data/console/reveals.jsonl. 2 persons named.");
    await user.click(screen.getByRole("button", { name: "Hide names" }));
    expect(hidden).toBe(1);
  });

  it("fills the name with the console's person", async () => {
    const user = userEvent.setup();
    const shows: string[] = [];
    render(<OwnerNames shown={false} me="Casey Sample" onShow={(by) => shows.push(by)} onHide={() => undefined} />);
    await user.click(screen.getByRole("button", { name: "Show owners' names" }));
    expect(screen.getByLabelText("Your name")).toHaveValue("Casey Sample");
    await user.click(screen.getByRole("button", { name: "Show names" }));
    expect(shows).toEqual(["Casey Sample"]);
  });

  it("says so when there is nothing to draw", () => {
    render(<InstrumentGraph data={{ found: false, note: "no ownership store on disk", nodes: [], edges: [] }} />);
    expect(screen.getByText("no ownership store on disk")).toBeInTheDocument();
  });
});
