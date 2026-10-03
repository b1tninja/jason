import { useCallback, useEffect, useMemo, useState } from "react";
import { getJson } from "./api";

/** The signed-in person. There is no real sign-in: this is a sample picker over the association's officers (from
 * `/api/approvals`), and the chosen name is what goes on the record (`by`) when the person approves or records a step.
 * The name is remembered per browser in localStorage (`jason-console-user`); the server checks every approval against
 * the profile's officers anyway, so picking a name here grants nothing. */

export interface Person { name: string; role: string; approves: string[]; canApproveBoard: boolean }

export const BOARD = "the board";
export const SESSION_KEY = "jason-console-user";

/** Whether `person` may approve for `approver`: "the board" only through the president or the secretary, who record
 * its vote at a meeting (CIV 4910); any other approver through the person whose `approves` names it. */
export function canApprove(person: string, approver: string, people: readonly Person[]): boolean {
  const p = people.find((x) => x.name === person);
  if (!p) return false;
  return approver === BOARD ? p.canApproveBoard : p.approves.includes(approver);
}

export function readMe(): string {
  try {
    return localStorage.getItem(SESSION_KEY) ?? "";
  } catch {
    return "";
  }
}

export function writeMe(name: string): void {
  try {
    if (name) localStorage.setItem(SESSION_KEY, name);
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    /* storage blocked: the pick lasts for the page */
  }
}

/** `people` comes from `/api/approvals` unless the caller passes the list it already loaded. */
export function useSession(given?: readonly Person[]) {
  const [me, setMeState] = useState<string>(readMe);
  const [fetched, setFetched] = useState<Person[]>([]);
  useEffect(() => {
    if (given) return;
    const ctl = new AbortController();
    getJson<{ people?: Person[] }>("/api/approvals", ctl.signal).then((d) => setFetched(d.people ?? []), () => setFetched([]));
    return () => ctl.abort();
  }, [given]);
  const people = useMemo(() => (given ? [...given] : fetched), [given, fetched]);
  const setMe = useCallback((name: string) => { setMeState(name); writeMe(name); }, []);
  const can = useCallback((approver: string) => canApprove(me, approver, people), [me, people]);
  return { me, setMe, people, canApprove: can };
}
