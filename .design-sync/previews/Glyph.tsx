import { GLYPHS, GLYPH_META, Glyph, type GlyphName } from "jason-ui";

const row = { display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" } as const;
const label = { display: "inline-flex", gap: 6, alignItems: "center", fontSize: 14 } as const;

/** Beside its word, always: the glyph is decoration and the word is the label. 16px inline and in table cells. */
export const BesideItsWord = () => (
  <div style={row}>
    {(["info", "clock", "triangle-alert", "octagon-alert", "circle-check", "circle-dashed", "circle-question-mark"] as GlyphName[]).map((n) => {
      const m = GLYPH_META.find((x) => x.name === n)!;
      return <span key={n} style={label}><Glyph name={n} size="16px" />{m.label}</span>;
    })}
  </div>
);

/** Sizes: 16 inline, 20 in nav and buttons, 24 in headers, 32 only in empty states. The stroke thins as it grows. */
export const Sizes = () => (
  <div style={{ ...row, alignItems: "end" }}>
    {["16px", "20px", "24px", "32px"].map((s) => <span key={s} style={{ display: "grid", justifyItems: "center", gap: 4, fontSize: 12 }}><Glyph name="gavel" size={s} />{s}</span>)}
  </div>
);

/** Standing alone (an icon-only Close): then, and only then, `label` names it. */
export const Labelled = () => (
  <div style={row}>
    <button type="button" aria-label="Close" style={{ display: "inline-grid", placeItems: "center", width: 32, height: 32, padding: 0 }}><Glyph name="x" size="20px" label="Close" /></button>
    <button type="button"><span style={label}><Glyph name="refresh-cw" size="16px" />Read again</span></button>
  </div>
);

/** jason's own glyphs for what Lucide has no single icon for, on the same grid. */
export const JasonsOwn = () => (
  <div style={row}>
    {(["assessment", "lien", "reserve", "minutes", "notice", "open-meeting", "exec-session", "ledger", "reconcile", "unit", "owner", "common-area", "board", "quorum", "rollcall", "proposal", "cosign"] as GlyphName[]).map((n) => (
      <span key={n} style={label}><Glyph name={n} size="20px" />{GLYPH_META.find((x) => x.name === n)?.label ?? n}</span>
    ))}
  </div>
);

/** The whole set, by name (the catalog is GLYPH_META: one meaning per glyph). */
export const EveryGlyph = () => (
  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(28px, 1fr))", gap: 6, maxWidth: 960 }}>
    {(Object.keys(GLYPHS) as GlyphName[]).map((n) => <span key={n} title={n} style={{ display: "grid", placeItems: "center", height: 28 }}><Glyph name={n} size="16px" /></span>)}
  </div>
);
