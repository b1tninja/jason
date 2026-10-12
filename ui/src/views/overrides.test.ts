import { describe, expect, it } from "vitest";

/** The console review's style fixes (October 2026), read from the stylesheets themselves so a token or a rule changed there is measured
 * here: contrast of the badge, chip, button, and rail colours (WCAG 1.4.3, text 4.5:1; 1.4.11, an edge 3:1), and the rules that must
 * out-rank `styles.css` (a link button's text, a row header's case, the sticky bars). jsdom loads no CSS, so these read the files. */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

declare const process: { cwd(): string };
const read = (name: string) => {
  const at = [join(process.cwd(), "src", name), join(process.cwd(), "ui", "src", name)].find(existsSync);
  if (!at) throw new Error(`cannot find ${name} from ${process.cwd()}`);
  return new TextDecoder().decode(readFileSync(at));
};
const CONSOLE = read("styles.css");
const A11Y = read("styles/a11y.css");
const WORK = read("styles/work.css");
const ITEMS = read("styles/work-items.css");
const GUIDE = read("styles/work-guide.css");
const BAR = read("styles/approve-bar.css");

type Tokens = Record<string, string>;
type Rgb = [number, number, number];
const declarations = (block: string): Tokens => {
  const out: Tokens = {};
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
};
const light: Tokens = declarations(/:root\s*\{([^}]*)\}/.exec(CONSOLE)![1]);
const dark: Tokens = declarations(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}/.exec(CONSOLE)![1]);
/** The community theme's two accents (the checked-in profile's brand: `mystique/theme.py`, made of the design handoff's values). */
const THEMES: Record<string, { light: Tokens; dark: Tokens }> = {
  neutral: { light: {}, dark: {} },
  branded: { light: { "--accent": "#5b3f8f", "--on-accent": "#fff" }, dark: { "--accent": "#bba3ee", "--on-accent": "#1e1726" } },
};
const SCHEMES = (["light", "dark"] as const).flatMap((scheme) =>
  Object.entries(THEMES).map(([theme, t]) => [`${scheme}, ${theme}`, { ...light, ...(scheme === "dark" ? dark : {}), ...t[scheme] }, scheme] as const));

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
function parse(value: string, t: Tokens): Rgb {
  const v = value.trim();
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(v);
  const hex = /^#([0-9a-f]{6})$/i.exec(short ? `#${short[1]}${short[1]}${short[2]}${short[2]}${short[3]}${short[3]}` : v);
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)) as Rgb;
  const ref = /^var\((--[\w-]+)(?:\s*,\s*(.+))?\)$/.exec(v);
  if (ref) {
    const got = t[ref[1]] ?? (ref[2] !== undefined ? ref[2] : undefined);
    if (got === undefined) throw new Error(`no token ${ref[1]}`);
    return parse(got, t);
  }
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
const lin = (c: number) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
const lum = (c: Rgb) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
const ratio = (a: Rgb, b: Rgb) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
const over = (fg: Rgb, bg: Rgb, share: number): Rgb => [0, 1, 2].map((i) => Math.round(fg[i] * share + bg[i] * (1 - share))) as Rgb;
const SURFACES = ["--panel", "--paper", "--bg"];
const TINT = Number(/:root \.badge \{[^}]*background: color-mix\(in srgb, currentColor (\d+)%, transparent\)/.exec(CONSOLE)![1]) / 100;

/** the value of a property in the first rule whose selector contains `selector` */
function rule(css: string, selector: string, prop: string): string {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m = new RegExp(`${esc}\\s*\\{([^}]*)\\}`).exec(css);
  if (!m) throw new Error(`no rule for ${selector}`);
  const d = new RegExp(`(?:^|;|\\s)${prop}\\s*:\\s*([^;]+)`).exec(m[1]);
  if (!d) throw new Error(`${selector} has no ${prop}`);
  return d[1].trim();
}

describe("badges, chips, and stamps reach 4.5:1", () => {
  for (const [name, t] of SCHEMES) {
    it(`good, warning, and neutral badge text on its tint, on every surface (${name})`, () => {
      for (const tone of ["good", "warn", "neutral"]) {
        const fg = parse(rule(A11Y, `:root .badge.badge-${tone}`, "color"), t);
        for (const s of SURFACES) expect(ratio(fg, over(fg, parse(`var(${s})`, t), TINT)), `${tone} on ${s}`).toBeGreaterThanOrEqual(4.5);
      }
    });
    it(`a code chip inside a good, warning, or error notice (${name})`, () => {
      // the chip's text is its inherited colour mixed toward the ink: the worst case is the weakest status colour
      const mixed = rule(A11Y, ":root .chip, :root code.chip", "color");
      expect(mixed).toBe("color-mix(in srgb, currentColor 70%, var(--ink))");
      for (const c of ["--good", "--warn", "--bad", "--muted"]) {
        const fg = parse(`color-mix(in srgb, var(${c}) 70%, var(--ink))`, t);
        expect(ratio(fg, parse("var(--paper)", t)), `${c} chip on paper`).toBeGreaterThanOrEqual(4.5);
      }
    });
    it(`a stamp's small line at full opacity, on every surface (${name})`, () => {
      const colour: Record<string, string> = {
        good: rule(A11Y, ":root .stamp-good", "color"), warn: rule(A11Y, ":root .stamp-warn", "color"), bad: "var(--bad)", neutral: "var(--muted)",
      };
      for (const [tone, c] of Object.entries(colour)) for (const s of SURFACES)
        expect(ratio(parse(c, t), parse(`var(${s})`, t)), `${tone} on ${s}`).toBeGreaterThanOrEqual(4.5);
    });
  }
  it("a stamp is not faded, and its small line is not below 10px", () => {
    expect(rule(A11Y, ":root .stamp", "opacity")).toBe("1");
    expect(rule(A11Y, ":root .stamp-sub", "opacity")).toBe("1");
    expect(rule(A11Y, ":root .stamp-sub", "font-size")).toMatch(/^max\(10px,/);
  });
  it("a pending history entry is told by italics, not by fading its timestamp", () => {
    expect(rule(WORK, ".work-history-pending", "font-style")).toBe("italic");
    expect(WORK).not.toMatch(/\.work-history-pending\s*\{[^}]*opacity/);
  });
});

describe("buttons reach 4.5:1", () => {
  for (const [name, t, scheme] of SCHEMES) {
    it(`the primary fill and its text (${name})`, () => {
      const fillRule = scheme === "light" ? /:root\s*\{[^}]*--accent-fill:\s*([^;]+);/ : /:root\[data-scheme="dark"\]\s*\{[^}]*--accent-fill:\s*([^;]+);/;
      const fill = parse(fillRule.exec(A11Y)![1], t);
      const fallback = scheme === "light" ? "#fff" : "#10161f";
      expect(A11Y).toContain(`--on-fill: var(--on-accent, ${fallback})`);
      const text = parse(t["--on-accent"] ?? fallback, t);
      expect(ratio(text, fill)).toBeGreaterThanOrEqual(4.5);
    });
    it(`a primary button that cannot be pressed: muted text on the panel, and a dashed edge of 3:1 (${name})`, () => {
      const r = rule(A11Y, ":root button.primary:disabled, :root button.primary[aria-disabled=\"true\"]", "color");
      expect(r).toBe("var(--muted)");
      expect(ratio(parse("var(--muted)", t), parse("var(--panel)", t))).toBeGreaterThanOrEqual(4.5);
      expect(rule(A11Y, ":root button.primary:disabled, :root button.primary[aria-disabled=\"true\"]", "opacity")).toBe("1");
      expect(rule(A11Y, ":root button.primary:disabled, :root button.primary[aria-disabled=\"true\"]", "border")).toBe("1px dashed var(--muted)");
    });
    it(`the rail's selected step: its words on the tint, its 'current step' on the tint (${name})`, () => {
      const tint = over(parse("var(--accent)", t), parse("var(--panel)", t), 0.12);
      for (const c of ["var(--ink)", "var(--muted)", rule(WORK, ".work-rail-here", "color")])
        expect(ratio(parse(c, t), tint), c).toBeGreaterThanOrEqual(4.5);
      // the selected card keeps the page colours: ink on a tint, never the console's inverted pressed button
      const selected = ":root .work-rail-step button[aria-pressed=\"true\"]";
      expect(rule(WORK, selected, "color")).toBe("var(--ink)");
      expect(rule(WORK, selected, "background")).toBe("color-mix(in srgb, var(--accent) 12%, var(--panel))");
    });
  }
  it("the disabled primary button is not the accent at 60% opacity any more", () => {
    expect(CONSOLE).toMatch(/\.approve-bar button\[aria-disabled="true"\][^}]*opacity: \.6/);   // the rule it replaces is still there
    expect(A11Y).toMatch(/:root button\.primary\[aria-disabled="true"\] \{[^}]*opacity: 1/);       // and is out-ranked (0,3,1) over (0,2,1)
  });
});

describe("what must out-rank the console's styles", () => {
  it("a link button's text colour wins over `[data-community] a` and its hover, in every state", () => {
    expect(CONSOLE).toMatch(/\[data-community\] a \{ color: var\(--accent\)/);
    for (const state of ["", ":visited", ":hover", ":focus-visible"]) {
      expect(WORK).toContain(`:root a.work-btn.work-btn-primary${state}`);
      expect(WORK).toContain(`:root a.work-btn${state}`);
    }
    expect(WORK).toMatch(/:root a\.work-btn\.work-btn-primary:active \{ color: var\(--on-fill/);
    // the plain link button keeps the ink, and the whole-row link keeps its inherited colour
    expect(WORK).toMatch(/:root a\.work-btn:focus-visible \{ color: var\(--ink\); text-decoration: none; \}/);
    expect(WORK).toMatch(/:root a\.work-row-link:hover \{ color: inherit; \}/);
  });

  it("an item id is shown as stored: not upper-cased by the table head's label rule, with a row header the height of its cells", () => {
    expect(CONSOLE).toMatch(/:root :is\([^)]*\bth\b[^)]*\) \{[^}]*text-transform: uppercase/);        // the rule that upper-cased it
    const th = ":root .work-items-table.work-items-table tbody th";
    expect(rule(ITEMS, th, "text-transform")).toBe("none");
    expect(rule(ITEMS, th, "border-bottom")).toBe("1px solid var(--line)");
    expect(rule(ITEMS, th, "padding")).toBe(rule(ITEMS, ":root .work-items-table.work-items-table tbody td", "padding"));
    expect(rule(ITEMS, ":root .work-items-table.work-items-table tbody th code", "text-transform")).toBe("none");
    expect(rule(ITEMS, ".work-items-table caption", "text-align")).toBe("left");
  });

  it("the filters stack in one column on a phone and no select sets the page's width", () => {
    expect(WORK).toMatch(/\.work-filters select, \.work-filters input\[type="search"\] \{ max-width: 100%; min-width: 0; \}/);
    expect(WORK).toMatch(/@media \(max-width: 599px\) \{[^@]*form\.work-filters \{ display: grid; grid-template-columns: minmax\(0, 1fr\)/);
  });

  it("the guide's act row sticks only to a screen at least 600px wide and tall, and the 44px targets stay on a phone", () => {
    expect(GUIDE).toMatch(/@media \(min-width: 600px\) and \(max-width: 719px\) and \(min-height: 600px\) \{\s*\.guide-act-row \{ position: sticky/);
    // no rule sticks it below 600px: the old phone-wide sticky is gone
    expect(GUIDE).not.toMatch(/@media \(max-width: 719px\) \{\s*\.guide-act-row \{ position: sticky/);
    expect(GUIDE).toMatch(/@media \(max-width: 719px\) \{[^}]*\.guide-act-row button[^}]*min-height: 44px/);
  });

  it("the approve bar is capped where it sticks, two columns where wide, and its help is out of the way", () => {
    expect(BAR).toMatch(/@media \(min-height: 820px\) and \(min-width: 720px\) \{\s*:root \.approve-bar \{ max-height: min\(17rem, 34vh\); overflow: auto/);
    expect(BAR).toMatch(/@media \(min-width: 720px\) \{\s*:root \.approve-bar \{ grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\)/);
    // the sticky query it caps is the console's own: the same two bounds
    expect(CONSOLE).toMatch(/@media \(min-height: 820px\) and \(min-width: 720px\) \{ \.approve-bar \{ position: sticky/);
  });

  it("targets: a sort button, sign out, and the private-view switch are at least 24px", () => {
    expect(rule(A11Y, ":root table th > button", "min-height")).toBe("24px");
    expect(rule(A11Y, ":root .console-signin button, :root .private-switch > button", "min-height")).toBe("24px");
    expect(rule(A11Y, ":root .table-wrap caption", "text-align")).toBe("left");
    expect(rule(A11Y, ":root td .badge, :root th .badge", "white-space")).toBe("nowrap");
  });
});

describe("the second batch: links, outlines, and layout", () => {
  const OFFICE = read("styles/office-views.css");
  const CONTROLS = read("styles/controls.css");
  const ITEMS2 = read("styles/work-items.css");

  it("a proposed date is drawn dashed with a width, a law date with its heavy edge, out-ranking `:root .badge { border: 0 }`", () => {
    expect(CONSOLE).toMatch(/:root \.badge \{ border: 0;/);
    expect(WORK).toMatch(/:root \.badge\.basis-proposed \{ border: 1px dashed currentColor; \}/);
    expect(WORK).toMatch(/:root \.badge\.basis-law \{ border: 2px solid currentColor; \}/);
  });

  it("'Go to the step' is an accent link, underlined, with a ring on focus", () => {
    expect(WORK).toMatch(/:root \.work-changed button\.link \{[^}]*color: color-mix\(in srgb, var\(--accent\) 80%, var\(--ink\)\)[^}]*text-decoration: underline/);
    expect(WORK).toMatch(/:root \.work-changed button\.link:focus-visible \{ outline: 2px solid var\(--accent\)/);
  });

  for (const [name, t] of SCHEMES) {
    it(`the link colour in a notice and in a changed banner reaches 4.5:1 on the panel and the paper (${name})`, () => {
      const c = parse("color-mix(in srgb, var(--accent) 80%, var(--ink))", t);
      // the accent is the community's, so the check is on the plainly neutral and the branded accents of THEMES alone
      for (const s of ["--panel", "--paper", "--bg"]) expect(ratio(c, parse(`var(${s})`, t)), s).toBeGreaterThanOrEqual(4.5);
    });
    it(`a badge on the rail's selected step is the ink on the tint (${name})`, () => {
      expect(WORK).toMatch(/:root \.work-rail-step button\[aria-pressed="true"\] \.badge \{ color: var\(--ink\); \}/);
      const tint = over(parse("var(--accent)", t), parse("var(--panel)", t), 0.12);
      const ink = parse("var(--ink)", t);
      expect(ratio(ink, over(ink, tint, TINT))).toBeGreaterThanOrEqual(4.5);
    });
  }

  it("control links are scoped to the notice and the changed banner and take the accent", () => {
    expect(CONTROLS).toMatch(/:root :is\(\.control-notice, \.control-changed\) a \{ color: color-mix\(in srgb, var\(--accent\) 80%, var\(--ink\)\); text-decoration: underline/);
    expect(CONTROLS).toMatch(/:root :is\(\.control-notice, \.control-changed\) a:focus-visible \{ outline: 2px solid var\(--accent\)/);
  });

  it("the office banner keeps its button on the row until a phone", () => {
    expect(OFFICE).toMatch(/\.office-banner \{ display: flex; flex-wrap: nowrap;/);
    expect(OFFICE).toMatch(/@media \(max-width: 479px\) \{ \.office-banner \{ flex-wrap: wrap; \}/);
  });

  it("a remedy note is a grid with the glyph's own column, and a late mark has room before the date", () => {
    expect(ITEMS2).toMatch(/\.work-remedy \{ display: grid; grid-template-columns: auto minmax\(0, 1fr\);/);
    expect(ITEMS2).toMatch(/\.work-item-late \{[^}]*margin-left: \.5rem/);
  });
});
