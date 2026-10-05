import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ColorDetail, PaletteMatrix, SourcedDate, Swatch, contrastRatio, inkFor, luminance, PAINT_CAPTION, TOUCH_UP_CAVEAT } from "./index";
import { brick, clay, cream, dates, detail, discontinuedDetail, ink, lost, moss, schedule, slate, unavailableNoCopy, unavailableSchedule } from "./paint.fixture";

describe("luminance ink", () => {
  it("is black on a very light swatch and white on a very dark one, each at 4.5:1 or better", () => {
    expect(inkFor("#F7F3E8")).toBe("#000000");
    expect(inkFor("#1F1F22")).toBe("#ffffff");
    expect(contrastRatio("#F7F3E8", inkFor("#F7F3E8"))).toBeGreaterThan(4.5);
    expect(contrastRatio("#1F1F22", inkFor("#1F1F22"))).toBeGreaterThan(4.5);
  });
  it("holds 4.5:1 across every gray, including the mid tones", () => {
    for (let v = 0; v < 256; v++) {
      const hex = `#${v.toString(16).padStart(2, "0").repeat(3)}`;
      expect(contrastRatio(hex, inkFor(hex))).toBeGreaterThanOrEqual(4.5);
    }
    expect(luminance("#000000")).toBe(0);
  });
  it("sets the ink on the rendered fill", () => {
    render(<><Swatch color={cream} /><Swatch color={ink} /></>);
    const fills = document.querySelectorAll<HTMLElement>(".swatch-fill");
    expect(fills[0].dataset.ink).toBe("#000000");
    expect(fills[1].dataset.ink).toBe("#ffffff");
    expect(fills[0].style.background).toMatch(/rgb\(247, 243, 232\)|#f7f3e8/i);
  });
});

describe("Swatch", () => {
  it("carries the code and the name as text at every size", () => {
    for (const size of ["chip", "tile", "card"] as const) {
      const { unmount } = render(<Swatch color={cream} size={size} />);
      expect(screen.getByText("SW 0001")).toBeInTheDocument();
      expect(screen.getByText("Sample Cream")).toBeInTheDocument();
      unmount();
    }
  });
  it("says each status in words", () => {
    const words: [typeof cream, string][] = [[cream, "current"], [moss, "renamed"], [slate, "discontinued"], [lost, "not found"], [{ ...cream, status: "not checked" }, "not checked"]];
    for (const [color, word] of words) {
      const { unmount } = render(<Swatch color={color} size="tile" />);
      expect(screen.getByText(word)).toBeInTheDocument();
      unmount();
    }
  });
  it("shows the printed name beside the current one when renamed", () => {
    render(<Swatch color={moss} />);
    expect(screen.getByText("Sample Moss")).toBeInTheDocument();
    expect(screen.getByText("printed as Sample Fern")).toBeInTheDocument();
  });
  it("flags a hand-entered color as entered, not checked, and fills with the typed hex", () => {
    render(<Swatch color={brick} />);
    expect(screen.getByText("entered, not checked")).toBeInTheDocument();
    expect(screen.getByText("#8A3B2E")).toBeInTheDocument();
  });
  it("draws no fill for a color the catalog does not have", () => {
    render(<Swatch color={lost} />);
    expect(document.querySelector(".swatch-fill")).toHaveClass("swatch-nofill");
    expect(screen.getByText("no catalog color")).toBeInTheDocument();
  });
  it("is a button that opens the color when given onOpen", async () => {
    const onOpen = vi.fn();
    render(<Swatch color={clay} onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: /SW 0004/ }));
    expect(onOpen).toHaveBeenCalledWith(clay);
  });
});

describe("PaletteMatrix", () => {
  it("is a table with column and row headers in the schedule's printed words", () => {
    render(<PaletteMatrix schedule={schedule} />);
    const table = screen.getByRole("table");
    const cols = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(cols).toEqual(["Surface", "Scheme 1", "Scheme 2", "Scheme 3"]);
    for (const h of within(table).getAllByRole("columnheader")) expect(h).toHaveAttribute("scope", "col");
    const rows = within(table).getAllByRole("rowheader");
    expect(rows.map((h) => h.textContent)).toEqual(expect.arrayContaining(["FASCIA", "ENTRY DOORS"].map((s) => expect.stringContaining(s))));
    for (const h of rows) expect(h).toHaveAttribute("scope", "row");
  });
  it("puts a swatch with its code and name as text in each scheduled cell", () => {
    render(<PaletteMatrix schedule={schedule} />);
    const table = screen.getByRole("table");
    expect(within(table).getAllByText("Sample Cream").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("SW 0004").length).toBe(2);
  });
  it("renders a row with no paint as text", () => {
    render(<PaletteMatrix schedule={schedule} />);
    expect(screen.getByText("tile, not paint")).toBeInTheDocument();
  });
  it("flags drift in words, and shows both names for the renamed color", () => {
    render(<PaletteMatrix schedule={schedule} />);
    expect(screen.getByText(/SW 0003 Sample Moss: renamed\. The schedule printed it as Sample Fern\./)).toBeInTheDocument();
    expect(screen.getByText(/SW 0005 Sample Slate: discontinued\./)).toBeInTheDocument();
    expect(screen.getByText(/OM 0001 Sample Brick: entered, not checked\./)).toBeInTheDocument();
    expect(screen.getAllByText("printed as Sample Fern").length).toBeGreaterThan(0);
  });
  it("switches the visible columns with the scheme radio group", async () => {
    render(<PaletteMatrix schedule={schedule} />);
    const group = screen.getByRole("group", { name: "Scheme" });
    expect(within(group).getAllByRole("radio")).toHaveLength(4);
    expect(screen.getByRole("columnheader", { name: "Scheme 3" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Scheme 2" }));
    expect(screen.getByRole("columnheader", { name: "Scheme 2" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Scheme 1" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Scheme 3" })).not.toBeInTheDocument();
    // the other schemes' cells stay in the table, hidden, so print shows every scheme
    expect(screen.getByText("Sample Slate").closest("td")).toHaveAttribute("hidden");
    expect(screen.getByRole("table")).not.toHaveTextContent("Sample Slate".repeat(2));
    expect(screen.queryByRole("cell", { name: /Sample Slate/ })).not.toBeInTheDocument();
    expect(screen.getByRole("cell", { name: /Sample Moss/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "All schemes" }));
    expect(screen.getByRole("columnheader", { name: "Scheme 3" })).toBeInTheDocument();
  });
  it("can be controlled", async () => {
    const onSchemeChange = vi.fn();
    render(<PaletteMatrix schedule={schedule} scheme={1} onSchemeChange={onSchemeChange} />);
    expect(screen.queryByRole("columnheader", { name: "Scheme 2" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Scheme 3" }));
    expect(onSchemeChange).toHaveBeenCalledWith(3);
  });
  it("says the number on the schedule governs", () => {
    render(<PaletteMatrix schedule={schedule} />);
    expect(screen.getByText(PAINT_CAPTION)).toBeInTheDocument();
    expect(PAINT_CAPTION).toBe("Screens and printers shift color. The number on the schedule governs.");
  });
  it("invites when there is no schedule", () => {
    render(<PaletteMatrix schedule={null} />);
    expect(screen.getByText("The association has no color schedule yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
  it("states the copy's age when the catalog is unavailable, and the command when there is no copy", () => {
    const { unmount } = render(<PaletteMatrix schedule={unavailableSchedule} today={new Date("2099-10-04T12:00:00")} />);
    expect(screen.getByRole("status")).toHaveTextContent(/catalog is unavailable.*3 days old/);
    expect(screen.getByRole("table")).toBeInTheDocument();
    unmount();
    render(<PaletteMatrix schedule={unavailableNoCopy} />);
    expect(screen.getByRole("status")).toHaveTextContent(/no copy is kept on disk/);
    expect(screen.getByText("jason paint --refresh")).toBeInTheDocument();
  });
});

describe("SourcedDate", () => {
  it("says recorded, with its document", () => {
    render(<SourcedDate value={dates.recorded} />);
    expect(screen.getByText("recorded")).toBeInTheDocument();
    expect(screen.getByText("Jun 12, 2099")).toBeInTheDocument();
    expect(document.querySelector("time")).toHaveAttribute("datetime", "2099-06-12");
    expect(screen.getByText(/Sample painting invoice/)).toBeInTheDocument();
  });
  it("says implied and shows its arithmetic", () => {
    render(<SourcedDate value={dates.implied} />);
    expect(screen.getByText("implied")).toBeInTheDocument();
    expect(screen.getByText(/due 2099 minus a 7-year life/)).toBeInTheDocument();
  });
  it("says reported with a count, apart from the association's record", () => {
    render(<SourcedDate value={dates.reported} />);
    expect(screen.getByText("reported by 3 owners")).toBeInTheDocument();
    expect(screen.getByText(/not the association's record/)).toBeInTheDocument();
  });
  it("invites when it needs input", async () => {
    const onEnter = vi.fn();
    render(<SourcedDate value={dates.needsInput} onEnter={onEnter} />);
    expect(screen.getByText("needs input")).toBeInTheDocument();
    expect(screen.getByText(/Add the date with its source/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enter the date" }));
    expect(onEnter).toHaveBeenCalled();
  });
});

describe("ColorDetail", () => {
  it("shows the swatch, description, reflectance, family, use and chips, with the touch-up caveat", () => {
    render(<ColorDetail detail={detail} />);
    expect(screen.getByRole("heading", { name: "SW 0003 Sample Moss" })).toBeInTheDocument();
    expect(screen.getByText(/muted green/)).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
    expect(screen.getByText("Green")).toBeInTheDocument();
    expect(screen.getByText("STUCCO FIELD")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Coordinating colors" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Similar colors" })).toBeInTheDocument();
    expect(screen.getByText(TOUCH_UP_CAVEAT)).toBeInTheDocument();
    expect(TOUCH_UP_CAVEAT).toBe("A touch-up on aged paint may not match the code.");
  });
  it("offers the closest current colors for a discontinued color, and the description fetch on a click", async () => {
    const onFetch = vi.fn();
    render(<ColorDetail detail={discontinuedDetail} onFetchDescription={onFetch} />);
    expect(screen.getByRole("heading", { name: "Closest current colors" })).toBeInTheDocument();
    expect(screen.getByText("discontinued")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fetch the description" }));
    expect(onFetch).toHaveBeenCalled();
  });
  it("opens a chip's own detail", async () => {
    const onOpenColor = vi.fn();
    render(<ColorDetail detail={detail} onOpenColor={onOpenColor} />);
    await userEvent.click(screen.getByRole("button", { name: /SW 0001/ }));
    expect(onOpenColor).toHaveBeenCalledWith(cream);
  });
});
