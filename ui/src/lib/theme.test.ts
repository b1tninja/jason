import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, themeCss, THEME_FONT_ID, THEME_STYLE_ID, type ThemeData } from "./theme";

const sample: ThemeData = {
  found: true, slug: "sample-commons", wordmark: "Sample Commons",
  light: { accent: "#2f6b55", "on-accent": "#fff", "brand-font": '"Sample Serif", serif', "brand-case": "uppercase" },
  dark: { accent: "#7fcba8", "on-accent": "#10241c", "brand-font": '"Sample Serif", serif', "brand-case": "uppercase" },
  surface: { bg: "#f6f3ee", panel: "#fffdfa", radius: "14px" },
  surfaceDark: { bg: "#15111b", panel: "#1e1926" },
  fontUrl: "https://fonts.example/css2?family=Sample+Serif",
};

afterEach(() => applyTheme(null));

describe("themeCss", () => {
  it("scopes the brand to [data-community], pins dark values, and keeps the surface behind data-reach=full", () => {
    const css = themeCss(sample);
    expect(css).toContain('[data-community="sample-commons"]{--accent:#2f6b55;--on-accent:#fff;');
    expect(css).toContain('@media (prefers-color-scheme:dark){[data-community="sample-commons"]:not([data-scheme="light"]){--accent:#7fcba8;--on-accent:#10241c;');
    expect(css).toContain('[data-community="sample-commons"][data-scheme="dark"]{--accent:#7fcba8;');
    expect(css).toContain('[data-community="sample-commons"][data-reach="full"]{color-scheme:light;--bg:#f6f3ee;--panel:#fffdfa;--radius:14px}');
    expect(css).toContain('[data-community="sample-commons"][data-reach="full"][data-scheme="dark"]{color-scheme:dark;--bg:#15111b;');
    expect(css).not.toMatch(/\[data-community="sample-commons"\]\{[^}]*--bg/); // the surface never leaks into the brand layer
  });

  it("is empty for a profile without a theme", () => {
    expect(themeCss({ ...sample, found: false })).toBe("");
  });
});

describe("applyTheme", () => {
  it("sets data-community, one style element, and the font link; a missing theme clears them", () => {
    applyTheme(sample);
    expect(document.documentElement.getAttribute("data-community")).toBe("sample-commons");
    expect(document.getElementById(THEME_STYLE_ID)?.textContent).toContain("--accent:#2f6b55");
    expect((document.getElementById(THEME_FONT_ID) as HTMLLinkElement).href).toBe(sample.fontUrl);
    applyTheme(sample);
    expect(document.querySelectorAll(`#${THEME_STYLE_ID}`).length).toBe(1);
    applyTheme({ ...sample, found: false });
    expect(document.documentElement.hasAttribute("data-community")).toBe(false);
    expect(document.getElementById(THEME_STYLE_ID)?.textContent).toBe("");
    expect(document.getElementById(THEME_FONT_ID)).toBeNull();
  });
});
