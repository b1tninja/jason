import type { DocRef } from "../lib/docref";
import type { PaintColorDetail } from "./ColorDetail";
import type { PaintSchedule } from "./PaletteMatrix";
import type { SourcedDate } from "./SourcedDate";
import type { PaintColor } from "./Swatch";

/* Made-up colors and a made-up schedule. No real association's palette: names, codes and hex values are invented. */

export const cream: PaintColor = { code: "SW 0001", maker: "sherwin-williams", name: "Sample Cream", hex: "#F7F3E8", lrv: 82, status: "ok" };
export const sand: PaintColor = { code: "SW 0002", maker: "sherwin-williams", name: "Sample Sand", hex: "#D9C9A8", lrv: 58, status: "ok" };
export const moss: PaintColor = { code: "SW 0003", maker: "sherwin-williams", name: "Sample Moss", printedName: "Sample Fern", hex: "#6E7F5A", lrv: 21, status: "renamed" };
export const clay: PaintColor = { code: "SW 0004", maker: "sherwin-williams", name: "Sample Clay", hex: "#B5654A", lrv: 17, status: "ok" };
export const slate: PaintColor = { code: "SW 0005", maker: "sherwin-williams", name: "Sample Slate", hex: "#5C6B7A", lrv: 14, status: "discontinued" };
export const ink: PaintColor = { code: "SW 0007", maker: "sherwin-williams", name: "Sample Charcoal", hex: "#1F1F22", lrv: 3, status: "ok" };
export const brick: PaintColor = { code: "OM 0001", maker: "other", name: "Sample Brick", hex: "#8A3B2E", status: "not checked", entered: true };
export const lost: PaintColor = { code: "SW 9999", maker: "sherwin-williams", name: "Sample Mystery", hex: "", status: "not found" };

export const scheduleDoc: DocRef = {
  address: "file:paint/sample-schedule.pdf", document: "pdf", name: "Sample exterior color schedule", kind: "pdf", level: "P0", source: "Scan",
};

/** Five surfaces and a roof tile row, three schemes, one renamed color, one discontinued, one from another maker. */
export const schedule: PaintSchedule = {
  title: "Exterior palette",
  source: scheduleDoc,
  prepared: "Prepared for the developer, 2099-01-15",
  schemes: [1, 2, 3],
  rows: [
    { label: "FASCIA", surface: "Fascia", colors: { 1: cream } },
    { label: "TRIM", surface: "Trim", colors: { 1: cream, 2: cream, 3: sand } },
    { label: "STUCCO FIELD", surface: "Stucco field", colors: { 1: sand, 2: moss, 3: slate } },
    { label: "ENTRY DOORS", surface: "Entry doors", colors: { 1: clay, 3: brick } },
    { label: "GARAGE DOORS", surface: "Garage doors", colors: { 1: clay, 2: ink } },
    { label: "ROOF", surface: "Roof", note: "tile, not paint", colors: {} },
  ],
  catalogFetched: "2099-10-01",
};

/** The same schedule with no catalog reachable: a copy on disk, colors as last checked. */
export const unavailableSchedule: PaintSchedule = { ...schedule, unavailable: true };
export const unavailableNoCopy: PaintSchedule = { ...schedule, unavailable: true, catalogFetched: "" };

export const detail: PaintColorDetail = {
  color: moss,
  description: "A muted green with a gray undertone, for stucco and trim.",
  family: "Green",
  usedOn: ["STUCCO FIELD"],
  coordinating: [cream, sand, ink],
  similar: [slate, clay],
};

export const discontinuedDetail: PaintColorDetail = {
  color: slate,
  family: "Blue",
  usedOn: ["STUCCO FIELD"],
  closestCurrent: [moss, ink],
};

export const dates: Record<"recorded" | "implied" | "reported" | "needsInput", SourcedDate> = {
  recorded: { date: "2099-06-12", source: "recorded", docs: [{ address: "file:paint/sample-invoice.pdf", document: "pdf", name: "Sample painting invoice", kind: "pdf", level: "P1" }] },
  implied: { date: "2092", source: "implied", arithmetic: "due 2099 minus a 7-year life" },
  reported: { date: "2095", source: "reported", count: 3 },
  needsInput: { source: "needs input" },
};
