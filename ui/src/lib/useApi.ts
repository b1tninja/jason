import { useCallback, useEffect, useState } from "react";
import { forView, getJson } from "./api";

export type Remote<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

/** A read of `path`, again on `reload`. In the owner view the read carries `view=owner` (`forView`), and the URL with
 * it is the key, so switching between the Board and the Owner view reads again. */
export function useApi<T>(path: string): Remote<T> & { reload: () => void } {
  const [state, setState] = useState<Remote<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  const url = forView(path);
  useEffect(() => {
    const ctl = new AbortController();
    setState({ status: "loading" });
    getJson<T>(url, ctl.signal).then(
      (data) => setState({ status: "ready", data }),
      (e: Error) => e.name !== "AbortError" && setState({ status: "error", error: e.message }),
    );
    return () => ctl.abort();
  }, [url, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
