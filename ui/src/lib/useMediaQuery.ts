import { useCallback, useSyncExternalStore } from "react";

/** A phone's width: the console's one narrow breakpoint (styles.css, `max-width: 719px`). */
export const PHONE_QUERY = "(max-width: 719px)";

const list = (query: string): MediaQueryList | null =>
  typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(query) : null;

/** Whether `query` matches now, following changes. False on the server, in a test without `matchMedia`, and when
 * `enabled` is false (nothing is subscribed then). */
export function useMediaQuery(query: string, enabled = true): boolean {
  const subscribe = useCallback((on: () => void) => {
    const m = enabled ? list(query) : null;
    if (!m) return () => {};
    if (typeof m.addEventListener === "function") {
      m.addEventListener("change", on);
      return () => m.removeEventListener("change", on);
    }
    m.addListener?.(on);   // older Safari
    return () => m.removeListener?.(on);
  }, [query, enabled]);
  return useSyncExternalStore(subscribe, () => (enabled ? list(query)?.matches ?? false : false), () => false);
}
