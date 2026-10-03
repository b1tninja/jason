import { useEffect, useState } from "react";
import { getJson } from "./api";

/** What `/api/theme` answers: the profile's brand tokens by scheme (names without the `--`), the public page's surface
 * layer, and the font stylesheet the page may load. `found: false` is jason's neutral look: nothing is applied. */
export interface ThemeData {
  found: boolean;
  slug: string;
  wordmark: string;
  light: Record<string, string>;
  dark: Record<string, string>;
  surface: Record<string, string>;
  surfaceDark: Record<string, string>;
  fontUrl: string;
}

export const THEME_STYLE_ID = "jason-theme";
export const THEME_FONT_ID = "jason-theme-font";

const decl = (tokens: Record<string, string>) =>
  Object.entries(tokens).filter(([, v]) => v).map(([k, v]) => `--${k}:${v}`).join(";");

/** The stylesheet for one theme, scoped to `[data-community="<slug>"]` the way `themes/<slug>.css` is: the brand layer
 * always on, dark values under `prefers-color-scheme: dark` unless `data-scheme="light"` pins light, and again under
 * `data-scheme="dark"`; the surface layer only where `data-reach="full"` opts in (the public owner page). */
export function themeCss(t: ThemeData): string {
  if (!t.found || !t.slug) return "";
  const root = `[data-community="${t.slug}"]`;
  const out: string[] = [];
  if (Object.keys(t.light).length) out.push(`${root}{${decl(t.light)}}`);
  const dark = decl(t.dark);
  if (dark) {
    out.push(`@media (prefers-color-scheme:dark){${root}:not([data-scheme="light"]){${dark}}}`);
    out.push(`${root}[data-scheme="dark"]{${dark}}`);
  }
  const surface = decl(t.surface);
  if (surface) out.push(`${root}[data-reach="full"]{color-scheme:light;${surface}}`);
  const surfaceDark = decl(t.surfaceDark);
  if (surfaceDark) {
    out.push(`@media (prefers-color-scheme:dark){${root}[data-reach="full"]:not([data-scheme="light"]){color-scheme:dark;${surfaceDark}}}`);
    out.push(`${root}[data-reach="full"][data-scheme="dark"]{color-scheme:dark;${surfaceDark}}`);
  }
  return out.join("\n");
}

/** Put the theme on the document: `data-community` on the root, one `<style>`, and the font link. Idempotent; a theme
 * that is not found removes what an earlier one set. Every step is guarded: no document, no theme, no-op. */
export function applyTheme(t: ThemeData | null): void {
  try {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    const style = (document.getElementById(THEME_STYLE_ID) as HTMLStyleElement | null) ?? Object.assign(document.createElement("style"), { id: THEME_STYLE_ID });
    if (!style.parentNode) document.head.appendChild(style);
    if (!t || !t.found || !t.slug) {
      root.removeAttribute("data-community");
      style.textContent = "";
      document.getElementById(THEME_FONT_ID)?.remove();
      return;
    }
    root.setAttribute("data-community", t.slug);
    style.textContent = themeCss(t);
    const old = document.getElementById(THEME_FONT_ID) as HTMLLinkElement | null;
    if (t.fontUrl) {
      const link = old ?? Object.assign(document.createElement("link"), { id: THEME_FONT_ID, rel: "stylesheet" });
      if (link.href !== t.fontUrl) link.href = t.fontUrl;
      if (!link.parentNode) document.head.appendChild(link);
    } else old?.remove();
  } catch {
    /* a blocked document or stylesheet leaves the neutral look */
  }
}

/** Fetch `/api/theme` once and apply it. Returns the theme (for the wordmark) or null while loading or when none. */
export function useTheme(): ThemeData | null {
  const [theme, setTheme] = useState<ThemeData | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<ThemeData>("/api/theme", ctl.signal).then(
      (t) => { applyTheme(t); setTheme(t); },
      () => { /* no theme endpoint: the neutral look stays */ },
    );
    return () => ctl.abort();
  }, []);
  return theme;
}
