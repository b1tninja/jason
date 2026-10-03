import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";

export type Remote<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

export function useApi<T>(path: string): Remote<T> & { reload: () => void } {
  const [state, setState] = useState<Remote<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    setState({ status: "loading" });
    getJson<T>(path, ctl.signal).then(
      (data) => setState({ status: "ready", data }),
      (e: Error) => e.name !== "AbortError" && setState({ status: "error", error: e.message }),
    );
    return () => ctl.abort();
  }, [path, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
