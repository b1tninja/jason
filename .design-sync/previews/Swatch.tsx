import { Swatch } from "jason-ui";

// Made-up colors; the codes, names and hex values are invented.
const cream = { code: "SW 0001", maker: "sherwin-williams" as const, name: "Sample Cream", hex: "#F7F3E8", lrv: 82, status: "ok" as const };
const moss = { code: "SW 0003", maker: "sherwin-williams" as const, name: "Sample Moss", printedName: "Sample Fern", hex: "#6E7F5A", lrv: 21, status: "renamed" as const };
const slate = { code: "SW 0005", maker: "sherwin-williams" as const, name: "Sample Slate", hex: "#5C6B7A", lrv: 14, status: "discontinued" as const };
const brick = { code: "OM 0001", maker: "other" as const, name: "Sample Brick", hex: "#8A3B2E", status: "not checked" as const, entered: true };
const lost = { code: "SW 9999", maker: "sherwin-williams" as const, name: "Sample Mystery", hex: "", status: "not found" as const };

/** The five statuses in a row at card size: every status is a word and a glyph, never color alone. */
export const Statuses = () => (
  <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
    {[cream, moss, slate, brick, lost].map((c) => <Swatch key={c.code} color={c} showStatus />)}
  </div>
);

/** Sizes: the card is the palette's default; the tile fits a detail drawer; the chip fits a row of related colors. */
export const Sizes = () => (
  <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
    <Swatch color={cream} size="card" />
    <Swatch color={moss} size="tile" />
    <Swatch color={slate} size="chip" />
    <Swatch color={cream} size="chip" />
  </div>
);

/** A renamed color shows the printed name beside the current one, so a person can still find it on the old schedule. */
export const Renamed = () => <Swatch color={moss} showStatus />;
