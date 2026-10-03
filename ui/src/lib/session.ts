import { useCallback, useEffect, useMemo, useState } from "react";
import { getJson, serverSession, signInHref, signOut, type SignedIn, type SignInSetup } from "./api";

/** The signed-in person. When the server has Google sign-in (`jason.web.signin`) and an officer signed in, `me` is that
 * officer, fixed by the server: every write goes on the record under that name. Otherwise it is a sample picker over
 * the association's officers (from `/api/approvals`), remembered per browser in localStorage (`jason-console-user`);
 * the server checks every approval against the profile's officers anyway, so picking a name grants nothing. */

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

/** What the server says about sign-in: who signed in, whether it is set up, and its last refusal (said once). */
export function useSignIn() {
  const [state, setState] = useState<{ account: SignedIn | null; setup?: SignInSetup; error: string }>({ account: null, error: "" });
  useEffect(() => {
    let on = true;
    serverSession().then((s) => on && setState({ account: s.signedIn ?? null, setup: s.signIn, error: s.signInError ?? "" }));
    return () => { on = false; };
  }, []);
  const href = state.setup?.configured ? signInHref(state.setup, typeof window !== "undefined" ? window.location.hash : "") : "";
  const out = useCallback(async () => {
    await signOut(state.setup);
    setState((s) => ({ ...s, account: null }));
  }, [state.setup]);
  return { account: state.account, setup: state.setup, error: state.error, signInHref: href, signOut: out };
}

/** `people` comes from `/api/approvals` unless the caller passes the list it already loaded. */
export function useSession(given?: readonly Person[]) {
  const [picked, setPicked] = useState<string>(readMe);
  const [fetched, setFetched] = useState<Person[]>([]);
  const signIn = useSignIn();
  useEffect(() => {
    if (given) return;
    const ctl = new AbortController();
    getJson<{ people?: Person[] }>("/api/approvals", ctl.signal).then((d) => setFetched(d.people ?? []), () => setFetched([]));
    return () => ctl.abort();
  }, [given]);
  const people = useMemo(() => (given ? [...given] : fetched), [given, fetched]);
  const me = signIn.account?.name ?? picked;
  const setMe = useCallback((name: string) => { setPicked(name); writeMe(name); }, []);
  const can = useCallback((approver: string) => canApprove(me, approver, people), [me, people]);
  return { me, setMe, people, canApprove: can, account: signIn.account, signInHref: signIn.signInHref, signInError: signIn.error, signOut: signIn.signOut };
}
