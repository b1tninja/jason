import { GLYPH_META, JASON_GLYPHS, LUCIDE_GLYPHS, LUCIDE_VERSION, type GlyphMeta } from "../lib/glyphData";

/** Every glyph by name: the Lucide subset (ISC, Lucide Contributors) and jason's own, bundled so nothing is fetched. */
export const GLYPHS: Readonly<Record<GlyphName, string>> = { ...LUCIDE_GLYPHS, ...JASON_GLYPHS };
export type GlyphName = keyof typeof LUCIDE_GLYPHS | keyof typeof JASON_GLYPHS;
/** jason's own glyphs (not Lucide's). */
export const JASON_GLYPH_NAMES = Object.keys(JASON_GLYPHS) as GlyphName[];
export { GLYPH_META, LUCIDE_VERSION, type GlyphMeta };

export function hasGlyph(name: string): name is GlyphName {
  return Object.prototype.hasOwnProperty.call(GLYPHS, name);
}

/** Stroke follows size so lines read the same weight: 2 up to 16px, 1.75 up to 24px, 1.5 above; 1.75 for a size not in px. */
export function strokeFor(size: string | number): number {
  const px = typeof size === "number" ? size : /^\s*[\d.]+px\s*$/.test(size) ? parseFloat(size) : NaN;
  if (Number.isNaN(px)) return 1.75;
  return px <= 16 ? 2 : px <= 24 ? 1.75 : 1.5;
}

const warned = new Set<string>();

export interface GlyphProps {
  name: GlyphName;
  /** A CSS length or pixels. 16px inline and in table cells, 20px in nav and buttons, 24px in headers, 32px only in empty states. */
  size?: string | number;
  /** Names a glyph that stands alone (an icon-only control's picture). Without it the glyph is decoration, hidden from
   * screen readers, and the word beside it is the label. */
  label?: string;
  stroke?: number;
  className?: string;
}

/** One glyph, one meaning (`GLYPH_META`), always beside its word; it inherits the text colour. A name that is not in
 * the set renders nothing and logs once. */
export function Glyph({ name, size = "1em", label, stroke, className }: GlyphProps) {
  const body = hasGlyph(name) ? GLYPHS[name] : undefined;
  if (!body) {
    if (!warned.has(name)) { warned.add(name); console.warn(`Glyph: no glyph named ${JSON.stringify(name)}`); }
    return null;
  }
  const s = typeof size === "number" ? `${size}px` : size;
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true as const };
  return (
    <svg className={className ? `glyph ${className}` : "glyph"} width={s} height={s} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke ?? strokeFor(size)} strokeLinecap="round" strokeLinejoin="round"
      focusable="false" data-glyph={name} {...a11y} dangerouslySetInnerHTML={{ __html: body }} />
  );
}
