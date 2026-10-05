import { Badge, type Tone } from "./Badge";
import type { GlyphName } from "./Glyph";

/** One paint color as the schedule and the maker's catalog give it (docs/console/handoff-unit-records.md). */
export interface PaintColor {
  /** "SW 7008", or another maker's code. */
  code: string;
  maker: "sherwin-williams" | "other";
  /** The current name. */
  name: string;
  /** As the schedule printed it, when it differs. */
  printedName?: string;
  /** The catalog color, "#EDEAE0"; never sampled from a scan or a photo. */
  hex: string;
  /** Light reflectance value. */
  lrv?: number;
  status: "ok" | "renamed" | "discontinued" | "not found" | "not checked";
  /** The hex was typed by a person, not looked up. */
  entered?: boolean;
}

export type SwatchSize = "chip" | "tile" | "card";

/** The word for each status. The word is the status; the fill, the glyph and the tone only repeat it. */
export const PAINT_STATUS_WORDS: Readonly<Record<PaintColor["status"], string>> = {
  ok: "current",
  renamed: "renamed",
  discontinued: "discontinued",
  "not found": "not found",
  "not checked": "not checked",
};
export const ENTERED_WORD = "entered, not checked";

const STATUS_MEANING: Record<PaintColor["status"], string> = {
  ok: "The maker's catalog lists this code under this name.",
  renamed: "The maker's catalog lists this code under another name than the schedule printed.",
  discontinued: "The maker's catalog no longer lists this code.",
  "not found": "The code is not in the maker's catalog.",
  "not checked": "The color has not been checked against the maker's catalog.",
};
const STATUS_TONE: Record<PaintColor["status"], Tone> = { ok: "good", renamed: "warn", discontinued: "bad", "not found": "warn", "not checked": "neutral" };
const STATUS_GLYPH: Record<PaintColor["status"], GlyphName> = {
  ok: "circle-check", renamed: "pencil", discontinued: "ban", "not found": "circle-question-mark", "not checked": "circle-dashed",
};

// --- contrast ------------------------------------------------------------------------------------------------------------

const BLACK = "#000000";
const WHITE = "#ffffff";

/** "#abc" or "#aabbcc" (with or without the hash) as [r, g, b], or null when it is not a hex color. */
export function parseHex(hex: string | null | undefined): [number, number, number] | null {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec((hex ?? "").trim());
  if (!m) return null;
  let h = m[1];
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** WCAG relative luminance, 0 (black) to 1 (white). A value that is not a color reads as white paper. */
export function luminance(hex: string): number {
  const rgb = parseHex(hex);
  if (!rgb) return 1;
  const [r, g, b] = rgb.map((v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio of two colors, 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const la = luminance(a), lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** The ink for text on a fill: black or white, whichever contrasts more. With pure black and white the worst case (a mid
 * tone) is 4.58:1, so text on every swatch meets 4.5:1 (WCAG 1.4.3). */
export function inkFor(hex: string): string {
  return contrastRatio(hex, BLACK) >= contrastRatio(hex, WHITE) ? BLACK : WHITE;
}

const upperHex = (hex: string) => { const rgb = parseHex(hex); return rgb ? `#${rgb.map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase()}` : ""; };

/** The status as a person reads it: the status word, or "entered, not checked" for a hex a person typed. */
export function swatchWord(color: PaintColor): string {
  return color.entered ? ENTERED_WORD : PAINT_STATUS_WORDS[color.status];
}

/** A color's status line for a finding: "SW 0003 Sample Moss: renamed. The schedule printed it as Sample Fern." */
export function driftText(color: PaintColor): string | null {
  if (color.entered) return `${color.code} ${color.name}: ${ENTERED_WORD}.`;
  if (color.status === "ok") return null;
  const head = `${color.code} ${color.name}: ${PAINT_STATUS_WORDS[color.status]}.`;
  return color.status === "renamed" && color.printedName ? `${head} The schedule printed it as ${color.printedName}.` : head;
}

/** A paint color: the maker's catalog color as the fill, with the code and the name as text on it (chip: beside it), the
 * status as a word, and the printed name beside the current one when the maker renamed it. The fill is the catalog's hex, or
 * the hex a person typed, labeled "entered, not checked"; it is never a color from a photo. `onOpen` makes the swatch a
 * button (a color's detail opens from any swatch). */
export function Swatch({ color, size = "card", onOpen, showStatus }: {
  color: PaintColor; size?: SwatchSize; onOpen?: (color: PaintColor) => void;
  /** Show the status word for a current color too (default: only when it is not current, except at tile and card size). */
  showStatus?: boolean;
}) {
  const fill = upperHex(color.hex);
  const ink = fill ? inkFor(fill) : undefined;
  const word = swatchWord(color);
  const flagged = color.entered || color.status !== "ok";
  const tone: Tone = color.entered ? "neutral" : STATUS_TONE[color.status];
  const glyph: GlyphName = color.entered ? "pencil" : STATUS_GLYPH[color.status];
  const meaning = color.entered ? "A person typed this color; it was not looked up in the maker's catalog." : STATUS_MEANING[color.status];
  const printed = color.status === "renamed" && color.printedName && color.printedName !== color.name ? color.printedName : null;
  const wordShown = showStatus ?? (size !== "chip" || flagged);
  const fillStyle = fill ? { background: fill, color: ink } : undefined;

  const body = (
    <>
      <span className={`swatch-fill${fill ? "" : " swatch-nofill"}`} style={fillStyle} data-ink={ink} data-hex={fill || undefined}>
        {size !== "chip" && (
          <>
            <span className="swatch-code">{color.code}</span>
            <span className="swatch-name">{color.name}</span>
          </>
        )}
      </span>
      <span className="swatch-text">
        {size === "chip" && (
          <>
            <span className="swatch-code">{color.code}</span>{" "}
            <span className="swatch-name">{color.name}</span>
          </>
        )}
        {printed && <span className="swatch-printed">printed as {printed}</span>}
        {!fill && <span className="swatch-printed">no catalog color</span>}
        {color.entered && fill && <span className="swatch-hex">{fill}</span>}
        {wordShown && (
          <span className="swatch-status" title={meaning}>
            <Badge tone={tone} glyph={glyph}>{word}</Badge>
          </span>
        )}
      </span>
    </>
  );
  const cls = `swatch swatch-${size}${flagged ? " swatch-flagged" : ""}`;
  if (onOpen) {
    return <button type="button" className={cls} onClick={() => onOpen(color)} data-status={color.status}>{body}</button>;
  }
  return <span className={cls} data-status={color.status}>{body}</span>;
}
