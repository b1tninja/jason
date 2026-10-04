/// <reference types="vite/client" />
import { describe, expect, it } from "vitest";
import allow from "./docrefs.allowlist.json";

/* The guard on the screens (docs/console/doc-component.md): a screen shows a document with `Doc`, fed a `DocRef`, never
 * a raw `/api/file?path=` URL, a Google link built by hand, or an iframe. It scans every view (`src/views/**`), test
 * files aside (a test may name a pattern to assert it is absent), and fails on any occurrence beyond
 * docrefs.allowlist.json, and on an entry whose count fell, so the list only shrinks as the fan-out groups move each
 * screen to `Doc`. */

const sources = import.meta.glob("../views/**/*.tsx", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

type Entry = { file: string; pattern: string; count: number; group: string; where: string };

function count(text: string, pattern: string): number {
  let n = 0;
  for (let at = text.indexOf(pattern); at >= 0; at = text.indexOf(pattern, at + pattern.length)) n += 1;
  return n;
}

describe("the screens' document links", () => {
  const found: Record<string, number> = {};
  for (const [path, text] of Object.entries(sources)) {
    if (/\.test\.tsx$/.test(path)) continue;
    const file = path.replace(/^\.\.\/views\//, "");
    for (const pattern of allow.patterns) {
      const n = count(text, pattern);
      if (n) found[`${file}\n${pattern}`] = n;
    }
  }
  const allowed = new Map((allow.entries as Entry[]).map((e) => [`${e.file}\n${e.pattern}`, e]));

  it("scans the views", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20);
  });

  it("holds no new raw document link: use <Doc> with the loader's DocRef", () => {
    const extra = Object.entries(found)
      .filter(([key, n]) => n > (allowed.get(key)?.count ?? 0))
      .map(([key, n]) => `${key.replace("\n", ": ")} (${n}, allowed ${allowed.get(key)?.count ?? 0})`);
    expect(extra).toEqual([]);
  });

  it("the allowlist only shrinks: lower an entry once its screen moved to Doc", () => {
    const stale = (allow.entries as Entry[])
      .filter((e) => (found[`${e.file}\n${e.pattern}`] ?? 0) < e.count)
      .map((e) => `${e.file}: ${e.pattern} (${found[`${e.file}\n${e.pattern}`] ?? 0} now, ${e.count} listed; ${e.group})`);
    expect(stale).toEqual([]);
  });

  it("names the group that removes each entry", () => {
    const groups = ["Mail", "Meetings", "Money", "Board", "Requests and links"];
    expect((allow.entries as Entry[]).filter((e) => !groups.includes(e.group) || !e.where)).toEqual([]);
  });
});
