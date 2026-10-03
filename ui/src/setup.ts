import "@testing-library/jest-dom/vitest";

// Node 25 defines its own global `localStorage` (Web Storage without a backing file), which hides jsdom's and has no
// methods. Tests get a plain in-memory Storage in its place, so code that reads and writes it behaves as in a browser.
if (typeof globalThis.localStorage?.getItem !== "function") {
  const store = new Map<string, string>();
  const memory: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key) => (store.has(key) ? store.get(key)! : null),
    key: (i) => Array.from(store.keys())[i] ?? null,
    removeItem: (key) => void store.delete(key),
    setItem: (key, value) => void store.set(key, String(value)),
  };
  Object.defineProperty(globalThis, "localStorage", { value: memory, configurable: true, writable: true });
}
