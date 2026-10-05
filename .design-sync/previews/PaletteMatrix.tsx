import { useState } from "react";
import { PaletteMatrix } from "jason-ui";

// A made-up schedule: invented codes, names and hex values; no real association's palette.
const cream = { code: "SW 0001", maker: "sherwin-williams" as const, name: "Sample Cream", hex: "#F7F3E8", lrv: 82, status: "ok" as const };
const sand = { code: "SW 0002", maker: "sherwin-williams" as const, name: "Sample Sand", hex: "#D9C9A8", lrv: 58, status: "ok" as const };
const moss = { code: "SW 0003", maker: "sherwin-williams" as const, name: "Sample Moss", printedName: "Sample Fern", hex: "#6E7F5A", lrv: 21, status: "renamed" as const };
const clay = { code: "SW 0004", maker: "sherwin-williams" as const, name: "Sample Clay", hex: "#B5654A", lrv: 17, status: "ok" as const };
const slate = { code: "SW 0005", maker: "sherwin-williams" as const, name: "Sample Slate", hex: "#5C6B7A", lrv: 14, status: "discontinued" as const };
const ink = { code: "SW 0007", maker: "sherwin-williams" as const, name: "Sample Charcoal", hex: "#1F1F22", lrv: 3, status: "ok" as const };
const brick = { code: "OM 0001", maker: "other" as const, name: "Sample Brick", hex: "#8A3B2E", status: "not checked" as const, entered: true };

const source = { address: "file:paint/sample-schedule.pdf", document: "pdf", name: "Sample exterior color schedule", kind: "pdf" as const, level: "P0" as const, source: "Scan" };

const schedule = {
  title: "Exterior palette",
  source,
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

const today = new Date("2099-10-04T12:00:00");

/** The palette as the schedule prints it: surfaces down the side, schemes across, the scheme toggle above. */
export const AllSchemes = () => {
  const [scheme, setScheme] = useState<number | null>(null);
  return <PaletteMatrix schedule={schedule} scheme={scheme} onSchemeChange={setScheme} onOpenColor={() => {}} today={today} />;
};

/** One scheme at a time: the same rows, one column. A row with no paint (a roof tile) says so. */
export const OneScheme = () => {
  const [scheme, setScheme] = useState<number | null>(2);
  return <PaletteMatrix schedule={schedule} scheme={scheme} onSchemeChange={setScheme} onOpenColor={() => {}} today={today} />;
};

/** The maker's catalog cannot be reached: the copy kept on disk is shown, with its age. */
export const CatalogUnavailable = () => (
  <PaletteMatrix schedule={{ ...schedule, unavailable: true }} scheme={1} onSchemeChange={() => {}} onOpenColor={() => {}} today={today} />
);

/** No copy on disk either: colors are shown as last checked, and the screen says there is nothing newer. */
export const NoCatalogCopy = () => (
  <PaletteMatrix schedule={{ ...schedule, unavailable: true, catalogFetched: "" }} scheme={1} onSchemeChange={() => {}} onOpenColor={() => {}} today={today} />
);
