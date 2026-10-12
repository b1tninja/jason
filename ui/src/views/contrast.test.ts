import { describe, expect, it } from "vitest";

/** The colour tokens' contrast (docs/pdf-splitter-accessibility.md, section 6.2; WCAG 1.4.3 text 4.5:1, 1.4.11 non-text 3:1), read from the
 * stylesheets themselves so a token changed there is measured here: the console's tokens (`styles.css`, light in `:root`, dark under
 * `prefers-color-scheme`) and the two the splitter adds (`split.css`, made of the console's with `color-mix`). */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

declare const process: { cwd(): string };
/** the stylesheets as files (vitest is run from `ui/`, or from the repository root; a `?raw` import of CSS is empty under vitest) */
const read = (name: string) => {
  const at = [join(process.cwd(), "src", name), join(process.cwd(), "ui", "src", name)].find(existsSync);
  if (!at) throw new Error(`cannot find ${name} from ${process.cwd()}`);
  return new TextDecoder().decode(readFileSync(at));
};
const STYLES = read("styles.css");
const SPLIT = read("views/split.css");

type Tokens = Record<string, string>;
function declarations(block: string): Tokens {
  const out: Tokens = {};
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
const light: Tokens = declarations(/:root\s*\{([^}]*)\}/.exec(STYLES)![1]);
const dark: Tokens = declarations(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}/.exec(STYLES)![1]);
const SCHEMES: [string, Tokens][] = [["light", light], ["dark", { ...light, ...dark }]];
/** the splitter's own tokens, as declared (`--split-field-line: color-mix(...)`), resolved against a scheme's */
const split = declarations(/\.split-view, \.skip-link \{([^}]*)\}/.exec(SPLIT)![1]);

type Rgb = [number, number, number];
function parse(value: string, t: Tokens): Rgb {
  const v = value.trim();
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(v);
  const hex = /^#([0-9a-f]{6})$/i.exec(short ? `#${short[1]}${short[1]}${short[2]}${short[2]}${short[3]}${short[3]}` : v);
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)) as Rgb;
  const ref = /^var\((--[\w-]+)\)$/.exec(v);
  if (ref) return parse(t[ref[1]] ?? split[ref[1]], t);
  const mix = /^color-mix\(in srgb,\s*(.+)\)$/.exec(v);
  if (mix) {
    const parts = splitTop(mix[1]);
    const one = (s: string): [Rgb, number | null] => {
      const m = /^(.*?)(?:\s+(\d+(?:\.\d+)?)%)?$/.exec(s.trim())!;
      return [parse(m[1], t), m[2] === undefined ? null : Number(m[2]) / 100];
    };
    const [a, pa] = one(parts[0]);
    const [b, pb] = one(parts[1]);
    const wa = pa ?? (pb === null ? 0.5 : 1 - pb);
    const wb = pb ?? 1 - wa;
    return [0, 1, 2].map((i) => Math.round((a[i] * wa + b[i] * wb) / (wa + wb))) as Rgb;
  }
  throw new Error(`cannot read the colour "${value}"`);
}
/** split a list at the commas that are not inside parentheses */
function splitTop(s: string): string[] {
  const out: string[] = [];
  let depth = 0, at = 0;
  for (let i = 0; i < s.length; i++) {
    if (s[i] === "(") depth++;
    else if (s[i] === ")") depth--;
    else if (s[i] === "," && depth === 0) { out.push(s.slice(at, i)); at = i + 1; }
  }
  out.push(s.slice(at));
  return out;
}

const lin = (c: number) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
const lum = (c: Rgb) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
/** WCAG contrast ratio of two colours */
export function ratio(a: Rgb, b: Rgb): number { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
const over = (fg: Rgb, bg: Rgb, share: number): Rgb => [0, 1, 2].map((i) => Math.round(fg[i] * share + bg[i] * (1 - share))) as Rgb;
const SURFACES = ["--panel", "--paper", "--bg"];

/** `:root .badge { background: color-mix(in srgb, currentColor 11%, transparent) }`: the tint is the text colour's 11% over what is behind it */
const TINT = (() => {
  const m = /:root \.badge \{[^}]*background: color-mix\(in srgb, currentColor (\d+)%, transparent\)/.exec(STYLES);
  if (!m) throw new Error("the console's badge tint rule changed: read it again");
  return Number(m[1]) / 100;
})();

describe("the console's tokens", () => {
  for (const [scheme, t] of SCHEMES) {
    it(`text tokens meet 4.5:1 on every surface, ${scheme}`, () => {
      for (const ink of ["--ink", "--muted"]) for (const s of SURFACES) {
        expect(ratio(parse(`var(${ink})`, t), parse(`var(${s})`, t)), `${ink} on ${s}`).toBeGreaterThanOrEqual(4.5);
      }
    });
    it(`status colours meet 4.5:1 on the panel, ${scheme}`, () => {
      for (const c of ["--good", "--warn", "--bad"]) expect(ratio(parse(`var(${c})`, t), parse("var(--panel)", t)), c).toBeGreaterThanOrEqual(4.5);
    });
    it(`focus and selection colours meet 3:1 on the panel, the paper, and the page, ${scheme}`, () => {
      for (const c of ["--accent", "--ink"]) for (const s of SURFACES) {
        expect(ratio(parse(`var(${c})`, t), parse(`var(${s})`, t)), `${c} on ${s}`).toBeGreaterThanOrEqual(3);
      }
    });
  }
});

describe("the splitter's badges and fields", () => {
  it("the console's good and warning badge text reaches only about 4:1 on the page's grey, which is why the splitter mixes in the ink", () => {
    const t = light;
    for (const c of ["--good", "--warn"]) {
      const fg = parse(`var(${c})`, t);
      expect(ratio(fg, over(fg, parse("var(--bg)", t), TINT)), `${c} on the page`).toBeLessThan(4.5);
    }
  });

  for (const [scheme, t] of SCHEMES) {
    it(`badge text meets 4.5:1 on its tint, on every surface, ${scheme}`, () => {
      const inks: [string, Rgb][] = [
        ["good", parse(split["--split-good-ink"], t)], ["warn", parse(split["--split-warn-ink"], t)],
        ["bad", parse("var(--bad)", t)], ["neutral", parse(split["--split-neutral-ink"], t)],
      ];
      for (const [name, fg] of inks) for (const s of SURFACES) {
        expect(ratio(fg, over(fg, parse(`var(${s})`, t), TINT)), `${name} on ${s}`).toBeGreaterThanOrEqual(4.5);
      }
    });
    it(`a field's border meets 3:1 on the panel, the paper, and the page, ${scheme}`, () => {
      const edge = parse(split["--split-field-line"], t);
      for (const s of SURFACES) expect(ratio(edge, parse(`var(${s})`, t)), `the field edge on ${s}`).toBeGreaterThanOrEqual(3);
    });
  }

  it("the splitter's fields and badges use those tokens", () => {
    expect(SPLIT).toMatch(/\.split-view :is\(input, select, textarea\) \{[^}]*border: 1px solid var\(--split-field-line\)/);
    expect(SPLIT).toMatch(/\.split-view \.badge-good \{ color: var\(--split-good-ink\); \}/);
    expect(SPLIT).toMatch(/\.split-view \.badge-warn \{ color: var\(--split-warn-ink\); \}/);
    expect(SPLIT).toMatch(/\.split-view \.badge\.badge-neutral \{ color: var\(--split-neutral-ink\); \}/);
  });
});
