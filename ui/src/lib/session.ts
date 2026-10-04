import { useCallback, useEffect, useMemo, useState } from "react";
import { actAs, closePrivate, getJson, openPrivate, serverSession, signInHref, signInLinks, signOut, type Acting, type PrivateOpenBody, type PrivateView, type ServerSession, type SignedIn, type SignInSetup } from "./api";

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
  privateView: PrivateView | null;
}

/** The browser-session flag that says the private view was just opened, so the band takes focus once after the reload. */
export const PRIVATE_OPENED_KEY = "jason-private-opened";

function takeOpened(): boolean {
  try {
    const was = sessionStorage.getItem(PRIVATE_OPENED_KEY) === "1";
    sessionStorage.removeItem(PRIVATE_OPENED_KEY);
    return was;
  } catch {
    return false;
  }
}

function markOpened(): void {
  try { sessionStorage.setItem(PRIVATE_OPENED_KEY, "1"); } catch { /* storage blocked: no focus move */ }
}

function reload(): void {
  try { window.location.reload(); } catch { /* not every window reloads (tests) */ }
}

/** The private view's acts for the console: open (`POST /api/private`) and close (`DELETE`), each followed by a full
 * reload, as viewing as someone else does, because every screen fetches on load; and the reload when it expires. A
 * refusal is thrown with the server's sentence for the form to say. */
export const privateActs = {
  open: async (body: PrivateOpenBody) => { await openPrivate(body); markOpened(); reload(); },
  close: async () => { await closePrivate(); reload(); },
  expired: () => reload(),
};

/** What the server says about sign-in: who signed in, whether it is set up, its last refusal (said once), under
 * `--dev` whom an admin may view the console as, and the private view (`privateView`; `privateFocus` once just after
 * it was opened). */
export function useSignIn() {
  const [state, setState] = useState<SignInState>({ account: null, error: "", canActAs: false, acting: null, actAsPeople: [], actAsRoles: [], privateView: null });
  const [privateFocus] = useState<boolean>(takeOpened);
  useEffect(() => {
    let on = true;
    serverSession().then((s) => on && setState({
      account: s.signedIn ?? null, setup: s.signIn, error: s.signInError ?? "", canActAs: !!s.canActAs,
      acting: s.acting ?? null, actAsPeople: s.actAsPeople ?? [], actAsRoles: s.actAsRoles ?? [],
      privateView: s.private ?? null,
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
  return { ...state, privateFocus, signInLinks: links, signOut: out, actAs: viewAs };
}

/** The name a write goes under, as `useSession` computes `me` (the person an admin views the console as, else who signed
 * in, else the name picked in this browser), without loading the officers. `enabled` false asks the server nothing. */
export function useMe(enabled = true): string {
  const [picked] = useState<string>(readMe);
  const [s, setS] = useState<ServerSession | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let on = true;
    serverSession().then((x) => { if (on) setS(x); });
    return () => { on = false; };
  }, [enabled]);
  return s?.acting ? s.acting.name : s?.signedIn?.name ?? picked;
}

/** Whether a person is signed in with Google on this server, for what needs a sign-in rather than a picked name: opening
 * a file or a document, or reading evidence again (`jason.web.access`). `known` is false until the server answers;
 * `href` is "Sign in with Google", back to this console route. `enabled` false asks the server nothing. */
export function useAccount(enabled = true): { account: SignedIn | null; known: boolean; configured: boolean; href: string } {
  const [s, setS] = useState<ServerSession | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let on = true;
    serverSession().then((x) => { if (on) setS(x); });
    return () => { on = false; };
  }, [enabled]);
  const hash = typeof window !== "undefined" ? window.location.hash : "";
  return { account: s?.signedIn ?? null, known: !!s, configured: !!s?.signIn?.configured, href: signInHref(s?.signIn, hash) };
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
    actAsRoles: signIn.actAsRoles, actAs: signIn.actAs, privateView: signIn.privateView, privateFocus: signIn.privateFocus,
  };
}
