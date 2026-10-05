import { ColorDetail } from "jason-ui";

// Made-up colors; the codes, names and hex values are invented.
const cream = { code: "SW 0001", maker: "sherwin-williams" as const, name: "Sample Cream", hex: "#F7F3E8", lrv: 82, status: "ok" as const };
const sand = { code: "SW 0002", maker: "sherwin-williams" as const, name: "Sample Sand", hex: "#D9C9A8", lrv: 58, status: "ok" as const };
const moss = { code: "SW 0003", maker: "sherwin-williams" as const, name: "Sample Moss", printedName: "Sample Fern", hex: "#6E7F5A", lrv: 21, status: "renamed" as const };
const clay = { code: "SW 0004", maker: "sherwin-williams" as const, name: "Sample Clay", hex: "#B5654A", lrv: 17, status: "ok" as const };
const slate = { code: "SW 0005", maker: "sherwin-williams" as const, name: "Sample Slate", hex: "#5C6B7A", lrv: 14, status: "discontinued" as const };
const ink = { code: "SW 0007", maker: "sherwin-williams" as const, name: "Sample Charcoal", hex: "#1F1F22", lrv: 3, status: "ok" as const };

/** A current color that was renamed since the schedule printed: its fetched description, family, the surfaces that use it,
 * and the maker's coordinating and similar colors as chips. */
export const RenamedWithDescription = () => (
  <ColorDetail
    detail={{
      color: moss,
      description: "A muted green with a gray undertone, for stucco and trim.",
      family: "Green",
      usedOn: ["STUCCO FIELD"],
      coordinating: [cream, sand, ink],
      similar: [slate, clay],
    }}
    onOpenColor={() => {}}
  />
);

/** A discontinued color has no description to fetch and offers the closest current colors instead, for a touch-up. */
export const Discontinued = () => (
  <ColorDetail
    detail={{ color: slate, family: "Blue", usedOn: ["STUCCO FIELD"], closestCurrent: [moss, ink] }}
    onOpenColor={() => {}}
  />
);

/** A current color the description has not been fetched for: the drawer says none is on file and offers to fetch it. */
export const NoDescriptionYet = () => (
  <ColorDetail
    detail={{ color: clay, family: "Red", usedOn: ["ENTRY DOORS", "GARAGE DOORS"], coordinating: [cream, sand], similar: [] }}
    onOpenColor={() => {}}
    onFetchDescription={() => {}}
  />
);
