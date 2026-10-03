import { useCallback, useEffect, useMemo, useState } from "react";
import { actAs, getJson, serverSession, signInLinks, signOut, type Acting, type SignedIn, type SignInSetup } from "./api";

/** The signed-in person. When the server has Google sign-in (`jason.web.signin`) and an officer signed in, `me` is that
 * officer, fixed by the server: every write goes on the record under that name. Under `jason-web --dev`, a signed-in
 * admin may view the console as another person or an office (`acting`); `me` is then that person (empty for an
 * office alone) and the server refuses every write until they go back to themselves. Otherwise it is a sample picker
 * over the association's officers (from `/api/approvals`), remembered per browser in localStorage
 * (`jason-console-user`); the server checks every approval against the profile's officers anyway, so picking a name
 * grants nothing. */

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

interface SignInState {
  account: SignedIn | null; setup?: SignInSetup; error: string;
  canActAs: boolean; acting: Acting | null; actAsPeople: { name: string; role: string }[]; actAsRoles: string[];
}

/** What the server says about sign-in: who signed in, whether it is set up, its last refusal (said once), and under
 * `--dev` whom an admin may view the console as. */
export function useSignIn() {
  const [state, setState] = useState<SignInState>({ account: null, error: "", canActAs: false, acting: null, actAsPeople: [], actAsRoles: [] });
  useEffect(() => {
    let on = true;
    serverSession().then((s) => on && setState({
      account: s.signedIn ?? null, setup: s.signIn, error: s.signInError ?? "", canActAs: !!s.canActAs,
      acting: s.acting ?? null, actAsPeople: s.actAsPeople ?? [], actAsRoles: s.actAsRoles ?? [],
    }));
    return () => { on = false; };
  }, []);
  const links = signInLinks(state.setup, typeof window !== "undefined" ? window.location.hash : "");
  const out = useCallback(async () => {
    await signOut(state.setup);
    setState((s) => ({ ...s, account: null, acting: null, canActAs: false }));
  }, [state.setup]);
  const viewAs = useCallback(async (target: { name?: string; role?: string }) => {
    const acting = await actAs(state.setup, target);
    setState((s) => ({ ...s, acting }));
  }, [state.setup]);
  return { ...state, signInLinks: links, signOut: out, actAs: viewAs };
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
  const me = signIn.acting ? signIn.acting.name : signIn.account?.name ?? picked;
  const setMe = useCallback((name: string) => { setPicked(name); writeMe(name); }, []);
  const can = useCallback((approver: string) => canApprove(me, approver, people), [me, people]);
  return {
    me, setMe, people, canApprove: can, account: signIn.account, signInLinks: signIn.signInLinks, signInError: signIn.error,
    signOut: signIn.signOut, acting: signIn.acting, canActAs: signIn.canActAs, actAsPeople: signIn.actAsPeople,
    actAsRoles: signIn.actAsRoles, actAs: signIn.actAs,
  };
}
