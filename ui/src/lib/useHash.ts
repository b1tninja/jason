import { useEffect, useState } from "react";

/** The view lives in the URL hash (#/board), so a reload and a shared link land on the same view. */
export function useHash(fallback: string): [string, (next: string) => void] {
  const read = () => (typeof window === "undefined" ? fallback : window.location.hash.replace(/^#\/?/, "") || fallback);
  const [hash, setHash] = useState(read);
  useEffect(() => {
    const on = () => setHash(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [hash, (next) => (window.location.hash = `/${next}`)];
}
